"""ContinuityManager — per-session long-term memory wrapper.

Every agent (MedicalAgent, ResearchPipeline, MCP tools, Streamlit AI panel)
instantiates one of these at the top of each session/request.

Flow:
  1. cm = ContinuityManager(user_email="...", session_id="...")
  2. preamble = cm.get_preamble()   # inject into LLM system prompt
  3. ... do work ...
  4. cm.record(title="...", ...)    # log what was done

The preamble is cached per-session and refreshed whenever record() is called.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger
from src.memory import change_log

_log = get_logger(__name__)


class ContinuityManager:
    """Manages long-term memory continuity for one user session.

    Usage:
        cm = ContinuityManager(user_email="mitto0519@gmail.com")
        system_prompt = BASE_PROMPT + "\\n\\n" + cm.get_preamble()
        result = llm.generate(user_msg, system_prompt=system_prompt)
        cm.record("주제 생성 완료", description="KYRBS 5개 주제 생성",
                  action_type="topic_generate", outputs={"topics": topics})
    """

    def __init__(
        self,
        user_email: str = "",
        session_id: Optional[str] = None,
        history_n: int = 25,
    ):
        self.user_email = user_email
        self.session_id = session_id or (
            datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
        )
        self.history_n = history_n
        self._preamble: Optional[str] = None

    # ── Read ──────────────────────────────────────────────────────────

    def get_preamble(self, refresh: bool = False) -> str:
        """Return history context string for LLM system prompt injection.

        Returns empty string if no history yet (doesn't break anything).
        Cache is invalidated whenever record() is called.
        """
        if self._preamble is None or refresh:
            self._preamble = change_log.build_context_summary(
                user_email=self.user_email,
                n=self.history_n,
            )
        return self._preamble

    def get_recent_titles(self, n: int = 10) -> List[str]:
        """Return list of recent action titles for display."""
        entries = change_log.get_recent(n=n, user_email=self.user_email)
        return [
            f"[{str(e.get('timestamp',''))[:16]}] ({e.get('action_type','')}) {e.get('title','')}"
            for e in entries
        ]

    def get_recent_entries(self, n: int = 20, action_type: Optional[str] = None) -> List[Dict]:
        """Return raw entry dicts for timeline display."""
        return change_log.get_recent(n=n, user_email=self.user_email, action_type=action_type)

    # ── Write ─────────────────────────────────────────────────────────

    def record(
        self,
        title: str,
        description: str = "",
        action_type: str = "general",
        what_changed: Optional[Dict] = None,
        why_better: str = "",
        inputs: Optional[Dict] = None,
        outputs: Optional[Dict] = None,
        impact: Optional[Dict] = None,
    ) -> None:
        """Log an action and invalidate preamble cache."""
        entry = change_log.make_entry(
            title=title,
            description=description,
            action_type=action_type,
            user_email=self.user_email,
            session_id=self.session_id,
            what_changed=what_changed,
            why_better=why_better,
            inputs=inputs,
            outputs=outputs,
            impact=impact,
        )
        change_log.append(entry)
        self._preamble = None  # force re-read on next get_preamble()
        _log.info("[continuity] %s | %s", action_type, title)


# ── Module-level helpers for simple one-liner use ─────────────────────

def record(
    title: str,
    user_email: str = "",
    session_id: str = "",
    **kwargs,
) -> None:
    """One-liner shortcut — create a throwaway manager and record."""
    cm = ContinuityManager(user_email=user_email, session_id=session_id)
    cm.record(title=title, **kwargs)


def get_preamble(user_email: str = "", n: int = 25) -> str:
    """One-liner shortcut to get the context preamble."""
    return change_log.build_context_summary(user_email=user_email, n=n)
