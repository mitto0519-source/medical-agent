"""Idempotency Cache — 같은 입력 외부 호출(PubMed/CrossRef/LLM 등)을 일정 시간 캐싱.

SQLite 기반 key→JSON 값 저장 + TTL. 데코레이터/컨텍스트 둘 다 지원.

API:
  cached_call(key, fn, ttl_sec=24*3600, namespace="default") -> result
      key 있으면 캐시 반환, 없으면 fn() 호출 + 저장

  @idempotent(namespace="pubmed", key_fn=lambda q: q.lower(), ttl_sec=3600)
  def search_pubmed(q): ...

  invalidate(namespace, key=None)  # key None이면 namespace 전체

설계:
  - 캐시 미스/히트 모두 events에 audit ("cache_hit"/"cache_miss")
  - 직렬화 가능한 값만 저장 (json.dumps with default=str)
  - 저장 실패해도 fn() 호출은 진행 (안전 fallback)
"""
from __future__ import annotations

import functools
import hashlib
import json
import os
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Callable

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)
_DB_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "idempotency.db"
_LOCAL = threading.local()


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
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS cache (
            namespace TEXT NOT NULL,
            key TEXT NOT NULL,
            value_json TEXT NOT NULL,
            created_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            hits INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(namespace, key)
        )
        """
    )
    c.execute("CREATE INDEX IF NOT EXISTS ix_cache_expires ON cache(expires_at)")
    _LOCAL.conn = c
    return c


def _hash_key(key: Any) -> str:
    if isinstance(key, str):
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
    return hashlib.sha256(json.dumps(key, sort_keys=True, default=str, ensure_ascii=False).encode("utf-8")).hexdigest()[:24]


def get(namespace: str, key: Any) -> Any | None:
    k = _hash_key(key)
    c = _conn()
    row = c.execute("SELECT value_json, expires_at FROM cache WHERE namespace=? AND key=?", (namespace, k)).fetchone()
    if not row:
        return None
    if row[1] < time.time():
        c.execute("DELETE FROM cache WHERE namespace=? AND key=?", (namespace, k))
        return None
    c.execute("UPDATE cache SET hits=hits+1 WHERE namespace=? AND key=?", (namespace, k))
    try:
        return json.loads(row[0])
    except Exception:
        return None


def set(namespace: str, key: Any, value: Any, ttl_sec: int = 24 * 3600) -> bool:
    k = _hash_key(key)
    try:
        payload = json.dumps(value, ensure_ascii=False, default=str)
    except Exception as e:
        _log.debug("idempotency set 직렬화 실패: %s", e)
        return False
    now = time.time()
    try:
        _conn().execute(
            "INSERT OR REPLACE INTO cache(namespace, key, value_json, created_at, expires_at, hits) VALUES (?,?,?,?,?,0)",
            (namespace, k, payload, now, now + ttl_sec),
        )
        return True
    except Exception as e:
        _log.debug("idempotency set 실패: %s", e)
        return False


def cached_call(key: Any, fn: Callable[[], Any], *,
                ttl_sec: int = 24 * 3600, namespace: str = "default") -> Any:
    """key로 캐시 조회. 미스면 fn() 호출 + 저장. fn 예외는 캐시 안 함."""
    hit = get(namespace, key)
    if hit is not None:
        _events.append("cache_hit", {"namespace": namespace, "key": _hash_key(key)[:8]}, actor="idempotency")
        return hit
    _events.append("cache_miss", {"namespace": namespace, "key": _hash_key(key)[:8]}, actor="idempotency")
    result = fn()
    set(namespace, key, result, ttl_sec=ttl_sec)
    return result


def idempotent(namespace: str, *, ttl_sec: int = 24 * 3600,
               key_fn: Callable[..., Any] | None = None):
    """데코레이터. key_fn(*args, **kwargs) → 캐시 키 (기본: (args, sorted(kwargs.items())))."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            k = key_fn(*args, **kwargs) if key_fn else {"args": args, "kwargs": kwargs}
            return cached_call(k, lambda: fn(*args, **kwargs), ttl_sec=ttl_sec, namespace=namespace)
        return wrapper
    return deco


def invalidate(namespace: str, key: Any | None = None) -> int:
    c = _conn()
    if key is None:
        cur = c.execute("DELETE FROM cache WHERE namespace=?", (namespace,))
    else:
        cur = c.execute("DELETE FROM cache WHERE namespace=? AND key=?", (namespace, _hash_key(key)))
    return cur.rowcount


def gc() -> int:
    """만료 항목 삭제. heartbeat에서 주기 호출."""
    cur = _conn().execute("DELETE FROM cache WHERE expires_at<?", (time.time(),))
    return cur.rowcount


def stats(namespace: str | None = None) -> dict:
    c = _conn()
    if namespace:
        row = c.execute("SELECT COUNT(*), COALESCE(SUM(hits),0) FROM cache WHERE namespace=?", (namespace,)).fetchone()
    else:
        row = c.execute("SELECT COUNT(*), COALESCE(SUM(hits),0) FROM cache").fetchone()
    return {"entries": row[0], "total_hits": row[1]}
