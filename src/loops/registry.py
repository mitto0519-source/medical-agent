"""LoopDefinition + Registry — 기존 자동화를 카탈로그로 표면화 (새 인프라 0).

기존 자산:
  heartbeat.py 7 jobs · backlog.py 6 handlers · peer_reviewer critique loop ·
  evolution.gate.run_gate · autonomous_research_loop · prompt_ab · improvement_engine
모두 LoopDefinition 객체로 wrap만. 로직 변경 0.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Callable, List, Optional, Dict

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class LoopDefinition:
    name: str
    purpose: str                            # 한 줄 설명
    trigger: str                            # "heartbeat:5min" / "backlog" / "manual" / "cron:daily"
    skill: str = ""                        # prompts/*.md key
    connectors: List[str] = field(default_factory=list)   # tool names
    reviewers: List[str] = field(default_factory=list)    # sub-agents (writer/critic/...)
    state_paths: List[str] = field(default_factory=list)  # change_log/events.db/ResearchProject
    completion: str = ""                   # success condition (text)
    handler: Optional[Callable] = None     # runnable (선택)

    def to_dict(self) -> dict:
        d = {k: v for k, v in asdict(self).items() if k != "handler"}
        d["has_handler"] = self.handler is not None
        return d


# ── 카탈로그 — 기존 자산 wrap (이미 다 작동 중인 것들) ──────────────────────

_LOOPS: Dict[str, LoopDefinition] = {}


def register(loop: LoopDefinition) -> None:
    _LOOPS[loop.name] = loop


def list_loops() -> List[dict]:
    return [l.to_dict() for l in _LOOPS.values()]


def get_loop(name: str) -> Optional[LoopDefinition]:
    return _LOOPS.get(name)


def run_loop(name: str, **kwargs) -> dict:
    """수동 실행. heartbeat 등이 이미 자동 실행 — 수동은 디버그/즉시 트리거용."""
    loop = _LOOPS.get(name)
    if loop is None:
        return {"ok": False, "error": f"unknown loop: {name}"}
    if loop.handler is None:
        return {"ok": False, "error": f"loop '{name}' has no manual handler — auto only"}
    try:
        result = loop.handler(**kwargs)
        return {"ok": True, "name": name, "result": result}
    except Exception as e:
        _log.warning("loop %s fail: %s", name, e)
        return {"ok": False, "name": name, "error": str(e)[:200]}


# ── Registration of existing assets (기존 모듈 wrap) ────────────────────────

# ── 실 handler 래퍼들 (lazy import — registry 로드 시 의존성 없음) ──────────

def _h_periodic_learn(**kw) -> dict:
    """heartbeat:periodic_learn — PubMed 24h 트렌드 + RAG 인덱싱."""
    from src.knowledge.trend_learner import run_trend_learn
    return run_trend_learn(days=kw.get("days", 60),
                              max_per_query=kw.get("max_per_query", 30))


def _h_backlog_drain(**kw) -> dict:
    """heartbeat:backlog_drain — backlog 5분 처리."""
    from src.runtime.backlog import drain_once
    return drain_once(max_jobs=kw.get("max_jobs", 5), owner=kw.get("owner"))


def _h_reconcile_state(**_kw) -> dict:
    """heartbeat:reconcile_state — CURRENT_STATE.json 갱신.

    실 구현은 scripts/reconcile_current_state.py 또는 heartbeat._job_*.
    여기선 in-process로 핵심 카운트만.
    """
    from pathlib import Path
    import json, time
    p = Path("CURRENT_STATE.json")
    if not p.exists():
        return {"error": "CURRENT_STATE.json 없음"}
    try:
        state = json.loads(p.read_text(encoding="utf-8"))
        # ChromaDB chunks 실측
        try:
            import chromadb
            c = chromadb.PersistentClient(path="data/chromadb")
            for col in c.list_collections():
                if "768" in col.name:
                    state.setdefault("verified_counts", {})["chromadb_chunks"] = col.count()
                    break
        except Exception:
            pass
        # oa_papers 카운트
        oa = Path("data/oa_papers")
        if oa.exists():
            state.setdefault("verified_counts", {})["oa_papers"] = len(list(oa.glob("PMC*.txt")))
        state["reconciled_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"ok": True, "reconciled": state.get("verified_counts", {})}
    except Exception as e:
        return {"error": str(e)[:200]}


def _make_backlog_handler(kind: str):
    """backlog:{kind} 실 호출 wrapper — backlog._HANDLERS[kind]를 lazy import."""
    def _runner(**kw):
        from src.runtime.backlog import _HANDLERS as _BH
        fn = _BH.get(kind)
        if fn is None:
            return {"error": f"backlog handler '{kind}' not registered in backlog._HANDLERS"}
        return fn(kw)
    return _runner


def _h_critique_revise(**kw) -> dict:
    """critique:revise_with_critique — writer↔critic 2라운드."""
    from src.research.peer_reviewer import PeerReviewer
    pr = PeerReviewer()
    if hasattr(pr, "revise_with_critique"):
        return pr.revise_with_critique(**kw) or {}
    return {"error": "PeerReviewer.revise_with_critique 미구현"}


def _h_evolution_gate(**kw) -> dict:
    """evolution:gate — candidate → 골드셋 채점 → promote/rollback."""
    from src.evolution.gate import run_gate
    kind = kw.get("kind", "prompt_change")
    cid = kw.get("id", "candidate")
    payload = kw.get("payload", {})
    return run_gate(kind, cid, payload, **{k: v for k, v in kw.items()
                                                if k not in ("kind", "id", "payload")})


def _h_research_autonomous(**kw) -> dict:
    """research:autonomous — run_full IMRAD 파이프라인."""
    from src.research.research_pipeline import ResearchPipeline
    rp = ResearchPipeline()
    if hasattr(rp, "run_full"):
        topic = kw.get("topic") or {"title": kw.get("title", "untitled")}
        return rp.run_full(topic, **{k: v for k, v in kw.items() if k != "topic"}) or {}
    return {"error": "ResearchPipeline.run_full 미구현"}


def _register_builtins() -> None:
    """기존 7+6+critique+gate+autonomous 모듈을 LoopDefinition으로 표면화 + handler wire."""
    # heartbeat 3 jobs (jobs는 src/runtime/heartbeat.py 내부)
    register(LoopDefinition(
        name="heartbeat:periodic_learn",
        purpose="PubMed 24h 트렌드 자동 수집 + 자가학습",
        trigger="heartbeat:hourly",
        skill="medical_core",
        connectors=["pubmed_search", "rag_search"],
        state_paths=["data/runtime/events.db", "data/knowledge_graph/"],
        completion="trend_state.json updated",
        handler=_h_periodic_learn,
    ))
    register(LoopDefinition(
        name="heartbeat:backlog_drain",
        purpose="업로드 파일·인제스트 큐 백그라운드 처리",
        trigger="heartbeat:5min",
        skill="",
        connectors=[],
        state_paths=["data/runtime/events.db", "data/oa_papers/"],
        completion="backlog empty or budget exhausted",
        handler=_h_backlog_drain,
    ))
    register(LoopDefinition(
        name="heartbeat:reconcile_state",
        purpose="CURRENT_STATE.json verified_counts 갱신 (ChromaDB·oa_papers 실측)",
        trigger="heartbeat:daily",
        skill="",
        connectors=[],
        state_paths=["CURRENT_STATE.json"],
        completion="all counts measured",
        handler=_h_reconcile_state,
    ))

    # backlog 실 핸들러 (src/runtime/backlog._HANDLERS) — 직접 동기화 (이름 mismatch 차단)
    try:
        from src.runtime.backlog import _HANDLERS as _BH
        _backlog_kinds = list(_BH.keys())
    except Exception as e:
        _log.warning("backlog._HANDLERS 로드 실패: %s — registry에 backlog 항목 누락", e)
        _backlog_kinds = []
    for kind in _backlog_kinds:
        register(LoopDefinition(
            name=f"backlog:{kind}",
            purpose=f"백로그 핸들러: {kind}",
            trigger="backlog",
            connectors=[],
            state_paths=["data/runtime/events.db"],
            handler=_make_backlog_handler(kind),
        ))

    # critique loop (peer_reviewer)
    register(LoopDefinition(
        name="critique:revise_with_critique",
        purpose="작성→비평→재작성 (최대 2회) — writer↔critic 분리",
        trigger="manual",
        skill="yoosun_style",
        connectors=["pubmed_search", "rag_search"],
        reviewers=["writer", "critic"],
        state_paths=["data/research_states/"],
        completion="score ≥ target_pct or max_iters",
        handler=_h_critique_revise,
    ))

    # evolution gate (SELF_EVOLUTION)
    register(LoopDefinition(
        name="evolution:gate",
        purpose="candidate change → 골드셋 채점 → promote/rollback",
        trigger="manual",
        skill="",
        connectors=["anchor", "ledger"],
        reviewers=["baseline_scorer", "candidate_scorer"],
        state_paths=["data/runtime/events.db", "eval/gold_set.json"],
        completion="ledger 기록 + active 갱신",
        handler=_h_evolution_gate,
    ))

    # autonomous research loop
    register(LoopDefinition(
        name="research:autonomous",
        purpose="run_full IMRAD — RQ→Stat→Write→Polish→Save (사용자 'autopilot')",
        trigger="manual",
        skill="paper_writing",
        connectors=["kyrbs_stat", "patch_preview", "rag_search", "pubmed_search"],
        reviewers=["writer", "critic", "physician_review"],
        state_paths=["data/research_states/", "data/working_papers/"],
        completion="sections complete + provenance recorded",
        handler=_h_research_autonomous,
    ))


_register_builtins()


__all__ = ["LoopDefinition", "register", "list_loops",
            "get_loop", "run_loop"]
