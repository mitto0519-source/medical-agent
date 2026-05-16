"""Methods Library — 통계 방법론 모듈 라이브러리

연구 설계 + 변수 타입 → 어떤 통계를 써야 하는지
그리고 각 방법론의 가정, 보고 방식, 코드 템플릿을 저장.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional


METHODS_DB = {
    # ── 연속형 결과변수 ──────────────────────────────────────────
    "linear_regression": {
        "use_when": "Continuous outcome, assess association adjusting for covariates",
        "assumptions": ["normality of residuals", "homoscedasticity", "no multicollinearity"],
        "report_as": "β (95% CI), p-value",
        "covariates": "age, sex, BMI, smoking, alcohol, physical activity, comorbidities",
        "code_hint": "statsmodels.formula.api.ols()",
        "subgroup_hint": "interaction term (var × subgroup)",
    },
    # ── 이분형 결과변수 ──────────────────────────────────────────
    "logistic_regression": {
        "use_when": "Binary outcome (yes/no, event/no event)",
        "assumptions": ["linearity in log-odds", "no complete separation"],
        "report_as": "OR (95% CI), p-value",
        "covariates": "age, sex, BMI, smoking, alcohol, physical activity, comorbidities",
        "code_hint": "statsmodels.formula.api.logit()",
        "subgroup_hint": "interaction term (var × subgroup)",
    },
    # ── 생존 분석 ────────────────────────────────────────────────
    "cox_regression": {
        "use_when": "Time-to-event outcome (survival, incidence)",
        "assumptions": ["proportional hazards", "no time-varying covariates (basic)"],
        "report_as": "HR (95% CI), p-value",
        "covariates": "age, sex, BMI, smoking, alcohol, physical activity, comorbidities",
        "code_hint": "lifelines.CoxPHFitter()",
        "subgroup_hint": "stratified Cox or interaction term",
    },
    "kaplan_meier": {
        "use_when": "Visualise survival curves between groups",
        "assumptions": ["independent censoring", "random censoring"],
        "report_as": "log-rank test p-value, median survival time",
        "code_hint": "lifelines.KaplanMeierFitter()",
        "subgroup_hint": "plot separate curves per group",
    },
    # ── 교차 분석 ────────────────────────────────────────────────
    "chi_square": {
        "use_when": "Compare proportions between two or more groups",
        "assumptions": ["expected cell count ≥5"],
        "report_as": "χ² statistic, p-value, proportions (%)",
        "code_hint": "scipy.stats.chi2_contingency()",
        "subgroup_hint": "stratified tables",
    },
    "fisher_exact": {
        "use_when": "Compare proportions when expected cell count <5",
        "assumptions": ["small sample"],
        "report_as": "OR (95% CI), p-value",
        "code_hint": "scipy.stats.fisher_exact()",
    },
    # ── 그룹 간 비교 ─────────────────────────────────────────────
    "t_test": {
        "use_when": "Compare means of continuous variable between 2 groups",
        "assumptions": ["normality (or n≥30)", "equal/unequal variance (Welch)"],
        "report_as": "mean ± SD or median (IQR), p-value",
        "code_hint": "scipy.stats.ttest_ind()",
    },
    "anova": {
        "use_when": "Compare means across 3+ groups",
        "assumptions": ["normality", "homogeneity of variance"],
        "report_as": "F-statistic, p-value, post-hoc test",
        "code_hint": "scipy.stats.f_oneway()",
    },
    "mann_whitney": {
        "use_when": "Non-parametric comparison of 2 groups (skewed continuous data)",
        "assumptions": ["ordinal or continuous data"],
        "report_as": "median (IQR), p-value",
        "code_hint": "scipy.stats.mannwhitneyu()",
    },
    # ── 다중검정 보정 ────────────────────────────────────────────
    "bonferroni": {
        "use_when": "Multiple comparisons correction (conservative)",
        "report_as": "adjusted p-value threshold = α/n",
        "code_hint": "statsmodels.stats.multitest.multipletests(method='bonferroni')",
    },
    "fdr_bh": {
        "use_when": "Multiple comparisons correction (FDR, less conservative)",
        "report_as": "FDR-adjusted p-value (q-value)",
        "code_hint": "statsmodels.stats.multitest.multipletests(method='fdr_bh')",
    },
    # ── 경향성 검정 ──────────────────────────────────────────────
    "trend_test": {
        "use_when": "Test linear trend across ordered categories (quartiles, quintiles)",
        "report_as": "p for trend",
        "code_hint": "treat category midpoint as continuous in regression",
    },
    # ── 매칭/성향점수 ────────────────────────────────────────────
    "propensity_score_matching": {
        "use_when": "Reduce confounding in observational study",
        "report_as": "SMD before/after matching, matched HR/OR",
        "code_hint": "use logistic regression for PS, then match 1:1 or 1:N",
    },
}


class MethodsLibrary:
    """통계 방법론 라이브러리.

    사용법:
        lib = MethodsLibrary()
        method = lib.recommend("binary", "observational_cohort")
        code_template = lib.get_method("logistic_regression")
    """

    def __init__(self, library_dir: str = "data/libraries"):
        self._dir = Path(library_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._custom_path = self._dir / "custom_methods.json"
        self._custom: Dict = self._load_custom()

    def _load_custom(self) -> Dict:
        if self._custom_path.exists():
            try:
                with open(self._custom_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_custom(self):
        with open(self._custom_path, "w", encoding="utf-8") as f:
            json.dump(self._custom, f, ensure_ascii=False, indent=2)

    def get_method(self, method_name: str) -> Optional[Dict]:
        return METHODS_DB.get(method_name) or self._custom.get(method_name)

    def add_custom_method(self, name: str, **kwargs):
        """사용자 정의 방법론 추가."""
        self._custom[name] = kwargs
        self._save_custom()

    def recommend(self, outcome_type: str, study_design: str = "") -> List[Dict]:
        """결과변수 타입과 연구 설계에 맞는 방법론 추천.

        outcome_type: 'continuous', 'binary', 'time_to_event', 'categorical'
        study_design: 'cross_sectional', 'cohort', 'case_control', 'rct'
        """
        mapping = {
            "continuous": ["linear_regression", "t_test", "anova", "mann_whitney"],
            "binary": ["logistic_regression", "chi_square", "fisher_exact"],
            "time_to_event": ["cox_regression", "kaplan_meier"],
            "categorical": ["chi_square", "logistic_regression"],
        }
        names = mapping.get(outcome_type.lower(), [])
        return [
            {"name": n, **METHODS_DB[n]}
            for n in names
            if n in METHODS_DB
        ]

    def get_covariate_template(self, domain: str = "general") -> str:
        """자주 쓰이는 공변량 세트 반환."""
        templates = {
            "general": "age, sex, BMI, smoking status, alcohol consumption, physical activity, income level, education",
            "cardiovascular": "age, sex, BMI, smoking, alcohol, physical activity, hypertension, diabetes, dyslipidemia, family history of CVD",
            "cancer": "age, sex, BMI, smoking, alcohol, physical activity, family history of cancer, comorbidities",
            "metabolic": "age, sex, BMI, smoking, alcohol, physical activity, hypertension, diabetes, dyslipidemia, menopausal status (women)",
            "breast": "age, menopausal status, BMI, smoking, alcohol, physical activity, parity, hormone therapy, family history of breast cancer",
        }
        return templates.get(domain, templates["general"])

    def format_methods_section_template(
        self,
        study_design: str,
        outcome: str,
        main_exposure: str,
        covariates: str,
        software: str = "SAS version 9.4 (SAS Institute)",
    ) -> str:
        """Methods 섹션 뼈대 생성."""
        return f"""Statistical Analysis

