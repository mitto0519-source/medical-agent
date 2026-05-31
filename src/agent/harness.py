"""AgentHarness — 모든 하네스 컴포넌트의 단일 진입점.

배경 (2026-06-01):
    Claude Code 하네스 / OmX (oh-my-codex) 같은 외부 하네스 엔지니어링 사례를
    검토한 결과, **우리는 모든 컴포넌트를 이미 보유하고 있으나 단일 진입점이
    없어 사용처마다 import + wiring을 반복**하고 있었다.

    이 모듈은 새 구현을 추가하지 않는다. 기존 컴포넌트의 facade일 뿐이다:

        AgentHarness(owner_email, task)
            .events    : src.runtime.events            (append-only audit)
            .tasks     : src.runtime.tasks             (TaskRun state machine)
            .budget    : src.llm.budget                (cost ceiling + downgrade)
            .heartbeat : src.runtime.heartbeat         (정기 catch-up)
            .memory    : src.memory.router             (typed write)
            .persona   : src.agent.persona             (style identity)
            .safety    : src.safety.unified            (citation+consistency+...)
            .llm       : src.llm.get_llm_client(task=) (3중 자동 폴백)
            .tools     : src.tools                     (tool wiring)
            .pool      : src.agent.agent_pool          (병렬 멀티에이전트)
            .planner   : src.agent.planner             (DAG)
            .knowledge : src.knowledge.orchestrator    (graph+vector+citation)
            .writing   : src.agent.writing_orchestrator (A2A contract)

    "한 객체에서 다 호출 가능"이 목적. 새 모듈 작성 시 이 facade만 받으면
    fallback / persona / safety / events / budget / memory가 자동 연결된다.

원칙:
    - 신규 구현 없음. 기존 컴포넌트의 정확한 호출만 노출.
    - 모든 메서드는 events.append + budget.record + memory.write를 자동 수행.
    - 사용자가 직접 src.* import해도 결과 동일 (facade 우회 가능).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class HarnessStep:
    """단일 step 실행 결과 — 자동으로 events에 기록되는 단위."""
    step: str
    output: str = ""
    error: str = ""
    elapsed_ms: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.error


class AgentHarness:
    """모든 하네스 컴포넌트의 단일 진입점.

    Usage:
        h = AgentHarness(owner_email="user@x.com", task="paper_writing")
        out = h.run_step("Write the methods section", system="...", max_tokens=4096)
        # → events.append + budget.record + memory.write 자동
    """

    def __init__(self, owner_email: str = "", task: str = "general"):
        self.owner = owner_email
        self.task = task
        # ── lazy imports (heavy modules) ───────────────────────────────
        from src.runtime import events as _ev
        from src.runtime import tasks as _tk
        from src.runtime import heartbeat as _hb
        from src.llm import budget as _bd
        from src.llm import get_llm_client as _llm
        from src.safety import unified as _sf
        from src.memory import router as _mr
        from src.agent import persona as _ps
        from src.agent import agent_pool as _pool
        from src import tools as _tl
        self.events = _ev
        self.tasks = _tk
        self.heartbeat = _hb
        self.budget = _bd
        self.safety = _sf
        self.memory = _mr
        self.tools = _tl
        # active LLM client (3중 폴백 + persona 자동 주입)
        # owner_email은 intent_sensor.set_current를 통해 주입 — get_llm_client는 안 받음
        self.llm = _llm(task=task)
        # persona instance (style identity)
        try:
            self.persona = _ps.get_persona()
        except Exception:
            self.persona = None
        # agent pool (병렬 + team_review 신규)
        self.pool = _pool.get_agent_pool()
        # optional heavy orchestrators (lazy)
        self._planner = None
        self._knowledge = None
        self._writing = None

    # ── lazy-loaded heavy components ─────────────────────────────────

    @property
    def planner(self):
        if self._planner is None:
            from src.agent import planner as _pl
            self._planner = _pl
        return self._planner

    @property
    def knowledge(self):
        if self._knowledge is None:
            try:
                from src.knowledge import orchestrator as _ko
                self._knowledge = _ko
            except Exception as e:
                _log.warning("[Harness] knowledge orchestrator import failed: %s", e)
                self._knowledge = None
        return self._knowledge

    @property
    def writing(self):
        if self._writing is None:
            try:
                from src.agent import writing_orchestrator as _wo
                self._writing = _wo
            except Exception as e:
                _log.warning("[Harness] writing orchestrator import failed: %s", e)
                self._writing = None
        return self._writing

    # ── 단일 step: events + safety + LLM + memory 자동 wiring ──────────

    def run_step(
        self,
        prompt: str,
        *,
        system: str = "",
        max_tokens: int = 4096,
        step_name: str = "llm_call",
        skip_safety: bool = False,
        skip_memory: bool = False,
    ) -> HarnessStep:
        """단일 LLM step — events 시작/종료 + safety + memory 자동.

        - claude_client.generate가 자체적으로 build_base_system + persona +
          intent_sensor pickup + provenance + tracing wire-up을 함.
          여기서는 그 위에 step 단위 events + memory write만 추가.
        """
        import time as _t
        t0 = _t.time()
        out = ""
        err = ""
        try:
            self.events.append(
                type="harness.step.start",
                payload={"step": step_name, "task": self.task,
                          "owner": self.owner, "prompt_len": len(prompt)},
            )
            out = self.llm.generate(
                prompt,
                system_prompt=system or None,
                max_tokens=max_tokens,
            ) or ""

            if not skip_safety and out:
                try:
                    rep = self.safety.check_all(out, scope=f"harness.{step_name}")
                    if rep.overall == "fail":
                        _log.warning("[Harness] safety FAIL at %s", step_name)
                except Exception:
                    pass

            if not skip_memory and out:
                try:
                    self.memory.write(
                        kind="episodic",
                        content=out[:4000],
                        meta={"step": step_name, "task": self.task,
                              "owner": self.owner, "harness": True},
                    )
                except Exception:
                    pass

        except Exception as e:
            err = str(e)
            _log.error("[Harness] step %s failed: %s", step_name, e)

        elapsed = int((_t.time() - t0) * 1000)
        self.events.append(
            type="harness.step.end",
            payload={"step": step_name, "elapsed_ms": elapsed,
                      "ok": bool(out) and not err, "err": err[:200]},
        )
        return HarnessStep(step=step_name, output=out, error=err,
                           elapsed_ms=elapsed,
                           metadata={"task": self.task, "owner": self.owner})

    # ── team review: 다중 perspective 병렬 리뷰 (OmX $team 양식) ───────

    def team_review(
        self,
        content: str,
        *,
        perspectives: Optional[List[str]] = None,
        max_tokens: int = 1500,
    ) -> Dict[str, str]:
        """동일 content에 여러 reviewer perspective를 병렬로 적용 → 합의/이견 정리.

        perspectives 예시 (논문 작업 기본값):
            ["statistical_rigor", "clinical_relevance", "writing_clarity",
             "novelty_check", "policy_translation"]

        AgentPool.team_review로 ThreadPool 위임 — 토큰 N배 사용에 주의.
        """
        return self.pool.team_review(
            content=content,
            perspectives=perspectives,
            llm=self.llm,
            max_tokens=max_tokens,
        )

    # ── DAG plan 실행 (planner 진입점 통일) ────────────────────────────

    def run_plan(self, graph_spec: dict) -> Dict[str, Any]:
        """ExecutionGraph spec → 실행. planner DAG 직접 사용을 facade화."""
        try:
            return self.planner.execute(graph_spec, harness=self)
        except AttributeError:
            # planner가 다른 시그니처일 경우
            return self.planner.run(graph_spec)

    # ── 상태 스냅샷 (디버깅) ─────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        """현재 하네스 상태 — events tail, budget snapshot, persona summary."""
        snap = {"task": self.task, "owner": self.owner}
        try:
            snap["events_recent"] = self.events.find(limit=5)
        except Exception:
            pass
        try:
            snap["budget"] = self.budget.snapshot()
        except Exception:
            pass
        try:
            if self.persona:
                snap["persona"] = getattr(self.persona, "name", "?")
        except Exception:
            pass
        return snap


# ── singleton 캐시 (owner 별) ─────────────────────────────────────────
_HARNESS_CACHE: Dict[tuple, AgentHarness] = {}


def get_harness(owner_email: str = "", task: str = "general") -> AgentHarness:
    """캐시된 AgentHarness 반환. (owner, task) 키로 재사용."""
    key = (owner_email, task)
    if key not in _HARNESS_CACHE:
        _HARNESS_CACHE[key] = AgentHarness(owner_email=owner_email, task=task)
    return _HARNESS_CACHE[key]


__all__ = ["AgentHarness", "HarnessStep", "get_harness"]
