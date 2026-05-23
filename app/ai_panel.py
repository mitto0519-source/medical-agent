"""
Persistent AI assistant panel — context-aware "vibe paper" chat.
Supports Claude (Anthropic), GPT-4 (OpenAI), Gemini (Google) via user's own API key.
"""
from __future__ import annotations
import os
import streamlit as st

from src.llm import get_llm_client

_PROVIDERS = ["🔄 자동 (무료 우선)", "Claude (Anthropic)", "GPT-4 (OpenAI)", "Gemini (Google)"]

PANEL_CSS = """
<style>
.ai-panel-header {
    display:flex; align-items:center; gap:8px;
    padding-bottom:10px; border-bottom:1px solid #30363d; margin-bottom:10px;
}
.ai-panel-title { font-size:14px; font-weight:700; color:#e6edf3; }
.ai-panel-sub { font-size:11px; color:#6e7681; margin-top:2px; }
.context-badge {
    font-size:11px; color:#8b5cf6; background:rgba(139,92,246,0.12);
    padding:2px 8px; border-radius:20px; display:inline-block; margin-bottom:8px;
}
.ai-history-item {
    padding:8px 10px; border-radius:6px; border:1px solid #30363d;
    background:#1c2128; margin-bottom:6px; font-size:12px; color:#8b949e;
}
.ai-history-ts { font-size:10px; color:#6e7681; }
</style>
"""


def _flatten_messages(messages: list) -> str:
    return "\n\n".join(
        f"{m['role'].capitalize()}: {m['content']}" for m in messages
    )


def _call_llm(provider: str, messages: list, system: str, api_key: str) -> str:
    """모든 provider를 통합 failover 클라이언트(get_llm_client)로 처리.

    - '🔄 자동' → provider 미지정. 건강도 우선순위로 작동하는(무료 Gemini 포함)
      provider를 자동 선택하고, 실패하면 나머지로 연쇄 폴백.
    - 특정 provider 지정 → 그 provider를 1순위로 두되 실패 시 나머지로 자동 폴백.
    페르소나/seed 주입은 build_base_system()을 공유하므로 어떤 provider로 가도 일관(규칙 9).
    """
    pk = provider.split()[0].lower()
    explicit = {
        "claude": "anthropic",
        "gpt-4": "openai", "gpt": "openai",
        "gemini": "google",
    }.get(pk)  # None이면 자동 (환경변수 기반 + 무료 우선 폴백)

    client = get_llm_client(
        api_key=api_key or None,
        provider=explicit,
        task="qa",
        with_failover=True,
    )
    return client.generate(
        _flatten_messages(messages),
        system_prompt=system,
        max_tokens=2048,
    )


