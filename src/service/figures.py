"""Figure service — publication_figure_generator wrapper.

generate_figure(project, kind) → (png_bytes, caption). Identical contract to ez_home._generate_figure
but pure (no Streamlit). Already implemented in src.service.paper.generate_figure — re-exported.
"""
from __future__ import annotations

from typing import Optional, Tuple

from src.config.logging_config import get_logger
from src.service.paper import generate_figure, detect_figure_request  # re-export

_log = get_logger(__name__)


def list_supported_kinds() -> list[str]:
    return ["forest", "subgroup", "coef", "roc", "prev", "table1", "table2"]


def generate_all_for_paper(project: dict) -> dict:
    """Bulk: generate all applicable figures for a project. Returns {kind: png_bytes}.

    Skips kinds whose required stat_result keys are missing (silently).
    """
    try:
        from src.export.publication_figure_generator import generate_figures_for_paper
        rs = project.get("research_state") or {}
        stat_result = rs.get("stat_result") or {}
        if not stat_result:
            return {}
        return generate_figures_for_paper(
            stat_result=stat_result,
            safe_title=str(project.get("id", "paper"))[:40],
        ) or {}
    except Exception as e:
        _log.warning("generate_all_for_paper fail: %s", e)
        return {}


__all__ = ["generate_figure", "detect_figure_request",
            "list_supported_kinds", "generate_all_for_paper"]
