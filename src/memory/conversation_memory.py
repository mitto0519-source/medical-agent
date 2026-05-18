"""Conversation Memory — 세션 간 대화 맥락 지속 기억.

Claude Code 자체 메모리와 별개로, 에이전트가 사용자와 나눈
연구 관련 대화의 핵심 맥락을 로컬 + Supabase에 저장한다.

용도:
  - 다음 세션에서 "어디까지 얘기했었지?" 없이 바로 이어짐
  - 페르소나 진화의 입력 소재
  - 연구 맥락 연속성 (어떤 주제를 논의 중이었는가)
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_FILE = Path("data/agent_self/conversation_memory.json")
_MAX = 100


def _load() -> List[Dict]:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(entries: List[Dict]):
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(
        json.dumps(entries[:_MAX], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def record(
    user_message: str,
    agent_response: str,
    topic: str = "",
    context_type: str = "general",  # 'research' | 'analysis' | 'qa' | 'general'
    quality: str = "neutral",
) -> None:
    """대화 교환 기록."""
    entries = _load()
    entries.insert(0, {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic or user_message[:50],
        "context_type": context_type,
        "user_summary": user_message[:200],
        "agent_summary": agent_response[:400],
        "quality": quality,
    })
    _save(entries)

    # 페르소나에도 연동
    try:
        from src.agent.persona import get_persona
        get_persona().record_exchange(user_message, agent_response, topic, quality)
    except Exception:
        pass


def get_recent_context(n: int = 5, context_type: Optional[str] = None) -> str:
    """최근 N개 대화를 LLM 주입용 텍스트로 반환."""
    entries = _load()
    if context_type:
        entries = [e for e in entries if e.get("context_type") == context_type]
    entries = entries[:n]
    if not entries:
        return ""
    lines = ["=== 최근 대화 맥락 (연속성 유지) ==="]
    for e in entries:
        lines.append(f"[{e['timestamp'][:10]}] {e['topic']}")
        lines.append(f"  → {e['agent_summary'][:120]}")
    lines.append("=== 끝 ===")
    return "\n".join(lines)


def get_research_thread(topic_keyword: str, n: int = 5) -> List[Dict]:
    """특정 키워드와 관련된 대화 이력 반환."""
    entries = _load()
    keyword_lower = topic_keyword.lower()
    return [
        e for e in entries
        if keyword_lower in e.get("topic", "").lower()
        or keyword_lower in e.get("user_summary", "").lower()
    ][:n]


def summarize_session() -> str:
    """오늘 세션의 주요 대화를 요약 텍스트로 반환."""
    today = datetime.now().strftime("%Y-%m-%d")
    entries = [e for e in _load() if e.get("timestamp", "").startswith(today)]
    if not entries:
        return "오늘 기록된 대화 없음."
    topics = list({e.get("topic", "") for e in entries if e.get("topic")})[:5]
    return f"오늘 논의 주제 ({len(entries)}건): {', '.join(topics)}"
