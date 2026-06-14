"""Evolution gate — baseline vs candidate runner on held-out gold_set.

SELF_EVOLUTION_SPEC §4: every candidate change MUST pass through this gate to be promoted.
No bypass. Auto-promote only for low-risk kinds; high-risk → human approval queue.

Flow:
    1. Build baseline_scores via anchor.run() with current active state
    2. Apply candidate (caller-supplied apply_fn) to a temporary state
    3. Build candidate_scores via anchor.run() with candidate state
    4. Restore baseline (caller-supplied restore_fn)
    5. Decide: Δ ≥ +ε on overall AND no axis dropped > drop_tol → promote
              else → rollback
    6. Record decision + provenance in ledger

LOW_RISK_KINDS auto-promote on win; HIGH_RISK_KINDS go to approval queue (decision="hold").
"""
from __future__ import annotations

from typing import Callable, Dict, Optional

from src.config.logging_config import get_logger
from src.evolution import anchor as _anchor
from src.evolution import ledger as _ledger

_log = get_logger(__name__)


LOW_RISK_KINDS = {"retrieval_config", "memory_rule"}
HIGH_RISK_KINDS = {"persona_perspective", "prompt_version", "safety_rule"}

# Decision thresholds — tuned conservative for medical (per SPEC §11 default)
EPSILON = 0.02           # overall must beat baseline by ≥ +0.02
AXIS_DROP_TOL = 0.05     # no individual axis may drop by more than 0.05


def _axis_drops(baseline: dict, candidate: dict, tol: float = AXIS_DROP_TOL) -> list[str]:
    drops: list[str] = []
    for axis, b_score in (baseline.get("axes") or {}).items():
        if b_score is None:
            continue
        c_score = (candidate.get("axes") or {}).get(axis)
        if c_score is None:
            continue
        if float(b_score) - float(c_score) > tol:
            drops.append(f"{axis}: {b_score} → {c_score}")
    return drops


def run_gate(kind: str, id: str, payload: dict,
                *, apply_fn: Callable[[], None],
                restore_fn: Callable[[], None],
                source: str = "improvement_engine",
                eps: float = EPSILON) -> Dict:
    """Run baseline-vs-candidate gate for one change.

    apply_fn:  caller activates candidate state (e.g. swap persona file)
    restore_fn: caller restores baseline (called regardless of outcome)

    Returns: {decision, delta, baseline, candidate, candidate_event_id}
    """
    cand_id = _ledger.record_candidate(kind, id, payload, source=source)
    if cand_id is None:
        return {"decision": "error", "reason": "ledger record failed"}

    try:
        baseline = _anchor.run()
        try:
            apply_fn()
        except Exception as e:
            _log.warning("gate apply_fn fail: %s", e)
            _ledger.record_gate_result(cand_id, {}, baseline.get("axes") or {},
                                          "rollback", delta=0.0,
                                          notes=f"apply_fn fail: {e}")
            _ledger.rollback(cand_id, reason=f"apply_fn fail: {str(e)[:120]}")
            return {"decision": "rollback", "delta": 0.0,
                     "baseline": baseline, "candidate": None,
                     "candidate_event_id": cand_id}

        candidate = _anchor.run()

        try:
            restore_fn()
        except Exception as e:
            _log.warning("gate restore_fn fail (continuing): %s", e)

        delta = float(candidate.get("overall", 0.0)) - float(baseline.get("overall", 0.0))
        axis_drops = _axis_drops(baseline, candidate)

        if kind in HIGH_RISK_KINDS:
            decision = "hold"
            notes = f"high-risk kind; awaits human approval. Δ={delta:.3f}, drops={axis_drops}"
        elif delta >= eps and not axis_drops:
            decision = "promote"
            notes = f"Δ={delta:.3f} ≥ {eps}, no axis drop"
        else:
            decision = "rollback"
            notes = f"Δ={delta:.3f} < {eps} or axis drops: {axis_drops}"

        _ledger.record_gate_result(cand_id,
                                      candidate.get("axes") or {},
                                      baseline.get("axes") or {},
                                      decision, delta=delta, notes=notes)
        if decision == "promote":
            _ledger.promote(cand_id)
        elif decision == "rollback":
            _ledger.rollback(cand_id, reason=notes)
        # decision == "hold" — no terminal event; sits in approval queue

        return {
            "decision": decision, "delta": round(delta, 4),
            "baseline": baseline, "candidate": candidate,
            "axis_drops": axis_drops,
            "candidate_event_id": cand_id,
        }
    except Exception as e:
        _log.exception("gate run fail")
        _ledger.rollback(cand_id, reason=f"gate exception: {str(e)[:200]}")
        return {"decision": "rollback", "reason": str(e)[:200],
                 "candidate_event_id": cand_id}


__all__ = ["run_gate", "LOW_RISK_KINDS", "HIGH_RISK_KINDS",
            "EPSILON", "AXIS_DROP_TOL"]
