"""ChatEvent — single contract across service → API → Next.js.

Per FRONTEND_MIGRATION_SPEC §5.5.2. Every layer either emits, serializes, or renders
these events. No regex JSON parsing. No band-aid.

UI mapping per event type:
    status        — 좌측 활동 로그 한 줄
    plan          — 단계 칩 (진행바)
    tool_start    — 로그 + 패널 스피너
    tool_result   — 패널/프리뷰 삽입 (stat 표 / figure / refs)
    token         — 우측 프리뷰 해당 섹션 append
    section_done  — 섹션 완료 체크
    warning       — 인라인 배지 (survey_weight / citation)
    badge         — 사후 confidence/provenance 배지 (BACKGROUND lane)
    done          — 마무리
    error         — 에러 토스트
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from itertools import count
from typing import Any, Dict, Iterator, Literal

EventType = Literal["status", "plan", "tool_start", "tool_result", "token",
                     "section_done", "warning", "badge", "done", "error"]


_SEQ = count(1)


@dataclass
class ChatEvent:
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    ts: float = field(default_factory=time.time)
    seq: int = field(default_factory=lambda: next(_SEQ))

    def to_dict(self) -> dict:
        return asdict(self)

    def to_sse(self) -> str:
        """Server-Sent Events frame: `data: <json>\\n\\n`."""
        body = json.dumps({"type": self.type, "data": self.data,
                              "ts": self.ts, "seq": self.seq},
                             ensure_ascii=False)
        return f"id: {self.seq}\ndata: {body}\n\n"


# ── Convenience constructors (one-line emits) ────────────────────────────────

def status(msg: str, **extra) -> ChatEvent:
    return ChatEvent("status", {"msg": msg, **extra})


def plan(steps: list[str], **extra) -> ChatEvent:
    return ChatEvent("plan", {"steps": steps, **extra})


def tool_start(tool: str, args_brief: str = "", **extra) -> ChatEvent:
    return ChatEvent("tool_start", {"tool": tool, "args_brief": args_brief, **extra})


def tool_result(tool: str, payload: dict, **extra) -> ChatEvent:
    return ChatEvent("tool_result", {"tool": tool, "payload": payload, **extra})


def token(section: str, text: str, **extra) -> ChatEvent:
    return ChatEvent("token", {"section": section, "text": text, **extra})


def section_done(section: str, **extra) -> ChatEvent:
    return ChatEvent("section_done", {"section": section, **extra})


def warning(kind: str, msg: str, **extra) -> ChatEvent:
    return ChatEvent("warning", {"kind": kind, "msg": msg, **extra})


def badge(kind: str, value: Any, **extra) -> ChatEvent:
    return ChatEvent("badge", {"kind": kind, "value": value, **extra})


def done(**extra) -> ChatEvent:
    return ChatEvent("done", {**extra})


def error(where: str, msg: str, **extra) -> ChatEvent:
    return ChatEvent("error", {"where": where, "msg": msg, **extra})


__all__ = ["ChatEvent", "EventType",
            "status", "plan", "tool_start", "tool_result", "token",
            "section_done", "warning", "badge", "done", "error"]
