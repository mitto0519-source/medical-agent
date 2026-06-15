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

def _register_builtins() -> None:
    """기존 7+6+critique+gate 모듈들을 LoopDefinition으로 표면화."""
    # heartbeat 7 jobs (jobs는 src/runtime/heartbeat.py 내부)
    register(LoopDefinition(
        name="heartbeat:periodic_learn",
        purpose="PubMed 24h 트렌드 자동 수집 + 자가학습",
        trigger="heartbeat:hourly",
        skill="medical_core",
        connectors=["pubmed_search", "rag_search"],
        state_paths=["data/runtime/events.db", "data/knowledge_graph/"],
        completion="trend_state.json updated",
    ))
    register(LoopDefinition(
        name="heartbeat:backlog_drain",
        purpose="업로드 파일·인제스트 큐 백그라운드 처리",
        trigger="heartbeat:5min",
        skill="",
        connectors=[],
        state_paths=["data/runtime/events.db", "data/oa_papers/"],
        completion="backlog empty or budget exhausted",
    ))
    register(LoopDefinition(
        name="heartbeat:reconcile_state",
        purpose="CURRENT_STATE.json verified_counts 갱신",
        trigger="heartbeat:daily",
        skill="",
        connectors=[],
        state_paths=["CURRENT_STATE.json"],
        completion="all counts measured",
    ))

    # backlog 6 handlers (src/runtime/backlog.py)
    for kind in ("ingest_paper", "register_dataset", "rag_reindex",
                  "style_profile", "checkpoint", "quality_eval"):
        register(LoopDefinition(
            name=f"backlog:{kind}",
            purpose=f"백로그 핸들러: {kind}",
            trigger="backlog",
            connectors=[],
            state_paths=["data/runtime/events.db"],
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
    ))


_register_builtins()


__all__ = ["LoopDefinition", "register", "list_loops",
            "get_loop", "run_loop"]
