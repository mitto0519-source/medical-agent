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


# ★ F5 로그인 풀림 사고 fix (2026-06-16): ez_home은 Streamlit 멀티페이지로 직접 URL 접근 가능
# → streamlit_app.py의 _login_gate를 안 거치고 user 없이 로드됨.
# 여기서 query_params 기반 자동 로그인 + session_state 복원을 직접 수행.
def _ensure_logged_in() -> bool:
    """session_state에 user 없으면 URL ?email=&auto=1로 자동 로그인 시도.
    실패 시 streamlit_app.py 본 페이지로 redirect.
    """
    if "user" in st.session_state:
        return True
    qp = st.query_params
    try:
        saved_email = qp.get("email", "") if hasattr(qp, "get") else ""
        auto_login = (qp.get("auto", "") == "1") if hasattr(qp, "get") else False
    except Exception:
        saved_email, auto_login = "", False
    if saved_email and auto_login:
        try:
            from src.auth.users import get_user_by_email
            user = get_user_by_email(saved_email.strip().lower())
            if user:
                st.session_state["user"] = user
                st.session_state["user_email"] = user.get("email", saved_email)
                return True
        except Exception:
            pass
    # 자동 로그인 실패 → streamlit_app.py로 redirect (게이트 page)
    try:
        st.switch_page("streamlit_app.py")
    except Exception:
        st.error("로그인이 필요합니다. 메인 페이지로 돌아가 다시 접속해주세요.")
        st.stop()
    return False


if not _ensure_logged_in():
    st.stop()


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
                        "SELECT id, title, updated_at, data_json FROM ma_working_papers "
                        "WHERE owner_email=:oe ORDER BY updated_at DESC LIMIT 50"),
                        {"oe": owner}).mappings().all()
                else:
                    rows = conn.execute(_sql(
                        "SELECT id, title, updated_at, data_json FROM ma_working_papers "
                        "ORDER BY updated_at DESC LIMIT 20")).mappings().all()
            for r in rows:
                pid = r["id"]
                if pid in seen_ids:
                    continue
                raw_title = (r["title"] or "").strip()
                ts = r["updated_at"] or 0
                # ★ Supabase title 정정 (2026-06-16): title이 pid 그대로 또는 chat_로 시작
                # 또는 '새 작업/대화/Untitled' 같은 stale placeholder면 첫 user msg로 대체
                meaningful_title = (raw_title and raw_title != pid and
                                       not raw_title.startswith("chat_") and
                                       raw_title not in ("새 작업","새 대화","제목 없음","Untitled"))
                fallback_used = False
                if not meaningful_title:
                    # data_json에서 첫 user msg 추출
                    try:
                        dj = r.get("data_json") or {}
                        if isinstance(dj, str):
                            dj = json.loads(dj)
                        msgs = (dj or {}).get("messages") or []
                        for m in msgs:
                            if m.get("role") == "user" and m.get("content"):
                                raw_title = m["content"][:60].strip()
                                fallback_used = True
                                break
                        # 그래도 없으면 sections 첫 본문
                        if not fallback_used:
                            secs = (dj or {}).get("sections") or {}
                            for k in ("Abstract", "abstract", "Introduction", "introduction", "full"):
                                v = secs.get(k)
                                if isinstance(v, str) and v.strip():
                                    raw_title = v.strip()[:60]
                                    fallback_used = True
                                    break
                    except Exception:
                        pass
                # 모든 fallback 실패 + 의미없는 placeholder면 skip (RECENT에 노이즈 안 박음)
                if not raw_title or raw_title == pid or raw_title.startswith("chat_"):
                    continue
                seen_ids.add(pid)
                title = raw_title[:60]
                edited = datetime.fromtimestamp(ts).strftime("Edited %Y-%m-%d") if ts else "Edited (cloud)"
                out.append({"title": title, "edited": edited,
                             "status": "☁ Cloud",
                             "gradient": grads[len(out) % len(grads)],
                             "id": pid, "mtime": float(ts) if ts else 0.0})
    except Exception:
        pass

    # 2) 로컬 working_papers/*.json (보조 — 동일 id 중복 제거)
    if _PROJECTS_DIR.exists():
        all_jsons = list(_PROJECTS_DIR.glob("*.json")) + list(_PROJECTS_DIR.glob("*/*.json"))
        for jp in sorted(all_jsons, key=lambda p: p.stat().st_mtime, reverse=True):
            pid = jp.stem
            if pid in seen_ids:
                continue
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
                # ★ 빈 채팅 필터
                raw_title = (data.get("title") or
                             (data.get("topic") or {}).get("title") or "").strip()
                n_msgs = len(data.get("messages") or [])
                has_sections = bool(data.get("sections"))
                meaningful = (n_msgs > 0 or has_sections or
                               (raw_title and raw_title not in ("새 작업", "새 대화", "제목 없음", "Untitled")))
                if not meaningful:
                    continue
                # ★ title이 pid와 같으면(=옛 데이터, 제목 업데이트 누락) 첫 user message로 대체
                if not raw_title or raw_title == pid or raw_title.startswith("chat_"):
                    for m in (data.get("messages") or []):
                        if m.get("role") == "user" and m.get("content"):
                            raw_title = m["content"][:60].strip()
                            break
                title = (raw_title or "(제목 없음)")[:60]
                mtime = jp.stat().st_mtime
                edited = datetime.fromtimestamp(mtime).strftime("Edited %Y-%m-%d")
                status = "Published" if data.get("status") == "published" else ""
                seen_ids.add(pid)
                out.append({"title": title, "edited": edited, "status": status,
                             "gradient": grads[len(out) % len(grads)], "id": pid,
                             "n_msgs": n_msgs, "mtime": mtime})
            except Exception:
                continue

    # ★ Supabase + 로컬 통합 후 mtime/updated_at으로 정확히 재정렬 (사용자 사고: '최신 반영 안 됨')
    def _sort_key(p):
        return p.get("mtime") or 0
    out.sort(key=_sort_key, reverse=True)
    # 빈 title 사후 필터
    out = [p for p in out
            if p.get("title") and p["title"].strip() not in
            ("새 작업", "새 대화", "제목 없음", "Untitled", "(제목 없음)")]
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

    # ★ 내 논문 업로드 (StyleProfiler) — "AI같지 않게" 핵심 엔진
    _owner = (st.session_state.get("user") or {}).get("email") or \
              st.session_state.get("user_email", "") or ""
    if _owner:
        _render_my_papers_uploader(_owner)

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

    # ★ LOOP_ENGINEERING_SPEC §2.3·§2.4 — Triage Inbox + Today View
    try:
        from src.loops.triage import inbox as _inbox
        from src.loops.state_view import today_view as _tv
        ib = _inbox(owner_email=_owner or None)
        tv = _tv(owner_email=_owner or None)
        totals = ib.get("totals", {})
        with st.sidebar.expander(
                f"📥 Triage ({totals.get('urgent',0)}🔴 "
                f"{totals.get('today',0)}🟠 {totals.get('background',0)}⚙)",
                expanded=False):
            if ib.get("urgent"):
                st.markdown("**🔴 긴급**")
                for i in ib["urgent"][:3]:
                    st.caption(f"• {i.get('kind','?')}: {str(i.get('reason') or i.get('title') or '')[:60]}")
            if ib.get("today"):
                st.markdown("**🟠 오늘 봐야**")
                for i in ib["today"][:3]:
                    st.caption(f"• {i.get('kind','?')}: {str(i.get('claim') or i.get('candidate_event_id') or '')[:60]}")
            if ib.get("background"):
                st.caption(f"⚙ 백그라운드: {len(ib['background'])} 작업 진행 중")
        # ★ LOOP_ENGINEERING_SPEC §3 — 인지적 항복 방지 알림
        try:
            _alerts: list[str] = []
            # 1) 5턴 연속 자동 turn 후 사용자 검토 없음
            _msgs = project.get("messages", []) if 'project' in dir() else []
            asst_streak = 0
            for m in reversed(_msgs[-12:]):
                if m.get("role") == "assistant":
                    asst_streak += 1
                else:
                    break
            if asst_streak >= 5:
                _alerts.append(f"🟡 5턴+ 자동 응답 — 한 번 직접 본문 점검 권장")
            # 2) 골드셋 0건 + 10턴 경과
            gs = tv.get("gold_set") or {}
            if gs.get("labelled", 0) == 0 and len(_msgs) >= 10:
                _alerts.append("📝 골드셋 라벨 0 — 자가발전 기준점 0 (SELF_EVOLUTION §2)")
            # 3) self-bias warning 최근
            try:
                from src.runtime import events as _e
                bias_events = _e.find(type="self_bias_warning", limit=3) or []
                if bias_events:
                    _alerts.append(f"⚠ self-bias 감지 {len(bias_events)}건 — critic 모델 교체 권장")
            except Exception:
                pass
            # 4) confidence < 0.6 최근
            try:
                from src.runtime import events as _e
                conf_evts = _e.find(type="confidence_calibration", limit=5) or []
                low = [e for e in conf_evts
                        if (e.get("payload") or {}).get("predicted", 1.0) < 0.6]
                if low:
                    _alerts.append(f"🔴 confidence < 0.6 ({len(low)}건) — 사용자 검토 필수")
            except Exception:
                pass
            if _alerts:
                st.sidebar.markdown(
                    "<div style='margin:8px 0;padding:8px 10px;"
                    "background:#FEF3C7;border-left:3px solid #F59E0B;"
                    "border-radius:6px;font-size:0.78rem;color:#92400E;'>"
                    "<b>👤 사용자 검토 필요</b><br>" +
                    "<br>".join(_alerts[:4]) + "</div>",
                    unsafe_allow_html=True)
        except Exception as _e:
            pass

        with st.sidebar.expander("🗂 오늘 상태", expanded=False):
            ing = tv.get("ingest") or {}
            if ing.get("running"):
                st.caption(f"🔄 RAG 인제스트: ok={ing.get('last_ok','?')}")
            elif ing.get("last_ok"):
                st.caption(f"✓ 인제스트 완료: {ing.get('last_ok')}편")
            gs = tv.get("gold_set") or {}
            if gs.get("total"):
                st.caption(f"📝 골드셋 라벨: {gs['labelled']}/{gs['total']} ({gs.get('pct',0):.0f}%)")
            na = tv.get("next_action")
            if na:
                st.caption(f"➡ 다음: {str(na)[:80]}")
    except Exception as _e:
        st.sidebar.caption(f"triage unavailable: {str(_e)[:80]}")

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


