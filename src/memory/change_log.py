"""Timebased change log — the single source of long-term continuity.

Every significant action across ALL agents (Streamlit, MCP, Claude Code,
ResearchPipeline) is appended here. Agents read this before every task so
they never lose context, never contradict past decisions, and always build
incrementally forward.

Storage: local JSON (data/change_log/history.json) + Supabase ma_change_log
         (dual-write; local is always written, cloud when available)

Action types:
  qa              — Q&A interaction with the agent
  topic_generate  — Research topic proposal
  novelty_check   — PubMed novelty verification
  paper_write     — Paper draft generation
  learn           — Document ingested into RAG
  workflow_step   — Research workflow stage completion/approval
  config_change   — Code or configuration modification
  mcp_tool        — MCP server tool call
  general         — Anything else
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_LOG_DIR = Path("data/change_log")
_LOG_FILE = _LOG_DIR / "history.json"
_MAX_LOCAL = 1000


# ── Data model ────────────────────────────────────────────────────────

@dataclass
class ChangeLogEntry:
    id: str
    timestamp: str
    user_email: str
    session_id: str
    action_type: str
    title: str
    description: str = ""
    what_changed: Dict[str, Any] = field(default_factory=dict)
    why_better: str = ""
    inputs: Dict[str, Any] = field(default_factory=dict)
    outputs: Dict[str, Any] = field(default_factory=dict)
    impact: Dict[str, Any] = field(default_factory=dict)


# ── Cloud helpers ─────────────────────────────────────────────────────

def _cloud() -> bool:
    try:
        from src.cloud.db import cloud_available
        return cloud_available()
    except Exception:
        return False


def _engine():
    from src.cloud.db import get_engine
    return get_engine()


# ── Write ─────────────────────────────────────────────────────────────

def append(entry: ChangeLogEntry) -> None:
    """Append entry to local JSON (always) and Supabase (when available)."""
    _write_local(entry)
    if _cloud():
        try:
            _write_cloud(entry)
        except Exception as e:
            _log.warning("Cloud change_log write failed: %s", e)


def _write_local(entry: ChangeLogEntry) -> None:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
    existing = _load_local()
    existing.insert(0, asdict(entry))
    _LOG_FILE.write_text(
        json.dumps(existing[:_MAX_LOCAL], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _write_cloud(entry: ChangeLogEntry) -> None:
    from sqlalchemy import text
    with _engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO ma_change_log
                (id, timestamp, user_email, session_id, action_type, title,
                 description, what_changed, why_better, inputs, outputs, impact)
            VALUES
                (:id, :ts, :user_email, :session_id, :action_type, :title,
                 :description,
                 CAST(:what_changed AS jsonb), :why_better,
                 CAST(:inputs AS jsonb), CAST(:outputs AS jsonb),
                 CAST(:impact AS jsonb))
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": entry.id,
            "ts": entry.timestamp,
            "user_email": entry.user_email,
            "session_id": entry.session_id,
            "action_type": entry.action_type,
            "title": entry.title,
            "description": entry.description,
            "what_changed": json.dumps(entry.what_changed, ensure_ascii=False),
            "why_better": entry.why_better,
            "inputs": json.dumps(entry.inputs, ensure_ascii=False),
            "outputs": json.dumps(entry.outputs, ensure_ascii=False),
            "impact": json.dumps(entry.impact, ensure_ascii=False),
        })


# ── Read ──────────────────────────────────────────────────────────────

def _load_local() -> List[Dict]:
    if not _LOG_FILE.exists():
        return []
    try:
        return json.loads(_LOG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def get_recent(
    n: int = 50,
    user_email: Optional[str] = None,
    action_type: Optional[str] = None,
) -> List[Dict]:
    """Return most recent n entries, optionally filtered."""
    if _cloud():
        try:
            from sqlalchemy import text
            conditions, params = [], {"lim": n}
            if user_email:
                conditions.append("user_email = :email")
                params["email"] = user_email
            if action_type:
                conditions.append("action_type = :atype")
                params["atype"] = action_type
            where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
            with _engine().connect() as conn:
                rows = conn.execute(
                    text(f"SELECT * FROM ma_change_log {where} ORDER BY timestamp DESC LIMIT :lim"),
                    params,
                ).mappings().all()
            return [dict(r) for r in rows]
        except Exception as e:
            _log.warning("Cloud get_recent failed: %s", e)

    entries = _load_local()
    if user_email:
        entries = [e for e in entries if e.get("user_email") == user_email]
    if action_type:
        entries = [e for e in entries if e.get("action_type") == action_type]
    return entries[:n]


# ── Context builder ───────────────────────────────────────────────────

def build_context_summary(user_email: Optional[str] = None, n: int = 25) -> str:
    """Build a compact markdown summary of recent history for LLM injection.

    This is prepended to every LLM system prompt so agents always know what
    has been done before and can maintain perfect continuity.
    """
    entries = get_recent(n=n, user_email=user_email)
    if not entries:
        return ""

    lines = [
        "=== 작업 연속성 컨텍스트 (장기 기억) ===",
        "아래 이력을 반드시 참조하여 이전 작업과의 연속성을 유지하세요.",
        "이전에 했던 결정을 번복하지 말고, 항상 이전 작업 위에 더 개선하는 방향으로만 진행하세요.",
        "",
    ]

    for e in entries:
        ts = str(e.get("timestamp", ""))[:16]
        title = e.get("title", "")
        atype = e.get("action_type", "")
        desc = e.get("description", "")
        why = e.get("why_better", "")
        out_summary = e.get("outputs", {})
        if isinstance(out_summary, dict):
            out_summary = out_summary.get("summary", "")

        line = f"[{ts}] ({atype}) {title}"
        if desc:
            line += f" — {desc[:120]}"
        if why:
            line += f" | 개선: {why[:80]}"
        if out_summary:
            line += f" | 결과: {str(out_summary)[:80]}"
        lines.append(line)

    lines.append("=== 컨텍스트 끝 ===")
    return "\n".join(lines)


# ── Factory ───────────────────────────────────────────────────────────

def make_entry(
    title: str,
    description: str = "",
    action_type: str = "general",
    user_email: str = "",
    session_id: str = "",
    what_changed: Optional[Dict] = None,
    why_better: str = "",
    inputs: Optional[Dict] = None,
    outputs: Optional[Dict] = None,
    impact: Optional[Dict] = None,
) -> ChangeLogEntry:
    now = datetime.now()
    return ChangeLogEntry(
        id=now.strftime("%Y%m%d_%H%M%S_%f"),
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
        user_email=user_email,
        session_id=session_id,
        action_type=action_type,
        title=title,
        description=description,
        what_changed=what_changed or {},
        why_better=why_better,
        inputs=inputs or {},
        outputs=outputs or {},
        impact=impact or {},
    )


def log(
    title: str,
    description: str = "",
    action_type: str = "general",
    user_email: str = "",
    session_id: str = "",
    **kwargs,
) -> None:
    """Convenience one-liner: create entry + append in one call."""
    entry = make_entry(
        title=title,
        description=description,
        action_type=action_type,
        user_email=user_email,
        session_id=session_id,
        **kwargs,
    )
    append(entry)
