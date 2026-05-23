"""LLM 클라이언트 팩토리 — provider 자동 선택 + Multi-LLM Failover.

우선순위:
  1. 명시적 provider 지정
  2. api_key 접두어 기반 자동 감지
  3. 환경변수 기반 자동 선택 (Anthropic 우선)
  4. with_failover=True 시 — 1순위 실패 시 2순위 자동 전환
"""
from __future__ import annotations

import os
import time
from typing import Iterator, List, Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.config.models import get_model, list_available_models

_log = get_logger(__name__)

# Claude API에서 재시도해야 하는 에러 코드 (크레딧 고갈, 레이트리밋, 일시 장애)
_RETRYABLE_STATUS = {429, 529, 503, 502, 500}
# Failover 트리거 에러 (인증 실패 or 크레딧 고갈은 재시도 무의미 → 즉시 failover)
_FAILOVER_TRIGGER_STATUS = {400, 401, 403, 429}


# ── 실제 client 생성 ──────────────────────────────────────────────────────────

def _make_client(provider: str, api_key: Optional[str], model: Optional[str], task: str):
    """provider 문자열 → 실제 LLM client 객체."""
    if provider == "anthropic":
        from src.llm.claude_client import ClaudeClient
        return ClaudeClient(api_key=api_key, model=model, task=task)
    if provider == "openai":
        from src.llm.openai_client import OpenAIClient
        return OpenAIClient(api_key=api_key, model=model, task=task)
    if provider in ("google", "gemini"):
        from src.llm.gemini_client import GeminiClient
        return GeminiClient(api_key=api_key, model=model, task=task)
    raise ValueError(f"알 수 없는 provider: {provider}")


def _detect_provider_from_key(api_key: str) -> Optional[str]:
    if api_key.startswith("sk-ant"):
        return "anthropic"
    if api_key.startswith("sk-"):
        return "openai"
    return None


def _resolve_provider_order() -> list[str]:
    """환경변수로 사용 가능한 provider 목록을 우선순위 순으로 반환."""
    bootstrap()
    order = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        order.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        order.append("openai")
    if os.environ.get("GOOGLE_API_KEY"):
        order.append("google")
    # 자동 검색 최적화: 실제로 작동하는 provider를 우선 (죽은 것은 쿨다운 후순위)
    try:
        from src.llm.health import order_by_health
        order = order_by_health(order)
    except Exception:
        pass
    return order


def _provider_of(client) -> str:
    """client 객체 → provider 문자열 (건강도 기록용)."""
    return {
        "ClaudeClient": "anthropic",
        "OpenAIClient": "openai",
        "GeminiClient": "google",
    }.get(type(client).__name__, "unknown")


# ── Failover Wrapper ──────────────────────────────────────────────────────────

class _FailoverClient:
    """1순위 클라이언트 실패 시 2순위로 자동 전환하는 래퍼."""

    def __init__(self, primary, fallbacks: list, task: str = "standard"):
        self._primary = primary
        self._fallbacks = fallbacks  # list of (provider, api_key, model)
        self._task = task
        self._active = primary
        self.model = getattr(primary, "model", "unknown")

    def _switch_to_fallback(self, err: Exception) -> bool:
        """가용한 fallback client를 생성해 _active로 교체. 성공 시 True."""
        for provider, api_key, model in self._fallbacks:
            try:
                client = _make_client(provider, api_key, model, self._task)
                _log.warning(
                    "LLM Failover: %s 오류 → %s 전환. 원인: %s",
                    type(self._active).__name__, provider, err,
                )
                self._active = client
                self.model = getattr(client, "model", "unknown")
                return True
            except Exception as fe:
                _log.warning("Failover %s 초기화 실패: %s", provider, fe)
        return False

    def _is_failover_trigger(self, err: Exception) -> bool:
        msg = str(err)
        for code in _FAILOVER_TRIGGER_STATUS:
            if f"Error code: {code}" in msg or f" {code} " in msg:
                return True
        # API key invalid, credit exhausted 등
        keywords = ["authentication_error", "invalid x-api-key", "credit", "insufficient_quota",
                    "rate_limit", "overloaded", "529"]
        return any(k in msg.lower() for k in keywords)

    def generate(self, user_message: str, **kwargs) -> str:
        from src.llm.health import record_success, record_failure
        # 1. 현재 active 시도
        try:
            result = self._active.generate(user_message, **kwargs)
            record_success(_provider_of(self._active))
            return result
        except Exception as e:
            last_err = e
            record_failure(_provider_of(self._active), str(e))
            if not self._is_failover_trigger(e):
                raise
        # 2. 모든 fallback을 순차 연쇄 시도 (작동하는 provider까지)
        for provider, api_key, model in self._fallbacks:
            try:
                client = _make_client(provider, api_key, model, self._task)
            except Exception as ce:
                _log.warning("Failover %s 초기화 실패: %s", provider, ce)
                record_failure(provider, str(ce))
                continue
            _log.warning("LLM Failover → %s 전환. 원인: %s", provider, last_err)
            self._active = client
            try:
                result = client.generate(user_message, **kwargs)
                record_success(provider)
                return result
            except Exception as e:
                last_err = e
                record_failure(provider, str(e))
                if not self._is_failover_trigger(e):
                    raise
                continue  # 다음 fallback으로
        raise last_err

    def generate_streamed(self, user_message: str, **kwargs) -> Iterator[str]:
        try:
            yield from self._active.generate_streamed(user_message, **kwargs)
        except Exception as e:
            if self._is_failover_trigger(e) and self._switch_to_fallback(e):
                yield from self._active.generate_streamed(user_message, **kwargs)
            else:
                raise

    def summarize_paper(self, paper_text: str) -> str:
        return self.generate(paper_text, system_prompt=(
            "You are a medical research expert. Summarise the paper: "
            "Background, Objective, Methods, Results, Conclusion."
        ), task="summary")

    def answer_from_papers(self, question: str, context_chunks: List[str], context_prefix: str = "") -> str:
        return self._active.answer_from_papers(question, context_chunks, context_prefix)

    def draft_abstract(self, background: str, objective: str, methods: str, results: str, conclusion: str) -> str:
        return self._active.draft_abstract(background, objective, methods, results, conclusion)

    def _build_system(self, base_prompt: str, context_chunks, task: str = "general"):
        return self._active._build_system(base_prompt, context_chunks, task)


