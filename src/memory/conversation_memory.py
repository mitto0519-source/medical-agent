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

# ── MemPalace식 의미 메모리 (대화 verbatim → ChromaDB → 의미검색 회수) ──────
# 요약본만 두면 세부가 손실되고 최근 N개만 보면 맥락이 끊긴다. 대화 전문을 벡터로
# 저장해 두고 "지금 질문과 의미적으로 관련된 과거"만 골라 회수한다.
_VSTORE = None
_VSTORE_TRIED = False


def _vstore():
    """대화 전용 ChromaDB 컬렉션 (lazy, graceful — 없으면 None)."""
    global _VSTORE, _VSTORE_TRIED
    if _VSTORE is not None or _VSTORE_TRIED:
        return _VSTORE
    _VSTORE_TRIED = True
    try:
        from src.vectordb.store import VectorStore
        _VSTORE = VectorStore(collection_name="conversation_memory")
    except Exception as e:
        _log.warning("대화 의미메모리 비활성(ChromaDB 없음): %s", str(e)[:100])
        _VSTORE = None
    return _VSTORE


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
    owner_email: str = "",
) -> None:
    """대화 교환 기록 — JSON(최근/요약) + ChromaDB(verbatim 의미검색) 동시 저장."""
    _id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    _ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entries = _load()
    entries.insert(0, {
        "id": _id,
        "timestamp": _ts,
        "topic": topic or user_message[:50],
        "context_type": context_type,
        "user_summary": user_message[:200],
        "agent_summary": agent_response[:400],
        "quality": quality,
        "owner_email": owner_email,
    })
    _save(entries)

    # MemPalace식: 대화 전문을 의미 메모리에 색인 (관련 과거 회수용)
    vs = _vstore()
    if vs is not None:
        try:
            vs.add_chunks([{
                "text": f"User: {user_message}\nAssistant: {agent_response}",
                "metadata": {
                    "timestamp": _ts, "topic": topic or user_message[:50],
                    "context_type": context_type, "owner_email": owner_email,
                },
            }])
        except Exception as e:
            _log.warning("대화 의미메모리 색인 실패(JSON은 저장됨): %s", str(e)[:100])

    # 페르소나에도 연동
    try:
        from src.agent.persona import get_persona
        get_persona().record_exchange(user_message, agent_response, topic, quality)
    except Exception:
        pass


def recall_relevant(query: str, n: int = 4, owner_email: Optional[str] = None,
                    min_score: float = 0.25) -> str:
    """질문과 의미적으로 관련된 과거 대화를 회수 (MemPalace식 의미검색).

    최근 N개가 아니라 '지금 맥락에 진짜 관련된' 과거만 골라 LLM에 주입한다.
    owner_email 주면 해당 계정 대화만 (멀티테넌시). 없으면 빈 문자열 반환.
    """
    vs = _vstore()
    if vs is None or not (query or "").strip():
        return ""
    try:
        where = {"owner_email": owner_email} if owner_email else None
        hits = vs.search(query, n_results=n, where=where)
    except Exception as e:
        _log.warning("대화 의미검색 실패: %s", str(e)[:100])
        return ""
    hits = [h for h in hits if h.get("score", 0) >= min_score]
    if not hits:
        return ""
    lines = ["=== 관련 과거 대화 (의미 검색) ==="]
    for h in hits:
        _t = h.get("metadata", {}).get("timestamp", "")[:10]
        lines.append(f"[{_t}] {h['text'][:400]}")
    lines.append("=== 끝 ===")
    return "\n".join(lines)


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
