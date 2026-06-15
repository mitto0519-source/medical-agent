"""Self-evolution learning hooks — ResearchProject 결과 → Failure KB / Gold / Ranking.

RESEARCH_STATE_SPEC §6 + SELF_EVOLUTION + MASTER #5.

원칙: 분석 실패·동료심사 점수·인용 NLI·confidence 캘리브레이션 등 모든 결과가
**자동으로** 다음 turn을 더 낫게 만들도록 SELF_EVOLUTION 모듈에 신호 emit.

새 학습루프 0 — 기존 reliability.failure_kb / evolution.ledger / quality_tracker 호출만.

API:
  emit_analysis_failure(failure_type, variables, resolution, project_id)
  emit_review_score(score_pct, components, project_id)
  emit_citation_check(claim, evidence_pmids, label_predicted, label_actual)
  emit_confidence_calibration(predicted, actual_correct, project_id)
  emit_reproducibility_break(provenance_id, divergence)
"""
from __future__ import annotations

from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def emit_analysis_failure(failure_type: str, variables: List[str],
                              resolution: str,
                              *, project_id: Optional[str] = None,
                              evidence: str = "") -> None:
    """분석 실패 → Failure KB (procedural memory) 누적."""
    try:
        from src.reliability.failure_kb import record_failure
        record_failure(failure_type, variables, resolution,
                          evidence=evidence, project_id=project_id)
    except Exception as e:
        _log.debug("emit_analysis_failure fail: %s", e)


def emit_review_score(score_pct: float, components: Dict,
                          *, project_id: Optional[str] = None,
                          reviewer_model: str = "",
                          writer_model: str = "") -> None:
    """동료심사 % 점수 → quality_tracker 추세 + 골드셋 후보 큐."""
    try:
        from src.diagnostics.quality_tracker import record_score
        record_score(score_pct=score_pct, components=components,
                       project_id=project_id)
    except Exception as e:
        _log.debug("quality_tracker.record_score fail: %s", e)

    # Self-bias warning (writer ↔ critic 동일 family 감지)
    if writer_model and reviewer_model:
        try:
            from src.safety.self_bias_guard import warn_if_self_review
            rep = warn_if_self_review(writer_model, reviewer_model)
            if rep.severity != "ok":
                from src.runtime.events import append as _evt
                _evt(type="self_bias_warning",
                      payload={"writer": writer_model, "critic": reviewer_model,
                                 "severity": rep.severity, "msg": rep.msg,
                                 "recommended": rep.recommended_critic_provider},
                      task_id=project_id, actor="learning_hooks")
        except Exception:
            pass


def emit_citation_check(claim: str, evidence_pmid: str,
                            label_predicted: str, label_actual: str,
                            *, project_id: Optional[str] = None) -> None:
    """Claim-Evidence NLI 결과 → 골드셋 검증 + citation_faithfulness 점수."""
    try:
        from src.runtime.events import append as _evt
        _evt(type="citation_check",
              payload={"claim": claim[:200], "pmid": evidence_pmid,
                         "predicted": label_predicted, "actual": label_actual,
                         "match": label_predicted == label_actual},
              task_id=project_id, actor="learning_hooks")
    except Exception:
        pass

    # 불일치 → 골드셋 후보로 emit
    if label_predicted != label_actual:
        try:
            from src.reliability.failure_kb import record_failure
            record_failure(
                failure_type="citation_hallucination",
                variables=[evidence_pmid],
                resolution=f"label {label_predicted} → {label_actual}",
                project_id=project_id,
                evidence=claim[:300],
            )
        except Exception:
            pass


def emit_confidence_calibration(predicted_conf: float, actual_correct: bool,
                                       *, project_id: Optional[str] = None) -> None:
    """confidence vs 실제 결과 → 캘리브레이션 (과신/과소 교정).

    Brier score 계산 + events.db에 누적. 누적 100건 이상이면
    SELF_EVOLUTION이 confidence weights 보정.
    """
    try:
        from src.runtime.events import append as _evt
        brier = (predicted_conf - (1.0 if actual_correct else 0.0)) ** 2
        _evt(type="confidence_calibration",
              payload={"predicted": predicted_conf,
                         "actual": actual_correct, "brier": brier},
              task_id=project_id, actor="learning_hooks")
    except Exception:
        pass


def emit_reproducibility_break(provenance_id: int, divergence: str,
                                       *, project_id: Optional[str] = None) -> None:
    """결정적 재실행 실패 → 회귀 가드 트리거 (SELF_EVOLUTION §5)."""
    try:
        from src.runtime.events import append as _evt
        _evt(type="reproducibility_break",
              payload={"provenance_id": provenance_id,
                         "divergence": divergence[:300]},
              task_id=project_id, actor="learning_hooks")
        # Failure KB에도 기록
        from src.reliability.failure_kb import record_failure
        record_failure(
            failure_type="stat_assumption_violated",
            variables=[],
            resolution=f"provenance_id={provenance_id} divergence={divergence[:200]}",
            project_id=project_id,
        )
    except Exception:
        pass


def emit_promotion_decision(decision: str, delta: float,
                                  axes_dropped: List[str],
                                  *, candidate_id: int) -> None:
    """SELF_EVOLUTION gate 결정 → ledger (이미 ledger.record_gate_result가 함)."""
    # ledger.record_gate_result에서 처리되므로 여기선 보조 emit만
    try:
        from src.runtime.events import append as _evt
        _evt(type="promotion_signal",
              payload={"decision": decision, "delta": delta,
                         "axes_dropped": axes_dropped,
                         "candidate_id": candidate_id},
              actor="learning_hooks")
    except Exception:
        pass


__all__ = [
    "emit_analysis_failure", "emit_review_score",
    "emit_citation_check", "emit_confidence_calibration",
    "emit_reproducibility_break", "emit_promotion_decision",
]
