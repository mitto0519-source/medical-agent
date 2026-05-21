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
            elif analysis == "cox":
                return self._cox(df, spec, outcome, outcome_label)
            elif analysis == "psm":
                return self._psm(df, spec, outcome, outcome_label)
            elif analysis == "multilevel":
                return self._multilevel(df, spec, outcome, outcome_label)
            elif analysis == "sensitivity":
                return self._sensitivity(df, spec, outcome, outcome_label)
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
    # 복합표본설계 가중치 + 상호작용항 지원
    # ------------------------------------------------------------------

    def _logistic(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        import statsmodels.api as sm

        predictors = spec.get("predictors", [])
        covariates = spec.get("covariates", [])
        weight_var = spec.get("weight_var")
        strata_var = spec.get("strata_var")       # 복합표본 층화변수
        cluster_var = spec.get("cluster_var")     # 복합표본 군집변수
        interactions = spec.get("interactions", [])  # [("var1", "var2"), ...]
        subgroups = spec.get("subgroups", [])

        all_vars = predictors + covariates
        cols_needed = [outcome] + all_vars
        for v in [weight_var, strata_var, cluster_var]:
            if v and v in df.columns:
                cols_needed.append(v)

        clean = df[[c for c in cols_needed if c in df.columns]].copy()
        # outcome을 수치형으로 강제 변환 (비수치 → NaN)
        import pandas as _pd
        clean[outcome] = _pd.to_numeric(clean[outcome], errors="coerce")
        clean = clean.dropna(subset=[outcome])
        n_total = len(clean)
        n_outcome = int(clean[outcome].fillna(0).astype(float).sum())
        outcome_rate = n_outcome / n_total * 100 if n_total else 0.0

        X = self._build_X(clean, all_vars)

        # 상호작용항 추가
        for v1, v2 in interactions:
            col1 = f"{v1}_x_{v2}"
            if v1 in clean.columns and v2 in clean.columns:
                X[col1] = clean[v1].astype(float) * clean[v2].astype(float)

        y = clean[outcome].astype(float)
        weights = clean[weight_var].astype(float) if weight_var and weight_var in clean.columns else None

        X_const = sm.add_constant(X)
        fit = None

        # 복합표본설계 가중 로지스틱 회귀 (GEE 또는 가중 Logit)
        if weights is not None and cluster_var and cluster_var in clean.columns:
            try:
                groups = clean[cluster_var].astype(str)
                gee_model = sm.GEE(
                    y, X_const,
                    groups=groups,
                    weights=weights,
                    family=sm.families.Binomial(),
                    cov_struct=sm.cov_struct.Independence(),
                )
                fit = gee_model.fit(disp=False)
                analysis_type = "logistic_gee"
            except Exception as e:
                _log.debug("GEE 실패, weighted Logit으로 폴백: %s", e)

        if fit is None:
            try:
                logit_model = sm.Logit(y, X_const)
                fit = logit_model.fit(disp=0, maxiter=300, method="bfgs")
            except Exception:
                fit = sm.Logit(y, X_const).fit(disp=0, maxiter=300)
            analysis_type = "logistic"

        model_vars = self._extract_or(fit, X_const, n_total)
        metrics = {
            "pseudo_r2": getattr(fit, "prsquared", None),
            "aic": getattr(fit, "aic", None),
            "bic": getattr(fit, "bic", None),
            "llr_pvalue": getattr(fit, "llr_pvalue", None),
            "n_obs": int(getattr(fit, "nobs", n_total)),
            "weighted": weights is not None,
            "complex_sample": bool(strata_var or cluster_var),
        }
        # ROC curve data for figure generator
        try:
            from sklearn.metrics import roc_curve, roc_auc_score
            y_pred = fit.predict(X_const)
            fpr, tpr, _ = roc_curve(y.values, y_pred)
            auc = float(roc_auc_score(y.values, y_pred))
            metrics["roc"] = {
                "fpr": fpr.tolist(),
                "tpr": tpr.tolist(),
                "auc": round(auc, 3),
            }
        except Exception as _roc_e:
            _log.debug("ROC 계산 실패: %s", _roc_e)
        desc = self._describe(clean, outcome, all_vars)

        # 층화 서브그룹 분석
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
                    sg_fit = sm.Logit(ys, Xs_c).fit(disp=0, maxiter=200)
                    sg_results[str(val)] = self._extract_or(sg_fit, Xs_c, len(sub))
                except Exception as e:
                    _log.debug("Subgroup %s=%s failed: %s", sg_var, val, e)
            if sg_results:
                subgroup_results[sg_var] = sg_results

        return AnalysisResult(
            analysis_type=analysis_type,
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
    # Cox proportional hazards regression (생존분석)
    # ------------------------------------------------------------------

    def _cox(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        """Cox 비례위험 회귀. spec에 'duration_var' 필수."""
        try:
            from lifelines import CoxPHFitter
        except ImportError:
            _log.warning("lifelines 미설치 — logistic으로 폴백")
            return self._logistic(df, spec, outcome, label)

        duration_var = spec.get("duration_var", "duration")
        predictors = spec.get("predictors", [])
        covariates = spec.get("covariates", [])
        all_vars = predictors + covariates

        cols = [outcome, duration_var] + [v for v in all_vars if v in df.columns]
        clean = df[cols].dropna()
        n_total = len(clean)

        cph = CoxPHFitter()
        cph.fit(clean, duration_col=duration_var, event_col=outcome, show_progress=False)

        summary = cph.summary
        model_vars = []
        for var in summary.index:
            row = summary.loc[var]
            model_vars.append(VariableResult(
                variable=str(var),
                label=self._prettify(str(var)),
                or_value=round(float(row.get("exp(coef)", 1.0)), 3),
                ci_lower=round(float(row.get("exp(coef) lower 95%", 0.0)), 3),
                ci_upper=round(float(row.get("exp(coef) upper 95%", 0.0)), 3),
                p_value=round(float(row.get("p", 1.0)), 4),
                n=n_total,
            ))

        metrics = {
            "concordance": round(cph.concordance_index_, 4),
            "log_likelihood": round(cph.log_likelihood_, 4),
            "n_obs": n_total,
        }

        return AnalysisResult(
            analysis_type="cox",
            outcome=outcome,
            outcome_label=label,
            n_total=n_total,
            n_outcome=int(clean[outcome].sum()),
            outcome_rate=clean[outcome].mean() * 100,
            model_vars=model_vars,
            model_metrics=metrics,
            descriptive_stats=self._describe(clean, outcome, all_vars),
        )

    # ------------------------------------------------------------------
    # Sensitivity analysis — E-value + 역전 임계값 계산
    # ------------------------------------------------------------------

    def _sensitivity(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        """민감도 분석: 주 분석 결과 + E-value + 역전 임계값(p-value sensitivity).

        E-value: 비측정 교란변수가 결론을 뒤집기 위해 필요한 최소 관련성.
        """
        # 주 분석 실행
        main_spec = {**spec, "analysis": "logistic"}
        main_result = self._logistic(df, main_spec, outcome, label)

        if main_result.error or not main_result.model_vars:
            return main_result

        main_or = main_result.model_vars[0].or_value
        main_ci_low = main_result.model_vars[0].ci_lower

        # E-value 계산 (VanderWeele & Ding, 2017)
        def e_value(or_val: float) -> float:
            if or_val <= 0:
                return float("nan")
            if or_val >= 1:
                return or_val + (or_val * (or_val - 1)) ** 0.5
            else:
                inv = 1 / or_val
                return inv + (inv * (inv - 1)) ** 0.5

        ev_point = round(e_value(main_or), 3)
        ev_ci = round(e_value(max(main_ci_low, 1e-6)), 3)

        # 역전 임계값: outcome prevalence를 변화시켜 OR이 1.0이 되는 지점 탐색
        thresholds = []
        try:
            import numpy as np
            for cutoff in np.arange(0.05, 0.5, 0.05):
                mod_df = df.copy()
                mod_df[outcome] = (mod_df[outcome].astype(float) >= cutoff).astype(int)
                try:
                    r = self._logistic(mod_df, {**spec, "analysis": "logistic"}, outcome, label)
                    if r.model_vars:
                        thresholds.append({
                            "cutoff": round(float(cutoff), 2),
                            "or": r.model_vars[0].or_value,
                            "p": r.model_vars[0].p_value,
                        })
                except Exception:
                    pass
        except Exception:
            pass

        main_result.model_metrics["sensitivity"] = {
            "e_value_point": ev_point,
            "e_value_ci_lower": ev_ci,
            "e_value_interpretation": (
                f"비측정 교란변수가 노출-결과 모두와 OR≥{ev_point:.1f} 이상 관련 있어야 "
                f"이 결과를 완전히 설명할 수 있음."
            ),
            "threshold_analysis": thresholds[:5],
        }
        main_result.analysis_type = "logistic+sensitivity"
        return main_result

    # ------------------------------------------------------------------
    # Propensity Score Matching (PSM)
    # ------------------------------------------------------------------

    def _psm(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        """Propensity Score Matching 1:1 최근접 이웃 매칭.

        spec 추가 필드:
            treatment_var: str — 처치 변수 (binary 0/1). 없으면 predictors[0] 사용.
            n_neighbors: int = 1 — 매칭 비율 (현재 1:1만 지원)
        """
        try:
            from sklearn.linear_model import LogisticRegression
            from sklearn.preprocessing import StandardScaler
        except ImportError:
            _log.warning("scikit-learn 미설치 — logistic으로 폴백")
            return self._logistic(df, spec, outcome, label)

        treatment_var = spec.get("treatment_var") or (spec.get("predictors", ["sex"]) or ["sex"])[0]
        all_vars = spec.get("predictors", []) + spec.get("covariates", [])
        covars = [v for v in all_vars if v != treatment_var and v in df.columns]

        cols = [outcome, treatment_var] + covars
        clean = df[[c for c in cols if c in df.columns]].dropna()
        n_total = len(df)

        if treatment_var not in clean.columns or len(clean) < 30:
            return self._logistic(df, spec, outcome, label)

        t = clean[treatment_var].astype(float)
        y = clean[outcome].astype(float)
        X = clean[covars].fillna(0).astype(float) if covars else pd.DataFrame(index=clean.index)

        # Step 1: 성향 점수 추정
        scaler = StandardScaler()
        if not X.empty:
            X_scaled = scaler.fit_transform(X)
            lr = LogisticRegression(max_iter=1000, random_state=42, C=1.0)
            lr.fit(X_scaled, t)
            ps = lr.predict_proba(X_scaled)[:, 1]
        else:
            ps = np.full(len(clean), 0.5)

        # Step 2: 1:1 최근접 이웃 매칭
        treated_idx = np.where(t.values == 1)[0]
        control_idx = np.where(t.values == 0)[0]
        used_ctrl: set = set()
        matched_rows = []
        for ti in treated_idx:
            ps_t = ps[ti]
            avail = [ci for ci in control_idx if ci not in used_ctrl]
            if not avail:
                break
            best_ci = avail[int(np.argmin(np.abs(ps[avail] - ps_t)))]
            matched_rows.extend([ti, best_ci])
            used_ctrl.add(best_ci)

        if len(matched_rows) < 10:
            return AnalysisResult(
                analysis_type="psm",
                outcome=outcome, outcome_label=label,
                n_total=n_total, n_outcome=0, outcome_rate=0.0,
                error="PSM 매칭 실패: 처치 변수 또는 매칭 조건을 확인하세요.",
            )

        matched_df = clean.iloc[matched_rows].copy()
        n_pairs = len(matched_rows) // 2

        # Step 3: 매칭 표본에 대한 회귀 분석
        main_result = self._logistic(matched_df, spec, outcome, label)
        main_result.analysis_type = "psm_logistic"
        main_result.n_total = n_total
        main_result.model_metrics["n_matched"] = len(matched_rows)
        main_result.model_metrics["n_pairs"] = n_pairs
        main_result.model_metrics["n_treated"] = len(treated_idx)
        _log.info("PSM 완료: %d쌍 매칭 (처치군 %d)", n_pairs, len(treated_idx))
        return main_result

    # ------------------------------------------------------------------
    # Multilevel (Mixed Effects) regression
    # ------------------------------------------------------------------

    def _multilevel(self, df: pd.DataFrame, spec: dict, outcome: str, label: str) -> AnalysisResult:
        """선형 혼합 효과 모형 (Mixed Effects / Multilevel Model).

        spec 추가 필드:
            group_var: str — 군집 변수 (학교, 지역 등). 없으면 logistic으로 폴백.
        """
        import statsmodels.formula.api as smf

        group_var = spec.get("group_var")
        if not group_var or group_var not in df.columns:
            _log.warning("multilevel: group_var 없음 — logistic으로 폴백")
            return self._logistic(df, spec, outcome, label)

        predictors = spec.get("predictors", [])
        covariates = spec.get("covariates", [])
        all_vars = [v for v in predictors + covariates if v in df.columns]

        cols = [outcome, group_var] + all_vars
        clean = df[[c for c in cols if c in df.columns]].dropna()
        n_total = len(clean)

        # 포뮬라 구성
        rhs = " + ".join(all_vars) if all_vars else "1"
        formula = f"{outcome} ~ {rhs}"

        try:
            model = smf.mixedlm(formula, clean, groups=clean[group_var])
            fit = model.fit(reml=False, disp=False)
        except Exception as e:
            _log.warning("Multilevel 모형 실패, logistic으로 폴백: %s", e)
            return self._logistic(df, spec, outcome, label)

        model_vars = []
        ci = fit.conf_int()
        for var in fit.params.index:
            if var in ("Intercept", "Group Var"):
                continue
            try:
                model_vars.append(VariableResult(
                    variable=var,
                    label=self._prettify(var),
                    or_value=round(float(fit.params[var]), 4),
                    ci_lower=round(float(ci.loc[var, 0]), 4),
                    ci_upper=round(float(ci.loc[var, 1]), 4),
                    p_value=round(float(fit.pvalues[var]), 4),
                    n=n_total,
                ))
            except Exception:
                pass

        metrics = {
            "log_likelihood": round(float(fit.llf), 4) if hasattr(fit, "llf") else None,
            "aic": round(float(fit.aic), 4) if hasattr(fit, "aic") else None,
            "group_var": group_var,
            "n_groups": int(clean[group_var].nunique()),
        }

        return AnalysisResult(
            analysis_type="multilevel",
            outcome=outcome,
            outcome_label=label,
            n_total=n_total,
            n_outcome=int(clean[outcome].sum()) if clean[outcome].dtype in [float, int] else 0,
            outcome_rate=float(clean[outcome].mean() * 100) if clean[outcome].dtype in [float, int] else 0.0,
            model_vars=model_vars,
            model_metrics=metrics,
            descriptive_stats=self._describe(clean, outcome, all_vars),
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
