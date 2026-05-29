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
  · slash + modal + seed 양식 자유 혼합
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

    st.markdown("<div class='sg-chip-row' style='margin-top:8px;'></div>",
                 unsafe_allow_html=True)
    cols = st.columns(n_cols)
    for i, a in enumerate(items):
        with cols[i % n_cols]:
            label = f"{a['icon']} {a['label']}"
            key = f"qa_{context}_{a['key'].replace('/','_')}"
            help_txt = a.get("desc", "")
            if st.button(label, key=key, use_container_width=True, help=help_txt):
                _dispatch(a, context=context, on_slash=on_slash)


def _dispatch(action: Dict, *, context: str, on_slash=None) -> None:
    """action.kind에 따라 분기."""
    kind = action.get("kind")
    key = action.get("key")
    payload = action.get("payload") or {}

    if kind == "slash":
        # 즉시 실행 (인자 없는 경우 default payload로)
        try:
            from src.agent.slash_commands import run_slash
            result = run_slash(key, payload)
            if on_slash:
                on_slash(key, result)
            else:
                if result.get("ok"):
                    st.toast(f"{key} 실행됨", icon="✅")
                    st.session_state[f"_qa_last_{key}"] = result
                else:
                    st.error(f"{key} 실패: {result.get('error', '')}")
        except Exception as e:
            st.error(f"slash 실패: {e}")

    elif kind == "modal":
        try:
            from app.sapphire_actions import open_action
            open_action(key, **payload)
        except Exception as e:
            st.error(f"modal 실패: {e}")

    elif kind == "chat_seed":
        # workspace 진입 + prompt seed 채우기
        prompt = payload.get("prompt", "")
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
