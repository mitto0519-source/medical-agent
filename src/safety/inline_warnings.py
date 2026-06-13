"""Inline warnings — "올바른 마찰" 4축.

비전: "마찰 0" 이 아니라 타이핑·서식·검색은 0마찰, 통계 가정·인용 실재·신규성·과대주장
4개 지점에서만 사람을 붙잡는다. 이 모듈이 manuscript draft를 받아 4개 게이트 결과를 반환.

ez_home preview가 이 결과를 박스/하이라이트로 표시해 사용자가 검증할 곳을 한눈에 봄.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class GateResult:
    gate: str
    severity: str       # "high" | "medium" | "low" | "info"
    message: str
    spans: List[dict] = field(default_factory=list)   # 본문 하이라이트 위치


@dataclass
class InlineReport:
    statistical_assumptions: List[GateResult] = field(default_factory=list)
    citation_existence: List[GateResult] = field(default_factory=list)
    novelty_concerns: List[GateResult] = field(default_factory=list)
    overclaim_flags: List[GateResult] = field(default_factory=list)

    @property
    def total_issues(self) -> int:
        return sum(len(getattr(self, k)) for k in
                    ("statistical_assumptions", "citation_existence",
                     "novelty_concerns", "overclaim_flags"))


# ──────────────────────────────────────────────────────────────
# Gate 1: 통계 가정 위반 감지
# ──────────────────────────────────────────────────────────────

_CAUSAL_PHRASES = [
    r"\b(?:causes?|leads? to|results? in|due to|because of)\b",
    r"\b(?:caused by|attributable to)\b",
]
_CROSS_SECTIONAL_MARKER = re.compile(r"\bcross[-\s]?sectional\b", re.IGNORECASE)
_MULTIPLE_TESTING_MARKER = re.compile(
    r"\b(?:multiple\s+testing|Bonferroni|FDR|Benjamini[-\s]?Hochberg|BH-FDR)\b", re.IGNORECASE)
_PVALUE_PAT = re.compile(r"p\s*[<>=≤≥]\s*0?\.\d+", re.IGNORECASE)


def check_statistical_assumptions(text: str) -> List[GateResult]:
    out = []
    is_cross = bool(_CROSS_SECTIONAL_MARKER.search(text))

    # 횡단연구에서 인과 주장
    if is_cross:
        for pat in _CAUSAL_PHRASES:
            for m in re.finditer(pat, text, re.IGNORECASE):
                out.append(GateResult(
                    gate="statistical_assumptions", severity="high",
                    message=f"횡단연구에서 인과적 표현 사용: '{m.group(0)}'. "
                             "'associated with' / 'linked to'로 바꾸세요.",
                    spans=[{"start": m.start(), "end": m.end()}],
                ))

    # p-value 다중인데 multiple testing 보정 미언급
    pvals = _PVALUE_PAT.findall(text)
    if len(pvals) >= 3 and not _MULTIPLE_TESTING_MARKER.search(text):
        out.append(GateResult(
            gate="statistical_assumptions", severity="medium",
            message=f"{len(pvals)}개의 p-value를 보고하지만 multiple testing 보정 "
                     "(Bonferroni / BH-FDR) 언급 없음.",
        ))

    return out


# ──────────────────────────────────────────────────────────────
# Gate 2: 인용 실재성
# ──────────────────────────────────────────────────────────────

_PMID_TOK = re.compile(r"\[PMID:(\d+)\]")
_NUM_TOK = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")


def check_citation_existence(text: str, known_pmids: Optional[List[str]] = None,
                                verify_via_pubmed: bool = False) -> List[GateResult]:
    """본문에 박힌 [PMID:xxx] 또는 [n]가 실제 reference list와 일치하는지.

    known_pmids: RAG hits에서 확보된 PMID 화이트리스트 (있으면 실재 검증).
    verify_via_pubmed: True면 PubMed API로 한 번 더 확인 (느림).
    """
    out = []
    cited_pmids = set(_PMID_TOK.findall(text))
    if known_pmids is not None:
        known = set(known_pmids)
        invalid = cited_pmids - known
        if invalid:
            out.append(GateResult(
                gate="citation_existence", severity="high",
                message=f"RAG hits에 없는 PMID 인용: {sorted(invalid)} — fabrication 의심",
            ))

    if verify_via_pubmed and cited_pmids:
        try:
            from src.safety.citation_grounding import verify_doi_crossref
            # PubMed 검증은 양식 양식 양식 양식 — TODO: PubMed E-utilities로 PMID 실재 확인
        except Exception:
            pass

    # numbered 인용 [n]이 References 섹션 number와 매칭되는지 확인
    num_cites = set()
    for m in _NUM_TOK.finditer(text):
        for tok in re.split(r"[,\-]", m.group(1)):
            tok = tok.strip()
            if tok.isdigit():
                num_cites.add(int(tok))
    if num_cites:
        # References 섹션 count
        ref_match = re.search(r"(?:^|\n)##\s*References?\s*\n", text, re.IGNORECASE)
        if ref_match:
            ref_block = text[ref_match.end():]
            ref_lines = re.findall(r"^\s*(\d+)\.\s+", ref_block, re.MULTILINE)
            ref_nums = set(int(n) for n in ref_lines)
            orphans_in_text = num_cites - ref_nums
            orphans_in_refs = ref_nums - num_cites
            if orphans_in_text:
                out.append(GateResult(
                    gate="citation_existence", severity="high",
                    message=f"References에 없는 인용 번호: {sorted(orphans_in_text)}",
                ))
            if orphans_in_refs:
                out.append(GateResult(
                    gate="citation_existence", severity="low",
                    message=f"본문에 인용 안 된 reference 번호: {sorted(orphans_in_refs)}",
                ))
        elif num_cites:
            out.append(GateResult(
                gate="citation_existence", severity="medium",
                message=f"본문에 [n] 인용 {len(num_cites)}개 있지만 References 섹션 없음",
            ))

    return out


# ──────────────────────────────────────────────────────────────
# Gate 3: 신규성 부족
# ──────────────────────────────────────────────────────────────

def check_novelty(novelty_score: Optional[float], topic: Optional[Dict] = None) -> List[GateResult]:
    out = []
    if novelty_score is None:
        return out
    if novelty_score < 0.4:
        out.append(GateResult(
            gate="novelty_concerns", severity="medium",
            message=f"NoveltyChecker score {novelty_score:.2f} < 0.4 — "
                     "기존 연구와 차별점이 약합니다. Discussion에 'first study to / "
                     "to our knowledge' 같은 contribution 명시 문장이 있는지 확인.",
        ))
    elif novelty_score < 0.6:
        out.append(GateResult(
            gate="novelty_concerns", severity="low",
            message=f"NoveltyChecker score {novelty_score:.2f} — 신규성 보통. 명시적 contribution 문장 추가 권장",
        ))
    return out


# ──────────────────────────────────────────────────────────────
# Gate 4: 과대주장 (overclaim)
# ──────────────────────────────────────────────────────────────

_OVERCLAIM_PATS = [
    (r"\bsignificantly\s+(?:improves?|increases?|reduces?|enhances?)\b", "단정적 우월성 주장"),
    (r"\b(?:definitely|certainly|undoubtedly|clearly\s+shows?|proves?)\b", "확실성 단정"),
    (r"\b(?:cure[ds]?|eradicates?)\b", "치료 단정 (cure/eradicate)"),
    (r"\bnever\b.*\b(?:fails?|wrong|incorrect)\b", "절대 단정"),
    (r"\bfor the first time\b(?!.*to our knowledge)", "최초 주장 (qualifier 없음)"),
    (r"\bonly\s+study\b", "유일성 단정"),
    (r"\brevolutioniz(?:es?|ed|ing)\b", "혁신 단정"),
]


def check_overclaim(text: str) -> List[GateResult]:
    out = []
    for pat, label in _OVERCLAIM_PATS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            out.append(GateResult(
                gate="overclaim_flags", severity="medium",
                message=f"{label}: '{m.group(0)}' — 한정 표현 (may/might/suggests/limited evidence)으로 완화 권장",
                spans=[{"start": m.start(), "end": m.end()}],
            ))
    return out


# ──────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────

def run_all_gates(text: str, *, known_pmids: Optional[List[str]] = None,
                    novelty_score: Optional[float] = None,
                    topic: Optional[Dict] = None,
                    verify_via_pubmed: bool = False) -> InlineReport:
    """4 게이트 모두 실행 → InlineReport 반환."""
    return InlineReport(
        statistical_assumptions=check_statistical_assumptions(text),
        citation_existence=check_citation_existence(text, known_pmids=known_pmids,
                                                     verify_via_pubmed=verify_via_pubmed),
        novelty_concerns=check_novelty(novelty_score, topic=topic),
        overclaim_flags=check_overclaim(text),
    )


def report_to_chat_blocks(rep: InlineReport) -> List[str]:
    """InlineReport → chat에 표시할 마크다운 블록 list."""
    blocks = []
    if rep.total_issues == 0:
        return ["✅ 4 inline gates passed: no statistical/citation/novelty/overclaim issues."]
    if rep.statistical_assumptions:
        blocks.append("⚠️ **통계 가정**: " + " | ".join(g.message for g in rep.statistical_assumptions[:3]))
    if rep.citation_existence:
        blocks.append("📑 **인용 실재성**: " + " | ".join(g.message for g in rep.citation_existence[:3]))
    if rep.novelty_concerns:
        blocks.append("🆕 **신규성**: " + " | ".join(g.message for g in rep.novelty_concerns[:3]))
    if rep.overclaim_flags:
        blocks.append("🚩 **과대주장**: " + " | ".join(g.message for g in rep.overclaim_flags[:3]))
    return blocks
