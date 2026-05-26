"""Physician Review Queue — 임상 의사결정 단어 포함 산출물을 검토 큐로.

차단 패턴(자동 큐잉):
  - "처방"/"prescribe"/"treatment recommendation"
  - "진단"/"diagnosis"/"diagnose"
  - "복용량"/"dosage"/"dose"
  - "환자 진료"/"clinical management"
  - 그 외 사용자 정의 keyword

큐 상태: pending → approved | rejected | escalated
저장: SQLite (data/runtime/physician_review.db)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import time
import uuid
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)
_DB_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "physician_review.db"
_LOCAL = threading.local()

# 검토 필수 키워드 (한·영)
_REVIEW_KEYWORDS = re.compile(
    r"\b(prescrib(?:e|ing|ed)|diagnos(?:e|is|ing)|dosage|dose\s+of|"
    r"treatment\s+recommend(?:ation)?|clinical\s+management|"
    r"recommend\s+(?:a\s+)?(?:medication|drug|surgery))\b"
    r"|(처방|진단|복용량|용량.{0,3}투여|투약|환자.{0,3}진료|임상.{0,3}결정|"
    r"치료.{0,3}권고|수술.{0,3}권고)",
    re.IGNORECASE,
)


def _conn() -> sqlite3.Connection:
    c = getattr(_LOCAL, "conn", None)
    if c is not None:
        try: c.execute("SELECT 1"); return c
        except sqlite3.ProgrammingError: pass
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=15, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute(
        """CREATE TABLE IF NOT EXISTS review_queue (
            id TEXT PRIMARY KEY,
            ts REAL NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            owner_email TEXT,
            content TEXT NOT NULL,
            triggers_json TEXT,
            source TEXT,
            reviewer TEXT,
            reviewed_at REAL,
            decision_note TEXT
        )"""
    )
    c.execute("CREATE INDEX IF NOT EXISTS ix_review_status ON review_queue(status, ts)")
    _LOCAL.conn = c
    return c


def review_required(text: str) -> tuple:
    """텍스트에 임상 의사결정 키워드가 있나 → (필요여부, 매칭된 키워드 list)."""
    if not text:
        return (False, [])
    matches = [m.group(0) for m in _REVIEW_KEYWORDS.finditer(text)]
    return (bool(matches), matches[:10])


def queue_for_review(content: str, *, source: str = "llm",
                     owner_email: str = "", auto_check: bool = True) -> dict:
    """검토 큐에 추가. auto_check=True면 키워드 없으면 큐 안 함."""
    if auto_check:
        needed, triggers = review_required(content)
        if not needed:
            return {"queued": False, "reason": "no_clinical_keyword"}
    else:
        triggers = []

    rid = uuid.uuid4().hex[:16]
    _conn().execute(
        "INSERT INTO review_queue(id, ts, status, owner_email, content, triggers_json, source) "
        "VALUES (?,?,?,?,?,?,?)",
        (rid, time.time(), "pending", owner_email, content[:5000],
         json.dumps(triggers, ensure_ascii=False), source),
    )
    _events.append("physician_review_queued",
                   {"id": rid, "triggers": triggers, "source": source,
                    "owner": owner_email, "content_preview": content[:120]},
                   actor="safety.physician_review")
    return {"queued": True, "id": rid, "triggers": triggers}


def get_pending(owner_email: str | None = None, limit: int = 50) -> list:
    sql = "SELECT id, ts, owner_email, content, triggers_json, source FROM review_queue WHERE status='pending'"
    params: list = []
    if owner_email:
        sql += " AND owner_email=?"; params.append(owner_email)
    sql += " ORDER BY ts ASC LIMIT ?"; params.append(limit)
    return [{"id": r[0], "ts": r[1], "owner_email": r[2], "content": r[3],
             "triggers": json.loads(r[4] or "[]"), "source": r[5]}
            for r in _conn().execute(sql, tuple(params)).fetchall()]


def _decide(rid: str, status: str, reviewer: str, note: str) -> bool:
    c = _conn()
    cur = c.execute(
        "UPDATE review_queue SET status=?, reviewer=?, reviewed_at=?, decision_note=? WHERE id=?",
        (status, reviewer, time.time(), note[:500], rid),
    )
    if cur.rowcount:
        _events.append("physician_review_decided",
                       {"id": rid, "status": status, "reviewer": reviewer},
                       actor="safety.physician_review")
        return True
    return False


def approve(rid: str, reviewer_email: str, note: str = "") -> bool:
    return _decide(rid, "approved", reviewer_email, note)


def reject(rid: str, reviewer_email: str, note: str = "") -> bool:
    return _decide(rid, "rejected", reviewer_email, note)


def stats() -> dict:
    c = _conn()
    out = {}
    for r in c.execute("SELECT status, COUNT(*) FROM review_queue GROUP BY status").fetchall():
        out[r[0]] = r[1]
    return out
