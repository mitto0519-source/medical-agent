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


def sensitivity_panel(spec: dict, df=None) -> dict:
    """Run multiple sensitivity specs (complete-case / MI / restricted model)."""
    try:
        from src.analysis.sensitivity import run_sensitivity_panel
        return run_sensitivity_panel(spec, df=df) or {}
    except Exception as e:
        _log.warning("sensitivity_panel fail: %s", e)
        return {"error": str(e)[:200]}


__all__ = ["analyze", "sensitivity_panel"]
