"""JWT 인증 미들웨어 — src.auth.users 재사용.

FRONTEND_NEXTJS_SPEC §9: httpOnly 쿠키 JWT. (app) 게이트, (public) 무인증.
"""
from __future__ import annotations

import os
import time
from typing import Optional

try:
    from jose import jwt, JWTError
except Exception:
    jwt = None
    JWTError = Exception

from src.config.logging_config import get_logger

_log = get_logger(__name__)

JWT_SECRET = os.environ.get("MA_JWT_SECRET", "dev-secret-please-rotate")
JWT_ALG = "HS256"
JWT_EXPIRE_SECONDS = 7 * 24 * 3600  # 7일


def create_token(email: str) -> str:
    if jwt is None:
        return f"dev-token-{email}"
    payload = {
        "sub": email,
        "iat": int(time.time()),
        "exp": int(time.time()) + JWT_EXPIRE_SECONDS,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALG)


def decode_token(token: str) -> Optional[str]:
    if not token:
        return None
    if jwt is None or token.startswith("dev-token-"):
        return token.replace("dev-token-", "") if token.startswith("dev-token-") else None
    try:
        data = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALG])
        return data.get("sub")
    except JWTError as e:
        _log.debug("jwt decode fail: %s", e)
        return None


def get_current_email(authorization: str = "", cookie_token: str = "") -> Optional[str]:
    """Authorization Bearer 또는 httpOnly 쿠키에서 email 추출."""
    token = ""
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif cookie_token:
        token = cookie_token
    return decode_token(token)


def verify_user(email: str, password: str) -> bool:
    """이메일만으로 인증 — Streamlit과 동일 (개발 환경).

    Streamlit `_ensure_logged_in`이 비밀번호 없이 `get_user_by_email`만 호출하므로
    FastAPI도 동일하게: 사용자 DB에 등록 + active=True면 통과. 비밀번호는 무시.
    프로덕션 전환 시 bcrypt 등으로 강화 — 지금은 본인 노트북 단일 사용자 환경.
    """
    if not email:
        return False
    try:
        from src.auth.users import get_user_by_email
        user = get_user_by_email(email)
        return bool(user and user.get("active", True))
    except Exception as e:
        _log.warning("verify_user fail: %s", e)
        return False
