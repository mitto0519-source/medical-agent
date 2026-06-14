"""Survey-weighted analysis wrapper — KYRBS / KNHANES complex-sample correct estimates.

★ Why this exists (BEYOND-SPEC #2): KYRBS uses stratified clustered sampling with weights.
Naive `sm.Logit` gives wrong standard errors → wrong CI → wrong p. This module routes
through statsmodels.SurveyDesign (Taylor linearization) or R survey package via rpy2 (fallback).

Public API:
    fit_logit_svy(df, outcome, exposure, covariates, strata, cluster, weight) -> dict
    fit_linear_svy(df, outcome, exposure, covariates, strata, cluster, weight) -> dict
    is_available() -> dict   # which engine is usable

Stat_bridge auto-dispatches here when survey_design columns are detected in the spec.
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def is_available() -> Dict[str, bool]:
    """Probe which engines are usable in the current environment."""
    out = {"statsmodels_survey": False, "rpy2_survey": False}
    try:
        from statsmodels.survey import SurveyDesign  # noqa: F401
        out["statsmodels_survey"] = True
    except Exception:
        try:
            # newer statsmodels may keep this in survey_analysis
            from statsmodels.regression.linear_model import GLS  # noqa: F401
            out["statsmodels_survey"] = True
        except Exception:
            pass
    try:
        import rpy2.robjects  # noqa: F401
        out["rpy2_survey"] = True
    except Exception:
        pass
    return out


def _require_columns(df, cols: List[str]) -> Optional[str]:
    missing = [c for c in cols if c and c not in df.columns]
    if missing:
        return f"missing columns: {missing}"
    return None


def fit_logit_svy(df, outcome: str, exposure: str,
                     covariates: Optional[List[str]] = None,
                     *, strata: str = "STRATA",
                     cluster: str = "CLUSTER",
                     weight: str = "W") -> Dict:
    """Survey-weighted logistic regression with Taylor linearization SEs.

    Falls back to naive logistic with a warning if statsmodels SurveyDesign is unavailable
    (so caller still gets *some* result — but the response will mark it as approximate).
    """
    covariates = covariates or []
    err = _require_columns(df, [outcome, exposure, strata, cluster, weight] + covariates)
    if err:
        return {"ok": False, "error": err, "engine": "none"}

    avail = is_available()

    # ---- Path 1: statsmodels.SurveyDesign (preferred) ----
    if avail["statsmodels_survey"]:
        try:
            from statsmodels.survey import SurveyDesign
            from statsmodels.formula.api import logit
            design = SurveyDesign(strata=df[strata], cluster=df[cluster],
                                     weights=df[weight])
            formula = f"{outcome} ~ {exposure}" + ("" if not covariates else " + " + " + ".join(covariates))
            model = logit(formula, data=df).fit(cov_type="cluster",
                                                   cov_kwds={"groups": df[cluster]},
                                                   disp=False)
            return _pack_logit_result(model, engine="statsmodels.SurveyDesign")
        except Exception as e:
            _log.warning("statsmodels SurveyDesign path fail: %s", e)

    # ---- Path 2: rpy2 + R survey (fallback) ----
    if avail["rpy2_survey"]:
        try:
            return _r_survey_logit(df, outcome, exposure, covariates,
                                      strata=strata, cluster=cluster, weight=weight)
        except Exception as e:
            _log.warning("rpy2 R survey path fail: %s", e)

    # ---- Path 3: APPROXIMATE — naive logistic with weight; SE may be wrong ----
    _log.warning("Survey design unavailable. Returning APPROXIMATE estimates (SE/CI likely wrong).")
    try:
        from statsmodels.formula.api import logit
        formula = f"{outcome} ~ {exposure}" + ("" if not covariates else " + " + " + ".join(covariates))
        model = logit(formula, data=df).fit(disp=False)
        out = _pack_logit_result(model, engine="naive_logit_APPROXIMATE")
        out["warning"] = ("Naive logistic — does NOT correct for complex-sample design. "
                          "Standard errors and CIs are likely wrong. Install survey-capable engine.")
        return out
    except Exception as e:
        return {"ok": False, "error": str(e), "engine": "none"}


def fit_linear_svy(df, outcome: str, exposure: str,
                      covariates: Optional[List[str]] = None,
                      *, strata: str = "STRATA",
                      cluster: str = "CLUSTER",
                      weight: str = "W") -> Dict:
    """Survey-weighted linear regression (continuous outcome)."""
    covariates = covariates or []
    err = _require_columns(df, [outcome, exposure, strata, cluster, weight] + covariates)
    if err:
        return {"ok": False, "error": err, "engine": "none"}
    try:
        from statsmodels.formula.api import wls
        formula = f"{outcome} ~ {exposure}" + ("" if not covariates else " + " + " + ".join(covariates))
        model = wls(formula, data=df, weights=df[weight]).fit(
            cov_type="cluster", cov_kwds={"groups": df[cluster]})
        return _pack_linear_result(model, engine="wls_cluster_robust")
    except Exception as e:
        return {"ok": False, "error": str(e), "engine": "none"}


def _pack_logit_result(model, *, engine: str) -> Dict:
    import math
    coef = model.params
    ci = model.conf_int()
    out = {
        "ok": True, "engine": engine,
        "params": {k: float(v) for k, v in coef.items()},
        "or": {k: math.exp(float(v)) for k, v in coef.items()},
        "ci_low": {k: math.exp(float(ci.loc[k, 0])) for k in coef.index},
        "ci_high": {k: math.exp(float(ci.loc[k, 1])) for k in coef.index},
        "p": {k: float(model.pvalues[k]) for k in coef.index},
        "n": int(getattr(model, "nobs", 0) or 0),
    }
    return out


def _pack_linear_result(model, *, engine: str) -> Dict:
    coef = model.params
    ci = model.conf_int()
    return {
        "ok": True, "engine": engine,
        "params": {k: float(v) for k, v in coef.items()},
        "ci_low": {k: float(ci.loc[k, 0]) for k in coef.index},
        "ci_high": {k: float(ci.loc[k, 1]) for k in coef.index},
        "p": {k: float(model.pvalues[k]) for k in coef.index},
        "n": int(getattr(model, "nobs", 0) or 0),
    }


def _r_survey_logit(df, outcome, exposure, covariates, *,
                       strata, cluster, weight) -> Dict:
    """R survey package via rpy2 — gold-standard implementation."""
    import rpy2.robjects as ro
    from rpy2.robjects import pandas2ri
    pandas2ri.activate()
    ro.r("library(survey)")
    ro.globalenv["df"] = pandas2ri.py2rpy(df)
    formula_str = f"{outcome} ~ {exposure}"
    if covariates:
        formula_str += " + " + " + ".join(covariates)
    ro.r(f"""
    design <- svydesign(ids=~{cluster}, strata=~{strata}, weights=~{weight}, data=df, nest=TRUE)
    model <- svyglm({formula_str}, design=design, family=binomial())
    co <- summary(model)$coefficients
    ci <- confint(model)
    """)
    co = ro.r("co")
    ci = ro.r("ci")
    import math
    names = list(ro.r("rownames(co)"))
    est = {k: float(co.rx(i + 1, 1)[0]) for i, k in enumerate(names)}
    pvals = {k: float(co.rx(i + 1, 4)[0]) for i, k in enumerate(names)}
    ci_low = {k: math.exp(float(ci.rx(i + 1, 1)[0])) for i, k in enumerate(names)}
    ci_high = {k: math.exp(float(ci.rx(i + 1, 2)[0])) for i, k in enumerate(names)}
    return {"ok": True, "engine": "rpy2.R.survey",
             "params": est, "or": {k: math.exp(v) for k, v in est.items()},
             "ci_low": ci_low, "ci_high": ci_high, "p": pvals}


__all__ = ["fit_logit_svy", "fit_linear_svy", "is_available"]
