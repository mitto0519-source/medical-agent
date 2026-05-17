"""Medical-Agent Streamlit UI — Dark Theme + AI Panel + Activity History"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
os.environ['PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION'] = 'python'

from dotenv import load_dotenv
from pathlib import Path as _Path
# Explicit path — works regardless of Streamlit's working directory
_root = _Path(__file__).parent.parent
load_dotenv(dotenv_path=_root / ".env", override=True)

import streamlit as st
import json
from pathlib import Path

try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass

st.set_page_config(
    page_title="Medical-Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ══════════════════════════════════════════════════════════════════════
# CSS — Dark Theme
# ══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
:root {
    --bg:#0B1220; --bg2:#121A2B; --bg3:#16223A; --bg4:#1A2540;
    --border:#1F2A44; --t1:#E5E7EB; --t2:#94A3B8; --t3:#64748B;
    --accent:#6366F1; --accent2:#818CF8; --green:#22C55E; --blue:#3B82F6;
    --warning:#F59E0B; --danger:#EF4444;
}
#MainMenu,header,footer,.stDeployButton{visibility:hidden;display:none;}
.stApp,[data-testid="stAppViewContainer"]{background:var(--bg)!important;}
[data-testid="stSidebar"]{background:var(--bg2)!important;border-right:1px solid var(--border)!important;}
[data-testid="stSidebar"]>div:first-child{padding:0!important;}
.main .block-container{padding:1.5rem 2rem!important;max-width:100%!important;}

[data-testid="stSidebar"] .stButton>button{
    background:transparent!important;border:none!important;color:var(--t2)!important;
    text-align:left!important;padding:7px 14px!important;width:100%!important;
    border-radius:6px!important;font-size:13.5px!important;transition:all 0.15s!important;
    box-shadow:none!important;margin:1px 0!important;justify-content:flex-start!important;
}
[data-testid="stSidebar"] .stButton>button:hover{background:rgba(124,58,237,.12)!important;color:var(--t1)!important;}
[data-testid="stSidebar"] .stButton>button:focus{box-shadow:none!important;}
.nav-active [data-testid="stSidebar"] .stButton>button{background:rgba(124,58,237,.2)!important;color:var(--t1)!important;font-weight:600!important;}
.nav-section{font-size:11px;font-weight:600;color:var(--t3);text-transform:uppercase;letter-spacing:.08em;padding:14px 16px 5px;}
.sidebar-logo{padding:18px 16px 14px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.sidebar-profile{padding:12px 14px;border-top:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.s-avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#2563eb);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:white;flex-shrink:0;}
.s-name{font-size:13px;font-weight:600;color:var(--t1);}
.s-email{font-size:11px;color:var(--t3);}

.card{background:var(--bg3);border:1px solid var(--border);border-radius:12px;padding:20px;}
.pipeline-step{background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:18px 20px;}
.step-n{font-size:11px;color:var(--accent2);font-weight:600;margin-bottom:6px;}
.step-t{font-size:15px;font-weight:700;color:var(--t1);margin-bottom:5px;}
.step-d{font-size:12px;color:var(--t2);}
.kb-item{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:9px;background:var(--bg4);border:1px solid var(--border);margin-bottom:8px;}
.kb-badge{background:var(--green);color:#000;font-size:11px;font-weight:700;padding:2px 8px;border-radius:20px;margin-left:auto;}
.proj-row{display:flex;align-items:center;padding:13px 0;border-bottom:1px solid var(--border);gap:12px;}
.proj-badge{font-size:12px;padding:3px 10px;border-radius:20px;margin-left:auto;flex-shrink:0;}

.history-item{padding:10px 12px;border-radius:8px;background:var(--bg4);border:1px solid var(--border);margin-bottom:6px;}
.history-ts{font-size:10px;color:var(--t3);}
.history-action{font-size:12px;color:var(--t2);}
.history-summary{font-size:13px;color:var(--t1);font-weight:500;}

.ai-panel-wrap{background:var(--bg2);border:1px solid var(--border);border-radius:12px;padding:14px;height:100%;}

[data-testid="stMetric"]{background:var(--bg3)!important;border:1px solid var(--border)!important;border-radius:10px!important;padding:16px!important;}
[data-testid="stMetricLabel"]{color:var(--t2)!important;font-size:12px!important;}
[data-testid="stMetricValue"]{color:var(--t1)!important;}
h1,h2,h3,h4,p,label{color:var(--t1)!important;}
.stMarkdown p{color:var(--t1)!important;}
input,textarea,[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:var(--bg3)!important;border-color:var(--border)!important;color:var(--t1)!important;}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--accent),var(--accent2))!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;}
hr,[data-testid="stDivider"]{border-color:var(--border)!important;}
[data-testid="stExpander"]{background:var(--bg3)!important;border:1px solid var(--border)!important;border-radius:8px!important;}
[data-testid="stSelectbox"]>div>div{background:var(--bg3)!important;border-color:var(--border)!important;color:var(--t1)!important;}
[data-testid="stTabs"] [role="tablist"]{border-bottom:1px solid var(--border)!important;}
[data-testid="stTabs"] button[role="tab"]{color:var(--t2)!important;}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:var(--accent2)!important;border-bottom:2px solid var(--accent2)!important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# Login Gate — with remember-me (st.query_params) + auto-login
# ══════════════════════════════════════════════════════════════════════
def _login_gate():
    if "user" in st.session_state:
        return True

    # Auto-login from query params
    params = st.query_params
    saved_email = params.get("email", "")
    auto_login = params.get("auto", "") == "1"

    if saved_email and auto_login:
        from src.auth.users import get_user_by_email
        user = get_user_by_email(saved_email.strip().lower())
        if user:
            st.session_state["user"] = user
            st.rerun()

    st.markdown("""
    <div style="max-width:420px;margin:80px auto;padding:2.5rem;
                background:#1c2128;border:1px solid #30363d;border-radius:16px;
                box-shadow:0 16px 48px rgba(0,0,0,0.5);text-align:center;">
        <div style="font-size:2.5rem;margin-bottom:0.5rem;">🔬</div>
        <h2 style="color:#e6edf3;margin:0;font-size:1.4rem;">Medical-Agent</h2>
        <p style="color:#8b949e;margin-top:.4rem;font-size:.85rem;">조유선 스타일 의학 논문 자동 생산 파이프라인</p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        email = st.text_input("이메일 주소", value=saved_email, placeholder="your@email.com")
        col_r, col_a = st.columns(2)
        with col_r:
            remember = st.checkbox("이메일 기억하기", value=bool(saved_email))
        with col_a:
            autologin = st.checkbox("자동 로그인", value=auto_login,
                                    help="다음 방문 시 이메일 확인 없이 바로 접속")
        submitted = st.form_submit_button("접속하기", use_container_width=True, type="primary")

    if submitted:
        if not email or "@" not in email:
            st.error("올바른 이메일 주소를 입력하세요.")
            return False
        from src.auth.users import get_user_by_email
        user = get_user_by_email(email.strip().lower())
        if not user:
            st.error("등록되지 않은 이메일입니다.")
            return False
        st.session_state["user"] = user
        # Save to query params for next visit
        if remember:
            st.query_params["email"] = email.strip().lower()
            if autologin:
                st.query_params["auto"] = "1"
            else:
                st.query_params.pop("auto", None)
        else:
            st.query_params.pop("email", None)
            st.query_params.pop("auto", None)
        st.rerun()
    return False

if not _login_gate():
    st.stop()

# API 키 확인 — 누락 시 경고
if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("OPENAI_API_KEY"):
    st.warning(
        "⚠️ **LLM API 키가 설정되지 않았습니다.**  \n"
        f"`{str(_root / '.env')}` 파일에 `ANTHROPIC_API_KEY=sk-ant-...` 또는 `OPENAI_API_KEY=sk-...` 를 추가하거나 "
        "Streamlit Cloud Secrets를 설정하세요.",
        icon="🔑",
    )

# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════
if "nav" not in st.session_state:
    st.session_state["nav"] = "홈"

def _nav(p):
    st.session_state["nav"] = p
    st.rerun()

def _log(action, inp, summary, out=None):
    from src.activity.logger import log_activity
    user_email = st.session_state.get("user", {}).get("email", "anonymous")
    log_activity(user_email, st.session_state["nav"], action, inp, summary, out)

def _show_history(page_name: str):
    """Show collapsed activity history for this page."""
    user_email = st.session_state.get("user", {}).get("email", "")
    if not user_email:
        return
    from src.activity.logger import get_user_log
    logs = get_user_log(user_email, page=page_name, limit=10)
    if not logs:
        return
    with st.expander(f"📋 이전 작업 이력 ({len(logs)}건) — 클릭하여 재사용", expanded=False):
        for entry in logs:
            st.markdown(f"""
            <div class="history-item">
                <div class="history-ts">{entry['timestamp']}</div>
                <div class="history-summary">{entry.get('output_summary','')[:120]}</div>
                <div class="history-action">입력: {str(entry.get('input',''))[:80]}</div>
            </div>
            """, unsafe_allow_html=True)
            col_a, col_b = st.columns([3, 1])
            with col_b:
                if st.button("↩ 재사용", key=f"_reuse_{entry['id']}"):
                    st.session_state["_replay"] = entry
                    st.rerun()

page = st.session_state["nav"]
_u = st.session_state.get("user", {})

