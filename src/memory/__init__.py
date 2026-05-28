"""Memory facade — 11+ 분산 모듈을 단일 진입으로 노출 (vision diagram 'Multi-layer Memory').

5층 메모리 (Vision 'Multi-layer Memory System'):
  A. Working    — 단기 (대화 컨텍스트/현재 작업 상태) → events.memory_working (TTL)
  B. Episodic   — 사건 (시간별/상황별/대화 history) → conversation_memory + events.memory_episodic
  C. Semantic   — 의미 (개념/관계/도메인 지식) → ChromaDB semantic_* + medical_graph
  D. Procedural — 절차 (작업 절차/규칙/자동화) → procedural.py SQLite
  E. Goal       — 목표 (장기/단기/이전/성취) → agent_self/goals.json

통합 흐름 ([[feedback_organism_flow]]):
    user_msg → trigger_analyzer → cognitive_activation → recall_all_layers
              → build_system_with_preview → LLM tool_use → write(typed)
              → audit_trail → events → capability_bench (자가발전 회로 닫힘)

API:
    from src.memory import write, recall_all_layers, stats
    write("aOR 1.27", type="semantic", source="paper_writer")
    layers = recall_all_layers("ZCB depression", owner="me@x.com")
    # layers = {"working":[], "episodic": str, "semantic":[],
    #           "procedural":[], "goal":[]}
"""
from __future__ import annotations

from typing import Dict, List, Optional

# 핵심 함수 re-export (단일 진입)
from src.memory.router import write, MemType        # noqa: F401
from src.memory.memory_gate import assess           # noqa: F401
from src.memory.scorer import score, gate           # noqa: F401
from src.memory.conversation_memory import (        # noqa: F401
    record as record_conversation,
    recall_relevant as recall_episodic,
)
from src.memory.agent_insight import (              # noqa: F401
    build_self_context as recall_insights,
    record as record_insight,
)
from src.memory.procedural import (                 # noqa: F401
    add_rule as add_procedural_rule,
    find_applicable as recall_procedural,
    report_outcome as report_procedural_outcome,
)
from src.memory.schemas import (                    # noqa: F401
    MemoryRecord, MemoryScores, MemoryMeta, ProceduralRule,
    validate_record, validate_procedural, migrate, SCHEMA_VERSION,
)


def recall_all_layers(query: str, *, owner: Optional[str] = None,
                       n_per_layer: int = 3) -> Dict[str, object]:
    """5층 메모리 동시 recall — Vision 'Multi-layer Retrieval Router' 보강."""
    out: Dict[str, object] = {"working": [], "episodic": "",
                                "semantic": [], "procedural": [], "goal": []}
    # Working
    try:
        from src.runtime import events as _ev
        rows = _ev.find(type="memory_working", limit=n_per_layer * 2)
        out["working"] = [
            {"text": (r.get("payload") or {}).get("text", "")[:200]
                      if isinstance(r.get("payload"), dict)
                      else str(r.get("payload"))[:200],
             "ts": r.get("ts")}
            for r in rows[:n_per_layer]
        ]
    except Exception:
        pass
    # Episodic
    try:
        out["episodic"] = recall_episodic(query, n=n_per_layer, owner_email=owner) or ""
    except Exception:
        pass
    # Semantic
    try:
        from src.rag.pipeline import RAGPipeline
        hits = RAGPipeline().search(query, n_results=n_per_layer) or []
        out["semantic"] = [{"text": (h.get("text") or "")[:200],
                             "score": h.get("score"),
                             "metadata": h.get("metadata", {})} for h in hits[:n_per_layer]]
    except Exception:
        pass
    # Procedural
    try:
        out["procedural"] = recall_procedural(query, limit=n_per_layer)
    except Exception:
        pass
    # Goal
    try:
        from pathlib import Path as _P
        import json as _j
        gp = _P("data/agent_self/goals.json")
        if gp.exists():
            data = _j.loads(gp.read_text(encoding="utf-8"))
            if isinstance(data, list):
                out["goal"] = data[-n_per_layer:]
            elif isinstance(data, dict):
                out["goal"] = list(data.items())[:n_per_layer]
    except Exception:
        pass
    return out


def stats() -> Dict:
    """5층 메모리 누적 통계 — Dashboard용."""
    s: Dict = {}
    try:
        from src.runtime import events as _ev
        s["working_events"] = _ev.count(type="memory_working")
        s["episodic_events"] = _ev.count(type="memory_episodic")
    except Exception:
        pass
    try:
        import chromadb
        cli = chromadb.PersistentClient(path="data/chromadb")
        for c in cli.list_collections():
            s[f"semantic.{c.name}"] = c.count()
    except Exception:
        pass
    try:
        from src.memory.procedural import stats as _ps
        s["procedural"] = _ps()
    except Exception:
        pass
    try:
        from src.knowledge.medical_graph import get_graph
        g = get_graph()
        if g and hasattr(g, "_G"):
            s["graph"] = {"nodes": g._G.number_of_nodes(),
                           "edges": g._G.number_of_edges()}
    except Exception:
        pass
    return s


def lifecycle_tick():
    """수명주기 sweep (decay/archive/충돌 supersede) — heartbeat에서도 호출."""
    try:
        from src.memory.lifecycle import tick
        return tick()
    except Exception as e:
        return {"error": str(e)[:200]}


__all__ = [
    "write", "MemType", "assess", "score", "gate",
    "record_conversation", "recall_episodic",
    "recall_insights", "record_insight",
    "add_procedural_rule", "recall_procedural", "report_procedural_outcome",
    "lifecycle_tick",
    "MemoryRecord", "MemoryScores", "MemoryMeta", "ProceduralRule",
    "validate_record", "validate_procedural", "migrate", "SCHEMA_VERSION",
    "recall_all_layers", "stats",
]
