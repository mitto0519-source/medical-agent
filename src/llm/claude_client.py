"""Claude API client with streaming and prompt caching"""

import os
import anthropic
from typing import Iterator, List, Dict, Optional


class ClaudeClient:
    """Wrapper around the Anthropic Python SDK.

    Defaults to claude-opus-4-7 with adaptive thinking and streaming.
    Prompt caching is applied to the system prompt so repeated calls
    with the same large paper context don't re-process tokens.
    """

    DEFAULT_MODEL = "claude-opus-4-7"

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        resolved_key = api_key or os.environ.get("ANTHROPIC_API_KEY") or ""
        if not resolved_key:
            # Try loading dotenv one more time with explicit path
            try:
                from dotenv import load_dotenv as _ld
                from pathlib import Path as _P
                import inspect as _i
                _root = _P(_i.getfile(_i.currentframe())).parent.parent.parent
                _ld(dotenv_path=_root / ".env", override=True)
                resolved_key = os.environ.get("ANTHROPIC_API_KEY", "")
            except Exception:
                pass
        if not resolved_key:
            raise ValueError(
                "ANTHROPIC_API_KEY가 설정되지 않았습니다.\n"
                "1) Medical-Agent/.env 파일에 ANTHROPIC_API_KEY=sk-ant-... 를 추가하거나\n"
                "2) Streamlit Cloud Secrets에 추가하세요."
            )
        self._client = anthropic.Anthropic(api_key=resolved_key)
        self.model = model

    # ------------------------------------------------------------------
    # Core generation
    # ------------------------------------------------------------------

    def generate(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        stream: bool = False,
        max_tokens: int = 4096,
    ) -> str:
        """Generate a response, optionally with retrieved context.

        Args:
            user_message: The user's question or instruction
            system_prompt: High-level role/instructions for Claude
            context_chunks: Retrieved paper excerpts to inject into context
            stream: If True, use streaming (recommended for long responses)

        Returns:
            Complete response text
        """
        system = self._build_system(system_prompt, context_chunks)
        messages = [{"role": "user", "content": user_message}]

        if stream:
            return self._stream(system, messages, max_tokens=max_tokens)
        else:
            response = self._client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                thinking={"type": "adaptive"},
                system=system,
                messages=messages,
            )
            return self._extract_text(response)

    def generate_streamed(
        self,
        user_message: str,
        system_prompt: str = "",
        context_chunks: Optional[List[str]] = None,
        max_tokens: int = 4096,
    ) -> Iterator[str]:
        """Yield text tokens as they arrive (generator).

        Useful when you want to stream output to a UI in real time.
        """
        system = self._build_system(system_prompt, context_chunks)
        messages = [{"role": "user", "content": user_message}]

        with self._client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            thinking={"type": "adaptive"},
            system=system,
            messages=messages,
        ) as stream:
            for text in stream.text_stream:
                yield text

    # ------------------------------------------------------------------
    # Specialised paper tasks
    # ------------------------------------------------------------------

    def summarize_paper(self, paper_text: str) -> str:
        """Summarise a full paper text into structured sections."""
        system = (
            "You are a medical research expert. "
            "Summarise the provided paper clearly and concisely. "
            "Structure your output as: Background, Objective, Methods, Results, Conclusion."
        )
        return self.generate(paper_text, system_prompt=system)

    def answer_from_papers(self, question: str, context_chunks: List[str]) -> str:
        """Answer a question grounded in retrieved paper excerpts."""
        system = (
            "You are a medical research assistant. "
            "Answer the question using ONLY the provided paper excerpts. "
            "If the answer is not in the excerpts, say so explicitly. "
            "Cite the source filename when available."
        )
        return self.generate(question, system_prompt=system, context_chunks=context_chunks)

    def draft_abstract(self, background: str, objective: str, methods: str,
                       results: str, conclusion: str) -> str:
        """Generate a polished abstract using Claude."""
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
        return self.generate(prompt, system_prompt=system)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_system(self, base_prompt: str, context_chunks: Optional[List[str]]) -> list:
        """Build a system prompt list with optional prompt-cached context.

        Prepends the medical knowledge foundation preamble (if seed is built)
        before any task-specific or author-style prompt.
        """
        preamble = ""
        try:
            from src.knowledge.medical_seed import get_medical_preamble
            preamble = get_medical_preamble()
        except Exception:
            pass

        base = base_prompt or "You are a helpful medical research assistant."
        full_base = (preamble + base) if preamble else base

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

    def _stream(self, system, messages: list) -> str:
        with self._client.messages.stream(
            model=self.model,
            max_tokens=4096,
            thinking={"type": "adaptive"},
            system=system,
            messages=messages,
        ) as stream:
            return stream.get_final_message().content[0].text if stream.get_final_message().content else ""

    @staticmethod
    def _extract_text(response) -> str:
        for block in response.content:
            if block.type == "text":
                return block.text
        return ""
