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
from src.utils.text_sanitize import safe_json_dumps, strip_lone_surrogates

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
    # sanitize: lone UTF-16 surrogate / nasty ctrl char 차단 (API 사고 방어, 2026-05-30)
    _FILE.write_text(
        safe_json_dumps(entries[:_MAX], indent=2),
        encoding="utf-8",
    )


def _distill(user_message: str, agent_response: str,
                topic: str = "", owner_email: str = "") -> Dict:
    """FIX-7 (REVIEW_FIX_SPEC, 2026-06-13): 절단이 아니라 압축 증류.

    LLM이 turn에서 (확정된 사실 / 열린 질문 / 사용자 선호 / 다음 액션 후보)를
    구조화 추출. 실패 시 단순 truncation으로 폴백.
    """
    fallback = {
        "facts_established": [user_message[:200]],
        "open_questions": [],
        "user_preferences": [],
        "next_action_candidates": [],
        "agent_brief": agent_response[:400],
    }
    if not (user_message or agent_response):
        return fallback
    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="standard")
        prompt = (
            "Extract from this turn (JSON only, keys: facts_established list, "
            "open_questions list, user_preferences list, next_action_candidates list, "
            "agent_brief string ≤300 chars):\n\n"
            f"User: {user_message[:1500]}\n\n"
            f"Assistant: {agent_response[:2500]}\n\n"
            f"Topic: {topic}"
        )
        out = client.generate(prompt, system_prompt="Output strict JSON only.",
                                max_tokens=400) or ""
        # JSON 양식
        import json as _j, re as _re
        m = _re.search(r"\{[\s\S]*\}", out)
        if m:
            parsed = _j.loads(m.group(0))
            if isinstance(parsed, dict):
                # 형식 양식
                for k in ("facts_established", "open_questions",
                           "user_preferences", "next_action_candidates"):
                    if not isinstance(parsed.get(k), list):
                        parsed[k] = []
                if not isinstance(parsed.get("agent_brief"), str):
                    parsed["agent_brief"] = agent_response[:400]
                return parsed
    except Exception as e:
        _log.debug("distill fail (fallback to truncation): %s", e)
    return fallback


def record(
    user_message: str,
    agent_response: str,
    topic: str = "",
    context_type: str = "general",  # 'research' | 'analysis' | 'qa' | 'general'
    quality: str = "neutral",
    owner_email: str = "",
) -> None:
    """대화 교환 기록 — JSON(최근/요약) + ChromaDB(verbatim 의미검색) 동시 저장.

    FIX-7: 절단(:200/:400) → reflection 증류(facts/open_q/prefs/agent_brief).
    구조화 dict가 저장되어 다음 턴에 의미가 깨지지 않음.
    """
    # 외부 입력 sanitize: 깨진 utf-16 surrogate가 ChromaDB / JSON / API에 전파되지 않도록
    user_message = strip_lone_surrogates(user_message)
    agent_response = strip_lone_surrogates(agent_response)
    topic = strip_lone_surrogates(topic)
    _id = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    _ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    entries = _load()

    distilled = _distill(user_message, agent_response, topic, owner_email)
    entries.insert(0, {
        "id": _id,
        "timestamp": _ts,
        "topic": topic or user_message[:50],
        "context_type": context_type,
        # FIX-7: 절단 대신 증류
        "user_summary": user_message[:200],          # 호환용 (legacy reader)
        "agent_summary": agent_response[:400],       # 호환용
        "distilled": distilled,                       # 신규: 구조화 증류
        "quality": quality,
        "owner_email": owner_email,
    })
    _save(entries)
    # rolling summary 갱신 (legacy summarize_session 양식 양식)
    try:
        _update_rolling_summary(owner_email=owner_email)
    except Exception as _e:
        _log.debug("rolling summary update skip: %s", _e)

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

    # 라우터 감사(events trail) — JSON/ChromaDB 저장은 위에서 끝, 여기선 audit-only
    try:
        from src.memory import router as _router
        _router.write(
            f"User: {user_message[:200]}\nAssistant: {agent_response[:400]}",
            type="episodic", source="user",
            owner_email=owner_email or None,
            extra_meta={"topic": topic, "context_type": context_type, "quality": quality},
            record_only=True,
        )
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


# FIX-7 (REVIEW_FIX_SPEC, 2026-06-13): rolling summary — 세션 누적 요약을 LLM이 매 N턴
# 갱신해 build_system_with_preview가 매 호출마다 짧은 high-density summary를 inject.
_ROLLING_SUMMARY_PATH = _DIR / "rolling_summary.json"
_ROLLING_UPDATE_EVERY = 4   # 매 4 turn마다 갱신


def _update_rolling_summary(owner_email: str = "") -> None:
    """세션 누적 요약을 LLM으로 압축 갱신.

    매 4턴마다 호출되어 최근 8턴의 distilled facts/open_questions를 합쳐
    rolling summary 갱신. recall_relevant가 검색 안 잡는 흐름·연속성을 보존.
    """
    entries = _load()
    # 양식 양식 양식 양식 양식 양식 양식
    if owner_email:
        scope = [e for e in entries if e.get("owner_email") == owner_email][:8]
    else:
        scope = entries[:8]
    if len(scope) < 2:
        return
    if len(scope) % _ROLLING_UPDATE_EVERY != 0:
        return

    facts: list = []
    open_q: list = []
    prefs: list = []
    for e in scope:
        d = e.get("distilled") or {}
        facts += d.get("facts_established") or []
        open_q += d.get("open_questions") or []
        prefs += d.get("user_preferences") or []
    if not (facts or open_q or prefs):
        return

    text = (
        "최근 대화 누적 사실:\n- " + "\n- ".join(facts[-15:]) +
        "\n\n열린 질문:\n- " + "\n- ".join(open_q[-8:]) +
        "\n\n사용자 선호:\n- " + "\n- ".join(prefs[-8:])
    )
    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="standard")
        summary = client.generate(
            "Compress the following into a concise 200-word running session summary "
            "(facts → open questions → preferences). Preserve specifics:\n\n" + text[:4000],
            system_prompt="Concise factual summarizer.", max_tokens=400) or text[:800]
    except Exception:
        summary = text[:800]

    payload = {
        "owner_email": owner_email,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "n_turns": len(scope),
        "summary": summary,
    }
    try:
        _ROLLING_SUMMARY_PATH.write_text(safe_json_dumps(payload, indent=2),
                                              encoding="utf-8")
    except Exception as _e:
        _log.debug("rolling summary write fail: %s", _e)


def get_rolling_summary(owner_email: str = "") -> str:
    """누적 rolling summary 텍스트 반환 (build_system_with_preview에서 호출)."""
    if not _ROLLING_SUMMARY_PATH.exists():
        return ""
    try:
        import json as _j
        d = _j.loads(_ROLLING_SUMMARY_PATH.read_text(encoding="utf-8"))
        if owner_email and d.get("owner_email") and d["owner_email"] != owner_email:
            return ""
        return d.get("summary", "")
    except Exception:
        return ""
