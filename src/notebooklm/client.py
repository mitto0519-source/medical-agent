"""NotebookLM Python API wrapper.

Primary cloud storage for the Medical-Agent research pipeline.
Auth tokens are read from the notebooklm-mcp-cli cache (~/.notebooklm-mcp-cli/).
Falls back to local ChromaDB when NotebookLM is unreachable.
"""

from __future__ import annotations

from typing import Any

from src.config.logging_config import get_logger

logger = get_logger(__name__)


def _make_client():
    """Build an authenticated NotebookLMClient or raise if auth missing."""
    from notebooklm_tools import NotebookLMClient
    from notebooklm_tools.core.auth import load_cached_tokens

    tokens = load_cached_tokens()
    if tokens is None:
        raise RuntimeError(
            "NotebookLM auth tokens not found. "
            "Run 'notebooklm-mcp login' or 'nlm login' first."
        )
    return NotebookLMClient(
        cookies=tokens.cookies,
        csrf_token=tokens.csrf_token,
        session_id=tokens.session_id,
        build_label=tokens.build_label,
    )


class NLMClient:
    """Thin synchronous wrapper around NotebookLMClient for use in Streamlit."""

    def __init__(self):
        self._client = None
        self._available: bool | None = None

    # ------------------------------------------------------------------
    # Availability
    # ------------------------------------------------------------------

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            self._client = _make_client()
            # Lightweight probe: list notebooks (fast RPC)
            self._client.list_notebooks()
            self._available = True
        except Exception as e:
            logger.warning(f"[NLM] Not available: {e}")
            self._available = False
        return self._available

    def _c(self):
        if self._client is None:
            self._client = _make_client()
        return self._client

    # ------------------------------------------------------------------
    # Notebooks
    # ------------------------------------------------------------------

    def list_notebooks(self) -> list[dict]:
        nbs = self._c().list_notebooks()
        return [
            {
                "id": nb.id,
                "title": nb.title,
                "source_count": getattr(nb, "source_count", 0),
            }
            for nb in (nbs or [])
        ]

    def find_notebook_by_title(self, title: str) -> str | None:
        for nb in self.list_notebooks():
            if nb["title"] == title:
                return nb["id"]
        return None

    def create_notebook(self, title: str) -> str:
        """Create notebook and return its ID."""
        nb = self._c().create_notebook(title)
        return nb.id if hasattr(nb, "id") else nb["id"]

    def get_or_create_notebook(self, title: str) -> str:
        nb_id = self.find_notebook_by_title(title)
        if nb_id:
            return nb_id
        return self.create_notebook(title)

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def add_text_source(self, notebook_id: str, title: str, text: str) -> bool:
        try:
            self._c().add_text_source(notebook_id, text, title=title)
            return True
        except Exception as e:
            logger.warning(f"[NLM] add_text_source failed: {e}")
            return False

    def add_url_source(self, notebook_id: str, url: str) -> bool:
        try:
            self._c().add_url_source(notebook_id, url)
            return True
        except Exception as e:
            logger.warning(f"[NLM] add_url_source failed: {e}")
            return False

    def add_file_source(self, notebook_id: str, file_path: str) -> bool:
        try:
            result = self._c().add_file(notebook_id, file_path)
            return bool(result)
        except Exception as e:
            logger.warning(f"[NLM] add_file_source failed: {e}")
            return False

    def get_sources(self, notebook_id: str) -> list[dict]:
        try:
            raw = self._c().get_notebook_sources_with_types(notebook_id)
            return raw if isinstance(raw, list) else []
        except Exception as e:
            logger.warning(f"[NLM] get_sources failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Query / Analysis
    # ------------------------------------------------------------------

    def query(self, notebook_id: str, question: str) -> str:
        try:
            result = self._c().query(notebook_id, question)
            if isinstance(result, dict):
                return result.get("answer", result.get("text", str(result)))
            return str(result)
        except Exception as e:
            logger.warning(f"[NLM] query failed: {e}")
            return f"[NotebookLM query error: {e}]"

    def get_summary(self, notebook_id: str) -> dict[str, Any]:
        try:
            return self._c().get_notebook_summary(notebook_id) or {}
        except Exception as e:
            logger.warning(f"[NLM] get_summary failed: {e}")
            return {}
