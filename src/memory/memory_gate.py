"""Memory Gate — 자가 메모리 오염 방지 (verified-only commit).

조언(research OS) #2: LLM output을 검증 없이 self-memory에 바로 저장하면
hallucination이 self-memory로 들어가고 reasoning pattern이 잘못 강화된다(self-pollution).

이 게이트는 commit 전에 결정론적(LLM-무관) 규칙으로 평가해 tier를 부여한다:
  - verified : 사용자/피드백/관찰 기반, 검증 통과 → production 메모리
  - auto     : 자동 수집(PubMed 등) → 저장하되 '미검증' 표식 (retrieval 시 구분 가능)
  - quarantine: 너무 짧음/중복/환각마커 → 저장 거부 (오염 차단)

RAW → CURATED → VERIFIED 계층. raw→production 직행 금지.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

# 환각/메타발화 마커 (의학 인사이트엔 나올 수 없는 표현 → 거부)
_HALLUC_MARKERS = [
    "as an ai", "i cannot", "i am unable", "language model", "i'm sorry",
    "죄송하지만", "제공할 수 없", "답변할 수 없", "저는 ai", "모델로서",
]
_VERIFIED_SOURCES = {"user", "feedback", "observation", "human", "verified", "rule"}
_AUTO_SOURCES = {"auto_learn", "pubmed", "trend", "periodic_learn", "crawl"}


def _norm(t: str) -> set:
    return set(re.findall(r"[\w가-힣]{2,}", (t or "").lower()))


def _is_duplicate(text: str, existing: List[str], thresh: float = 0.9) -> bool:
    """기존 항목과 거의 동일한가 (토큰 자카드 ≥ thresh 또는 완전포함)."""
    tw = _norm(text)
    if not tw:
        return False
    for e in existing or []:
        if text.strip() and text.strip() in (e or ""):
            return True
        ew = _norm(e)
        if not ew:
            continue
        inter = len(tw & ew)
        jac = inter / max(len(tw | ew), 1)
        if jac >= thresh:
            return True
    return False


def _audit(reason: str, text: str, source: str) -> None:
    """quarantine 사건을 safety audit_trail에 자동 기록. 실패는 silent (게이트 자체는 살아있어야)."""
    try:
        from src.safety.audit_trail import record_safety_event
        record_safety_event(
            "memory_gate_quarantine",
            {"reason": reason, "source": source,
             "text_preview": (text or "")[:120].replace("\n", " ")},
        )
    except Exception:
        pass


# ── ★ MEMORY_HARDENING_SPEC §1 기법 ③ — 티켓+Curator+Policy Gate (agentlas 이식) ──
# raw observation → MemoryTicket → Curator 결정(drop/accept/route_to_policy_gate) →
# Policy Gate (semantic/procedural 승격은 citation OR stat OR human 중 하나 충족) → ledger.

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class MemoryTicket:
    """raw 메모리 후보 — Curator가 판정 전 양식.

    evidence: 'citation' / 'stat_result' / 'human_approval' / 'rag_hit' 중 1개 이상이면
    semantic/procedural 승격 가능. 없으면 episodic까지만.
    """
    text: str
    proposed_type: Literal["working", "episodic", "semantic", "procedural", "goal"]
    source: str = "observation"
    owner_email: Optional[str] = None
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    raw_meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CuratorDecision:
    """drop / accept / route_to_policy_gate. 라우터가 이 결정만 보고 진행."""
    action: Literal["drop", "accept", "route_to_policy_gate"]
    reason: str
    final_tier: Optional[str] = None       # accept 시: "verified"/"auto"
    promotion_allowed: bool = False         # policy_gate 통과 시 True


def curator_decide(ticket: MemoryTicket) -> CuratorDecision:
    """단순 룰 기반 Curator — LLM 무관.

    규칙:
      R1: assess() 가 quarantine → drop.
      R2: episodic + verified source → accept (그대로 저장).
      R3: semantic/procedural 승격은 evidence 있어야 → route_to_policy_gate.
      R4: 그 외 → accept (default tier).
    """
    g1 = assess(ticket.text, source=ticket.source)
    if not g1.get("ok", True):
        return CuratorDecision(action="drop", reason=g1.get("reason", "gate_assess_fail"))

    if ticket.proposed_type in ("semantic", "procedural"):
        # 승격 — Policy Gate 통과 필요
        return CuratorDecision(
            action="route_to_policy_gate",
            reason="promotion_to_semantic_or_procedural",
            final_tier=None,
            promotion_allowed=False,
        )

    return CuratorDecision(
        action="accept",
        reason="default_accept",
        final_tier=g1.get("tier", "auto"),
        promotion_allowed=False,
    )


def policy_gate(ticket: MemoryTicket) -> CuratorDecision:
    """semantic/procedural 승격 게이트 — citation OR stat_result OR human_approval.

    evidence 양식: [{"kind": "citation", "pmid": "..."}, {"kind": "stat_result", ...},
                   {"kind": "human_approval", "email": "..."}, {"kind": "rag_hit", ...}]
    """
    accepted_kinds = {"citation", "stat_result", "human_approval"}
    has_accepted_evidence = any(
        e.get("kind") in accepted_kinds for e in (ticket.evidence or [])
    )
    if has_accepted_evidence:
        return CuratorDecision(
            action="accept", reason="policy_gate_passed",
            final_tier="verified", promotion_allowed=True,
        )
    return CuratorDecision(
        action="drop", reason="policy_gate_blocked_no_evidence",
        final_tier=None, promotion_allowed=False,
    )


def process_ticket(ticket: MemoryTicket) -> CuratorDecision:
    """티켓 → Curator → (필요시) Policy Gate → 최종 결정 + ledger 기록."""
    d = curator_decide(ticket)
    if d.action == "route_to_policy_gate":
        d = policy_gate(ticket)
    try:
        from src.evolution.ledger import record_candidate
        record_candidate(
            kind="memory_ticket",
            id=f"tk_{ticket.proposed_type}_{abs(hash(ticket.text[:80]))%10**12:012d}",
            payload={
                "text_preview": ticket.text[:160],
                "proposed_type": ticket.proposed_type,
                "source": ticket.source,
                "evidence_kinds": [e.get("kind") for e in (ticket.evidence or [])],
                "curator_action": d.action,
                "curator_reason": d.reason,
                "final_tier": d.final_tier,
            },
            actor="memory_gate.curator",
        )
    except Exception as _e:
        _log.debug("ledger record_candidate fail: %s", _e)
    return d


# ───────────────────────────────────────────────────────────────────────────


def assess(text: str, source: str = "observation",
           existing: Optional[List[str]] = None, min_len: int = 20) -> Dict:
    """메모리 후보 평가 → {ok, tier, confidence, reason}. LLM 불필요.
    quarantine 사건은 audit_trail에 자동 기록(events.db) → compliance_report에 잡힘."""
    t = (text or "").strip()
    if len(t) < min_len:
        _audit("too_short", t, source)
        return {"ok": False, "tier": "quarantine", "confidence": 0.0, "reason": "too_short"}
    low = t.lower()
    if any(m in low for m in _HALLUC_MARKERS):
        _audit("hallucination_marker", t, source)
        return {"ok": False, "tier": "quarantine", "confidence": 0.0, "reason": "hallucination_marker"}
    if _is_duplicate(t, existing or []):
        _audit("duplicate", t, source)
        return {"ok": False, "tier": "quarantine", "confidence": 0.0, "reason": "duplicate"}
    s = (source or "").lower()
    if s in _VERIFIED_SOURCES:
        return {"ok": True, "tier": "verified", "confidence": 0.9, "reason": "ok"}
    if s in _AUTO_SOURCES:
        return {"ok": True, "tier": "auto", "confidence": 0.6, "reason": "ok_unverified"}
    return {"ok": True, "tier": "auto", "confidence": 0.5, "reason": "ok_unknown_source"}
