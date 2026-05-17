"""Central model registry — 모든 모델 ID와 task routing을 한 곳에서 관리.

Usage:
    from src.config.models import get_model, get_embedding_model, thinking_config

    provider, model_id = get_model("paper_writing")  # ("anthropic", "claude-opus-4-7")
    provider, model_id = get_model("ocr")            # ("anthropic", "claude-haiku-4-5-20251001")
    cfg = thinking_config("paper_writing")           # {"type": "enabled", "budget_tokens": 10000}

환경변수 오버라이드:
    LLM_MODEL_OVERRIDE=claude-sonnet-4-6   # 특정 모델 강제
    LLM_TIER_OVERRIDE=fast|standard|premium # 전체 티어 조정
    EMBEDDING_MODEL=all-MiniLM-L6-v2       # 임베딩 모델 변경
    LLM_DISABLE_THINKING=1                 # thinking 비활성화
"""
from __future__ import annotations

import os
from typing import Optional

# ── Claude model IDs ──────────────────────────────────────────────────────────
CLAUDE: dict[str, str] = {
    "premium":  "claude-opus-4-7",           # 논문 작성, 복잡한 추론
    "standard": "claude-sonnet-4-6",          # Q&A, 요약, 주제 생성
    "fast":     "claude-haiku-4-5-20251001",  # OCR, 빠른 분류
}

# ── OpenAI fallback model IDs ─────────────────────────────────────────────────
OPENAI: dict[str, str] = {
    "premium":  "gpt-4o",
    "standard": "gpt-4o-mini",
    "fast":     "gpt-4o-mini",
}

# ── 임베딩 모델 ───────────────────────────────────────────────────────────────
_DEFAULT_EMBEDDING = "all-MiniLM-L6-v2"  # 384-dim, sentence-transformers

# ── Task → tier 매핑 ──────────────────────────────────────────────────────────
_TASK_TIER: dict[str, str] = {
    "ocr":              "fast",
    "classification":   "fast",
    "qa":               "standard",
    "summary":          "standard",
    "topic_generation": "fast",
    "novelty_check":    "fast",
    "feasibility":      "fast",
    "evidence_search":  "standard",
    "paper_writing":    "premium",
    "author_profile":   "premium",
    "synthesis":        "premium",
    "abstract":         "premium",
}

# ── thinking 지원 모델 목록 ───────────────────────────────────────────────────
_THINKING_SUPPORTED: frozenset[str] = frozenset({
    "claude-opus-4-7",
    "claude-sonnet-4-6",
})

_THINKING_BUDGET: dict[str, int] = {
    "premium":  10000,
    "standard": 5000,
    "fast":     0,
}


# ── Public API ────────────────────────────────────────────────────────────────

def get_model(task: str = "standard") -> tuple[str, str]:
    """task 이름 또는 tier 이름으로 (provider, model_id) 반환.

    우선순위:
      1. LLM_MODEL_OVERRIDE 환경변수 (특정 모델 강제)
      2. LLM_TIER_OVERRIDE 환경변수 (티어 조정)
      3. task → tier → provider 자동 선택 (Anthropic 우선)
    """
    override = os.environ.get("LLM_MODEL_OVERRIDE", "").strip()
    if override:
        provider = "anthropic" if "claude" in override.lower() else "openai"
        return provider, override

    tier_override = os.environ.get("LLM_TIER_OVERRIDE", "").strip().lower()
    tier = tier_override or _TASK_TIER.get(task, task)
    if tier not in ("fast", "standard", "premium"):
        tier = "standard"

    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", CLAUDE[tier]
    if os.environ.get("OPENAI_API_KEY"):
        return "openai", OPENAI[tier]

    raise ValueError(
        "LLM API 키가 없습니다.\n"
        ".env 파일에 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 설정하세요."
    )


def get_vision_model() -> tuple[str, str]:
    """이미지 OCR/Vision 전용 모델. Claude Haiku(빠르고 저렴) 기본."""
    return get_model("ocr")


def get_embedding_model() -> str:
    """임베딩 모델명 반환 (sentence-transformers 호환)."""
    return os.environ.get("EMBEDDING_MODEL", _DEFAULT_EMBEDDING)


def get_embedding_dim() -> int:
    """임베딩 출력 차원 반환."""
    _dims = {
        "all-MiniLM-L6-v2":         384,
        "all-mpnet-base-v2":         768,
        "paraphrase-MiniLM-L3-v2":   384,
    }
    return _dims.get(get_embedding_model(), 384)


def thinking_config(task: str = "standard") -> Optional[dict]:
    """task에 맞는 extended thinking 파라미터 반환.

    Returns:
        {"type": "enabled", "budget_tokens": N}  — thinking 활성화
        {"type": "disabled"}                      — thinking 비활성화
        None                                       — OpenAI 등 thinking 미지원 provider
    """
    if os.environ.get("LLM_DISABLE_THINKING", "").lower() in ("1", "true", "yes"):
        return {"type": "disabled"}

    provider, model_id = get_model(task)
    if provider != "anthropic":
        return None

    if model_id not in _THINKING_SUPPORTED:
        return {"type": "disabled"}

    tier = _TASK_TIER.get(task, task)
    if tier not in _THINKING_BUDGET:
        tier = "standard"
    budget = _THINKING_BUDGET[tier]

    if budget == 0:
        return {"type": "disabled"}
    return {"type": "enabled", "budget_tokens": budget}


def list_available_models() -> dict:
    """현재 API 키 기준 사용 가능한 모델 정보 반환."""
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_openai = bool(os.environ.get("OPENAI_API_KEY"))

    available: dict = {}
    if has_anthropic:
        available["anthropic"] = CLAUDE.copy()
    if has_openai:
        available["openai"] = OPENAI.copy()
    if not available:
        available["status"] = "API 키 없음 — .env에 ANTHROPIC_API_KEY 또는 OPENAI_API_KEY 설정 필요"

    active_provider, active_model = "none", "none"
    try:
        active_provider, active_model = get_model("standard")
    except Exception:
        pass

    return {
        "available": available,
        "active": {"provider": active_provider, "model": active_model},
        "embedding": get_embedding_model(),
        "overrides": {
            "model": os.environ.get("LLM_MODEL_OVERRIDE", ""),
            "tier":  os.environ.get("LLM_TIER_OVERRIDE", ""),
        },
    }
