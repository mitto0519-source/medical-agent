"""Google Gemini API client — ClaudeClient/OpenAIClient와 동일 인터페이스.

Claude·OpenAI 크레딧 소진 시 무료 티어가 있는 Gemini로 폴백하기 위한 클라이언트.
페르소나 주입은 claude_client.build_base_system()을 공유해 일관성 유지(규칙 9).
"""
from __future__ import annotations

import os
from typing import Iterator, List, Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.config.models import get_model
from src.llm.claude_client import build_base_system

_log = get_logger(__name__)

# gemini-flash-latest = 무료 티어로 실제 작동 확인됨 (gemini-2.0-flash는 일부 키에서 limit:0).
# 환경변수 GEMINI_MODEL로 오버라이드 가능 (예: gemini-2.5-flash, gemma-4-31b-it).
_DEFAULT_GEMINI = "gemini-flash-latest"


class GeminiClient:
    """google-generativeai SDK 래퍼. ClaudeClient와 같은 generate() 시그니처."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        task: str = "standard",
    ):
        bootstrap()
        resolved_key = api_key or os.environ.get("GOOGLE_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "GOOGLE_API_KEY가 설정되지 않았습니다.\n"
                "Medical-Agent/.env 파일에 GOOGLE_API_KEY=... 를 추가하세요."
            )
        try:
            import google.generativeai as genai
        except ImportError as e:
            raise ImportError(
                "google-generativeai 패키지가 설치되어 있지 않습니다.\n  pip install google-generativeai"
            ) from e

        genai.configure(api_key=resolved_key)
        self._genai = genai

        # 모델: 명시 > 환경 GEMINI_MODEL > 기본
        self.model = model or os.environ.get("GEMINI_MODEL", _DEFAULT_GEMINI)
        self._task = task
        _log.debug("GeminiClient 초기화: model=%s, task=%s", self.model, task)

    # ── Core generation (ClaudeClient.generate와 동일 시그니처) ──────────────
    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        stream: bool = False,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> str:
        task = task or self._task
        full_system = build_base_system(system_prompt, task)
        if context_chunks:
            ctx = "\n\n---\n\n".join(context_chunks)
            full_system = f"{full_system}\n\n<context>\n{ctx}\n</context>"

        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=full_system or None,
        )
        gen_config = {"max_output_tokens": max_tokens}
        try:
            resp = model.generate_content(user_message, generation_config=gen_config)
            return (resp.text or "").strip()
        except Exception as e:
            _log.warning("Gemini generate 실패: %s", e)
            raise

    def stream(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> Iterator[str]:
        task = task or self._task
        full_system = build_base_system(system_prompt, task)
        if context_chunks:
            ctx = "\n\n---\n\n".join(context_chunks)
            full_system = f"{full_system}\n\n<context>\n{ctx}\n</context>"
        model = self._genai.GenerativeModel(
            model_name=self.model,
            system_instruction=full_system or None,
        )
        try:
            for chunk in model.generate_content(
                user_message,
                generation_config={"max_output_tokens": max_tokens},
                stream=True,
            ):
                if getattr(chunk, "text", None):
                    yield chunk.text
        except Exception as e:
            _log.warning("Gemini stream 실패: %s", e)
            raise
