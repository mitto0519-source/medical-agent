"""Chat service — system-prompt assembly + streaming + per-turn hooks.

Pure: takes project dict + user_msg, returns text generator. No Streamlit.
ez_home.py wraps these for the Streamlit chat panel; FastAPI later does SSE wrap.
"""
from __future__ import annotations

from typing import Generator, Iterable, Optional

from src.config.logging_config import get_logger
from src.service import rag as rag_service

_log = get_logger(__name__)


def build_full_system(project: dict, user_msg: str, *, owner_email: str = "") -> str:
    """Single-core system prompt: persona → RAG inject → rule overlay."""
    try:
        from src.agent.persona import get_system_prompt
        base_sys = get_system_prompt(task="paper_writing", owner_email=owner_email or None)
    except Exception as e:
        _log.warning("persona load fail: %s", e)
        base_sys = "당신은 의학 연구 코파일럿입니다."

    try:
        from app.agentic_loop import build_system_with_preview
        full_sys = build_system_with_preview(base_sys, project, user_msg)
    except Exception as e:
        _log.warning("agentic_loop build fail: %s", e)
        full_sys = base_sys

    rag_block = rag_service.retrieve_as_text_block(user_msg, top_k=5, max_text_per_hit=600)
    if rag_block:
        full_sys = (
            full_sys
            + "\n\n--- RETRIEVED MEDICAL EVIDENCE (cite by PMID inline as [PMID:xxx]) ---\n"
            + rag_block
            + "\n--- END EVIDENCE ---"
        )

    rule_overlay = (
        "\n\n--- RULE-8 (vibe paper) ---\n"
        "사용자 주제가 모호하면 PICO·데이터·통계·하위군 중 짧은 역질문 2-3개로 좁히세요.\n"
        "'알아서 해' '그냥 해' '한번에' 같은 trigger를 들으면 그때 자동 파이프라인을 진행합니다.\n"
        "응답은 한국어 대화체, 동료 의학연구자 어투, 마크다운 짧게.\n"
        "위 RETRIEVED MEDICAL EVIDENCE를 참고해 답변에 PMID 인라인 인용을 넣으세요."
    )
    return full_sys + rule_overlay


def stream_reply(
    project: dict,
    user_msg: str,
    *,
    extra_system: str = "",
    max_tokens: int = 1200,
    owner_email: str = "",
) -> Generator[str, None, None]:
    """Generator yielding token chunks via failover LLM client."""
    try:
        from src.llm import get_llm_client
    except Exception as e:
        yield f"(LLM 클라이언트 import 실패: {e})"
        return

    full_sys = build_full_system(project, user_msg, owner_email=owner_email)
    if extra_system:
        full_sys = full_sys + "\n\n--- TASK OVERLAY ---\n" + extra_system

    history_lines = []
    for m in project.get("messages", [])[-10:]:
        role = "사용자" if m.get("role") == "user" else "코파일럿"
        history_lines.append(f"{role}: {m.get('content','')}")
    prompt = "\n".join(history_lines) + f"\n사용자: {user_msg}\n코파일럿:"

    try:
        client = get_llm_client(task="paper_writing")
        yielded = False
        for chunk in client.generate_streamed(prompt, system_prompt=full_sys, max_tokens=max_tokens):
            if chunk:
                yielded = True
                yield chunk
        if not yielded:
            yield "(빈 응답)"
    except Exception as e:
        _log.warning("stream_reply LLM fail: %s", e)
        yield f"(LLM 호출 실패: {e})"


def post_turn_hooks(project: dict, user_msg: str, full_reply: str, *, owner_email: str = "") -> None:
    """After-each-turn persistence: conversation_memory + events + typed memory + change_log."""
    try:
        from src.memory.conversation_memory import record as _cm_record
        _cm_record(user_message=user_msg, agent_response=full_reply,
                    topic=project.get("title", "")[:80],
                    context_type="ez_home_chat", quality="neutral",
                    owner_email=owner_email or "")
    except Exception as e:
        _log.debug("conversation_memory.record fail: %s", e)

    try:
        from src.runtime.events import append as _evt
        _evt(type="ez_home_chat_turn",
              payload={"pid": project.get("id"), "user": user_msg[:300],
                       "resp_len": len(full_reply)},
              actor=owner_email or "anon")
    except Exception as e:
        _log.debug("events.append fail: %s", e)

    try:
        from src.memory.router import write as _mem_write
        _mem_write(f"[chat:{project.get('id','')}] {user_msg[:200]} || {full_reply[:400]}",
                    type="episodic", source="ez_home_chat",
                    owner_email=owner_email or None,
                    extra_meta={"project_id": project.get("id"),
                                  "project_title": project.get("title", "")[:80]})
    except Exception as e:
        _log.debug("memory.router.write fail: %s", e)

    try:
        from src.memory import change_log as _cl
        _cl.log(title=f"chat turn: {user_msg[:50]}",
                 action_type="chat",
                 description=f"pid={project.get('id')} user={user_msg[:200]}",
                 why_better="user dialogue accumulated for cross-session context",
                 impact={"project_id": project.get("id")})
    except Exception as e:
        _log.debug("change_log.log fail: %s", e)
