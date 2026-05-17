"""Agent self-learning insight DB — Claude의 자체 학습 및 캐릭터 저장소.

Claude가 이 프로젝트를 작업하면서 스스로 발견한 패턴, 실수, 최적화,
다음 액션 제안, 흡수한 외부 자료를 독립적으로 저장한다.

매 세션 시작 시 이 DB를 읽어 "내가 이전에 무엇을 배웠는가"를 파악하고,
작업 완료 후 "이번에 무엇을 새로 발견했는가"를 자동 기록한다.

카테고리:
  pattern      — 이 코드베이스/도메인에서 발견된 반복 패턴
  mistake      — 잘못됐던 것 + 재발 방지 방법
  optimization — 더 좋아지게 만든 것
  next_action  — 다음 우선 개선 제안 (선제 제안용)
  reference    — 사용자가 공유한 외부 자료 흡수
  decision     — 중요한 아키텍처 결정 기록
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DIR = Path("data/agent_self")
_FILE = _DIR / "insights.json"
_MAX = 500

CATEGORIES = {"pattern", "mistake", "optimization", "next_action", "reference", "decision"}


@dataclass
class Insight:
    id: str
    timestamp: str
    category: str          # pattern | mistake | optimization | next_action | reference | decision
    title: str
    insight: str           # 발견한 내용
    why_matters: str = ""  # 왜 중요한가
    how_to_apply: str = "" # 어떻게 적용할 것인가
    confidence: float = 0.8
    tags: List[str] = field(default_factory=list)
    source: str = "observation"  # observation | user_feedback | test_result | external_reference
    status: str = "active"       # active | resolved | superseded


def _cloud() -> bool:
    try:
        from src.cloud.db import cloud_available
        return cloud_available()
    except Exception:
        return False


def _engine():
    from src.cloud.db import get_engine
    return get_engine()


def _load() -> List[Dict]:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save_local(insights: List[Dict]) -> None:
    _DIR.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(
        json.dumps(insights[:_MAX], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record(
    title: str,
    insight: str,
    category: str = "pattern",
    why_matters: str = "",
    how_to_apply: str = "",
    confidence: float = 0.8,
    tags: Optional[List[str]] = None,
    source: str = "observation",
) -> Insight:
    """새 인사이트를 기록한다."""
    if category not in CATEGORIES:
        category = "pattern"
    now = datetime.now()
    entry = Insight(
        id=now.strftime("%Y%m%d_%H%M%S_%f"),
        timestamp=now.strftime("%Y-%m-%d %H:%M:%S"),
        category=category,
        title=title,
        insight=insight,
        why_matters=why_matters,
        how_to_apply=how_to_apply,
        confidence=confidence,
        tags=tags or [],
        source=source,
    )
    existing = _load()
    existing.insert(0, asdict(entry))
    _save_local(existing)

    if _cloud():
        try:
            _write_cloud(entry)
        except Exception as e:
            _log.warning("Cloud insight write failed: %s", e)

    _log.info("[insight/%s] %s", category, title)
    return entry


def _write_cloud(entry: Insight) -> None:
    from sqlalchemy import text
    with _engine().begin() as conn:
        conn.execute(text("""
            INSERT INTO ma_agent_insights
                (id, timestamp, category, title, insight, why_matters,
                 how_to_apply, confidence, tags, source, status)
            VALUES
                (:id, :ts, :category, :title, :insight, :why_matters,
                 :how_to_apply, :confidence, CAST(:tags AS jsonb), :source, :status)
            ON CONFLICT (id) DO NOTHING
        """), {
            "id": entry.id,
            "ts": entry.timestamp,
            "category": entry.category,
            "title": entry.title,
            "insight": entry.insight,
            "why_matters": entry.why_matters,
            "how_to_apply": entry.how_to_apply,
            "confidence": entry.confidence,
            "tags": json.dumps(entry.tags, ensure_ascii=False),
            "source": entry.source,
            "status": entry.status,
        })


def get_all(
    category: Optional[str] = None,
    tags: Optional[List[str]] = None,
    status: str = "active",
    n: int = 100,
) -> List[Dict]:
    entries = _load()
    if status:
        entries = [e for e in entries if e.get("status") == status]
    if category:
        entries = [e for e in entries if e.get("category") == category]
    if tags:
        entries = [e for e in entries if any(t in e.get("tags", []) for t in tags)]
    return entries[:n]


def get_next_actions(n: int = 5) -> List[Dict]:
    """우선순위 순으로 다음 액션 제안 반환."""
    actions = get_all(category="next_action", n=50)
    return sorted(actions, key=lambda x: x.get("confidence", 0), reverse=True)[:n]


def resolve(insight_id: str) -> None:
    """완료된 액션/해결된 인사이트를 resolved로 표시."""
    entries = _load()
    for e in entries:
        if e.get("id") == insight_id:
            e["status"] = "resolved"
    _save_local(entries)


def build_self_context() -> str:
    """Claude의 자체 학습 내용을 LLM 주입용 텍스트로 반환."""
    all_insights = _load()
    if not all_insights:
        return ""

    active = [e for e in all_insights if e.get("status") == "active"]
    patterns = [e for e in active if e.get("category") == "pattern"][:5]
    mistakes = [e for e in active if e.get("category") == "mistake"][:5]
    next_actions = [e for e in active if e.get("category") == "next_action"][:3]
    decisions = [e for e in active if e.get("category") == "decision"][:5]

    lines = ["=== Claude 자체 학습 컨텍스트 ==="]

    if decisions:
        lines.append("\n[중요 결정 사항]")
        for e in decisions:
            lines.append(f"- {e['title']}: {e['insight'][:100]}")

    if patterns:
        lines.append("\n[발견된 패턴]")
        for e in patterns:
            lines.append(f"- {e['title']}: {e['how_to_apply'][:80] or e['insight'][:80]}")

    if mistakes:
        lines.append("\n[재발 방지]")
        for e in mistakes:
            lines.append(f"- {e['title']}: {e['how_to_apply'][:80] or e['insight'][:80]}")

    if next_actions:
        lines.append("\n[다음 우선 작업]")
        for e in next_actions:
            conf = int(e.get("confidence", 0.8) * 100)
            lines.append(f"- [{conf}%] {e['title']}: {e['insight'][:80]}")

    lines.append("=== 끝 ===")
    return "\n".join(lines)


def absorb_reference(title: str, content: str, tags: Optional[List[str]] = None) -> Insight:
    """사용자가 공유한 외부 자료를 흡수하고 인사이트로 변환."""
    return record(
        title=title,
        insight=content[:800],
        category="reference",
        why_matters="사용자가 공유한 참고 자료",
        how_to_apply="다음 관련 작업 시 참조",
        confidence=0.7,
        tags=tags or ["external"],
        source="external_reference",
    )
