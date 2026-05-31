"""Emphasis Profile — 논문의 궁극 강조점을 LLM 임프린트로 자동 적용.

사용자 비전 (2026-05-31):
    "논문마다 궁극적으로 표현하고자 하는 톤앤 매너가 있다. 노벨티 / 통일성 /
     학술적 혁신성 / 공중보건 함의 / 통계적 견고성 — 그것을 살리는 구조에 따라
     작성 톤이 미묘하게 바뀐다."

5가지 강조점 (multi-select):
    NOVELTY              — 첫/최대 N/새로운 finding 강조
    CONSISTENCY          — subgroup 일관성, robustness, replicability
    INNOVATION           — mechanism, methodology, conceptual leap
    PUBLIC_HEALTH        — 정책·임상·역학 함의
    METHODOLOGICAL_RIGOR — 통계 견고성, design strength

API:
    EmphasisProfile(novelty=True, consistency=True, ...).apply_to_intent(owner_email)
    list_emphasis_options() -> [(slug, label, hint)]
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional


# ── 5가지 강조점 정의 ─────────────────────────────────────────────────────

EMPHASIS_DEFS = [
    {
        "slug": "novelty",
        "label": "Novelty (새로움/최초/큰 규모)",
        "hint": "이 논문이 '처음 보여주는' 또는 '가장 큰 규모로 입증한' finding을 부각",
        "emphasis_labels": [
            "first_adolescent_study", "largest_N", "novel_finding",
            "first_to_show_dose_response",
        ],
        "voice_tone": ["assertive", "confident", "framing as discovery"],
        "section_weight": {
            "Abstract": "first/largest/novel을 첫 문장에",
            "Introduction": "기존 문헌의 빈 자리(gap) 명확히",
            "Discussion": "기존 연구와의 차이점 강조 + future direction",
        },
        "avoid": ["incremental contribution", "confirmatory framing"],
    },
    {
        "slug": "consistency",
        "label": "Consistency (subgroup 일관성·견고성)",
        "hint": "여러 subgroup·sensitivity 모두에서 같은 방향 결과 → 결과 신뢰성",
        "emphasis_labels": [
            "consistent_across_subgroups", "robust_to_sensitivity",
            "no_effect_modification", "replicated_findings",
        ],
        "voice_tone": ["measured", "cautious", "evidential"],
        "section_weight": {
            "Results": "Overall + subgroup × 7 stratifier 같은 방향임을 forest plot 양식",
            "Discussion": "robustness emphasis — 다른 연구와도 일치",
            "Strengths": "comprehensive covariate adjustment + multiple sensitivity",
        },
        "avoid": ["overemphasis on one significant subgroup",
                   "ignoring null subgroup"],
    },
    {
        "slug": "innovation",
        "label": "Innovation (기전·방법론·개념 혁신)",
        "hint": "새 mechanism 가설 또는 새 방법론·개념 양식 — 의학사적 진전",
        "emphasis_labels": [
            "novel_mechanism", "new_methodology", "conceptual_leap",
            "interdisciplinary_bridge",
        ],
        "voice_tone": ["intellectual", "exploratory", "hypothesis-driven"],
        "section_weight": {
            "Introduction": "기존 mechanism의 한계 → 새 개념 도입",
            "Methods": "방법론의 novelty 명시",
            "Discussion": "mechanism 가설 + future mechanism studies 제안",
        },
        "avoid": ["pure replication tone", "no new conceptual contribution"],
    },
    {
        "slug": "public_health",
        "label": "Public Health Implication (정책·임상 함의)",
        "hint": "결과가 임상·정책·교육 양식에 직접 작용 — relevance",
        "emphasis_labels": [
            "policy_implication", "clinical_actionable",
            "school_intervention", "regulatory_signal",
        ],
        "voice_tone": ["practical", "action-oriented", "advocacy"],
        "section_weight": {
            "Abstract": "Conclusion에 'should consider' 양식 정책 hook",
            "Discussion": "임상·교육·정책 양식 actionable item 명시",
            "Conclusion": "imperative/recommendation 문장",
        },
        "avoid": ["passive 'warrants further research' 양식만",
                   "academic-only framing"],
    },
    {
        "slug": "methodological_rigor",
        "label": "Methodological Rigor (통계·design 견고성)",
        "hint": "복합표본설계, 12 covariate, dose-response, sensitivity 양식 정확성",
        "emphasis_labels": [
            "complex_survey_design", "11_covariate_adjustment",
            "dose_response_linear_trend", "multiple_sensitivity",
        ],
        "voice_tone": ["precise", "quantitative", "methodological"],
        "section_weight": {
            "Methods": "각 분석 단계의 rationale 명시 (왜 그 covariate / 왜 그 cutoff)",
            "Results": "categorical + linear trend + sensitivity 모두 보고",
            "Strengths": "methodological detail 양식 — 비교 연구 대비 우위",
        },
        "avoid": ["overstatement of effect size",
                   "incomplete reporting of sensitivity"],
    },
]


@dataclass
class EmphasisProfile:
    novelty: bool = False
    consistency: bool = False
    innovation: bool = False
    public_health: bool = False
    methodological_rigor: bool = False
    # 사용자가 직접 추가한 자유 양식 강조 양식 (예: "여성 청소년에서의 사회문화적 압력")
    custom_notes: List[str] = field(default_factory=list)

    def selected(self) -> List[dict]:
        out = []
        for d in EMPHASIS_DEFS:
            if getattr(self, d["slug"], False):
                out.append(d)
        return out

    def to_dict(self) -> dict:
        return asdict(self)

    def as_system_block(self) -> str:
        sel = self.selected()
        if not sel and not self.custom_notes:
            return ""
        lines = ["# 🎯 EMPHASIS PROFILE — 논문의 궁극 강조점",
                 ""]
        for d in sel:
            lines.append(f"## {d['label']}")
            lines.append(d["hint"])
            lines.append("")
            lines.append("**섹션별 적용:**")
            for sec, what in d["section_weight"].items():
                lines.append(f"- {sec}: {what}")
            lines.append("")
            lines.append("**피해야 할 톤:**")
            for a in d["avoid"]:
                lines.append(f"- {a}")
            lines.append("")
        if self.custom_notes:
            lines.append("## 사용자 자유 강조 양식")
            for c in self.custom_notes:
                lines.append(f"- {c}")
        lines.append("")
        lines.append("→ 이 강조점을 본문 의미·구성·강조점·뉘앙스 단위로 살려라. "
                     "단순 키워드 나열 X. Abstract 첫 문장·Discussion 첫 단락·"
                     "Conclusion의 imperative에서 가장 두드러져야 한다.")
        return "\n".join(lines)

    def apply_to_intent(self, owner_email: str = "") -> bool:
        """intent_sensor의 현재 의도에 emphasis 양식 imprint → 이후 모든 LLM 호출 자동 반영."""
        try:
            from src.agent.intent_sensor import (
                get_current, set_current, IntentSignal, merge_signals,
            )
            cur = get_current() or IntentSignal()
            all_labels = []
            all_tones = []
            for d in self.selected():
                all_labels.extend(d["emphasis_labels"])
                all_tones.extend(d["voice_tone"])
            for note in self.custom_notes:
                all_labels.append(f"custom:{note[:60]}")
            addition = IntentSignal(
                explicit_request=f"Emphasis: {[d['slug'] for d in self.selected()]}",
                implicit_emphasis=all_labels,
                voice_tone=all_tones,
            )
            merged = merge_signals(cur, addition)
            set_current(merged, owner_email=owner_email)
            return True
        except Exception:
            return False


def list_emphasis_options() -> List[dict]:
    """UI multi-select에 쓸 양식."""
    return [{"slug": d["slug"], "label": d["label"], "hint": d["hint"]}
            for d in EMPHASIS_DEFS]


__all__ = ["EmphasisProfile", "EMPHASIS_DEFS", "list_emphasis_options"]
