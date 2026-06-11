"""OpenRouter 클라이언트 — 무료 고품질 모델로 결제 잠긴 상황 해결.

핵심: OpenAI SDK 호환 endpoint. base_url만 바꾸면 OpenRouter의 수십 개 모델 사용 가능.
무료 모델은 빠르고 쿼터가 거의 무제한 — Anthropic 크레딧 부족 / OpenAI 쿼터 초과 /
Gemini 무료 RPM 5 한계 모두 우회.

가입: https://openrouter.ai/keys (이메일만, 결제 정보 불필요)
.env 에 OPENROUTER_API_KEY=sk-or-v1-... 추가.

모델 후보 (2026-06 기준 무료):
- nvidia/nemotron-nano-9b-v2:free  (가장 빠름, 9B)
- google/gemma-3n-e4b-it:free       (4B, 안정적)
- meta-llama/llama-3.3-70b-instruct:free (큰 모델, 가끔 느림)
- mistralai/mistral-7b-instruct:free
- microsoft/phi-3.5-mini-128k-instruct:free
"""
from __future__ import annotations

import os
from typing import List, Optional, Iterator

from src.config.env import bootstrap
from src.config.logging_config import get_logger

_log = get_logger(__name__)

_FREE_MODELS_PREFERRED = [
    "google/gemma-3n-e4b-it:free",
    "nvidia/nemotron-nano-9b-v2:free",
    "mistralai/mistral-7b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]


class OpenRouterClient:
    """OpenRouter OpenAI 호환 endpoint 래퍼.

    동일 인터페이스: generate / generate_streamed / summarize_paper / answer_from_papers /
    draft_abstract / _build_system  (ClaudeClient·OpenAIClient와 swap 가능).
    """

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
            raise ImportError("openai 패키지 필요: pip install openai")

        resolved = api_key or os.environ.get("OPENROUTER_API_KEY", "")
        if not resolved:
            raise ValueError(
                "OPENROUTER_API_KEY가 설정되지 않았습니다.\n"
                "가입(무료, 카드 불필요): https://openrouter.ai/keys"
            )

        self._client = _openai.OpenAI(
            api_key=resolved,
            base_url="https://openrouter.ai/api/v1",
        )
        self.model = model or _FREE_MODELS_PREFERRED[0]
        self._fallback_models = [m for m in _FREE_MODELS_PREFERRED if m != self.model]
        self._task = task
        _log.debug("OpenRouterClient 초기화: model=%s task=%s", self.model, task)

    def _try_model(self, model: str, messages: list, max_tokens: int) -> str:
        resp = self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            extra_headers={
                "HTTP-Referer": "https://huggingface.co/spaces/cave87/medical-agent",
                "X-Title": "Medical-Agent",
            },
        )
        return (resp.choices[0].message.content or "").strip()

    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 1500,
        task: Optional[str] = None,
        **_ignored,
    ) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context_chunks:
            ctx = "\n\n---\n\n".join(context_chunks)
            messages.append({"role": "system", "content": f"<context>\n{ctx}\n</context>"})
        messages.append({"role": "user", "content": user_message})

        # 무료 모델 순환 — 첫 모델이 rate-limit 걸리면 다음 무료 모델로
        models_to_try = [self.model] + self._fallback_models
        last_err = None
        for m in models_to_try:
            try:
                out = self._try_model(m, messages, max_tokens)
                if out:
                    if m != self.model:
                        _log.info("OpenRouter 모델 순환: %s → %s", self.model, m)
                        self.model = m
                    return out
            except Exception as e:
                last_err = e
                _log.warning("OpenRouter %s 실패: %s", m, str(e)[:140])
                continue
        raise RuntimeError(f"OpenRouter 전체 무료 모델 실패: {last_err}")

    def generate_streamed(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 1500,
        **_ignored,
    ) -> Iterator[str]:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context_chunks:
            ctx = "\n\n---\n\n".join(context_chunks)
            messages.append({"role": "system", "content": f"<context>\n{ctx}\n</context>"})
        messages.append({"role": "user", "content": user_message})

        stream = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=max_tokens,
            stream=True,
            extra_headers={
                "HTTP-Referer": "https://huggingface.co/spaces/cave87/medical-agent",
                "X-Title": "Medical-Agent",
            },
        )
        for chunk in stream:
            try:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
            except Exception:
                continue

    def summarize_paper(self, paper_text: str) -> str:
        return self.generate(paper_text, system_prompt=(
            "You are a medical research expert. Summarise: "
            "Background, Objective, Methods, Results, Conclusion."
        ))

    def answer_from_papers(self, question: str, context_chunks: List[str], context_prefix: str = "") -> str:
        system = (
            "You are a medical research assistant. Answer using ONLY the provided paper excerpts. "
            "If not in excerpts, say so. Cite the source filename when available."
        )
        return self.generate(question, system_prompt=system, context_chunks=context_chunks)

    def draft_abstract(self, background: str, objective: str, methods: str,
                        results: str, conclusion: str) -> str:
        system = (
            "Professional medical writer. Concise IMRAD abstract (≤250 words)."
        )
        prompt = (
            f"Background: {background}\nObjective: {objective}\nMethods: {methods}\n"
            f"Results: {results}\nConclusion: {conclusion}\n\nWrite the abstract."
        )
        return self.generate(prompt, system_prompt=system)

    def _build_system(self, base_prompt: str, context_chunks, task: str = "general"):
        return base_prompt
