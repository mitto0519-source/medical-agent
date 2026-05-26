"""Memory Truth Hierarchy — 메모리 항목의 진실 수준 계층.

사용자 분석 (2026-05-27)에서 지적된 "memory truth hierarchy" 구현.

레벨 (높을수록 신뢰):
  SYSTEM       — 코드/CLAUDE.md 규칙·data dictionary. 절대 불변.
  VERIFIED_FACT — 사용자가 직접 검증 또는 CrossRef/PubMed 검증된 fact.
  PROJECT_FACT — 현재 프로젝트의 데이터 분석 결과(StatBridge 출력 등). 재현 가능.
  SESSION      — 대화 맥락. 세션 한정.
  TEMP         — LLM 산출물 미검증. 컨텍스트 주입 금지.

규칙:
  - 다른 LLM 호출에 컨텍스트로 주입 가능: SYSTEM, VERIFIED_FACT, PROJECT_FACT만
  - SESSION/TEMP는 retrieval 결과로 보여줄 수는 있어도 system_prompt에 못 들어감
  - 충돌 시 높은 레벨이 항상 승리 (lifecycle.resolve_conflict와 연동)
"""
from __future__ import annotations

from enum import Enum
from typing import Any


class TruthLevel(Enum):
    SYSTEM = 5         # 코드/규칙/dictionary
    VERIFIED_FACT = 4  # 외부 검증(CrossRef/PubMed) 또는 사용자 검증
    PROJECT_FACT = 3   # StatBridge·figure 등 재현 가능 산출
    SESSION = 2        # 대화 맥락
    TEMP = 1           # 미검증 LLM 출력


# source(메모리 router에서 쓰는) → TruthLevel 매핑
_SOURCE_LEVEL = {
    "system": TruthLevel.SYSTEM,
    "rule": TruthLevel.SYSTEM,
    "user": TruthLevel.VERIFIED_FACT,
    "human": TruthLevel.VERIFIED_FACT,
    "verified": TruthLevel.VERIFIED_FACT,
    "crossref": TruthLevel.VERIFIED_FACT,
    "pubmed": TruthLevel.VERIFIED_FACT,
    "stat_bridge": TruthLevel.PROJECT_FACT,
    "observation": TruthLevel.PROJECT_FACT,   # 우리 시스템 직접 관찰
    "reflection": TruthLevel.PROJECT_FACT,
    "conversation": TruthLevel.SESSION,
    "llm": TruthLevel.TEMP,
    "auto_learn": TruthLevel.TEMP,
    "trend": TruthLevel.TEMP,
    "scratchpad": TruthLevel.TEMP,
}


def classify(source: str, *, verified: bool = False,
             grounded_in_data: bool = False) -> TruthLevel:
    """source + 검증 플래그 → TruthLevel.

    verified=True : 사용자/외부가 명시적으로 OK 한 항목 → 한 단계 승격
    grounded_in_data=True : 데이터/citation으로 grounded → PROJECT_FACT 이상 보장
    """
    base = _SOURCE_LEVEL.get((source or "").lower(), TruthLevel.TEMP)
    if grounded_in_data and base.value < TruthLevel.PROJECT_FACT.value:
        base = TruthLevel.PROJECT_FACT
    if verified and base.value < TruthLevel.VERIFIED_FACT.value:
        base = TruthLevel.VERIFIED_FACT
    return base


def can_inject_to_context(level: TruthLevel) -> bool:
    """이 진실 수준의 메모리를 다른 LLM 호출에 컨텍스트로 주입할 수 있는가."""
    return level.value >= TruthLevel.PROJECT_FACT.value


def can_show_to_user(level: TruthLevel) -> bool:
    """사용자에게 보여줘도 되는가 (모든 레벨 가능, TEMP는 'unverified' 표시)."""
    return True


def filter_for_injection(items: list, *, source_key: str = "source") -> list:
    """retrieval 결과 list에서 컨텍스트 주입 가능 항목만 통과.

    items: [{source: ..., text: ..., ...}, ...]
    """
    out = []
    for item in items:
        src = item.get(source_key, "") if isinstance(item, dict) else ""
        verified = bool(item.get("verified", False)) if isinstance(item, dict) else False
        grounded = bool(item.get("grounded_in_data", False)) if isinstance(item, dict) else False
        if can_inject_to_context(classify(src, verified=verified, grounded_in_data=grounded)):
            out.append(item)
    return out


def annotate_with_level(item: dict) -> dict:
    """dict에 truth_level 메타 추가."""
    lvl = classify(item.get("source", ""),
                   verified=bool(item.get("verified", False)),
                   grounded_in_data=bool(item.get("grounded_in_data", False)))
    return {**item, "truth_level": lvl.name, "truth_score": lvl.value}
