"""Minimal OpenAI client wrapper compatible with existing usage.

This wrapper uses `openai` if available and maps a simple `generate`/`summarize_paper`
and `answer_from_papers` interface similar to `ClaudeClient`.
"""
import os
from typing import List, Optional

try:
    import openai
except Exception:
    openai = None


class OpenAIClient:
    DEFAULT_MODEL = "gpt-4"

    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        resolved = api_key or os.environ.get("OPENAI_API_KEY") or ""
        if not resolved:
            # try dotenv
            try:
                from dotenv import load_dotenv
                from pathlib import Path
                _root = Path(__file__).parent.parent.parent
                load_dotenv(_root / ".env")
                resolved = os.environ.get("OPENAI_API_KEY", "")
            except Exception:
                pass
        if not resolved:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 또는 환경변수를 확인하세요.")
        if openai is None:
            raise ImportError("openai 패키지가 설치되어 있지 않습니다. pip install openai")
        openai.api_key = resolved
        self.model = model

    def generate(self, user_message: str, system_prompt: str = "", context_chunks: Optional[List[str]] = None, stream: bool = False, max_tokens: int = 1500) -> str:
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if context_chunks:
            ctx = "\n\n---\n\n".join(context_chunks)
            messages.append({"role": "system", "content": f"<context>\n{ctx}\n</context>"})
        messages.append({"role": "user", "content": user_message})

        resp = openai.ChatCompletion.create(model=self.model, messages=messages, max_tokens=max_tokens)
        choice = resp.choices[0]
        if hasattr(choice, 'message'):
            content = choice.message.get('content') if isinstance(choice.message, dict) else choice.message['content']
        else:
            content = choice['message']['content']
        return content.strip()

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

    def draft_abstract(self, background: str, objective: str, methods: str, results: str, conclusion: str) -> str:
        system = (
            "You are a professional medical writer. Write a concise, well-structured abstract (≤250 words) for a medical research paper. Follow the IMRAD format."
        )
        prompt = (
            f"Background: {background}\nObjective: {objective}\nMethods: {methods}\nResults: {results}\nConclusion: {conclusion}\n\nWrite the abstract."
        )
        return self.generate(prompt, system_prompt=system)
