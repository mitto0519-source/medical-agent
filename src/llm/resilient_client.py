"""Resilient LLM Client — Multi-provider failover (Claude → GPT-4 → Gemini).

시스템 가용성(Availability) 공식:
  A = 1 - (P(Claude fails) × P(GPT-4 fails) × P(Gemini fails))

목표: 단일 API 에러로 파이프라인이 멈추지 않도록 자동 라우팅.
"""
from __future__ import annotations

import os
from typing import Iterator, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

FAILOVER_ORDER = ["anthropic", "openai", "google"]


class ResilientLLMClient:
    """다중 모델 자동 페일오버 클라이언트."""

    def __init__(self, task: str = "standard", fallback_chain: Optional[List[str]] = None):
        """
        Args:
            task: 작업 유형
            fallback_chain: 페일오버 순서. None이면 FAILOVER_ORDER 사용.
        """
        self.task = task
        self.fallback_chain = fallback_chain or FAILOVER_ORDER
        self._client = None
        self._used_provider = None

    def _try_client(self, provider: str):
        """주어진 provider의 클라이언트 생성 시도."""
        try:
            if provider == "anthropic":
                if not os.environ.get("ANTHROPIC_API_KEY"):
                    _log.debug("Claude: API 키 미설정")
                    return None
                from src.llm.claude_client import ClaudeClient
                client = ClaudeClient(task=self.task)
                _log.info("✅ Claude 클라이언트 초기화 성공")
                return client, "claude"

            elif provider == "openai":
                if not os.environ.get("OPENAI_API_KEY"):
                    _log.debug("GPT-4: API 키 미설정")
                    return None
                from src.llm.openai_client import OpenAIClient
                client = OpenAIClient(task=self.task)
                _log.info("✅ GPT-4 클라이언트 초기화 성공")
                return client, "gpt4"

            elif provider == "google":
                if not os.environ.get("GOOGLE_API_KEY"):
                    _log.debug("Gemini: API 키 미설정")
                    return None
                _log.info("⚠️ Gemini: 아직 미구현 (fallback 체인에서 건너뜀)")
                return None

        except Exception as e:
            _log.warning(f"[{provider.upper()}] 초기화 실패: {e}")
            return None

    def _get_client(self):
        """페일오버 체인을 따라 작동하는 클라이언트 획득."""
        if self._client is not None:
            return self._client, self._used_provider

        for provider in self.fallback_chain:
            result = self._try_client(provider)
            if result:
                client, name = result
                self._client = client
                self._used_provider = name
                return client, name

        raise RuntimeError(
            f"모든 LLM 백업이 실패했습니다.\n"
            f"설정된 API 키 확인: ANTHROPIC_API_KEY, OPENAI_API_KEY, GOOGLE_API_KEY"
        )

    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        stream: bool = False,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> str:
        """텍스트 생성 (자동 페일오버 포함)."""
        for i, provider in enumerate(self.failover_chain):
            try:
                client, name = self._try_client(provider)
                if client is None:
                    continue

                _log.info(f"[{i+1}/{len(self.fallover_chain)}] {name.upper()} 시도 중...")
                response = client.generate(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    context_chunks=context_chunks,
                    stream=stream,
                    max_tokens=max_tokens,
                    task=task or self.task,
                )
                self._client = client
                self._used_provider = name
                _log.info(f"✅ {name.upper()}에서 생성 완료")
                return response

            except Exception as e:
                error_msg = str(e)
                if "credit" in error_msg.lower() or "quota" in error_msg.lower():
                    _log.warning(f"[{name.upper()}] 할당량 초과: {error_msg[:80]}")
                else:
                    _log.warning(f"[{name.upper()}] 오류: {error_msg[:80]}")

                if i < len(self.failover_chain) - 1:
                    next_provider = self.failover_chain[i + 1]
                    _log.info(f"→ {next_provider.upper()}로 자동 페일오버...")
                else:
                    _log.error("모든 LLM 백업이 소진되었습니다.")
                    raise

        raise RuntimeError("모든 페일오버 시도 실패")

    def generate_streamed(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> Iterator[str]:
        """스트리밍 생성 (자동 페일오버 포함)."""
        for i, provider in enumerate(self.failover_chain):
            try:
                client, name = self._try_client(provider)
                if client is None:
                    continue

                _log.info(f"[스트림] {name.upper()} 시도 중...")
                for chunk in client.generate_streamed(
                    user_message=user_message,
                    system_prompt=system_prompt,
                    context_chunks=context_chunks,
                    max_tokens=max_tokens,
                    task=task or self.task,
                ):
                    yield chunk
                self._client = client
                self._used_provider = name
                _log.info(f"✅ {name.upper()}에서 스트리밍 완료")
                return

            except Exception as e:
                _log.warning(f"[{name.upper()}] 스트림 오류: {str(e)[:80]}")
                if i < len(self.failover_chain) - 1:
                    _log.info(f"→ {self.failover_chain[i+1].upper()}로 자동 페일오버...")

        raise RuntimeError("모든 스트리밍 시도 실패")

    def get_used_provider(self) -> str:
        """현재 사용 중인 provider 반환 (UI 표시용)."""
        if self._used_provider is None:
            self._get_client()
        return self._used_provider
