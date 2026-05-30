"""EZ-style 홈 — sapphire glass theme.

Streamlit **자동 멀티페이지**: 파일이 `app/pages/`에 있으면 사이드바에 자동 노출되고
URL `/ez_home`로 직접 접근 가능 (Streamlit Cloud 포함).

좌측 사이드바: Home / Search / Resources / Projects / Recents (커스텀)
중앙: 큰 입력바 ("논문 아이디어를 입력하세요…")
하단: 프로젝트 카드 그리드 (My projects / Recently viewed / Starred / Templates)

⚠️ 현재 상태(2026-05-27): UX/UI 디테일 미완 + e2e 기능 미연결. 기존 8501 단위
기능 UI(streamlit_app.py)는 작동하는 참고용으로 살아있음. 점진 개선 중.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

# pages/ez_home.py에서 직접 `import app.styles...`를 하려면 repo root가 sys.path에 있어야 함
_root = Path(__file__).resolve().parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

import streamlit as st

# ── Page-level config + 즉시 chrome_hide micro-CSS ──
# 사용자 사고(2026-05-30): chip 첫 클릭 전 진입 시점에 sapphire 미주입 + Streamlit chrome
# (Deploy/Stop/Menu/Toolbar) 노출되던 사고. 양식 양식 양식 양식 양식 양식 양식 양식.
# set_page_config는 module-level 첫 st 호출이어야 함 → import 직후로 옮김.
try:
    st.set_page_config(
        page_title="Medical-Agent · EZ home",
        page_icon="🔬",
        layout="wide",
        initial_sidebar_state="expanded",
    )
except Exception:
    pass  # streamlit_app.py가 이미 set_page_config 호출했으면 silently skip
# 양식 진입 즉시 chrome 숨김 — sapphire가 박히기 전 시점에 raw 양식 노출 차단
st.markdown(
    "<style>"
    "#MainMenu{visibility:hidden!important;display:none!important;}"
    "header[data-testid='stHeader']{background:transparent!important;}"
    "[data-testid='stToolbar']{display:none!important;}"
    "[data-testid='stToolbarActions']{display:none!important;}"
    "[data-testid='stDecoration']{display:none!important;}"
    "[data-testid='stStatusWidget']{display:none!important;}"
    "[data-testid='stAppDeployButton']{display:none!important;}"
    ".stDeployButton{display:none!important;}"
    "button[kind='header']{display:none!important;}"
    "footer{visibility:hidden!important;display:none!important;}"
    "html,body,[data-testid='stApp']{background:#1E1B4B!important;color:#F5F5FA!important;}"
    "</style>",
    unsafe_allow_html=True,
)

from app.styles.sapphire_glass import (
    inject_sapphire_glass, hero_title, glass_card, chip_row,
    project_grid, action_card,
)


_PROJECTS_DIR = Path("data/working_papers")
_UPLOAD_DIR = Path("data/uploads")


def _enqueue_uploaded_files(uploaded_files, prompt_hint: str = "") -> None:
    """첨부 파일을 디스크에 저장하고, 양식별로 적절한 backlog job 등록.
    - PDF/DOCX/TXT → paper_ingest (논문 학습)
    - PNG/JPG       → vision_check (figure 검증)
    """
    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    try:
        from src.runtime.backlog import enqueue
    except Exception as e:
        st.error(f"backlog import 실패: {e}")
        return
    owner = st.session_state.get("user_email", "")
    n_paper, n_vision = 0, 0
    for f in uploaded_files:
        target = _UPLOAD_DIR / f.name
        try:
            target.write_bytes(f.getbuffer())
        except Exception as e:
            st.warning(f"저장 실패 {f.name}: {e}")
            continue
        ext = target.suffix.lower()
        if ext in (".pdf", ".docx", ".txt"):
            enqueue("paper_ingest",
                     {"path": str(target), "filename": f.name, "hint": prompt_hint[:300]},
                     owner=owner)
            n_paper += 1
        elif ext in (".png", ".jpg", ".jpeg"):
            enqueue("vision_check",
                     {"path": str(target), "filename": f.name},
                     owner=owner)
            n_vision += 1
    if n_paper or n_vision:
        st.success(f"📥 백로그 등록: 논문 {n_paper}편 · 이미지 {n_vision}장")


def _load_projects() -> list[dict]:
    """data/working_papers/*.json 스캔 → 카드용 dict 리스트."""
    out: list[dict] = []
    if not _PROJECTS_DIR.exists():
        return out
    for jp in sorted(_PROJECTS_DIR.glob("*.json"),
                      key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            data = json.loads(jp.read_text(encoding="utf-8"))
            title = data.get("title") or data.get("topic", {}).get("title") or jp.stem
            edited = datetime.fromtimestamp(jp.stat().st_mtime).strftime("Edited %Y-%m-%d")
            status = "Published" if data.get("status") == "published" else ""
            grads = [
                "linear-gradient(135deg, #1E1B4B, #312E81)",
                "linear-gradient(135deg, #312E81, #7C3AED)",
                "linear-gradient(135deg, #581C87, #EC4899)",
                "linear-gradient(135deg, #1E3A8A, #06B6D4)",
            ]
            out.append({"title": title[:60], "edited": edited, "status": status,
                         "gradient": grads[len(out) % len(grads)],
                         "id": jp.stem})
        except Exception:
            continue
    return out


def _sidebar():
    st.sidebar.markdown(
        "<div style='padding:8px 4px 16px 4px;font-weight:700;font-size:1.1rem;'>"
        "<span style='background:linear-gradient(135deg,#3B82F6,#8B5CF6);"
        "-webkit-background-clip:text;-webkit-text-fill-color:transparent;'>"
        "Medical-Agent</span>"
        "</div>", unsafe_allow_html=True)

    nav = st.sidebar.radio("nav", ["🏠 Home", "🔍 Search", "📚 Resources", "🔌 Connectors"],
                            label_visibility="collapsed", key="sg_nav")
    st.sidebar.markdown("<div style='margin:18px 0 6px 0;color:#A3A3B8;"
                         "font-size:0.78rem;letter-spacing:0.08em;'>PROJECTS</div>",
                         unsafe_allow_html=True)
    sub = st.sidebar.radio("subnav", ["▦ All projects", "★ Starred",
                                       "👤 Created by me", "👥 Shared with me"],
                            label_visibility="collapsed", key="sg_subnav")
    st.sidebar.markdown("<div style='margin:18px 0 6px 0;color:#A3A3B8;"
                         "font-size:0.78rem;letter-spacing:0.08em;'>RECENTS</div>",
                         unsafe_allow_html=True)
    projects = _load_projects()
    for p in projects[:5]:
        if st.sidebar.button(p["title"][:24], key=f"sg_recent_{p['id']}",
                              use_container_width=True):
            st.session_state["sg_active_project"] = p["id"]
            try:
                st.switch_page("pages/project_workspace.py")
            except Exception:
                st.rerun()
    return nav, sub, projects


def render() -> None:
    """홈 렌더링 — `app/streamlit_app.py`에서 호출."""
    inject_sapphire_glass()
    # 모달 dialog가 pending이면 먼저 띄움 (FAB/chip 클릭 시)
    try:
        from app.sapphire_actions import render_open_action_if_any, render_fab
        render_open_action_if_any()
    except Exception:
        render_fab = None
    _, _, projects = _sidebar()

    # Top notice
    st.markdown(
        "<div style='display:flex;justify-content:center;margin-top:24px;'>"
        "<div class='sg-chip active'>⚡ Powered by Claude · OpenAI · Gemini · 3중 자동 폴백</div>"
        "</div>", unsafe_allow_html=True)

    # Hero
    user_name = st.session_state.get("user_name", "Researcher")
    hero_title(f"좋은 아이디어 있으세요, {user_name}?")

    # Big input + 파일 첨부 (러버블 양식: + 버튼 → uploader)
    with st.container():
        c1, c2 = st.columns([6, 1])
        with c1:
            prompt = st.text_area(
                "prompt", placeholder="논문 아이디어 / KYRBS 분석 / Yoosun 스타일 재작성 요청…\n"
                                       "💡 파일을 첨부하면 자동으로 백로그에 학습/분석 작업으로 등록됩니다.",
                label_visibility="collapsed", height=110, key="sg_home_prompt")
            uploaded = st.file_uploader(
                "📎 파일 첨부 (PDF/DOCX/이미지 — 논문 학습·참고·vision 검증)",
                type=["pdf", "docx", "txt", "png", "jpg", "jpeg", "sav", "csv", "xlsx"],
                accept_multiple_files=True, key="sg_home_files",
                label_visibility="visible")
        with c2:
            st.markdown("<div style='height:40px;'></div>", unsafe_allow_html=True)
            send = st.button("✨ Build", use_container_width=True, type="primary",
                              key="sg_home_send")
            st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
            st.caption(f"📎 {len(uploaded) if uploaded else 0} 파일")

    if send and (prompt or uploaded):
        # 1) 파일 첨부 — 백로그 enqueue (즉시 처리 X, 미처리 로그에 표시)
        if uploaded:
            _enqueue_uploaded_files(uploaded, prompt_hint=prompt)
        # 2) prompt가 있으면 workspace 진입
        if prompt:
            st.session_state["sg_active_project"] = "new"
            st.session_state["sg_initial_prompt"] = prompt
            st.session_state["sg_view"] = "workspace"
            try:
                st.switch_page("pages/project_workspace.py")
            except Exception:
                st.rerun()
        else:
            st.toast(f"{len(uploaded)}개 파일을 백로그에 등록함. /backlog에서 진행도 확인",
                      icon="📥")
            st.rerun()

    # ── Quick actions (통합 matrix) — chip + modal + slash 단일 진입 ──
    st.markdown("<div style='max-width:1080px;margin:10px auto 24px auto;'>",
                 unsafe_allow_html=True)
    try:
        from app.styles.quick_actions import render_quick_actions, render_last_slash_result
        render_quick_actions(context="ez_home", n_cols=4, max_actions=8)
        render_last_slash_result()
    except Exception as e:
        st.warning(f"Quick actions 로드 실패: {e}")
    st.markdown("</div>", unsafe_allow_html=True)

    # Tabs
    st.markdown("<div style='max-width:1080px;margin:24px auto 0 auto;'>",
                 unsafe_allow_html=True)
    tab_my, tab_recent, tab_star, tab_template = st.tabs(
        ["My projects", "Recently viewed", "Starred", "Templates"])

    with tab_my:
        if projects:
            project_grid(projects)
        else:
            st.markdown(
                "<div class='sg-card' style='text-align:center;color:#A3A3B8;'>"
                "아직 프로젝트가 없습니다. 위 입력바에 아이디어를 적어 첫 논문을 시작하세요."
                "</div>", unsafe_allow_html=True)
    with tab_recent:
        project_grid(projects[:3])
    with tab_star:
        st.markdown("<div class='sg-card' style='color:#A3A3B8;'>"
                     "★ 표시한 프로젝트가 여기 나타납니다.</div>", unsafe_allow_html=True)
    with tab_template:
        # 템플릿 — Lovable처럼 시드된 양식
        tpl_html = (
            "<div class='sg-project-grid'>"
            "<div class='sg-project-card'>"
            "<div class='sg-project-thumb' style='background:linear-gradient(135deg,#1E3A8A,#06B6D4);'>"
            "<div style='position:absolute;bottom:8px;left:8px;'>"
            "<span class='sg-badge'>Template</span></div></div>"
            "<div class='sg-project-meta'><div class='sg-project-title'>"
            "Cross-sectional · STROBE (Yoosun 양식)</div>"
            "<div class='sg-project-date'>KYRBS 2025 / IMRAD 기본</div></div></div>"
            "<div class='sg-project-card'>"
            "<div class='sg-project-thumb' style='background:linear-gradient(135deg,#581C87,#EC4899);'>"
            "<div style='position:absolute;bottom:8px;left:8px;'>"
            "<span class='sg-badge'>Template</span></div></div>"
            "<div class='sg-project-meta'><div class='sg-project-title'>"
            "Cohort · STROBE 코호트</div>"
            "<div class='sg-project-date'>KNHANES 다년 추적 / 생존분석</div></div></div>"
            "<div class='sg-project-card'>"
            "<div class='sg-project-thumb' style='background:linear-gradient(135deg,#312E81,#7C3AED);'>"
            "<div style='position:absolute;bottom:8px;left:8px;'>"
            "<span class='sg-badge'>Template</span></div></div>"
            "<div class='sg-project-meta'><div class='sg-project-title'>"
            "Systematic review · PRISMA</div>"
            "<div class='sg-project-date'>PubMed 자동 수집 + 평가</div></div></div>"
            "</div>"
        )
        st.markdown(tpl_html, unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    # ── Floating Action Button (우하단 quick-action 메뉴) ──
    try:
        from app.sapphire_actions import render_fab as _render_fab
        _render_fab()
    except Exception:
        pass


# Streamlit 멀티페이지: 페이지 파일을 runpy로 실행하므로 무조건 render() 호출
# (Streamlit은 `runpy.run_path(...,run_name='__main__')` 으로 page를 실행)
try:
    render()
except Exception as _e:
    import traceback
    st.error(f"EZ home 렌더 실패: {_e}")
    st.code(traceback.format_exc())
    st.info("기존 단위 기능 UI는 메인(/) 페이지에서 정상 동작합니다.")
