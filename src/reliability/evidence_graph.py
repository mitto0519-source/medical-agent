"""Evidence Graph close — Claim → Evidence/Dataset/Paper chain on top of medical_graph.

MASTER_UPGRADE §3 #1: schema_v2 already has Finding/REPORTS/USES_DATASET/SUPPORTS.
We add Claim nodes (one per generated sentence/section) plus CLAIMS/EVIDENCED_BY/
DERIVED_FROM/CITES_FOR edges so every manuscript line is traceable.

API:
    register_claim(paper_id, claim_id, text, *, pmids=[], dataset_label="", finding_ids=[]) -> str
    list_claims(paper_id) -> list[dict]
    trace_back(claim_id) -> dict  # full evidence chain
    extract_claims_from_draft(draft, paper_id) -> list[dict]
        # naive: split by sentence, pull PMIDs/numbers, register one Claim each
"""
from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


_CLAIM_ID_RE = re.compile(r"[^a-zA-Z0-9_:-]")


def _slug(text: str, maxlen: int = 40) -> str:
    s = _CLAIM_ID_RE.sub("_", (text or "").strip().lower())[:maxlen]
    return s.strip("_") or "claim"


def _hash_id(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", errors="replace")).hexdigest()[:10]


def _graph():
    try:
        from src.knowledge.medical_graph import get_graph
        return get_graph()
    except Exception as e:
        _log.warning("medical_graph load fail: %s", e)
        return None


def register_claim(paper_id: str, claim_id: str, text: str,
                      *, pmids: Optional[List[str]] = None,
                      dataset_label: str = "",
                      finding_ids: Optional[List[str]] = None) -> Optional[str]:
    """Add Claim node + edges to medical_graph. Returns node id or None on failure.

    paper_id  — Paper node id (manuscript or our project id, e.g. 'paper:proj-xyz').
    claim_id  — caller-supplied stable id (e.g. 'sec:Results:para3:sent2').
    text      — claim sentence (stored on node).
    pmids     — cited PMIDs (CITES_FOR edges).
    dataset_label — own dataset (DERIVED_FROM edge).
    finding_ids — graph Finding nodes (EVIDENCED_BY edges).
    """
    g = _graph()
    if g is None:
        return None

    node_id = f"claim:{paper_id}:{claim_id}"
    try:
        g.add_concept(
            concept_id=node_id,
            label=text[:200],
            domain="Claim",
            axis="Claim",
            discipline="evidence",
        )
    except Exception as e:
        _log.warning("add Claim node fail (%s): %s", node_id, e)
        return None

    # Edges
    try:
        if paper_id:
            g.link_concepts(paper_id, node_id, weight=1.0, rel="CLAIMS")
    except Exception as e:
        _log.debug("CLAIMS edge fail: %s", e)

    for pmid in (pmids or []):
        try:
            g.link_concepts(node_id, f"paper:{pmid}", weight=0.8, rel="CITES_FOR")
        except Exception as e:
            _log.debug("CITES_FOR edge fail (%s): %s", pmid, e)

    if dataset_label:
        try:
            g.link_concepts(node_id, f"dataset:{_slug(dataset_label)}",
                              weight=1.0, rel="DERIVED_FROM")
        except Exception as e:
            _log.debug("DERIVED_FROM edge fail: %s", e)

    for fid in (finding_ids or []):
        try:
            g.link_concepts(node_id, fid, weight=0.8, rel="EVIDENCED_BY")
        except Exception as e:
            _log.debug("EVIDENCED_BY edge fail (%s): %s", fid, e)

    return node_id


def extract_claims_from_draft(draft: str, paper_id: str,
                                 *, dataset_label: str = "",
                                 max_claims: int = 200) -> List[Dict]:
    """Naive claim extractor — split draft into sentences, pull inline PMID:xxxxx, register each.

    Returns [{"claim_id", "node_id", "text", "pmids": [...]} ...].
    Does NOT touch graph if medical_graph unavailable — returns metadata only.
    """
    if not draft:
        return []

    # Sentence split (medical text — keep simple, avoid abbrev-aware over-engineering)
    sentences = re.split(r"(?<=[.!?])\s+(?=[A-Z])", draft)
    claims: List[Dict] = []
    for idx, sent in enumerate(sentences):
        sent = sent.strip()
        if len(sent) < 40:  # skip short headings/labels
            continue
        if len(claims) >= max_claims:
            break
        pmids = re.findall(r"PMID:?(\d+)", sent)
        cid = f"sent_{idx:04d}_{_hash_id(sent)}"
        nid = register_claim(paper_id, cid, sent,
                                pmids=pmids, dataset_label=dataset_label)
        claims.append({"claim_id": cid, "node_id": nid, "text": sent[:200],
                        "pmids": pmids})
    return claims


def list_claims(paper_id: str) -> List[Dict]:
    """All Claim nodes attached to paper_id."""
    g = _graph()
    if g is None or not hasattr(g, "graph"):
        return []
    prefix = f"claim:{paper_id}:"
    out: List[Dict] = []
    try:
        for n, data in g.graph.nodes(data=True):
            if str(n).startswith(prefix):
                out.append({"node_id": n,
                            "text": (data.get("label") or "")[:200]})
    except Exception as e:
        _log.warning("list_claims fail: %s", e)
    return out


def trace_back(claim_node_id: str) -> Dict:
    """Walk outgoing edges from a Claim → return chain dict."""
    g = _graph()
    if g is None or not hasattr(g, "graph"):
        return {"node_id": claim_node_id, "edges": []}
    chain: List[Dict] = []
    try:
        for nbr in g.graph.successors(claim_node_id):
            edata = g.graph.get_edge_data(claim_node_id, nbr) or {}
            rel = edata.get("rel") or edata.get("relation") or "?"
            chain.append({"to": nbr, "rel": rel,
                            "weight": edata.get("weight", 0.0)})
    except Exception as e:
        _log.warning("trace_back fail: %s", e)
    return {"node_id": claim_node_id, "edges": chain}


__all__ = ["register_claim", "extract_claims_from_draft",
            "list_claims", "trace_back"]
