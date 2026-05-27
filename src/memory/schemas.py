"""Memory schemas — Pydantic versioned + migration.

사용자 요구 (외부 진단 2026-05-28 "memory schema stabilization"):
  · 지금 memory.router/lifecycle는 dict 통신이라 drift 위험
  · Pydantic strict schema + version + migration framework로 잠금
  · 이후 frontier-level agent로 확장할 때 invariants 유지

호환 정책:
  · 새 코드는 본 모듈의 schemas를 통해 dict↔model 변환
  · 기존 호출(dict 직접 전달)도 그대로 작동 — schemas는 검증/직렬화 helper

Versions:
  v1 (현재) — episodic/semantic/procedural/goal의 최소 공통 필드
  v1 schema 변경 시 v2 + migrate_v1_to_v2() 추가
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Literal, Optional

try:
    from pydantic import BaseModel, Field, ConfigDict, field_validator
    _PYDANTIC_OK = True
except Exception:
    _PYDANTIC_OK = False
    BaseModel = object  # type: ignore
    Field = lambda **kw: None  # type: ignore


SCHEMA_VERSION = "1.0.0"

MemType = Literal["episodic", "semantic", "procedural", "goal"]
TruthTier = Literal["system", "verified", "project_fact", "session", "temp", "quarantine"]
Decision = Literal["store", "review", "skip", "quarantine"]


if _PYDANTIC_OK:

    class MemoryScores(BaseModel):
        """scorer 산출 점수 (importance/novelty/recurrence/trust)."""
        model_config = ConfigDict(extra="allow")
        importance: float = Field(default=0.0, ge=0.0, le=1.0)
        novelty: float = Field(default=0.0, ge=0.0, le=1.0)
        recurrence: float = Field(default=0.0, ge=0.0, le=1.0)
        trust: float = Field(default=0.5, ge=0.0, le=1.0)


    class MemoryMeta(BaseModel):
        """memory.router에 첨부되는 meta dict 정형."""
        model_config = ConfigDict(extra="allow")
        source: str = "observation"
        owner_email: Optional[str] = None
        task_id: Optional[str] = None
        related_to: List[str] = Field(default_factory=list)
        grounded_in_data: bool = False
        truth_level: Optional[str] = None
        injectable_to_context: bool = False
        confidence: Optional[float] = None
        # 도메인별 추가 필드는 extra=allow로 자유


    class MemoryRecord(BaseModel):
        """단일 메모리 항목 — 모든 type 공통."""
        model_config = ConfigDict(extra="allow")

        schema_version: str = SCHEMA_VERSION
        id: str
        type: MemType = "episodic"
        text: str = Field(min_length=1, max_length=20000)
        created_at: float = Field(default_factory=time.time)
        updated_at: float = Field(default_factory=time.time)
        ttl_days: Optional[int] = None
        tier: TruthTier = "session"
        scores: Optional[MemoryScores] = None
        meta: MemoryMeta = Field(default_factory=MemoryMeta)
        archived: bool = False
        supersedes: Optional[str] = None   # 이 메모리가 대체한 이전 id

        @field_validator("text")
        @classmethod
        def _strip_text(cls, v: str) -> str:
            return (v or "").strip()


    class ProceduralRule(BaseModel):
        """행동 전략 메모리 — '이 reviewer는 X를 본다' 양식.
        외부 진단 'procedural learning 부재' 해결용."""
        model_config = ConfigDict(extra="allow")
        schema_version: str = SCHEMA_VERSION
        id: str
        trigger: str = Field(min_length=4, max_length=500,
                              description="when/condition: 'reviewer feedback contains X'")
        action: str = Field(min_length=4, max_length=1000,
                              description="then/strategy: 'include sample weighting detail'")
        domain: str = "general"               # journal_review|stat_method|figure_style|...
        confidence: float = Field(default=0.5, ge=0.0, le=1.0)
        n_applied: int = 0
        n_success: int = 0
        last_applied: float = 0.0
        source_episodes: List[str] = Field(default_factory=list)
        created_at: float = Field(default_factory=time.time)


    class A2AMessage(BaseModel):
        """Knowledge↔Writing orchestrator 간 메시지 schema (감사용)."""
        model_config = ConfigDict(extra="allow")
        schema_version: str = SCHEMA_VERSION
        intent: str
        from_agent: str
        to_agent: str
        payload: Dict[str, Any] = Field(default_factory=dict)
        ts: float = Field(default_factory=time.time)


    # ── Validation helpers ───────────────────────────────────────────────

    def validate_record(d: Dict[str, Any]) -> Dict[str, Any]:
        """dict → MemoryRecord 검증 → dict 반환. drift 차단."""
        try:
            m = MemoryRecord.model_validate(d)
            return m.model_dump()
        except Exception as e:
            # 호환성 — invalid는 원본 + 오류 표시
            return {**d, "_schema_invalid": str(e)[:200]}


    def validate_procedural(d: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return ProceduralRule.model_validate(d).model_dump()
        except Exception as e:
            return {**d, "_schema_invalid": str(e)[:200]}


    # ── Migrations ────────────────────────────────────────────────────────

    def migrate(d: Dict[str, Any]) -> Dict[str, Any]:
        """이전 버전 → 최신. 현재는 v1만 있으므로 schema_version만 강제."""
        d.setdefault("schema_version", SCHEMA_VERSION)
        # v2가 생기면 if d['schema_version'] == '1.0.0': v1_to_v2(d)
        return d

else:

    # Pydantic 미설치 환경 안전망 — passthrough
    class MemoryScores(dict): ...
    class MemoryMeta(dict): ...
    class MemoryRecord(dict): ...
    class ProceduralRule(dict): ...
    class A2AMessage(dict): ...

    def validate_record(d): return d
    def validate_procedural(d): return d
    def migrate(d):
        d.setdefault("schema_version", SCHEMA_VERSION)
        return d


__all__ = [
    "SCHEMA_VERSION", "MemType", "TruthTier", "Decision",
    "MemoryScores", "MemoryMeta", "MemoryRecord",
    "ProceduralRule", "A2AMessage",
    "validate_record", "validate_procedural", "migrate",
]
