"""OpenAI client — openai v1+ API (ChatCompletion 구 버전 제거).

수정 사항:
  - openai.ChatCompletion.create (v0) → openai.OpenAI().chat.completions.create (v1+)
  - 모델명 하드코딩 제거 → src.config.models 사용
  - dotenv 중복 로드 제거 → src.config.env.bootstrap() 사용
"""
from __future__ import annotations

import os
from typing import List, Optional

from src.config.env import bootstrap
from src.config.logging_config import get_logger
from src.config.models import get_model

_log = get_logger(__name__)


class OpenAIClient:
    """OpenAI SDK v1+ 래퍼 (ClaudeClient와 동일 인터페이스)."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        task: str = "standard",
    ):
        bootstrap()

        try:
            import openai as _openai
        except ImportError:
            raise ImportError(
                "openai 패키지가 설치되어 있지 않습니다.\n"
                "  pip install openai"
            )

        resolved = api_key or os.environ.get("OPENAI_API_KEY", "")
        if not resolved:
            raise ValueError(
                "OPENAI_API_KEY가 설정되지 않았습니다.\n"
                "Medical-Agent/.env 파일에 OPENAI_API_KEY=sk-... 를 추가하세요."
            )

        self._openai = _openai
        self._client = _openai.OpenAI(api_key=resolved)

        if model:
            self.model = model
        else:
            _, self.model = get_model(task)
            # openai provider가 아닐 때 fallback
            from src.config.models import OPENAI
            if "claude" in self.model.lower():
                tier = "standard"
                self.model = OPENAI[tier]

        _log.debug(f"OpenAIClient 초기화: model={self.model}")

    # ── Core generation ───────────────────────────────────────────────────────

    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        stream: bool = False,
        max_tokens: int = 1500,
        task: Optional[str] = None,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context_chunks:
            ctx = "\n\n---\n\n".join(context_chunks)
            messages.append({"role": "system", "content": f"<context>\n{ctx}\n</context>"})
        messages.append({"role": "user", "content": user_message})

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content.strip()

        # Provenance — reuse runtime.provenance helper, graceful on fail.
        try:
            from src.runtime import provenance as _prov
            u = getattr(resp, "usage", None)
            _prov.auto_record_llm_call(
                provider="openai", model=self.model,
                prompt=user_message, system_prompt=system_prompt or "",
                response_sha=_prov.text_hash(text),
                tokens_in=int(getattr(u, "prompt_tokens", 0) or 0),
                tokens_out=int(getattr(u, "completion_tokens", 0) or 0),
                latency_ms=0,
            )
        except Exception:
            pass
        return text

    # ── 전문 논문 작업 (ClaudeClient와 동일 인터페이스) ───────────────────────

    def summarize_paper(self, paper_text: str) -> str:
        system = (
            "You are a medical research expert. Summarise the provided paper clearly and concisely. "
            "Structure your output as: Background, Objective, Methods, Results, Conclusion."
        )
        return self.generate(paper_text, system_prompt=system)

    def answer_from_papers(self, question: str, context_chunks: List[str]) -> str:
        system = (
            "You are a medical research assistant. Answer the question using ONLY the provided paper excerpts. "
            "If the answer is not in the excerpts, say so explicitly. Cite the source filename when available."
        )
        return self.generate(question, system_prompt=system, context_chunks=context_chunks)

    def draft_abstract(
        self, background: str, objective: str, methods: str,
        results: str, conclusion: str,
    ) -> str:
        system = (
            "You are a professional medical writer. Write a concise, well-structured abstract "
            "(≤250 words) for a medical research paper. Follow the IMRAD format."
        )
        prompt = (
            f"Background: {background}\nObjective: {objective}\nMethods: {methods}\n"
            f"Results: {results}\nConclusion: {conclusion}\n\nWrite the abstract."
        )
        return self.generate(prompt, system_prompt=system)
