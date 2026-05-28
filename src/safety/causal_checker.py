"""Causal consistency checker — 외부 진단의 'causal consistency / external evidence' 격차.

설계 의도:
  의학 논문 단면연구(cross-sectional)에서 자주 발생하는 **인과 진술 과장**을 자동 검출.
  - "X causes Y" / "X leads to Y" / "X results in Y" 같은 강한 인과 표현이 단면연구에서
    쓰이면 STROBE 권고 위반. consistency_checker는 숫자 모순만 잡으므로 본 모듈이 보완.
  - 약한 인과 (associated with / linked to / may contribute) 인지 강한 인과인지 분류.
  - 발견된 인과 진술 별로 design 일치 여부 + 인용 grounded 여부 보고.

extension hook (옵션):
  · external_evidence_consensus(claim) — PubMed/RAG에서 해당 claim 지지/반박 ref 검색
  · LLM judge (sampling) — 룰로 분류 모호한 문장만 LLM에 묻기

호출:
    from src.safety.causal_checker import check_causal_claims
    rep = check_causal_claims(text, study_design="cross_sectional")
    # rep = {"severity":"warn", "claims":[{"text":..., "strength":"strong",
    #                                       "design_appropriate": False, ...}, ...]}
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── Causal strength vocabulary ──────────────────────────────────────────────

# Strong causal verbs/phrases — observational design에 부적절
_STRONG_CAUSAL = [
    r"\bcauses?\b", r"\bcaused by\b", r"\bcausation\b",
    r"\bleads? to\b", r"\bresult(?:s|ed)? in\b", r"\bresults? from\b",
    r"\bproduces?\b", r"\binduces?\b", r"\btriggers?\b",
    r"\bdetermines?\b", r"\bprevents?\b(?! the development)",
    r"\beliminates?\b", r"\bensures?\b",
    r"\bproves?\b", r"\bdemonstrates? (?:definitively|conclusively)\b",
    r"\bcaus(?:al|ality) (?:relationship|link|effect)\b",
]
_STRONG_RE = re.compile("|".join(_STRONG_CAUSAL), re.IGNORECASE)

# Acceptable hedged language for observational studies
_WEAK_CAUSAL = [
    r"\bassociated with\b", r"\blinked to\b", r"\brelated to\b",
    r"\bcorrelated with\b", r"\bobserved (?:in|among)\b",
    r"\bmay (?:contribute|underlie|explain|mediate|reflect)\b",
    r"\bmight (?:contribute|underlie|explain|mediate|reflect)\b",
    r"\bappears? to (?:be associated|relate)\b",
    r"\bis consistent with\b", r"\baligns? with\b",
    r"\bsuggest(?:s|ive of)?\b",
]
_WEAK_RE = re.compile("|".join(_WEAK_CAUSAL), re.IGNORECASE)

# Design-aware acceptable strength
DESIGN_ALLOWED_STRENGTH = {
    "cross_sectional": ("weak",),
    "case_control":    ("weak",),
    "cohort":          ("weak", "medium"),   # 인과 추정 일부 허용
    "rct":             ("weak", "medium", "strong"),
    "meta_analysis":   ("weak", "medium"),
    "experimental":    ("weak", "medium", "strong"),
    "review":          ("weak",),
}


@dataclass
class CausalClaim:
    text: str
    strength: str        # "strong" | "weak" | "neutral"
    position: int = 0
    design_appropriate: bool = True
    has_citation: bool = False
    suggestion: str = ""


@dataclass
class CausalReport:
    severity: str = "ok"     # ok | warn | fail
    study_design: str = ""
    n_strong: int = 0
    n_weak: int = 0
    claims: List[CausalClaim] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {**asdict(self),
                "claims": [asdict(c) for c in self.claims]}


_CITE_RE = re.compile(r"\[\d+(?:[\s,\-–]\d+)*\]")
_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _sentences(text: str) -> List[str]:
    return [s.strip() for s in _SENT_SPLIT.split(text or "") if 10 < len(s) < 700]


def _classify(sentence: str) -> str:
    """strong / weak / neutral."""
    if _STRONG_RE.search(sentence):
        return "strong"
    if _WEAK_RE.search(sentence):
        return "weak"
    return "neutral"


def check_causal_claims(text: str, *, study_design: str = "cross_sectional",
                         min_severity: str = "warn") -> CausalReport:
    """본문에서 causal claim 추출 + design 적합성 평가.

    Args:
        text: 논문 본문 (Abstract/Discussion 위주)
        study_design: 'cross_sectional'|'cohort'|'rct'|'meta_analysis'|'review'|'case_control'

    Returns: CausalReport
    """
    rep = CausalReport(study_design=study_design)
    if not text:
        return rep
    allowed = DESIGN_ALLOWED_STRENGTH.get(study_design, ("weak",))
    sents = _sentences(text)

    for i, s in enumerate(sents):
        strength = _classify(s)
        if strength == "neutral":
            continue
        has_cite = bool(_CITE_RE.search(s))
        appropriate = strength in allowed
        suggestion = ""
        if not appropriate:
            if strength == "strong" and "weak" in allowed:
                suggestion = (
                    "Replace causal language with association: "
                    "'causes' → 'is associated with', 'leads to' → 'may contribute to'"
                )
            elif strength == "strong" and "medium" in allowed:
                suggestion = (
                    "Soften to medium: 'increases the risk of', 'may predispose to'"
                )
        claim = CausalClaim(text=s, strength=strength, position=i,
                             design_appropriate=appropriate,
                             has_citation=has_cite, suggestion=suggestion)
        rep.claims.append(claim)
        if strength == "strong":
            rep.n_strong += 1
        elif strength == "weak":
            rep.n_weak += 1

    # severity
    n_inappropriate = sum(1 for c in rep.claims if not c.design_appropriate)
    if n_inappropriate >= 3:
        rep.severity = "fail"
        rep.notes.append(
            f"{n_inappropriate} causal claims violate {study_design} STROBE recommendations. "
            "Major revision required."
        )
    elif n_inappropriate >= 1:
        rep.severity = "warn"
        rep.notes.append(
            f"{n_inappropriate} causal claim(s) inappropriate for {study_design} design."
        )

    # ungrounded strong claims (인용 없는 강한 주장)
    ungrounded = [c for c in rep.claims
                   if c.strength == "strong" and not c.has_citation]
    if ungrounded:
        rep.notes.append(
            f"{len(ungrounded)} strong causal claim(s) without citation — add ref or soften."
        )
        if rep.severity == "ok":
            rep.severity = "warn"

    # audit 기록 (severity fail)
    if rep.severity == "fail":
        try:
            from src.safety.audit_trail import record_safety_event
            record_safety_event("causal_claim_violation",
                                 {"design": study_design,
                                  "n_inappropriate": n_inappropriate,
                                  "first": rep.claims[0].text[:200]
                                            if rep.claims else ""})
        except Exception:
            pass

    return rep


# ── External evidence consensus (optional, RAG-backed) ──────────────────────

def external_evidence_consensus(claim_text: str, *, k: int = 5) -> Dict:
    """RAG에서 해당 claim을 지지/반박하는 ref 검색.
    실 LLM 평가는 비싸므로 키워드 매칭 + recall_relevant만 기본 제공."""
    try:
        from src.rag.pipeline import RAGPipeline
        hits = RAGPipeline().search(claim_text, n_results=k) or []
    except Exception as e:
        return {"error": str(e)[:200]}
    if not hits:
        return {"n_supporting": 0, "n_contradicting": 0,
                 "verdict": "no_evidence", "hits": []}
    # 단순 휴리스틱 — 본문에 "no association" / "did not find" 류 키워드면 contradicting
    n_support, n_contra = 0, 0
    classified: List[Dict] = []
    for h in hits[:k]:
        t = (h.get("text") or "").lower()
        contradict_signals = ["no significant", "not associated", "did not find",
                               "no association", "null result", "did not differ"]
        is_contra = any(sig in t for sig in contradict_signals)
        if is_contra:
            n_contra += 1
            label = "contradict"
        else:
            n_support += 1
            label = "support"
        classified.append({
            "text_preview": (h.get("text") or "")[:200],
            "label": label,
            "metadata": h.get("metadata", {}),
        })
    if n_support > n_contra:
        verdict = "mostly_supported"
    elif n_contra > n_support:
        verdict = "mostly_contradicted"
    else:
        verdict = "mixed"
    return {
        "n_supporting": n_support, "n_contradicting": n_contra,
        "verdict": verdict, "hits": classified,
    }
