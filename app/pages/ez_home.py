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
# (Deploy/Stop/Menu/Toolbar) 노출되던 사고를 page-level micro-CSS로 차단.
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
#  진입 즉시 chrome 숨김 — sapphire가 박히기 전 시점에 raw  노출 차단
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
    # ★ 2026-06-01: 다크 강제(#1E1B4B) 제거 — sapphire_glass 라이트 톤에 위임.
    # 다크 강제가 라이트 톤을 덮어 카드 글자 invisible 사고의 직접 원인이었음.
    "html,body,[data-testid='stApp']{background:#FFFFFF!important;color:#0F172A!important;}"
    # Quick action 카드 — 페이지 전역 .stButton(default) 다크 카드 + 흰글자 강제
    ".stMainBlockContainer .stButton > button:not([kind='primary']),"
    ".stMain .stButton > button:not([kind='primary']) {"
    "  background:#0F172A !important;"
    "  color:#FFFFFF !important;"
    "  border:none !important;"
    "  border-radius:14px !important;"
    "  text-align:left !important;"
    "  padding:16px 20px 16px 22px !important;"
    "  font-size:0.92rem !important;"
    "  font-weight:500 !important;"
    "  min-height:58px !important;"
    "  box-shadow:0 1px 2px rgba(15,23,42,0.06),0 4px 12px rgba(15,23,42,0.06) !important;"
    "  display:flex !important; align-items:center !important; justify-content:flex-start !important;"
    "}"
    ".stMainBlockContainer .stButton > button:not([kind='primary']) *,"
    ".stMain .stButton > button:not([kind='primary']) * {"
    "  color:#FFFFFF !important;"
    "}"
    ".stMainBlockContainer .stButton > button:not([kind='primary']):hover,"
    ".stMain .stButton > button:not([kind='primary']):hover {"
    "  background:#1E293B !important;"
    "  transform:translateX(2px) !important;"
    "}"
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
        elif ext == ".json":
            # 프로젝트 .json 자동 import — sections/messages/references 가진 파일이면 작업실 진입
            try:
                data = json.loads(target.read_text(encoding="utf-8"))
                if isinstance(data, dict) and ("sections" in data or "messages" in data):
                    import uuid as _uuid
                    new_pid = f"imported_{_uuid.uuid4().hex[:10]}"
                    # working_papers/에 저장 (Supabase는 _save_project가 알아서 동기)
                    _PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
                    out_path = _PROJECTS_DIR / f"{new_pid}.json"
                    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                    st.session_state["sg_active_project"] = new_pid
                    st.success(f"📥 프로젝트 import: {new_pid} → 작업실로 이동합니다")
                    try:
                        st.switch_page("pages/project_workspace.py")
                    except Exception:
                        pass
            except Exception as _je:
                st.warning(f"JSON import 실패: {_je}")
    if n_paper or n_vision:
        st.success(f"📥 백로그 등록: 논문 {n_paper}편 · 이미지 {n_vision}장")