def render_ai_panel(current_page: str, page_context: dict | None = None, user_email: str = ""):
    """Render the persistent AI assistant panel in the right column."""
    st.markdown(PANEL_CSS, unsafe_allow_html=True)

    st.markdown("""
    <div class="ai-panel-header">
        <span style="font-size:20px;">🤖</span>
        <div>
            <div class="ai-panel-title">AI 어시스턴트</div>
            <div class="ai-panel-sub">Vibe Paper — 컨텍스트 기반 연구 지원</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f'<div class="context-badge">📍 {current_page}</div>', unsafe_allow_html=True)

    # ── Provider & API key ──────────────────────────────────────────
    with st.expander("⚙️ LLM 설정", expanded=False):
        provider = st.selectbox("LLM Provider", _PROVIDERS, key="_ai_provider")
        api_key_input = st.text_input(
            "내 API Key (비워두면 시스템 키)",
            type="password", key="_ai_key",
            placeholder="sk-ant-... / sk-... / AI...",
            help="내 API Key를 입력하면 시스템 키 대신 사용됩니다.",
        )
        if st.button("💾 저장", key="_ai_save_key", use_container_width=True):
            if api_key_input:
                if "user" in st.session_state:
                    st.session_state.setdefault("user_api_keys", {})
                    provider_key = provider.split()[0].lower()
                    st.session_state["user_api_keys"][provider_key] = api_key_input
                    st.success("저장됨")

    if "_ai_provider" not in st.session_state:
        # 기본은 '🔄 자동 (무료 우선)' — Claude 고정 아님. 작동하는 provider 자동 폴백.
        st.session_state["_ai_provider"] = _PROVIDERS[0]

    provider = st.session_state.get("_ai_provider", _PROVIDERS[0])

    # ── Build context for system prompt ───────────────────────────
    ctx_lines = [f"현재 페이지: {current_page}"]
    if page_context:
        for k, v in page_context.items():
            ctx_lines.append(f"{k}: {str(v)[:600]}")
    context_str = "\n".join(ctx_lines)

    # ── Long-term continuity preamble ──────────────────────────────────
    # (페르소나는 _build_system()이 자동 주입 — 여기서 중복 추가 안 함)
    continuity_preamble = ""
    if user_email:
        try:
            from src.memory.continuity import get_preamble
            continuity_preamble = get_preamble(user_email=user_email, n=20)
        except Exception:
            pass

    # ── 세션 간 대화 맥락 ───────────────────────────────────────────────
    conv_ctx = ""
    try:
        from src.memory.conversation_memory import get_recent_context
        conv_ctx = get_recent_context(n=3, context_type="qa")
    except Exception:
        pass

    SYSTEM = f"""{continuity_preamble}

{conv_ctx}

=== 현재 사용자 작업 컨텍스트 ===
{context_str}
================================"""

    # ── Chat history ───────────────────────────────────────────────
    if "ai_messages" not in st.session_state:
        st.session_state["ai_messages"] = []

    chat_area = st.container(height=380)
    with chat_area:
        if not st.session_state["ai_messages"]:
            st.markdown("""
            <div style="text-align:center;padding:40px 16px;color:#6e7681;font-size:13px;">
                💬 질문을 입력하면 현재 페이지 컨텍스트를 기반으로<br>
                연구를 도와드립니다.<br><br>
                <span style="font-size:11px;">예: "이 주제의 novelty를 높이려면?"<br>
                "Methods 섹션을 어떻게 구성할까요?"</span>
            </div>
            """, unsafe_allow_html=True)
        for msg in st.session_state["ai_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # ── Input ──────────────────────────────────────────────────────
    prompt = st.chat_input("연구에 대해 물어보세요...", key="_ai_input")
    if prompt:
        st.session_state["ai_messages"].append({"role": "user", "content": prompt})

        # Resolve API key per provider
        saved_keys = st.session_state.get("user_api_keys", {})
        provider_key = provider.split()[0].lower()
        default_keys = {
            "claude": os.environ.get("ANTHROPIC_API_KEY", ""),
            "gpt-4": os.environ.get("OPENAI_API_KEY", ""),
            "gemini": os.environ.get("GOOGLE_API_KEY", ""),
        }
        api_key = (
            st.session_state.get("_ai_key")
            or saved_keys.get(provider_key)
            or default_keys.get(provider_key, "")
        )

        msgs_for_api = [{"role": m["role"], "content": m["content"]}
                        for m in st.session_state["ai_messages"]]

        with st.spinner("생각 중..."):
            try:
                # 모든 provider(자동 포함)를 통합 failover 클라이언트로 처리
                answer = _call_llm(provider, msgs_for_api, SYSTEM, api_key)
            except Exception as e:
                answer = f"⚠️ 오류: {e}"

        st.session_state["ai_messages"].append({"role": "assistant", "content": answer})

        # 대화 기억에 자동 저장 + 페르소나 record_exchange (세션 간 연속성)
        if "오류" not in answer[:10]:
            try:
                from src.memory.conversation_memory import record as _record_conv
                _record_conv(
                    user_message=prompt,
                    agent_response=answer,
                    topic=current_page,
                    context_type="qa",
                    quality="neutral",
                )
            except Exception:
                pass
            # 마지막 교환 저장 (👍 피드백용)
            st.session_state["_last_exchange"] = {
                "user": prompt,
                "answer": answer,
            }

        st.rerun()

    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("🗑️ 초기화", key="_ai_clear", use_container_width=True):
            st.session_state["ai_messages"] = []
            st.rerun()
    with col_b:
        if st.button("📋 컨텍스트 보기", key="_ai_ctx", use_container_width=True):
            st.session_state["_show_ctx"] = not st.session_state.get("_show_ctx", False)
    with col_c:
        last = st.session_state.get("_last_exchange")
        if last and st.button("👍 유용했어요", key="_ai_thumbsup", use_container_width=True):
            try:
                from src.agent.persona import get_persona
                get_persona().evolve_from_conversation(
                    user_message=last["user"],
                    agent_response=last["answer"],
                    feedback="positive",
                )
                try:
                    from src.memory.conversation_memory import record as _record_conv
                    _record_conv(
                        user_message=last["user"],
                        agent_response=last["answer"],
                        topic=current_page,
                        context_type="qa",
                        quality="positive",
                    )
                except Exception:
                    pass
                st.toast("페르소나가 이 대화에서 학습했습니다.")
                st.session_state.pop("_last_exchange", None)
            except Exception:
                pass

    if st.session_state.get("_show_ctx"):
        with st.expander("현재 컨텍스트", expanded=True):
            st.code(context_str, language="yaml")
