"""LLM 클라이언트 팩토리 — provider 자동 선택 + 모델 정보 노출.

사용 가능한 provider(Anthropic/OpenAI)를 자동 감지하고
task에 맞는 최적 모델을 반환한다.
"""
from __future__ import annotations

import os
from typing import Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.config.models import get_model, list_available_models


def get_llm_client(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    task: str = "standard",
    resilient: bool = True,
):
    """task에 맞는 LLM 클라이언트 반환.

    Args:
        api_key: API 키 (None이면 환경변수 자동 사용)
        provider: "anthropic" | "openai" | None(자동)
        model: 특정 모델 ID 강제 (None이면 task 기반 자동 선택)
        task: "ocr" | "qa" | "summary" | "paper_writing" | "standard" 등
        resilient: True이면 다중 모델 페일오버 활성화 (기본값)

    Returns:
        ClaudeClient 또는 OpenAIClient 또는 ResilientLLMClient
    """
    bootstrap()

    # resilient 모드: 자동 페일오버 (Claude → GPT-4 → Gemini)
    if resilient and provider is None and not api_key:
        from src.llm.resilient_client import ResilientLLMClient
        _log = get_logger(__name__)
        _log.debug(f"[Factory] 탄력적 모드 활성화 (task={task})")
        return ResilientLLMClient(task=task)

    explicit_provider = (provider or "").strip().lower()

    # provider 명시 지정
    if explicit_provider == "anthropic":
        from src.llm.claude_client import ClaudeClient
        return ClaudeClient(api_key=api_key, model=model, task=task)

    if explicit_provider == "openai":
        from src.llm.openai_client import OpenAIClient
        return OpenAIClient(api_key=api_key, model=model, task=task)

    # api_key 접두어로 자동 감지
    if api_key:
        if api_key.startswith("sk-ant"):
            from src.llm.claude_client import ClaudeClient
            return ClaudeClient(api_key=api_key, model=model, task=task)
        if api_key.startswith("sk-"):
            from src.llm.openai_client import OpenAIClient
            return OpenAIClient(api_key=api_key, model=model, task=task)

    # 환경변수 기반 자동 선택 (Anthropic 우선)
    detected_provider, detected_model = get_model(task)

    if detected_provider == "anthropic":
        from src.llm.claude_client import ClaudeClient
        return ClaudeClient(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
            model=model or detected_model,
            task=task,
        )

    if detected_provider == "openai":
        from src.llm.openai_client import OpenAIClient
        return OpenAIClient(
            api_key=api_key or os.environ.get("OPENAI_API_KEY"),
            model=model or detected_model,
            task=task,
        )

    raise ValueError(
        "LLM API 키가 설정되지 않았습니다.\n"
        "ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 .env 또는 환경변수에 추가하세요."
    )


def get_model_info() -> dict:
    """현재 설정된 모델 정보 반환 (디버깅/UI 표시용)."""
    return list_available_models()
