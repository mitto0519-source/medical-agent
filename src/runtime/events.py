"""Event Sourcing — 모든 시스템 동작 append-only 기록 (SQLite, WAL).

용도:
  - 환각/오작동 발생 시 replay로 정확한 시점·원인 추적
  - LLM 호출(prompt_hash·model·tokens), 메모리 쓰기, 작업 상태 전이, 도구 호출 감사
  - "본문에 없던 숫자가 어느 호출에서 처음 등장?" 같은 추적 가능

API:
  events.append(type, payload, task_id=None, parent_event_id=None, actor=None) -> event_id
  events.recent(n=50, type=None) -> list[dict]
  events.replay(task_id) -> list[dict]  (시간순)
  events.find(predicate_kwargs) -> list[dict]

설계:
  - INSERT만 허용(UPDATE/DELETE 금지) — 감사 무결성
  - WAL 모드 + busy_timeout으로 다중 프로세스 동시 쓰기 안전
  - payload는 JSON 텍스트 (정렬 키로 빠른 prefix 검색 가능)
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterable

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DB_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "events.db"
_LOCAL = threading.local()


def _conn() -> sqlite3.Connection:
    """스레드별 connection (sqlite3은 connection을 스레드 간 공유 못 함)."""
    c = getattr(_LOCAL, "conn", None)
    if c is not None:
        try:
            c.execute("SELECT 1")
            return c
        except sqlite3.ProgrammingError:
            pass  # 닫힘 → 재생성
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=15, isolation_level=None)  # autocommit
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=10000")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            task_id TEXT,
            parent_event_id INTEGER,
            actor TEXT,
            type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            state_before_hash TEXT,
            state_after_hash TEXT
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS ix_events_task ON events(task_id, id)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_events_type_ts ON events(type, ts)")
    c.execute("CREATE INDEX IF NOT EXISTS ix_events_ts ON events(ts)")
    # ★ MEMORY_HARDENING_SPEC §1 기법 ① — 서버리스 내용기반 수렴 (memorize 이식)
    # dedup_key = sha256(actor+type+payload_canonical). 두 머신이 같은 사건을 독립 기록해도
    # 같은 hash → Supabase 없이도 자연스럽게 dedup.
    try:
        c.execute("ALTER TABLE events ADD COLUMN dedup_key TEXT")
    except Exception:
        pass  # 이미 존재
    c.execute("CREATE INDEX IF NOT EXISTS ix_events_dedup ON events(dedup_key)")
    _LOCAL.conn = c
    return c


def _compute_dedup_key(type: str, payload: Any, actor: str | None) -> str:
    """내용 결정론 hash — 같은 (type, actor, payload) 이면 같은 key."""
    import hashlib
    canon = json.dumps(
        {"t": type, "a": actor or "", "p": payload if payload is not None else None},
        ensure_ascii=False, sort_keys=True, default=str,
    )
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:32]


def append(
    type: str,
    payload: Any = None,
    task_id: str | None = None,
    parent_event_id: int | None = None,
    actor: str | None = None,
    state_before_hash: str | None = None,
    state_after_hash: str | None = None,
    *,
    dedup_window_sec: float | None = None,
) -> int:
    """이벤트 append. 실패해도 호출자 망가지지 않게 swallow (감사용은 부수효과).

    dedup_window_sec: 지정 시 같은 dedup_key가 그 시간 내에 있으면 INSERT skip, 기존 id 반환.
                       기본 None = 항상 INSERT (기존 동작 유지, 하위호환).
    """
    try:
        c = _conn()
        dk = _compute_dedup_key(type, payload, actor)
        if dedup_window_sec is not None and dedup_window_sec > 0:
            existing = c.execute(
                "SELECT id FROM events WHERE dedup_key=? AND ts >= ? ORDER BY id DESC LIMIT 1",
                (dk, time.time() - dedup_window_sec)
            ).fetchone()
            if existing:
                return int(existing[0])
        cur = c.execute(
            "INSERT INTO events(ts, task_id, parent_event_id, actor, type, payload_json, "
            "state_before_hash, state_after_hash, dedup_key) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (
                time.time(), task_id, parent_event_id, actor, type,
                json.dumps(payload, ensure_ascii=False, default=str) if payload is not None else "null",
                state_before_hash, state_after_hash, dk,
            ),
        )
        return int(cur.lastrowid or 0)
    except Exception as e:
        _log.debug("events.append 실패 (무시): %s", e)
        return -1


def _row_to_dict(row: tuple) -> dict:
    return {
        "id": row[0], "ts": row[1], "task_id": row[2], "parent_event_id": row[3],
        "actor": row[4], "type": row[5],
        "payload": json.loads(row[6]) if row[6] else None,
        "state_before_hash": row[7], "state_after_hash": row[8],
    }


def recent(n: int = 50, type: str | None = None) -> list[dict]:
    c = _conn()
    if type:
        rows = c.execute("SELECT * FROM events WHERE type=? ORDER BY id DESC LIMIT ?", (type, n)).fetchall()
    else:
        rows = c.execute("SELECT * FROM events ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def replay(task_id: str) -> list[dict]:
    c = _conn()
    rows = c.execute("SELECT * FROM events WHERE task_id=? ORDER BY id ASC", (task_id,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def find(type: str | None = None, actor: str | None = None,
         since_ts: float | None = None, limit: int = 200) -> list[dict]:
    c = _conn()
    sql = "SELECT * FROM events WHERE 1=1"
    params: list = []
    if type:
        sql += " AND type=?"; params.append(type)
    if actor:
        sql += " AND actor=?"; params.append(actor)
    if since_ts:
        sql += " AND ts>=?"; params.append(since_ts)
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(limit)
    return [_row_to_dict(r) for r in c.execute(sql, tuple(params)).fetchall()]


def count(type: str | None = None) -> int:
    c = _conn()
    if type:
        return c.execute("SELECT COUNT(*) FROM events WHERE type=?", (type,)).fetchone()[0]
    return c.execute("SELECT COUNT(*) FROM events").fetchone()[0]


@contextmanager
def span(type: str, payload: Any = None, **kw):
    """이벤트 span — try 블록 진입/종료를 한 쌍으로 기록.

    with events.span("llm_call", {"model":"opus"}) as eid:
        result = client.generate(...)
        events.append("llm_call_done", {"tokens": tokens}, parent_event_id=eid)
    """
    eid = append(type, payload, **kw)
    try:
        yield eid
    except Exception as e:
        append(f"{type}_error", {"error": str(e)[:300]}, parent_event_id=eid, **{k: v for k, v in kw.items() if k != "type"})
        raise
