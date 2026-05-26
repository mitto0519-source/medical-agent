"""Heartbeat — 정기 작업 단일 진입점 (분 단위 polling + 부팅 catch-up).

설계:
  - 부팅 시 last_run 확인 → interval 지난 job은 즉시 실행 (anacron 식)
  - 짧은 sleep 루프로 분 단위 트리거
  - 각 job은 idempotent — 실패해도 다음 사이클로 (예외는 swallow + events에 기록)
  - data/runtime/heartbeat_state.json에 {job_name: last_run_ts} 영속

JOBS:
  task_recover     1h   — stale RUNNING TaskRun을 RETRYING으로
  lifecycle_tick   24h  — confidence decay + 만료 archive
  idempotency_gc   6h   — 만료 캐시 정리
  budget_snapshot  1h   — 사용량 events 기록 (대시보드용)
  trend_learn      24h  — 외부 학습 (기존 learn_scheduler 흡수)

실행: python -m src.runtime.heartbeat   (learner 컨테이너에서)
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)
_STATE_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "heartbeat_state.json"
_TICK_SECONDS = int(os.environ.get("HEARTBEAT_TICK_SEC", "60"))   # polling 주기 (기본 1분)


@dataclass
class Job:
    name: str
    interval_sec: int
    fn: Callable[[], dict | None]
    catchup_on_boot: bool = True


def _load_state() -> dict:
    if _STATE_PATH.exists():
        try: return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    return {}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _run_job(job: Job, state: dict, reason: str) -> None:
    started = time.time()
    eid = _events.append("job_start", {"job": job.name, "reason": reason}, actor="heartbeat")
    try:
        result = job.fn() or {}
        _events.append("job_done", {"job": job.name, "duration_sec": round(time.time() - started, 2),
                                     "result": result}, parent_event_id=eid, actor="heartbeat")
        _log.info("heartbeat job=%s ok %.2fs %s", job.name, time.time() - started, result)
    except Exception as e:
        _events.append("job_error", {"job": job.name, "error": str(e)[:300]},
                       parent_event_id=eid, actor="heartbeat")
        _log.warning("heartbeat job=%s 실패: %s", job.name, e)
    state[job.name] = time.time()
    _save_state(state)


# ── Job 콜백 ─────────────────────────────────────────────────────────────────

def _job_task_recover() -> dict:
    from src.runtime.tasks import TaskRun
    n = TaskRun.recover_stale()
    return {"recovered": n}


def _job_lifecycle_tick() -> dict:
    from src.memory.lifecycle import tick
    return tick()


def _job_idempotency_gc() -> dict:
    from src.runtime.idempotency import gc, stats
    n = gc()
    return {"purged": n, "stats": stats()}


def _job_budget_snapshot() -> dict:
    from src.llm.budget import snapshot
    snap = snapshot()
    _events.append("budget_snapshot", snap, actor="budget")
    return {"day_pct_used": snap["day"]["pct_used"], "day_cost_usd": snap["day"]["cost_usd"]}


def _job_trend_learn() -> dict:
    """기존 trend_learner 흡수 (있을 때만). 함수명은 run_trend_learn."""
    try:
        from src.knowledge.trend_learner import run_trend_learn
    except Exception as e:
        return {"skipped": f"trend_learner import 실패: {str(e)[:80]}"}
    try:
        out = run_trend_learn()
        return out if isinstance(out, dict) else {"ok": True}
    except Exception as e:
        return {"error": str(e)[:200]}


JOBS = [
    Job("task_recover",     interval_sec=3600,      fn=_job_task_recover),
    Job("budget_snapshot",  interval_sec=3600,      fn=_job_budget_snapshot),
    Job("idempotency_gc",   interval_sec=6 * 3600,  fn=_job_idempotency_gc),
    Job("lifecycle_tick",   interval_sec=24 * 3600, fn=_job_lifecycle_tick),
    Job("trend_learn",      interval_sec=24 * 3600, fn=_job_trend_learn),
]


# ── 메인 루프 ─────────────────────────────────────────────────────────────────

_RUNNING = True


def _stop(*_):
    global _RUNNING; _RUNNING = False


def run(jobs: list[Job] = JOBS, *, once: bool = False) -> None:
    """heartbeat 메인 루프. once=True면 catch-up만 하고 종료(테스트용)."""
    state = _load_state()
    now = time.time()

    # 부팅 catch-up
    for j in jobs:
        last = state.get(j.name, 0.0)
        if j.catchup_on_boot and (now - last) >= j.interval_sec:
            _run_job(j, state, reason="catchup")

    if once:
        return

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    _log.info("heartbeat 시작 (tick=%ds, jobs=%d)", _TICK_SECONDS, len(jobs))

    while _RUNNING:
        time.sleep(_TICK_SECONDS)
        now = time.time()
        state = _load_state()
        for j in jobs:
            last = state.get(j.name, 0.0)
            if (now - last) >= j.interval_sec:
                _run_job(j, state, reason="scheduled")


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Medical-Agent runtime heartbeat")
    ap.add_argument("--once", action="store_true", help="catch-up만 하고 종료 (테스트)")
    args = ap.parse_args()
    run(once=args.once)


if __name__ == "__main__":
    main()
