"""Access Control — 초대 링크 발급, 세션 추적, 기능별 권한 확인.

src/auth/users.py의 기본 사용자 레지스트리 위에 올라가는 고수준 레이어.

역할(Role) 계층:
  super_admin  → 전체 기능 + 사용자 관리
  admin        → 논문 작성/통계/RAG + 사용자 조회
  viewer       → 조회 + AI 패널만 가능 (쓰기 불가)

기능별 권한 매트릭스 (PERMISSION_MAP):
  - paper_write   : admin+
  - stat_run      : admin+
  - rag_query     : admin+
  - user_manage   : super_admin only
  - pipeline_run  : super_admin only
  - view_drafts   : viewer+
"""
from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_INVITE_FILE = Path("data/invitations.json")
_SESSION_FILE = Path("data/sessions.json")

# ---------------------------------------------------------------------------
# Permission matrix
# ---------------------------------------------------------------------------

ROLE_LEVEL = {"super_admin": 3, "admin": 2, "viewer": 1}

PERMISSION_MAP: Dict[str, int] = {
    "view_drafts":    1,  # viewer+
    "ai_panel":       1,
    "rag_query":      2,  # admin+
    "stat_run":       2,
    "paper_write":    2,
    "export_docx":    2,
    "peer_review":    2,
    "pipeline_run":   3,  # super_admin only
    "user_manage":    3,
    "system_config":  3,
}


def can(email: str, feature: str) -> bool:
    """이메일 + 기능명으로 권한 확인.

    Usage:
        if not can(user_email, "paper_write"):
            raise PermissionError("권한이 없습니다.")
    """
    from src.auth.users import get_user_by_email
    user = get_user_by_email(email)
    if not user or not user.get("active", True):
        return False
    role = user.get("role", "viewer")
    required = PERMISSION_MAP.get(feature, 3)  # unknown → super_admin only
    return ROLE_LEVEL.get(role, 0) >= required


def require(email: str, feature: str) -> None:
    """권한 없으면 PermissionError 발생."""
    if not can(email, feature):
        raise PermissionError(f"'{feature}' 기능에 대한 권한이 없습니다. (계정: {email})")


# ---------------------------------------------------------------------------
# Invitation system
# ---------------------------------------------------------------------------

def _load_invites() -> dict:
    if _INVITE_FILE.exists():
        return json.loads(_INVITE_FILE.read_text(encoding="utf-8"))
    return {}


def _save_invites(invites: dict) -> None:
    _INVITE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INVITE_FILE.write_text(json.dumps(invites, ensure_ascii=False, indent=2), encoding="utf-8")


def create_invite(
    email: str,
    role: str = "viewer",
    inviter_email: str = "",
    expires_hours: int = 72,
) -> str:
    """초대 토큰 생성 + 저장. 반환값: 초대 토큰 (URL에 붙여 사용).

    사용자가 이미 존재하면 기존 계정 활성화 후 토큰 반환.
    """
    from src.auth.users import ROLES
    if role not in ROLES:
        raise ValueError(f"유효하지 않은 역할: {role}")

    token = secrets.token_urlsafe(32)
    invites = _load_invites()
    invites[token] = {
        "email": email,
        "role": role,
        "inviter": inviter_email,
        "created_at": datetime.now().isoformat(),
        "expires_at": (datetime.now() + timedelta(hours=expires_hours)).isoformat(),
        "used": False,
    }
    _save_invites(invites)
    _log.info("초대 토큰 생성: %s → %s (%s)", inviter_email, email, role)
    return token


def accept_invite(token: str) -> Optional[dict]:
    """초대 토큰 수락 → 사용자 생성 + 토큰 사용 처리.

    Returns: 생성된 사용자 dict, 실패 시 None.
    """
    invites = _load_invites()
    invite = invites.get(token)
    if not invite:
        _log.warning("유효하지 않은 초대 토큰: %s", token)
        return None
    if invite.get("used"):
        _log.warning("이미 사용된 초대 토큰: %s", token)
        return None
    if datetime.now() > datetime.fromisoformat(invite["expires_at"]):
        _log.warning("만료된 초대 토큰: %s", token)
        return None

    from src.auth.users import add_user
    user = add_user(invite["email"], role=invite["role"])
    invite["used"] = True
    invite["accepted_at"] = datetime.now().isoformat()
    _save_invites(invites)
    _log.info("초대 수락: %s (%s)", invite["email"], invite["role"])
    return user


