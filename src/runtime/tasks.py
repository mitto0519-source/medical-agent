"""Durable Task State Machine — 장기 작업의 영속 상태(SQLite).

목적: 함수 호출 도중 크래시(쿼터 소진/네트워크/Streamlit 재실행)되어도 진행 상태 보존,
같은 입력 재호출은 캐시 반환(idempotency), 미완료 작업은 새 세션에서 이어쓰기 가능.

상태: CREATED → RUNNING → (WAITING|RETRYING) → COMPLETED|FAILED
스텝: 각 단계의 출력·에러·시도횟수 누적 기록.

API:
  with task_run("paper_write", input_payload, owner) as run:
      if run.cached: return run.output
      result1 = ...; run.commit_step("classify", output=result1)
      result2 = ...; run.commit_step("write", output=result2)
      run.set_output(result2)
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)
_DB_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "tasks.db"
_LOCAL = threading.local()

STATUS = ("CREATED", "RUNNING", "WAITING", "RETRYING", "COMPLETED", "FAILED")
_STALE_HOURS = 4   # last_heartbeat 이만큼 지나면 stale → recover 대상
_CACHE_HOURS = 24  # COMPLETED 작업을 같은 idempotency_key로 캐시 반환할 윈도우


def _conn() -> sqlite3.Connection:
    c = getattr(_LOCAL, "conn", None)
    if c is not None:
        try:
            c.execute("SELECT 1"); return c
        except sqlite3.ProgrammingError:
            pass
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB_PATH), timeout=15, isolation_level=None)
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("PRAGMA synchronous=NORMAL")
    c.execute("PRAGMA busy_timeout=10000")
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS task_runs (
            id TEXT PRIMARY KEY,
            idempotency_key TEXT NOT NULL,
            task_type TEXT NOT NULL,
            owner_email TEXT,
            status TEXT NOT NULL,
            input_json TEXT,
            output_json TEXT,
            error TEXT,
            created_at REAL NOT NULL,
            updated_at REAL NOT NULL,
            last_heartbeat REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ix_taskruns_key ON task_runs(idempotency_key, created_at);
        CREATE INDEX IF NOT EXISTS ix_taskruns_status ON task_runs(status, last_heartbeat);
        CREATE INDEX IF NOT EXISTS ix_taskruns_owner ON task_runs(owner_email, created_at);

        CREATE TABLE IF NOT EXISTS task_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL,
            ts REAL NOT NULL,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            output_json TEXT,
            error TEXT,
            attempts INTEGER NOT NULL DEFAULT 1
        );
        CREATE INDEX IF NOT EXISTS ix_steps_task ON task_steps(task_id, id);
        """
    )
    _LOCAL.conn = c
    return c


def make_idempotency_key(task_type: str, owner: str, payload: Any, *, granularity: str = "day") -> str:
    """입력 payload + 시간 granularity로 안정적 키 생성. 같은 키 = 같은 의미의 작업."""
    canon = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    if granularity == "day":
        slot = datetime.utcnow().strftime("%Y-%m-%d")
    elif granularity == "hour":
        slot = datetime.utcnow().strftime("%Y-%m-%dT%H")
    else:
        slot = "any"
    h = hashlib.sha256(f"{task_type}|{owner}|{slot}|{canon}".encode("utf-8")).hexdigest()[:16]
    return h