def _load_projects() -> list[dict]:
    """data/working_papers/*.json 스캔 + Supabase ma_working_papers 통합 (2026-05-30).
    로컬 docker에서 만든 프로젝트는 Supabase로 자동 sync되므로,
    클라우드에서 같은 user_email로 로그인하면 자동 표시."""
    out: list[dict] = []
    seen_ids: set = set()
    grads = [
        "linear-gradient(135deg, #1E1B4B, #312E81)",
        "linear-gradient(135deg, #312E81, #7C3AED)",
        "linear-gradient(135deg, #581C87, #EC4899)",
        "linear-gradient(135deg, #1E3A8A, #06B6D4)",
    ]

    # 1) Supabase (있으면 우선) — 클라우드에서 데이터 없어도 프로젝트 보기·첨삭 가능
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text as _sql
            owner = (st.session_state.get("user") or {}).get("email") or \
                     st.session_state.get("user_email", "")
            with get_engine().connect() as conn:
                if owner:
                    rows = conn.execute(_sql(
                        "SELECT id, title, updated_at FROM ma_working_papers "
                        "WHERE owner_email=:oe ORDER BY updated_at DESC LIMIT 50"),
                        {"oe": owner}).mappings().all()
                else:
                    rows = conn.execute(_sql(
                        "SELECT id, title, updated_at FROM ma_working_papers "
                        "ORDER BY updated_at DESC LIMIT 20")).mappings().all()
            for r in rows:
                pid = r["id"]
                if pid in seen_ids:
                    continue
                seen_ids.add(pid)
                title = (r["title"] or "Untitled")[:60]
                ts = r["updated_at"] or 0
                edited = datetime.fromtimestamp(ts).strftime("Edited %Y-%m-%d") if ts else "Edited (cloud)"
                out.append({"title": title, "edited": edited,
                             "status": "☁ Cloud",
                             "gradient": grads[len(out) % len(grads)],
                             "id": pid})
    except Exception:
        pass

    # 2) 로컬 working_papers/*.json (보조 — 동일 id 중복 제거)
    if _PROJECTS_DIR.exists():
        # 평탄: data/working_papers/{user}/{pid}.json + 직접 data/working_papers/{pid}.json
        all_jsons = list(_PROJECTS_DIR.glob("*.json")) + list(_PROJECTS_DIR.glob("*/*.json"))
        for jp in sorted(all_jsons, key=lambda p: p.stat().st_mtime, reverse=True):
            pid = jp.stem
            if pid in seen_ids:
                continue
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
                title = (data.get("title") or
                         (data.get("topic") or {}).get("title") or pid)[:60]
                edited = datetime.fromtimestamp(jp.stat().st_mtime).strftime("Edited %Y-%m-%d")
                status = "Published" if data.get("status") == "published" else ""
                seen_ids.add(pid)
                out.append({"title": title, "edited": edited, "status": status,
                             "gradient": grads[len(out) % len(grads)], "id": pid})
            except Exception:
                continue

    return out[:30]


def _sidebar():
    # Minimal sidebar — chat-first UX. 잡동사니 nav 제거. 사용자 + 로그아웃 + 새 채팅만.
    st.sidebar.markdown(
        "<div style='padding:12px 4px 24px 4px;font-weight:600;font-size:1.05rem;"
        "color:#0F172A;'>Medical-Agent</div>", unsafe_allow_html=True)

    if st.sidebar.button("✚ 새 채팅", use_container_width=True, key="sg_new_chat"):
        st.session_state["sg_active_project"] = "new"
        st.session_state["sg_initial_prompt"] = None
        st.rerun()

    st.sidebar.markdown("<div style='margin:24px 0 6px 0;color:#94A3B8;"
                         "font-size:0.72rem;letter-spacing:0.08em;'>RECENT</div>",
                         unsafe_allow_html=True)
    projects = _load_projects()
    for p in projects[:6]:
        if st.sidebar.button(p["title"][:28], key=f"sg_recent_{p['id']}",
                              use_container_width=True):
            st.session_state["sg_active_project"] = p["id"]
            try:
                st.switch_page("pages/project_workspace.py")
            except Exception:
                st.rerun()
            try:
                st.switch_page("pages/project_workspace.py")
            except Exception:
                st.rerun()
    return None, None, projects


def _project_path(pid: str) -> Path:
    _PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return _PROJECTS_DIR / f"{pid}.json"


def _load_or_init_project(pid: str, initial_title: str = "새 작업") -> dict:
    p = _project_path(pid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"id": pid, "title": initial_title[:60], "messages": [],
            "sections": {}, "updated": datetime.now().isoformat()}


