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
같은 자유  추구 유형을 추가할 수 있다 (custom_notes).

API:
    PaperOrientation(novelty=True, ...).apply_to_intent(owner_email)
    list_orientation_types() -> [(slug, label, hint)]
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List


# ── 대표적 추구 유형 카탈로그 (예시 — 확장 가능) ──────────────────────────

CLINICAL_ORIENTATION_TYPES = [
    {
        "slug": "clinical_unanswered_question",
        "label": "Clinical Unanswered Question — RCT does not cover this patient",
        "hint": "주요 RCT가 답하지 못한 subpopulation·시나리오. Guideline 권고가 약한 자리.",
        "imprint_labels": ["unanswered_clinical_question", "rct_subpopulation_gap",
                            "guideline_weak_recommendation", "real_world_decision_gap"],
        "voice_tone": ["clinician-facing", "decision-oriented", "uncertainty-acknowledging"],
        "section_weight": {
            "Introduction": "기존 RCT의 inclusion/exclusion 한계 명시 → 이 환자군은 답 없음",
            "Methods": "trial emulation framework 또는 target trial 명시",
            "Discussion": "guideline 적용 시점·환자군 명시, 다음 RCT 설계 방향 제안",
        },
        "avoid": ["epidemiologic burden framing", "lifestyle factor framing"],
    },
    {
        "slug": "drug_safety_signal",
        "label": "Drug Safety Signal — post-marketing AE detection",
        "hint": "RCT에서 못 잡은 rare/long-term AE를 real-world data로 탐지.",
        "imprint_labels": ["pharmacovigilance", "adverse_event_detection",
                            "self_controlled_case_series", "disproportionality_analysis"],
        "voice_tone": ["safety-focused", "regulator-aware", "mechanistic when possible"],
        "section_weight": {
            "Introduction": "약물 작용기전 → 예상 AE → RCT 한계 (sample size, follow-up)",
            "Methods": "SCCS / new-user active-comparator design / negative control",
            "Results": "exposure window별 IRR + sensitivity",
            "Discussion": "FDA/EMA/MFDS 시그널 비교, 임상의 처방 결정 implication",
        },
        "avoid": ["public-health burden opening", "ecological inference"],
    },
    {
        "slug": "trial_emulation",
        "label": "Target Trial Emulation (Hernán framework)",
        "hint": "Observational data로 가상의 RCT를 protocol 단위로 emulation.",
        "imprint_labels": ["target_trial_emulation", "hernan_framework",
                            "active_comparator_new_user", "clone_censor_weight"],
        "voice_tone": ["epidemiologic methods rigor", "causal language careful"],
        "section_weight": {
            "Methods": "target trial protocol table (eligibility/intervention/assignment/outcome/follow-up/analysis)",
            "Results": "intention-to-treat + per-protocol with IPW",
            "Discussion": "RCT 결과와 일치 여부, 외적 타당성",
        },
        "avoid": ["weak adjustment", "naive PSM only"],
    },
    {
        "slug": "biomarker_validation",
        "label": "Biomarker / Risk Score Validation",
        "hint": "기존 또는 신규 biomarker·예측모델의 임상 검증 (validation cohort).",
        "imprint_labels": ["biomarker_validation", "prediction_model_validation",
                            "tripod_compliant", "calibration_discrimination"],
        "voice_tone": ["TRIPOD-aligned", "clinical utility focus"],
        "section_weight": {
            "Methods": "biomarker measurement protocol, derivation vs validation cohort",
            "Results": "AUC, calibration plot, decision curve analysis",
            "Discussion": "임상 적용 cutoff, clinical utility",
        },
        "avoid": ["effect size only without clinical utility"],
    },
    {
        "slug": "guideline_gap",
        "label": "Guideline Gap — RWE for under-represented patient",
        "hint": "가이드 권고가 약하거나 부재한 patient subgroup에 대한 RWE.",
        "imprint_labels": ["guideline_gap", "weak_recommendation_evidence",
                            "underrepresented_subgroup", "comparative_effectiveness"],
        "voice_tone": ["guideline-aware", "subgroup-precise"],
        "section_weight": {
            "Introduction": "current guideline 인용 + 권고 등급 명시 + gap 정의",
            "Methods": "subgroup analysis pre-specified, effect modification test",
            "Discussion": "guideline 개정 시 고려할 evidence 위치",
        },
        "avoid": ["overstating guideline change implication"],
    },
    {
        "slug": "mechanism_translational",
        "label": "Mechanism → Biomarker → Outcome translational chain",
        "hint": "분자/세포 기전 → biomarker → 임상 endpoint의 연결.",
        "imprint_labels": ["translational_chain", "mechanism_biomarker_outcome",
                            "mediator_analysis", "pathway_specific"],
        "voice_tone": ["mechanistic", "translational"],
        "section_weight": {
            "Introduction": "biological pathway 명시 → 임상 가설 도출",
            "Methods": "mediator measurement + 4-way decomposition or G-computation",
            "Discussion": "mechanism이 outcome을 얼마나 매개하는지, druggable target",
        },
        "avoid": ["mechanism speculation without measurement"],
    },
]


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
    """이 논문이 추구하는 유형 (다중 선택 가능).

    공중보건/역학 5개 + 임상 reasoning 6개. 사용자 분과/주제에 따라 임의 조합.
    """
    # epidemiology-leaning (original 5)
    novelty: bool = False
    consistency: bool = False
    innovation: bool = False
    public_health: bool = False
    methodological_rigor: bool = False
    # clinical reasoning (added 2026-06-04)
    clinical_unanswered_question: bool = False
    drug_safety_signal: bool = False
    trial_emulation: bool = False
    biomarker_validation: bool = False
    guideline_gap: bool = False
    mechanism_translational: bool = False
    # 사용자가 자유롭게 추가
    custom_notes: List[str] = field(default_factory=list)

    def selected(self) -> List[dict]:
        out = []
        for d in (ORIENTATION_TYPES + CLINICAL_ORIENTATION_TYPES):
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
    """UI multi-select용 — epidemiology 5 + clinical 6 = 11 카테고리."""
    return [{"slug": d["slug"], "label": d["label"], "hint": d["hint"],
              "category": "clinical" if d in CLINICAL_ORIENTATION_TYPES else "epidemiology"}
            for d in (ORIENTATION_TYPES + CLINICAL_ORIENTATION_TYPES)]


# ── 후방 호환 alias (이전 명명) ──────────────────────────────────────────
EmphasisProfile = PaperOrientation
EMPHASIS_DEFS = ORIENTATION_TYPES
list_emphasis_options = list_orientation_types


__all__ = [
    "PaperOrientation", "ORIENTATION_TYPES", "list_orientation_types",
    "EmphasisProfile", "EMPHASIS_DEFS", "list_emphasis_options",
]
