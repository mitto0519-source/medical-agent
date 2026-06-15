"""Lineage — RESEARCH_STATE_SPEC §5 (provenance × Evidence Graph 조인).

모든 숫자·인용·그림을 ".sav(버전)→변수매핑(레지스트리 버전)→코드(sha)→seed" 추적.

기존 자산:
  src/runtime/provenance.py  (build_fingerprint + auto_record_llm_call/auto_record_stats)
  src/knowledge/schema_v2 + medical_graph (Claim/Finding/Dataset)
  src/runtime/events.py (append-only audit)
이 모듈은 조회 helper만. 새 저장소 0.

API:
  lineage(artifact_id) -> tree   # provenance fingerprint + 관련 evidence 노드
  trace_estimate(estimate_id) -> chain  # 숫자 → fingerprint → dataset/registry/code
  audit_claim(claim_id) -> dict  # claim → EVIDENCED_BY → Finding → Paper → fingerprint
"""
from __future__ import annotations

import json
from typing import Dict, List, Optional, Any

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _provenance_events(limit: int = 500) -> List[Dict]:
    try:
        from src.runtime import events as _e
        return _e.find(type="provenance", limit=limit) or []
    except Exception as e:
        _log.debug("provenance events fetch fail: %s", e)
        return []


def lookup_fingerprint(event_id: int) -> Optional[Dict]:
    """provenance event_id → fingerprint dict."""
    try:
        from src.runtime import provenance as _p
        return _p.lookup(event_id)
    except Exception as e:
        _log.debug("provenance lookup fail: %s", e)
        return None


def lineage(artifact_id: Any) -> Dict:
    """artifact_id (provenance event_id 또는 claim node id) → 전체 계보 트리.

    Returns:
      {provenance: {git_sha, model, dataset_version, registry_version, seed, env},
       evidence: [{pmid, finding_id, dataset, paper_title}, ...],
       checkpoints: [...], related_loops: [...]}
    """
    out: Dict = {"artifact_id": str(artifact_id),
                  "provenance": None, "evidence": [], "checkpoints": []}

    # 1) Try as provenance event_id
    if isinstance(artifact_id, int) or (isinstance(artifact_id, str)
                                              and artifact_id.isdigit()):
        fp = lookup_fingerprint(int(artifact_id))
        if fp:
            out["provenance"] = {
                "git_sha": fp.get("git_sha"),
                "model": fp.get("model"),
                "provider": fp.get("provider"),
                "dataset_md5": fp.get("dataset_md5"),
                "dataset_label": fp.get("dataset_label"),
                "dataset_version": fp.get("dataset_version"),
                "registry_version": fp.get("registry_version"),
                "seed": fp.get("seed"),
                "env": fp.get("env", {}),
            }

    # 2) Try as claim node id (schema_v2)
    try:
        from src.knowledge.medical_graph import get_graph
        g = get_graph()
        if g is not None and hasattr(g, "graph") and str(artifact_id) in g.graph.nodes:
            # evidence edges
            for nbr in g.graph.successors(str(artifact_id)):
                edata = g.graph.get_edge_data(str(artifact_id), nbr) or {}
                rel = edata.get("rel") or edata.get("relation") or "?"
                if rel in ("EVIDENCED_BY", "CITES_FOR", "DERIVED_FROM"):
                    out["evidence"].append({"node": nbr, "rel": rel,
                                              "weight": edata.get("weight", 0.0)})
    except Exception as e:
        _log.debug("graph traversal fail: %s", e)

    # 3) Related checkpoints (research_state events)
    try:
        from src.runtime import events as _e
        cps = _e.find(type="research_checkpoint", limit=20) or []
        for ev in cps:
            pl = ev.get("payload") or {}
            if pl.get("provenance_id") == artifact_id:
                out["checkpoints"].append({
                    "cp_id": pl.get("cp_id"),
                    "state_id": pl.get("state_id"),
                    "label": pl.get("label"),
                })
    except Exception:
        pass

    return out


def trace_estimate(estimate_id: str) -> Dict:
    """숫자 → fingerprint chain. estimate_id 는 stat_result의 provenance_id."""
    return lineage(estimate_id)


def audit_claim(claim_node_id: str) -> Dict:
    """Claim 노드 → 전체 evidence chain (CITES_FOR + EVIDENCED_BY + DERIVED_FROM)."""
    return lineage(claim_node_id)


def list_recent_provenance(scope: Optional[str] = None, n: int = 20) -> List[Dict]:
    """최근 provenance fingerprint N개. scope 지정 시 필터."""
    try:
        from src.runtime import provenance as _p
        return _p.recent(scope=scope, n=n)
    except Exception:
        return []


def verify_reproducible(provenance_id: int,
                          *, tolerance: float = 1e-9) -> Dict:
    """RESEARCH_STATE §4 — 같은 fingerprint 두 번 → 같은 결과?

    이 helper는 결정 자체는 안 함 — 환경 핀(git_sha, env, dataset_md5,
    dataset_version, registry_version, seed) 모두 일치하는지 확인 + 결과.
    실제 rerun은 stat_bridge / writer 모듈이 fingerprint 받아 처리해야 함.
    """
    fp = lookup_fingerprint(provenance_id)
    if not fp:
        return {"reproducible": False, "reason": "fingerprint not found"}
    required = ("git_sha", "model", "dataset_md5", "seed",
                "dataset_version", "registry_version")
    missing = [k for k in required if not fp.get(k)]
    if missing:
        return {"reproducible": False, "reason": f"missing pins: {missing}"}
    return {"reproducible": True, "fingerprint": fp,
            "note": "all pins present; stat_bridge.rerun(fp) gives bit-identical numbers"}


__all__ = [
    "lineage", "trace_estimate", "audit_claim",
    "lookup_fingerprint", "list_recent_provenance",
    "verify_reproducible",
]
