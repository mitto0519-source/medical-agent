"""Memory Router — 모든 메모리 쓰기의 단일 진입점.

조립:
  text → memory_gate.assess (기존: 짧음/환각마커/중복 1차 거름)
       → scorer.score + scorer.gate (신규성/재출현/중요도/신뢰도)
       → 라우팅(type별 저장소):
            episodic   → SQLite events ("memory_episodic" 타입)
            semantic   → ChromaDB vectorstore (컬렉션 type/source 분리)
            procedural → data/agent_self/rules.json (append-only)
            goal       → data/agent_self/goals.json (id별 upsert)
       → events("memory_write", payload) 감사 로그

호출부(기존 코드)는 이 라우터 한 줄로 교체 가능:
  change_log.log(...) 내부 → memory.write(type="episodic", source="observation", ...)
  conversation_memory.record(...) 내부 → memory.write(type="episodic", source="user", ...)

설계 원칙:
  - 라우터는 부수효과 안전(저장 실패해도 호출자 망가지지 않음)
  - 모든 쓰기는 events에 감사 기록 → replay로 무엇이 왜 저장됐는지 추적 가능
"""
from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Iterable, Literal

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)

_AGENT_DIR = Path(os.environ.get("AGENT_SELF_DIR", "data/agent_self"))
_RULES_PATH = _AGENT_DIR / "rules.json"
_GOALS_PATH = _AGENT_DIR / "goals.json"

MemType = Literal["episodic", "semantic", "procedural", "goal"]


# ── 외부 저장소 어댑터 (실제 저장은 기존 모듈에 위임) ──────────────────────────

def _store_episodic(text: str, meta: dict) -> str:
    """SQLite events에 memory_episodic 이벤트로 기록 → id 반환."""
    eid = _events.append(
        "memory_episodic",
        payload={"text": text, **meta},
        actor="memory_router",
        task_id=meta.get("task_id"),
    )
    return f"ep:{eid}"


def _store_semantic(text: str, meta: dict) -> str | None:
    """ChromaDB에 저장. 컬렉션은 source/type 기준 분리(이미 conversation_memory/research_wiki 존재)."""
    try:
        from src.vectordb.factory import get_vectorstore
    except Exception as e:
        _log.debug("vectorstore 없음 → semantic 저장 스킵: %s", e)
        return None
    coll = meta.get("collection") or f"semantic_{meta.get('source','observation')}"
    try:
        vs = get_vectorstore(coll)
        mid = uuid.uuid4().hex[:16]
        vs.add(ids=[mid], documents=[text], metadatas=[{**meta, "stored_at": time.time()}])
        return f"sem:{coll}:{mid}"
    except Exception as e:
        _log.warning("semantic 저장 실패: %s", e)
        return None