class TaskRun:
    """단일 작업의 상태·스텝을 다루는 핸들. 직접 생성 말고 get_or_create() 사용."""

    def __init__(self, row: tuple):
        self.id = row[0]
        self.idempotency_key = row[1]
        self.task_type = row[2]
        self.owner_email = row[3]
        self.status = row[4]
        self.input = json.loads(row[5]) if row[5] else None
        self.output = json.loads(row[6]) if row[6] else None
        self.error = row[7]
        self.created_at = row[8]
        self.updated_at = row[9]
        self.last_heartbeat = row[10]

    @property
    def cached(self) -> bool:
        return self.status == "COMPLETED"

    @classmethod
    def get_or_create(cls, task_type: str, owner: str, input_payload: Any,
                      *, granularity: str = "day") -> "TaskRun":
        """idempotency_key로 기존 작업 조회 → COMPLETED면 캐시, RUNNING이면 그대로 반환,
        아니면 새 CREATED 작업 생성."""
        key = make_idempotency_key(task_type, owner, input_payload, granularity=granularity)
        c = _conn()
        # 캐시 윈도우 내 가장 최신 동일 키 작업 조회
        cutoff = time.time() - _CACHE_HOURS * 3600
        row = c.execute(
            "SELECT * FROM task_runs WHERE idempotency_key=? AND created_at>=? ORDER BY created_at DESC LIMIT 1",
            (key, cutoff),
        ).fetchone()
        if row is not None:
            run = cls(row)
            # stale RUNNING은 새로 시작 (이전 프로세스 죽었을 가능성)
            if run.status == "RUNNING" and (time.time() - run.last_heartbeat) > _STALE_HOURS * 3600:
                run._set_status("RETRYING")
                _events.append("task_recovered_stale", {"task_id": run.id}, task_id=run.id, actor="task_runtime")
            return run
        # 신규
        tid = uuid.uuid4().hex[:16]
        now = time.time()
        c.execute(
            "INSERT INTO task_runs(id, idempotency_key, task_type, owner_email, status, input_json, created_at, updated_at, last_heartbeat) "
            "VALUES (?,?,?,?,?,?,?,?,?)",
            (tid, key, task_type, owner, "CREATED",
             json.dumps(input_payload, ensure_ascii=False, default=str),
             now, now, now),
        )
        _events.append("task_created", {"task_type": task_type, "owner": owner, "key": key}, task_id=tid, actor="task_runtime")
        return cls.get_by_id(tid)

    @classmethod
    def get_by_id(cls, tid: str) -> "TaskRun":
        row = _conn().execute("SELECT * FROM task_runs WHERE id=?", (tid,)).fetchone()
        if row is None:
            raise KeyError(f"task {tid} 없음")
        return cls(row)

    @classmethod
    def list_unfinished(cls, owner_email: str | None = None, limit: int = 20) -> list["TaskRun"]:
        c = _conn()
        sql = "SELECT * FROM task_runs WHERE status IN ('CREATED','RUNNING','WAITING','RETRYING')"
        params: list = []
        if owner_email:
            sql += " AND owner_email=?"; params.append(owner_email)
        sql += " ORDER BY updated_at DESC LIMIT ?"; params.append(limit)
        return [cls(r) for r in c.execute(sql, tuple(params)).fetchall()]

    @classmethod
    def recover_stale(cls, hours: int = _STALE_HOURS) -> int:
        """heartbeat 끊긴 RUNNING을 RETRYING으로. heartbeat job용."""
        cutoff = time.time() - hours * 3600
        c = _conn()
        cur = c.execute(
            "UPDATE task_runs SET status='RETRYING', updated_at=? WHERE status='RUNNING' AND last_heartbeat<?",
            (time.time(), cutoff),
        )
        n = cur.rowcount
        if n:
            _events.append("task_recover_stale_batch", {"n": n}, actor="task_runtime")
        return n

    def heartbeat(self) -> None:
        now = time.time()
        _conn().execute("UPDATE task_runs SET last_heartbeat=?, updated_at=? WHERE id=?", (now, now, self.id))
        self.last_heartbeat = now
        self.updated_at = now

    def _set_status(self, status: str, error: str | None = None) -> None:
        if status not in STATUS:
            raise ValueError(f"invalid status: {status}")
        now = time.time()
        prev = self.status
        _conn().execute(
            "UPDATE task_runs SET status=?, error=?, updated_at=?, last_heartbeat=? WHERE id=?",
            (status, error, now, now, self.id),
        )
        self.status = status; self.error = error; self.updated_at = now; self.last_heartbeat = now
        _events.append("task_transition", {"from": prev, "to": status, "error": error}, task_id=self.id, actor="task_runtime")

    def commit_step(self, name: str, output: Any = None, error: str | None = None) -> int:
        c = _conn()
        # 같은 step 이름이 이미 있으면 attempts++
        prev = c.execute("SELECT id, attempts FROM task_steps WHERE task_id=? AND name=? ORDER BY id DESC LIMIT 1", (self.id, name)).fetchone()
        attempts = (prev[1] + 1) if prev else 1
        status = "FAILED" if error else "COMPLETED"
        cur = c.execute(
            "INSERT INTO task_steps(task_id, ts, name, status, output_json, error, attempts) VALUES (?,?,?,?,?,?,?)",
            (self.id, time.time(), name, status,
             json.dumps(output, ensure_ascii=False, default=str) if output is not None else None,
             error, attempts),
        )
        self.heartbeat()
        _events.append("task_step", {"name": name, "status": status, "attempts": attempts}, task_id=self.id, actor="task_runtime")
        return int(cur.lastrowid or 0)

    def steps(self) -> list[dict]:
        rows = _conn().execute(
            "SELECT id, ts, name, status, output_json, error, attempts FROM task_steps WHERE task_id=? ORDER BY id ASC",
            (self.id,),
        ).fetchall()
        return [
            {"id": r[0], "ts": r[1], "name": r[2], "status": r[3],
             "output": json.loads(r[4]) if r[4] else None, "error": r[5], "attempts": r[6]}
            for r in rows
        ]

    def set_output(self, output: Any) -> None:
        _conn().execute(
            "UPDATE task_runs SET output_json=?, updated_at=?, last_heartbeat=? WHERE id=?",
            (json.dumps(output, ensure_ascii=False, default=str), time.time(), time.time(), self.id),
        )
        self.output = output


@contextmanager
def task_run(task_type: str, input_payload: Any, owner_email: str = "",
             *, granularity: str = "day"):
    """ergonomic context manager.

    with task_run("paper_write", {"msg": user_msg}, owner) as run:
        if run.cached:
            return run.output
        ...
        run.set_output(result)
    """
    run = TaskRun.get_or_create(task_type, owner_email, input_payload, granularity=granularity)
    if not run.cached:
        run._set_status("RUNNING")
    try:
        yield run
        if run.status not in ("COMPLETED", "FAILED"):
            run._set_status("COMPLETED")
    except Exception as e:
        run._set_status("FAILED", error=str(e)[:500])
        raise