def _save_project(project: dict) -> None:
    pid = project.get("id")
    if not pid:
        return
    project["updated"] = datetime.now().isoformat()
    try:
        _project_path(pid).write_text(
            json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    # Supabase mirror (best-effort)
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text as _sql
            owner = (st.session_state.get("user") or {}).get("email") or \
                     st.session_state.get("user_email", "")
            with get_engine().begin() as conn:
                conn.execute(_sql(
                    "INSERT INTO ma_working_papers (id, owner_email, title, data_json, updated_at) "
                    "VALUES (:id, :oe, :ti, :dj, :ts) "
                    "ON CONFLICT (id) DO UPDATE SET title=:ti, data_json=:dj, updated_at=:ts"),
                    {"id": pid, "oe": owner, "ti": project.get("title", "")[:200],
                     "dj": json.dumps(project, ensure_ascii=False),
                     "ts": int(datetime.now().timestamp())})
    except Exception:
        pass


def _is_autopilot_trigger(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    triggers = ["알아서 해", "알아서해", "go ahead", "그냥 해", "그냥해",
                 "전체 진행", "끝까지", "한번에", "full run", "auto run"]
    return any(k in t for k in triggers)


def _build_full_system(project: dict, user_msg: str) -> str:
    """단일 코어 system prompt 합성 (CLAUDE.md 규칙 12)."""
    try:
        from src.agent.persona import get_system_prompt
        base_sys = get_system_prompt(task="paper_writing")
    except Exception:
        base_sys = "당신은 의학 연구 코파일럿입니다."
    try:
        from app.agentic_loop import build_system_with_preview
        full_sys = build_system_with_preview(base_sys, project, user_msg)
    except Exception:
        full_sys = base_sys
    rule_overlay = (
        "\n\n--- RULE-8 (vibe paper) ---\n"
        "사용자 주제가 모호하면 PICO·데이터·통계·하위군 중 짧은 역질문 2-3개로 좁히세요.\n"
        "'알아서 해' '그냥 해' '한번에' 같은 trigger를 들으면 그때 자동 파이프라인을 진행합니다.\n"
        "응답은 한국어, 동료 의학연구자 어투, 마크다운 짧게."
    )
    return full_sys + rule_overlay


def _stream_reply(project: dict, user_msg: str):
    """generator — token 단위 yield. failover 클라이언트의 generate_streamed 사용."""
    try:
        from src.llm import get_llm_client
    except Exception as e:
        yield f"(LLM 클라이언트 import 실패: {e})"
        return

    full_sys = _build_full_system(project, user_msg)
    history = "\n".join(
        f"{'사용자' if m['role']=='user' else '코파일럿'}: {m['content']}"
        for m in project.get("messages", [])[-10:])
    prompt = f"{history}\n사용자: {user_msg}\n코파일럿:"

    try:
        client = get_llm_client(task="paper_writing")
        yielded = False
        for chunk in client.generate_streamed(prompt, system_prompt=full_sys, max_tokens=1200):
            if chunk:
                yielded = True
                yield chunk
        if not yielded:
            yield "(빈 응답)"
    except Exception as e:
        yield f"(LLM 호출 실패: {e})"


def _post_turn_hooks(project: dict, user_msg: str, full_reply: str, owner_email: str = ""):
    """채팅 한 턴 완료 후 단일 코어 누적 (best-effort)."""
    try:
        from src.memory.conversation_memory import record as _cm_record
        _cm_record(user_message=user_msg, agent_response=full_reply,
                    topic=project.get("title", "")[:80],
                    context_type="ez_home_chat", quality="neutral",
                    owner_email=owner_email or "")
    except Exception:
        pass
    try:
        from src.runtime.events import append as _evt
        _evt(type="ez_home_chat_turn",
              payload={"pid": project.get("id"), "user": user_msg[:300],
                       "resp_len": len(full_reply)},
              actor=owner_email or "anon")
    except Exception:
        pass
    try:
        from src.memory.router import write as _mem_write
        _mem_write(f"[chat:{project.get('id','')}] {user_msg[:200]} || {full_reply[:400]}",
                    type="episodic", source="ez_home_chat",
                    owner_email=owner_email or None,
                    extra_meta={"project_id": project.get("id"),
                                  "project_title": project.get("title", "")[:80]})
    except Exception:
        pass
    try:
        from src.memory import change_log as _cl
        _cl.log(title=f"chat turn: {user_msg[:50]}",
                 action_type="chat",
                 description=f"pid={project.get('id')} user={user_msg[:200]}",
                 why_better="user dialogue accumulated for cross-session context",
                 impact={"project_id": project.get("id")})
    except Exception:
        pass


def _render_msg(role: str, content: str):
    """단일 메시지를 chat bubble HTML 로 렌더."""
    safe = (content or "").replace("<", "&lt;").replace(">", "&gt;")
    cls = "msg-user" if role == "user" else "msg-asst"
    st.markdown(f"<div class='{cls}'>{safe}</div>", unsafe_allow_html=True)


def _render_chat_page(pid: str):
    """단일 페이지 chat + preview — 스트리밍 + 고정높이 스크롤."""
    project = _load_or_init_project(pid, st.session_state.get("sg_initial_prompt") or "새 작업")
    owner_email = (st.session_state.get("user") or {}).get("email") or \
                   st.session_state.get("user_email", "")

    # Topbar
    cback, ctitle = st.columns([1, 7])
    with cback:
        if st.button("← 홈", key="chat_back_btn"):
            st.session_state.pop("sg_active_project", None)
            st.rerun()
    with ctitle:
        st.markdown(f"<div style='font-weight:600;font-size:1.05rem;color:#0F172A;"
                    f"padding-top:6px;'>{project.get('title','새 작업')[:80]}</div>",
                    unsafe_allow_html=True)

    st.markdown("""
    <style>
    .msg-user { background:#0F172A; color:#FFFFFF; border-radius:14px 14px 4px 14px;
                 padding:10px 14px; margin:8px 0 8px auto; max-width:85%;
                 width:fit-content; font-size:0.92rem; line-height:1.5;
                 white-space:pre-wrap; word-wrap:break-word; }
    .msg-asst { background:#F1F5F9; color:#0F172A; border-radius:14px 14px 14px 4px;
                 padding:10px 14px; margin:8px auto 8px 0; max-width:92%;
                 width:fit-content; font-size:0.92rem; line-height:1.55;
                 white-space:pre-wrap; word-wrap:break-word; }
    .preview-box { background:#FFFFFF; border:1px solid rgba(15,23,42,0.08);
                    border-radius:12px; padding:32px; min-height:600px;
                    box-shadow:0 1px 3px rgba(15,23,42,0.04); }
    .preview-box h1 { font-size:1.4rem; color:#0F172A; margin:0 0 8px 0; }
    .preview-box h2 { font-size:1.0rem; color:#0F172A; margin:18px 0 6px 0;
                       border-bottom:1px solid rgba(15,23,42,0.08); padding-bottom:4px; }
    .preview-box p  { color:#334155; font-size:0.92rem; line-height:1.7; margin:0 0 10px 0; }
    .preview-empty  { color:#94A3B8; font-size:0.9rem; text-align:center; padding-top:240px; }
    /* st.container(height=...) 내부 스크롤바 정돈 */
    [data-testid='stVerticalBlockBorderWrapper'] > div > div > [data-testid='stVerticalBlock']::-webkit-scrollbar {
        width: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    # 입력은 컨테이너 위에서 받음 (chat_input은 페이지 하단 고정)
    initial = st.session_state.pop("sg_initial_prompt", None)
    user_msg = st.chat_input("메시지를 입력하세요…", key=f"chat_input_{pid}")
    if not user_msg and initial and not project["messages"]:
        user_msg = initial
        if not project.get("title") or project["title"] == "새 작업":
            project["title"] = initial[:60]

    col_chat, col_preview = st.columns([0.46, 0.54], gap="medium")

    with col_chat:
        # 고정 높이 스크롤 박스 — 무한정 늘어나지 않음
        msgs_box = st.container(height=600, border=False)
        with msgs_box:
            # 1) 누적된 과거 메시지
            for m in project.get("messages", []):
                _render_msg(m.get("role", "assistant"), m.get("content", ""))

            # 2) 새 사용자 입력 처리 (같은 run 안에서 스트리밍)
            if user_msg:
                if not project.get("title") or project["title"] == "새 작업":
                    project["title"] = user_msg[:60]
                project["messages"].append({"role": "user", "content": user_msg,
                                              "ts": datetime.now().isoformat()})
                _render_msg("user", user_msg)

                if _is_autopilot_trigger(user_msg):
                    reply = ("알겠습니다. 지금까지 합의된 PICO·데이터·통계 조건으로 "
                              "파이프라인을 시작합니다. 진행 상황을 이 채팅과 우측 프리뷰로 알려드릴게요.\n\n"
                              "(현 단계: 실제 파이프라인 hookup은 다음 작업)")
                    _render_msg("assistant", reply)
                else:
                    # 스트리밍 — placeholder를 토큰 단위로 갱신
                    placeholder = st.empty()
                    full = ""
                    for chunk in _stream_reply(project, user_msg):
                        full += chunk
                        safe = full.replace("<", "&lt;").replace(">", "&gt;")
                        placeholder.markdown(
                            f"<div class='msg-asst'>{safe}▌</div>",
                            unsafe_allow_html=True)
                    # 커서 제거 + 최종
                    safe = full.replace("<", "&lt;").replace(">", "&gt;")
                    placeholder.markdown(
                        f"<div class='msg-asst'>{safe}</div>",
                        unsafe_allow_html=True)
                    reply = full

                project["messages"].append({"role": "assistant", "content": reply,
                                              "ts": datetime.now().isoformat()})
                _save_project(project)
                _post_turn_hooks(project, user_msg, reply, owner_email)

    with col_preview:
        sections = project.get("sections") or {}
        if not sections:
            st.markdown(
                "<div class='preview-box'><div class='preview-empty'>"
                "📄 논문 초안이 생성되면 이곳에 실시간으로 표시됩니다.<br>"
                "<span style='font-size:0.82rem;'>(대화로 주제·데이터·통계가 합의되고 "
                "'알아서 해'라고 말씀하시면 자동 작성이 시작됩니다)</span></div></div>",
                unsafe_allow_html=True)
        else:
            html_parts = [f"<div class='preview-box'><h1>{project.get('title','')[:80]}</h1>"]
            for key in ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]:
                if key in sections and sections[key]:
                    body = str(sections[key]).replace("<", "&lt;").replace(">", "&gt;")
                    body_html = "".join(f"<p>{para}</p>" for para in body.split("\n\n") if para.strip())
                    html_parts.append(f"<h2>{key.capitalize()}</h2>{body_html}")
            html_parts.append("</div>")
            st.markdown("".join(html_parts), unsafe_allow_html=True)


def render() -> None:
    """홈 렌더링 — `app/streamlit_app.py`에서 호출.

    Single-page architecture: 활성 프로젝트 있으면 workspace 양식 인라인 렌더,
    없으면 hero+chat 입력 양식.
    """
    inject_sapphire_glass()
    try:
        from app.sapphire_actions import render_open_action_if_any, render_fab
        render_open_action_if_any()
    except Exception:
        render_fab = None
    _, _, projects = _sidebar()

    # 상태 기반 분기 — 활성 프로젝트가 있으면 chat+preview 단일 페이지 양식
    active = st.session_state.get("sg_active_project")
    if active and active != "new":
        _render_chat_page(active)
        return

    # 페이지별 UX CSS — Chat-first 양식 (Lovable/ChatGPT 양식)
    st.markdown("""
    <style>
    /* Hero — clean tool-like, not marketing */
    .ez-hero { text-align:center; margin: 14vh 0 28px 0; }
    .ez-hero h1 { font-size:1.9rem; font-weight:600; color:#0F172A; letter-spacing:-0.02em;
                   margin:0 0 8px 0; }
    .ez-hero p  { color:#64748B; font-size:0.95rem; margin:0; }
    /* Chat box — input + paperclip + arrow in one frame */
    .ez-chat-wrap { max-width: 720px; margin: 0 auto; position: relative; }
    .ez-chat-wrap .stTextArea textarea {
        min-height: 56px !important;
        max-height: 280px !important;
        padding: 16px 92px 16px 20px !important;
        font-size: 0.98rem !important;
        background: #FFFFFF !important;
        border: 1px solid rgba(15,23,42,0.10) !important;
        border-radius: 18px !important;
        box-shadow: 0 1px 3px rgba(15,23,42,0.04), 0 8px 24px rgba(15,23,42,0.06) !important;
        line-height: 1.5 !important;
        resize: none !important;
    }
    .ez-chat-wrap .stTextArea textarea:focus {
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.10), 0 8px 24px rgba(15,23,42,0.06) !important;
    }
    /* 파일 첨부 widget — 작은 라벨 + 박스 inline 양식 */
    .ez-attach { max-width:720px; margin:8px auto 0; display:flex; align-items:center;
                  gap:8px; color:#64748B; font-size:0.82rem; }
    .ez-attach .stFileUploader { flex: 1; }
    .ez-attach [data-testid='stFileUploader'] section {
        min-height: 40px !important;
        padding: 6px 12px !important;
        border-radius: 10px !important;
        border: 1px dashed rgba(15,23,42,0.12) !important;
        background: rgba(255,255,255,0.5) !important;
    }
    /* Send 버튼 — 박스 안 우측 floating */
    .ez-send-overlay { position: relative; max-width: 720px; margin: -56px auto 0; }
    .ez-send-overlay .stButton { position: absolute; right: 10px; top: -52px; width: 80px; }
    .ez-send-overlay .stButton button {
        height: 36px !important; min-height: 36px !important;
        border-radius: 12px !important; padding: 0 14px !important;
        background: #0F172A !important; color: #FFFFFF !important;
        border: none !important; font-weight: 600 !important;
    }
    .ez-send-overlay .stButton button:disabled { background: #CBD5E1 !important; color: #94A3B8 !important; }
    /* Example chips */
    .ez-suggest-row { max-width:720px; margin: 18px auto 0; display:flex; flex-wrap:wrap;
                       gap:8px; justify-content:center; }
    .ez-suggest-row .stButton button {
        background: rgba(15,23,42,0.04) !important;
        border: 1px solid rgba(15,23,42,0.08) !important;
        border-radius: 999px !important;
        padding: 6px 14px !important;
        min-height: 30px !important;
        color: #475569 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
        text-align: center !important;
        box-shadow: none !important;
    }
    .ez-suggest-row .stButton button:hover {
        background: rgba(15,23,42,0.08) !important; color: #0F172A !important;
    }
    /* Recent projects section */
    .ez-recent-h { max-width:1080px; margin: 56px auto 8px; font-size:0.78rem;
                    color:#94A3B8; text-transform:uppercase; letter-spacing:0.06em; }
    </style>
    """, unsafe_allow_html=True)

    # Hero — short tool-like
    st.markdown(
        "<div class='ez-hero'>"
        "<h1>의학 연구를 채팅으로</h1>"
        "<p>주제만 적어주세요. 데이터·통계·구조는 대화로 같이 정해갑니다.</p>"
        "</div>", unsafe_allow_html=True)

    # Example chip이 클릭되면 입력에 채움 (다음 입력에 prepend)
    chip_text = st.session_state.pop("_ez_chip_clicked", None)

    # 첨부 widget — chat input 위에 작게
    st.markdown("<div style='max-width:720px;margin:0 auto 12px;'>", unsafe_allow_html=True)
    uploaded = st.file_uploader(
        "📎 기존 논문/데이터 첨부 (선택)",
        type=["pdf","docx","txt","png","jpg","jpeg","sav","csv","xlsx","json"],
        accept_multiple_files=True, key="sg_home_files",
        label_visibility="collapsed")
    st.markdown("</div>", unsafe_allow_html=True)

    # ★ st.chat_input — Enter로 즉시 제출 (ChatGPT/Lovable 양식)
    prompt = st.chat_input(
        "무엇을 연구하고 싶으세요?",
        key="sg_home_chat_input",
    )
    if chip_text and not prompt:
        prompt = chip_text
    send = bool(prompt)

    # Example chips — 입력이 비어있으면 항상 표시 (projects 있어도 OK)
    if not prompt:
        st.markdown("<div class='ez-suggest-row'>", unsafe_allow_html=True)
        EX_CHIPS = [
            "SGLT2 억제제의 한국 심부전 환자 신기능 보존 효과 RWE",
            "GLP-1 RA 비급여 처방 후 갑상선 미세변화 시그널",
            "코로나 락다운 전후 청소년 ADHD 진단·처방 추세",
            "한국 청소년 우울증과 카페인 음료 노출의 자연실험",
        ]
        cols = st.columns(len(EX_CHIPS))
        for i, ex in enumerate(EX_CHIPS):
            with cols[i]:
                if st.button(ex[:40] + ("…" if len(ex) > 40 else ""),
                              key=f"sg_ex_{i}", help=ex):
                    st.session_state["_ez_chip_clicked"] = ex
                    st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if send and (prompt or uploaded):
        if uploaded:
            _enqueue_uploaded_files(uploaded, prompt_hint=prompt or "")
        if prompt:
            # ★ Single-page architecture (사용자 요구 2026-06-05):
            # switch_page X. 같은 ez_home 페이지 안에서 상태로 chat+preview split 전환.
            import uuid as _uuid
            pid = f"chat_{_uuid.uuid4().hex[:10]}"
            st.session_state["sg_active_project"] = pid
            st.session_state["sg_initial_prompt"] = prompt
            st.rerun()
        else:
            st.rerun()

    # 최근 프로젝트 — 명확한 헤더 + 카드
    if projects:
        st.markdown("<div class='ez-recent-h'>RECENT</div>", unsafe_allow_html=True)
        project_grid(projects[:6])
    # Templates 탭 제거. 아래 templates 코드는 dead — 절대 호출 안 됨.
    if False:
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
