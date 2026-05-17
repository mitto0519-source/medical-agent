import os
from typing import Optional

from .claude_client import ClaudeClient
from .openai_client import OpenAIClient


def get_llm_client(api_key: Optional[str] = None, provider: Optional[str] = None, model: Optional[str] = None):
    """Return a usable LLM client based on available keys or explicit provider."""
    provider = (provider or "").strip().lower()
    if provider == "anthropic":
        return ClaudeClient(api_key=api_key, model=model) if model else ClaudeClient(api_key=api_key)
    if provider == "openai":
        return OpenAIClient(api_key=api_key, model=model or OpenAIClient.DEFAULT_MODEL)

    # Prefer Anthropic if an Anthropic key exists.
    anthropic_key = api_key if api_key and api_key.startswith("sk-ant") else os.environ.get("ANTHROPIC_API_KEY")
    openai_key = api_key if api_key and api_key.startswith("sk-") and not api_key.startswith("sk-ant") else os.environ.get("OPENAI_API_KEY")

    if anthropic_key:
        return ClaudeClient(api_key=anthropic_key, model=model) if model else ClaudeClient(api_key=anthropic_key)
    if openai_key:
        return OpenAIClient(api_key=openai_key, model=model or OpenAIClient.DEFAULT_MODEL)

    # If API key is supplied but does not match the standard prefix, try both implementations.
    if api_key:
        try:
            return ClaudeClient(api_key=api_key, model=model) if model else ClaudeClient(api_key=api_key)
        except Exception:
            return OpenAIClient(api_key=api_key, model=model or OpenAIClient.DEFAULT_MODEL)

    raise ValueError(
        "LLM API 키가 설정되지 않았습니다. ANTHROPIC_API_KEY 또는 OPENAI_API_KEY를 .env 또는 환경변수에 추가하세요."
    )
