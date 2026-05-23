"""Design Template — 연구 설계 패턴 지식 자산.

실제 논문의 방법론 로직·통계 구성·Table/Figure 구조·공변량 분류 원리를
재사용 가능한 템플릿으로 자산화한다. (methods_library = 개별 통계, 이건 상위 설계 패턴)

paper_writer/methods가 방법론·결과·구조를 쓸 때 build_context()로 이 패턴을 주입해
"논문 구조의 라인"(조유선식 단면연구 흐름)을 일관되게 따른다.

저장: data/libraries/design_templates/{slug}.json
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DIR = Path("data/libraries/design_templates")


class DesignTemplate:
    """연구 설계 패턴 저장소."""

    def __init__(self, template_dir: str | Path = _DIR):
        self._dir = Path(template_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def save(self, slug: str, template: Dict) -> None:
        (self._dir / f"{slug}.json").write_text(
            json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        _log.info("설계 템플릿 저장: %s", slug)

    def get(self, slug: str) -> Optional[Dict]:
        p = self._dir / f"{slug}.json"
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None

    def list_templates(self) -> List[Dict]:
        out = []
        for f in sorted(self._dir.glob("*.json")):
            try:
                t = json.loads(f.read_text(encoding="utf-8"))
                out.append({"slug": f.stem, "name": t.get("name", f.stem),
                            "design": t.get("design", "")})
            except Exception:
                continue
        return out

    def build_context(self, slug: str) -> str:
        """LLM 프롬프트 주입용 — 방법론·Table·Figure 구조 가이드 텍스트."""
        t = self.get(slug)
        if not t:
            return ""
        lines = [f"[설계 템플릿: {t.get('name', slug)}] — 이 논문 구조의 라인을 따르라."]
        if t.get("design"):
            lines.append(f"• 설계: {t['design']}")
        ms = t.get("modeling_strategy")
        if ms:
            lines.append(f"• 모델링 전략: {' → '.join(ms)}")
        cc = t.get("covariate_classification", {})
        if cc:
            lines.append("• 공변량 분류 원리 (핵심):")
            for k, v in cc.items():
                lines.append(f"    - {k}: {v}")
        tb = t.get("tables", {})
        if tb:
            lines.append("• Table 구조:")
            for k, v in tb.items():
                lines.append(f"    - {k}: {v}")
        fg = t.get("figures", {})
        if fg:
            lines.append("• Figure 구조:")
            for k, v in fg.items():
                lines.append(f"    - {k}: {v}")
        if t.get("exclusion_rationale"):
            lines.append("• 성층화 제외 근거: " + "; ".join(
                f"{k}({v})" for k, v in t["exclusion_rationale"].items()))
        if t.get("sample_flow"):
            lines.append(f"• 표본 흐름: {t['sample_flow']}")
        return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────
# 시드: 조유선 KYRBS 단면연구 표준 패턴 (Zero-Calorie Beverage × Depression)
# ──────────────────────────────────────────────────────────────────────

KYRBS_CROSS_SECTIONAL_SEED = {
    "name": "조유선식 KYRBS 단면연구 (용량-반응 + 효과수정 + 서브그룹 일관성)",
    "source_paper": "Zero-Calorie Beverage Consumption and Depressive Symptoms in Korean Adolescents — KYRBS 2025",
    "author": "Yoosun Cho",
    "design": "Cross-sectional, complex survey design (svyset: strata/PSU/weight)",
    "dataset": "KYRBS",
    "exposure_modeling": {
        "continuous": "frequency 1–7 (선형 용량-반응)",
        "categorical": "4-level 범주 + p-trend (범주 중간값을 연속 취급)",
    },
    "outcomes": {
        "primary": "Depressive symptoms (binary)",
        "secondary": ["High perceived stress", "Poor sleep recovery"],
    },
    "modeling_strategy": [
        "Crude (무조정)",
        "M1 (부분 조정: 인구학적)",
        "M2 (완전 조정: 12개 공변량)",
        "p-trend (용량-반응 경향성)",
    ],
    "covariate_classification": {
        "confounders (조정)": "진성 교란변수 — 결과에 직접 영향 (흡연=니코틴, 음주=알코올). 모델에 포함.",
        "effect_modifiers (성층화)": "효과수정자 — 성별은 Table3+상호작용, 나머지(나이/BMI/SES/학업/스마트폰/신체활동/아침결식)는 서브그룹 일관성.",
        "co_exposures (공변량만)": "공노출 — ZCB와 공선성(SSB/카페인). 조정만, 성층화/주노출 아님.",
    },
    "primary_covariate_set": [
        "sex", "age_cat", "bmi_cat", "ses3", "school_n", "academic3",
        "ever_smoker", "ever_drinker", "swd_freq3", "caff_freq3", "pa_cat", "br_skip",
    ],
    "tables": {
        "Table 2": "전체 분석 (Crude/M1/M2 OR+95%CI + p-trend)",
        "Table 3": "성별 성층화 + 상호작용항 (핵심 효과수정자)",
        "Supp Table 1": "이차 결과 (high stress, poor sleep)",
    },
    "figures": {
        "Figure 2": "예측확률 marginsplot (2A 전체 + 2B 성별 성층화)",
        "Figure 3": "서브그룹 일관성 forest plot (7개 성층화자, 성별 제외)",
    },
    "figure3_stratifiers": [
        "Age category (발달단계)", "BMI category (체성분/다이어트 문화)",
        "Household SES (건강형평성)", "Academic performance (심리사회 스트레스)",
        "Smartphone use (생활습관 형제노출)", "Physical activity (생활습관)",
        "Breakfast skip (식이패턴 지표)",
    ],
    "exclusion_rationale": {
        "Sex": "Table3+Figure2B에서 다룸 (효과수정자, 일관성 아님)",
        "Ever smoker/drinker": "진성 교란변수 (기분에 직접 효과)",
        "SSB/Caffeine": "공노출 (ZCB와 공선성, 공변량만)",
    },
    "sample_flow": "Raw N=54,170 → 3,198 제외 → 최종 분석표본 N=50,972",
    "structure_principles": [
        "용량-반응을 연속+범주(p-trend) 양쪽으로 제시해 견고성 확보",
        "공변량을 '교란/효과수정/공노출' 3분류해 각각 다르게 처리 (조정 vs 성층화 vs 공변량)",
        "효과수정자(성별)는 상호작용으로 입증, 나머지는 서브그룹 일관성으로 견고성 입증",
        "marginsplot으로 예측확률 시각화 → 임상적 해석 용이",
        "forest plot 서브그룹 일관성 → 결과의 일반화가능성 입증",
    ],
}


def seed_default_templates() -> None:
    """기본 설계 템플릿 시드 (조유선 KYRBS 단면연구)."""
    dt = DesignTemplate()
    if not dt.get("kyrbs_cross_sectional"):
        dt.save("kyrbs_cross_sectional", KYRBS_CROSS_SECTIONAL_SEED)
        _log.info("KYRBS 단면연구 설계 템플릿 시드 완료")
