"""Replay CLI — `events.db`의 특정 task_id를 시간순 재구성해 환각/오류를 사후 추적.

기존 `src.runtime.events.replay(task_id)`가 raw events 리스트를 반환 → 본 스크립트가
정형 콘솔 리포트(LLM 호출/도구/메모리 쓰기/safety 이벤트 분류)로 정리.

사용:
    python scripts/replay_task.py --task=task-abc-123
    python scripts/replay_task.py --since=2026-05-27T08:00 --type=safety
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _short(s, n=120):
    s = str(s or "")
    return s if len(s) <= n else s[:n] + "…"


def _print_event(ev: dict):
    ts = ev.get("ts", "?")
    typ = ev.get("type", "?")
    actor = ev.get("actor", "")
    payload = ev.get("payload") or {}
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {"raw": payload}

    label_map = {
        "tool_call":              "🛠️  ",
        "tool_loop_end":          "✅ ",
        "safety":                 "⚠️  ",
        "memory_write":           "💾 ",
        "memory_gate_quarantine": "🚫 ",
        "llm_call":               "🤖 ",
        "llm_error":              "❌ ",
        "task_state":             "🔄 ",
    }
    icon = label_map.get(typ, "•  ")
    print(f"{icon}{ts}  {typ:28s} actor={actor:18s}  {_short(json.dumps(payload, ensure_ascii=False), 200)}")


def main():
    ap = argparse.ArgumentParser(description="Replay events from runtime/events.db")
    ap.add_argument("--task", help="task_id로 필터 (events.replay 사용)")
    ap.add_argument("--type", help="event type 필터 (예: safety, tool_call)")
    ap.add_argument("--actor", help="actor 필터")
    ap.add_argument("--limit", type=int, default=200)
    ap.add_argument("--since", help="ISO timestamp 이후만 (선택)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    from src.runtime import events as ev

    if args.task:
        rows = ev.replay(args.task)
    else:
        rows = ev.find(type=args.type, actor=args.actor, limit=args.limit)

    if args.since:
        rows = [r for r in rows if str(r.get("ts", "")) >= args.since]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
        return 0

    print("=" * 100)
    print(f"Replay — {len(rows)} events"
          f"{f' for task={args.task}' if args.task else ''}"
          f"{f' type={args.type}' if args.type else ''}")
    print("=" * 100)
    by_type: dict = {}
    for r in rows:
        by_type[r.get("type", "?")] = by_type.get(r.get("type", "?"), 0) + 1
        _print_event(r)
    print("-" * 100)
    print("요약:", ", ".join(f"{k}={v}" for k, v in sorted(by_type.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
