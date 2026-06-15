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
    """Single-core system prompt: persona → RAG inject → rule overlay.

    Per UX_CHAT_DESIGN_SPEC §1: chat 말풍선엔 chat_style 주입(결론 먼저, 거대헤더 금지,
    짧은 문단). paper_writing이 아닌 chat task로 호출 → prompt_loader가 chat_style
    합성 → 응답 톤이 문서체 → 대화체로 전환.
    """
    try:
        from src.agent.persona import get_system_prompt
        base_sys = get_system_prompt(task="chat", owner_email=owner_email or None)
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


def stream_turn(project: dict, msg: str, *,
                  owner_email: str = "",
                  save_project_fn=None,
                  max_tokens: int = 4096,
                  max_iters: int = 6):
    """3-Lane event generator — FRONTEND_MIGRATION_SPEC §5.5.3.

    HOT (<300ms):  status emit immediately (no model wait)
    STREAM:        tool_start / tool_result / token events as LLM dispatches tools
    BACKGROUND:    provenance / confidence / critique deferred → badge events at end

    Yields ChatEvent. ez_home / FastAPI both consume this same generator.
    """
    from src.service import events as ev
    import time as _t

    # === HOT LANE — instant ack (no LLM wait) ===
    t0 = _t.time()
    yield ev.status("이해 중", lane="hot", elapsed_ms=int((_t.time()-t0)*1000))

    # Build system prompt (cached when project unchanged)
    full_sys = build_full_system(project, msg, owner_email=owner_email)
    yield ev.status("컨텍스트 합성 완료", lane="hot",
                       elapsed_ms=int((_t.time()-t0)*1000))

    try:
        from app.agentic_loop import TOOL_SCHEMAS, make_tool_handler
    except Exception as e:
        yield ev.error("agentic_loop_import", str(e)[:200])
        yield ev.done()
        return

    _proj_ref = {"p": project}
    _tool_events: list = []   # captured tool events to yield after dispatch

    def _get(): return _proj_ref["p"]
    def _set(p):
        _proj_ref["p"] = p
        if save_project_fn:
            try: save_project_fn(p)
            except Exception as _e: _log.debug("save_project_fn fail: %s", _e)
    def _evt(t, payload):
        # Map legacy tool handler events → ChatEvent
        if t == "preview_patched":
            _tool_events.append(ev.tool_result("patch_preview", payload))
        elif t == "user_message":
            _tool_events.append(ev.status(payload.get("user_message", "")[:200]))
        else:
            _tool_events.append(ev.status(f"{t}: {str(payload)[:120]}"))

    handler = make_tool_handler(_get, _set, _evt)

    # === STREAM LANE — native tool-use dispatch ===
    yield ev.status("LLM dispatch 시작", lane="stream")

    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="chat_orchestrate")
        active = getattr(client, "_active", client)

        # ★ Streaming + tools (2026-06-15) — 토큰 단위 yield로 Claude/VS Code 양식 효과
        if hasattr(active, "generate_with_tools_streamed"):
            text_acc: list = []
            for chunk in active.generate_with_tools_streamed(
                    user_message=msg, tools=TOOL_SCHEMAS, tool_handler=handler,
                    system_prompt=full_sys, max_tokens=max_tokens, max_iters=max_iters):
                ct = chunk.get("type")
                if ct == "text_delta":
                    text_acc.append(chunk.get("text", ""))
                    yield ev.token("body", chunk.get("text", ""))
                elif ct == "tool_start":
                    yield ev.tool_start(chunk.get("tool", "?"),
                                          args_brief=str(chunk.get("input", ""))[:120])
                elif ct == "tool_result":
                    yield ev.tool_result(chunk.get("tool", "?"),
                                            {"preview": (chunk.get("result_preview") or "")[:300]})
                elif ct == "error":
                    yield ev.warning("stream_partial", chunk.get("msg", "")[:200])
                elif ct == "done":
                    # captured preview_patched 등 chat events flush
                    for e in _tool_events: yield e
                    _tool_events.clear()
            text = "".join(text_acc)
        elif hasattr(active, "generate_with_tools"):
            # Non-streaming tool-use fallback
            result = active.generate_with_tools(
                user_message=msg, tools=TOOL_SCHEMAS, tool_handler=handler,
                system_prompt=full_sys, max_tokens=max_tokens, max_iters=max_iters,
            )
            text = result.get("text", "")
            trace = result.get("trace") or []
            for t in trace:
                yield ev.tool_start(t.get("tool", "?"),
                                      args_brief=str(t.get("input", ""))[:120])
                yield ev.tool_result(t.get("tool", "?"),
                                       {"preview": (t.get("result_preview") or "")[:400]})
            for e in _tool_events:
                yield e
            if text:
                yield ev.token("body", text)
        else:
            # Plain streamed text fallback
            yield ev.warning("no_tools", "client lacks tool-use, text-only stream")
            buf = []
            for chunk in client.generate_streamed(msg, system_prompt=full_sys,
                                                      max_tokens=max_tokens):
                if chunk:
                    buf.append(chunk)
                    yield ev.token("body", chunk)
            text = "".join(buf)
    except Exception as e:
        # 에러 출력은 silent log + UI에는 한 줄만
        _log.warning("dispatch fail: %s", str(e)[:300])
        yield ev.error("dispatch", str(e)[:150])
        yield ev.done()
        return

    # === BACKGROUND LANE — deferred verification badges (non-blocking concept) ===
    # NOTE: Streamlit context blocks true async. We emit badges inline but mark them
    # as background so the UI knows they came after primary content.
    try:
        from src.reliability.confidence import aggregate
        manuscript = (_proj_ref["p"].get("research_state") or {}).get("manuscript_text") or text
        rep = aggregate(draft=manuscript)
        yield ev.badge("confidence", rep.overall,
                          components=rep.components, lane="background")
        for issue in rep.issues[:3]:
            yield ev.warning("provenance", issue, lane="background")
    except Exception as e:
        _log.debug("background confidence fail: %s", e)

    yield ev.done(elapsed_ms=int((_t.time()-t0)*1000),
                     n_tool_events=len(_tool_events))


