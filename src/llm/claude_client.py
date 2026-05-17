"""Claude API client — streaming, prompt caching, extended thinking.

수정 사항 (버그 수정):
  1. thinking={"type":"adaptive"} → 중앙 models.py의 thinking_config() 사용
  2. _stream() max_tokens 파라미터 누락 → 수정
  3. 여러 모듈의 dotenv 중복 로드 → src.config.env.bootstrap() 사용
  4. 모델명 하드코딩 → src.config.models.get_model() 사용
"""
from __future__ import annotations

import os
from typing import Dict, Iterator, List, Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.config.models import get_model, thinking_config

_log = get_logger(__name__)


class ClaudeClient:
    """Anthropic Python SDK 래퍼.

    - 모델은 src.config.models에서 task 기반으로 자동 선택
    - Extended thinking: premium/standard task에서 자동 활성화
    - Prompt caching: 반복 컨텍스트를 ephemeral cache로 처리
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        task: str = "standard",
    ):
        bootstrap()  # .env 1회 로드 (이미 로드됐으면 무시)

        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
                "Medical-Agent/.env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하세요."
            )

        import anthropic
        self._client = anthropic.Anthropic(api_key=resolved_key)

        # 모델: 명시 지정 > 환경변수 오버라이드 > task 기반 자동 선택
        if model:
            self.model = model
        else:
            _, self.model = get_model(task)

        self._task = task
        _log.debug(f"ClaudeClient 초기화: model={self.model}, task={task}")

    # ── Core generation ───────────────────────────────────────────────────────

    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        stream: bool = False,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> str:
        """텍스트 생성.

        Args:
            user_message: 질문 또는 지시
            system_prompt: 역할/지시 프롬프트
            context_chunks: 검색된 논문 청크 (prompt cache 적용)
            stream: True면 streaming 사용
            max_tokens: 최대 출력 토큰
            task: thinking 레벨 결정용 task 이름 (기본: 초기화 시 task)
        """
        effective_task = task or self._task
        system = self._build_system(system_prompt, context_chunks)
        messages = [{"role": "user", "content": user_message}]

        if stream:
            return self._stream(system, messages, max_tokens=max_tokens, task=effective_task)

        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        t_cfg = thinking_config(effective_task)
        if t_cfg and t_cfg.get("type") == "enabled":
            # budget_tokens must be strictly less than max_tokens
            if t_cfg.get("budget_tokens", 0) >= max_tokens:
                t_cfg = {"type": "disabled"}
        if t_cfg:
            kwargs["thinking"] = t_cfg

        try:
            response = self._client.messages.create(**kwargs)
        except Exception as e:
            # thinking 파라미터 미지원 모델 폴백
            if "thinking" in str(e).lower() and "thinking" in kwargs:
                _log.warning(f"thinking 파라미터 미지원, 재시도: {e}")
                del kwargs["thinking"]
                response = self._client.messages.create(**kwargs)
            else:
                raise

        return self._extract_text(response)

    def generate_streamed(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 4096,
        task: Optional[str] = None,
    ) -> Iterator[str]:
        """토큰 단위 스트리밍 생성기."""
        effective_task = task or self._task
        system = self._build_system(system_prompt, context_chunks)
        messages = [{"role": "user", "content": user_message}]

        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        t_cfg = thinking_config(effective_task)
        if t_cfg and t_cfg.get("type") == "enabled":
            if t_cfg.get("budget_tokens", 0) >= max_tokens:
                t_cfg = {"type": "disabled"}
        if t_cfg:
            kwargs["thinking"] = t_cfg

        try:
            with self._client.messages.stream(**kwargs) as s:
                for text in s.text_stream:
                    yield text
        except Exception as e:
            if "thinking" in str(e).lower() and "thinking" in kwargs:
                _log.warning(f"thinking 스트리밍 미지원, 폴백: {e}")
                del kwargs["thinking"]
                with self._client.messages.stream(**kwargs) as s:
                    for text in s.text_stream:
                        yield text
            else:
                raise

    # ── 전문 논문 작업 ────────────────────────────────────────────────────────

    def summarize_paper(self, paper_text: str) -> str:
        system = (
            "You are a medical research expert. "
            "Summarise the provided paper clearly and concisely. "
            "Structure your output as: Background, Objective, Methods, Results, Conclusion."
        )
        return self.generate(paper_text, system_prompt=system, task="summary")

    def answer_from_papers(
        self,
        question: str,
        context_chunks: List[str],
        context_prefix: str = "",
    ) -> str:
        base = (
            "You are a medical research assistant. "
            "Answer the question using ONLY the provided paper excerpts. "
            "If the answer is not in the excerpts, say so explicitly. "
            "Cite the source filename when available."
        )
        system = f"{context_prefix}\n\n{base}" if context_prefix else base
        return self.generate(
            question, system_prompt=system,
            context_chunks=context_chunks, task="qa",
        )

    def draft_abstract(
        self, background: str, objective: str, methods: str,
        results: str, conclusion: str,
    ) -> str:
        system = (
            "You are a professional medical writer. "
            "Write a concise, well-structured abstract (≤250 words) for a medical research paper. "
            "Follow the IMRAD format."
        )
        prompt = (
            f"Background: {background}\n"
            f"Objective: {objective}\n"
            f"Methods: {methods}\n"
            f"Results: {results}\n"
            f"Conclusion: {conclusion}\n\n"
            "Write the abstract."
        )
        return self.generate(prompt, system_prompt=system, task="abstract")

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────────

    def _build_system(
        self,
        base_prompt: str,
        context_chunks: Optional[List[str]],
    ):
        """시스템 프롬프트 구성. context가 있으면 prompt cache 적용."""
        preamble = ""
        try:
            from src.knowledge.medical_seed import get_medical_preamble
            preamble = get_medical_preamble()
        except Exception:
            pass

        base = base_prompt or "You are a helpful medical research assistant."
        full_base = (preamble + "\n\n" + base) if preamble else base

        if not context_chunks:
            return full_base

        context_text = "\n\n---\n\n".join(context_chunks)
        return [
            {"type": "text", "text": full_base},
            {
                "type": "text",
                "text": f"<context>\n{context_text}\n</context>",
                "cache_control": {"type": "ephemeral"},
            },
        ]

    def _stream(
        self,
        system,
        messages: list,
        max_tokens: int = 4096,
        task: str = "standard",
    ) -> str:
        """스트리밍으로 완전한 응답 반환."""
        kwargs = dict(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=messages,
        )
        t_cfg = thinking_config(task)
        if t_cfg and t_cfg.get("type") == "enabled":
            if t_cfg.get("budget_tokens", 0) >= max_tokens:
                t_cfg = {"type": "disabled"}
        if t_cfg:
            kwargs["thinking"] = t_cfg

        try:
            with self._client.messages.stream(**kwargs) as s:
                msg = s.get_final_message()
                return self._extract_text(msg)
        except Exception as e:
            if "thinking" in str(e).lower() and "thinking" in kwargs:
                del kwargs["thinking"]
                with self._client.messages.stream(**kwargs) as s:
                    msg = s.get_final_message()
                    return self._extract_text(msg)
            raise

    @classmethod
    def _extract_text(cls, response) -> str:
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                return block.text
        _log.warning(
            "API 응답에 text 블록이 없습니다. stop_reason=%s, blocks=%s",
            getattr(response, "stop_reason", "?"),
            [getattr(b, "type", "?") for b in response.content],
        )
        return ""
