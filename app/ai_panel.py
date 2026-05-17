"""
Persistent AI assistant panel — context-aware "vibe paper" chat.
Supports Claude (Anthropic), GPT-4 (OpenAI), Gemini (Google) via user's own API key.
"""
from __future__ import annotations
import os
import streamlit as st

_PROVIDERS = ["Claude (Anthropic)", "GPT-4 (OpenAI)", "Gemini (Google)"]

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


def _call_claude(messages: list, system: str, api_key: str) -> str:
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2048,
        system=system,
        messages=messages,
        thinking={"type": "adaptive"},
    )
    for block in resp.content:
        if block.type == "text":
            return block.text
    return ""


def _call_openai(messages: list, system: str, api_key: str) -> str:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        full_msgs = [{"role": "system", "content": system}] + messages
        resp = client.chat.completions.create(model="gpt-4o", messages=full_msgs, max_tokens=2048)
        return resp.choices[0].message.content
    except ImportError:
        return "⚠️ openai 패키지가 설치되지 않았습니다. `pip install openai`"


def _call_gemini(messages: list, system: str, api_key: str) -> str:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=system)
        history = []
        for m in messages[:-1]:
            role = "user" if m["role"] == "user" else "model"
            history.append({"role": role, "parts": [m["content"]]})
        chat = model.start_chat(history=history)
        resp = chat.send_message(messages[-1]["content"])
        return resp.text
    except ImportError:
        return "⚠️ google-generativeai 패키지가 설치되지 않았습니다."


def render_ai_panel(current_page: str, page_context: dict | None = None):
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

    provider = st.session_state.get("_ai_provider", _PROVIDERS[0])

    # ── Build context for system prompt ───────────────────────────
    ctx_lines = [f"현재 페이지: {current_page}"]
    if page_context:
        for k, v in page_context.items():
            ctx_lines.append(f"{k}: {str(v)[:600]}")
    context_str = "\n".join(ctx_lines)

    SYSTEM = f"""당신은 의학 연구 논문 공동 저자 AI 어시스턴트입니다.
조유선 스타일의 한국 공중보건 의학 논문 생산 파이프라인에서 사용자를 돕습니다.

=== 현재 사용자 작업 컨텍스트 ===
{context_str}
================================

역할:
- 연구 주제 선정, PubMed 검색 전략, 통계 분석 방법 제안
- 논문 섹션별 작성 지원 (Abstract, Introduction, Methods, Results, Discussion)
- KYRBS/K-PRESS 데이터셋 분석 조언
- 신규성 판단 및 연구 공백 식별
- 조유선 교수 스타일의 논문 구조와 표현 방식 유지

항상 한국어로 답변하고, 의학 통계와 역학 전문 용어를 정확하게 사용하세요.
사용자가 현재 보고 있는 페이지 컨텍스트를 충분히 활용하여 즉시 실행 가능한 조언을 제공하세요."""

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
                if "Claude" in provider:
                    answer = _call_claude(msgs_for_api, SYSTEM, api_key)
                elif "GPT" in provider:
                    answer = _call_openai(msgs_for_api, SYSTEM, api_key)
                else:
                    answer = _call_gemini(msgs_for_api, SYSTEM, api_key)
            except Exception as e:
                answer = f"⚠️ 오류: {e}"

        st.session_state["ai_messages"].append({"role": "assistant", "content": answer})
        st.rerun()

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🗑️ 초기화", key="_ai_clear", use_container_width=True):
            st.session_state["ai_messages"] = []
            st.rerun()
    with col_b:
        if st.button("📋 컨텍스트 보기", key="_ai_ctx", use_container_width=True):
            st.session_state["_show_ctx"] = not st.session_state.get("_show_ctx", False)

    if st.session_state.get("_show_ctx"):
        with st.expander("현재 컨텍스트", expanded=True):
            st.code(context_str, language="yaml")
