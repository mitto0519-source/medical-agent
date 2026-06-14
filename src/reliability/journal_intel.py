"""Journal Intelligence — submission-rule compliance checks.

MASTER_UPGRADE §3 #7: journal_targeting.py + cover_letter + journal_docx already exist.
We add: compliance checks (word counts vs limit, ref count vs cap, fig/tbl count) and a one-shot
report the writer/reviewer can read before submission.

API:
    compliance_report(journal_slug, manuscript_text, refs, figures, tables) -> dict
    as_block(report) -> str           # system_prompt-ready
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


_WORD_RE = re.compile(r"\b\w+\b")


def _word_count(text: str) -> int:
    return len(_WORD_RE.findall(text or ""))


def _extract_abstract(manuscript_text: str) -> str:
    """Pull the Abstract section (## Abstract → next ## heading)."""
    if not manuscript_text:
        return ""
    m = re.search(r"##\s*Abstract\s*\n([\s\S]*?)(?=\n##\s|\Z)", manuscript_text,
                   re.IGNORECASE)
    return (m.group(1).strip() if m else "")


def compliance_report(journal_slug: str, manuscript_text: str,
                         *, refs: Optional[List] = None,
                         n_figures: Optional[int] = None,
                         n_tables: Optional[int] = None) -> Dict:
    """Check manuscript vs journal targeting submission rules. Returns issue list + pass/fail."""
    try:
        from src.export.journal_targeting import get_journal_targeting
    except Exception as e:
        return {"ok": False, "issues": [f"journal_targeting import fail: {e}"]}

    jt = get_journal_targeting(journal_slug)
    if jt is None:
        return {"ok": False, "issues": [f"unknown journal slug: {journal_slug}"]}

    issues: List[str] = []

    # Total words
    total_w = _word_count(manuscript_text)
    if jt.word_limit_total and total_w > jt.word_limit_total:
        issues.append(
            f"Manuscript over word limit: {total_w} > {jt.word_limit_total} "
            f"({total_w - jt.word_limit_total} over)"
        )

    # Abstract words
    abstract = _extract_abstract(manuscript_text)
    abs_w = _word_count(abstract)
    if jt.word_limit_abstract and abs_w > jt.word_limit_abstract:
        issues.append(
            f"Abstract over word limit: {abs_w} > {jt.word_limit_abstract}"
        )

    # References cap
    n_refs = len(refs or [])
    if jt.reference_max and n_refs > jt.reference_max:
        issues.append(f"References exceed cap: {n_refs} > {jt.reference_max}")

    # Figures / tables
    if n_figures is not None and jt.figure_max is not None and n_figures > jt.figure_max:
        issues.append(f"Figures exceed cap: {n_figures} > {jt.figure_max}")
    if n_tables is not None and jt.table_max is not None and n_tables > jt.table_max:
        issues.append(f"Tables exceed cap: {n_tables} > {jt.table_max}")

    # Structured abstract requirement
    if jt.structured_abstract:
        required = ["Background", "Methods", "Results", "Conclusion"]
        missing = [k for k in required
                    if not re.search(rf"\*\*{k}", abstract, re.IGNORECASE)]
        if missing:
            issues.append(f"Structured abstract missing sections: {','.join(missing)}")

    # STROBE
    if jt.requires_strobe and "STROBE" not in (manuscript_text or "").upper():
        issues.append("STROBE compliance statement not detected (observational design required)")

    return {
        "ok": not issues,
        "journal": {"slug": jt.slug, "full_name": jt.full_name},
        "measured": {"manuscript_words": total_w, "abstract_words": abs_w,
                       "n_refs": n_refs, "n_figures": n_figures, "n_tables": n_tables},
        "limits": {"manuscript": jt.word_limit_total,
                     "abstract": jt.word_limit_abstract,
                     "references": jt.reference_max,
                     "figures": jt.figure_max, "tables": jt.table_max},
        "issues": issues,
    }


def as_block(report: Dict) -> str:
    """Render report for chat or system_prompt overlay."""
    if not isinstance(report, dict):
        return ""
    j = report.get("journal") or {}
    head = f"## Journal compliance — {j.get('full_name','?')} ({j.get('slug','?')})"
    if report.get("ok"):
        return head + "\n✓ All submission rules satisfied."
    lines = [head]
    for i in report.get("issues", [])[:10]:
        lines.append(f"- {i}")
    return "\n".join(lines)


__all__ = ["compliance_report", "as_block"]
