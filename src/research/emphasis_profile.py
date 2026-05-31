"""Paper Orientation — 논문이 추구하는 유형에 따라 톤앤매너 자동 조정.

사용자 비전 (2026-05-31):
    "5개는 강조점이 아니다. 논문이 보통 추구하고자 하는 유형들이 있다는 것이다.
     노벨티를 추구하는지, 통일성을 추구하는지, 학술적 혁신성을 추구하는지,
     공중보건 함의를 추구하는지, 통계적 견고성을 추구하는지 —
     논문마다 궁극적으로 표현하고자 하는 톤앤매너가 있다.
     그 추구 유형에 따라 작성 톤이 미묘하게 바뀐다."

본 모듈은 그 추구 유형(orientation)을 카탈로그하고, 선택된 유형(다중 가능)을
intent_sensor에 임프린트하여 이후 모든 LLM 호출의 톤·구성·뉘앙스를 조정한다.

대표적 추구 유형 (확장 가능 — 사용자가 자유 양식으로도 추가 가능):
    NOVELTY              — 첫/최대 규모/새로운 finding을 추구
    CONSISTENCY          — subgroup 일관성·robustness·재현성을 추구
    INNOVATION           — 기전·방법론·개념적 혁신을 추구
    PUBLIC_HEALTH        — 정책·임상·교육 함의를 추구
    METHODOLOGICAL_RIGOR — 통계·design의 견고성을 추구

이것들은 폐쇄적 enum이 아니다. 논문 작성자가 "여성 청소년의 사회문화적 압력"
같은 자유 양식 추구 유형을 추가할 수 있다 (custom_notes).

API:
    PaperOrientation(novelty=True, ...).apply_to_intent(owner_email)
    list_orientation_types() -> [(slug, label, hint)]
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List


# ── 대표적 추구 유형 카탈로그 (예시 — 확장 가능) ──────────────────────────

ORIENTATION_TYPES = [
    {
        "slug": "novelty",
        "label": "Novelty (새로움/최초/큰 규모를 추구)",
        "hint": "이 논문이 '처음 보여주는' 또는 '가장 큰 규모로 입증한' finding을 부각하는 유형",
        "imprint_labels": [
            "first_adolescent_study", "largest_N", "novel_finding",
            "first_to_show_dose_response",
        ],
        "voice_tone": ["assertive", "confident", "framing as discovery"],
        "section_weight": {
            "Abstract": "first/largest/novel을 첫 문장에",
            "Introduction": "기존 문헌의 빈 자리(gap) 명확히",
            "Discussion": "기존 연구와의 차이점 강조 + future direction",
        },
        "avoid": ["incremental contribution framing", "confirmatory tone"],
    },
    {
        "slug": "consistency",
        "label": "Consistency (subgroup 일관성·견고성을 추구)",
        "hint": "여러 subgroup·sensitivity 모두에서 같은 방향 결과 → 결과 신뢰성 강조 유형",
        "imprint_labels": [
            "consistent_across_subgroups", "robust_to_sensitivity",
            "no_effect_modification", "replicated_findings",
        ],
        "voice_tone": ["measured", "cautious", "evidential"],
        "section_weight": {
            "Results": "Overall + subgroup × stratifier 같은 방향임을 forest plot으로",
            "Discussion": "robustness 강조 — 다른 연구와도 일치",
            "Strengths": "comprehensive covariate adjustment + multiple sensitivity",
        },
        "avoid": ["overemphasis on one significant subgroup",
                   "ignoring null subgroups"],
    },
    {
        "slug": "innovation",
        "label": "Innovation (기전·방법론·개념적 혁신을 추구)",
        "hint": "새로운 mechanism 가설 또는 새 방법론·개념을 도입하여 의학적 진전을 추구하는 유형",
        "imprint_labels": [
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
        "label": "Public Health Implication (정책·임상 함의를 추구)",
        "hint": "결과가 임상·정책·교육 현장에 직접 작용하는 함의(relevance)를 추구하는 유형",
        "imprint_labels": [
            "policy_implication", "clinical_actionable",
            "school_intervention", "regulatory_signal",
        ],
        "voice_tone": ["practical", "action-oriented", "advocacy"],
        "section_weight": {
            "Abstract": "Conclusion에 'should consider' 형태로 정책 hook",
            "Discussion": "임상·교육·정책 actionable item 명시",
            "Conclusion": "imperative/recommendation 문장",
        },
        "avoid": ["passive 'warrants further research' framing만",
                   "academic-only framing"],
    },
    {
        "slug": "methodological_rigor",
        "label": "Methodological Rigor (통계·design 견고성을 추구)",
        "hint": "복합표본설계·다수 covariate·dose-response·sensitivity의 정확성을 추구하는 유형",
        "imprint_labels": [
            "complex_survey_design", "multi_covariate_adjustment",
            "dose_response_linear_trend", "multiple_sensitivity",
        ],
        "voice_tone": ["precise", "quantitative", "methodological"],
        "section_weight": {
            "Methods": "각 분석 단계의 rationale 명시 (왜 그 covariate / 왜 그 cutoff)",
            "Results": "categorical + linear trend + sensitivity 모두 보고",
            "Strengths": "methodological detail — 비교 연구 대비 우위",
        },
        "avoid": ["overstatement of effect size",
                   "incomplete reporting of sensitivity"],
    },
]


@dataclass
class PaperOrientation:
    """이 논문이 추구하는 유형 (다중 선택 가능)."""
    novelty: bool = False
    consistency: bool = False
    innovation: bool = False
    public_health: bool = False
    methodological_rigor: bool = False
    # 사용자가 자유롭게 추가하는 추구 유형 (위 5개에 없는 것)
    custom_notes: List[str] = field(default_factory=list)

    def selected(self) -> List[dict]:
        out = []
        for d in ORIENTATION_TYPES:
            if getattr(self, d["slug"], False):
                out.append(d)
        return out

    def to_dict(self) -> dict:
        return asdict(self)

    def as_system_block(self) -> str:
        sel = self.selected()
        if not sel and not self.custom_notes:
            return ""
        lines = ["# 🎯 PAPER ORIENTATION — 이 논문이 추구하는 유형", ""]
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
            lines.append("## 사용자 자유 추구 유형")
            for c in self.custom_notes:
                lines.append(f"- {c}")
            lines.append("")
        lines.append("→ 이 추구 유형을 본문 의미·구성·뉘앙스 단위로 살려라. "
                     "단순 키워드 나열 X. Abstract 첫 문장·Discussion 첫 단락·"
                     "Conclusion의 imperative에서 가장 두드러져야 한다.")
        return "\n".join(lines)

    def apply_to_intent(self, owner_email: str = "") -> bool:
        """intent_sensor의 현재 의도에 orientation imprint
        → 이후 모든 LLM 호출이 자동으로 이 추구 유형을 반영한다."""
        try:
            from src.agent.intent_sensor import (
                get_current, set_current, IntentSignal, merge_signals,
            )
            cur = get_current() or IntentSignal()
            all_labels: List[str] = []
            all_tones: List[str] = []
            for d in self.selected():
                all_labels.extend(d["imprint_labels"])
                all_tones.extend(d["voice_tone"])
            for note in self.custom_notes:
                all_labels.append(f"custom_orientation:{note[:80]}")
            addition = IntentSignal(
                explicit_request=f"Paper orientation: {[d['slug'] for d in self.selected()]}",
                implicit_emphasis=all_labels,
                voice_tone=all_tones,
            )
            merged = merge_signals(cur, addition)
            set_current(merged, owner_email=owner_email)
            return True
        except Exception:
            return False


def list_orientation_types() -> List[dict]:
    """UI multi-select용."""
    return [{"slug": d["slug"], "label": d["label"], "hint": d["hint"]}
            for d in ORIENTATION_TYPES]


# ── 후방 호환 alias (이전 명명) ──────────────────────────────────────────
EmphasisProfile = PaperOrientation
EMPHASIS_DEFS = ORIENTATION_TYPES
list_emphasis_options = list_orientation_types


__all__ = [
    "PaperOrientation", "ORIENTATION_TYPES", "list_orientation_types",
    "EmphasisProfile", "EMPHASIS_DEFS", "list_emphasis_options",
]
