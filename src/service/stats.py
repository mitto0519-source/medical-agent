"""Stats service — thin wrapper around StatBridge.

Pure: spec dict in → result dict out. No Streamlit. FastAPI compute endpoint imports this.
"""
from __future__ import annotations

from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def analyze(spec: dict, df=None, *, dataset_path: Optional[str] = None) -> dict:
    """Run StatBridge.analyze on a spec dict.

    spec keys: design, outcome, exposure, confounders[], weights, cluster, strata, ...
    Result has: aOR/HR/coef, CI, p, n, model_meta. Provenance auto-recorded.
    """
    try:
        from src.analysis.stat_bridge import StatBridge
        sb = StatBridge()
        result = sb.analyze(spec, df=df)
        # Provenance fingerprint
        try:
            from src.runtime.provenance import auto_record_stats
            auto_record_stats(spec, dataset_path=dataset_path)
        except Exception as e:
            _log.debug("provenance auto_record_stats fail: %s", e)
        return result if isinstance(result, dict) else {"raw": result}
    except Exception as e:
        _log.warning("stats.analyze fail: %s", e)
        return {"error": str(e)[:200]}


def analyze_knhanes(spec: dict, df=None) -> dict:
    """KNHANES preset — strata=kstrata, cluster=psu, weight=wt_itvex 자동 적용.

    spec 의 strata/cluster/weight 키 비어 있으면 KNHANES 표준으로 채움.
    이후 survey_weighted.fit_logit_svy 호출.
    """
    spec = dict(spec or {})
    spec.setdefault("strata", "kstrata")
    spec.setdefault("cluster", "psu")
    spec.setdefault("weight", "wt_itvex")
    spec.setdefault("design", "logistic")
    try:
        from src.analysis import survey_weighted as svy
        if spec["design"] == "logistic":
            res = svy.fit_logit_svy(
                df, spec.get("outcome", ""), spec.get("exposure", ""),
                spec.get("covariates"),
                strata=spec["strata"], cluster=spec["cluster"], weight=spec["weight"])
        else:
            res = svy.fit_linear_svy(
                df, spec.get("outcome", ""), spec.get("exposure", ""),
                spec.get("covariates"),
                strata=spec["strata"], cluster=spec["cluster"], weight=spec["weight"])
        try:
            from src.runtime.provenance import auto_record_stats
            auto_record_stats(spec)
        except Exception as e:
            _log.debug("knhanes provenance fail: %s", e)
        return res if isinstance(res, dict) else {"raw": res}
    except Exception as e:
        _log.warning("analyze_knhanes fail: %s", e)
        return {"error": str(e)[:200]}


def sensitivity_panel(spec: dict, df=None) -> dict:
    """Run multiple sensitivity specs (complete-case / MI / restricted model)."""
    try:
        from src.analysis.sensitivity import run_sensitivity_panel
        return run_sensitivity_panel(spec, df=df) or {}
    except Exception as e:
        _log.warning("sensitivity_panel fail: %s", e)
        return {"error": str(e)[:200]}


__all__ = ["analyze", "analyze_knhanes", "sensitivity_panel"]
