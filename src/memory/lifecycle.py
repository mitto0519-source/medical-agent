"""Memory Lifecycle — TTL 만료, confidence decay, contradiction resolution.

대상: router가 SQLite events("memory_episodic")로 저장한 항목 + procedural rules.json + goals.json.
ChromaDB(semantic)는 컬렉션별 TTL/archive를 lifecycle.tick() 정기 실행으로 관리.

API:
  tick() -> {decayed, archived, expired, conflicts_resolved}  # heartbeat에서 일일 호출
  resolve_conflict(new_item_text, neighbors) -> {action, supersedes}  # router가 write 전 호출
  archive_old(window_days=180)  # 오래된 항목 archive 테이블로 이동

설계:
  - decay rate: 일별 곱연산 (예: 0.998 → 1년 후 confidence ~70%)
  - archive: 삭제 안 함, archive 테이블로 이동(복구 가능)
  - contradiction: 같은 entity·다른 fact (휴리스틱 + 옵션 cheap LLM)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Iterable

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)
_DB_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "lifecycle.db"
_AGENT_DIR = Path(os.environ.get("AGENT_SELF_DIR", "data/agent_self"))
_LOCAL = threading.local()

DECAY_PER_DAY = 0.998   # 약 1년 후 confidence ~70%, 2년 후 ~48%
ARCHIVE_THRESHOLD = 0.20
DEFAULT_TTL_DAYS = 365


def _conn() -> sqlite3.Connection:
    c = getattr(_LOCAL, "conn", None)
    if c is not None:
        try: c.execute("SELECT 1"); return c
        except sqlite3.ProgrammingError: pass
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=15, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=10000")
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS items (
            id TEXT PRIMARY KEY,             -- "ep:42" / "sem:coll:abc"
            type TEXT NOT NULL,
            source TEXT,
            text TEXT NOT NULL,
            confidence REAL NOT NULL DEFAULT 0.7,
            created_at REAL NOT NULL,
            last_validated_at REAL NOT NULL,
            expires_at REAL,
            supersedes TEXT                  -- JSON list of superseded ids
        );
        CREATE INDEX IF NOT EXISTS ix_items_type ON items(type, last_validated_at);
        CREATE INDEX IF NOT EXISTS ix_items_conf ON items(confidence);

        CREATE TABLE IF NOT EXISTS archive (
            id TEXT PRIMARY KEY,
            type TEXT, source TEXT, text TEXT,
            archived_at REAL NOT NULL,
            reason TEXT,
            confidence REAL,
            data_json TEXT
        );
        """
    )
    _LOCAL.conn = c
    return c


def register(item_id: str, type: str, text: str, source: str = "observation",
             confidence: float = 0.7, ttl_days: int | None = DEFAULT_TTL_DAYS) -> None:
    """라우터에서 저장 직후 호출 — lifecycle 추적 시작."""
    now = time.time()
    expires_at = (now + ttl_days * 86400) if ttl_days else None
    try:
        _conn().execute(
            "INSERT OR REPLACE INTO items(id, type, source, text, confidence, created_at, last_validated_at, expires_at, supersedes) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (item_id, type, source, text, confidence, now, now, expires_at, "[]"),
        )
    except Exception as e:
        _log.debug("lifecycle.register 실패: %s", e)


def revalidate(item_id: str, boost: float = 0.05) -> None:
    """항목이 다시 retrieve되거나 재확인되면 confidence 회복 + last_validated 갱신."""
    now = time.time()
    c = _conn()
    row = c.execute("SELECT confidence FROM items WHERE id=?", (item_id,)).fetchone()
    if row:
        new_conf = min(1.0, row[0] + boost)
        c.execute("UPDATE items SET confidence=?, last_validated_at=? WHERE id=?", (new_conf, now, item_id))


def _days_since(ts: float) -> float:
    return max(0.0, (time.time() - ts) / 86400.0)


