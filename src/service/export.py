"""Export service — DOCX/PDF + EndNote bundle.

bundle_for_download(project, with_endnote=True) → dict {docx_bytes, enl_bytes, figures: {kind: png_bytes}}
"""
from __future__ import annotations

from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def export_docx(project: dict, *, journal_slug: Optional[str] = None) -> bytes:
    """Render manuscript to DOCX bytes. Uses paper_writer / word_exporter."""
    try:
        from src.export.word_exporter import build_docx
        rs = project.get("research_state") or {}
        manuscript = rs.get("manuscript_text") or rs.get("draft", "")
        if not manuscript:
            return b""
        return build_docx(manuscript=manuscript,
                           title=project.get("title", "Manuscript"),
                           target_journal=journal_slug or rs.get("target_journal", ""),
                           refs=rs.get("references", []))
    except Exception as e:
        _log.warning("export_docx fail: %s", e)
        return b""


def export_endnote(project: dict) -> bytes:
    """EndNote .enl bytes for cited PMIDs."""
    try:
        from src.export.endnote_exporter import build_enl_bytes
        rs = project.get("research_state") or {}
        refs = rs.get("references") or []
        if not refs:
            return b""
        return build_enl_bytes(refs)
    except Exception as e:
        _log.warning("export_endnote fail: %s", e)
        return b""


def bundle_for_download(project: dict, *, with_endnote: bool = True,
                          with_figures: bool = True) -> dict:
    """One-shot bundle for Lovable-style download button."""
    bundle = {"docx": export_docx(project)}
    if with_endnote:
        bundle["enl"] = export_endnote(project)
    if with_figures:
        try:
            from src.service.figures import generate_all_for_paper
            bundle["figures"] = generate_all_for_paper(project)
        except Exception as e:
            _log.debug("figure bundle fail: %s", e)
            bundle["figures"] = {}
    return bundle


__all__ = ["export_docx", "export_endnote", "bundle_for_download"]