def _is_go_wide_trigger(text: str) -> bool:
    """Delegate → src.service.paper.is_go_wide_trigger (Phase1 extraction)."""
    from src.service.paper import is_go_wide_trigger
    return is_go_wide_trigger(text)


def _detect_figure_request(text: str) -> str | None:
    """figurelabs 양식 — 자연어에서 figure 종류 감지.

    반환: forest / subgroup / coef / roc / prev / table1 / table2 / None
    """
    if not text:
        return None
    t = text.strip().lower()
    if any(k in t for k in ["forest plot", "forest 그", "forest plot 만"]):
        if "subgroup" in t or "하위군" in t:
            return "subgroup"
        return "forest"
    if "subgroup" in t and ("plot" in t or "그림" in t or "그려" in t):
        return "subgroup"
    if any(k in t for k in ["coefficient plot", "coef plot", "회귀 계수"]):
        return "coef"
    if any(k in t for k in ["roc curve", "auc", "roc 그", "roc plot"]):
        return "roc"
    if any(k in t for k in ["prevalence", "유병률", "prevalence bar"]):
        return "prev"
    if "table 1" in t or "표 1" in t or "table1" in t:
        return "table1"
    if "table 2" in t or "표 2" in t or "table2" in t:
        return "table2"
    return None


def _generate_figure(project: dict, figure_type: str) -> tuple[bytes, str] | None:
    """Delegate → src.service.figures.generate_figure (FRONTEND_MIGRATION_SPEC Phase 1)."""
    from src.service.figures import generate_figure
    return generate_figure(project, figure_type)


def _strip_korean_prelude(text: str) -> str:
    """Delegate → src.service.paper.strip_korean_prelude."""
    from src.service.paper import strip_korean_prelude
    return strip_korean_prelude(text)


def _hits_to_references(rag_context: str) -> list:
    """Delegate → src.service.paper.hits_to_references."""
    from src.service.paper import hits_to_references
    return hits_to_references(rag_context)


def _post_process_imrad(draft: str, rag_context: str) -> tuple[str, dict]:
    """Delegate → src.service.paper.post_process_imrad."""
    from src.service.paper import post_process_imrad
    return post_process_imrad(draft, rag_context)


def _enrich_imrad(draft: str, project: dict, user_msg: str) -> tuple[str, dict]:
    """Delegate → src.service.paper.enrich_imrad."""
    from src.service.paper import enrich_imrad
    return enrich_imrad(draft, project, user_msg)


def _is_full_paper_trigger(text: str) -> bool:
    """Delegate → src.service.paper.is_full_paper_trigger."""
    from src.service.paper import is_full_paper_trigger
    return is_full_paper_trigger(text)


def _full_paper_prompt(project: dict) -> str:
    """Delegate → src.service.paper.full_paper_prompt."""
    from src.service.paper import full_paper_prompt
    return full_paper_prompt(project)


def _is_go_deep_trigger(text: str) -> bool:
    """Delegate → src.service.paper.is_go_deep_trigger."""
    from src.service.paper import is_go_deep_trigger
    return is_go_deep_trigger(text)


def _go_wide_prompt(user_msg: str) -> str:
    """Delegate → src.service.paper.go_wide_prompt."""
    from src.service.paper import go_wide_prompt
    return go_wide_prompt(user_msg)


def _go_deep_prompt(user_msg: str, project: dict) -> str:
    """Delegate → src.service.paper.go_deep_prompt."""
    from src.service.paper import go_deep_prompt
    return go_deep_prompt(user_msg, project)


def _is_autopilot_trigger(text: str) -> bool:
    """Delegate → src.service.paper.is_autopilot_trigger."""
    from src.service.paper import is_autopilot_trigger
    return is_autopilot_trigger(text)


def _rag_retrieve(query: str, top_k: int = 5) -> str:
    """Delegate to src.service.rag — single-source pure logic for future FastAPI reuse."""
    try:
        from src.service.rag import retrieve_as_text_block
        return retrieve_as_text_block(query, top_k=top_k, max_text_per_hit=600)
    except Exception:
        return ""


def _owner_email() -> str:
    """Streamlit session_state에서 owner_email 추출 — Phase 1 추출 후 service에 인자 전달용."""
    import streamlit as _st
    return ((_st.session_state.get("user") or {}).get("email")
            or _st.session_state.get("user_email", "") or "")


def _build_full_system(project: dict, user_msg: str) -> str:
    """Delegate → src.service.chat.build_full_system. st.session_state는 caller가 분리.

    Phase 1 ★: pure logic은 service. ez_home은 owner_email 추출만 담당.
    """
    from src.service.chat import build_full_system
    return build_full_system(project, user_msg, owner_email=_owner_email())


def _stream_reply(project: dict, user_msg: str, extra_system: str = "", max_tokens: int = 1200):
    """Delegate → src.service.chat.stream_reply."""
    from src.service.chat import stream_reply
    yield from stream_reply(project, user_msg, extra_system=extra_system,
                              max_tokens=max_tokens, owner_email=_owner_email())


def _post_turn_hooks(project: dict, user_msg: str, full_reply: str, owner_email: str = ""):
    """Delegate → src.service.chat.post_turn_hooks."""
    from src.service.chat import post_turn_hooks
    post_turn_hooks(project, user_msg, full_reply, owner_email=owner_email)


_PIN_SECTIONS = ("Abstract", "Introduction", "Methods", "Results",
                  "Discussion", "Conclusion", "Tables", "Figures", "References")


# ★ UX-1: 빈 채팅 환영 화면 — 사용자가 "연구 아이디어 한 줄" 입력으로 시작하게
_EXAMPLE_TOPICS = [
    "청소년 제로음료와 우울",
    "KNHANES UPF × MASLD (2023 신정의)",
    "수면 시간과 자살 생각 KYRBS 분석",
    "카페인 섭취와 대사증후군",
    "신체활동 빈도와 우울감 코호트",
]


def _render_welcome_chat(project: dict, owner_email: str = "") -> None:
    """빈 채팅 환영 카드. 5개 예시 chip + 알아서 해 버튼 + 최근 3개 프로젝트.

    여기 채팅 메시지가 한 건이라도 있으면 표시 안 됨.
    """
    st.markdown(
        "<div class='msg-asst' style='background:#F8FAFC;border:none;'>"
        "<div style='font-size:1.0rem;font-weight:600;color:#0F172A;margin-bottom:6px;'>"
        "👋 무엇을 연구하시겠어요?</div>"
        "<div style='font-size:0.86rem;color:#475569;margin-bottom:14px;'>"
        "연구 아이디어 한 줄만 입력하면 PICO·변수·통계·신규성·저널까지 자동으로 정리합니다. "
        "막막하면 아래 예시를 누르세요.</div>"
        "</div>", unsafe_allow_html=True)

    # 예시 chip 5개
    cols = st.columns(min(3, len(_EXAMPLE_TOPICS[:3])))
    for i, topic in enumerate(_EXAMPLE_TOPICS[:3]):
        with cols[i]:
            if st.button(f"💡 {topic}", key=f"sg_ex_{i}",
                          use_container_width=True):
                st.session_state["sg_initial_prompt"] = topic
                st.session_state["sg_active_project"] = "new"
                st.rerun()
    cols2 = st.columns(min(2, len(_EXAMPLE_TOPICS[3:])))
    for i, topic in enumerate(_EXAMPLE_TOPICS[3:]):
        with cols2[i]:
            if st.button(f"💡 {topic}", key=f"sg_ex2_{i}",
                          use_container_width=True):
                st.session_state["sg_initial_prompt"] = topic
                st.session_state["sg_active_project"] = "new"
                st.rerun()

    # 알아서 해 버튼 (옵션 — 주제 입력 후 자동 트리거 안내)
    st.markdown(
        "<div style='margin-top:14px;padding:10px 14px;background:#EFF6FF;"
        "border-left:3px solid #3B82F6;border-radius:6px;font-size:0.82rem;"
        "color:#1E40AF;'>"
        "🚀 주제 입력 후 <b>'알아서 해'</b>라고 말씀하시면 PICO·통계·초안까지 한 번에 진행합니다."
        "</div>", unsafe_allow_html=True)
    # 최근 프로젝트는 사이드바 RECENT에 이미 있음 — 중앙 중복 제거 (사용자 사고 2026-06-16)


