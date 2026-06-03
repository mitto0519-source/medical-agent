"""Unified Quick Action Matrix — EZ home chip + sapphire_actions modal + slash_commands 통합.

사용자 진단 (2026-05-29): "Quick action 3중복 — 통폐합 필요".

설계:
  · 모든 quick action은 (label, kind, key, payload, icon)로 정의
  · kind ∈ {"slash", "modal", "chat_seed"}:
      - "slash"      → src.agent.slash_commands.run_slash 직접 실행 (즉시)
      - "modal"      → app.sapphire_actions.open_action 모달 띄움
      - "chat_seed"  → workspace 입력에 prompt seed 채우고 진입
  · 같은 UI 양식 (sapphire glass chip) — 어디 페이지에서 호출하든 동일

호출:
    from app.styles.quick_actions import render_quick_actions
    render_quick_actions(context="ez_home", n_cols=4)
    render_quick_actions(context="workspace", n_cols=3)  # workspace용 subset

장점:
  · 한 군데서 정의 → 일관성
  · 새 action 추가/수정 한 군데
  · slash + modal + seed  자유 혼합
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import streamlit as st


# ── Action registry (단일 진실원본) ─────────────────────────────────────────

# 각 action: {"label", "icon", "kind", "key", "payload", "contexts"}
#   contexts: 어느 페이지에서 노출할지 ("ez_home", "workspace", "backlog", ...)
QUICK_ACTIONS: List[Dict[str, Any]] = [
    # ── 의학 논문 lifecycle 7 슬래시 ──
    {"label": "Research Question",  "icon": "🔬", "kind": "slash",
     "key": "/research-question",
     "payload": {"topic": ""},
     "contexts": ["ez_home", "workspace"],
     "desc": "PubMed 신규성 + cross-modal 검색"},
    {"label": "Study Design",       "icon": "📐", "kind": "slash",
     "key": "/study-design",
     "payload": {"sections": {}},
     "contexts": ["workspace"],
     "desc": "STROBE 22 + design 검증"},
    {"label": "Run Analysis",       "icon": "📊", "kind": "slash",
     "key": "/run-analysis",
     "payload": {"outcome": "depression", "exposure": "zcb_freq"},
     "contexts": ["ez_home", "workspace"],
     "desc": "KYRBS 2025 svy logistic"},
    {"label": "Draft Section",      "icon": "📝", "kind": "slash",
     "key": "/draft-section",
     "payload": {"section": "Introduction", "goal": "ZCB depression"},
     "contexts": ["ez_home", "workspace"],
     "desc": "content+style Planner DAG"},
    {"label": "STROBE Review",      "icon": "📑", "kind": "slash",
     "key": "/strobe-review",
     "payload": {"text": "", "study_design": "cross_sectional"},
     "contexts": ["ez_home", "workspace"],
     "desc": "STROBE+consistency+causal"},
    {"label": "Submit Journal",     "icon": "📤", "kind": "slash",
     "key": "/submit-journal",
     "payload": {"project": {}},
     "contexts": ["workspace"],
     "desc": "docx+figure+EndNote"},
    {"label": "Research Pulse",     "icon": "📡", "kind": "slash",
     "key": "/research-pulse",
     "payload": {},
     "contexts": ["ez_home", "workspace", "backlog", "dashboard"],
     "desc": "전체 자산 진척 요약"},

    # ── 부가기능 modals (sapphire_actions) ──
    {"label": "신규성 확인",        "icon": "🔍", "kind": "modal",
     "key": "novelty", "payload": {},
     "contexts": ["ez_home", "workspace"],
     "desc": "PubMed 신규성 평가 + chat 삽입"},
    {"label": "Yoosun 스타일",      "icon": "✍️", "kind": "modal",
     "key": "yoosun", "payload": {},
     "contexts": ["workspace"],
     "desc": "본문 → Yoosun voice 재작성"},
    {"label": "본문 일관성",        "icon": "🔍", "kind": "modal",
     "key": "consistency", "payload": {},
     "contexts": ["workspace"],
     "desc": "n/OR-CI/P값/연도 모순"},
    {"label": "Figure 생성",        "icon": "🎨", "kind": "modal",
     "key": "figure", "payload": {},
     "contexts": ["workspace"],
     "desc": "Forest/ROC/Bar publication-grade"},
    {"label": "인용/Ref 관리",      "icon": "📚", "kind": "modal",
     "key": "citation", "payload": {},
     "contexts": ["workspace"],
     "desc": "PubMed → Vancouver/EndNote"},
    {"label": "지식 위키",          "icon": "🧠", "kind": "modal",
     "key": "wiki", "payload": {},
     "contexts": ["ez_home", "workspace"],
     "desc": "누적 개념·증례 위키"},
    {"label": "자동 학습",          "icon": "🎓", "kind": "modal",
     "key": "learn", "payload": {},
     "contexts": ["dashboard", "backlog"],
     "desc": "OA bulk 학습 컨트롤"},

    # ── 작업실 진입 seed (chat_seed) ──
    {"label": "ZCB 빠른 분석",      "icon": "⚡", "kind": "chat_seed",
     "key": "kyrbs_quick",
     "payload": {"prompt": "KYRBS 2025 ZCB-depression 빠른 분석 + Table 1 만들어줘"},
     "contexts": ["ez_home"],
     "desc": "샘플 프로젝트 seed"},
]


def actions_for(context: str) -> List[Dict]:
    """특정 context에서 노출할 action 목록."""
    return [a for a in QUICK_ACTIONS if context in a.get("contexts", [])]


def render_quick_actions(*, context: str, n_cols: int = 4,
                          on_slash=None, max_actions: int = 12) -> None:
    """Sapphire glass chip 그리드로 렌더. 클릭 시 kind에 따라 dispatch.

    Args:
        context: "ez_home"|"workspace"|"backlog"|"dashboard"
        n_cols: 칼럼 수
        on_slash: 슬래시 실행 콜백 (None이면 즉시 실행 + st.toast)
        max_actions: 최대 표시 수
    """
    items = actions_for(context)[:max_actions]
    if not items:
        return

    # ★ 2026-06-01 (사용자 사고 fix): 카드 강제 양식
    # - 다크 배경 + 흰 글자 + 무테 + 좌측 정렬 + 앞 여백 (Anymorph 양식)
    # - 아이콘과 라벨 사이 여백, 라벨 font-weight 정돈
    # 컨테이너 id 단위로 scope해서 다른 페이지 stButton에 영향 없음
    st.markdown(f"""
    <style>
    /* Quick action 카드 — 이 컨테이너 내부의 stButton에만 적용 (페이지 다른 버튼 보존) */
    div[data-testid="stHorizontalBlock"]:has(button[data-qa-{context}]) .stButton > button,
    .qa-grid-{context} .stButton > button {{
      background: #0F172A !important;
      color: #FFFFFF !important;
      border: none !important;
      border-radius: 14px !important;
      text-align: left !important;
      padding: 16px 20px 16px 22px !important;
      font-size: 0.92rem !important;
      font-weight: 500 !important;
      letter-spacing: -0.01em !important;
      min-height: 58px !important;
      box-shadow: 0 1px 2px rgba(15,23,42,0.06), 0 4px 12px rgba(15,23,42,0.06) !important;
      transition: all 150ms cubic-bezier(0.4, 0, 0.2, 1) !important;
      display: flex !important;
      align-items: center !important;
      justify-content: flex-start !important;
    }}
    .qa-grid-{context} .stButton > button:hover {{
      background: #1E293B !important;        /* slate-800 */
      transform: translateX(2px) !important;
      box-shadow: 0 2px 6px rgba(15,23,42,0.10), 0 8px 20px rgba(15,23,42,0.10) !important;
    }}
    .qa-grid-{context} .stButton > button p {{
      margin: 0 !important;
      color: #FFFFFF !important;
      font-weight: 500 !important;
    }}
    </style>
    <div class='qa-grid-{context}'>
    """, unsafe_allow_html=True)

    cols = st.columns(n_cols)
    for i, a in enumerate(items):
        with cols[i % n_cols]:
            # 아이콘과 라벨 사이 양식 — wide-space로 시각적 여백 확보 (Anymorph 양식)
            label = f"{a['icon']}    {a['label']}"
            key = f"qa_{context}_{a['key'].replace('/','_')}"
            help_txt = a.get("desc", "")
            if st.button(label, key=key, use_container_width=True, help=help_txt):
                _dispatch(a, context=context, on_slash=on_slash)
    st.markdown("</div>", unsafe_allow_html=True)


def _read_user_prompt() -> str:
    """현재 페이지의 입력바 값을 읽어 slash 인자로 자동 주입.
    ez_home은 sg_home_prompt, workspace는 ws_form 안 text_area — 둘 다 시도."""
    for k in ("sg_home_prompt", "ws_input_text", "sg_workspace_prompt"):
        v = st.session_state.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


# slash별 "필수 인자 → 사용자 prompt에서 채울 키" 매핑 (2026-05-30 fix)
_PROMPT_FILLS = {
    "/research-question": ["topic", "query"],
    "/study-design":      [],  # sections는 prompt가 아니라 docx에서 와야 함
    "/run-analysis":      ["exposure"],
    "/draft-section":     ["goal"],
    "/strobe-review":     ["text"],
    "/submit-journal":    [],
    "/research-pulse":    [],
}

# slash별 "최소 필요 인자" — 부족하면 inline form 띄움
_REQUIRED_ARGS = {
    "/research-question": ["topic"],
    "/study-design":      ["sections"],
    "/run-analysis":      ["exposure"],
    "/strobe-review":     ["text"],
    "/submit-journal":    ["project"],
}


def _autofill_payload(slash_key: str, base_payload: Dict) -> Dict:
    """입력바 prompt를 _PROMPT_FILLS에 따라 빈 인자에 자동 주입."""
    p = dict(base_payload)
    user_text = _read_user_prompt()
    if not user_text:
        return p
    for arg in _PROMPT_FILLS.get(slash_key, []):
        if not p.get(arg):
            p[arg] = user_text
    return p


def _missing_required(slash_key: str, payload: Dict) -> list:
    """필수 인자 중 빈 키들 반환."""
    req = _REQUIRED_ARGS.get(slash_key, [])
    return [k for k in req if not payload.get(k)]


def _dispatch(action: Dict, *, context: str, on_slash=None) -> None:
    """action.kind에 따라 분기.

    slash kind 처리 흐름 (2026-05-30 fix):
      1) 입력바 prompt가 있으면 _PROMPT_FILLS에 따라 자동 인자 주입
      2) 필수 인자가 여전히 비어있으면 inline form을 띄워 사용자에게 안내 (즉시 실패 X)
      3) 다 채워졌으면 run_slash 실행
    """
    kind = action.get("kind")
    key = action.get("key")
    base_payload = action.get("payload") or {}

    if kind == "slash":
        payload = _autofill_payload(key, base_payload)
        missing = _missing_required(key, payload)
        if missing:
            # 사용자에게 명확히 안내 — 즉시 fail 토스트 대신 inline 안내
            need = ", ".join(missing)
            st.session_state[f"_qa_need_{key}"] = {
                "missing": missing, "label": action.get("label", key),
                "hint": (
                    f"💡 입력바에 {need}을(를) 입력 후 다시 누르면 자동 실행됩니다."
                    if "topic" in missing or "text" in missing or "exposure" in missing
                    else f"이 액션은 {need} 인자가 필요합니다."
                ),
            }
            st.warning(
                f"**{action.get('label', key)}** — 입력바에 `{need}`을(를) "
                f"먼저 적고 다시 눌러 주세요."
            )
            return

        # 인자 OK — 실행
        try:
            from src.agent.slash_commands import run_slash
            with st.spinner(f"{action.get('label', key)} 실행 중..."):
                result = run_slash(key, payload)
            if on_slash:
                on_slash(key, result)
            else:
                if result.get("ok"):
                    st.toast(f"{action.get('label', key)} 완료", icon="✅")
                    st.session_state[f"_qa_last_{key}"] = result
                else:
                    st.error(f"{action.get('label', key)} 실패: {result.get('error', '')}")
        except Exception as e:
            st.error(f"slash 실패: {e}")

    elif kind == "modal":
        try:
            from app.sapphire_actions import open_action
            open_action(key, **base_payload)
        except Exception as e:
            st.error(f"modal 실패: {e}")

    elif kind == "chat_seed":
        # workspace 진입 + prompt seed 채우기 (사용자가 입력바에 적은 게 있으면 그걸 우선)
        prompt = _read_user_prompt() or base_payload.get("prompt", "")
        st.session_state["sg_active_project"] = "new"
        st.session_state["sg_initial_prompt"] = prompt
        try:
            st.switch_page("pages/project_workspace.py")
        except Exception:
            st.rerun()


def render_last_slash_result(*, slash: str = None) -> None:
    """가장 최근 슬래시 실행 결과 표시 (있으면)."""
    if slash:
        key = f"_qa_last_{slash}"
    else:
        # 최근 모든 slash result 중 1개
        candidates = [k for k in st.session_state if k.startswith("_qa_last_")]
        if not candidates:
            return
        key = sorted(candidates, key=lambda k: -hash(k))[0]
    r = st.session_state.get(key)
    if not r:
        return
    with st.expander(f"📋 마지막 슬래시 결과 · {key.replace('_qa_last_', '')}",
                       expanded=False):
        st.json(r.get("output") or r, expanded=False)
