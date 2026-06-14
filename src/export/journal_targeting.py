"""Journal targeting — 저널별 강조 strength를 LLM 임프린트로 자동 적용.

배경 (2026-05-30, 사용자 요구):
    같은 데이터/결과여도 어느 저널에 제출하느냐에 따라 강조점·톤·구조가 달라야 한다.
    각 저널의 reviewer가 어떤 점을 가장 보고 싶어하는지를 미리 system_prompt에 박아,
    Discussion/Abstract/Introduction의 angle을 자동 조정.

저널별 strength 매핑 (사용자 명시):
    JAH (Journal of Adolescent Health):
        Adolescent-specific developmental window (12-15세) + sex differences
    JAMA Network Open:
        First adolescent ZCB-depression study, large N (50K+), novel sex finding
    Appetite:
        Body image / dieting behavioral pathway 가설
    Nutrients:
        Dose-response + comprehensive covariate adjustment

추가 저널 (확장 시):
    NEJM, Lancet, JKMS, BMJ Open, Pediatrics 등은 JOURNALS dict에 같은 양식으로 추가.

API:
    list_journals() -> list[str]
    get_journal_targeting(slug) -> JournalTargeting
    apply_to_intent(slug, owner_email="") -> None  # intent_sensor에 임프린트
    rewrite_prompt(slug, section="Discussion") -> str  # LLM에 줄 rewrite 트리거

호출:
    workspace 토픽바의 🎯 Target Journal selectbox → Apply 버튼.
    apply하면 intent_sensor에 강조점이 임프린트되어 이후 모든 LLM 호출이 그 angle로 작동.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class JournalTargeting:
    slug: str
    full_name: str
    impact_factor: Optional[float] = None
    strengths_to_emphasize: List[str] = field(default_factory=list)
    angle: str = ""               # 한 줄 핵심 angle
    reader_assumption: str = ""   # 가정 독자 (reviewer 양식)
    voice_tone: str = ""          # 권장 톤
    section_priorities: dict = field(default_factory=dict)   # 섹션별 강조 weight
    avoid: List[str] = field(default_factory=list)           # 회피
    # MASTER_UPGRADE §3 #7 — Journal Intelligence: 작성/제출 룰
    word_limit_total: Optional[int] = None        # full manuscript word cap
    word_limit_abstract: Optional[int] = None
    reference_style: str = ""                     # "Vancouver"|"AMA"|"APA"|"Harvard"
    reference_max: Optional[int] = None
    figure_max: Optional[int] = None
    table_max: Optional[int] = None
    structured_abstract: bool = False
    requires_strobe: bool = False
    submission_url: str = ""
    acceptance_rate_hint: str = ""                # e.g. "~25%" / "competitive"

    def to_dict(self) -> dict:
        return asdict(self)

    def as_emphasis_labels(self) -> List[str]:
        """intent_sensor.implicit_emphasis에 주입할 label 양식."""
        return [f"journal:{self.slug}:{s[:50]}" for s in self.strengths_to_emphasize]

    def as_system_block(self) -> str:
        """system_prompt에 박을 한국어 블록."""
        lines = [
            f"# 🎯 TARGET JOURNAL: {self.full_name} ({self.slug})",
            "",
            f"## Angle (한 줄로)",
            self.angle,
            "",
            "## 이 저널이 가장 보고 싶어하는 strength (Discussion/Abstract에서 강조)",
        ]
        for i, s in enumerate(self.strengths_to_emphasize, 1):
            lines.append(f"{i}. {s}")
        if self.reader_assumption:
            lines += ["", f"## 가정 독자/reviewer", self.reader_assumption]
        if self.voice_tone:
            lines += ["", f"## 권장 톤", self.voice_tone]
        if self.section_priorities:
            lines += ["", "## 섹션별 강조 weight"]
            for sec, w in self.section_priorities.items():
                lines.append(f"- {sec}: {w}")
        if self.avoid:
            lines += ["", "## 피해야 할 양식"]
            for a in self.avoid:
                lines.append(f"- {a}")
        # 제출 룰 블록 (#7 확장)
        rule_lines = []
        if self.word_limit_total:
            rule_lines.append(f"- Manuscript word limit: {self.word_limit_total}")
        if self.word_limit_abstract:
            rule_lines.append(f"- Abstract word limit: {self.word_limit_abstract}")
        if self.reference_style:
            rule_lines.append(f"- Reference style: {self.reference_style}")
        if self.reference_max:
            rule_lines.append(f"- Max references: {self.reference_max}")
        if self.figure_max is not None:
            rule_lines.append(f"- Max figures: {self.figure_max}")
        if self.table_max is not None:
            rule_lines.append(f"- Max tables: {self.table_max}")
        if self.structured_abstract:
            rule_lines.append("- Structured abstract required (Background/Methods/Results/Conclusions)")
        if self.requires_strobe:
            rule_lines.append("- STROBE checklist required (observational design)")
        if self.acceptance_rate_hint:
            rule_lines.append(f"- Acceptance rate hint: {self.acceptance_rate_hint}")
        if rule_lines:
            lines += ["", "## Submission rules"] + rule_lines

        lines += ["",
                  "→ 위 strength를 단순 나열이 아니라 의미 단위로 본문에 살려라. "
                  "Discussion의 implication·Abstract의 첫 문장에서 가장 두드러져야 한다."]
        return "\n".join(lines)


# ── 저널 레지스트리 (사용자 4개 + 확장 가능) ──────────────────────────────

JOURNALS: dict[str, JournalTargeting] = {

    # ── 사용자 명시 4개 ──

    "jah": JournalTargeting(
        slug="jah",
        full_name="Journal of Adolescent Health",
        impact_factor=7.5,
        strengths_to_emphasize=[
            "Adolescent-specific developmental window (12-15세) — 뇌·정신건강 발달의 결정적 시기",
            "Sex differences in dose-response (여성에서 단순히 더 강한 효과 X — "
            "구체: 'effect evident only in females, P for interaction < 0.001')",
            "Korean national survey representativeness (KYRBS, n=50K+)",
        ],
        angle=(
            "청소년기는 뇌 성숙·정체성 형성의 결정적 시기로, ZCB 섭취가 이 시기에 미치는 "
            "성별 특이적 효과를 처음 보여준다.  보강이 아닌 행동·정책 timing의 함의."
        ),
        reader_assumption=(
            "Adolescent health 전문 reviewer (소아청소년과·청소년 정신건강 전문의·역학자). "
            "Developmental sensitivity 양식을 가장 중요하게 봄."
        ),
        voice_tone="assertive but cautious, developmental framing 강조",
        section_priorities={
            "Introduction": "adolescent developmental window 중심",
            "Discussion": "sex-diff implication + adolescent-specific timing",
            "Abstract": "발달 시기 + 성별 차이  두 문장에 명시",
        },
        avoid=["성인 데이터와 단순 비교", "general adult literature  의존"],
        # Submission rules (#7) — Journal of Adolescent Health 2024 guidelines
        word_limit_total=4500, word_limit_abstract=275,
        reference_style="AMA", reference_max=50,
        figure_max=5, table_max=5,
        structured_abstract=True, requires_strobe=True,
        submission_url="https://www.editorialmanager.com/jah/",
        acceptance_rate_hint="~25% (competitive)",
    ),

    "jama_open": JournalTargeting(
        slug="jama_open",
        full_name="JAMA Network Open",
        impact_factor=13.8,
        strengths_to_emphasize=[
            "First adolescent ZCB-depression study with this scale (novelty claim)",
            "Large N (50,000+) — population-representative",
            "Novel sex-specific finding (effect evident only in females, P_interaction<0.001)",
            "Rigorous survey design (stratification + clustering + weights)",
        ],
        angle=(
            "청소년 ZCB-우울증 연관성을 인구 대표 표본으로 처음 정량한 연구. "
            "Public health-level finding으로 frame."
        ),
        reader_assumption=(
            "Top-tier general medical reviewer — novelty + methodological rigor + "
            "clinical/public health relevance 셋 다 양식. Reviewer 1은 통계, "
            "Reviewer 2는 임상, Reviewer 3는 public health 가능."
        ),
        voice_tone="confident, broad-audience, public health framing",
        section_priorities={
            "Abstract": "First/Largest/Novel 세 키워드 첫 문장에",
            "Methods": "complex survey design + 11 covariate 강조",
            "Discussion": "public health implication + policy hook",
        },
        avoid=["narrow specialist jargon", "본 연구 한계를 첫 단락에 두는 양식"],
        word_limit_total=4000, word_limit_abstract=350,
        reference_style="AMA", reference_max=75,
        figure_max=6, table_max=5,
        structured_abstract=True, requires_strobe=True,
        submission_url="https://manuscripts.jamanetwork.com/jamanetworkopen",
        acceptance_rate_hint="~13% (very competitive)",
    ),

    "appetite": JournalTargeting(
        slug="appetite",
        full_name="Appetite",
        impact_factor=4.6,
        strengths_to_emphasize=[
            "Body image / dieting behavioral pathway 가설 — 왜 ZCB가 mental health에 영향을 주는가의 mechanism",
            "Sweetener-specific behavioral pathway (sugar 대체가 아니라 dieting intent의 marker)",
            "Korean adolescents — culturally salient body image pressure 맥락",
            "Daily ZCB intake vs occasional의 dose-response in eating behavior",
        ],
        angle=(
            "ZCB는 단순 영양소가 아니라 dieting behavior의 marker로 작용. "
            "Body image distortion이 mental health와 ZCB 양쪽의 공통 driver."
        ),
        reader_assumption=(
            "Eating behavior / appetite science reviewer — 통계 결과보다 mechanism + "
            "behavioral pathway에 가장 관심. Pure clinical outcome 단독 보고는 약함."
        ),
        voice_tone="hypothesis-driven, behavioral framework 중심",
        section_priorities={
            "Introduction": "dieting/body image behavioral framework 양식",
            "Discussion": "mediation hypothesis + future mediator analysis suggestion",
        },
        avoid=["sweetener의 생화학적 직접 효과를 1순위로 두는 양식",
                "neural reward 가설을 충분한 근거 없이 단정"],
        word_limit_total=6000, word_limit_abstract=250,
        reference_style="APA", reference_max=80,
        figure_max=8, table_max=5,
        structured_abstract=False, requires_strobe=False,
        submission_url="https://www.editorialmanager.com/appetite/",
        acceptance_rate_hint="~30%",
    ),

    "nutrients": JournalTargeting(
        slug="nutrients",
        full_name="Nutrients",
        impact_factor=5.9,
        strengths_to_emphasize=[
            "Dose-response (frequency 1단위 증가당 aOR의 선형 추세 + categorical aOR 표)",
            "Comprehensive covariate adjustment (11개: 인구통계 + lifestyle + dietary)",
            "Linear trend test + categorical frequency 양쪽 모두 보고",
            "Sensitivity analysis (complete-case / multiple imputation / restricted model 다중)",
        ],
        angle=(
            "Frequency 단위의 dose-response를 11개 공변량 조정 후 견고하게 입증 — "
            "nutritional epidemiology의 정량성·강건성 강조."
        ),
        reader_assumption=(
            "Nutritional epidemiology reviewer — statistical rigor에 가장 무게. "
            "Methodological detail이 본문에 충분히 드러나야 함."
        ),
        voice_tone="precise, quantitative, methodological",
        section_priorities={
            "Methods": "covariate selection rationale + dose coding 상세",
            "Results": "categorical aOR 표 + linear trend P value",
            "Discussion": "robustness — multiple sensitivity analysis 결과 정리 + 추정의 안정성",
        },
        avoid=["mechanism speculation을 통계 결과보다 앞세우는 양식"],
        word_limit_total=8000, word_limit_abstract=200,
        reference_style="MDPI/Harvard", reference_max=120,
        figure_max=10, table_max=8,
        structured_abstract=False, requires_strobe=True,
        submission_url="https://susy.mdpi.com/user/manuscripts/upload?journal=nutrients",
        acceptance_rate_hint="~45%",
    ),

    # ── 확장 후보 (추후 keys 추가) ──
    # "nejm": JournalTargeting(slug="nejm", ...),
    # "lancet": JournalTargeting(slug="lancet", ...),
    # "jkms": JournalTargeting(slug="jkms", ...),
    # "bmj_open": JournalTargeting(slug="bmj_open", ...),
    # "pediatrics": JournalTargeting(slug="pediatrics", ...),
}


def list_journals() -> List[dict]:
    """UI selectbox에 쓸 (slug, full_name, IF) 리스트."""
    return [{"slug": j.slug, "full_name": j.full_name,
             "impact_factor": j.impact_factor,
             "angle": j.angle[:120]}
            for j in JOURNALS.values()]


def get_journal_targeting(slug: str) -> Optional[JournalTargeting]:
    return JOURNALS.get(slug.lower())


def apply_to_intent(slug: str, *, owner_email: str = "") -> bool:
    """저널 strength를 intent_sensor의 현재 의도에 merge → 이후 모든 LLM 호출 자동 반영."""
    jt = get_journal_targeting(slug)
    if jt is None:
        return False
    try:
        from src.agent.intent_sensor import (
            get_current, set_current, IntentSignal, merge_signals,
        )
        cur = get_current() or IntentSignal()
        addition = IntentSignal(
            explicit_request=f"Target journal: {jt.full_name}",
            implicit_emphasis=jt.as_emphasis_labels() + [f"angle:{jt.angle[:80]}"],
            voice_tone=[jt.voice_tone] if jt.voice_tone else [],
            reader_assumption=[jt.reader_assumption[:120]] if jt.reader_assumption else [],
        )
        merged = merge_signals(cur, addition)
        set_current(merged, owner_email=owner_email)
        return True
    except Exception as e:
        _log.warning("journal apply_to_intent 실패: %s", e)
        return False


def rewrite_prompt(slug: str, section: str = "Discussion") -> str:
    """저널 strength에 맞춰 특정 섹션 재작성을 LLM에 요청할 prompt."""
    jt = get_journal_targeting(slug)
    if jt is None:
        return f"Unknown journal slug: {slug}"
    strengths_md = "\n".join(f"- {s}" for s in jt.strengths_to_emphasize)
    avoid_md = "\n".join(f"- {a}" for a in jt.avoid) if jt.avoid else "(없음)"
    return (
        f"섹션 '{section}'을 {jt.full_name} 저널의 reviewer에 맞춰 다시 써라.\n\n"
        f"이 저널이 가장 보고 싶어하는 strength:\n{strengths_md}\n\n"
        f"피해야 할 양식:\n{avoid_md}\n\n"
        f"Angle (한 줄): {jt.angle}\n"
        f"가정 독자: {jt.reader_assumption}\n"
        f"권장 톤: {jt.voice_tone}\n\n"
        f"기존 본문의 핵심 finding은 유지하되, 위 strength를 의미 단위로 본문에 살려라. "
        f"단순 키워드 나열 X — Discussion 첫 단락의 첫 문장이 angle을 강하게 드러내야 한다."
    )


__all__ = [
    "JournalTargeting", "JOURNALS",
    "list_journals", "get_journal_targeting",
    "apply_to_intent", "rewrite_prompt",
]
