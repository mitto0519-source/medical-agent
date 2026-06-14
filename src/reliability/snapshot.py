"""Research State Snapshot — named checkpoint on events.db.

MASTER_UPGRADE §3 #4: events.db already append-only, provenance.fingerprint already exists.
This module names checkpoints (research_state_v1/v2/v3) and supports rollback to a labelled point.

API:
    save(project_id, label, state) -> snapshot_id
    list(project_id) -> list[{snapshot_id, label, ts, state_keys}]
    load(snapshot_id) -> state dict
    rollback_to(project_id, label) -> state dict
    diff(snapshot_id_a, snapshot_id_b) -> {added, removed, changed}
"""
from __future__ import annotations

import json
import time
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events
from src.runtime import provenance as _prov

_log = get_logger(__name__)


def save(project_id: str, label: str, state: dict, *,
          actor: Optional[str] = None) -> Optional[int]:
    """Append a named snapshot to events.db. Returns event_id (snapshot_id) or None.

    label examples: "rq_locked", "vars_chosen", "stat_done", "draft_v1",
                    "writer_done", "reviewer_passed"
    """
    fp = _prov.build_fingerprint(
        scope="snapshot",
        extra={
            "project_id": project_id,
            "label": label,
            "state_keys": sorted(list(state.keys())) if isinstance(state, dict) else [],
        },
    )
    payload = {
        "project_id": project_id,
        "label": label,
        "state": state,
        "fingerprint": fp,
        "ts": time.time(),
    }
    try:
        return _events.append(
            type="research_snapshot",
            payload=payload,
            task_id=project_id,
            actor=actor or "snapshot",
        )
    except Exception as e:
        _log.warning("snapshot.save fail: %s", e)
        return None


def list_snapshots(project_id: str, *, limit: int = 50) -> List[Dict]:
    """All snapshots for a project, newest first."""
    try:
        items = _events.find(type="research_snapshot", task_id=project_id,
                                limit=limit * 4)
    except Exception as e:
        _log.warning("snapshot.list find fail: %s", e)
        return []
    out: List[Dict] = []
    for ev in items:
        pl = ev.get("payload") or {}
        if pl.get("project_id") != project_id:
            continue
        out.append({
            "snapshot_id": ev.get("id"),
            "label": pl.get("label"),
            "ts": pl.get("ts") or ev.get("ts"),
            "state_keys": (pl.get("fingerprint") or {}).get("state_keys", []),
        })
        if len(out) >= limit:
            break
    return out


def load(snapshot_id: int) -> Optional[Dict]:
    """Full state dict for one snapshot."""
    try:
        import sqlite3
        c = _events._conn()
        row = c.execute(
            "SELECT payload_json FROM events WHERE id=? AND type='research_snapshot'",
            (snapshot_id,),
        ).fetchone()
        if row:
            pl = json.loads(row[0])
            return pl.get("state")
    except Exception as e:
        _log.warning("snapshot.load fail: %s", e)
    return None


def rollback_to(project_id: str, label: str) -> Optional[Dict]:
    """Find most-recent snapshot with given label, return its state (caller applies it).

    Does NOT mutate events.db (append-only). Caller should call save() again with
    label='rollback_from_<label>' after applying, for audit clarity.
    """
    snaps = list_snapshots(project_id, limit=200)
    for s in snaps:
        if s.get("label") == label:
            return load(s["snapshot_id"])
    return None


def diff(snapshot_id_a: int, snapshot_id_b: int) -> Dict:
    """Compare two snapshot states. Returns added/removed/changed key lists."""
    a = load(snapshot_id_a) or {}
    b = load(snapshot_id_b) or {}
    a_keys, b_keys = set(a.keys()), set(b.keys())
    added = sorted(b_keys - a_keys)
    removed = sorted(a_keys - b_keys)
    changed = sorted(k for k in (a_keys & b_keys) if a.get(k) != b.get(k))
    return {"added": added, "removed": removed, "changed": changed}


__all__ = ["save", "list_snapshots", "load", "rollback_to", "diff"]