def list_invites(active_only: bool = True) -> List[dict]:
    """초대 목록 조회."""
    invites = _load_invites()
    result = []
    now = datetime.now()
    for token, inv in invites.items():
        expired = datetime.fromisoformat(inv["expires_at"]) < now
        used = inv.get("used", False)
        if active_only and (expired or used):
            continue
        result.append({
            "token": token[:8] + "...",  # 보안: 전체 노출 금지
            "email": inv["email"],
            "role": inv["role"],
            "inviter": inv["inviter"],
            "created_at": inv["created_at"][:10],
            "expires_at": inv["expires_at"][:10],
            "used": used,
            "expired": expired,
        })
    return result


def revoke_invite(token: str) -> bool:
    """초대 토큰 철회 (expires_at을 현재로 설정)."""
    invites = _load_invites()
    if token not in invites:
        return False
    invites[token]["expires_at"] = datetime.now().isoformat()
    _save_invites(invites)
    return True


# ---------------------------------------------------------------------------
# Session tracking (API key → active session)
# ---------------------------------------------------------------------------

def _load_sessions() -> dict:
    if _SESSION_FILE.exists():
        return json.loads(_SESSION_FILE.read_text(encoding="utf-8"))
    return {}


def _save_sessions(sessions: dict) -> None:
    _SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    _SESSION_FILE.write_text(json.dumps(sessions, ensure_ascii=False, indent=2), encoding="utf-8")


def start_session(email: str, ip: str = "", user_agent: str = "") -> str:
    """세션 시작 → 세션 ID 반환."""
    session_id = secrets.token_urlsafe(24)
    sessions = _load_sessions()
    sessions[session_id] = {
        "email": email,
        "ip": ip,
        "user_agent": user_agent[:100],
        "started_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
        "active": True,
    }
    _save_sessions(sessions)
    _log.info("세션 시작: %s (%s)", email, session_id[:8])
    return session_id


def end_session(session_id: str) -> None:
    sessions = _load_sessions()
    if session_id in sessions:
        sessions[session_id]["active"] = False
        sessions[session_id]["ended_at"] = datetime.now().isoformat()
        _save_sessions(sessions)


def touch_session(session_id: str) -> bool:
    """세션 last_active 갱신. 유효하면 True."""
    sessions = _load_sessions()
    if session_id in sessions and sessions[session_id].get("active"):
        sessions[session_id]["last_active"] = datetime.now().isoformat()
        _save_sessions(sessions)
        return True
    return False


def active_sessions() -> List[dict]:
    """현재 활성 세션 목록 (super_admin용)."""
    sessions = _load_sessions()
    now = datetime.now()
    result = []
    for sid, s in sessions.items():
        if not s.get("active"):
            continue
        last = datetime.fromisoformat(s["last_active"])
        idle_min = (now - last).seconds // 60
        result.append({
            "session_id": sid[:8] + "...",
            "email": s["email"],
            "started_at": s["started_at"][:16],
            "last_active": s["last_active"][:16],
            "idle_minutes": idle_min,
            "ip": s.get("ip", ""),
        })
    return result


# ---------------------------------------------------------------------------
# Convenience: bulk user summary
# ---------------------------------------------------------------------------

def user_summary() -> List[dict]:
    """모든 사용자 + 기능별 권한 요약 (사용자 관리 페이지용)."""
    from src.auth.users import list_users
    users = list_users()
    result = []
    for u in users:
        email = u["email"]
        perms = {f: can(email, f) for f in PERMISSION_MAP}
        result.append({
            "email": email,
            "name": u.get("name", ""),
            "role": u.get("role", "viewer"),
            "active": u.get("active", True),
            "created_at": u.get("created_at", ""),
            "permissions": perms,
        })
    return result
