"""Improvement Engine — 자가 진단 결과 기반 자동 개선 실행.

AUTO 실행 (즉시):
  - 아키텍처 갭 → agent_insight next_action으로 기록
  - 코드 이슈(high severity) → insight mistake로 기록
  - RAG 품질 저하 → trend_learn 재실행
  - 페르소나 관점 갱신

MANUAL 큐 (승인 필요):
  - 모듈 구조 변경 제안
  - 프롬프트 대규모 수정
  - 데이터 스키마 변경

결과 저장:
  data/diagnostics/approval_queue.json
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.memory import agent_insight, change_log

_log = get_logger(__name__)
_APPROVAL_QUEUE = Path("data/diagnostics/approval_queue.json")

_MANUAL_CATEGORIES = {"ux", "data"}  # 이 카테고리는 항상 manual 큐로


class ImprovementEngine:
    """자가 진단 결과를 받아 자동 개선을 실행하고 수동 항목을 큐에 쌓는다."""

    def run(self, audit_result: Dict) -> Dict:
        auto_applied: List[str] = []
        queued: List[Dict] = []

        # ── LLM이 발견한 갭 처리 ──────────────────────────────────────
        for gap in audit_result.get("llm_gaps", []):
            if not isinstance(gap, dict):
                continue
            cat = gap.get("category", "")
            is_auto = gap.get("auto", False) and cat not in _MANUAL_CATEGORIES
            if is_auto:
                label = self._record_gap_as_insight(gap)
                if label:
                    auto_applied.append(label)
            else:
                queued.append(gap)

        # ── 코드 이슈 → insight 기록 ──────────────────────────────────
        high_issues = [i for i in audit_result.get("code_issues", []) if i.get("severity") == "high"]
        for issue in high_issues[:5]:  # 상위 5개만
            self._record_code_issue(issue)
        if high_issues:
            auto_applied.append(f"코드 이슈 {len(high_issues)}건 insight 기록")

        # ── RAG 품질 저하 → 재인제스트 ───────────────────────────────
        rag_status = audit_result.get("rag_health", {}).get("status", "")
        if rag_status in ("poor", "empty"):
            label = self._trigger_rag_reingest()
            if label:
                auto_applied.append(label)

        # ── 페르소나 갭 반영 ──────────────────────────────────────────
        gaps = audit_result.get("llm_gaps", [])
        if gaps:
            self._update_persona_from_gaps(gaps)
            auto_applied.append("페르소나 연구 관점 갱신")

        # ── 승인 큐 저장 ──────────────────────────────────────────────
        if queued:
            _append_to_queue(queued)
            _log.info("승인 큐 %d개 추가", len(queued))

        # ── change_log 기록 ───────────────────────────────────────────
        if auto_applied or queued:
            change_log.log(
                title=f"자가 개선: {len(auto_applied)}개 자동 적용, {len(queued)}개 승인 대기",
                action_type="self_evolution",
                description="; ".join(auto_applied[:4]),
                why_better="자율 자가 개선으로 Medical Agent 지속 성장",
                impact={"affected_modules": ["diagnostics", "agent_insight", "persona"]},
            )

        return {"auto_applied": auto_applied, "queued_count": len(queued)}

    # ── 내부 메서드 ───────────────────────────────────────────────────────

    def _record_gap_as_insight(self, gap: Dict) -> str:
        try:
            agent_insight.record(
                title=f"[자가진단 갭] {gap.get('gap', '')[:60]}",
                insight=f"{gap.get('gap', '')}\n\n해결책: {gap.get('solution', '')}",
                category="next_action",
                why_matters=gap.get("impact", "")[:200],
                how_to_apply=gap.get("solution", "")[:200],
                confidence=0.85,
                tags=["self_audit", gap.get("category", "general")],
                source="self_audit",
            )
            return f"insight: {gap.get('gap', '')[:40]}"
        except Exception as e:
            _log.warning("갭 insight 기록 실패: %s", e)
            return ""

    def _record_code_issue(self, issue: Dict) -> None:
        try:
            agent_insight.record(
                title=f"[코드이슈] {issue.get('type', '')}: {Path(issue.get('file','')).name}:{issue.get('line','')}",
                insight=issue.get("text", ""),
                category="mistake",
                why_matters="CLAUDE.md 규칙 위반 — 코드 품질 저하",
                how_to_apply=f"파일 {issue.get('file', '')} L{issue.get('line', '')} 수정",
                confidence=0.92,
                tags=["code_quality", "self_audit", issue.get("type", "")],
                source="self_audit",
            )
        except Exception as e:
            _log.warning("코드이슈 기록 실패: %s", e)

    def _trigger_rag_reingest(self) -> str:
        try:
            _log.info("RAG 재인제스트 자동 트리거 (품질 저하 감지)")
            from src.knowledge.trend_learner import run_trend_learn
            summary = run_trend_learn(days=30, max_per_query=15)
            new_papers = summary.get("new_papers", 0)
            return f"RAG 재인제스트: {new_papers}편 추가"
        except Exception as e:
            _log.warning("RAG 재인제스트 실패: %s", e)
            return ""

    def _update_persona_from_gaps(self, gaps: List[Dict]) -> None:
        """갭 분석 결과를 페르소나 관점으로 흡수."""
        try:
            from src.agent.persona import get_persona
            persona = get_persona()
            for gap in gaps[:2]:  # 상위 2개만
                topic = gap.get("gap", "")[:60]
                perspective = gap.get("solution", "")[:200]
                if topic and perspective:
                    persona.add_perspective(
                        topic=f"[자가진단] {topic}",
                        perspective=perspective,
                        confidence=0.72,
                        evidence_basis="self_audit",
                    )
        except Exception as e:
            _log.warning("페르소나 갱신 실패: %s", e)


# ── 승인 큐 공개 API ─────────────────────────────────────────────────────────

def get_approval_queue() -> List[Dict]:
    if not _APPROVAL_QUEUE.exists():
        return []
    try:
        items = json.loads(_APPROVAL_QUEUE.read_text(encoding="utf-8"))
        return [i for i in items if i.get("status") == "pending"]
    except Exception:
        return []


def approve_item(item_id: str) -> bool:
    return _update_item_status(item_id, "approved")


def reject_item(item_id: str) -> bool:
    return _update_item_status(item_id, "rejected")


def _update_item_status(item_id: str, status: str) -> bool:
    if not _APPROVAL_QUEUE.exists():
        return False
    try:
        items = json.loads(_APPROVAL_QUEUE.read_text(encoding="utf-8"))
        for item in items:
            if item.get("id") == item_id:
                item["status"] = status
                item[f"{status}_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _APPROVAL_QUEUE.write_text(
            json.dumps(items, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True
    except Exception as e:
        _log.warning("큐 상태 업데이트 실패: %s", e)
        return False


def _append_to_queue(items: List[Dict]) -> None:
    _APPROVAL_QUEUE.parent.mkdir(parents=True, exist_ok=True)
    existing: List[Dict] = []
    if _APPROVAL_QUEUE.exists():
        try:
            existing = json.loads(_APPROVAL_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            pass
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for item in items:
        existing.append({
            "id": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
            "queued_at": now,
            "status": "pending",
            **{k: v for k, v in item.items() if k not in ("id", "status")},
        })
    _APPROVAL_QUEUE.write_text(
        json.dumps(existing[-100:], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