def tick(decay_per_day: float = DECAY_PER_DAY,
         archive_threshold: float = ARCHIVE_THRESHOLD) -> dict:
    """일일 호출용. confidence decay + 만료(expires_at) + 임계값 미만 archive."""
    c = _conn()
    now = time.time()
    decayed = 0; archived = 0; expired = 0
    for row in c.execute("SELECT id, confidence, last_validated_at, expires_at FROM items").fetchall():
        iid, conf, lva, exp = row
        new_conf = conf * (decay_per_day ** _days_since(lva))
        reason = None
        if exp is not None and exp < now:
            reason = "expired_ttl"; expired += 1
        elif new_conf < archive_threshold:
            reason = "low_confidence"; archived += 1
        if reason:
            _archive(iid, reason)
        else:
            if abs(new_conf - conf) > 0.001:
                c.execute("UPDATE items SET confidence=? WHERE id=?", (new_conf, iid))
                decayed += 1

    out = {"decayed": decayed, "archived": archived, "expired": expired}
    _events.append("lifecycle_tick", out, actor="lifecycle")
    return out


def _archive(item_id: str, reason: str) -> None:
    c = _conn()
    row = c.execute("SELECT id, type, source, text, confidence FROM items WHERE id=?", (item_id,)).fetchone()
    if not row:
        return
    c.execute(
        "INSERT OR REPLACE INTO archive(id, type, source, text, archived_at, reason, confidence, data_json) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (row[0], row[1], row[2], row[3], time.time(), reason, row[4], "{}"),
    )
    c.execute("DELETE FROM items WHERE id=?", (item_id,))


# ── Contradiction Resolution ─────────────────────────────────────────────────

# 단순 entity 추출 (대문자 시작 명사구 + 한글 명사 후보 — 휴리스틱)
import re as _re
_ENTITY = _re.compile(r"[A-Z][A-Za-z][A-Za-z\-]+|[가-힣]{2,}")


def _entities(text: str) -> set[str]:
    return {m.group(0) for m in _ENTITY.finditer(text or "")}


def _numeric_tokens(text: str) -> set[str]:
    # 천단위 콤마(50,972), 소수(1.04), %(5.4%), p값까지 — 통계 충돌 감지에 필요
    return set(_re.findall(r"\d{1,3}(?:,\d{3})+|\d+\.\d+|\d+%|p\s*[=<]\s*0?\.\d+", text or ""))


def detect_contradiction(new_text: str, existing_text: str) -> bool:
    """휴리스틱: 공통 entity ≥1 AND 다른 숫자 토큰 존재 → 잠재 충돌."""
    e_new = _entities(new_text); e_old = _entities(existing_text)
    if len(e_new & e_old) < 1:
        return False
    n_new = _numeric_tokens(new_text); n_old = _numeric_tokens(existing_text)
    if n_new and n_old and (n_new != n_old) and (n_new & n_old != n_new | n_old):
        return True
    return False


def resolve_conflict(new_text: str, new_source: str, neighbors: Iterable[tuple]) -> dict:
    """neighbors = [(neighbor_id, neighbor_text, confidence), ...]
    반환: {action, supersedes_ids} — router가 신규 저장 시 메타에 supersedes 기록.
    """
    supersede: list[str] = []
    new_trust = {"user": 1.0, "verified": 0.95, "rule": 0.95, "human": 1.0,
                 "reflection": 0.85, "observation": 0.75,
                 "llm": 0.55, "auto_learn": 0.45}.get(new_source, 0.5)
    for nid, ntext, nconf in neighbors:
        if detect_contradiction(new_text, ntext):
            # 신규의 trust × 1.0 vs 기존 confidence — 신규가 강하면 supersede
            if new_trust >= (nconf + 0.1):
                supersede.append(nid)
                # 기존 confidence 깎기
                try:
                    _conn().execute("UPDATE items SET confidence=confidence*0.5 WHERE id=?", (nid,))
                except Exception:
                    pass
    if supersede:
        _events.append("contradiction_resolved", {"new_source": new_source, "supersedes": supersede},
                       actor="lifecycle")
        return {"action": "supersede", "supersedes_ids": supersede}
    return {"action": "coexist", "supersedes_ids": []}


def stats() -> dict:
    c = _conn()
    n_items = c.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    n_arch = c.execute("SELECT COUNT(*) FROM archive").fetchone()[0]
    avg = c.execute("SELECT AVG(confidence) FROM items").fetchone()[0] or 0.0
    return {"items": n_items, "archived": n_arch, "avg_confidence": round(avg, 3)}