def _friendly_error(kind: str, raw_msg: str,
                       alternatives: list = None) -> str:
    """★ UX-5: 에러 메시지 친절화 — 원인 + 대안.

    kind: stat / data / llm / network / file
    """
    titles = {
        "stat": "📊 통계 분석 실패",
        "data": "💾 데이터 로드 실패",
        "llm":  "🤖 AI 호출 실패",
        "network": "🌐 외부 연결 실패",
        "file": "📁 파일 처리 실패",
    }
    title = titles.get(kind, "⚠ 작업 실패")
    msg = f"<b>{title}</b><br>"
    msg += f"<span style='color:#475569;font-size:0.84rem;'>원인: {raw_msg[:200]}</span>"
    if alternatives:
        msg += "<br><b style='font-size:0.84rem;'>해결책:</b><ul style='margin:4px 0 0 20px;font-size:0.84rem;'>"
        for alt in alternatives[:4]:
            msg += f"<li>{alt}</li>"
        msg += "</ul>"
    return msg


def _pin_to_section(project: dict, content: str, section: str,
                       *, mode: str = "append") -> None:
    """assistant 응답(또는 선택 블록)을 sections에 박는 핵심 액션.

    mode='append': 기존 내용 뒤에 \\n\\n+content
    mode='overwrite': 통째로 교체
    저장 후 _save_project → 우측 프리뷰 즉시 반영 + 다음 turn에 build_system_with_preview가
    sections snapshot으로 LLM 컨텍스트에 자동 주입(=양방향 binding).
    """
    if not content or not section:
        return
    secs = project.setdefault("sections", {})
    cur = secs.get(section) or ""
    if isinstance(cur, dict):
        # 기존 구조가 dict (Abstract.Background 등) — _appended 슬롯에 추가
        cur_text = str(cur.get("_appended", "") or "")
        new = (cur_text + "\n\n" + content).strip() if (mode == "append" and cur_text) else content
        cur["_appended"] = new
        secs[section] = cur
    else:
        cur_text = str(cur or "")
        new = (cur_text + "\n\n" + content).strip() if (mode == "append" and cur_text) else content
        secs[section] = new
    # research_state.manuscript_text도 동시 갱신 (autopilot이 쓰는 키)
    # ★ RESEARCH_STATE_SPEC §1: manuscript_text 이중쓰기 제거.
    # sections가 유일 정본 — manuscript_text는 더 이상 저장하지 않음 (파생 getter 사용).
    # legacy 키는 None으로 명시(이전 저장본 호환), 새로 저장하지 않음.
    project.setdefault("research_state", {})["manuscript_text"] = None
    _save_project(project)


def _render_msg(role: str, content: str, *, msg_idx: int = -1,
                  project: dict = None, allow_pin: bool = True) -> None:
    """단일 메시지를 chat bubble HTML 로 렌더 + assistant 메시지엔 📌 핀 row 추가.

    msg_idx: messages 리스트 인덱스 — Streamlit button key 고유성 보장용
    project: 핀 적용 대상 project dict
    allow_pin: False면 핀 row 생략 (스트리밍 중간 표시 등 일회성 렌더)
    """
    safe = (content or "").replace("<", "&lt;").replace(">", "&gt;")
    cls = "msg-user" if role == "user" else "msg-asst"
    st.markdown(f"<div class='{cls}'>{safe}</div>", unsafe_allow_html=True)

    # 핀 row — assistant 메시지에만, project 제공된 경우만
    if role != "assistant" or not allow_pin or project is None or not content:
        return
    if msg_idx < 0:
        msg_idx = abs(hash(content)) % 100000
    key_prefix = f"pin_{project.get('id','x')}_{msg_idx}"

    with st.container():
        st.markdown(
            "<div style='font-size:0.74rem;color:#64748B;margin:2px 0 4px 0;"
            "padding-left:4px;'>📌 프리뷰에 박기:</div>",
            unsafe_allow_html=True)
        # 9 sections in 3 rows of 3
        cols_r1 = st.columns(3)
        cols_r2 = st.columns(3)
        cols_r3 = st.columns(3)
        rows = [cols_r1, cols_r2, cols_r3]
        for i, sec in enumerate(_PIN_SECTIONS):
            row, col = divmod(i, 3)
            with rows[row][col]:
                if st.button(sec, key=f"{key_prefix}_{sec}",
                              use_container_width=True,
                              help=f"이 응답을 {sec} 섹션에 추가"):
                    _pin_to_section(project, content, sec, mode="append")
                    st.toast(f"📌 {sec}에 박았습니다 ({len(content):,}자)",
                              icon="✅")
                    st.rerun()


def _render_my_papers_uploader(owner_email: str) -> None:
    """사이드바: 사용자 본인 논문 업로드 → StyleProfiler 자동 실행."""
    import streamlit as _st
    from pathlib import Path
    if not owner_email:
        return
    with _st.sidebar.expander("📚 내 논문 업로드 (문체 그라운딩)", expanded=False):
        try:
            from src.ingestion.style_profiler import StyleProfiler, extract_and_save_for_user
            existing = StyleProfiler.load(owner_email)
            if existing and existing.sample_size_sentences > 0:
                _st.caption(
                    f"✅ 프로파일 활성 — {existing.sample_size_papers}편 / "
                    f"avg sent {existing.avg_sent_len}w, hedge {existing.hedge_ratio*100:.1f}%")
                if _st.button("프로파일 재추출", key="restyle_reextract"):
                    _st.session_state["_style_force_reextract"] = True
            else:
                _st.caption("아직 업로드된 논문이 없습니다. .docx/.pdf/.txt 1편 이상 올리면 본인 문체로 글이 나옵니다.")

            files = _st.file_uploader(
                "본인 논문 업로드",
                type=["docx", "pdf", "txt"],
                accept_multiple_files=True,
                key="my_paper_upload",
                label_visibility="collapsed",
            )
            if files:
                upload_dir = Path("data/uploads/style_corpus") / owner_email.replace("@", "_at_")
                upload_dir.mkdir(parents=True, exist_ok=True)
                saved_paths = []
                for f in files:
                    target = upload_dir / f.name
                    target.write_bytes(f.getbuffer())
                    saved_paths.append(str(target))
                with _st.spinner("문체 추출 중…"):
                    profile = extract_and_save_for_user(saved_paths, owner_email=owner_email)
                _st.success(
                    f"✅ 추출 완료 — {profile.sample_size_papers}편 / {profile.sample_size_sentences} 문장 / "
                    f"avg sent {profile.avg_sent_len}w / hedge {profile.hedge_ratio*100:.1f}% / "
                    f"top vocab: {', '.join(profile.vocab_top10[:5]) or '(generic)'}")
        except Exception as _e:
            _st.caption(f"style_profiler unavailable: {_e}")


