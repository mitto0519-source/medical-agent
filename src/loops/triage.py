"""Triage Inbox — backlog/events/change_log를 합성한 4분류 우선순위 큐.

기존 자산:
  src/runtime/backlog.py  — enqueue/drain (handlers 6종)
  src/runtime/events.py   — append-only audit
  src/memory/change_log.py — 작업 이력
모두 그대로. triage는 정렬·분류 view만 추가.

4 분류:
  urgent: physician_review 대기 / 통계 실패 retry / safety violation
  today:  사용자 응답 필요 / 골드셋 라벨 후보 / promote 승인 대기
  soon:   confidence 낮은 결과 / 검토 미수행 알림
  background: 인제스트 진행 / 자동 cron 실행 중
"""
from __future__ import annotations

import time
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def _backlog_items(limit: int = 50) -> List[Dict]:
    try:
        from src.runtime import backlog as _bl
        if hasattr(_bl, "list_pending"):
            return _bl.list_pending(limit=limit)
        if hasattr(_bl, "status"):
            s = _bl.status()
            if isinstance(s, dict) and "pending" in s:
                return list(s["pending"])[:limit]
    except Exception as e:
        _log.debug("backlog list fail: %s", e)
    return []


def _recent_events(n: int = 30, types: Optional[List[str]] = None) -> List[Dict]:
    try:
        from src.runtime import events as _e
        if types:
            out = []
            for t in types:
                out.extend(_e.find(type=t, limit=n // max(1, len(types))) or [])
            return out
        return _e.recent(n=n)
    except Exception as e:
        _log.debug("events fetch fail: %s", e)
        return []


def _physician_review_pending() -> List[Dict]:
    try:
        items = _recent_events(n=50, types=["physician_review_required"])
        return [
            {"kind": "physician_review", "ts": e.get("ts"),
              "title": (e.get("payload") or {}).get("title", "")[:120],
              "task_id": e.get("task_id")}
            for e in items
        ]
    except Exception:
        return []


def _failed_jobs() -> List[Dict]:
    try:
        items = _recent_events(n=30, types=["job_failed", "stat_fail"])
        return [
            {"kind": "failed", "ts": e.get("ts"),
              "reason": (e.get("payload") or {}).get("reason", "")[:120]}
            for e in items
        ]
    except Exception:
        return []


def _gold_set_candidates() -> List[Dict]:
    """SELF_EVOLUTION §2 — 골드셋 라벨 대기 후보."""
    try:
        import json
        from pathlib import Path
        gs = json.loads(Path("eval/gold_set.json").read_text(encoding="utf-8"))
        unlabelled = [
            p for p in (gs.get("claim_evidence_pairs") or [])
            if (p.get("label") or "").startswith("TODO")
        ]
        return [{"kind": "gold_label", "id": p.get("id"),
                  "claim": (p.get("claim") or "")[:120]}
                  for p in unlabelled[:10]]
    except Exception:
        return []


def _promotion_holds() -> List[Dict]:
    """SELF_EVOLUTION §4 — gate decision='hold' (사람 승인 대기)."""
    try:
        items = _recent_events(n=30, types=["evolution_gate_result"])
        return [
            {"kind": "promotion_hold", "ts": e.get("ts"),
              "candidate_event_id": (e.get("payload") or {}).get("candidate_event_id")}
            for e in items
            if (e.get("payload") or {}).get("decision") == "hold"
        ]
    except Exception:
        return []


def _ingest_in_progress() -> List[Dict]:
    """data/logs/ingest_full.log 진행 상황."""
    from pathlib import Path
    out: List[Dict] = []
    log = Path("data/logs/ingest_full.log")
    if log.exists():
        try:
            lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
            last = lines[-1] if lines else ""
            out.append({"kind": "ingest", "last_line": last[:200],
                          "log_size_kb": log.stat().st_size // 1024})
        except Exception:
            pass
    return out


def inbox(owner_email: Optional[str] = None) -> Dict[str, List[Dict]]:
    """4 카테고리 분류된 inbox 반환 (Lovable 양식 사이드바 위젯용)."""
    urgent = _physician_review_pending() + _failed_jobs()
    today = _gold_set_candidates() + _promotion_holds()
    soon = []
    background = _backlog_items(limit=10) + _ingest_in_progress()
    return {
        "urgent": urgent[:5],
        "today": today[:5],
        "soon": soon[:5],
        "background": background[:5],
        "totals": {"urgent": len(urgent), "today": len(today),
                     "soon": len(soon), "background": len(background)},
    }


__all__ = ["inbox"]