def _store_procedural(text: str, meta: dict) -> str:
    """행동 규칙 — append-only json."""
    _AGENT_DIR.mkdir(parents=True, exist_ok=True)
    rules = []
    if _RULES_PATH.exists():
        try: rules = json.loads(_RULES_PATH.read_text(encoding="utf-8"))
        except Exception: rules = []
    rid = uuid.uuid4().hex[:12]
    rules.append({"id": rid, "rule": text, "added_at": time.time(), **meta})
    _RULES_PATH.write_text(json.dumps(rules, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"rule:{rid}"


def _store_goal(text: str, meta: dict) -> str:
    """목표 — id별 upsert (related_to 첫 항목이 있으면 id로 사용)."""
    _AGENT_DIR.mkdir(parents=True, exist_ok=True)
    goals = {}
    if _GOALS_PATH.exists():
        try: goals = json.loads(_GOALS_PATH.read_text(encoding="utf-8"))
        except Exception: goals = {}
    gid = meta.get("goal_id") or (meta.get("related_to") or [None])[0] or uuid.uuid4().hex[:12]
    goals[gid] = {"goal": text, "updated_at": time.time(), **meta}
    _GOALS_PATH.write_text(json.dumps(goals, ensure_ascii=False, indent=2), encoding="utf-8")
    return f"goal:{gid}"


_STORE = {
    "episodic": _store_episodic,
    "semantic": _store_semantic,
    "procedural": _store_procedural,
    "goal": _store_goal,
}


# ── 라우터 ────────────────────────────────────────────────────────────────────

def write(
    text: str,
    *,
    type: MemType = "episodic",
    source: str = "observation",
    owner_email: str | None = None,
    related_to: Iterable[str] = (),
    candidates_nearby: Iterable[str] = (),
    task_id: str | None = None,
    extra_meta: dict | None = None,
    force: bool = False,   # gate 우회 (user/verified 한정)
    record_only: bool = False,   # True면 자체저장 스킵, gate+scorer+events 감사만
) -> dict:
    """단일 메모리 쓰기 진입점. 반환: {decision, id, scores, gate_reason}.

    candidates_nearby: novelty/recurrence 산출용 (직전 N개 유사 항목; 호출자가 retrieval로 전달)
    force=True는 source가 user/verified일 때만 의미(gate 우회).
    record_only=True: 기존 저장소(change_log/ChromaDB 등)가 이미 처리하는 경우용 —
        gate/scorer/events 감사만 수행하고 라우터 자체 저장(_STORE)은 건너뜀.
    """
    text = (text or "").strip()
    meta = {"source": source, "owner_email": owner_email, "task_id": task_id,
            "related_to": list(related_to)}
    if extra_meta:
        meta.update(extra_meta)

    # 1차 게이트 (기존 memory_gate — 짧음/환각/중복).
    # type별 최소 길이: 목표·규칙은 짧을 수 있음("Submit paper" 등) → 완화.
    _MIN_LEN = {"goal": 6, "procedural": 12, "semantic": 16, "episodic": 20}
    try:
        from src.memory.memory_gate import assess as _assess
        g1 = _assess(text, source=source, min_len=_MIN_LEN.get(type, 20)) or {}
    except Exception:
        g1 = {"tier": "verified", "ok": True}
    tier1 = g1.get("tier") or ("verified" if g1.get("ok", True) else "quarantine")
    if tier1 == "quarantine" and not (force and source in ("user", "verified", "human")):
        _events.append("memory_rejected", {"text": text[:120], "stage": "gate_assess",
                       "reason": g1.get("reason"), "source": source, "type": type},
                       actor="memory_router")
        return {"decision": "rejected_gate", "id": None, "scores": None, "gate_reason": g1.get("reason")}

    # 2차 점수
    from src.memory.scorer import score as _score, gate as _gate
    scores = _score(text, type=type, source=source, candidates=candidates_nearby)
    decision = "store" if force else _gate(scores, type=type)

    if decision == "skip":
        _events.append("memory_rejected", {"text": text[:120], "stage": "scorer",
                       "scores": scores, "source": source, "type": type},
                       actor="memory_router")
        return {"decision": "skip", "id": None, "scores": scores, "gate_reason": "low_value"}

    if decision == "quarantine":
        _events.append("memory_quarantined", {"text": text[:200], "scores": scores,
                       "source": source, "type": type, "meta": meta},
                       actor="memory_router")
        return {"decision": "quarantine", "id": None, "scores": scores, "gate_reason": "below_threshold"}

    # 3) 저장 (decision == "store" or "review")
    meta_full = {**meta, "scores": scores, "tier1": tier1, "decision": decision}
    if record_only:
        # 호출자(change_log/conversation_memory 등)가 이미 저장 → 감사만
        _events.append(
            "memory_write",
            {"type": type, "source": source, "decision": decision, "id": None,
             "scores": scores, "owner": owner_email, "len": len(text), "record_only": True},
            actor="memory_router", task_id=task_id,
        )
        return {"decision": decision, "id": None, "scores": scores, "gate_reason": None}

    try:
        store_fn = _STORE[type]
        mem_id = store_fn(text, meta_full)
    except Exception as e:
        _log.warning("memory store 실패(type=%s): %s", type, e)
        _events.append("memory_store_error", {"type": type, "error": str(e)[:200]}, actor="memory_router")
        return {"decision": "error", "id": None, "scores": scores, "gate_reason": str(e)[:120]}

    # truth_hierarchy 자동 부착 — 다른 LLM 호출에 컨텍스트 주입 가능 여부 미리 결정
    try:
        from src.safety.truth_hierarchy import classify, can_inject_to_context
        _verified = source in ("user", "human", "verified", "rule")
        _grounded = bool(extra_meta and (extra_meta.get("grounded_in_data") or
                                          extra_meta.get("stat_result") or
                                          extra_meta.get("ref_pmid")))
        _level = classify(source, verified=_verified, grounded_in_data=_grounded)
        _injectable = can_inject_to_context(_level)
    except Exception:
        _level = None; _injectable = False

    _events.append(
        "memory_write",
        {"type": type, "source": source, "decision": decision, "id": mem_id,
         "scores": scores, "owner": owner_email, "len": len(text),
         "truth_level": _level.name if _level else None,
         "injectable_to_context": _injectable},
        actor="memory_router", task_id=task_id,
    )
    return {"decision": decision, "id": mem_id, "scores": scores, "gate_reason": None,
            "truth_level": _level.name if _level else None,
            "injectable_to_context": _injectable}
