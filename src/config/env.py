"""환경변수 관리 — 단일 dotenv 로드 + 시작 시 필수값 검증.

모든 모듈은 이 파일을 통해서만 .env를 로드한다.
다른 파일에서 직접 load_dotenv()를 호출하지 말 것.

Usage:
    # 앱 시작 시 1회:
    from src.config.env import bootstrap
    bootstrap()          # .env 로드 + 필수 변수 검증

    # 나머지 모듈에서는 os.environ으로 바로 접근:
    import os
    key = os.environ.get("ANTHROPIC_API_KEY")
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Optional

_bootstrapped = False
_ROOT = Path(__file__).parent.parent.parent  # Medical-Agent/


def _find_env_file() -> Optional[Path]:
    for candidate in [_ROOT / ".env", Path(".env"), Path("../.env")]:
        if candidate.exists():
            return candidate
    return None


def bootstrap(strict: bool = False) -> dict:
    """dotenv 로드 + 환경변수 검증.

    Args:
        strict: True면 필수 변수 누락 시 sys.exit(1). False면 경고만.

    Returns:
        {"ok": bool, "missing": [...], "warnings": [...]}
    """
    global _bootstrapped
    if not _bootstrapped:
        env_path = _find_env_file()
        if env_path:
            try:
                from dotenv import load_dotenv
                load_dotenv(dotenv_path=env_path, override=False)
            except ImportError:
                pass  # python-dotenv 없으면 os.environ 그대로 사용
        _bootstrapped = True

    result = _validate()

    if result["missing"] and strict:
        print("[ENV] 필수 환경변수 누락으로 종료합니다:")
        for var in result["missing"]:
            print(f"  ✗ {var}")
        print(f"\n  → {_ROOT}/.env 파일에 위 변수를 추가하세요.")
        print(f"  → 예시: {_ROOT}/.env.example")
        sys.exit(1)

    if result["warnings"]:
        for w in result["warnings"]:
            print(f"[ENV] WARNING: {w}")

    return result


def _validate() -> dict:
    missing = []
    warnings = []

    # 필수: LLM 공급자 중 최소 하나
    has_llm = bool(
        os.environ.get("ANTHROPIC_API_KEY") or
        os.environ.get("OPENAI_API_KEY")
    )
    if not has_llm:
        missing.append("ANTHROPIC_API_KEY 또는 OPENAI_API_KEY (둘 중 하나 필수)")

    # ANTHROPIC_API_KEY 형식 검사
    ant_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if ant_key and not ant_key.startswith("sk-ant"):
        warnings.append("ANTHROPIC_API_KEY가 'sk-ant'로 시작하지 않습니다. 키를 확인하세요.")

    # OPENAI_API_KEY 형식 검사
    oai_key = os.environ.get("OPENAI_API_KEY", "")
    if oai_key and not oai_key.startswith("sk-"):
        warnings.append("OPENAI_API_KEY가 'sk-'로 시작하지 않습니다. 키를 확인하세요.")

    # 선택: Supabase DB URL
    if not os.environ.get("SUPABASE_DB_URL"):
        warnings.append(
            "SUPABASE_DB_URL 미설정 — 로컬 ChromaDB + JSON 파일 모드로 동작합니다."
        )

    return {
        "ok": len(missing) == 0,
        "missing": missing,
        "warnings": warnings,
        "providers": {
            "anthropic": bool(ant_key),
            "openai": bool(oai_key),
            "supabase": bool(os.environ.get("SUPABASE_DB_URL")),
        },
    }


def get_api_key(provider: str = "anthropic") -> str:
    """provider별 API 키 반환. 없으면 ValueError."""
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
                f".env 파일 위치: {_ROOT}/.env"
            )
        return key
    if provider == "openai":
        key = os.environ.get("OPENAI_API_KEY", "")
        if not key:
            raise ValueError(
                "OPENAI_API_KEY가 설정되지 않았습니다.\n"
                f".env 파일 위치: {_ROOT}/.env"
            )
        return key
    raise ValueError(f"알 수 없는 provider: {provider}")
