"""RAG service — pure logic extracted from ez_home._rag_retrieve.

Pattern: input dict/str → output dict/str. No Streamlit, no session_state.
Caches RAGPipeline instance at module level (process-wide singleton).
"""
from __future__ import annotations

from typing import List, Dict, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

# Module-level cache (single pipeline, lazy init)
_PIPELINE = {"pipeline": None, "fail": False}


def _get_pipeline():
    if _PIPELINE["fail"]:
        return None
    if _PIPELINE["pipeline"] is None:
        try:
            from src.rag.pipeline import RAGPipeline
            _PIPELINE["pipeline"] = RAGPipeline()
        except Exception as e:
            _log.warning("RAGPipeline init fail: %s", e)
            _PIPELINE["fail"] = True
            return None
    return _PIPELINE["pipeline"]


def retrieve(query: str, top_k: int = 5, *, use_hyde: bool = False) -> List[Dict]:
    """Return list of {text, score, metadata} hits. Empty list on no match/fail.

    FIX-6: search_with_rerank if available, else basic search.
    """
    if not query or len(query.strip()) < 6:
        return []
    pipe = _get_pipeline()
    if pipe is None:
        return []
    try:
        if hasattr(pipe, "search_with_rerank"):
            return pipe.search_with_rerank(query, n_final=top_k, n_pool=20,
                                              use_hyde=use_hyde) or []
        return pipe.search(query, n_results=top_k) or []
    except Exception as e:
        _log.warning("RAG retrieve fail: %s", e)
        return []


def retrieve_as_text_block(query: str, top_k: int = 5,
                              *, max_text_per_hit: int = 600,
                              use_hyde: bool = False) -> str:
    """Convenience: retrieve + format as `[RAG#n PMID:... — title]\\n<text>` block."""
    hits = retrieve(query, top_k=top_k, use_hyde=use_hyde)
    if not hits:
        return ""
    blocks: list[str] = []
    for i, h in enumerate(hits, 1):
        text = (h.get("text", "") or "").strip().replace("\n", " ")[:max_text_per_hit]
        meta = h.get("metadata") or {}
        pmid = meta.get("pmid", "")
        title = (meta.get("title", "") or meta.get("source", ""))[:120]
        tag = f"[RAG#{i}"
        if pmid:
            tag += f" PMID:{pmid}"
        if title:
            tag += f" — {title}"
        tag += "]"
        blocks.append(f"{tag}\n{text}")
    return "\n\n".join(blocks)


def extract_pmids_from_hits(hits: List[Dict]) -> List[str]:
    """PMID list from hit metadata (deduped, preserve order)."""
    seen: set = set()
    out: list[str] = []
    for h in hits:
        md = h.get("metadata") or {}
        pmid = str(md.get("pmid") or "").strip()
        if pmid and pmid not in seen:
            seen.add(pmid)
            out.append(pmid)
    return out
