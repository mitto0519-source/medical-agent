"""State View — 흩어진 상태(ResearchProject + CURRENT_STATE + self_model + events)를
한 줄 view로 합성 (사용자가 '오늘 어디까지 왔나' 즉시 인지).

기존 자산 그대로 — 합성 view만.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _read_current_state() -> Dict:
    try:
        return json.loads(Path("CURRENT_STATE.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def _list_active_projects(owner_email: Optional[str] = None) -> List[Dict]:
    out: List[Dict] = []
    proj_dir = Path("data/projects")
    if not proj_dir.exists():
        return out
    for p in sorted(proj_dir.glob("*.json"),
                       key=lambda x: x.stat().st_mtime, reverse=True)[:10]:
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
            if owner_email and d.get("owner_email") and d["owner_email"] != owner_email:
                continue
            out.append({
                "id": d.get("id"),
                "title": (d.get("title") or "")[:80],
                "n_messages": len(d.get("messages") or []),
                "has_sections": bool(d.get("sections")),
                "updated": d.get("updated", ""),
            })
        except Exception:
            continue
    return out


def _last_checkpoint(state_id: Optional[str] = None) -> Optional[Dict]:
    try:
        from src.research.research_state import list_checkpoints
        if state_id:
            cps = list_checkpoints(state_id, limit=1)
            return cps[0] if cps else None
    except Exception:
        pass
    return None


def _self_model_next_action() -> Optional[str]:
    try:
        from src.memory.self_model import surface_next_action
        return surface_next_action()
    except Exception:
        return None


def _ingest_progress() -> Dict:
    log = Path("data/logs/ingest_full.log")
    if not log.exists():
        return {"running": False}
    try:
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        last_ok = 0
        for ln in reversed(lines):
            if "ok=" in ln:
                import re
                m = re.search(r"ok=(\d+)", ln)
                if m:
                    last_ok = int(m.group(1))
                    break
        done = "DONE" in (lines[-1] if lines else "")
        return {"running": not done, "last_ok": last_ok,
                "last_line": (lines[-1] if lines else "")[:200]}
    except Exception:
        return {"running": False}


def _gold_set_label_count() -> Dict:
    try:
        gs = json.loads(Path("eval/gold_set.json").read_text(encoding="utf-8"))
        pairs = gs.get("claim_evidence_pairs") or []
        labelled = sum(1 for p in pairs
                       if (p.get("label") or "").lower() in
                       ("supports", "contradicts", "neutral"))
        total = len(pairs)
        return {"labelled": labelled, "total": total,
                "pct": (labelled / total * 100) if total else 0.0}
    except Exception:
        return {"labelled": 0, "total": 0, "pct": 0.0}


def today_view(owner_email: Optional[str] = None) -> Dict:
    """오늘 어디까지 왔나 — 1 view 합성."""
    cs = _read_current_state()
    vc = cs.get("verified_counts") or {}
    projects = _list_active_projects(owner_email=owner_email)
    return {
        "last_session_at": cs.get("last_session_at") or vc.get("measured_at"),
        "active_projects": projects[:5],
        "active_count": len(projects),
        "last_checkpoint": _last_checkpoint(projects[0]["id"]) if projects else None,
        "next_action": _self_model_next_action(),
        "ingest": _ingest_progress(),
        "gold_set": _gold_set_label_count(),
        "rag_chunks_768d": (vc.get("chromadb") or {}).get("embeddings"),
        "graph_nodes": (vc.get("knowledge_graph") or {}).get("nodes_total"),
    }


__all__ = ["today_view"]
