"""Audit Trail — safety 이벤트 + compliance 리포트.

events.py(append-only) 위에 safety 전용 query/리포트 레이어.
HIPAA/IRB 등 compliance 요구사항 대응 시 활용.
"""
from __future__ import annotations

import time
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)


# safety 이벤트 타입 표준 (events.append 시 type 값)
SAFETY_TYPES = {
    "physician_review_queued",
    "physician_review_decided",
    "citation_grounding_failed",
    "memory_rejected",        # 환각 차단
    "memory_quarantined",
    "hallucination_marker_detected",
    "truth_level_blocked",    # TEMP가 컨텍스트 주입 시도
    "budget_exhausted",
    "contradiction_resolved",
}


def record_safety_event(type: str, payload: dict | None = None,
                        actor: str = "safety", task_id: str | None = None) -> int:
    """safety 표준 type 검증 + 일반 events.append."""
    if type not in SAFETY_TYPES:
        _log.debug("safety event 비표준 type: %s", type)
    return _events.append(type, payload or {}, actor=actor, task_id=task_id)


def get_safety_events(since_ts: float | None = None, type: str | None = None,
                      limit: int = 200) -> list:
    """safety 관련 이벤트만 필터해서 반환."""
    if type:
        return _events.find(type=type, since_ts=since_ts, limit=limit)
    # 여러 type — 합쳐서 시간순 정렬
    out: list = []
    for t in SAFETY_TYPES:
        out.extend(_events.find(type=t, since_ts=since_ts, limit=limit))
    out.sort(key=lambda e: e.get("ts", 0), reverse=True)
    return out[:limit]


def compliance_report(window_days: int = 30) -> dict:
    """최근 N일 compliance 요약 — physician review 비율, 환각 차단 카운트, 충돌 해결 등."""
    since = time.time() - window_days * 86400
    out = {"window_days": window_days, "since_ts": since, "counts": {}}
    for t in SAFETY_TYPES:
        rows = _events.find(type=t, since_ts=since, limit=10000)
        out["counts"][t] = len(rows)

    # 파생 메트릭
    q = out["counts"].get("physician_review_queued", 0)
    d = out["counts"].get("physician_review_decided", 0)
    out["physician_review_pending_estimate"] = max(0, q - d)
    out["hallucination_blocks"] = (out["counts"].get("memory_rejected", 0) +
                                    out["counts"].get("memory_quarantined", 0) +
                                    out["counts"].get("hallucination_marker_detected", 0))
    out["citation_failures"] = out["counts"].get("citation_grounding_failed", 0)
    out["budget_exhaustions"] = out["counts"].get("budget_exhausted", 0)

    # 헬스 신호
    healthy = (out["physician_review_pending_estimate"] < 50
               and out["citation_failures"] == 0)
    out["healthy"] = healthy
    out["summary"] = (f"{window_days}d: hallu_blocks={out['hallucination_blocks']}, "
                      f"review_pending~{out['physician_review_pending_estimate']}, "
                      f"citation_fail={out['citation_failures']}, "
                      f"healthy={healthy}")
    return out
