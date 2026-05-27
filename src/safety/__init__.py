"""의료 안전 레이어 — 환각·인용깨짐·사실 충돌·미검토 결과로부터 보호.

4개 모듈:
  citation_grounding  — 본문 [n] 마커가 실존 reference에 mapping, DOI CrossRef 검증, 연도 일관성
  truth_hierarchy     — SYSTEM > VERIFIED_FACT > PROJECT_FACT > SESSION > TEMP 메모리 진실 계층
  physician_review    — 사용자(연구자/의사) 검토 큐: pending/approved/rejected/escalated
  audit_trail         — events.py 기반 감사 로그 + compliance 리포트

설계 원칙:
  - 모든 LLM 산출물은 ground-truth(citation·data)에 연결돼야 함
  - VERIFIED FACT만이 다른 LLM에게 컨텍스트로 주입 가능
  - 임상 의사결정 지원 단어("진단·처방·복용량")는 항상 physician_review 큐 거침
"""
from .citation_grounding import (
    verify_citation_integrity, verify_doi_crossref, check_year_consistency,
)
from .truth_hierarchy import TruthLevel, classify, can_inject_to_context
from .physician_review import (
    review_required, queue_for_review, get_pending, approve, reject,
)
from .audit_trail import (
    record_safety_event, get_safety_events, compliance_report,
)
from .consistency_checker import check_consistency, ConsistencyReport
from .figure_validator import validate_figure, FigureValidationReport

__all__ = [
    "verify_citation_integrity", "verify_doi_crossref", "check_year_consistency",
    "TruthLevel", "classify", "can_inject_to_context",
    "review_required", "queue_for_review", "get_pending", "approve", "reject",
    "record_safety_event", "get_safety_events", "compliance_report",
    "check_consistency", "ConsistencyReport",
    "validate_figure", "FigureValidationReport",
]
