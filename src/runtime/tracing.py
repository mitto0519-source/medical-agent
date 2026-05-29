"""Distributed-style tracing — 한 task의 모든 spans를 events.db에 자동 적재.

배경:
    "이 결과가 어디서 왔는가"를 분 단위가 아니라 호출 단위로 보려면 span tree가 필요하다.
    OpenTelemetry 전체를 가져오긴 무거우니, events.db 위에 가벼운 trace_span을 얹는다.

API:
    with trace_span("paper_section.intro", model="claude-haiku") as sp:
        sp.set("tokens_in", 1200)
        ... LLM 호출 ...
        sp.set("tokens_out", 800)
    # 종료 시 자동으로 events.append("span_end", payload={..., latency_ms, status})

특징:
    - parent span 자동 추적 (contextvar 양식) — 중첩 호출도 부모-자식 관계 보존
    - status=ok/error 자동 (예외 시 error)
    - task_id 자동 전파 — 호출 트리 전체가 한 task_id 공유
    - events.append 기반 → events.replay(task_id)로 시간순 재구성 가능

호출 위치:
    - ClaudeClient.generate() 진입 → trace_span("llm.generate", provider, model, prompt_sha)
    - tools.run_tool() 진입 → trace_span("tool.{name}")
    - safety check_all() → trace_span("safety.check_all")
    - StatBridge.analyze() → trace_span("stat.analyze")
"""
from __future__ import annotations

import contextvars
import time
import uuid
from contextlib import contextmanager
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)

# Context vars — span 중첩과 task_id 전파를 위한 변수
_CURRENT_SPAN: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "trace_current_span", default=None,
)
_CURRENT_TASK: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "trace_current_task", default=None,
)


class Span:
    """단일 span — attrs를 set/get하고 종료 시 events.append('span_end')."""

    __slots__ = ("trace_id", "span_id", "parent_id", "name", "task_id",
                 "start_ts", "attrs", "_finished", "_event_id")

    def __init__(self, name: str, *, task_id: str | None = None, parent: "Span | None" = None,
                 attrs: dict | None = None):
        self.trace_id = parent.trace_id if parent else uuid.uuid4().hex[:16]
        self.span_id = uuid.uuid4().hex[:12]
        self.parent_id = parent.span_id if parent else None
        self.name = name
        self.task_id = task_id or (parent.task_id if parent else None)
        self.start_ts = time.time()
        self.attrs: dict = dict(attrs or {})
        self._finished = False
        self._event_id = -1
        # 시작 이벤트
        try:
            self._event_id = _events.append(
                type="span_start",
                payload={
                    "trace_id": self.trace_id, "span_id": self.span_id,
                    "parent_id": self.parent_id, "name": name,
                    "attrs": self.attrs,
                },
                task_id=self.task_id, actor=name,
            )
        except Exception:
            pass

    def set(self, key: str, value: Any) -> None:
        self.attrs[key] = value

    def update(self, **kwargs: Any) -> None:
        self.attrs.update(kwargs)

    def finish(self, status: str = "ok", error: str | None = None) -> None:
        if self._finished:
            return
        self._finished = True
        latency_ms = int((time.time() - self.start_ts) * 1000)
        payload = {
            "trace_id": self.trace_id, "span_id": self.span_id,
            "parent_id": self.parent_id, "name": self.name,
            "latency_ms": latency_ms, "status": status,
            "attrs": self.attrs,
        }
        if error:
            payload["error"] = str(error)[:240]
        try:
            _events.append(type="span_end", payload=payload,
                           task_id=self.task_id, actor=self.name,
                           parent_event_id=self._event_id if self._event_id > 0 else None)
        except Exception:
            pass


@contextmanager
def trace_span(name: str, *, task_id: str | None = None, **attrs):
    """context manager. 진입 시 span_start, 정상/예외 종료 시 span_end."""
    parent = _CURRENT_SPAN.get()
    sp = Span(name, task_id=task_id or _CURRENT_TASK.get(), parent=parent, attrs=attrs)
    tok_span = _CURRENT_SPAN.set(sp)
    tok_task = _CURRENT_TASK.set(sp.task_id) if sp.task_id else None
    try:
        yield sp
        sp.finish(status="ok")
    except Exception as e:
        sp.finish(status="error", error=str(e))
        raise
    finally:
        _CURRENT_SPAN.reset(tok_span)
        if tok_task is not None:
            _CURRENT_TASK.reset(tok_task)


def current_span() -> Span | None:
    return _CURRENT_SPAN.get()


def current_task_id() -> str | None:
    return _CURRENT_TASK.get()


def start_task(task_id: str | None = None) -> str:
    """현재 contextvar에 task_id 설정 (한 작업 전체를 묶어 replay 가능하게).

    반환값을 보관하고 끝나면 `end_task(token)` 호출.
    """
    tid = task_id or uuid.uuid4().hex[:16]
    token = _CURRENT_TASK.set(tid)
    return tid  # type: ignore[return-value]


# ── 분석 helpers — events.db 기반 trace tree 재구성 ─────────────────────────

def trace_tree(trace_id: str) -> list[dict]:
    """한 trace_id 에 속한 모든 span_start/span_end events. 시간순."""
    starts = _events.find(type="span_start", limit=2000)
    ends = _events.find(type="span_end", limit=2000)
    out = []
    for e in starts + ends:
        p = e.get("payload") or {}
        if p.get("trace_id") == trace_id:
            out.append(e)
    out.sort(key=lambda x: x.get("ts", 0) or x.get("id", 0))
    return out


def recent_traces(n: int = 20) -> list[dict]:
    """최근 trace들 — trace_id별 첫 span_start와 마지막 span_end 페어."""
    ends = _events.find(type="span_end", limit=n * 6)
    seen: dict[str, dict] = {}
    for e in ends:
        p = e.get("payload") or {}
        tid = p.get("trace_id")
        if tid and tid not in seen:
            seen[tid] = {
                "trace_id": tid, "name": p.get("name"),
                "latency_ms": p.get("latency_ms"), "status": p.get("status"),
                "ts": e.get("ts"), "task_id": e.get("task_id"),
            }
        if len(seen) >= n:
            break
    return list(seen.values())


__all__ = [
    "Span", "trace_span", "current_span", "current_task_id", "start_task",
    "trace_tree", "recent_traces",
]
