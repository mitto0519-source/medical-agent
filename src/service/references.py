"""Reference service — citation_workflow.Reference CRUD + EndNote .enl export.

Thin wrapper exposing the existing citation_workflow primitives so the FastAPI/Next.js layer
can manipulate reference lists without depending on Streamlit.
"""
from __future__ import annotations

from typing import List, Optional

from src.config.logging_config import get_logger
from src.service.paper import hits_to_references  # re-export

_log = get_logger(__name__)


def references_from_pmid_list(pmids: List[str], *, fetch_pubmed: bool = False) -> List:
    """Build Reference objects from raw PMID list.

    fetch_pubmed=True → src.research.pubmed lookup for title/year/journal (slow).
    """
    try:
        from src.export.citation_workflow import Reference
    except Exception as e:
        _log.warning("Reference import fail: %s", e)
        return []
    seen: set = set()
    refs: List = []
    for pmid in pmids:
        pmid = str(pmid).strip()
        if not pmid or pmid in seen:
            continue
        seen.add(pmid)
        if fetch_pubmed:
            meta = _fetch_pubmed_meta(pmid)
            refs.append(Reference(pmid=pmid,
                                     title=meta.get("title", f"PubMed {pmid}"),
                                     authors=meta.get("authors", []),
                                     journal=meta.get("journal", ""),
                                     year=meta.get("year", 0),
                                     citation_key=f"PMID{pmid}"))
        else:
            refs.append(Reference(pmid=pmid, title=f"PubMed {pmid}",
                                     citation_key=f"PMID{pmid}"))
    return refs


def _fetch_pubmed_meta(pmid: str) -> dict:
    try:
        from src.research.pubmed import fetch_metadata
        return fetch_metadata(pmid) or {}
    except Exception as e:
        _log.debug("pubmed metadata fetch fail (%s): %s", pmid, e)
        return {}


def render_reference_list_markdown(refs: List) -> str:
    """Vancouver-style markdown list."""
    try:
        from src.export.citation_workflow import reference_list_markdown
        return reference_list_markdown(refs)
    except Exception as e:
        _log.warning("reference_list_markdown fail: %s", e)
        return "\n".join(f"{i+1}. PMID {r.pmid}" for i, r in enumerate(refs))


def export_endnote_enl(refs: List, output_path: str) -> bool:
    """EndNote .enl export via existing endnote_exporter."""
    try:
        from src.export.endnote_exporter import export_to_enl
        return export_to_enl(refs, output_path)
    except Exception as e:
        _log.warning("endnote_exporter fail: %s", e)
        return False


def insert_references_into_draft(draft: str, refs: List) -> tuple[str, dict]:
    """PMID-inline → numbered + auto-generate References section.

    Returns (draft, meta dict with cited_pmids).
    """
    if not refs:
        return draft, {"cited_pmids": []}
    meta: dict = {}
    try:
        from src.export.citation_workflow import convert_pmid_inline_to_numbered, reference_list_markdown
        draft, ordered_pmid, n_conv = convert_pmid_inline_to_numbered(draft, refs)
        meta["cited_pmids"] = [r.pmid for r in ordered_pmid]
        meta["n_converted"] = n_conv
        if ordered_pmid and "## References" not in draft:
            draft = draft.rstrip() + "\n\n## References\n\n" + reference_list_markdown(ordered_pmid)
    except Exception as e:
        _log.warning("insert_references fail: %s", e)
        meta["error"] = str(e)[:120]
    return draft, meta


__all__ = [
    "hits_to_references",
    "references_from_pmid_list",
    "render_reference_list_markdown",
    "export_endnote_enl",
    "insert_references_into_draft",
]
