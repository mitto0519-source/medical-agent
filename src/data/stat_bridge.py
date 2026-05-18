"""Statistical analysis bridge: DataFrame → paper-ready OR/HR/RR/CI results.

Takes a survey DataFrame (from SurveyLoader) + study specification and runs
real statistical analysis using statsmodels, returning structured results that
paper_writer.py can inject directly into manuscript sections.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd

from src.config.logging_config import get_logger

_log = get_logger(__name__)

warnings.filterwarnings("ignore", category=FutureWarning)


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class VariableResult:
    variable: str
    label: str
    or_value: float
    ci_lower: float
    ci_upper: float
    p_value: float
    n: int
    ref_category: str | None = None
    significant: bool = False

    def __post_init__(self):
        self.significant = self.p_value < 0.05

    def format_or(self) -> str:
        return f"{self.or_value:.2f} (95% CI {self.ci_lower:.2f}–{self.ci_upper:.2f})"

    def format_p(self) -> str:
        if self.p_value < 0.001:
            return "p<0.001"
        return f"p={self.p_value:.3f}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["or_formatted"] = self.format_or()
        d["p_formatted"] = self.format_p()
        return d


@dataclass
class AnalysisResult:
    analysis_type: str          # "logistic", "cox", "linear", "chi2"
    outcome: str
    outcome_label: str
    n_total: int
    n_outcome: int
    outcome_rate: float
    model_vars: list[VariableResult] = field(default_factory=list)
    model_metrics: dict[str, Any] = field(default_factory=dict)
    descriptive_stats: dict[str, Any] = field(default_factory=dict)
    subgroup_results: dict[str, list[VariableResult]] = field(default_factory=dict)
    error: str | None = None

    def get_significant(self) -> list[VariableResult]:
        return [v for v in self.model_vars if v.significant]

    def to_paper_summary(self) -> str:
        """Returns a compact Korean-language statistical summary for paper_writer."""
        lines = []
        n_sig = len(self.get_significant())
        lines.append(
            f"총 {self.n_total:,}명 중 {self.outcome_label} 경험자 {self.n_outcome:,}명 "
            f"({self.outcome_rate:.1f}%)이었다."
        )
        for v in self.model_vars:
            if v.significant:
                lines.append(
                    f"{v.label}는 {self.outcome_label}과 유의한 관련이 있었다 "
                    f"(adjusted OR={v.format_or()}, {v.format_p()})."
                )
        if not lines[1:]:
            lines.append("통계적으로 유의한 독립 변수는 확인되지 않았다.")
        return " ".join(lines)

    def to_dict(self) -> dict:
        return {
            "analysis_type": self.analysis_type,
            "outcome": self.outcome,
            "outcome_label": self.outcome_label,
            "n_total": self.n_total,
            "n_outcome": self.n_outcome,
            "outcome_rate": self.outcome_rate,
            "model_vars": [v.to_dict() for v in self.model_vars],
            "model_metrics": self.model_metrics,
            "descriptive_stats": self.descriptive_stats,
            "paper_summary": self.to_paper_summary(),
            "error": self.error,
        }


# ---------------------------------------------------------------------------
# Main bridge
# ---------------------------------------------------------------------------

class StatBridge:
    """Runs real statistical analysis on survey DataFrames.

    Usage:
        bridge = StatBridge()
        result = bridge.run(df, spec)

    spec example:
        {
            "outcome": "depression",
            "outcome_label": "우울감 경험",
            "predictors": ["sex", "sleep_hours", "screen_time", "smoking"],
            "covariates": ["grade", "family_econ"],
            "analysis": "logistic",        # logistic | linear | chi2
            "weight_var": "weight_var",    # complex sampling weight
            "subgroups": ["sex"],          # optional subgroup analysis
        }
    """

    def run(self, df: pd.DataFrame, spec: dict) -> AnalysisResult:
        analysis = spec.get("analysis", "logistic")
        outcome = spec["outcome"]
        outcome_label = spec.get("outcome_label", outcome)

        try:
            if analysis == "logistic":
                return self._logistic(df, spec, outcome, outcome_label)
            elif analysis == "linear":
                return self._linear(df, spec, outcome, outcome_label)
            elif analysis == "chi2":
                return self._chi2(df, spec, outcome, outcome_label)
            else:
                return self._logistic(df, spec, outcome, outcome_label)
        except Exception as e:
            _log.error("StatBridge.run failed: %s", e, exc_info=True)
            return AnalysisResult(
                analysis_type=analysis,
                outcome=outcome,
                outcome_label=outcome_label,
                n_total=len(df),
                n_outcome=0,
                outcome_rate=0.0,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Logistic regression (binary outcome → OR + 95%CI)
    # ------------------------------------------------------------------

    def _logistic(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        import statsmodels.api as sm

        predictors = spec.get("predictors", [])
        covariates = spec.get("covariates", [])
        weight_var = spec.get("weight_var")
        subgroups = spec.get("subgroups", [])

        all_vars = predictors + covariates
        cols_needed = [outcome] + all_vars
        if weight_var and weight_var in df.columns:
            cols_needed.append(weight_var)

        clean = df[cols_needed].dropna()
        n_total = len(clean)
        n_outcome = int(clean[outcome].sum())
        outcome_rate = n_outcome / n_total * 100 if n_total else 0.0

        # Build design matrix
        X = self._build_X(clean, all_vars)
        y = clean[outcome].astype(float)
        weights = clean[weight_var].astype(float) if weight_var and weight_var in clean.columns else None

        X_const = sm.add_constant(X)

        if weights is not None:
            model = sm.WLS(y, X_const, weights=weights)
            # For binary with weights, use MNLogit approximation via Logit
            try:
                logit_model = sm.Logit(y, X_const)
                fit = logit_model.fit(disp=0, maxiter=200)
            except Exception:
                fit = model.fit(disp=0)
                return self._build_result_linear(fit, X_const, clean, spec, outcome, label, n_total, n_outcome, outcome_rate)
        else:
            logit_model = sm.Logit(y, X_const)
            fit = logit_model.fit(disp=0, maxiter=200)

        model_vars = self._extract_or(fit, X_const, n_total)
        metrics = {
            "pseudo_r2": getattr(fit, "prsquared", None),
            "aic": fit.aic,
            "bic": fit.bic,
            "llr_pvalue": getattr(fit, "llr_pvalue", None),
            "n_obs": int(fit.nobs),
        }
        desc = self._describe(clean, outcome, all_vars)

        # Subgroup analysis
        subgroup_results = {}
        for sg_var in subgroups:
            if sg_var not in clean.columns:
                continue
            sg_results = {}
            for val in sorted(clean[sg_var].unique()):
                sub = clean[clean[sg_var] == val]
                if len(sub) < 30:
                    continue
                try:
                    Xs = self._build_X(sub, [v for v in all_vars if v != sg_var])
                    Xs_c = sm.add_constant(Xs)
                    ys = sub[outcome].astype(float)
                    sg_fit = sm.Logit(ys, Xs_c).fit(disp=0, maxiter=100)
                    sg_results[str(val)] = self._extract_or(sg_fit, Xs_c, len(sub))
                except Exception as e:
                    _log.debug("Subgroup %s=%s failed: %s", sg_var, val, e)
            if sg_results:
                subgroup_results[sg_var] = sg_results

        return AnalysisResult(
            analysis_type="logistic",
            outcome=outcome,
            outcome_label=label,
            n_total=n_total,
            n_outcome=n_outcome,
            outcome_rate=outcome_rate,
            model_vars=model_vars,
            model_metrics=metrics,
            descriptive_stats=desc,
            subgroup_results=subgroup_results,
        )

    # ------------------------------------------------------------------
    # Linear regression (continuous outcome)
    # ------------------------------------------------------------------

    def _linear(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        import statsmodels.api as sm

        predictors = spec.get("predictors", [])
        covariates = spec.get("covariates", [])
        all_vars = predictors + covariates

        clean = df[[outcome] + all_vars].dropna()
        n_total = len(clean)

        X = self._build_X(clean, all_vars)
        X_const = sm.add_constant(X)
        y = clean[outcome].astype(float)

        fit = sm.OLS(y, X_const).fit()

        model_vars = []
        ci = fit.conf_int()
        for col in X_const.columns:
            if col == "const":
                continue
            model_vars.append(VariableResult(
                variable=col,
                label=self._prettify(col),
                or_value=round(float(fit.params[col]), 4),
                ci_lower=round(float(ci.loc[col, 0]), 4),
                ci_upper=round(float(ci.loc[col, 1]), 4),
                p_value=float(fit.pvalues[col]),
                n=n_total,
            ))

        metrics = {
            "r_squared": fit.rsquared,
            "adj_r_squared": fit.rsquared_adj,
            "f_pvalue": fit.f_pvalue,
            "aic": fit.aic,
        }

        return AnalysisResult(
            analysis_type="linear",
            outcome=outcome,
            outcome_label=label,
            n_total=n_total,
            n_outcome=n_total,
            outcome_rate=float(y.mean()),
            model_vars=model_vars,
            model_metrics=metrics,
            descriptive_stats=self._describe(clean, outcome, all_vars),
        )

    # ------------------------------------------------------------------
    # Chi-squared test (categorical association)
    # ------------------------------------------------------------------

    def _chi2(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        from scipy.stats import chi2_contingency

        predictors = spec.get("predictors", [])
        clean = df[[outcome] + predictors].dropna()
        n_total = len(clean)
        n_outcome = int(clean[outcome].sum()) if clean[outcome].dtype in [float, int] else 0

        model_vars = []
        for pred in predictors:
            ct = pd.crosstab(clean[pred], clean[outcome])
            chi2, p, dof, _ = chi2_contingency(ct)
            # Cramér's V as effect size
            n = ct.values.sum()
            cramers_v = np.sqrt(chi2 / (n * (min(ct.shape) - 1)))
            model_vars.append(VariableResult(
                variable=pred,
                label=self._prettify(pred),
                or_value=round(cramers_v, 4),
                ci_lower=0.0,
                ci_upper=0.0,
                p_value=float(p),
                n=n_total,
            ))

        return AnalysisResult(
            analysis_type="chi2",
            outcome=outcome,
            outcome_label=label,
            n_total=n_total,
            n_outcome=n_outcome,
            outcome_rate=n_outcome / n_total * 100 if n_total else 0.0,
            model_vars=model_vars,
            descriptive_stats=self._describe(clean, outcome, predictors),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_X(self, df: pd.DataFrame, vars: list[str]) -> pd.DataFrame:
        """One-hot encode categoricals, keep numerics as-is."""
        parts = []
        for v in vars:
            if v not in df.columns:
                continue
            col = df[v]
            if col.dtype == object or col.nunique() <= 6:
                dummies = pd.get_dummies(col, prefix=v, drop_first=True)
                parts.append(dummies)
            else:
                parts.append(col.to_frame())
        if not parts:
            return pd.DataFrame(index=df.index)
        return pd.concat(parts, axis=1).astype(float)

    def _extract_or(self, fit, X_const: pd.DataFrame, n: int) -> list[VariableResult]:
        """Extract OR + 95%CI from logistic fit."""
        results = []
        try:
            ci = fit.conf_int()
            for col in X_const.columns:
                if col == "const":
                    continue
                results.append(VariableResult(
                    variable=col,
                    label=self._prettify(col),
                    or_value=round(float(np.exp(fit.params[col])), 3),
                    ci_lower=round(float(np.exp(ci.loc[col, 0])), 3),
                    ci_upper=round(float(np.exp(ci.loc[col, 1])), 3),
                    p_value=round(float(fit.pvalues[col]), 4),
                    n=n,
                ))
        except Exception as e:
            _log.warning("_extract_or error: %s", e)
        return results

    def _build_result_linear(self, fit, X_const, clean, spec, outcome, label, n_total, n_outcome, rate) -> AnalysisResult:
        ci = fit.conf_int()
        model_vars = []
        for col in X_const.columns:
            if col == "const":
                continue
            model_vars.append(VariableResult(
                variable=col,
                label=self._prettify(col),
                or_value=round(float(fit.params[col]), 4),
                ci_lower=round(float(ci.loc[col, 0]), 4),
                ci_upper=round(float(ci.loc[col, 1]), 4),
                p_value=float(fit.pvalues[col]),
                n=n_total,
            ))
        return AnalysisResult(
            analysis_type="logistic_weighted",
            outcome=outcome,
            outcome_label=label,
            n_total=n_total,
            n_outcome=n_outcome,
            outcome_rate=rate,
            model_vars=model_vars,
            model_metrics={"r_squared": fit.rsquared, "aic": fit.aic},
        )

    def _describe(self, df: pd.DataFrame, outcome: str, vars: list[str]) -> dict:
        stats = {}
        for col in [outcome] + vars:
            if col not in df.columns:
                continue
            s = df[col]
            if s.dtype in [float, int, np.float64, np.int64]:
                stats[col] = {
                    "mean": round(float(s.mean()), 3),
                    "std": round(float(s.std()), 3),
                    "median": round(float(s.median()), 3),
                    "min": float(s.min()),
                    "max": float(s.max()),
                }
            else:
                vc = s.value_counts(normalize=True)
                stats[col] = {"categories": vc.head(5).round(3).to_dict()}
        return stats

    @staticmethod
    def _prettify(col_name: str) -> str:
        """Convert dummy variable names to human-readable labels."""
        label_map = {
            "sex": "성별(여성)",
            "sex_2": "성별(여성)",
            "sleep_hours": "수면 시간",
            "screen_time": "화면 노출 시간",
            "smoking": "흡연",
            "smoking_1": "흡연",
            "alcohol": "음주",
            "alcohol_1": "음주",
            "physical_act": "신체 활동",
            "grade": "학년",
            "family_econ": "가정 경제 수준",
            "bmi": "체질량지수",
            "stress": "스트레스",
            "depression": "우울감",
            "loneliness": "외로움",
            "academic_perf": "학업 성취도",
            "breakfast": "아침 식사",
            "age": "연령",
            "edu": "교육 수준",
            "income": "소득 수준",
            "diabetes": "당뇨",
            "hypertension": "고혈압",
            "metabolic_syn": "대사 증후군",
            "sbp": "수축기 혈압",
            "dbp": "이완기 혈압",
            "glucose": "공복 혈당",
            "hba1c": "당화혈색소",
            "total_chol": "총 콜레스테롤",
            "hdl": "HDL 콜레스테롤",
            "ldl": "LDL 콜레스테롤",
            "trigly": "중성지방",
        }
        return label_map.get(col_name, col_name.replace("_", " ").title())


# ---------------------------------------------------------------------------
# Convenience function
# ---------------------------------------------------------------------------

def run_analysis(df: pd.DataFrame, spec: dict) -> AnalysisResult:
    """Run statistical analysis and return AnalysisResult."""
    return StatBridge().run(df, spec)


def quick_demo() -> AnalysisResult:
    """Run a quick demo with synthetic KYRBS data."""
    from src.data.survey_loader import SurveyLoader
    loader = SurveyLoader()
    df = loader.generate_synthetic("KYRBS", n=3000, seed=42)
    spec = {
        "outcome": "depression",
        "outcome_label": "우울감 경험",
        "predictors": ["sex", "sleep_hours", "screen_time", "smoking"],
        "covariates": ["grade", "family_econ"],
        "analysis": "logistic",
        "weight_var": "weight_var",
        "subgroups": ["sex"],
    }
    result = run_analysis(df, spec)
    _log.info("Demo analysis: n=%d, OR results=%d", result.n_total, len(result.model_vars))
    return result
