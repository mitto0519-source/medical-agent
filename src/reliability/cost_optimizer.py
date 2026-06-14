"""Cost Optimizer — critical-path reviewer selection (the ONE net-new reliability layer).

Problem: peer_reviewer.revise_with_critique() currently runs the FULL rubric on every iteration,
even when only the Stat section changed between revisions. This explodes tokens, latency, and cost.

Fix: classify the *change set* between iter_N and iter_N+1, then run only the rubric axes whose
inputs changed. Other axes inherit the previous score.

Per MASTER_UPGRADE_ROADMAP: this MUST land before #2 Provenance / #6 Confidence wiring,
because those increase per-iteration cost. Without critical-path routing, full enable = timeout.

API:
    classify_change(prev_text, new_text, *, stat_changed=False, refs_changed=False) -> ChangeSet
    select_reviewers(change_set) -> list[str]            # rubric axis keys to re-run
    rebuild_score(prev_result, axis_scores) -> dict       # inherit + override

ChangeSet axes:
    "stat"     — numbers / OR / CI / p / table values changed
    "citation" — [n] markers, References list, PMIDs changed
    "language" — non-stat-non-cite text changed (paragraph rewrites, IMRAD prose)
    "figure"   — Figure legends section changed
    "structural" — heading/IMRAD-section structure changed
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── rubric axis ↔ change axis routing table ──────────────────────────────────
# Map MASTER_UPGRADE §3 axes onto peer_reviewer rubric sections.
# peer_reviewer.RUBRIC keys (verified): clarity, methodology, results_analysis, discussion,
#   literature_review, novelty, statistical_rigor, citation_quality, ethics, writing_quality
_AXIS_TO_RUBRIC: Dict[str, List[str]] = {
    "stat":       ["statistical_rigor", "results_analysis", "methodology"],
    "citation":   ["citation_quality", "literature_review"],
    "language":   ["clarity", "writing_quality"],
    "figure":     ["results_analysis"],
    "structural": ["clarity", "discussion", "methodology"],
}

# Patterns that fingerprint each axis
_NUMBER_PAT = re.compile(r"\b(\d+\.\d+|\d{2,})\b")          # numbers / decimals
_CI_PAT = re.compile(r"\b\d+\.\d+\s*[-–~]\s*\d+\.\d+\b")    # CI bounds
_P_PAT = re.compile(r"\bp\s*[<=>]\s*0?\.\d+\b", re.IGNORECASE)
_OR_PAT = re.compile(r"\b(a?OR|HR|RR|aHR|aRR)\b", re.IGNORECASE)
_PMID_PAT = re.compile(r"PMID:?\s*(\d+)")
_NUM_CITE_PAT = re.compile(r"\[(\d+(?:,\s*\d+)*)\]")
_HEADING_PAT = re.compile(r"^#{1,3}\s+\S", re.MULTILINE)
_FIGURE_PAT = re.compile(r"##\s*Figure\s*legends?[\s\S]*", re.IGNORECASE)


@dataclass
class ChangeSet:
    """Summary of what changed between two manuscript revisions."""
    stat: bool = False
    citation: bool = False
    language: bool = False
    figure: bool = False
    structural: bool = False
    details: Dict[str, str] = field(default_factory=dict)

    def axes(self) -> List[str]:
        return [a for a in ("stat", "citation", "language", "figure", "structural")
                 if getattr(self, a)]

    def is_empty(self) -> bool:
        return not any((self.stat, self.citation, self.language, self.figure, self.structural))

    def to_dict(self) -> dict:
        return {"stat": self.stat, "citation": self.citation, "language": self.language,
                 "figure": self.figure, "structural": self.structural, "details": self.details}


def _stat_fingerprint(text: str) -> set:
    """All numbers + CI bounds + p-values + effect-measure tokens → comparable set."""
    if not text:
        return set()
    nums = set(_NUMBER_PAT.findall(text))
    cis = set(_CI_PAT.findall(text))
    ps = set(_P_PAT.findall(text))
    ors = set(_OR_PAT.findall(text))
    return nums | cis | ps | ors


def _citation_fingerprint(text: str) -> set:
    """PMIDs + [n] markers → comparable set."""
    if not text:
        return set()
    pmids = set(_PMID_PAT.findall(text))
    nums = set()
    for grp in _NUM_CITE_PAT.findall(text):
        for n in grp.split(","):
            nums.add(n.strip())
    return pmids | {f"[{n}]" for n in nums}


def _figure_block(text: str) -> str:
    m = _FIGURE_PAT.search(text or "")
    return m.group(0) if m else ""


def _heading_set(text: str) -> set:
    return set(_HEADING_PAT.findall(text or ""))


def _language_residue(text: str) -> str:
    """Strip stat tokens + citations + figures + headings → bare prose."""
    if not text:
        return ""
    out = _NUMBER_PAT.sub("N", text)
    out = _NUM_CITE_PAT.sub("[C]", out)
    out = _PMID_PAT.sub("PMID", out)
    out = _FIGURE_PAT.sub("", out)
    out = _HEADING_PAT.sub("#", out)
    return re.sub(r"\s+", " ", out).strip()


def classify_change(prev_text: str, new_text: str,
                       *, stat_changed: Optional[bool] = None,
                       refs_changed: Optional[bool] = None) -> ChangeSet:
    """Diff two revisions → which axes changed. Caller may pre-set stat/refs flags."""
    cs = ChangeSet()

    if prev_text is None or new_text is None or prev_text == new_text:
        return cs

    if stat_changed is True or _stat_fingerprint(prev_text) != _stat_fingerprint(new_text):
        cs.stat = True
        cs.details["stat"] = "numeric / OR / CI / p / effect-measure tokens differ"

    if refs_changed is True or _citation_fingerprint(prev_text) != _citation_fingerprint(new_text):
        cs.citation = True
        cs.details["citation"] = "PMIDs or [n] markers differ"

    if _figure_block(prev_text) != _figure_block(new_text):
        cs.figure = True
        cs.details["figure"] = "Figure legends block differs"

    prev_heads = _heading_set(prev_text)
    new_heads = _heading_set(new_text)
    if prev_heads != new_heads:
        cs.structural = True
        cs.details["structural"] = (
            f"+{len(new_heads - prev_heads)} / -{len(prev_heads - new_heads)} headings"
        )

    if _language_residue(prev_text) != _language_residue(new_text):
        cs.language = True
        cs.details["language"] = "prose residue (stat-stripped) differs"

    return cs


def select_reviewers(change_set: ChangeSet) -> List[str]:
    """Map ChangeSet → rubric axis keys to re-run. Returns deduplicated ordered list."""
    if change_set.is_empty():
        return []
    rubric_keys: List[str] = []
    seen: set = set()
    for axis in change_set.axes():
        for k in _AXIS_TO_RUBRIC.get(axis, []):
            if k not in seen:
                seen.add(k)
                rubric_keys.append(k)
    return rubric_keys


def rebuild_score(prev_result: Optional[dict], axis_scores: Dict[str, dict]) -> dict:
    """Inherit prev_result.section_scores for un-re-run axes, override with axis_scores.

    prev_result: ReviewResult.to_dict() shape — {section_scores: {key: {score, max_score, ...}}}
    axis_scores: {rubric_key: SectionFeedback.to_dict()}
    """
    base = dict(prev_result or {})
    section = dict(base.get("section_scores") or {})
    section.update(axis_scores)
    total = sum((v.get("score") or 0) for v in section.values())
    max_total = sum((v.get("max_score") or 0) for v in section.values())
    base["section_scores"] = section
    base["total_score"] = total
    base["max_score"] = max_total
    base["pct"] = (total / max_total * 100) if max_total else 0.0
    base["reused_from_prev"] = sorted(set(section.keys()) - set(axis_scores.keys()))
    base["re_evaluated"] = sorted(axis_scores.keys())
    return base


def estimate_token_savings(full_n_axes: int, reused_n_axes: int,
                              *, avg_tokens_per_axis: int = 800) -> dict:
    """Quick report for the dashboard / change_log."""
    saved_axes = max(0, reused_n_axes)
    return {
        "axes_total": full_n_axes,
        "axes_reused": saved_axes,
        "axes_re_evaluated": max(0, full_n_axes - saved_axes),
        "tokens_saved_est": saved_axes * avg_tokens_per_axis,
        "pct_saved": round(100 * saved_axes / full_n_axes, 1) if full_n_axes else 0.0,
    }


__all__ = [
    "ChangeSet", "classify_change", "select_reviewers", "rebuild_score",
    "estimate_token_savings",
]
