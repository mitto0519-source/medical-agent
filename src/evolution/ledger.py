"""Evolution ledger — append-only record of candidate change attempts + gate outcomes.

SELF_EVOLUTION_SPEC §3 / §8: events.db is already append-only, so we wrap it. Every
candidate (persona perspective / prompt version / retrieval config tweak) gets:

    record_candidate → record_gate_result → promote OR rollback (terminal)

Each transition stamps a provenance fingerprint (git_sha, model, gold_set version) so
post-hoc analysis can answer "why did v17 get rolled back when v16 was kept?"

API:
    record_candidate(kind, id, payload, *, source="improvement_engine") -> int
    record_gate_result(candidate_event_id, scores, baseline_scores, decision, delta) -> int
    promote(candidate_event_id, *, actor=None) -> int   # marks status=active
    rollback(candidate_event_id, *, reason, actor=None) -> int  # marks status=retired
    history_for(kind, id, limit=20) -> list[dict]
    open_candidates(*, kind=None) -> list[dict]    # status=candidate (awaiting gate)
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events
from src.runtime import provenance as _prov

_log = get_logger(__name__)

_CHANGE_KINDS = {"persona_perspective", "prompt_version", "retrieval_config",
                  "memory_rule", "tool_config", "safety_rule"}


def record_candidate(kind: str, id: str, payload: dict,
                        *, source: str = "improvement_engine",
                        actor: Optional[str] = None) -> Optional[int]:
    """Register a new candidate change.

    Returns event_id (the candidate's primary key in the ledger).
    """
    if kind not in _CHANGE_KINDS:
        _log.warning("ledger: unknown change kind '%s' (recording anyway)", kind)
    fp = _prov.build_fingerprint(
        scope="evolution_candidate",
        extra={"kind": kind, "id": id, "source": source},
    )
    body = {
        "kind": kind, "id": id, "status": "candidate",
        "payload": payload, "fingerprint": fp,
        "source": source, "ts": time.time(),
    }
    try:
        return _events.append(
            type="evolution_candidate",
            payload=body, actor=actor or source,
        )
    except Exception as e:
        _log.warning("ledger.record_candidate fail: %s", e)
        return None


def record_gate_result(candidate_event_id: int, scores: Dict[str, float],
                          baseline_scores: Dict[str, float], decision: str,
                          *, delta: Optional[float] = None,
                          notes: str = "") -> Optional[int]:
    """Record the outcome of a gate run.

    decision ∈ {"promote", "rollback", "hold"}  (hold = needs human review)
    """
    if decision not in {"promote", "rollback", "hold"}:
        decision = "hold"
    fp = _prov.build_fingerprint(
        scope="evolution_gate",
        extra={"candidate_id": candidate_event_id,
                "decision": decision, "delta": delta},
    )
    body = {
        "candidate_event_id": candidate_event_id,
        "decision": decision, "delta": delta,
        "scores_candidate": scores, "scores_baseline": baseline_scores,
        "notes": notes[:600], "fingerprint": fp,
        "ts": time.time(),
    }
    try:
        return _events.append(
            type="evolution_gate_result",
            payload=body, parent_event_id=candidate_event_id,
            actor="evolution_gate",
        )
    except Exception as e:
        _log.warning("ledger.record_gate_result fail: %s", e)
        return None


def promote(candidate_event_id: int, *, actor: Optional[str] = None) -> Optional[int]:
    """Mark candidate as active. Terminal — no further transitions."""
    return _events.append(
        type="evolution_promote",
        payload={"candidate_event_id": candidate_event_id, "ts": time.time()},
        parent_event_id=candidate_event_id,
        actor=actor or "evolution_gate",
    )


def rollback(candidate_event_id: int, *, reason: str = "",
                actor: Optional[str] = None) -> Optional[int]:
    """Mark candidate as retired. Terminal."""
    return _events.append(
        type="evolution_rollback",
        payload={"candidate_event_id": candidate_event_id,
                  "reason": reason[:300], "ts": time.time()},
        parent_event_id=candidate_event_id,
        actor=actor or "evolution_gate",
    )


def history_for(kind: str, id: str, *, limit: int = 20) -> List[Dict]:
    """All ledger events for one (kind, id), newest first."""
    out: List[Dict] = []
    try:
        items = _events.find(type="evolution_candidate", limit=limit * 4)
    except Exception as e:
        _log.warning("ledger.history_for find fail: %s", e)
        return []
    for ev in items:
        pl = ev.get("payload") or {}
        if pl.get("kind") == kind and pl.get("id") == id:
            out.append({"event_id": ev.get("id"), **pl})
            if len(out) >= limit:
                break
    return out


def open_candidates(*, kind: Optional[str] = None,
                       limit: int = 50) -> List[Dict]:
    """Candidates with no terminal (promote/rollback) event yet."""
    try:
        cands = _events.find(type="evolution_candidate", limit=limit * 4)
        promoted = {(ev.get("payload") or {}).get("candidate_event_id")
                    for ev in _events.find(type="evolution_promote",
                                              limit=limit * 4)}
        retired = {(ev.get("payload") or {}).get("candidate_event_id")
                   for ev in _events.find(type="evolution_rollback",
                                             limit=limit * 4)}
    except Exception as e:
        _log.warning("ledger.open_candidates fail: %s", e)
        return []
    out: List[Dict] = []
    for ev in cands:
        eid = ev.get("id")
        if eid in promoted or eid in retired:
            continue
        pl = ev.get("payload") or {}
        if kind and pl.get("kind") != kind:
            continue
        out.append({"event_id": eid, **pl})
        if len(out) >= limit:
            break
    return out


__all__ = ["record_candidate", "record_gate_result",
            "promote", "rollback",
            "history_for", "open_candidates"]
