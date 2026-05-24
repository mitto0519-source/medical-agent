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


def assess(text: str, source: str = "observation",
           existing: Optional[List[str]] = None, min_len: int = 20) -> Dict:
    """메모리 후보 평가 → {ok, tier, confidence, reason}. LLM 불필요."""
    t = (text or "").strip()
    if len(t) < min_len:
        return {"ok": False, "tier": "quarantine", "confidence": 0.0, "reason": "too_short"}
    low = t.lower()
    if any(m in low for m in _HALLUC_MARKERS):
        return {"ok": False, "tier": "quarantine", "confidence": 0.0, "reason": "hallucination_marker"}
    if _is_duplicate(t, existing or []):
        return {"ok": False, "tier": "quarantine", "confidence": 0.0, "reason": "duplicate"}
    s = (source or "").lower()
    if s in _VERIFIED_SOURCES:
        return {"ok": True, "tier": "verified", "confidence": 0.9, "reason": "ok"}
    if s in _AUTO_SOURCES:
        return {"ok": True, "tier": "auto", "confidence": 0.6, "reason": "ok_unverified"}
    return {"ok": True, "tier": "auto", "confidence": 0.5, "reason": "ok_unknown_source"}
