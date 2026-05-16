"""User registry — email/API-key based access control.

super_admin : 모든 기능 + 사용자 관리 + 상호 동기화
viewer      : 읽기 전용 (향후 확장)
"""

from __future__ import annotations

import json
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

_USERS_FILE = Path("data/users.json")

ROLES = {"super_admin", "admin", "viewer"}

SUPER_ADMIN_EMAILS = {"mitto0519@gmail.com", "misslonghorn46@gmail.com"}


def _default_users() -> dict:
    """슈퍼어드민 기본값 — users.json 없을 때 사용."""
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


def _load() -> dict:
    if _USERS_FILE.exists():
        return json.loads(_USERS_FILE.read_text(encoding="utf-8"))
    # Auto-init with super admins on first run (local or Streamlit Cloud)
    users = _default_users()
    try:
        _save(users)
    except Exception:
        pass
    return users


def _save(users: dict) -> None:
    _USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    _USERS_FILE.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")


# ------------------------------------------------------------------
# Key ↔ email lookup
# ------------------------------------------------------------------

def get_user_by_key(api_key: str) -> Optional[dict]:
    """API 키로 사용자 정보 반환. 없으면 None."""
    users = _load()
    for email, info in users.items():
        if info.get("api_key") == api_key and info.get("active", True):
            return {"email": email, **info}
    return None


def get_user_by_email(email: str) -> Optional[dict]:
    users = _load()
    info = users.get(email)
    if info and info.get("active", True):
        return {"email": email, **info}
    return None


def is_super_admin(email: str) -> bool:
    user = get_user_by_email(email)
    if not user:
        return False
    return user.get("role") == "super_admin" or email in SUPER_ADMIN_EMAILS


# ------------------------------------------------------------------
# CRUD  (super_admin only — enforced at MCP tool level)
# ------------------------------------------------------------------

def add_user(email: str, name: str = "", role: str = "viewer") -> dict:
    """신규 사용자 추가. API 키 자동 생성."""
    if role not in ROLES:
        raise ValueError(f"Invalid role '{role}'. Must be one of {ROLES}")
    users = _load()
    if email in users:
        raise ValueError(f"User '{email}' already exists.")
    api_key = "ma-" + secrets.token_hex(16)
    users[email] = {
        "name": name or email.split("@")[0],
        "role": role,
        "api_key": api_key,
        "created_at": datetime.now().strftime("%Y-%m-%d"),
        "active": True,
    }
    # Super admin emails always get super_admin role
    if email in SUPER_ADMIN_EMAILS:
        users[email]["role"] = "super_admin"
    _save(users)
    return {"email": email, **users[email]}


def remove_user(email: str) -> bool:
    """사용자 비활성화 (super_admin 이메일은 삭제 불가)."""
    if email in SUPER_ADMIN_EMAILS:
        raise ValueError("Cannot remove super admin accounts.")
    users = _load()
    if email not in users:
        return False
    users[email]["active"] = False
    _save(users)
    return True


def list_users() -> list[dict]:
    """전체 사용자 목록."""
    users = _load()
    return [{"email": e, **info} for e, info in users.items()]


def rotate_key(email: str) -> str:
    """API 키 재발급."""
    users = _load()
    if email not in users:
        raise ValueError(f"User '{email}' not found.")
    new_key = "ma-" + secrets.token_hex(16)
    users[email]["api_key"] = new_key
    _save(users)
    return new_key


def save_llm_settings(email: str, provider: str, api_key: str = "") -> None:
    """사용자 LLM 공급자 및 API 키 저장."""
    users = _load()
    if email not in users:
        return
    users[email]["llm_provider"] = provider
    if api_key:
        users[email]["llm_api_key"] = api_key
    _save(users)


def get_llm_settings(email: str) -> dict:
    """사용자 LLM 설정 반환."""
    users = _load()
    info = users.get(email, {})
    return {
        "provider": info.get("llm_provider", "Claude (Anthropic)"),
        "api_key": info.get("llm_api_key", ""),
    }
