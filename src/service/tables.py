"""Table service — Table 1 / Table 2 builder facade."""
from __future__ import annotations

from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def build_table1(df=None, *, group_var: Optional[str] = None,
                  vars_continuous: Optional[list] = None,
                  vars_categorical: Optional[list] = None) -> dict:
    """STROBE Table 1: baseline characteristics by group."""
    try:
        from src.analysis.table_builder import make_table1
        return make_table1(df=df, group_var=group_var,
                            vars_continuous=vars_continuous or [],
                            vars_categorical=vars_categorical or []) or {}
    except Exception as e:
        _log.warning("build_table1 fail: %s", e)
        return {"error": str(e)[:200]}


def build_table2(stat_result: dict) -> dict:
    """Multivariable model table — crude + adjusted ORs."""
    try:
        from src.analysis.table_builder import make_table2
        return make_table2(stat_result) or {}
    except Exception as e:
        _log.warning("build_table2 fail: %s", e)
        return {"error": str(e)[:200]}


__all__ = ["build_table1", "build_table2"]
