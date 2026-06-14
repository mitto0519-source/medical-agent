"""Failure Knowledge Base — structured failure pattern store on procedural memory.

MASTER_UPGRADE §3 #5: FAILURE_PATTERNS.md + self_auditor + memory.router already exist as primitives.
This module gives them a structured shape:

    {failure_type, variables[], resolution, evidence, recurrence_count, last_seen}

It also exposes a query API so the planner can inject "known-failure avoidance" hints into
the prompt: e.g. "if BMI + WaistCircum together → multicollinearity, remove BMI".

API:
    record_failure(failure_type, variables, resolution, *, evidence="", project_id=None) -> id
    query_for_context(variables, *, top_k=5) -> list[FailureRule]
    list_all(*, limit=50) -> list[FailureRule]
    as_avoid_block(rules) -> str   # system_prompt-ready text
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)

_FAILURE_TYPES = {
    "multicollinearity", "small_sample", "missing_data", "convergence_failure",
    "model_misspecification", "outcome_imbalance", "selection_bias",
    "confounder_omission", "weight_misuse", "design_mismatch",
    "citation_hallucination", "stat_assumption_violated", "imrad_incomplete",
}


@dataclass
class FailureRule:
    failure_type: str
    variables: List[str] = field(default_factory=list)
    resolution: str = ""
    evidence: str = ""
    recurrence_count: int = 1
    last_seen: float = field(default_factory=time.time)
    project_id: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


def record_failure(failure_type: str, variables: List[str], resolution: str,
                      *, evidence: str = "",
                      project_id: Optional[str] = None) -> Optional[int]:
    """Append a structured failure record to events.db + procedural memory."""
    ftype = (failure_type or "").lower().strip()
    if ftype not in _FAILURE_TYPES:
        _log.warning("unknown failure_type=%s (recording anyway)", ftype)

    rule = FailureRule(
        failure_type=ftype,
        variables=[str(v) for v in (variables or [])],
        resolution=resolution[:600],
        evidence=evidence[:600],
        project_id=project_id,
    )

    # 1) events.db append (audit)
    eid: Optional[int] = None
    try:
        eid = _events.append(
            type="failure_recorded",
            payload=rule.to_dict(),
            task_id=project_id,
            actor="failure_kb",
        )
    except Exception as e:
        _log.warning("failure_kb events.append fail: %s", e)

    # 2) procedural memory write (router) — so future prompts can recall
    try:
        from src.memory.router import write as _mem_write
        _mem_write(
            f"[FAILURE] type={ftype} vars={','.join(rule.variables)[:200]} → {resolution[:200]}",
            type="procedural", source="failure_kb",
            extra_meta={"failure_type": ftype, "variables": rule.variables,
                          "project_id": project_id},
        )
    except Exception as e:
        _log.debug("failure_kb procedural write fail: %s", e)

    return eid


def list_all(*, limit: int = 50) -> List[FailureRule]:
    """Recent failure rules (latest first)."""
    try:
        items = _events.find(type="failure_recorded", limit=limit * 2)
    except Exception as e:
        _log.warning("failure_kb find fail: %s", e)
        return []
    out: List[FailureRule] = []
    for ev in items:
        pl = ev.get("payload") or {}
        try:
            out.append(FailureRule(
                failure_type=pl.get("failure_type", ""),
                variables=list(pl.get("variables", [])),
                resolution=pl.get("resolution", ""),
                evidence=pl.get("evidence", ""),
                recurrence_count=int(pl.get("recurrence_count", 1)),
                last_seen=float(pl.get("last_seen") or ev.get("ts") or 0),
                project_id=pl.get("project_id"),
            ))
        except Exception as e:
            _log.debug("failure_kb parse fail: %s", e)
    return out[:limit]


def query_for_context(variables: List[str], *, top_k: int = 5) -> List[FailureRule]:
    """Rules whose variable set overlaps with `variables`. Sorted by overlap size."""
    if not variables:
        return []
    vs = set(str(v).lower() for v in variables)
    scored: List[tuple[int, FailureRule]] = []
    for rule in list_all(limit=500):
        overlap = len(vs & set(str(v).lower() for v in rule.variables))
        if overlap:
            scored.append((overlap, rule))
    scored.sort(key=lambda x: (-x[0], -x[1].last_seen))
    return [r for _, r in scored[:top_k]]


def as_avoid_block(rules: List[FailureRule]) -> str:
    """Format rules as a system_prompt-ready 'known failures to avoid' block."""
    if not rules:
        return ""
    lines = ["## Known failure patterns to AVOID (from prior runs)"]
    for i, r in enumerate(rules, 1):
        vs = ", ".join(r.variables[:4])
        lines.append(f"{i}. [{r.failure_type}] vars={vs} → {r.resolution[:160]}")
    lines.append("→ Do not repeat these failures. Pre-empt the resolution in this run.")
    return "\n".join(lines)


__all__ = ["FailureRule", "record_failure", "list_all",
            "query_for_context", "as_avoid_block"]
