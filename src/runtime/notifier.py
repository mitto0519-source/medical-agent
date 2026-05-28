"""Notifier — Vision 다이어그램 '알림 시스템' (중요/경고/보고서).

events.db의 safety/regression/fail 이벤트를 수집 → 사용자가 봐야 할 알림 생성.
출력 채널 (다중 지원):
  · in_app: data/runtime/notifications.json (UI에서 polling)
  · log: 표준 logger
  · file: data/runtime/alerts.log
  · webhook(future): Slack/Discord/Email — 사용자가 .env에 URL 등록 시

Heartbeat에서 `notify_drain()`을 5min마다 호출 → 새 safety/regression/fail event를
notification에 자동 등록.

호출:
    from src.runtime.notifier import notify, list_unread, mark_read, notify_drain
    notify("warning", "5만편 학습 OA fetch fail 다수", source="oa_bulk")
    items = list_unread(limit=20)
    mark_read(item_id)
    notify_drain()   # heartbeat에서 자동
"""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_NOTIFY_PATH = Path("data/runtime/notifications.json")
_ALERT_LOG = Path("data/runtime/alerts.log")


# severity 정의
_SEVERITIES = ("info", "warning", "error", "critical")


def _load() -> List[Dict]:
    if not _NOTIFY_PATH.exists():
        return []
    try:
        return json.loads(_NOTIFY_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(items: List[Dict]):
    _NOTIFY_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        _NOTIFY_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2)[:1_000_000],
                                  encoding="utf-8")
    except Exception as e:
        _log.warning("notify save fail: %s", e)


def _append_log(severity: str, title: str, detail: str):
    _ALERT_LOG.parent.mkdir(parents=True, exist_ok=True)
    try:
        with _ALERT_LOG.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} [{severity.upper()}] {title}: {detail[:300]}\n")
    except Exception:
        pass


def notify(severity: str, title: str, detail: str = "",
            source: str = "system", payload: Optional[Dict] = None) -> str:
    """알림 추가. severity ∈ {info, warning, error, critical}. id 반환."""
    if severity not in _SEVERITIES:
        severity = "info"
    item_id = uuid.uuid4().hex[:12]
    record = {
        "id": item_id,
        "ts": time.time(),
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "severity": severity,
        "title": title[:200],
        "detail": detail[:1000],
        "source": source,
        "payload": payload or {},
        "read": False,
    }
    items = _load()
    items.insert(0, record)
    # 1000개 cap
    items = items[:1000]
    _save(items)
    _append_log(severity, title, detail)

    if severity in ("error", "critical"):
        _log.error("[notify:%s] %s — %s", severity, title, detail[:200])
    elif severity == "warning":
        _log.warning("[notify:warning] %s — %s", title, detail[:200])
    else:
        _log.info("[notify:%s] %s", severity, title)

    # webhook (옵션 — Slack/Discord)
    try:
        import os
        url = os.environ.get("NOTIFY_WEBHOOK_URL")
        if url and severity in ("warning", "error", "critical"):
            import urllib.request as _ur
            req = _ur.Request(
                url, method="POST",
                data=json.dumps({"text": f"[{severity}] {title}\n{detail[:400]}",
                                  "source": source}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )
            _ur.urlopen(req, timeout=5).close()
    except Exception as e:
        _log.debug("webhook fail: %s", e)

    return item_id


def list_unread(*, limit: int = 50, severity: Optional[str] = None) -> List[Dict]:
    items = _load()
    out = [it for it in items if not it.get("read")]
    if severity:
        out = [it for it in out if it.get("severity") == severity]
    return out[:limit]


def list_all(*, limit: int = 200) -> List[Dict]:
    return _load()[:limit]


def mark_read(item_id: str) -> bool:
    items = _load()
    changed = False
    for it in items:
        if it.get("id") == item_id and not it.get("read"):
            it["read"] = True
            it["read_ts"] = time.time()
            changed = True
            break
    if changed:
        _save(items)
    return changed


def mark_all_read() -> int:
    items = _load()
    n = sum(1 for it in items if not it.get("read"))
    for it in items:
        if not it.get("read"):
            it["read"] = True
            it["read_ts"] = time.time()
    _save(items)
    return n


# ── Drain — events.db의 safety/regression/fail을 notification으로 흡수 ──────

def notify_drain(*, lookback_min: int = 10) -> Dict:
    """events.db의 최근 safety/fail/regression event를 notification으로 변환.
    heartbeat에서 매 5분 호출. 같은 event 중복 변환 방지를 위해 state cache 사용."""
    from src.runtime import events as _ev
    state_path = Path("data/runtime/notify_drain_state.json")
    state = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except Exception:
            state = {}
    last_ts = float(state.get("last_ts", 0))
    now = time.time()
    since = max(last_ts, now - lookback_min * 60)

    n_created = 0
    seen_ids = set(state.get("seen_ids", []))

    # safety event 자동 변환
    for typ, sev in [
        ("safety", "warning"),
        ("memory_quarantined", "warning"),
        ("memory_schema_invalid", "warning"),
        ("longitudinal_regression", "error"),
        ("backlog_failed", "error"),
        ("citation_grounding_failed", "warning"),
        ("consistency_check_fail", "warning"),
        ("causal_claim_violation", "warning"),
        ("budget_exhausted", "critical"),
        ("planner_node_failed", "warning"),
    ]:
        try:
            rows = _ev.find(type=typ, limit=50, since_ts=since)
        except TypeError:
            # 일부 events.find 시그니처 차이
            try:
                rows = _ev.find(type=typ, limit=50)
                rows = [r for r in rows if float(str(r.get("ts", 0)).replace("Z","").replace("T"," ")[:19].replace("-","").replace(":","").replace(" ","") or 0) > 0]
            except Exception:
                rows = []
        for r in rows:
            rid = str(r.get("id") or r.get("ts", ""))
            if rid in seen_ids:
                continue
            seen_ids.add(rid)
            pl = r.get("payload") or {}
            detail = json.dumps(pl, ensure_ascii=False)[:400] if isinstance(pl, dict) else str(pl)[:400]
            notify(sev, f"{typ}", detail=detail, source="event_drain", payload=pl)
            n_created += 1

    state["last_ts"] = now
    state["seen_ids"] = list(seen_ids)[-2000:]
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass

    return {"n_created": n_created, "lookback_min": lookback_min,
            "checked_types": 10}


def stats() -> Dict:
    items = _load()
    by_sev: Dict[str, int] = {}
    n_unread = 0
    for it in items:
        s = it.get("severity", "info")
        by_sev[s] = by_sev.get(s, 0) + 1
        if not it.get("read"):
            n_unread += 1
    return {"total": len(items), "unread": n_unread, "by_severity": by_sev}
