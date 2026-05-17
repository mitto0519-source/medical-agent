"""User registry — Supabase (cloud) with local JSON fallback.

Cloud path : SUPABASE_DB_URL 환경변수 설정 시 → ma_users 테이블
Local path : data/users.json (항상 동시 기록 — 오프라인 백업)

super_admin : 모든 기능 + 사용자 관리
viewer      : 기본 접속
"""
from __future__ import annotations

import json
import logging
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

_log = logging.getLogger(__name__)
_USERS_FILE = Path("data/users.json")

ROLES = {"super_admin", "admin", "viewer"}
SUPER_ADMIN_EMAILS = {"mitto0519@gmail.com", "misslonghorn46@gmail.com"}


# ── Cloud helpers ──────────────────────────────────────────────────────

def _cloud() -> bool:
    try:
        from src.cloud.db import cloud_available
        return cloud_available()
    except Exception:
        return False


def _engine():
    from src.cloud.db import get_engine
    return get_engine()


def _row_to_dict(row) -> dict:
    d = dict(row._mapping) if hasattr(row, "_mapping") else dict(row)
    return {
        "email": d["email"],
        "name": d.get("name", ""),
        "role": d.get("role", "viewer"),
        "api_key": d.get("api_key", ""),
        "active": bool(d.get("active", True)),
        "created_at": str(d.get("created_at", "")),
        "llm_provider": d.get("llm_provider") or "Claude (Anthropic)",
        "llm_api_key": d.get("llm_api_key") or "",
    }


