"""Orientation Detector — 업로드된 작성 중 논문에서 추구 유형을 자동 감지.

사용자 비전 (2026-05-31):
    "작성되어 있는 상태의 논문을 올리거나 작업 중인 논문의 원문이 있으면
     결국 어느 요소를 강조할 것인지 되물어보고 그 느낌을 더 살리는 구조에
     따라서 작성 톤앤 매너가 미묘하게 바뀌어야 한다."

흐름:
    upload paper text → detect_orientations(text)
      → 휴리스틱 점수 (각 유형별 키워드 frequency / 문장 패턴 / 강조어)
      → LLM-free fallback + (가능 시) LLM 정밀 판정
      → OrientationCandidates(scores={...}, top=[...], suggested=PaperOrientation(...))

UI는 이 결과를 사용자에게 보여주고 "맞나요? 추가/제거할 것?" 확인 후 apply_to_intent.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.research.emphasis_profile import (
    PaperOrientation, ORIENTATION_TYPES,
)

_log = get_logger(__name__)


# ── 휴리스틱 키워드/문구 패턴 (논문 텍스트에서 추구 유형 감지) ─────────────

ORIENTATION_HEURISTICS = {
    "novelty": {
        "strong": [
            r"\bfirst (?:study|to (?:show|demonstrate|report|examine))\b",
            r"\blargest (?:cohort|study|sample|analysis)\b",
            r"\bnovel (?:finding|approach|insight)\b",
            r"\bto our knowledge\b",
            r"\bnationally representative\b",
            r"\bunique(?:ly)? positioned\b",
        ],
        "moderate": [
            r"\bunprecedented\b", r"\bground[- ]?breaking\b",
            r"\bemerging\b", r"\bpreviously unexplored\b",
            r"\bgap in (?:the )?literature\b",
        ],
    },
    "consistency": {
        "strong": [
            r"\bconsistent across\b", r"\brobust to\b",
            r"\bsensitivity analy(?:sis|ses)\b",
            r"\b(?:subgroup|stratified) analy(?:sis|ses)\b",
            r"\bremained (?:significant|robust|similar)\b",
            r"\bno (?:significant )?(?:effect[- ]?modification|interaction)\b",
        ],
        "moderate": [
            r"\breplicate(?:d|s)?\b", r"\breproduc(?:ible|ed)\b",
            r"\bsimilar (?:pattern|magnitude|direction)\b",
        ],
    },
    "innovation": {
        "strong": [
            r"\bnovel mechanism\b", r"\bnew methodology\b",
            r"\bnovel approach\b", r"\bnew conceptual framework\b",
            r"\bbiologically plausible mechanism\b",
            r"\bmediation analy(?:sis|ses)\b",
            r"\bcausal inference\b",
        ],
        "moderate": [
            r"\bmechanism\b", r"\bpathway\b", r"\bhypothesis-driven\b",
            r"\binterdisciplinary\b",
        ],
    },
    "public_health": {
        "strong": [
            r"\bpublic health (?:implication|relevance|impact)\b",
            r"\bpolicy implication\b",
            r"\bclinical(?:ly)? (?:actionable|relevant)\b",
            r"\bshould (?:be considered|consider|target)\b",
            r"\bschool[- ]based intervention\b",
            r"\bregulatory\b", r"\btargeted intervention\b",
        ],
        "moderate": [
            r"\bprevention\b", r"\bscreening\b", r"\bhealth education\b",
            r"\bclinician(?:s)?\b", r"\bpolicy[- ]?makers?\b",
        ],
    },
    "methodological_rigor": {
        "strong": [
            r"\bcomplex survey design\b",
            r"\b(?:cluster|robust)[- ]?(?:robust )?(?:standard error|variance)\b",
            r"\bsampling weight(?:s)?\b",
            r"\bdose[- ]?response\b",
            r"\blinear trend\b",
            r"\bmultiple imputation\b",
            r"\b(?:fully )?adjusted (?:for )?(?:\d+|all|extensive)\b",
            r"\bpropensity score\b",
        ],
        "moderate": [
            r"\bmultivariable adjustment\b", r"\bcovariate(?:s)?\b",
            r"\bsurvey[- ]weighted\b", r"\bsvy\b",
        ],
    },
}


@dataclass
class OrientationCandidates:
    scores: Dict[str, float] = field(default_factory=dict)
    matched_phrases: Dict[str, List[str]] = field(default_factory=dict)
    top: List[str] = field(default_factory=list)  # score 상위 슬러그
    suggested: Optional[PaperOrientation] = None
    text_chars: int = 0

    def to_dict(self) -> dict:
        return {
            "scores": self.scores,
            "matched_phrases": self.matched_phrases,
            "top": self.top,
            "suggested": self.suggested.to_dict() if self.suggested else None,
            "text_chars": self.text_chars,
        }


def detect_orientations(
    text: str,
    *,
    threshold: float = 1.0,
    max_top: int = 3,
) -> OrientationCandidates:
    """텍스트(논문 본문)에서 휴리스틱으로 추구 유형 점수 산출.

    점수 = strong 매칭 × 2 + moderate 매칭 × 1 (per 1k chars).
    threshold 이상이면 suggested에 포함, 상위 max_top개를 top에 정리.
    """
    if not text:
        return OrientationCandidates()

    text_norm = text.lower()
    n_chars = len(text_norm)
    per_1k = max(1.0, n_chars / 1000.0)

    scores: Dict[str, float] = {}
    matched: Dict[str, List[str]] = {}

    for slug, patterns in ORIENTATION_HEURISTICS.items():
        s = 0.0
        hits: List[str] = []
        for p in patterns.get("strong", []):
            found = re.findall(p, text_norm)
            if found:
                s += 2.0 * len(found)
                hits.extend([f"[STRONG]{p}" for _ in found[:3]])
        for p in patterns.get("moderate", []):
            found = re.findall(p, text_norm)
            if found:
                s += 1.0 * len(found)
                hits.extend([f"[MOD]{p}" for _ in found[:2]])
        # 정규화: 1000자당 점수
        scores[slug] = round(s / per_1k * 10, 2)
        matched[slug] = hits[:8]

    # 상위 추출
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    top_slugs = [slug for slug, sc in ranked if sc >= threshold][:max_top]

    suggested = PaperOrientation()
    for slug in top_slugs:
        if hasattr(suggested, slug):
            setattr(suggested, slug, True)

    return OrientationCandidates(
        scores=scores,
        matched_phrases=matched,
        top=top_slugs,
        suggested=suggested,
        text_chars=n_chars,
    )


def describe_for_ui(cand: OrientationCandidates) -> str:
    """popover/dialog에 표시할 사람이 읽는 요약."""
    if not cand.scores:
        return "분석할 텍스트 없음"
    lines = [f"📄 텍스트 {cand.text_chars:,}자 분석 결과:", ""]
    slug2label = {d["slug"]: d["label"] for d in ORIENTATION_TYPES}
    ranked = sorted(cand.scores.items(), key=lambda kv: kv[1], reverse=True)
    for slug, sc in ranked:
        flag = "★" if slug in cand.top else " "
        lines.append(f"  {flag} {slug2label.get(slug, slug)}: {sc:.2f}")
    if cand.top:
        lines.append("")
        lines.append(f"→ 추정 추구 유형: {', '.join(cand.top)}")
    else:
        lines.append("")
        lines.append("→ 뚜렷한 추구 유형 미감지 (모든 유형 약함)")
    return "\n".join(lines)


__all__ = [
    "OrientationCandidates", "detect_orientations", "describe_for_ui",
    "ORIENTATION_HEURISTICS",
]
