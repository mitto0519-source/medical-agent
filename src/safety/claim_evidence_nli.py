"""Claim-Evidence NLI stub — does the cited paper actually support this claim?

★ Why this exists (BEYOND-SPEC #3): PMID realism checks catch fake IDs but not
"real PMID, wrong paper for this claim". Real entailment needs an NLI model. This stub
provides a 3-tier fallback so the pipeline never breaks:

    Tier 1: sentence-transformers cross-encoder NLI (microsoft/deberta-v3-large-mnli)
            — pip install sentence-transformers; gold-quality but slow + heavy.
    Tier 2: LLM-as-judge via get_llm_client(task="qa") — moderate cost, no model download.
    Tier 3: lexical overlap heuristic (Jaccard on stopword-filtered tokens) — always works.

API:
    classify(claim, evidence_text) -> {"label", "score", "engine"}
        label ∈ {"supports","contradicts","neutral"}; score ∈ [0,1]
    batch_classify(pairs) -> list[dict]
"""
from __future__ import annotations

import re
from typing import Dict, Iterable, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


_NLI_MODEL = {"name": "cross-encoder/nli-deberta-v3-base", "model": None, "fail": False}
_LLM_AVAILABLE: Optional[bool] = None
_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "and", "or", "with", "for", "by", "to",
    "is", "are", "was", "were", "be", "been", "being", "this", "that", "these",
    "those", "we", "they", "it", "as", "at", "from", "but", "not", "no",
}


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z][A-Za-z\-]+", text or "")
             if t.lower() not in _STOPWORDS and len(t) > 2]


def _lexical_score(claim: str, evidence: str) -> Dict:
    """Tier-3: token Jaccard + simple negation flip detection."""
    c, e = set(_tokens(claim)), set(_tokens(evidence))
    if not c or not e:
        return {"label": "neutral", "score": 0.0, "engine": "lexical"}
    jacc = len(c & e) / len(c | e)
    neg_c = bool(re.search(r"\b(no|not|never|without|reduce[sd]?|decrease[sd]?)\b",
                              claim, re.IGNORECASE))
    neg_e = bool(re.search(r"\b(no|not|never|without|reduce[sd]?|decrease[sd]?)\b",
                              evidence, re.IGNORECASE))
    # If negation polarity differs and overlap is meaningful → contradict
    if jacc >= 0.15 and neg_c != neg_e:
        return {"label": "contradicts", "score": round(jacc, 3), "engine": "lexical"}
    if jacc >= 0.25:
        return {"label": "supports", "score": round(jacc, 3), "engine": "lexical"}
    return {"label": "neutral", "score": round(jacc, 3), "engine": "lexical"}


def _try_nli_model(claim: str, evidence: str) -> Optional[Dict]:
    """Tier-1: cross-encoder NLI. Returns None if model unavailable."""
    if _NLI_MODEL["fail"]:
        return None
    if _NLI_MODEL["model"] is None:
        try:
            from sentence_transformers import CrossEncoder
            _NLI_MODEL["model"] = CrossEncoder(_NLI_MODEL["name"])
        except Exception as e:
            _log.debug("NLI cross-encoder unavailable: %s", e)
            _NLI_MODEL["fail"] = True
            return None
    try:
        scores = _NLI_MODEL["model"].predict([(evidence, claim)])
        # nli-deberta-v3-base label order: [contradiction, entailment, neutral]
        s = scores[0] if hasattr(scores, "__iter__") else scores
        contrad, entail, neutral = float(s[0]), float(s[1]), float(s[2])
        if entail > max(contrad, neutral):
            return {"label": "supports", "score": round(entail, 3), "engine": "deberta-v3-mnli"}
        if contrad > max(entail, neutral):
            return {"label": "contradicts", "score": round(contrad, 3), "engine": "deberta-v3-mnli"}
        return {"label": "neutral", "score": round(neutral, 3), "engine": "deberta-v3-mnli"}
    except Exception as e:
        _log.warning("NLI predict fail: %s", e)
        return None


def _try_llm_judge(claim: str, evidence: str) -> Optional[Dict]:
    """Tier-2: LLM-as-judge. Returns None on failure."""
    global _LLM_AVAILABLE
    if _LLM_AVAILABLE is False:
        return None
    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="qa")
        prompt = (
            f"CLAIM: {claim[:600]}\n\nEVIDENCE: {evidence[:1200]}\n\n"
            "Does the EVIDENCE support, contradict, or neither (neutral) the CLAIM? "
            "Reply with exactly one word: supports | contradicts | neutral"
        )
        out = (client.generate(prompt, system_prompt="You judge NLI entailment.",
                                  max_tokens=8) or "").strip().lower()
        if "support" in out:
            return {"label": "supports", "score": 0.85, "engine": "llm_judge"}
        if "contradict" in out:
            return {"label": "contradicts", "score": 0.80, "engine": "llm_judge"}
        if "neutral" in out:
            return {"label": "neutral", "score": 0.70, "engine": "llm_judge"}
        _LLM_AVAILABLE = True
        return {"label": "neutral", "score": 0.5, "engine": "llm_judge_unparsed"}
    except Exception as e:
        _log.debug("LLM judge unavailable: %s", e)
        _LLM_AVAILABLE = False
        return None


def classify(claim: str, evidence: str, *, prefer: str = "auto") -> Dict:
    """Classify claim-vs-evidence entailment with graceful fallback.

    prefer: "nli" | "llm" | "lexical" | "auto" (default — try in tier order).
    """
    if not claim or not evidence:
        return {"label": "neutral", "score": 0.0, "engine": "empty"}
    if prefer == "lexical":
        return _lexical_score(claim, evidence)
    if prefer in ("nli", "auto"):
        nli = _try_nli_model(claim, evidence)
        if nli is not None:
            return nli
    if prefer in ("llm", "auto"):
        judge = _try_llm_judge(claim, evidence)
        if judge is not None:
            return judge
    return _lexical_score(claim, evidence)


def batch_classify(pairs: Iterable[Dict]) -> List[Dict]:
    """pairs: [{"claim": "...", "evidence": "..."} ...]"""
    return [classify(p.get("claim", ""), p.get("evidence", "")) for p in pairs]


__all__ = ["classify", "batch_classify"]