def dispatch_with_tools(project: dict, user_msg: str, *,
                           owner_email: str = "",
                           save_project_fn=None,
                           append_chat_event_fn=None,
                           max_tokens: int = 4096,
                           max_iters: int = 6) -> dict:
    """Native Anthropic tool-use dispatch — replaces regex JSON parser.

    LLM이 tools=[patch_preview, kyrbs_stat, rag_search, ...] 양식 tool_use 블록을 반환하면
    agentic_loop.make_tool_handler 가 직접 실행 → project.sections 갱신.
    이걸로 patch_preview/stat/figure/refs/strobe/rag 18개 툴 동시 작동.

    save_project_fn: callback(project_dict) — handler가 project를 mutate한 후 호출
    append_chat_event_fn: callback(event_type, payload) — preview_patched 등 chat 이벤트

    Returns: {"text": str, "trace": list, "stop_reason": str, "iters": int}
    """
    full_sys = build_full_system(project, user_msg, owner_email=owner_email)
    try:
        from app.agentic_loop import TOOL_SCHEMAS, make_tool_handler
    except Exception as e:
        _log.warning("agentic_loop import fail: %s", e)
        return {"text": f"(agentic_loop import 실패: {e})", "trace": [],
                 "stop_reason": "import_error", "iters": 0}

    _proj_ref = {"p": project}

    def _get(): return _proj_ref["p"]
    def _set(p):
        _proj_ref["p"] = p
        if save_project_fn:
            try: save_project_fn(p)
            except Exception as e: _log.debug("save_project_fn fail: %s", e)
    def _evt(t, payload):
        if append_chat_event_fn:
            try: append_chat_event_fn(t, payload)
            except Exception as e: _log.debug("append_chat_event fn fail: %s", e)

    handler = make_tool_handler(_get, _set, _evt)

    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="paper_writing")
        # Unwrap failover wrapper if present
        active = getattr(client, "_active", client)
        if not hasattr(active, "generate_with_tools"):
            _log.warning("active client lacks generate_with_tools — text-only fallback")
            text = "".join(client.generate_streamed(user_msg, system_prompt=full_sys,
                                                       max_tokens=max_tokens))
            return {"text": text, "trace": [], "stop_reason": "no_tools",
                     "iters": 0}
        result = active.generate_with_tools(
            user_message=user_msg,
            tools=TOOL_SCHEMAS,
            tool_handler=handler,
            system_prompt=full_sys,
            max_tokens=max_tokens,
            max_iters=max_iters,
        )
        return result
    except Exception as e:
        _log.warning("dispatch_with_tools fail: %s", e)
        return {"text": f"(tool dispatch 실패: {e})", "trace": [],
                 "stop_reason": "exception", "iters": 0}


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
