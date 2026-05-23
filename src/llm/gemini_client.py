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
        # google.generativeai(deprecated)는 import 시 FutureWarning을 stderr로 쓴다.
        # Streamlit ScriptRunner 스레드에선 stderr가 닫혀 있어 "I/O operation on closed file"로
        # 초기화가 통째로 실패 → 무료 폴백이 막힌다. 경고 출력을 차단하고 닫힌 스트림도 무시한다.
        import warnings as _warnings
        import contextlib as _contextlib
        import io as _io
        try:
            with _warnings.catch_warnings():
                _warnings.simplefilter("ignore")
                # 일부 하위 라이브러리가 import 중 stderr/stdout에 직접 쓰는 경우까지 흡수
                with _contextlib.redirect_stderr(_io.StringIO()), _contextlib.redirect_stdout(_io.StringIO()):
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
        # gemini-flash-latest 등 사고형 모델은 출력 예산을 추론에 먼저 소비한다.
        # max_tokens가 너무 작으면 finish_reason=MAX_TOKENS로 text가 비어버리므로
        # 최소 256 토큰을 보장하고, 비면 더 큰 예산으로 1회 재시도한다.
        budget = max(int(max_tokens), 256)
        text = self._generate_once(model, user_message, budget)
        if text:
            return text
        text = self._generate_once(model, user_message, max(budget * 2, 2048))
        if text:
            return text
        # 끝까지 텍스트가 없으면 폴백이 동작하도록 명확히 예외 발생 (규칙 11)
        raise RuntimeError(
            f"Gemini({self.model}) 응답에 텍스트가 없습니다 "
            "(finish_reason=MAX_TOKENS 또는 SAFETY 추정) — 다른 provider로 폴백 필요"
        )

    def _generate_once(self, model, user_message: str, budget: int) -> str:
        try:
            resp = model.generate_content(
                user_message,
                generation_config={"max_output_tokens": int(budget)},
            )
        except Exception as e:
            _log.warning("Gemini generate 실패: %s", e)
            raise
        return self._extract_text(resp)

    @staticmethod
    def _extract_text(resp) -> str:
        """response.text quick accessor가 finish_reason=MAX_TOKENS 등에서 던지므로
        candidates→parts를 수동 조립해 부분 텍스트라도 안전하게 회수한다."""
        try:
            t = resp.text
            if t and t.strip():
                return t.strip()
        except Exception:
            pass
        out = []
        for cand in (getattr(resp, "candidates", None) or []):
            content = getattr(cand, "content", None)
            for part in (getattr(content, "parts", None) or []):
                t = getattr(part, "text", None)
                if t:
                    out.append(t)
        return "".join(out).strip()

    def generate_streamed(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> Iterator[str]:
        """ClaudeClient.generate_streamed와 동일 시그니처 (Failover 호환)."""
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
                generation_config={"max_output_tokens": max(int(max_tokens), 256)},
                stream=True,
            ):
                txt = self._extract_text(chunk)
                if txt:
                    yield txt
        except Exception as e:
            _log.warning("Gemini stream 실패: %s", e)
            raise

    # 하위호환 별칭
    def stream(self, *args, **kwargs) -> Iterator[str]:
        yield from self.generate_streamed(*args, **kwargs)

    # ClaudeClient 호환용 보조 메서드 (RAG/요약 경로) ─────────────────────────
    def answer_from_papers(self, question: str, context_chunks: List[str], context_prefix: str = "") -> str:
        base = (
            "You are a medical research assistant. Answer using ONLY the provided excerpts. "
            "If the answer is absent, say so. Cite the source filename when available."
        )
        system = f"{context_prefix}\n\n{base}" if context_prefix else base
        return self.generate(question, system_prompt=system, context_chunks=context_chunks, task="qa")