All statistical analyses were performed using {software}.
Continuous variables are presented as mean ± standard deviation (SD) or median (interquartile range [IQR])
and categorical variables as frequency (percentage).

The association between {main_exposure} and {outcome} was evaluated using
multivariable-adjusted models. Covariates included {covariates}.

Multivariable models were sequentially adjusted:
  - Model 1: age- and sex-adjusted
  - Model 2: additionally adjusted for [specify covariates]
  - Model 3: fully adjusted model

Trend across categories was assessed by assigning median values to each category
and treating these as a continuous variable (p for trend).

Subgroup analyses were performed to examine whether the association was consistent
across pre-specified subgroups. Interactions were tested using likelihood ratio tests.

Sensitivity analyses were conducted by [specify: excluding prevalent disease,
restricting to complete cases, using alternative cutoffs].

A two-sided p-value of <0.05 was considered statistically significant.
All confidence intervals were calculated at the 95% level.
"""

    def get_context_for_claude(self, methods: List[str]) -> str:
        """Claude 프롬프트 삽입용 방법론 컨텍스트."""
        lines = ["STATISTICAL METHODS TO USE:"]
        for name in methods:
            m = self.get_method(name)
            if m:
                lines.append(f"\n{name.upper()}:")
                lines.append(f"  Use when: {m.get('use_when', '')}")
                lines.append(f"  Report as: {m.get('report_as', '')}")
                if m.get("assumptions"):
                    lines.append(f"  Assumptions: {', '.join(m['assumptions'])}")
        return "\n".join(lines)