def _upsert_cloud(email: str, info: dict) -> None:
    from sqlalchemy import text
    with _engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO ma_users
                (email, name, role, api_key, created_at, active, llm_provider, llm_api_key)
            VALUES
                (:email, :name, :role, :api_key, :created_at, :active, :llm_provider, :llm_api_key)
            ON CONFLICT (email) DO UPDATE SET
                name         = EXCLUDED.name,
                role         = EXCLUDED.role,
                api_key      = EXCLUDED.api_key,
                active       = EXCLUDED.active,
                llm_provider = EXCLUDED.llm_provider,
                llm_api_key  = EXCLUDED.llm_api_key
        """), {
            "email": email,
            "name": info.get("name", ""),
            "role": info.get("role", "viewer"),
            "api_key": info.get("api_key", ""),
            "created_at": info.get("created_at", datetime.now().strftime("%Y-%m-%d")),
            "active": info.get("active", True),
            "llm_provider": info.get("llm_provider"),
            "llm_api_key": info.get("llm_api_key") or "",
        })


# ── Local helpers ──────────────────────────────────────────────────────

def _default_users() -> dict:
    return {
        email: {
            "name": email.split("@")[0],
            "role": "super_admin",
            "api_key": "ma-" + secrets.token_hex(16),
            "created_at": datetime.now().strftime("%Y-%m-%d"),
            "active": True,
        }
        for email in SUPER_ADMIN_EMAILS
    }


def _load_local() -> dict:
    if _USERS_FILE.exists():
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    users = _default_users()
    try:
        _save_local(users)
    except Exception:
        pass
    return users


def _save_local(users: dict) -> None:
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


# ── Core load/save — dual write ────────────────────────────────────────

def _load() -> dict:
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().connect() as conn:
                rows = conn.execute(text("SELECT * FROM ma_users")).mappings().all()
            return {r["email"]: _row_to_dict(r) for r in rows}
        except Exception as e:
            _log.warning(f"Cloud _load() failed, using local: {e}")
    return _load_local()


def _save(users: dict) -> None:
    _save_local(users)
    if _cloud():
        try:
            for email, info in users.items():
                _upsert_cloud(email, info)
        except Exception as e:
            _log.warning(f"Cloud _save() failed: {e}")


# ── Public API ─────────────────────────────────────────────────────────

def get_user_by_key(api_key: str) -> Optional[dict]:
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM ma_users WHERE api_key = :k AND active = TRUE"),
                    {"k": api_key},
                ).mappings().first()
            return _row_to_dict(row) if row else None
        except Exception as e:
            _log.warning(f"Cloud get_user_by_key failed: {e}")
    users = _load_local()
    for email, info in users.items():
        if info.get("api_key") == api_key and info.get("active", True):
            return {"email": email, **info}
    return None


def get_user_by_email(email: str) -> Optional[dict]:
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().connect() as conn:
                row = conn.execute(
                    text("SELECT * FROM ma_users WHERE email = :e AND active = TRUE"),
                    {"e": email},
                ).mappings().first()
            return _row_to_dict(row) if row else None
        except Exception as e:
            _log.warning(f"Cloud get_user_by_email failed: {e}")
    users = _load_local()
    info = users.get(email)
    if info and info.get("active", True):
        return {"email": email, **info}
    return None


def is_super_admin(email: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        return False
    return user.get("role") == "super_admin" or email in SUPER_ADMIN_EMAILS


def list_users() -> list[dict]:
    users = _load()
    if isinstance(users, dict):
        return [{"email": e, **info} for e, info in users.items()]
    return users


def add_user(email: str, name: str = "", role: str = "viewer") -> dict:
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'.")
    api_key = "ma-" + secrets.token_hex(16)
    info = {
        "name": name or email.split("@")[0],
        "role": "super_admin" if email in SUPER_ADMIN_EMAILS else role,
        "api_key": api_key,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "active": True,
        "llm_provider": "Claude (Anthropic)",
        "llm_api_key": "",
    }
    if _cloud():
        try:
            _upsert_cloud(email, info)
        except Exception as e:
            _log.warning(f"Cloud add_user failed: {e}")
    users = _load_local()
    users[email] = info
    _save_local(users)
    return {"email": email, **info}


def remove_user(email: str) -> bool:
    if email in SUPER_ADMIN_EMAILS:
        raise ValueError("Cannot remove super admin accounts.")
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().begin() as conn:
                result = conn.execute(
                    text("UPDATE ma_users SET active = FALSE WHERE email = :e"),
                    {"e": email},
                )
            if result.rowcount > 0:
                users = _load_local()
                if email in users:
                    users[email]["active"] = False
                    _save_local(users)
                return True
        except Exception as e:
            _log.warning(f"Cloud remove_user failed: {e}")
    users = _load_local()
    if email not in users:
        return False
    users[email]["active"] = False
    _save_local(users)
    return True


def rotate_key(email: str) -> str:
    new_key = "ma-" + secrets.token_hex(16)
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().begin() as conn:
                conn.execute(
                    text("UPDATE ma_users SET api_key = :k WHERE email = :e"),
                    {"k": new_key, "e": email},
                )
        except Exception as e:
            _log.warning(f"Cloud rotate_key failed: {e}")
    users = _load_local()
    if email in users:
        users[email]["api_key"] = new_key
        _save_local(users)
    return new_key


def save_llm_settings(email: str, provider: str, api_key: str = "") -> None:
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().begin() as conn:
                conn.execute(
                    text("UPDATE ma_users SET llm_provider = :p, llm_api_key = :k WHERE email = :e"),
                    {"p": provider, "k": api_key, "e": email},
                )
        except Exception as e:
            _log.warning(f"Cloud save_llm_settings failed: {e}")
    users = _load_local()
    if email in users:
        users[email]["llm_provider"] = provider
        users[email]["llm_api_key"] = api_key
        _save_local(users)


def get_llm_settings(email: str) -> dict:
    if _cloud():
        try:
            from sqlalchemy import text
            with _engine().connect() as conn:
                row = conn.execute(
                    text("SELECT llm_provider, llm_api_key FROM ma_users WHERE email = :e"),
                    {"e": email},
                ).mappings().first()
            if row:
                return {
                    "provider": row["llm_provider"] or "Claude (Anthropic)",
                    "api_key": row["llm_api_key"] or "",
                }
        except Exception as e:
            _log.warning(f"Cloud get_llm_settings failed: {e}")
    users = _load_local()
    info = users.get(email, {})
    return {
        "provider": info.get("llm_provider", "Claude (Anthropic)"),
        "api_key": info.get("llm_api_key", ""),
    }
