"""External anchor scorer — gold_set.json → per-axis score → overall.

SELF_EVOLUTION_SPEC §2 / §9: gold_set is HELD-OUT. This module is the ONLY caller of
gold_set.json — never inject the labels into prompts or train on them.

Six axes (per SPEC §2):
    retrieval              — nDCG@k / recall@k vs labelled relevant_pmids
    citation_faithfulness  — claim_evidence NLI agreement with gold label
    stat_correctness       — survey-weighted result within tolerance + survey_weight=true
    style_match            — StyleProfiler distance to labelled target
    structure              — manuscript required sections present
    functional             — E2E journey J1..J11 green ratio (computed elsewhere, injected)

If a gold set axis has zero labelled examples → score is `None` (NOT zero — caller
distinguishes "untested" from "failed"). overall = weighted geomean over non-None axes.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_GOLD_PATH = Path("eval/gold_set.json")

# Per-axis weights for overall aggregation. Stat + citation get extra weight (medical safety).
_DEFAULT_WEIGHTS = {
    "retrieval": 0.15,
    "citation_faithfulness": 0.25,
    "stat_correctness": 0.25,
    "style_match": 0.10,
    "structure": 0.10,
    "functional": 0.15,
}


def _load_gold() -> dict:
    if not _GOLD_PATH.exists():
        _log.warning("gold_set missing: %s", _GOLD_PATH)
        return {}
    try:
        return json.loads(_GOLD_PATH.read_text(encoding="utf-8"))
    except Exception as e:
        _log.warning("gold_set load fail: %s", e)
        return {}


# ── retrieval axis ───────────────────────────────────────────────────────────

def _ndcg_at_k(retrieved_pmids: List[str], relevant_pmids: List[str], k: int = 5) -> float:
    if not retrieved_pmids or not relevant_pmids:
        return 0.0
    rel = set(str(p) for p in relevant_pmids)
    dcg = 0.0
    for i, pmid in enumerate(retrieved_pmids[:k], start=1):
        if str(pmid) in rel:
            dcg += 1.0 / math.log2(i + 1)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, min(k, len(rel)) + 1))
    return dcg / idcg if idcg else 0.0


def score_retrieval(gold: dict, *, k: int = 5) -> Optional[float]:
    items = []
    for q in (gold.get("queries") or []):
        rel = q.get("expected_pmids") or []
        if not rel:
            continue
        try:
            from src.service.rag import retrieve
            hits = retrieve(q.get("query", ""), top_k=k) or []
            retrieved = [(h.get("metadata") or {}).get("pmid", "") for h in hits]
            items.append(_ndcg_at_k(retrieved, rel, k=k))
        except Exception as e:
            _log.debug("retrieval scoring item fail: %s", e)
    if not items:
        return None
    return round(sum(items) / len(items), 3)


# ── citation faithfulness axis ───────────────────────────────────────────────

def score_citation_faithfulness(gold: dict) -> Optional[float]:
    pairs = gold.get("claim_evidence_pairs") or []
    labelled = [p for p in pairs
                if (p.get("label") or "").lower() in {"supports", "contradicts", "neutral"}]
    if not labelled:
        return None
    try:
        from src.safety.claim_evidence_nli import classify
    except Exception:
        return None
    correct = 0
    for p in labelled:
        # If no evidence text, treat the claim itself as the only signal — degenerates to lexical
        evidence = p.get("evidence_text", "") or " ".join(p.get("evidence_pmids", []))
        out = classify(p.get("claim", ""), evidence)
        if out.get("label") == p.get("label"):
            correct += 1
    return round(correct / len(labelled), 3)


# ── stat correctness axis ────────────────────────────────────────────────────

def score_stat_correctness(gold: dict, *, tol: float = 0.05) -> Optional[float]:
    """Run each survey_design_test_case → check (a) survey-weight engine used (b) within tolerance."""
    cases = gold.get("survey_design_test_cases") or []
    if not cases:
        return None
    try:
        from src.analysis import survey_weighted as svy
    except Exception:
        return None
    passes = 0
    for c in cases:
        spec = c.get("spec") or {}
        expected = c.get("expected") or {}
        if not expected:  # unlabelled — skip
            continue
        try:
            # Load df (caller would normally provide; we skip if dataset missing)
            df = None
            from src.service.data import load_dataset
            df, meta = load_dataset(c.get("dataset", "KYRBS"), year=c.get("year"))
            if df is None:
                continue
            res = svy.fit_logit_svy(df, spec.get("outcome", ""), spec.get("exposure", ""),
                                       spec.get("covariates"),
                                       strata=spec.get("strata", "STRATA"),
                                       cluster=spec.get("cluster", "CLUSTER"),
                                       weight=spec.get("weight", "W"))
            if not res.get("ok"):
                continue
            engine = res.get("engine", "")
            if c.get("must_use_survey_weight", True) and "APPROXIMATE" in engine:
                continue  # survey weights skipped — fail
            aOR = (res.get("or") or {}).get(spec.get("exposure", "")) or 0.0
            expected_aOR = float(expected.get("aOR") or 0.0)
            if expected_aOR and abs(aOR - expected_aOR) / expected_aOR <= tol:
                passes += 1
        except Exception as e:
            _log.debug("stat scoring case fail: %s", e)
    return round(passes / len(cases), 3) if cases else None


# ── style match axis ─────────────────────────────────────────────────────────

def score_style_match(gold: dict, *, owner_email: str = "") -> Optional[float]:
    targets = gold.get("style_targets") or []
    if not targets:
        return None
    try:
        from src.agent.style_profiler import get_profile
    except Exception:
        return None
    matches = []
    for t in targets:
        prof = get_profile(owner_email or t.get("owner_email_hash", ""))
        if prof is None:
            continue
        avg_lo, avg_hi = t.get("expected_avg_sent_len", [0, 999])
        sl = getattr(prof, "avg_sent_len", 0) or 0
        in_range = avg_lo <= sl <= avg_hi
        matches.append(1.0 if in_range else 0.0)
    if not matches:
        return None
    return round(sum(matches) / len(matches), 3)


# ── structure axis ──────────────────────────────────────────────────────────

def score_structure(gold: dict, *, manuscript_text: str = "") -> Optional[float]:
    targets = gold.get("manuscript_targets") or []
    if not targets or not manuscript_text:
        return None
    scores = []
    for t in targets:
        req = t.get("must_have_sections") or []
        if not req:
            continue
        present = sum(1 for sec in req
                       if sec.lower() in manuscript_text.lower())
        scores.append(present / len(req))
    return round(sum(scores) / len(scores), 3) if scores else None


# ── functional axis (E2E injection) ─────────────────────────────────────────

def score_functional(*, journey_results: Optional[Dict[str, bool]] = None) -> Optional[float]:
    """ui_eval / E2E pilot result injected externally — keys are J1..J11, values bool."""
    if not journey_results:
        return None
    if not journey_results:
        return None
    green = sum(1 for v in journey_results.values() if v)
    return round(green / len(journey_results), 3)


# ── overall aggregator ─────────────────────────────────────────────────────

def run(*, owner_email: str = "",
          manuscript_text: str = "",
          journey_results: Optional[Dict[str, bool]] = None,
          weights: Optional[Dict[str, float]] = None) -> Dict:
    """Run all six axes against the held-out gold set. Returns axis scores + overall."""
    gold = _load_gold()
    w = dict(_DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    axes = {
        "retrieval": score_retrieval(gold),
        "citation_faithfulness": score_citation_faithfulness(gold),
        "stat_correctness": score_stat_correctness(gold),
        "style_match": score_style_match(gold, owner_email=owner_email),
        "structure": score_structure(gold, manuscript_text=manuscript_text),
        "functional": score_functional(journey_results=journey_results),
    }
    # Weighted geomean over non-None axes
    eps = 1e-6
    log_sum, w_sum = 0.0, 0.0
    counted = 0
    for k, v in axes.items():
        if v is None:
            continue
        wk = w.get(k, 0.0)
        log_sum += wk * math.log(max(float(v), eps))
        w_sum += wk
        counted += 1
    overall = math.exp(log_sum / w_sum) if w_sum else 0.0
    return {
        "version": gold.get("version", "?"),
        "axes": axes,
        "axes_evaluated": counted,
        "axes_total": len(axes),
        "overall": round(overall, 3),
        "held_out": True,
        "weights": w,
    }


__all__ = ["run", "score_retrieval", "score_citation_faithfulness",
            "score_stat_correctness", "score_style_match",
            "score_structure", "score_functional"]
