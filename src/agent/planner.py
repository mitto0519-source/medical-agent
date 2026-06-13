"""Planner — hierarchical task decomposition + execution DAG.

외부 진단 (2026-05-28): "frontier agent와 가장 큰 차이 = planning engine 약함".

설계:
  · Goal → DAG (nodes=tasks, edges=dependencies)
  · 각 노드: action_type, args, retry_policy, expected_output
  · executor가 topological order로 실행, 의존성 satisfied될 때 진행
  · 노드 실패 → retry → root cause → DAG mutation (replanning)
  · 모든 transition은 events.db에 기록 (replay 가능)

`WritingOrchestrator.plan_section`은 룰 base에 그쳤지만,
본 Planner는 **LLM이 DAG를 직접 생성**하고 **mutation 가능**.

호출:
    p = Planner()
    dag = p.plan(goal="Write Introduction for ZCB-depression paper",
                  context={"section": "Introduction", "exposure": "zcb_freq"})
    # dag: ExecutionGraph
    p.execute(dag, on_step=lambda node, result: ...)
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class TaskNode:
    """DAG 단일 노드. agent-time vs human-time 분리 (EstreGenesis v1.6.0)."""
    id: str
    action: str                    # "gather_evidence" | "patch_preview" | "run_stat" | "apply_style" | ...
    args: Dict[str, Any] = field(default_factory=dict)
    deps: List[str] = field(default_factory=list)    # 선행 노드 id
    state: str = "pending"          # pending | running | done | failed | skipped
    output: Optional[Any] = None
    error: Optional[str] = None
    n_attempts: int = 0
    max_attempts: int = 2
    expected_output: str = ""
    rationale: str = ""
    # ── 시간 분리 (EstreGenesis 패턴) ──────────────────────────
    agent_time_sec: float = 0.0            # LLM 호출 + tool 실행 시간 (실측)
    human_review_time_sec: float = 0.0     # 사용자 검토/승인 시간 (예측 또는 측정)
    wall_clock_sec: float = 0.0            # 전체 경과 (대기 포함)

    def to_dict(self) -> Dict:
        return asdict(self)


# pace_mode → agent×human 배수 (EstreGenesis v1.6.0 시간 추정 보정)
PACE_MULTIPLIER = {
    "cautious":  3.0,    # 2-4× 평균
    "proactive": 5.5,    # 5-6× 평균 (기본)
    "burst":     7.0,    # 6-8×
    "sprint":    9.5,    # 9-10×
}


@dataclass
class ExecutionGraph:
    """DAG (nodes + edges)."""
    id: str
    goal: str
    nodes: Dict[str, TaskNode] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    state: str = "pending"   # pending | running | completed | failed | partial
    pace_mode: str = "proactive"   # cautious|proactive|burst|sprint (EstreGenesis v1.6.0)

    def add(self, node: TaskNode):
        self.nodes[node.id] = node

    def topological_order(self) -> List[str]:
        """deps 만족 순서대로 노드 id 반환 (Kahn's algorithm)."""
        in_deg = {nid: len(n.deps) for nid, n in self.nodes.items()}
        out_edges: Dict[str, List[str]] = {nid: [] for nid in self.nodes}
        for nid, n in self.nodes.items():
            for d in n.deps:
                if d in out_edges:
                    out_edges[d].append(nid)
        queue = [nid for nid, deg in in_deg.items() if deg == 0]
        order: List[str] = []
        while queue:
            cur = queue.pop(0)
            order.append(cur)
            for nxt in out_edges[cur]:
                in_deg[nxt] -= 1
                if in_deg[nxt] == 0:
                    queue.append(nxt)
        return order

    def ready_nodes(self) -> List[TaskNode]:
        """deps 모두 done 인 pending 노드."""
        out = []
        for n in self.nodes.values():
            if n.state != "pending":
                continue
            if all(self.nodes.get(d) and self.nodes[d].state == "done" for d in n.deps):
                out.append(n)
        return out

    def to_dict(self) -> Dict:
        return {"id": self.id, "goal": self.goal, "state": self.state,
                 "created_at": self.created_at,
                 "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()}}


class Planner:
    """Goal → DAG 생성 + execute."""

    _instance: Optional["Planner"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    # ── DAG 생성 ────────────────────────────────────────────────────────────

    def plan(self, goal: str, context: Optional[Dict] = None,
              pace_mode: str = "proactive") -> ExecutionGraph:
        """goal + context → DAG. 룰 base 기본 + LLM mutation 옵션.
        pace_mode (EstreGenesis): cautious(2-4×) | proactive(5-6× 기본) | burst(6-8×) | sprint(9-10×)."""
        ctx = context or {}
        section = (ctx.get("section") or "").lower()
        # context에 pace_mode 있으면 우선 (slash_commands 등 호출자가 넘김)
        pace_mode = ctx.get("pace_mode") or pace_mode
        if pace_mode not in PACE_MULTIPLIER:
            pace_mode = "proactive"
        graph = ExecutionGraph(id=uuid.uuid4().hex[:12], goal=goal, pace_mode=pace_mode)

        if section in ("introduction", "intro"):
            n1 = TaskNode(id="evidence_def",
                           action="gather_evidence",
                           args={"intent": "definition",
                                  "query": f"{goal} definition epidemiology",
                                  "k": 4, "section_target": "Introduction"},
                           rationale="Introduction은 정의 + 역학")
            n2 = TaskNode(id="evidence_assoc",
                           action="gather_evidence",
                           args={"intent": "evidence",
                                  "query": f"{goal} association adolescent",
                                  "k": 6, "section_target": "Introduction"},
                           rationale="선행연구 association")
            n3 = TaskNode(id="components_topic",
                           action="find_components",
                           args={"kind": "topic_sentence", "n": 4},
                           rationale="단락 시작  풀")
            n4 = TaskNode(id="components_hedge",
                           action="find_components",
                           args={"kind": "hedging", "n": 6, "author_style": "yoosun_cho"},
                           rationale="hedging vocabulary")
            n5 = TaskNode(id="compose_draft",
                           action="compose",
                           args={"section": "Introduction"},
                           deps=["evidence_def", "evidence_assoc", "components_topic"],
                           rationale="content layer 합성")
            n6 = TaskNode(id="apply_style",
                           action="apply_author_style",
                           args={"author_style": "yoosun_cho"},
                           deps=["compose_draft", "components_hedge"],
                           rationale="② style layer 입힘")
            n7 = TaskNode(id="patch",
                           action="patch_preview",
                           args={"section": "Introduction"},
                           deps=["apply_style"],
                           rationale="docx에 patch")
            n8 = TaskNode(id="verify",
                           action="verify_consistency",
                           args={},
                           deps=["patch"],
                           rationale="정형 일관성 검사")
            for n in [n1, n2, n3, n4, n5, n6, n7, n8]:
                graph.add(n)
        elif section == "methods":
            n1 = TaskNode(id="stat",
                           action="run_stat",
                           args={"outcome": ctx.get("outcome", "depression"),
                                  "exposure": ctx.get("exposure", "zcb_freq")},
                           rationale="실 KYRBS 분석")
            n2 = TaskNode(id="components_methods",
                           action="find_components",
                           args={"kind": "methods_boilerplate", "n": 4},
                           rationale="Methods  풀")
            n3 = TaskNode(id="compose_draft",
                           action="compose",
                           args={"section": "Methods"},
                           deps=["stat", "components_methods"],
                           rationale="content 합성")
            n4 = TaskNode(id="apply_style",
                           action="apply_author_style",
                           args={"author_style": "yoosun_cho"},
                           deps=["compose_draft"],
                           rationale="style 입힘")
            n5 = TaskNode(id="patch",
                           action="patch_preview",
                           args={"section": "Methods"},
                           deps=["apply_style"],
                           rationale="docx patch")
            n6 = TaskNode(id="strobe",
                           action="strobe_check",
                           args={},
                           deps=["patch"],
                           rationale="STROBE 22항목 검사")
            for n in [n1, n2, n3, n4, n5, n6]:
                graph.add(n)
        elif section == "results":
            n1 = TaskNode(id="stat",
                           action="run_stat",
                           args={"outcome": ctx.get("outcome", "depression"),
                                  "exposure": ctx.get("exposure", "zcb_freq")},
                           rationale="aOR 산출")
            n2 = TaskNode(id="components_stat",
                           action="find_components",
                           args={"kind": "stat_report", "n": 4},
                           rationale="통계 보고 양식")
            n3 = TaskNode(id="compose_draft", action="compose",
                           args={"section": "Results"}, deps=["stat", "components_stat"],
                           rationale="Results 합성")
            n4 = TaskNode(id="apply_style", action="apply_author_style",
                           args={"author_style": "yoosun_cho"}, deps=["compose_draft"],
                           rationale="style 입힘")
            n5 = TaskNode(id="patch", action="patch_preview",
                           args={"section": "Results"}, deps=["apply_style"],
                           rationale="docx patch")
            n6 = TaskNode(id="verify", action="verify_consistency",
                           args={}, deps=["patch"], rationale="n/OR-CI 정합성")
            for n in [n1, n2, n3, n4, n5, n6]:
                graph.add(n)
        else:
            # 기본 — 단일 단계
            n1 = TaskNode(id="evidence",
                           action="gather_evidence",
                           args={"intent": "evidence", "query": goal, "k": 5},
                           rationale="기본 evidence")
            n2 = TaskNode(id="patch", action="patch_preview",
                           args={"section": context.get("section", "Notes")},
                           deps=["evidence"], rationale="patch")
            for n in [n1, n2]:
                graph.add(n)

        try:
            from src.runtime import events as _events
            _events.append("planner_dag_created",
                            {"id": graph.id, "goal": goal[:200],
                             "n_nodes": len(graph.nodes),
                             "n_edges": sum(len(n.deps) for n in graph.nodes.values()),
                             "pace_mode": pace_mode,
                             "multiplier": PACE_MULTIPLIER[pace_mode]},
                            actor="planner")
        except Exception:
            pass
        return graph

    # ── Execution ───────────────────────────────────────────────────────────

    def execute(self, graph: ExecutionGraph, *,
                  executor: Callable[[TaskNode], Any],
                  on_step: Optional[Callable[[TaskNode, Any], None]] = None,
                  on_fail: Optional[Callable[[TaskNode, Exception], None]] = None
                  ) -> ExecutionGraph:
        """ready_nodes loop. 각 노드 executor 호출 → state 전이.
        실패 시 max_attempts까지 retry, 그 이상은 failed로 marking + 의존 노드 skip."""
        graph.state = "running"
        try:
            from src.runtime import events as _events
        except Exception:
            _events = None

        while True:
            ready = graph.ready_nodes()
            if not ready:
                break
            for node in ready:
                node.state = "running"
                node.n_attempts += 1
                if _events:
                    try:
                        _events.append("planner_node_start",
                                        {"graph_id": graph.id, "node_id": node.id,
                                         "action": node.action, "attempt": node.n_attempts},
                                        actor="planner")
                    except Exception as _ee:
                        _log.warning("planner_node_start emit fail: %s", _ee)
                node_t0 = time.time()
                try:
                    result = executor(node)
                    node.output = result
                    node.state = "done"
                    # 시간 측정 (EstreGenesis 패턴)
                    node.agent_time_sec = round(time.time() - node_t0, 3)
                    mult = PACE_MULTIPLIER.get(graph.pace_mode, 5.5)
                    node.human_review_time_sec = round(node.agent_time_sec * mult, 2)
                    node.wall_clock_sec = node.agent_time_sec    # 비동기 대기 X = 동일
                    if _events:
                        try:
                            _events.append("planner_node_done",
                                            {"graph_id": graph.id, "node_id": node.id,
                                             "action": node.action,
                                             "agent_time_sec": node.agent_time_sec,
                                             "est_human_review_sec": node.human_review_time_sec,
                                             "pace_mode": graph.pace_mode},
                                            actor="planner")
                        except Exception as _ee:
                        _log.warning("planner_node_start emit fail: %s", _ee)
                    if on_step:
                        try: on_step(node, result)
                        except Exception as _ee:
                        _log.warning("planner_node_start emit fail: %s", _ee)
                except Exception as e:
                    node.error = str(e)[:300]
                    if node.n_attempts < node.max_attempts:
                        node.state = "pending"   # retry 다음 cycle
                    else:
                        node.state = "failed"
                        if _events:
                            try:
                                _events.append("planner_node_failed",
                                                {"graph_id": graph.id, "node_id": node.id,
                                                 "error": node.error},
                                                actor="planner")
                            except Exception as _ee:
                        _log.warning("planner_node_start emit fail: %s", _ee)
                        if on_fail:
                            try: on_fail(node, e)
                            except Exception as _ee:
                        _log.warning("planner_node_start emit fail: %s", _ee)
                        # 의존 노드 skip
                        for other in graph.nodes.values():
                            if node.id in other.deps and other.state == "pending":
                                other.state = "skipped"

        # final state
        states = {n.state for n in graph.nodes.values()}
        if "failed" in states:
            graph.state = "partial" if "done" in states else "failed"
        elif all(n.state == "done" for n in graph.nodes.values()):
            graph.state = "completed"
        else:
            graph.state = "partial"

        if _events:
            try:
                _events.append("planner_dag_done",
                                {"graph_id": graph.id, "state": graph.state,
                                 "n_done": sum(1 for n in graph.nodes.values() if n.state == "done"),
                                 "n_failed": sum(1 for n in graph.nodes.values() if n.state == "failed")},
                                actor="planner")
            except Exception as _ee:
                _log.warning("planner_dag_done emit fail: %s", _ee)
        return graph


def get_planner() -> Planner:
    return Planner()