def _render_chat_page(pid: str):
    """단일 페이지 chat + preview — 스트리밍 + 고정높이 스크롤."""
    project = _load_or_init_project(pid, st.session_state.get("sg_initial_prompt") or "새 작업")
    owner_email = (st.session_state.get("user") or {}).get("email") or \
                   st.session_state.get("user_email", "")

    # Topbar — title only (사이드바에 새 채팅 버튼 있음)
    title_text = project.get("title", "새 작업") or "새 작업"
    if title_text == "새 작업" and not project.get("messages"):
        title_text = "새 대화"
    st.markdown(f"<div style='font-weight:600;font-size:1.0rem;color:#0F172A;"
                f"padding:4px 0 12px 0;'>{title_text[:80]}</div>",
                unsafe_allow_html=True)

    st.markdown("""
    <style>
    .msg-user { background:#0F172A; color:#FFFFFF; border-radius:14px 14px 4px 14px;
                 padding:10px 14px; margin:8px 0 8px auto; max-width:74ch;
                 width:fit-content; font-size:15px; line-height:1.55;
                 white-space:pre-wrap; word-wrap:break-word; }
    .msg-asst { background:#F1F5F9; color:#0F172A; border-radius:14px 14px 14px 4px;
                 padding:13px 16px; margin:8px auto 8px 0; max-width:74ch;
                 width:fit-content; font-size:15px; line-height:1.65;
                 white-space:pre-wrap; word-wrap:break-word; }
    /* UX_CHAT_DESIGN_SPEC §6.1 — 채팅 말풍선 헤더/타이포 규율 (문서급 거대 헤더 차단) */
    .msg-asst h1, .msg-asst h2 { font-size:1.05rem; font-weight:700;
                                  margin:14px 0 6px; line-height:1.3;
                                  color:#0F172A; border:none; padding:0; }
    .msg-asst h3 { font-size:0.95rem; font-weight:600; margin:12px 0 4px;
                    color:#0F172A; }
    .msg-asst p  { margin:0 0 10px; line-height:1.65; text-indent:0;
                    text-align:left; }
    .msg-asst ul, .msg-asst ol { margin:6px 0 10px; padding-left:22px; }
    .msg-asst li { margin:2px 0; line-height:1.6; }
    .msg-asst table { font-size:0.88rem; border-collapse:collapse; margin:8px 0; }
    .msg-asst th, .msg-asst td { padding:4px 8px;
                                  border:1px solid rgba(15,23,42,0.12); }
    .msg-asst code { font-size:0.86em;
                      font-family:ui-monospace,"SF Mono",Consolas,monospace;
                      background:rgba(15,23,42,0.05); padding:1px 5px;
                      border-radius:4px; }
    .msg-asst pre { background:rgba(15,23,42,0.05); padding:10px 12px;
                     border-radius:8px; overflow-x:auto; margin:8px 0; }
    .msg-asst strong, .msg-asst b { font-weight:700; }
    .msg-asst blockquote { margin:8px 0; padding:6px 12px;
                            border-left:3px solid rgba(15,23,42,0.18);
                            background:rgba(15,23,42,0.03); }
    .preview-box { background:#FFFFFF; border:1px solid rgba(15,23,42,0.08);
                    border-radius:12px; padding:32px; min-height:600px;
                    box-shadow:0 1px 3px rgba(15,23,42,0.04); }
    .preview-box h1 { font-size:1.4rem; color:#0F172A; margin:0 0 8px 0; }
    .preview-box h2 { font-size:1.0rem; color:#0F172A; margin:18px 0 6px 0;
                       border-bottom:1px solid rgba(15,23,42,0.08); padding-bottom:4px; }
    .preview-box p  { color:#334155; font-size:0.92rem; line-height:1.7; margin:0 0 10px 0; }
    .preview-empty  { color:#94A3B8; font-size:0.9rem; text-align:center; padding-top:140px; }
    /* st.container(height=...) 내부 스크롤바 정돈 */
    [data-testid='stVerticalBlockBorderWrapper'] > div > div > [data-testid='stVerticalBlock']::-webkit-scrollbar {
        width: 6px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ★ 컴포저 시각 통합 (2026-06-16 v2): Streamlit은 markdown div로 cols 못 감쌈.
    # 대신 chat_input 위 액션을 더 작게 + 사이 여백 0 + chat_input 자체 box-shadow로
    # 시각적으로 묶이게. popover 버튼·selectbox 높이 균일화.
    st.markdown("""
    <style>
    /* chat_input 위 마지막 row와 chat_input 사이 여백 최소화 */
    [data-testid='stChatInput'] { margin-top:-4px !important; }
    /* 컴포저 row의 popover 버튼: 작고 투명하게 */
    div[data-testid='stPopover'] button {
        padding:5px 12px !important; font-size:0.8rem !important;
        background:rgba(255,255,255,0.6) !important;
        border:1px solid rgba(15,23,42,0.10) !important;
        color:#475569 !important;
        height:36px !important;
    }
    div[data-testid='stPopover'] button:hover {
        background:rgba(255,255,255,0.95) !important; color:#0F172A !important;
    }
    /* 모델 selectbox 높이 맞춤 */
    [data-testid='stSelectbox'] > div > div { min-height:36px !important; }
    /* 첨부 칩 */
    .attached-chips { display:flex; flex-wrap:wrap; gap:6px; padding:0 4px 6px 4px; }
    .attached-chip {
        background:#EFF6FF; border:1px solid #BFDBFE; border-radius:14px;
        padding:3px 10px; font-size:0.76rem; color:#1E40AF;
        display:inline-flex; align-items:center; gap:4px;
    }
    </style>
    """, unsafe_allow_html=True)

    # ★ 채팅 컴포저 (2026-06-16): chat_input과 시각 통합. 첨부 칩 + 액션 + 모델 picker.
    # 첨부는 즉시 universal_loader.load() → project["attachments"]에 텍스트 추출본 저장 →
    # 다음 LLM turn의 system prompt에 자동 inject (양방향 binding + 영속화).
    initial = st.session_state.pop("sg_initial_prompt", None)

    attachments = project.setdefault("attachments", [])

    # 1) 첨부 칩 (chat_input 바로 위, 한 박스로 시각화)
    if attachments:
        chip_html = "<div class='attached-chips'>"
        for att in attachments[-8:]:
            kind_icon = {"image": "🖼", "office": "📄", "data": "💾",
                          "text": "📝", "notebook": "📓"}.get(att.get("kind",""), "📎")
            n_chars = len(att.get("text", "") or "")
            chip_html += (
                f"<div class='attached-chip'>"
                f"{kind_icon} <b>{att.get('name','?')[:24]}</b>"
                f"<span style='color:#64748B;font-size:0.7rem;margin-left:3px;'>"
                f"({att.get('size_kb','?')}KB · {n_chars:,}자)</span></div>"
            )
        chip_html += "</div>"
        st.markdown(chip_html, unsafe_allow_html=True)
        # 제거 row (압축)
        _rm_cols = st.columns(min(len(attachments), 8))
        for _ci, att in enumerate(attachments[-8:]):
            with _rm_cols[_ci]:
                if st.button(f"✕ {att.get('name','?')[:10]}",
                              key=f"rm_att_{pid}_{att.get('id', _ci)}",
                              use_container_width=True):
                    attachments.remove(att)
                    _save_project(project)
                    st.rerun()

    # 2) 컴포저 row — ★ 2026-06-20 v3: 모델 picker만 (첨부는 chat_input 안에 통합).
    # 사용자 정직 지적: '첨부+채팅박스 합쳐서 VS Code/Claude 양식으로'.
    # Streamlit 1.30+ chat_input(accept_file="multiple") = 한 박스 안에 📎+text+전송.
    _composer_col1, _composer_col2 = st.columns([0.7, 0.3])
    with _composer_col1:
        _model_choices = {
            "auto":    "🤖 자동 (균형)",
            "fast":    "⚡ Haiku — 빠름·간단",
            "premium": "🏆 Opus — 최고 품질·느림",
        }
        cur = st.session_state.get("sg_model_override", "auto")
        sel = st.selectbox(
            "모델",
            options=list(_model_choices.keys()),
            index=list(_model_choices.keys()).index(cur) if cur in _model_choices else 0,
            format_func=lambda k: _model_choices.get(k, k),
            key=f"composer_model_{pid}",
            label_visibility="collapsed",
        )
        if sel != st.session_state.get("sg_model_override"):
            st.session_state["sg_model_override"] = sel
            import os as _os
            if sel == "auto":
                _os.environ.pop("LLM_MODEL_OVERRIDE", None)
            else:
                _os.environ["LLM_MODEL_OVERRIDE"] = sel

    with _composer_col2:
        att_n = len(attachments)
        owner_for_uploader = (st.session_state.get("user") or {}).get("email") or \
                               st.session_state.get("user_email", "")
        suffix = f" · 📎 {att_n}" if att_n else ""
        st.caption(f"{_model_choices.get(sel,sel).split('—')[0].strip()}{suffix}")
        if owner_for_uploader and not att_n:
            st.caption("💡 chat 박스 📎로 PDF/CSV 첨부 가능")

    # ★ UX-1: 빈 채팅이면 "연구 아이디어 한 줄" 안내, 진행 중이면 일반 안내
    _placeholder = (
        "연구 아이디어 한 줄… (예: 청소년 제로음료와 우울 · /help 슬래시 명령)"
        if not project.get("messages")
        else "메시지를 입력하세요… (/help · 'Intro 써줘' · '알아서 해')"
    )
    # ★ VS Code/Claude 양식: chat_input 한 박스에 📎 첨부 + 텍스트 + 전송 통합
    chat_result = st.chat_input(
        _placeholder,
        key=f"chat_input_{pid}",
        accept_file="multiple",
        file_type=["pdf", "docx", "doc", "pptx", "ppt", "xlsx", "xls",
                     "txt", "md", "csv", "tsv", "json", "yaml",
                     "sav", "dta", "sas7bdat",
                     "png", "jpg", "jpeg", "gif", "webp",
                     "ipynb", "py", "html"],
    )
    user_msg = None
    new_files = []
    if chat_result:
        # Streamlit 1.30+ accept_file 결과: ChatInputValue(text, files) — dict 양식
        user_msg = getattr(chat_result, "text", None) or (
            chat_result.get("text") if isinstance(chat_result, dict) else str(chat_result))
        new_files = getattr(chat_result, "files", None) or (
            chat_result.get("files") if isinstance(chat_result, dict) else []) or []

    # ★ chat_input의 첨부 즉시 처리 — universal_loader.load() → project.attachments
    if new_files:
        try:
            from src.ingestion.universal_loader import load as _ul_load
            import uuid as _uuid
            added = 0
            for f in new_files:
                if any(a.get("name") == f.name for a in attachments):
                    continue
                tmp_dir = Path(f"data/attachments/{pid}")
                tmp_dir.mkdir(parents=True, exist_ok=True)
                tmp_path = tmp_dir / f.name
                try:
                    tmp_path.write_bytes(f.getvalue())
                    loaded = _ul_load(tmp_path)
                    attachments.append({
                        "id": _uuid.uuid4().hex[:10],
                        "name": f.name,
                        "kind": loaded.get("kind", "unknown"),
                        "size_kb": tmp_path.stat().st_size // 1024,
                        "text": (loaded.get("text") or "")[:50000],
                        "image_data_uri": loaded.get("image_data_uri"),
                        "added_at": datetime.now().isoformat(),
                        "local_path": str(tmp_path),
                    })
                    added += 1
                except Exception as _e:
                    st.caption(f"⚠ {f.name}: {str(_e)[:80]}")
            if added:
                _save_project(project)
                # text 없이 첨부만이면 user_msg를 placeholder로
                if not (user_msg or "").strip():
                    user_msg = f"[첨부 {added}건 분석 시작 — universal_loader.load 완료, 다음 응답에 자동 inject]"
        except Exception as _e:
            st.caption(f"⚠ 첨부 처리 실패: {str(_e)[:80]}")

    if not user_msg and initial and not project["messages"]:
        user_msg = initial
        if not project.get("title") or project["title"] == "새 작업":
            project["title"] = initial[:60]

    # ★ LOOP_ENGINEERING_SPEC §4 — slash 명령 dispatch (/loop /goal /triage /state /...)
    if user_msg and user_msg.strip().startswith("/"):
        try:
            from src.loops.commands import dispatch_slash
            parts = user_msg.strip().split(maxsplit=1)
            cmd = parts[0]
            args = parts[1] if len(parts) > 1 else ""
            result = dispatch_slash(cmd, args, project=project,
                                       owner_email=(st.session_state.get("user") or {}).get("email", ""))
            # chat에 명령 + 결과 박음 (messages에 append 안 — 1회용 표시)
            st.markdown(
                f"<div class='msg-user'>{user_msg}</div>",
                unsafe_allow_html=True)
            title = result.get("title", "")
            body = result.get("body", "")
            kind = result.get("kind", "text")
            if kind == "json":
                import json as _j
                body_html = f"<pre style='font-size:0.78rem;background:#F1F5F9;padding:8px;border-radius:6px;overflow-x:auto;'>{_j.dumps(body, indent=2, ensure_ascii=False, default=str)[:3000]}</pre>"
            elif kind == "table":
                rows = result.get("rows") or []
                if rows:
                    headers = list(rows[0].keys())
                    body_html = "<table style='font-size:0.82rem;border-collapse:collapse;'><tr>" + \
                                  "".join(f"<th style='border:1px solid #cbd5e1;padding:4px 8px;background:#f1f5f9;'>{h}</th>" for h in headers) + "</tr>" + \
                                  "".join("<tr>" + "".join(f"<td style='border:1px solid #cbd5e1;padding:4px 8px;'>{str(r.get(h,''))[:80]}</td>" for h in headers) + "</tr>" for r in rows) + "</table>"
                else:
                    body_html = "<i>(빈 카탈로그)</i>"
            else:
                body_html = f"<div>{str(body).replace(chr(10), '<br>')}</div>"
            st.markdown(
                f"<div class='msg-asst'><b>{title}</b><br>{body_html}</div>",
                unsafe_allow_html=True)
        except Exception as _e:
            st.markdown(
                f"<div class='msg-asst' style='background:#FEE2E2;'>"
                f"slash 명령 실패: {_e}</div>", unsafe_allow_html=True)
        user_msg = None  # 일반 LLM 흐름 안 타게

    col_chat, col_preview = st.columns([0.46, 0.54], gap="medium")

    with col_chat:
        # 고정 높이 스크롤 박스 — 무한정 늘어나지 않음
        msgs_box = st.container(height=600, border=False)
        with msgs_box:
            # ★ UX-1 (2026-06-15): 빈 채팅 환영 화면 — 연구 시작 발견성·연결성 우선
            if not project.get("messages"):
                _render_welcome_chat(project, owner_email)

            # 1) 누적된 과거 메시지 (assistant 메시지엔 📌 핀 row 자동)
            for _i, m in enumerate(project.get("messages", [])):
                _render_msg(m.get("role", "assistant"), m.get("content", ""),
                              msg_idx=_i, project=project)

            # ★ Auto-scroll anchor (2026-06-14) — 새 메시지·스트리밍 chunk마다 최하단으로
            # st.container(height=...)의 내부 div가 [data-testid='stVerticalBlockBorderWrapper']
            # 아래에 있어 직접 scrollTop 강제. anchor 자체는 보이지 않음.
            st.markdown(
                "<div id='chat-bottom-anchor' style='height:1px;'></div>"
                "<script>"
                "(function(){"
                " const doc = window.parent ? window.parent.document : document;"
                " const a = doc.getElementById('chat-bottom-anchor');"
                " if(!a) return;"
                " let p = a.parentElement;"
                " while(p && p !== doc.body){"
                "  if(p.scrollHeight > p.clientHeight + 5){ p.scrollTop = p.scrollHeight; break; }"
                "  p = p.parentElement;"
                " }"
                " // also try scrollIntoView for browsers that ignore manual scrollTop on inner div"
                " try { a.scrollIntoView({block:'end', behavior:'instant'}); } catch(e){}"
                "})();"
                "</script>",
                unsafe_allow_html=True,
            )

            # 2) 새 사용자 입력 처리 (같은 run 안에서 스트리밍)
            if user_msg:
                if not project.get("title") or project["title"] == "새 작업":
                    project["title"] = user_msg[:60]
                project["messages"].append({"role": "user", "content": user_msg,
                                              "ts": datetime.now().isoformat()})
                # ★ user msg 즉시 영속화 (assistant 응답 도중 끊겨도 user 입력은 살아남음)
                _save_project(project)
                _render_msg("user", user_msg)

                # 트리거 분기 — autopilot / Full IMRAD / Figure / Go wide / Go deep / 일반
                wide = _is_go_wide_trigger(user_msg)
                deep = _is_go_deep_trigger(user_msg)
                full = _is_full_paper_trigger(user_msg)
                fig_type = _detect_figure_request(user_msg)

                if fig_type:
                    # Figure 양식 시도 — stat_result 있으면 PNG 양식 양식 양식
                    fig = _generate_figure(project, fig_type)
                    if fig:
                        png_bytes, caption = fig
                        import base64 as _b64
                        b64 = _b64.b64encode(png_bytes).decode()
                        img_html = (f"<div class='msg-asst'>📊 <b>{fig_type.upper()}</b><br>"
                                      f"<img src='data:image/png;base64,{b64}' style='max-width:100%;'><br>"
                                      f"<i>{caption}</i></div>")
                        st.markdown(img_html, unsafe_allow_html=True)
                        reply = f"[Figure: {fig_type} generated, caption: {caption}]"
                        # research_state.figures 양식 양식 양식
                        rs = project.setdefault("research_state", {})
                        figs = rs.setdefault("figures", [])
                        figs.append({"type": fig_type, "caption": caption,
                                       "size_bytes": len(png_bytes), "ts": datetime.now().isoformat()})
                    else:
                        reply = (f"📊 **{fig_type}** 그림을 만들려고 했지만, 이 프로젝트에 통계 결과(`research_state.stat_result`)가 "
                                 f"아직 없습니다. 먼저 통계 분석을 실행하거나 데이터를 업로드해 주세요. "
                                 f"분석 결과 dict가 준비되면 한 번에 7종(forest/subgroup/coef/roc/prev/table1/table2) 그림을 만들 수 있습니다.")
                        _render_msg("assistant", reply)
                elif _is_autopilot_trigger(user_msg):
                    # REAL HOOKUP (2026-06-14): service.paper.autopilot_run generator
                    # ★ UX-2: 5단계 진행도 시각화 (✅완료/⏳진행중/⏸대기)
                    from src.service.paper import autopilot_run as _autopilot
                    _STAGES_ORDER = ["pico", "novelty", "stat", "write", "polish", "save"]
                    _stage_state = {s: "pending" for s in _STAGES_ORDER}
                    _stage_msgs = {}
                    progress_box = st.empty()

                    def _render_progress():
                        rows = []
                        for s in _STAGES_ORDER:
                            st_ = _stage_state[s]
                            icon = {"pending": "⏸", "running": "⏳",
                                      "done": "✅", "skip": "⏭", "fail": "❌"}.get(st_, "⏸")
                            label = {"pico": "1) PICO 합의",
                                       "novelty": "2) 신규성 검토",
                                       "stat": "3) 통계 분석",
                                       "write": "4) 초안 작성",
                                       "polish": "5) 후처리(인용·그림)",
                                       "save": "6) 저장 + 프리뷰"}[s]
                            color = {"done": "#10B981", "running": "#3B82F6",
                                       "fail": "#DC2626", "pending": "#94A3B8",
                                       "skip": "#94A3B8"}.get(st_, "#94A3B8")
                            extra = f"<span style='color:#64748B;font-size:0.78rem;margin-left:8px;'>{_stage_msgs.get(s,'').replace('<','&lt;')[:120]}</span>" if _stage_msgs.get(s) else ""
                            rows.append(
                                f"<div style='padding:4px 0;color:{color};font-size:0.86rem;'>"
                                f"{icon} <b>{label}</b>{extra}</div>")
                        progress_box.markdown(
                            "<div class='msg-asst' style='padding:12px 16px;'>"
                            "<div style='font-size:0.78rem;color:#94A3B8;margin-bottom:6px;'>"
                            "🚀 알아서 해 파이프라인</div>" +
                            "".join(rows) +
                            "</div>", unsafe_allow_html=True)

                    _render_progress()  # 초기 (모두 ⏸ 대기)
                    reply_lines = []
                    try:
                        for event in _autopilot(project, user_msg):
                            stage = event.get("stage", "?")
                            status = event.get("status", "?")
                            msg = event.get("message", "")
                            reply_lines.append(f"[{stage}/{status}] {msg}")
                            # state machine update
                            if stage in _stage_state:
                                if status in ("running",):
                                    _stage_state[stage] = "running"
                                elif status == "done":
                                    _stage_state[stage] = "done"
                                elif status == "skip":
                                    _stage_state[stage] = "skip"
                                elif status in ("fail", "error"):
                                    _stage_state[stage] = "fail"
                                _stage_msgs[stage] = msg
                            _render_progress()
                            # Save manuscript to sections live → 우측 프리뷰 즉시 표시
                            # RESEARCH_STATE_SPEC §1: sections만 정본. manuscript_text 이중쓰기 제거.
                            mt = event.get("manuscript_text")
                            if mt:
                                project.setdefault("sections", {})["full"] = mt
                                _save_project(project)
                    except Exception as e:
                        reply_lines.append(f"⚠ autopilot 예외: {str(e)[:200]}")
                        progress_box.markdown(
                            "<div class='msg-asst'>" + "<br>".join(reply_lines) + "</div>",
                            unsafe_allow_html=True)
                    reply = "\n".join(reply_lines)
                else:
                    # 트리거별 system prompt overlay
                    extra_system = ""
                    badge = ""
                    if full:
                        extra_system = _full_paper_prompt(project)
                        badge = "📄 Full IMRAD manuscript — English, no fabrication\n\n"
                    elif wide:
                        extra_system = _go_wide_prompt(user_msg)
                        badge = "🌐 Go wide — PICO 변형 3-5개\n\n"
                    elif deep:
                        extra_system = _go_deep_prompt(user_msg, project)
                        badge = "🔬 Go deep — 3관점 내부화 토론\n\n"

                    # ★ stream_turn event generator (2026-06-14): FRONTEND_MIGRATION §5.5
                    # 3-Lane HOT(<300ms status) / STREAM(tool 이벤트+토큰) / BACKGROUND(배지)
                    from src.service.chat import stream_turn
                    activity = st.empty()    # 활동 로그 (hot)
                    preview_ph = st.empty()  # 우측 프리뷰 mirror (token)

                    # ★ 즉시 시각 피드백 (2026-06-15) — 사용자 사고: "대답 전 로딩 표시 없음"
                    # build_full_system이 RAG retrieve + persona 합성으로 0.5~3s 걸리니까,
                    # stream_turn 첫 status event 전에 미리 spinner 메시지 표시.
                    activity.markdown(
                        "<div class='msg-asst' style='font-size:0.82rem;"
                        "background:#F1F5F9;padding:8px 12px;'>"
                        "<span class='loading-dot'>●</span>"
                        "<span class='loading-dot'>●</span>"
                        "<span class='loading-dot'>●</span> "
                        "응답 준비 중 — RAG 검색 + 컨텍스트 합성</div>"
                        "<style>"
                        "@keyframes blink { 0%,100% {opacity:0.2;} 50% {opacity:1;} }"
                        ".loading-dot { display:inline-block; margin:0 1px;"
                        " animation: blink 1.4s infinite; color:#3B82F6; }"
                        ".loading-dot:nth-child(2) { animation-delay:0.2s; }"
                        ".loading-dot:nth-child(3) { animation-delay:0.4s; }"
                        "</style>",
                        unsafe_allow_html=True)

                    # ★ Silent reducer (2026-06-16): status/tool 메시지는 활동 placeholder
                    # 한 곳에만 (chat에 영구 row 추가 X). warning/badge는 expander로 숨김.
                    # error만 친절히 한 줄 표시. 사용자가 본문만 깔끔히 봄.
                    tool_log: list[str] = []
                    body_buf: list[str] = []
                    badges: list[tuple] = []      # 사후 표시용
                    warnings: list[tuple] = []
                    errors: list[tuple] = []
                    # ★ AGENT_OUTPUT_UX_SPEC §2: 사고 과정 트레이스 (실제 ChatEvent 기반).
                    # LLM이 '음 생각해보면…' 가짜 추론 X — status/tool_start/tool_result 실 로그.
                    trace: list[tuple] = []
                    last_activity_msg = "🔍 검색·합성 중…"

                    # ★ 2026-06-20 v2 UI 강화 (사용자 정직 지적: "그냥 멈추면 고장난거처럼 보이잖아").
                    # 활동 박스 = 카드 양식 + 진행 단계 카운트 + 최근 3건 tool 라인 + 펄스 spinner.
                    # VS Code Claude 우측 "진행 상황" 패널 효과.
                    step_count = {"n": 0}
                    recent_tools: list[str] = []

                    def _set_activity(text: str, kind: str = "status"):
                        step_count["n"] += 1
                        if kind == "tool_start":
                            recent_tools.append(f"🔧 {text}")
                        elif kind == "tool_result":
                            recent_tools.append(f"✓ {text}")
                        tail = recent_tools[-3:]
                        tools_html = ""
                        if tail:
                            tools_html = (
                                "<div style='margin-top:6px;font-size:0.72rem;"
                                "color:#64748b;line-height:1.5;'>" +
                                "<br>".join(t.replace("<", "&lt;") for t in tail) +
                                "</div>")
                        activity.markdown(
                            f"<div class='msg-asst' style='font-size:0.82rem;"
                            f"background:linear-gradient(90deg,#F8FAFC,#EFF6FF);"
                            f"border-left:3px solid #3B82F6;padding:10px 14px;"
                            f"color:#1E293B;border-radius:6px;'>"
                            f"<div style='display:flex;align-items:center;gap:8px;'>"
                            f"<span class='loading-dot' style='color:#3B82F6;'>●</span>"
                            f"<span class='loading-dot' style='color:#3B82F6;'>●</span>"
                            f"<span class='loading-dot' style='color:#3B82F6;'>●</span>"
                            f"<b style='color:#3B82F6;'>진행 중</b>"
                            f"<span style='color:#94a3b8;font-size:0.7rem;'>"
                            f"step {step_count['n']}</span></div>"
                            f"<div style='margin-top:4px;font-size:0.85rem;'>{text}</div>"
                            f"{tools_html}"
                            f"</div>", unsafe_allow_html=True)

                    # ★ 출력 짤림 단일원인 fix (사용자: "10개 추천 짤려서 다 안나옴")
                    # 4500/2000 → 16K/8K (Sonnet 4.x은 출력 64K 지원, 안전 마진)
                    _mt = 16000 if full else 8000
                    for evt in stream_turn(
                            project, user_msg,
                            owner_email=owner_email,
                            save_project_fn=_save_project,
                            max_tokens=_mt, max_iters=6):
                        et = evt.type
                        d = evt.data or {}
                        if et == "status":
                            # 1줄짜리 activity placeholder만 갱신, chat row 안 만듦
                            msg = d.get("msg", "")[:80]
                            if msg:
                                last_activity_msg = msg
                                _set_activity(msg)
                                trace.append(("status", msg))
                        elif et == "tool_start":
                            tool = d.get("tool", "")
                            args_brief = str(d.get("args_brief", ""))[:60]
                            last_activity_msg = f"🔧 {tool} 호출 중…"
                            _set_activity(last_activity_msg,
                                            kind="tool_start")
                            # tail에 도구명+args 표시
                            recent_tools[-1] = f"🔧 {tool}({args_brief})"
                            tool_log.append(f"🔧 {tool}")
                            trace.append(("tool_start", tool, d.get("args_brief", "")))
                        elif et == "tool_result":
                            tool = d.get("tool", "")
                            preview = str(d.get("preview", ""))[:80]
                            _set_activity(f"✓ {tool} 완료",
                                            kind="tool_result")
                            recent_tools[-1] = f"✓ {tool} → {preview}"
                            tool_log.append(f"✓ {tool}")
                            trace.append(("tool_result", tool,
                                            str(d.get("preview", ""))[:200]))
                        elif et == "token":
                            body_buf.append(d.get("text", ""))
                            safe = "".join(body_buf).replace("<","&lt;").replace(">","&gt;")
                            preview_ph.markdown(
                                f"<div class='msg-asst'>{safe}▌</div>",
                                unsafe_allow_html=True)
                            # 첫 토큰 시점에 activity 박스 비움 (응답 시작됨)
                            if len(body_buf) == 1:
                                activity.empty()
                        elif et == "warning":
                            warnings.append((d.get("kind", ""), d.get("msg", "")))
                        elif et == "badge":
                            badges.append((d.get("kind", ""), d.get("value", "")))
                        elif et == "error":
                            errors.append((d.get("where", "?"), d.get("msg", "")))
                        elif et == "done":
                            activity.empty()

                    reply = (badge + "".join(body_buf)).strip()
                    safe = reply.replace("<","&lt;").replace(">","&gt;")
                    preview_ph.markdown(
                        f"<div class='msg-asst'>{safe}</div>",
                        unsafe_allow_html=True)

                    # ★ 사후 표시 (silent) — error만 친절 표시, warning/badge는 expander로 숨김
                    if errors:
                        for where, msg in errors[:2]:
                            st.markdown(
                                f"<div class='msg-asst' style='font-size:0.82rem;"
                                f"background:#FEE2E2;border-left:3px solid #DC2626;"
                                f"padding:8px 12px;color:#991B1B;'>"
                                f"❌ <b>{where}</b><br>"
                                f"<span style='font-size:0.78rem;'>{msg[:200].replace('<','&lt;')}</span></div>",
                                unsafe_allow_html=True)
                    # ★ AGENT_OUTPUT_UX_SPEC §2: 사고 과정 트레이스 (가짜 추론 X — 실 ChatEvent)
                    if trace:
                        with st.expander(
                                f"🧠 사고 과정 ({len(trace)} 단계)",
                                expanded=False):
                            st.caption("✏️ 이 트레이스는 **실제 진행 로그**입니다 — "
                                         "LLM 추론 연기가 아니라 status/tool 이벤트의 사람 읽기 형태.")
                            _STEP_ICON = {
                                "status": "💭",
                                "tool_start": "🔧",
                                "tool_result": "✓",
                            }
                            for i, step in enumerate(trace[:30], 1):
                                kind = step[0]
                                icon = _STEP_ICON.get(kind, "·")
                                if kind == "status":
                                    st.markdown(f"`{i:02d}` {icon} {step[1]}")
                                elif kind == "tool_start":
                                    tool, args = step[1], step[2]
                                    if args:
                                        st.markdown(f"`{i:02d}` {icon} **{tool}** "
                                                      f"<span style='color:#94A3B8;font-size:0.8rem;'>"
                                                      f"({args[:80]})</span>",
                                                      unsafe_allow_html=True)
                                    else:
                                        st.markdown(f"`{i:02d}` {icon} **{tool}**")
                                elif kind == "tool_result":
                                    tool, preview = step[1], step[2]
                                    st.markdown(f"`{i:02d}` {icon} **{tool}** 결과: "
                                                  f"<span style='color:#64748B;font-size:0.8rem;'>"
                                                  f"{preview.replace('<','&lt;')}</span>",
                                                  unsafe_allow_html=True)

                    if warnings or badges or tool_log:
                        # ★ 친절 라벨/의미 매핑 (의학 연구자가 즉시 이해)
                        _KIND_LABEL = {
                            "provenance": "🛡 근거 검증",
                            "confidence": "📈 신뢰도",
                            "no_tools": "ℹ 도구 미사용",
                            "dispatch": "⚠ 호출 오류",
                            "gates": "🛡 검증 게이트",
                        }
                        n_warn = len(warnings)
                        with st.expander(
                                f"🔧 응답 점검 결과 — "
                                f"{('보완 권장 ' + str(n_warn) + '건') if n_warn else '문제 없음'}"
                                f"{(' · 도구 ' + str(len(tool_log))) if tool_log else ''}",
                                expanded=False):
                            st.caption("✏️ 아래 항목은 **자동 점검 결과**입니다. 본문에 직접 영향 X — "
                                         "참고만 하시고 필요한 곳에 인용·통계 보완을 권장합니다.")
                            if tool_log:
                                st.caption("**사용한 도구**: " + " · ".join(tool_log[:10]))
                            # warnings: kind를 친절 라벨로 변환, msg는 그대로 (confidence.py가 이미 한국어)
                            for kind, msg in warnings[:5]:
                                label = _KIND_LABEL.get(kind, f"⚠ {kind}")
                                st.markdown(f"- {label} · {msg[:280]}")
                            # badges: confidence는 점수 의미 자동 표시
                            for kind, val in badges[:5]:
                                if kind == "confidence":
                                    try:
                                        v = float(val)
                                        if v >= 0.8: tier = "높음 ✓ (근거 충실)"
                                        elif v >= 0.5: tier = "중간 (보완 권장)"
                                        elif v >= 0.2: tier = "낮음 (인용·통계 추가 필요)"
                                        else: tier = "매우 낮음 (초안 단계 — 검증 미진행)"
                                        st.markdown(f"- 📈 **신뢰도 점수**: {v:.2f} / 1.00 — {tier}")
                                    except Exception:
                                        st.markdown(f"- 📈 신뢰도: {val}")
                                else:
                                    label = _KIND_LABEL.get(kind, kind)
                                    st.markdown(f"- {label}: {val}")

                    # ★ Full IMRAD 후처리 chain (capability_bench 약점 자동 fix)
                    if full and not wide and not deep:  # Full IMRAD trigger 일 때만
                        try:
                            rag_ctx = _rag_retrieve(user_msg, top_k=5)
                            improved, meta = _post_process_imrad(reply, rag_ctx)
                            # 추가 chain — novelty + figure
                            improved, meta2 = _enrich_imrad(improved, project, user_msg)
                            meta["enrich_steps"] = meta2.get("steps", [])
                            meta["enrich_warnings"] = meta2.get("warnings", [])
                            meta["novelty_score"] = meta2.get("novelty_score")
                            meta["figures"] = meta2.get("figures")
                            # ★ 검증 게이트 4종 inline warning + provenance hard audit
                            try:
                                import re as _re
                                pmid_in_rag = _re.findall(r"PMID:(\d+)", rag_ctx or "")
                                from src.safety.inline_warnings import (run_all_gates,
                                                                          report_to_chat_blocks)
                                gates_rep = run_all_gates(
                                    improved,
                                    known_pmids=pmid_in_rag,
                                    novelty_score=meta2.get("novelty_score"),
                                    topic={"title": project.get("title")},
                                )
                                gate_blocks = report_to_chat_blocks(gates_rep)
                                meta["gates"] = {"total_issues": gates_rep.total_issues,
                                                  "blocks": gate_blocks}
                                for b in gate_blocks:
                                    st.markdown(
                                        f"<div class='msg-asst' style='font-size:0.82rem;"
                                        f"background:#FEF3C7;border-left:3px solid #F59E0B;"
                                        f"padding:8px 12px;'>{b.replace('<','&lt;').replace('>','&gt;')}</div>",
                                        unsafe_allow_html=True)

                                # ★ Phase-Next #2: provenance hard audit ("근거 없는 문장 출력 금지")
                                try:
                                    from src.safety.provenance_guard import audit as _prov_audit
                                    rs = project.get("research_state") or {}
                                    prov = _prov_audit(
                                        improved,
                                        stat_result=rs.get("stat_result"),
                                        rag_context=rag_ctx,
                                        rag_pmids=pmid_in_rag,
                                    )
                                    meta["provenance"] = {
                                        "ok": prov.ok,
                                        "citation_realism": prov.citation_realism_rate,
                                        "stat_traceability": prov.stat_traceability_rate,
                                        "strong_claims": prov.strong_claim_count,
                                        "issues": [{"severity": i.severity, "kind": i.kind,
                                                      "detail": i.detail[:200]}
                                                     for i in prov.issues[:10]],
                                    }
                                    severity_bg = "#FEE2E2" if not prov.ok else "#ECFDF5"
                                    severity_bd = "#DC2626" if not prov.ok else "#10B981"
                                    label = "❌ PROVENANCE BLOCK" if not prov.ok else "✅ PROVENANCE OK"
                                    summary_html = (
                                        f"<div class='msg-asst' style='font-size:0.82rem;"
                                        f"background:{severity_bg};border-left:3px solid {severity_bd};"
                                        f"padding:8px 12px;'>"
                                        f"<b>{label}</b> · citation realism {prov.citation_realism_rate:.0%} "
                                        f"({prov.citations_total} cites) · stat traceability "
                                        f"{prov.stat_traceability_rate:.0%} ({prov.stats_total} stats) · "
                                        f"strong claims {prov.strong_claim_count}"
                                    )
                                    if not prov.ok and prov.issues:
                                        summary_html += "<br>" + "<br>".join(
                                            f"• [{i.severity}] {i.kind}: {i.detail[:150]}".replace(
                                                "<", "&lt;").replace(">", "&gt;")
                                            for i in prov.issues[:5]
                                        )
                                    summary_html += "</div>"
                                    st.markdown(summary_html, unsafe_allow_html=True)
                                except Exception as _ep:
                                    meta.setdefault("warnings", []).append(f"provenance: {_ep}")
                            except Exception as _eg:
                                meta.setdefault("warnings", []).append(f"gates: {_eg}")
                            if improved != reply:
                                reply = improved
                                # 후처리 결과 chat에 표시
                                summary = (f"<div class='msg-asst' style='font-size:0.82rem;color:#475569;'>"
                                            f"📋 후처리 chain — {meta.get('refs_count',0)} refs cited · "
                                            f"steps: {len(meta.get('steps',[]))} · "
                                            f"warnings: {len(meta.get('warnings',[]))}</div>")
                                st.markdown(summary, unsafe_allow_html=True)
                                # 수정된 본문도 보여줌
                                safe2 = reply.replace("<","&lt;").replace(">","&gt;")
                                placeholder.markdown(
                                    f"<div class='msg-asst'>{safe2}</div>",
                                    unsafe_allow_html=True)
                                # research_state에 메타 저장
                                rs = project.setdefault("research_state", {})
                                rs["last_imrad_meta"] = meta
                        except Exception as _e:
                            st.caption(f"후처리 skip: {_e}")

                project["messages"].append({"role": "assistant", "content": reply,
                                              "ts": datetime.now().isoformat()})
                _save_project(project)
                _post_turn_hooks(project, user_msg, reply, owner_email)

                # ★ Post-turn auto-scroll (응답 완료 직후 최하단으로)
                st.markdown(
                    "<script>"
                    "(function(){"
                    " const doc = window.parent ? window.parent.document : document;"
                    " const a = doc.getElementById('chat-bottom-anchor');"
                    " if(a){ try{a.scrollIntoView({block:'end'});}catch(e){} }"
                    "})();"
                    "</script>", unsafe_allow_html=True)

                # ★ tool dispatch가 sections에 박은 결과를 우측 프리뷰에 즉시 반영 (2026-06-15)
                # patch_preview tool이 호출되면 project.sections 변경됨 →
                # rerun 한 번 더 돌려서 col_preview가 새 sections 읽어 다시 그림.
                # 사용자 사고: "프리뷰에 바로바로 연동 안 됨"의 진짜 원인.
                if (project.get("sections") and
                    st.session_state.get("_last_preview_hash") !=
                    hash(repr(project.get("sections", {})))):
                    st.session_state["_last_preview_hash"] = hash(
                        repr(project.get("sections", {})))
                    st.rerun()

    with col_preview:
        sections = project.get("sections") or {}
        rs = project.get("research_state") or {}
        refs = rs.get("references") or []
        ref_style = rs.get("reference_style") or "vancouver"
        target_journal = rs.get("target_journal", "")

        if not sections:
            st.markdown(
                """
                <div class='preview-box'>
                  <div class='preview-empty'>
                    <div style='font-size:64px;line-height:1;margin-bottom:20px;'>🔬</div>
                    <div style='font-size:1.4rem;font-weight:600;color:#0F172A;margin-bottom:6px;'>
                      Medical-Agent
                    </div>
                    <div style='color:#64748B;font-size:0.92rem;margin-bottom:24px;'>
                      Vibe paper copilot · clinical / translational medicine
                    </div>
                    <div style='color:#94A3B8;font-size:0.82rem;line-height:1.6;
                                 max-width:340px;margin:0 auto;'>
                      대화로 주제·데이터·통계가 합의되고<br>
                      <b style='color:#475569;'>'알아서 해'</b>라고 말씀하시면<br>
                      이곳에 논문 초안이 실시간으로 작성됩니다.<br><br>
                      <span style='font-size:0.78rem;'>"논문 쓰자" → Full IMRAD · English<br>
                      "3가지로 펼쳐" → Go wide (PICO 변형)<br>
                      "이 방향 깊게" → Go deep (3관점 토론)</span>
                    </div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True)
        else:
            # Top toolbar: target journal + reference style + export buttons
            tj_label = target_journal or "Target journal: (not set)"
            st.markdown(
                f"<div style='display:flex;justify-content:space-between;align-items:center;"
                f"padding:6px 12px;background:#F8FAFC;border:1px solid rgba(15,23,42,0.08);"
                f"border-radius:8px;margin-bottom:8px;font-size:0.82rem;color:#475569;'>"
                f"<span>{tj_label}</span><span>📖 {ref_style.title()} style · {len(refs)} refs</span></div>",
                unsafe_allow_html=True)

            # Export buttons row
            c1, c2, c3 = st.columns(3)
            try:
                from src.export.citation_workflow import (
                    build_cited_docx, endnote_bytes, bibtex_bytes, Reference)
                # refs는 dict list로 직렬화되어 있을 수 있음 → Reference 객체로 변환
                ref_objs = []
                for rd in refs:
                    if isinstance(rd, dict):
                        ref_objs.append(Reference(**{k: rd.get(k, "") for k in
                            ("pmid","doi","title","journal","year","volume","issue","pages","abstract","citation_key")} | {"authors": rd.get("authors", [])}))
                    else:
                        ref_objs.append(rd)
                docx_bytes = build_cited_docx(project.get("title","Paper"), sections, ref_objs, style=ref_style)
                with c1:
                    st.download_button("📥 Word (.docx)", data=docx_bytes,
                        file_name=f"{project.get('id','paper')}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True, disabled=not docx_bytes)
                with c2:
                    enl = endnote_bytes(ref_objs)
                    st.download_button("📚 EndNote (.xml)", data=enl,
                        file_name=f"{project.get('id','paper')}.enl.xml",
                        mime="application/xml",
                        use_container_width=True, disabled=not enl)
                with c3:
                    bib = bibtex_bytes(ref_objs)
                    st.download_button("📑 BibTeX (.bib)", data=bib,
                        file_name=f"{project.get('id','paper')}.bib",
                        mime="application/x-bibtex",
                        use_container_width=True, disabled=not bib)
            except Exception as _e:
                st.caption(f"export 양식 미준비: {_e}")

            # Manuscript body — case-insensitive lookup (2026-06-15)
            # 📌 핀 UX가 박는 Title Case("Abstract") + 기존 lowercase("abstract") 모두 인식
            html_parts = [f"<div class='preview-box'><h1>{project.get('title','')[:80]}</h1>"]
            def _get_section(name: str):
                for k in (name, name.lower(), name.capitalize(), name.upper()):
                    if k in sections and sections[k]:
                        return sections[k]
                return None
            for key in ["Abstract", "Introduction", "Methods", "Results",
                          "Discussion", "Conclusion", "Tables", "Figures"]:
                v = _get_section(key)
                if not v:
                    continue
                # dict 섹션(Abstract.Background 등) — flatten 표시
                if isinstance(v, dict):
                    sub_parts = []
                    for sk, sv in v.items():
                        if not sv:
                            continue
                        sv_s = str(sv).replace("<", "&lt;").replace(">", "&gt;")
                        sub_parts.append(f"<p><b>{sk}:</b> {sv_s}</p>")
                    body_html = "".join(sub_parts)
                else:
                    body = str(v).replace("<", "&lt;").replace(">", "&gt;")
                    body_html = "".join(f"<p>{para}</p>"
                                          for para in body.split("\n\n") if para.strip())
                if body_html:
                    html_parts.append(f"<h2>{key}</h2>{body_html}")

            # References block (저널별 style 적용)
            if refs:
                try:
                    from src.export.citation_workflow import format_reference
                    html_parts.append("<h2>References</h2>")
                    for i, rd in enumerate(refs, 1):
                        if isinstance(rd, dict):
                            r_obj = Reference(**{k: rd.get(k, "") for k in
                                ("pmid","doi","title","journal","year","volume","issue","pages","abstract","citation_key")} | {"authors": rd.get("authors", [])})
                        else:
                            r_obj = rd
                        formatted = format_reference(r_obj, i, ref_style).replace("<","&lt;").replace(">","&gt;")
                        html_parts.append(f"<p style='font-size:0.85rem;color:#475569;'>{formatted}</p>")
                except Exception:
                    pass

            html_parts.append("</div>")
            st.markdown("".join(html_parts), unsafe_allow_html=True)


def render() -> None:
    """홈 렌더링 — 항상 chat(좌) + preview(우) 고정 2-split.

    Hero / chips / 우측 RECENT grid / FAB 모두 제거. 단일 항상-고정 레이아웃.

    Project ID resolution (F5 safe — 2026-06-14 사고 fix):
      1) URL query param ?pid=...   (F5 후에도 살아남는 진짜 진실원본)
      2) session_state sg_active_project  (같은 탭 내 폴백)
      3) 새 UUID 생성 (그리고 즉시 URL에 박음)
    """
    import uuid as _uuid
    inject_sapphire_glass()
    _sidebar()

    # 1) URL query → 가장 강한 진실원본 (F5 후에도 보존)
    # 2026-06-15: Streamlit 버전에 따라 qp가 dict-like 또는 legacy QueryParams
    url_pid = None
    try:
        qp = st.query_params
        # 새 API (Streamlit ≥1.30)
        if hasattr(qp, "get_all"):
            vals = qp.get_all("pid")
            url_pid = vals[0] if vals else None
        elif hasattr(qp, "get"):
            v = qp.get("pid")
            if isinstance(v, list):
                url_pid = v[0] if v else None
            else:
                url_pid = v
        # __getitem__ fallback
        if not url_pid:
            try:
                v = qp["pid"]
                url_pid = v[0] if isinstance(v, list) else v
            except (KeyError, TypeError):
                pass
    except Exception:
        url_pid = None
    # 빈 문자열 / "None" / "null" 정규화
    if url_pid in (None, "", "None", "null"):
        url_pid = None

    # 2) URL 우선, 없으면 session_state
    active = url_pid or st.session_state.get("sg_active_project")

    # ★ 사용자 정직 지적(2026-06-20): '껐다가 키더라도 직전까지 하던 상태 유지'.
    # URL/session_state 둘 다 없으면 → 가장 최근 mtime project 자동 활성화 (ChatGPT 양식).
    if not active or active == "new":
        try:
            from pathlib import Path as _P
            chat_dir = _P("data/runtime/projects")
            if chat_dir.exists():
                # 가장 최근 mtime의 chat_*.json 자동 선택
                files = sorted(chat_dir.glob("chat_*.json"),
                                  key=lambda p: p.stat().st_mtime, reverse=True)
                if files:
                    candidate = files[0].stem  # chat_xxxxxxxxxx
                    # 빈 채팅이 아닌지 확인 (messages 1개 이상)
                    try:
                        import json as _json
                        d = _json.loads(files[0].read_text(encoding="utf-8"))
                        if d.get("messages"):
                            active = candidate
                            st.session_state["sg_active_project"] = active
                    except Exception:
                        pass
        except Exception:
            pass

    # 3) 그래도 없으면 새 UUID
    if not active or active == "new":
        active = f"chat_{_uuid.uuid4().hex[:10]}"

    # 4) URL + session_state 동기화 → 다음 F5도 안전
    try:
        st.query_params["pid"] = active
    except Exception:
        pass
    st.session_state["sg_active_project"] = active

    _render_chat_page(active)


# Streamlit 멀티페이지: 페이지 파일을 runpy로 실행하므로 무조건 render() 호출
# (Streamlit은 `runpy.run_path(...,run_name='__main__')` 으로 page를 실행)
try:
    render()
except Exception as _e:
    import traceback
    st.error(f"EZ home 렌더 실패: {_e}")
    st.code(traceback.format_exc())
    st.info("기존 단위 기능 UI는 메인(/) 페이지에서 정상 동작합니다.")