# ══════════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════════
def _nb(label, target):
    active = page == target
    prefix = "▸ " if active else "   "
    st.markdown(f'<div class="{"nav-active" if active else ""}">', unsafe_allow_html=True)
    if st.button(f"{prefix}{label}", key=f"_nb_{target}"):
        _nav(target)
    st.markdown('</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span style="font-size:22px;">🔬</span>
        <span style="font-size:15px;font-weight:800;color:#e6edf3;">Medical-Agent</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="padding:8px 8px 4px;">', unsafe_allow_html=True)
    _nb("🏠  홈", "홈")
    _nb("⚡  워크플로우", "워크플로우")
    st.markdown('<div class="nav-section">프로젝트</div>', unsafe_allow_html=True)
    _nb("🔴  논문 생산 파이프라인", "논문 생산 파이프라인")
    _nb("🔴  연구 주제 생성", "연구 주제 생성")
    _nb("🔵  데이터 분석", "데이터 분석")
    _nb("🟢  논문 설계 & 타당성", "논문 설계 & 타당성")
    _nb("🔴  논문 작성", "논문 작성")
    _nb("🔵  신규성 확인", "신규성 확인")
    st.markdown('<div class="nav-section">에이전트</div>', unsafe_allow_html=True)
    _nb("○  Agent Q&A", "Agent Q&A")
    _nb("○  Notebook 에디터", "Notebook 에디터")
    st.markdown('<div class="nav-section">도구</div>', unsafe_allow_html=True)
    _nb("○  논문 업로드 & 인제스트", "논문 업로드 & 인제스트")
    _nb("○  지식베이스 관리", "지식베이스 관리")
    _nb("○  자동 학습 루프", "자동 학습 루프")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── LLM Provider 설정 ──────────────────────────────────────────
    st.markdown('<div class="nav-section">AI 어시스턴트</div>', unsafe_allow_html=True)
    st.markdown('<div style="padding:0 8px 8px;">', unsafe_allow_html=True)

    _PROVIDERS = {
        "🟠 Claude": "Claude (Anthropic)",
        "🟢 GPT-4": "GPT-4 (OpenAI)",
        "🔵 Gemini": "Gemini (Google)",
    }
    # Load saved setting
    _email = _u.get("email", "")
    if "llm_settings" not in st.session_state:
        try:
            from src.auth.users import get_llm_settings
            st.session_state["llm_settings"] = get_llm_settings(_email)
        except Exception:
            st.session_state["llm_settings"] = {"provider": "Claude (Anthropic)", "api_key": ""}

    _saved = st.session_state["llm_settings"]
    _cur_icon = next((k for k, v in _PROVIDERS.items() if v == _saved["provider"]), "🟠 Claude")

    _sel_icon = st.radio(
        "LLM 선택",
        list(_PROVIDERS.keys()),
        index=list(_PROVIDERS.keys()).index(_cur_icon),
        horizontal=True,
        key="_sidebar_llm_radio",
        label_visibility="collapsed",
    )
    _sel_provider = _PROVIDERS[_sel_icon]

    with st.expander("🔑 API Key 설정", expanded=False):
        _api_key_input = st.text_input(
            "API Key",
            value=_saved.get("api_key", ""),
            type="password",
            key="_sidebar_api_key",
            placeholder="sk-ant-... / sk-... / AI...",
            label_visibility="collapsed",
        )
        if st.button("💾 저장", key="_llm_save", use_container_width=True, type="primary"):
            try:
                from src.auth.users import save_llm_settings
                save_llm_settings(_email, _sel_provider, _api_key_input)
                st.session_state["llm_settings"] = {"provider": _sel_provider, "api_key": _api_key_input}
                # Push to AI panel session state
                st.session_state["_ai_provider"] = _sel_provider
                if _api_key_input:
                    st.session_state.setdefault("user_api_keys", {})
                    pk = _sel_provider.split()[0].lower()
                    st.session_state["user_api_keys"][pk] = _api_key_input
                st.success("저장됨!")
            except Exception as e:
                st.error(f"오류: {e}")

    # Push current provider to AI panel on every render
    if _sel_provider != _saved.get("provider"):
        st.session_state["llm_settings"]["provider"] = _sel_provider
    st.session_state["_ai_provider"] = _sel_provider

    st.markdown('</div>', unsafe_allow_html=True)

    # ── User profile ───────────────────────────────────────────────
    user_initial = (_u.get("name") or "U")[0].upper()
    role_tag = "👑 " if _u.get("role") == "super_admin" else ""
    st.markdown(f"""
    <div class="sidebar-profile">
        <div class="s-avatar">{user_initial}</div>
        <div style="flex:1;min-width:0;">
            <div class="s-name">{role_tag}{_u.get('name','')}</div>
            <div class="s-email">{_u.get('email','')}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("로그아웃", key="__logout__"):
        st.query_params.pop("auto", None)
        del st.session_state["user"]
        st.rerun()

# ══════════════════════════════════════════════════════════════════════
# Main layout: content col (left) + AI panel col (right)
# ══════════════════════════════════════════════════════════════════════
page_context: dict = {"current_page": page}
main_col, ai_col = st.columns([13, 7])

# ══════════════════════════════════════════════════════════════════════
# PAGE CONTENT
# ══════════════════════════════════════════════════════════════════════
with main_col:

    # ── HOME ─────────────────────────────────────────────────────────
    if page == "홈":
        col_h, col_btn = st.columns([5, 1])
        with col_h:
            st.markdown("""
            <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
                <span style="font-size:26px;font-weight:800;color:#e6edf3;">Medical-Agent</span>
                <span style="font-size:18px;">✨</span>
            </div>
            <p style="color:#8b949e;font-size:14px;margin:0;">조유선 스타일 의학 논문 자동 생산 파이프라인</p>
            """, unsafe_allow_html=True)
        with col_btn:
            st.markdown('<div style="margin-top:6px;"></div>', unsafe_allow_html=True)
            if st.button("➕ 새 프로젝트", type="primary", use_container_width=True):
                _nav("연구 주제 생성")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        for col, (num, title, desc, color) in zip([c1, c2, c3], [
            ("1 단계", "연구 주제 생성", "K-PRESS 데이터셋 · RAG 기반 주제 자동 생성", "#7c3aed"),
            ("2 단계", "연구 설계 & 타당성", "PubMed 검색 · Claude 분석", "#8b5cf6"),
            ("3 단계", "논문 작성", "조유선 스타일로 전체 논문 초안 생성", "#6d28d9"),
        ]):
            with col:
                st.markdown(f"""
                <div class="pipeline-step" style="border-left:3px solid {color};">
                    <div class="step-n">{num}</div><div class="step-t">{title}</div><div class="step-d">{desc}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown('<div class="card"><div style="font-size:16px;font-weight:700;color:#e6edf3;margin-bottom:4px;">🚀 빠른 시작</div><p style="color:#8b949e;font-size:13px;margin-bottom:12px;">원하는 작업을 선택하세요.</p></div>', unsafe_allow_html=True)
            for icon, label, desc, target in [
                ("📝", "연구 주제 생성", "새로운 연구 아이디어 발굴", "연구 주제 생성"),
                ("🔍", "연구 설계", "방법론 및 타당성 검토", "논문 설계 & 타당성"),
                ("✍️", "논문 초안 생성", "AI 기반 논문 초안 자동 작성", "논문 작성"),
                ("📊", "데이터 분석", "통계 분석 및 변수 탐색", "데이터 분석"),
            ]:
                if st.button(f"{icon}  {label}  ·  {desc}", key=f"_qs_{target}", use_container_width=True):
                    _nav(target)

        with col_r:
            st.markdown('<div class="card"><div style="font-size:16px;font-weight:700;color:#e6edf3;margin-bottom:4px;">🎓 학습된 자료</div><p style="color:#8b949e;font-size:13px;margin-bottom:12px;">조유선 교수님 연구 스타일 학습 자료.</p></div>', unsafe_allow_html=True)
            try:
                pp = Path("data/yoosun_cho_papers.json")
                if pp.exists():
                    cnt = len(json.loads(pp.read_text(encoding="utf-8")))
                    st.markdown(f'<div class="kb-item"><span style="font-size:20px;">📚</span><div><div style="font-size:13px;font-weight:600;color:#e6edf3;">조유선 교수 논문 학습 완료</div><div style="font-size:12px;color:#8b949e;">총 {cnt}편</div></div><div class="kb-badge">100%</div></div>', unsafe_allow_html=True)
            except Exception: pass
            try:
                lp = Path("data/libraries/dataset_kyrbs.json")
                if lp.exists():
                    ds_kyrbs = json.loads(lp.read_text(encoding="utf-8"))
                    n_vars = len(ds_kyrbs.get("variables", {}))
                    st.markdown(f'<div class="kb-item"><span style="font-size:20px;">📊</span><div><div style="font-size:13px;font-weight:600;color:#e6edf3;">KYRBS (청소년건강행태조사)</div><div style="font-size:12px;color:#8b949e;">{n_vars}개 변수</div></div><div class="kb-badge">100%</div></div>', unsafe_allow_html=True)
            except Exception: pass
            try:
                lp2 = Path("data/libraries/dataset_knhanes.json")
                if lp2.exists():
                    ds_knh = json.loads(lp2.read_text(encoding="utf-8"))
                    n_vars2 = len(ds_knh.get("variables", {}))
                    n_refs = len(ds_knh.get("papers_using_this", []))
                    st.markdown(f'<div class="kb-item"><span style="font-size:20px;">🏥</span><div><div style="font-size:13px;font-weight:600;color:#e6edf3;">KNHANES (국민건강영양조사)</div><div style="font-size:12px;color:#8b949e;">{n_vars2}개 변수 · 참조논문 {n_refs}편</div></div><div class="kb-badge">100%</div></div>', unsafe_allow_html=True)
            except Exception: pass
            try:
                from src.vectordb.store import get_vector_store
                cnt2 = get_vector_store().count()
                db_lbl = "Supabase" if os.environ.get("SUPABASE_DB_URL") else "ChromaDB"
                st.markdown(f'<div class="kb-item"><span style="font-size:20px;">🗄️</span><div><div style="font-size:13px;font-weight:600;color:#e6edf3;">의학 용어 사전 ({db_lbl})</div><div style="font-size:12px;color:#8b949e;">{cnt2:,}개 청크</div></div><div class="kb-badge">100%</div></div>', unsafe_allow_html=True)
            except Exception: pass
            if st.button("전체 학습 자료 보기 →", key="_kb_all", use_container_width=True):
                _nav("지식베이스 관리")

        st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
        recent = st.session_state.get("recent_projects", [])
        st.markdown('<div class="card"><div style="font-size:16px;font-weight:700;color:#e6edf3;margin-bottom:14px;">최근 프로젝트</div>', unsafe_allow_html=True)
        if not recent:
            st.markdown('<div style="text-align:center;padding:24px;color:#6e7681;font-size:13px;">아직 진행 중인 프로젝트가 없습니다.</div>', unsafe_allow_html=True)
        else:
            badge_colors = {"논문 작성 중": "#8b5cf6", "데이터 분석 중": "#3b82f6", "연구 설계 중": "#10b981"}
            for proj in recent[:5]:
                c = badge_colors.get(proj.get("status",""), "#6e7681")
                st.markdown(f'<div class="proj-row"><div><div style="font-size:14px;font-weight:600;color:#e6edf3;">{proj.get("title","")}</div><div style="font-size:12px;color:#6e7681;">{proj.get("updated","")}</div></div><div class="proj-badge" style="background:{c}22;color:{c};">{proj.get("status","")}</div></div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        page_context.update({"recent_projects": len(recent), "학습된_논문수": "14편"})

    # ── WORKFLOW ──────────────────────────────────────────────────────
    elif page == "워크플로우":
        st.markdown("<h2 style='color:#e6edf3;'>⚡ 워크플로우</h2>", unsafe_allow_html=True)
        for n, t, d, target in [
            ("1", "연구 주제 생성", "KYRBS / KNHANES 데이터 + RAG로 주제 자동 생성", "연구 주제 생성"),
            ("2", "신규성 확인", "PubMed로 연구 공백 확인", "신규성 확인"),
            ("3", "타당성 검증", "데이터셋 변수 기반 연구 가능성 검토", "논문 설계 & 타당성"),
            ("4", "논문 작성", "조유선 스타일 자동 초안 생성", "논문 작성"),
        ]:
            c1, c2 = st.columns([4, 1])
            with c1:
                st.markdown(f'<div class="pipeline-step" style="margin-bottom:10px;"><div class="step-n">STEP {n}</div><div class="step-t">{t}</div><div class="step-d">{d}</div></div>', unsafe_allow_html=True)
            with c2:
                st.markdown("<div style='margin-top:14px;'></div>", unsafe_allow_html=True)
                if st.button("시작 →", key=f"_wf_{n}", use_container_width=True, type="primary"):
                    _nav(target)
        _show_history("워크플로우")

    # ── 논문 생산 파이프라인 ───────────────────────────────────────────
    elif page == "논문 생산 파이프라인":
        st.markdown("<h2 style='color:#e6edf3;'>🔴 논문 생산 파이프라인</h2>", unsafe_allow_html=True)
        st.info("전체 논문 생산 프로세스 통합 관리. 왼쪽 메뉴에서 각 단계를 선택하세요.")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📚 연구 주제 생성 →", use_container_width=True, type="primary"): _nav("연구 주제 생성")
            if st.button("✅ 논문 설계 & 타당성 →", use_container_width=True): _nav("논문 설계 & 타당성")
        with c2:
            if st.button("🔍 신규성 확인 →", use_container_width=True): _nav("신규성 확인")
            if st.button("📝 논문 작성 →", use_container_width=True): _nav("논문 작성")

    # ── 연구 주제 생성 ────────────────────────────────────────────────
    elif page == "연구 주제 생성":
        st.markdown("<h2 style='color:#e6edf3;'>📚 연구 주제 생성</h2>", unsafe_allow_html=True)

        # Replay support
        replay = st.session_state.pop("_replay", None)
        if replay and replay.get("page") == "연구 주제 생성":
            st.info(f"↩ 재사용: {replay['timestamp']} 작업")
            if replay.get("output", {}).get("topics"):
                st.session_state["topics"] = replay["output"]["topics"]

        col1, col2 = st.columns([2, 1])
        with col1:
            dataset = st.selectbox("데이터셋", ["KYRBS", "KNHANES", "KYRBS + KNHANES"])
            focus = st.text_input("연구 포커스", placeholder="예: 청소년 비만과 정신건강")
        with col2:
            n_topics = st.slider("생성할 주제 수", 1, 10, 5)
            use_evidence = st.checkbox("오픈 에비던스 검색 포함", value=True)

        page_context.update({"dataset": dataset, "focus": focus, "n_topics": n_topics})

        if st.button("🚀 주제 생성", type="primary"):
            if not focus:
                st.error("연구 포커스를 입력하세요.")
            else:
                with st.spinner(f"Claude가 {n_topics}개 주제를 생성 중..."):
                    try:
                        from src.research.research_pipeline import ResearchPipeline
                        rp = ResearchPipeline()
                        topics = rp.generate_topics(dataset_name=dataset, focus=focus, n_topics=n_topics,
                                                    reference_query=focus if use_evidence else None)
                        st.session_state["topics"] = topics
                        from datetime import datetime
                        rp_list = st.session_state.get("recent_projects", [])
                        rp_list.insert(0, {"title": focus, "updated": datetime.now().strftime("%Y.%m.%d %H:%M"), "status": "연구 설계 중"})
                        st.session_state["recent_projects"] = rp_list[:10]
                        _log("generate_topics", {"focus": focus, "n": n_topics}, f"{len(topics)}개 주제 생성: {focus}", {"topics": topics})
                        st.success(f"✅ {len(topics)}개 주제 생성 완료!")
                    except Exception as e:
                        st.error(f"오류: {e}")

        if "topics" in st.session_state:
            page_context["생성된_주제"] = [t.get("title","") for t in st.session_state["topics"]]
            st.divider()
            st.markdown("<h3 style='color:#e6edf3;'>생성된 주제 목록</h3>", unsafe_allow_html=True)
            for i, t in enumerate(st.session_state["topics"]):
                with st.expander(f"[{i+1}] {t.get('title','제목 없음')}", expanded=(i == 0)):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**노출변수:** {t.get('exposure','-')}")
                        st.markdown(f"**결과변수:** {t.get('outcome','-')}")
                    with c2:
                        st.markdown(f"**대상:** {t.get('population','-')}")
                        st.markdown(f"**설계:** {t.get('suggested_design','-')}")
                    st.markdown(f"**근거:** {t.get('rationale','-')}")
                    ca, cb = st.columns(2)
                    with ca:
                        if st.button("🔍 신규성 확인", key=f"_nov_{i}"):
                            st.session_state["selected_topic"] = t; _nav("신규성 확인")
                    with cb:
                        if st.button("📝 논문 작성", key=f"_wr_{i}"):
                            st.session_state["selected_topic"] = t; _nav("논문 작성")

        _show_history("연구 주제 생성")

    # ── 신규성 확인 ───────────────────────────────────────────────────
    elif page == "신규성 확인":
        st.markdown("<h2 style='color:#e6edf3;'>🔍 신규성 확인 (PubMed)</h2>", unsafe_allow_html=True)
        prev = st.session_state.get("selected_topic", {})
        title = st.text_input("연구 제목", value=prev.get("title", ""))
        col1, col2 = st.columns(2)
        with col1:
            exposure = st.text_input("노출변수", value=prev.get("exposure", ""))
            outcome = st.text_input("결과변수", value=prev.get("outcome", ""))
        with col2:
            population = st.text_input("대상 집단", value=prev.get("population", ""))

        page_context.update({"title": title, "exposure": exposure, "outcome": outcome, "population": population})

        if st.button("🔍 PubMed 신규성 확인", type="primary"):
            if not title:
                st.error("연구 제목을 입력하세요.")
            else:
                with st.spinner("PubMed 검색 + 규칙기반 유사도 분석 + Claude 평가 중..."):
                    try:
                        from src.research.novelty_checker import NoveltyChecker
                        result = NoveltyChecker().check(
                            topic=title, exposure=exposure,
                            outcome=outcome, population=population,
                        )
                        st.session_state["novelty_result"] = result
                        _log("check_novelty", {"title": title},
                             f"신규성 점수 {result.get('novelty_score',0)}/10: {title}", result)
                        page_context.update({
                            "novelty_score": result.get("novelty_score", 0),
                            "gap": result.get("gap_identified", ""),
                        })
                    except Exception as e:
                        st.error(f"오류: {e}")
                        import traceback; st.code(traceback.format_exc())

        if "novelty_result" in st.session_state:
            result = st.session_state["novelty_result"]
            score = result.get("novelty_score", 0)
            rule_score = result.get("rule_based_score", score)
            rec = result.get("recommendation", "")
            rec_color = "#22C55E" if rec == "proceed" else "#F59E0B" if rec == "modify" else "#EF4444"
            page_context["이전_신규성_결과"] = f"점수 {score}/10"

            st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)
            s1, s2, s3 = st.columns(3)
            with s1:
                emoji = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
                st.metric("신규성 점수 (LLM)", f"{emoji} {score}/10")
            with s2:
                st.metric("규칙기반 점수", f"{rule_score}/10")
            with s3:
                stats = result.get("similarity_stats", {})
                st.metric("유사 논문", f"{stats.get('total_papers', 0)}편 중 {stats.get('high_similarity_count', 0)}편")

            st.markdown(f"""
            <div style="background:#1A2540;border:1px solid #1F2A44;border-radius:10px;padding:14px 18px;margin:10px 0;">
                <span style="font-size:13px;font-weight:600;color:#94A3B8;">권고사항</span>
                <span style="margin-left:12px;padding:3px 12px;border-radius:20px;font-size:13px;
                             font-weight:700;background:{rec_color}22;color:{rec_color};">{rec.upper()}</span>
                <p style="margin:8px 0 0;color:#E5E7EB;font-size:13px;">{result.get('llm_justification','')}</p>
            </div>
            """, unsafe_allow_html=True)

            col_sim, col_diff = st.columns(2)
            with col_sim:
                similar_list = result.get("overall_similar_aspects", [])
                items_html = "".join(
                    f'<div style="font-size:12px;color:#E5E7EB;padding:3px 0;">• {s}</div>'
                    for s in similar_list
                ) or '<div style="font-size:12px;color:#64748B;">유사 측면 없음</div>'
                st.markdown(f"""
                <div style="background:#1F2A44;border-left:3px solid #F59E0B;border-radius:8px;padding:12px 14px;">
                    <div style="font-size:13px;font-weight:700;color:#F59E0B;margin-bottom:8px;">
                        ⚠ 기존 연구와 유사한 점 ({len(similar_list)})</div>
                    {items_html}
                </div>""", unsafe_allow_html=True)
            with col_diff:
                diff_list = result.get("overall_different_aspects", [])
                items_html2 = "".join(
                    f'<div style="font-size:12px;color:#E5E7EB;padding:3px 0;">• {d}</div>'
                    for d in diff_list
                ) or '<div style="font-size:12px;color:#64748B;">차별 측면 정보 없음</div>'
                st.markdown(f"""
                <div style="background:#1A2540;border-left:3px solid #22C55E;border-radius:8px;padding:12px 14px;">
                    <div style="font-size:13px;font-weight:700;color:#22C55E;margin-bottom:8px;">
                        ✓ 차별화 포인트 ({len(diff_list)})</div>
                    {items_html2}
                </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
            ga1, ga2 = st.columns(2)
            with ga1:
                st.markdown(f"**연구 공백:** {result.get('gap_identified', '-')}")
            with ga2:
                st.markdown(f"**차별화 전략:** {result.get('suggested_angle', '-')}")

            matrix = result.get("similarity_matrix", [])
            if matrix:
                st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
                with st.expander(f"📊 논문별 유사도 상세 ({len(matrix)}편)", expanded=False):
                    for p in matrix[:10]:
                        sim = p["overall_similarity"]
                        bar_color = "#EF4444" if sim >= 0.7 else "#F59E0B" if sim >= 0.5 else "#22C55E"
                        bar_pct = int(sim * 100)
                        sim_asp = ", ".join(a["label"] for a in p.get("similar_aspects", []))
                        diff_asp = ", ".join(a["label"] for a in p.get("different_aspects", []))
                        sim_row = f'<div style="font-size:11px;color:#F59E0B;margin-top:5px;">⚠ 유사: {sim_asp}</div>' if sim_asp else ""
                        diff_row = f'<div style="font-size:11px;color:#22C55E;margin-top:3px;">✓ 차별: {diff_asp}</div>' if diff_asp else ""
                        st.markdown(f"""
                        <div style="background:#121A2B;border:1px solid #1F2A44;border-radius:8px;
                                    padding:11px 14px;margin-bottom:7px;">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                                <span style="font-size:12px;font-weight:700;color:{bar_color};">{bar_pct}%</span>
                                <div style="flex:1;background:#1F2A44;border-radius:4px;height:6px;">
                                    <div style="width:{bar_pct}%;background:{bar_color};border-radius:4px;height:6px;"></div>
                                </div>
                                <span style="font-size:10px;color:#64748B;">{p.get('year','')}</span>
                            </div>
                            <div style="font-size:12px;font-weight:600;color:#E5E7EB;margin-bottom:4px;">
                                {p.get('paper_title','')[:100]}</div>
                            <div style="font-size:11px;color:#64748B;margin-bottom:3px;">{p.get('vancouver_ref') or p.get('journal','')[:80]}</div>
                            {sim_row}{diff_row}
                        </div>""", unsafe_allow_html=True)

        _show_history("신규성 확인")

    # ── 논문 설계 & 타당성 ────────────────────────────────────────────
    elif page == "논문 설계 & 타당성":
        st.markdown("<h2 style='color:#e6edf3;'>🟢 논문 설계 & 타당성 검증</h2>", unsafe_allow_html=True)
        prev = st.session_state.get("selected_topic", {})
        topic_json = st.text_area("주제 JSON",
            value=json.dumps(prev, ensure_ascii=False, indent=2) if prev else '{"title":"","exposure":"","outcome":"","population":""}',
            height=180)
        dataset = st.selectbox("데이터셋", ["KYRBS", "KNHANES", "KYRBS + KNHANES"])
        page_context["topic_json"] = topic_json
        if st.button("✅ 타당성 검증", type="primary"):
            try:
                topic = json.loads(topic_json)
                with st.spinner("분석 중..."):
                    from src.research.research_pipeline import ResearchPipeline
                    result = ResearchPipeline().validate_feasibility(topic, dataset)
                    feasible = result.get("is_feasible")
                    st.metric("타당성", f"{'✅ 가능' if feasible else '❌ 어려움'} (신뢰도: {result.get('confidence','?')})")
                    c1, c2 = st.columns(2)
                    with c1:
                        avail = result.get("available_variables", [])
                        st.markdown(f"**사용 가능 변수 ({len(avail)}개)**")
                        for v in avail: st.markdown(f"  ✅ `{v}`")
                    with c2:
                        missing = result.get("missing_variables", [])
                        st.markdown(f"**부족한 변수 ({len(missing)}개)**")
                        for v in missing: st.markdown(f"  ❌ `{v}`")
                    st.markdown(f"**판정:** {result.get('verdict','-')}")
                    _log("validate_feasibility", {"topic": topic}, f"타당성: {'가능' if feasible else '어려움'}", result)
            except Exception as e:
                st.error(f"오류: {e}")
        _show_history("논문 설계 & 타당성")

    # ── 데이터 분석 ───────────────────────────────────────────────────
    elif page == "데이터 분석":
        st.markdown("<h2 style='color:#e6edf3;'>🔵 데이터 분석</h2>", unsafe_allow_html=True)
        tab_lib, tab_run = st.tabs(["📚 데이터셋 라이브러리", "📊 통계 분석 실행"])

        with tab_lib:
            try:
                from src.library.dataset_library import DatasetLibrary
                lib = DatasetLibrary()
                datasets = lib.list_datasets()
                if not datasets:
                    st.warning("등록된 데이터셋이 없습니다.")
                else:
                    sel_ds = st.selectbox("데이터셋 선택", datasets)
                    ds = lib.get_dataset(sel_ds)
                    c1, c2, c3 = st.columns(3)
                    c1.metric("변수 수", len(ds.get("variables", {})))
                    c2.metric("교란변수", len(ds.get("common_confounders", [])))
                    c3.metric("분석 주의사항", len(ds.get("analysis_notes", [])))
                    st.markdown(f"**설명:** {ds.get('description','-')}")
                    st.divider()
                    search = st.text_input("변수명 검색", placeholder="예: bmi, 흡연")
                    variables = ds.get("variables", {})
                    if search:
                        variables = {k: v for k, v in variables.items()
                                     if search.lower() in k.lower() or search.lower() in v.get("label","").lower()}
                    st.caption(f"{len(variables)}개 변수")
                    for vn, vi in variables.items():
                        with st.expander(f"`{vn}` — {vi.get('label','')} ({vi.get('type','')})", expanded=False):
                            a, b = st.columns(2)
                            with a:
                                st.markdown(f"**타입:** {vi.get('type','-')}")
                                st.markdown(f"**단위:** {vi.get('unit','-') or '-'}")
                            with b:
                                st.markdown(f"**처리:** {vi.get('processing','-')}")
                    page_context["데이터셋"] = sel_ds
            except Exception as e:
                st.error(f"오류: {e}")

        with tab_run:
            st.markdown("CSV/Excel 파일을 업로드하면 실제 통계 분석을 수행합니다.")
            uploaded_data = st.file_uploader("데이터 파일 업로드 (CSV / Excel)", type=["csv", "xlsx", "xls"])
            if uploaded_data:
                try:
                    import pandas as pd
                    if uploaded_data.name.endswith(".csv"):
                        df = pd.read_csv(uploaded_data)
                    else:
                        df = pd.read_excel(uploaded_data)
                    st.success(f"✅ {df.shape[0]:,}행 × {df.shape[1]}열 로드 완료")
                    st.dataframe(df.head(5), use_container_width=True)
                    st.session_state["analysis_df"] = df
                except Exception as e:
                    st.error(f"파일 로드 오류: {e}")

            df = st.session_state.get("analysis_df")
            if df is not None:
                cols = list(df.columns)
                st.divider()
                analysis_type = st.selectbox("분석 유형", [
                    "기술통계 (Descriptive Stats)",
                    "독립표본 t검정 (Independent t-test)",
                    "카이제곱 검정 (Chi-square)",
                    "일원분산분석 (One-way ANOVA)",
                    "피어슨 상관 (Pearson Correlation)",
                    "로지스틱 회귀 (Logistic Regression)",
                    "선형 회귀 (Linear Regression)",
                ])

                if analysis_type == "기술통계 (Descriptive Stats)":
                    sel_cols = st.multiselect("분석할 변수", cols, default=cols[:5])
                    if st.button("▶ 실행", type="primary") and sel_cols:
                        from src.statistics.medical_stats import MedicalStatistics
                        result_df = MedicalStatistics.descriptive_stats(df[sel_cols])
                        st.dataframe(result_df, use_container_width=True)
                        _log("stats_descriptive", {"cols": sel_cols}, f"기술통계: {sel_cols}")

                elif analysis_type == "독립표본 t검정 (Independent t-test)":
                    val_col = st.selectbox("연속형 변수", cols)
                    grp_col = st.selectbox("그룹 변수 (2개 그룹)", cols)
                    if st.button("▶ 실행", type="primary"):
                        from src.statistics.medical_stats import MedicalStatistics
                        res = MedicalStatistics.independent_t_test(df, val_col, grp_col)
                        st.json(res)
                        _log("stats_ttest", {"val": val_col, "grp": grp_col}, f"t-test: {val_col} by {grp_col}")

                elif analysis_type == "카이제곱 검정 (Chi-square)":
                    var1 = st.selectbox("변수 1", cols)
                    var2 = st.selectbox("변수 2", cols, index=min(1, len(cols)-1))
                    if st.button("▶ 실행", type="primary"):
                        from src.statistics.medical_stats import MedicalStatistics
                        res = MedicalStatistics.chi_square_test(df, var1, var2)
                        st.json(res)
                        _log("stats_chi2", {"var1": var1, "var2": var2}, f"chi2: {var1} vs {var2}")

                elif analysis_type == "일원분산분석 (One-way ANOVA)":
                    val_col = st.selectbox("연속형 변수", cols)
                    grp_col = st.selectbox("그룹 변수", cols)
                    if st.button("▶ 실행", type="primary"):
                        from src.statistics.medical_stats import MedicalStatistics
                        res = MedicalStatistics.one_way_anova(df, val_col, grp_col)
                        st.json(res)
                        _log("stats_anova", {"val": val_col, "grp": grp_col}, f"ANOVA: {val_col} by {grp_col}")

                elif analysis_type == "피어슨 상관 (Pearson Correlation)":
                    sel_cols = st.multiselect("변수 선택 (2개 이상)", cols, default=cols[:4])
                    if st.button("▶ 실행", type="primary") and len(sel_cols) >= 2:
                        import pandas as pd
                        corr = df[sel_cols].corr()
                        st.dataframe(corr.style.background_gradient(cmap="coolwarm"), use_container_width=True)
                        _log("stats_corr", {"cols": sel_cols}, f"상관분석: {sel_cols}")

                elif analysis_type == "로지스틱 회귀 (Logistic Regression)":
                    outcome = st.selectbox("결과변수 (이진)", cols)
                    predictors = st.multiselect("예측변수", [c for c in cols if c != outcome])
                    if st.button("▶ 실행", type="primary") and predictors:
                        from src.statistics.medical_stats import MedicalStatistics
                        res = MedicalStatistics.logistic_regression(df, outcome, predictors)
                        st.dataframe(res, use_container_width=True)
                        _log("stats_logistic", {"outcome": outcome, "predictors": predictors}, f"로지스틱: {outcome}")

                elif analysis_type == "선형 회귀 (Linear Regression)":
                    outcome = st.selectbox("결과변수", cols)
                    predictors = st.multiselect("예측변수", [c for c in cols if c != outcome])
                    if st.button("▶ 실행", type="primary") and predictors:
                        from src.statistics.medical_stats import MedicalStatistics
                        res = MedicalStatistics.linear_regression(df, outcome, predictors)
                        st.json(res)
                        _log("stats_linear", {"outcome": outcome, "predictors": predictors}, f"선형회귀: {outcome}")

    # ── 논문 작성 ─────────────────────────────────────────────────────
    elif page == "논문 작성":
        st.markdown("<h2 style='color:#e6edf3;'>📝 조유선 스타일 논문 작성</h2>", unsafe_allow_html=True)
        st.info("조유선 교수 논문 스타일 시드를 기반으로 논문 초안을 생성합니다.")
        prev = st.session_state.get("selected_topic", {})
        c1, c2 = st.columns(2)
        with c1:
            topic_title = st.text_input("연구 제목", value=prev.get("title", ""))
            journal = st.text_input("목표 저널", placeholder="예: Nutrients, IJERPH")
            design = st.selectbox("연구 설계", ["Cross-sectional", "Cohort", "Case-control", "RCT"])
        with c2:
            dataset_name = st.text_input("데이터셋", value="KYRBS 2025 (제21차 청소년건강행태조사)")
            sample_size = st.text_input("표본 수", placeholder="예: 54,633")
            survey_year = st.text_input("조사 연도", value="2025")
        results_text = st.text_area("주요 결과 (통계값 포함)", placeholder="예: 스마트폰 주중 4시간 이상 사용군에서 수면 부족 OR=2.34...", height=120)
        section = st.selectbox("작성할 섹션", ["전체 논문", "Abstract", "Introduction", "Methods", "Results", "Discussion"])
        page_context.update({"title": topic_title, "journal": journal, "design": design, "dataset": dataset_name, "results_summary": results_text[:200]})

        if st.button("✍️ 논문 작성 시작", type="primary"):
            if not topic_title or not results_text:
                st.error("연구 제목과 주요 결과를 입력하세요.")
            else:
                with st.spinner("조유선 스타일로 논문 작성 중... (1~2분 소요)"):
                    try:
                        from src.research.research_pipeline import ResearchPipeline
                        topic = {"title": topic_title, "exposure": prev.get("exposure",""), "outcome": prev.get("outcome",""), "population": prev.get("population","")}
                        study_info = {"dataset": dataset_name, "design": design, "sample_size": sample_size, "survey_year": survey_year, "journal": journal}
                        results = {"summary": results_text}
                        rp = ResearchPipeline()
                        if section == "전체 논문":
                            draft = rp.write_paper(topic, study_info, results)
                        else:
                            from src.research.paper_writer import PaperWriter
                            from src.profile.author_profile import AuthorProfile
                            from src.library.methods_library import MethodsLibrary
                            from src.library.dataset_library import DatasetLibrary as DL
                            from src.rag.pipeline import RAGPipeline
                            writer = PaperWriter(AuthorProfile("Yoosun Cho"), MethodsLibrary(), DL(), RAGPipeline())
                            fn = {"Abstract": writer.write_abstract, "Introduction": writer.write_introduction,
                                  "Methods": writer.write_methods, "Results": writer.write_results, "Discussion": writer.write_discussion}[section]
                            draft = fn(topic=topic_title, study_info=study_info, results=results)
                        st.session_state["draft"] = draft
                        from datetime import datetime
                        rp_list = st.session_state.get("recent_projects", [])
                        rp_list.insert(0, {"title": topic_title, "updated": datetime.now().strftime("%Y.%m.%d %H:%M"), "status": "논문 작성 중"})
                        st.session_state["recent_projects"] = rp_list[:10]
                        _log("write_paper", {"title": topic_title, "section": section}, f"{section} 작성 완료: {topic_title}", {"draft_len": len(draft)})
                        st.success("✅ 논문 작성 완료!")
                    except Exception as e:
                        st.error(f"오류: {e}"); import traceback; st.code(traceback.format_exc())

        if "draft" in st.session_state:
            page_context["현재_초안_길이"] = f"{len(st.session_state['draft'])}자"
            st.divider()
            st.markdown("<h3 style='color:#e6edf3;'>생성된 논문 초안</h3>", unsafe_allow_html=True)
            draft_val = st.text_area("내용", value=st.session_state["draft"], height=500)
            if draft_val != st.session_state["draft"]:
                st.session_state["draft"] = draft_val
            st.download_button("📥 TXT 다운로드", data=st.session_state["draft"].encode("utf-8"),
                               file_name=f"draft_{topic_title[:30]}.txt", mime="text/plain")
        _show_history("논문 작성")

    # ── Agent Q&A ─────────────────────────────────────────────────────
    elif page == "Agent Q&A":
        st.markdown("<h2 style='color:#e6edf3;'>🤖 Agent Q&A</h2>", unsafe_allow_html=True)
        st.info("학습된 논문과 데이터베이스를 기반으로 질문에 답합니다.")
        if "messages" not in st.session_state:
            st.session_state.messages = []
        for msg in st.session_state.messages:
            with st.chat_message(msg["role"]): st.markdown(msg["content"])
        if prompt := st.chat_input("질문을 입력하세요..."):
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"): st.markdown(prompt)
            with st.chat_message("assistant"):
                with st.spinner("답변 생성 중..."):
                    try:
                        from src.agent.medical_agent import MedicalAgent
                        response = MedicalAgent().ask(prompt)
                        answer = response.get("answer", response.get("raw", str(response)))
                        st.markdown(answer)
                        st.session_state.messages.append({"role": "assistant", "content": answer})
                        _log("agent_qa", {"prompt": prompt}, answer[:100])
                    except Exception as e:
                        err = f"오류: {e}"; st.error(err)
                        st.session_state.messages.append({"role": "assistant", "content": err})

    # ── Notebook 에디터 ───────────────────────────────────────────────
    elif page == "Notebook 에디터":
        st.markdown("<h2 style='color:#e6edf3;'>☁️ NotebookLM Research Hub</h2>", unsafe_allow_html=True)
        try:
            from src.storage.manager import StorageManager
            sm = StorageManager()
            stat = sm.status()
            c1, c2, c3 = st.columns(3)
            nlm_color = "🟢" if stat["notebooklm"] == "online" else "🔴"
            c1.metric("NotebookLM", f"{nlm_color} {stat['notebooklm']}")
            c2.metric("로컬 DB 청크", f"{stat['local_chromadb_chunks']:,}개")
            c3.metric("활성 스토리지", stat["active_storage"])
            st.divider()
        except Exception as e:
            st.error(f"초기화 오류: {e}"); st.stop()

        tab1, tab2, tab3 = st.tabs(["📄 논문 추가", "🔎 노트북 쿼리", "📋 노트북 목록"])
        with tab1:
            topic_input = st.text_input("연구 주제", key="nlm_topic")
            search_query = st.text_input("PubMed 검색어", key="nlm_q")
            n_papers = st.slider("최대 논문 수", 3, 20, 10)
            if st.button("🔍 검색 후 동기화", type="primary", disabled=not (topic_input and search_query)):
                with st.spinner(f"PubMed 검색 중..."):
                    try:
                        from src.research.novelty_checker import NoveltyChecker
                        papers = NoveltyChecker().search_papers(search_query, max_results=n_papers)
                        if papers:
                            st.success(f"✅ {len(papers)}편 검색")
                            result = sm.store_papers(papers, topic=topic_input)
                            st.success(f"NotebookLM: {result['nlm']}편 / 로컬: {result['local']}편")
                            _log("nlm_sync", {"query": search_query}, f"{len(papers)}편 동기화: {topic_input}")
                        else:
                            st.warning("검색 결과 없음")
                    except Exception as e:
                        st.error(f"오류: {e}")
        with tab2:
            notebooks = sm.get_topic_notebooks()
            if not notebooks:
                st.info("동기화된 주제 없음.")
            else:
                sel = st.selectbox("주제", [n["topic"] for n in notebooks])
                mode = st.radio("모드", ["자유 질문", "전방위 분석"], horizontal=True)
                if mode == "자유 질문":
                    q = st.text_area("질문", height=80)
                    if st.button("🔎 실행", type="primary", disabled=not q):
                        res = sm.search(q, topic=sel)
                        st.markdown(f"**출처:** `{res['source']}`")
                        st.markdown(res["answer"])
                else:
                    if st.button("🧪 전방위 분석", type="primary"):
                        analysis = sm.analyze_topic(sel)
                        if "error" in analysis: st.error(analysis["error"])
                        else:
                            for k, lbl in [("gap","연구 공백"),("methods","방법론"),("exposure_outcome","노출·결과"),("novelty_angle","신규 각도"),("key_findings","핵심 발견")]:
                                with st.expander(f"**{lbl}**", expanded=(k=="gap")): st.markdown(analysis.get(k,"-"))
        with tab3:
            notebooks = sm.get_topic_notebooks()
            if not notebooks: st.info("생성된 노트북 없음")
            else:
                for nb in notebooks:
                    url = f"https://notebooklm.google.com/notebook/{nb['notebook_id']}" if nb.get("notebook_id") else "#"
                    st.markdown(f"- **{nb['topic']}** — [열기]({url})")
        _show_history("Notebook 에디터")

    # ── 논문 업로드 & 인제스트 ────────────────────────────────────────
    elif page == "논문 업로드 & 인제스트":
        st.markdown("<h2 style='color:#e6edf3;'>📥 논문 업로드 & 인제스트</h2>", unsafe_allow_html=True)
        tab_pdf, tab_pm, tab_txt = st.tabs(["PDF 파일 업로드", "PubMed 검색 학습", "텍스트 직접 입력"])
        with tab_pdf:
            uploaded = st.file_uploader("PDF 파일 선택", type=["pdf"], accept_multiple_files=True)
            topic_tag = st.text_input("주제 태그", placeholder="예: 청소년 비만")
            if st.button("📚 인제스트 시작", type="primary", disabled=not uploaded):
                from src.ingestion.pdf_reader import PDFReader
                from src.ingestion.chunker import TextChunker
                from src.vectordb.store import get_vector_store
                import tempfile
                reader = PDFReader(); chunker = TextChunker(); store = get_vector_store(); total = 0
                for uf in uploaded:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        tmp.write(uf.read()); tmp_path = tmp.name
                    try:
                        with st.spinner(f"처리 중: {uf.name}"):
                            pages = reader.read(tmp_path)
                            text = " ".join(p.get("text","") for p in pages)
                            chunks = chunker.chunk(text, metadata={"filename": uf.name, "source": "pdf_upload", "topic": topic_tag})
                            added = store.add_chunks(chunks); total += added
                            st.success(f"✅ {uf.name} → {added}개 청크")
                    except Exception as e: st.error(f"❌ {uf.name}: {e}")
                    finally: os.unlink(tmp_path)
                if total:
                    st.balloons(); st.success(f"총 {total}개 청크!")
                    _log("pdf_ingest", {"files": [f.name for f in uploaded]}, f"PDF {len(uploaded)}개 → {total}청크")
        with tab_pm:
            pm_q = st.text_input("검색어", placeholder="adolescent obesity sleep Korea")
            pm_n = st.slider("최대 논문 수", 5, 50, 20)
            pm_topic = st.text_input("주제 태그")
            also_nlm = st.checkbox("NotebookLM에도 동기화", value=True)
            if st.button("🔍 검색 후 학습", type="primary", disabled=not pm_q):
                with st.spinner("PubMed 검색 중..."):
                    try:
                        from src.research.novelty_checker import NoveltyChecker
                        from src.vectordb.store import get_vector_store
                        from src.ingestion.chunker import TextChunker
                        from src.notebooklm.paper_sync import PaperSync
                        papers = NoveltyChecker().search_papers(pm_q, max_results=pm_n)
                        if papers:
                            store = get_vector_store(); chunker = TextChunker(); total = 0
                            for p in papers:
                                chunks = chunker.chunk(PaperSync._format_paper_text(p),
                                    metadata={"filename": p.get("title","")[:80], "source": f"pubmed:{p.get('pmid','')}", "topic": pm_topic})
                                total += store.add_chunks(chunks)
                            if also_nlm:
                                from src.storage.manager import StorageManager
                                nlm_r = StorageManager().store_papers(papers, topic=pm_topic)
                                st.info(f"NotebookLM: {nlm_r['nlm']}편")
                            st.success(f"✅ {len(papers)}편 / {total}청크 학습 완료")
                            _log("pubmed_ingest", {"query": pm_q}, f"{len(papers)}편 학습: {pm_topic}")
                        else: st.warning("결과 없음")
                    except Exception as e: st.error(f"오류: {e}"); import traceback; st.code(traceback.format_exc())
        with tab_txt:
            txt_title = st.text_input("제목 / 출처")
            txt_content = st.text_area("내용", height=250)
            txt_topic = st.text_input("주제 태그", key="txt_topic")
            if st.button("💾 저장", type="primary", disabled=not (txt_title and txt_content)):
                try:
                    from src.ingestion.chunker import TextChunker
                    from src.vectordb.store import get_vector_store
                    added = get_vector_store().add_chunks(TextChunker().chunk(txt_content, metadata={"filename": txt_title[:80], "source": "manual_input", "topic": txt_topic}))
                    st.success(f"✅ {added}개 청크 저장")
                    _log("text_ingest", {"title": txt_title}, f"텍스트 입력 → {added}청크")
                except Exception as e: st.error(f"오류: {e}")
        _show_history("논문 업로드 & 인제스트")

    # ── 지식베이스 관리 ───────────────────────────────────────────────
    elif page == "지식베이스 관리":
        st.markdown("<h2 style='color:#e6edf3;'>🧠 지식베이스 현황</h2>", unsafe_allow_html=True)
        db_type = "Supabase (클라우드)" if os.environ.get("SUPABASE_DB_URL") else "ChromaDB (로컬)"
        try:
            from src.vectordb.store import get_vector_store
            store = get_vector_store()
            c1, c2, c3 = st.columns(3)
            c1.metric("DB 유형", db_type)
            total_chunks = store.count()
            c2.metric("총 청크 수", f"{total_chunks:,}개")
            sources = store.list_sources()
            c3.metric("학습된 문서 수", f"{len(sources)}개")
            page_context.update({"db_type": db_type, "total_chunks": total_chunks, "documents": len(sources)})
            st.divider()
            if sources:
                search_src = st.text_input("문서명 검색")
                filtered = [s for s in sources if not search_src or search_src.lower() in s.lower()]
                for s in filtered: st.markdown(f"- `{s}`")
            else:
                st.info("아직 학습된 문서 없음.")
            st.divider()
            st.markdown("<h3 style='color:#e6edf3;'>의미 검색 테스트</h3>", unsafe_allow_html=True)
            test_q = st.text_input("검색어", placeholder="예: 청소년 비만 위험요인")
            if test_q:
                hits = store.search(test_q, n_results=5)
                for i, h in enumerate(hits, 1):
                    with st.expander(f"[{i}] {h.get('metadata',{}).get('filename','?')} (유사도: {h.get('score',0):.3f})"):
                        st.text(h["text"][:500])
        except Exception as e:
            st.error(f"DB 연결 오류: {e}")
        st.divider()
        try:
            from src.storage.manager import StorageManager
            sm = StorageManager()
            stat = sm.status()
            nlm_color = "🟢" if stat["notebooklm"] == "online" else "🔴"
            st.metric("NotebookLM", f"{nlm_color} {stat['notebooklm']}")
            notebooks = sm.get_topic_notebooks()
            if notebooks:
                st.markdown(f"**동기화된 주제**: {len(notebooks)}개")
                for nb in notebooks: st.markdown(f"- {nb['topic']}")
        except Exception as e:
            st.error(f"NotebookLM 오류: {e}")

    # ── 자동 학습 루프 ────────────────────────────────────────────────
    elif page == "자동 학습 루프":
        st.markdown("<h2 style='color:#e6edf3;'>🔄 자동 학습 루프</h2>", unsafe_allow_html=True)
        LOOP_CFG = Path("data/auto_learn_config.json")
        def _lc(): return json.loads(LOOP_CFG.read_text(encoding="utf-8")) if LOOP_CFG.exists() else {"jobs": []}
        def _sc(cfg): LOOP_CFG.parent.mkdir(parents=True, exist_ok=True); LOOP_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        cfg = _lc()
        page_context["등록된_키워드"] = [j["keyword"] for j in cfg["jobs"]]
        st.markdown("<h3 style='color:#e6edf3;'>키워드 등록</h3>", unsafe_allow_html=True)
        with st.form("add_job"):
            c1, c2, c3 = st.columns([3, 2, 1])
            kw = c1.text_input("PubMed 검색어")
            topic = c2.text_input("주제 태그")
            n_max = c3.number_input("최대", 5, 50, 20)
            if st.form_submit_button("➕ 추가") and kw and topic:
                cfg["jobs"].append({"keyword": kw, "topic": topic, "max": int(n_max), "last_run": None})
                _sc(cfg); st.success(f"✅ '{kw}' 등록됨"); st.rerun()
        st.markdown("<h3 style='color:#e6edf3;'>등록된 키워드</h3>", unsafe_allow_html=True)
        if not cfg["jobs"]: st.info("등록된 키워드 없음.")
        else:
            for i, job in enumerate(cfg["jobs"]):
                c1, c2, c3 = st.columns([4, 2, 1])
                c1.markdown(f"**{job['keyword']}** `{job['topic']}` (최대 {job['max']}편)")
                c2.caption(f"마지막 실행: {job.get('last_run') or '미실행'}")
                if c3.button("삭제", key=f"_del_{i}"):
                    cfg["jobs"].pop(i); _sc(cfg); st.rerun()
        st.divider()
        if cfg["jobs"] and st.button("▶️ 전체 키워드 지금 실행", type="primary"):
            from src.research.novelty_checker import NoveltyChecker
            from src.storage.manager import StorageManager
            from datetime import datetime
            checker = NoveltyChecker(); sm = StorageManager(); total = 0
            for job in cfg["jobs"]:
                with st.spinner(f"수집 중: {job['keyword']}"):
                    try:
                        papers = checker.search_papers(job["keyword"], max_results=job["max"])
                        if papers:
                            r = sm.store_papers(papers, topic=job["topic"]); total += len(papers)
                            st.success(f"✅ {job['keyword']}: {len(papers)}편")
                        else: st.warning(f"'{job['keyword']}': 결과 없음")
                        job["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                    except Exception as e: st.error(f"'{job['keyword']}' 오류: {e}")
            _sc(cfg); _log("auto_learn_run", {"jobs": len(cfg["jobs"])}, f"자동학습 {total}편 완료")
            st.success(f"✅ 완료: 총 {total}편")
        st.divider()
        st.info("Streamlit Cloud: 백그라운드 스케줄러 미지원.\n\n**로컬:** `python run_auto_learn.py` → Windows 작업 스케줄러 등록")
        _show_history("자동 학습 루프")

    else:
        st.info(f"페이지를 찾을 수 없습니다: {page}")

# ══════════════════════════════════════════════════════════════════════
# AI PANEL (right column)
# ══════════════════════════════════════════════════════════════════════
with ai_col:
    st.markdown('<div class="ai-panel-wrap">', unsafe_allow_html=True)
    from app.ai_panel import render_ai_panel
    render_ai_panel(page, page_context)
    st.markdown('</div>', unsafe_allow_html=True)