# ── 공개 API ──────────────────────────────────────────────────────────────────

def get_llm_client(
    api_key: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    task: str = "standard",
    with_failover: bool = True,
):
    """task에 맞는 LLM 클라이언트 반환.

    Args:
        api_key: API 키 (None이면 환경변수 자동 사용)
        provider: "anthropic" | "openai" | None(자동)
        model: 특정 모델 ID 강제 (None이면 task 기반 자동 선택)
        task: "ocr" | "qa" | "summary" | "paper_writing" | "standard" 등
        with_failover: True면 1순위 실패 시 자동 failover 래퍼 활성화

    Returns:
        ClaudeClient, OpenAIClient, 또는 _FailoverClient
    """
    bootstrap()

    explicit_provider = (provider or "").strip().lower()

    # ── 명시적 provider 지정 ─────────────────────────────────────────────
    if explicit_provider in ("anthropic", "claude"):
        primary = _make_client("anthropic", api_key, model, task)
        if not with_failover:
            return primary
        fallbacks = _build_fallbacks("anthropic", task)
        return _FailoverClient(primary, fallbacks, task) if fallbacks else primary

    if explicit_provider in ("openai", "gpt-4", "gpt"):
        primary = _make_client("openai", api_key, model, task)
        if not with_failover:
            return primary
        fallbacks = _build_fallbacks("openai", task)
        return _FailoverClient(primary, fallbacks, task) if fallbacks else primary

    # ── api_key 접두어로 자동 감지 ──────────────────────────────────────
    if api_key:
        detected = _detect_provider_from_key(api_key)
        if detected:
            primary = _make_client(detected, api_key, model, task)
            if not with_failover:
                return primary
            fallbacks = _build_fallbacks(detected, task)
            return _FailoverClient(primary, fallbacks, task) if fallbacks else primary

    # ── 환경변수 기반 자동 선택 (Anthropic 우선) ────────────────────────
    order = _resolve_provider_order()
    if not order:
        raise ValueError(
            "LLM API 키가 설정되지 않았습니다.\n"
            "ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 .env 또는 환경변수에 추가하세요."
        )

    # 1순위 client 생성 (건강도 최적화로 정렬된 order[0] = 작동하는 provider 우선)
    primary_provider = order[0]
    _key_env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    primary_key = os.environ.get(_key_env.get(primary_provider, ""))
    _detected_provider, _detected_model = get_model(task)
    # claude/openai 모델명을 Gemini에 넘기면 안 됨 — google이면 자체 기본 모델 사용
    _model = model or (_detected_model if primary_provider in ("anthropic", "openai") else None)
    primary = _make_client(primary_provider, primary_key, _model, task)

    if not with_failover or len(order) < 2:
        return primary

    fallbacks = _build_fallbacks(primary_provider, task)
    return _FailoverClient(primary, fallbacks, task) if fallbacks else primary


def _build_fallbacks(primary_provider: str, task: str) -> list:
    """primary 이외 사용 가능한 provider를 fallback 리스트로 반환."""
    bootstrap()
    fallbacks = []
    providers = [p for p in _resolve_provider_order() if p != primary_provider]
    _key_env = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "google": "GOOGLE_API_KEY",
    }
    for p in providers:
        key = os.environ.get(_key_env.get(p, ""))
        if key:
            fallbacks.append((p, key, None))
    return fallbacks


def get_model_info() -> dict:
    """현재 설정된 모델 정보 반환 (디버깅/UI 표시용)."""
    return list_available_models()
