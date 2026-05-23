"""Per-user activity logger — Supabase (cloud) + local JSON fallback."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
LOG_DIR = Path("data/activity")


def _cloud() -> bool:
    try:
        from src.cloud.db import cloud_available
        return cloud_available()
    except Exception:
        return False


def _engine():
    from src.cloud.db import get_engine
    return get_engine()


def _safe_email(email: str) -> str:
    return email.replace("@", "_at_").replace(".", "_")


def log_activity(
    user_email: str,
    page: str,
    action: str,
    input_data: dict,
    output_summary: str,
    output_data: Optional[dict] = None,
) -> dict:
    entry_id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    entry = {
        "id": entry_id,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "user_email": user_email,          # admin 전체조회 시 소유자 식별
        "page": page,
        "action": action,
        "input": input_data,
        "output_summary": output_summary,
        "output": output_data or {},
    }

    # ── Cloud write ────────────────────────────────────────────────────
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().begin() as conn:
                conn.execute(text("""
                    INSERT INTO ma_activity
                        (id, user_email, page, action, input_data, output_summary, output_data)
                    VALUES
                        (:id, :user_email, :page, :action,
                         CAST(:input_data AS jsonb), :output_summary, CAST(:output_data AS jsonb))
                    ON CONFLICT (id) DO NOTHING
                """), {
                    "id": entry_id,
                    "user_email": user_email,
                    "page": page,
                    "action": action,
                    "input_data": json.dumps(input_data or {}, ensure_ascii=False),
                    "output_summary": (output_summary or "")[:500],
                    "output_data": json.dumps(output_data or {}, ensure_ascii=False),
                })
        except Exception as e:
            _log.warning("Cloud log_activity failed: %s", e)

    # ── Local write (always — offline backup) ─────────────────────────
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"{_safe_email(user_email)}.json"
        existing = json.loads(log_file.read_text(encoding="utf-8")) if log_file.exists() else []
        existing.insert(0, entry)
        log_file.write_text(
            json.dumps(existing[:200], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        _log.debug("Local log_activity failed: %s", e)

    return entry


def get_user_log(user_email: str, page: Optional[str] = None, limit: int = 20) -> list:
    if _cloud():
        try:
            from sqlalchemy import text
            where = "user_email = :e"
            params: dict = {"e": user_email}
            if page:
                where += " AND page = :p"
                params["p"] = page
            with _engine().connect() as conn:
                rows = conn.execute(
                    text(f"SELECT * FROM ma_activity WHERE {where} ORDER BY timestamp DESC LIMIT :lim"),
                    {**params, "lim": limit},
                ).mappings().all()
            return [
                {
                    "id": r["id"],
                    "timestamp": str(r.get("timestamp", ""))[:19],
                    "page": r.get("page", ""),
                    "action": r.get("action", ""),
                    "input": r.get("input_data") or {},
                    "output_summary": r.get("output_summary", ""),
                    "output": r.get("output_data") or {},
                }
                for r in rows
            ]
        except Exception as e:
            _log.warning("Cloud get_user_log failed: %s", e)

    log_file = LOG_DIR / f"{_safe_email(user_email)}.json"
    if not log_file.exists():
        return []
    try:
        entries = json.loads(log_file.read_text(encoding="utf-8"))
        if page:
            entries = [e for e in entries if e.get("page") == page]
        return entries[:limit]
    except Exception:
        return []


def get_all_logs(page: Optional[str] = None, limit: int = 100) -> list:
    """admin 전용 — 전체 user의 활동 로그 (각 entry에 user_email 포함).

    일반 user는 get_user_log(본인)만, admin은 이 함수로 모두 조회 (full access).
    """
    if _cloud():
        try:
            from sqlalchemy import text
            where = "1=1"
            params: dict = {}
            if page:
                where = "page = :p"
                params["p"] = page
            with _engine().connect() as conn:
                rows = conn.execute(
                    text(f"SELECT * FROM ma_activity WHERE {where} ORDER BY timestamp DESC LIMIT :lim"),
                    {**params, "lim": limit},
                ).mappings().all()
            return [
                {
                    "id": r["id"],
                    "timestamp": str(r.get("timestamp", ""))[:19],
                    "user_email": r.get("user_email", ""),
                    "page": r.get("page", ""),
                    "action": r.get("action", ""),
                    "input": r.get("input_data") or {},
                    "output_summary": r.get("output_summary", ""),
                    "output": r.get("output_data") or {},
                }
                for r in rows
            ]
        except Exception as e:
            _log.warning("Cloud get_all_logs failed: %s", e)

    # local: 모든 user 로그 파일 병합
    results = []
    if LOG_DIR.exists():
        for f in LOG_DIR.glob("*.json"):
            try:
                entries = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            for e in entries:
                if page and e.get("page") != page:
                    continue
                e.setdefault("user_email", f.stem)  # 구 로그 폴백(파일명)
                results.append(e)
    results.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return results[:limit]
