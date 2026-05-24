"""Medical-Agent Streamlit UI — Dark Theme + AI Panel + Activity History"""

import sys, os, io, re
# Windows CP949 → UTF-8 강제 (한글 로그 깨짐 방지)
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    try: sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception: pass
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    try: sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)
    except Exception: pass
os.environ['PYTHONIOENCODING'] = 'utf-8'
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
:root{
    --bg:#080E1C;--bg2:#0A1528;--bg3:#0D1B30;--bg4:#0F1E38;
    --border:rgba(56,98,180,0.18);--t1:#E5E7EB;--t2:#94A3B8;--t3:#64748B;
    --accent:#3B82F6;--accent2:#6366F1;--green:#22C55E;--blue:#3B82F6;
    --warning:#F59E0B;--danger:#EF4444;
}
#MainMenu,header,footer,.stDeployButton{visibility:hidden;display:none;}
.stApp,[data-testid="stAppViewContainer"]{background:var(--bg)!important;}
[data-testid="stSidebar"]{background:var(--bg2)!important;border-right:1px solid var(--border)!important;}
[data-testid="stSidebar"]>div:first-child{padding:0!important;}
.main .block-container{padding:1.5rem 2rem!important;max-width:100%!important;}

[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:2px!important;}
[data-testid="stSidebar"] [data-testid="stButton"]{margin:0!important;padding:0!important;}
[data-testid="stSidebar"] .stButton>button{
    background:transparent!important;border:none!important;border-left:3px solid transparent!important;
    color:var(--t2)!important;text-align:left!important;padding:4px 12px!important;width:100%!important;
    border-radius:0 6px 6px 0!important;font-size:13px!important;transition:all .15s!important;
    box-shadow:none!important;margin:0!important;justify-content:flex-start!important;
}
[data-testid="stSidebar"] .stButton>button:hover{
    background:rgba(59,130,246,.08)!important;color:var(--t1)!important;
    border-left:3px solid rgba(59,130,246,0.35)!important;
}
[data-testid="stSidebar"] .stButton>button:focus{box-shadow:none!important;}
.nav-active [data-testid="stSidebar"] .stButton>button{
    background:rgba(59,130,246,.15)!important;color:var(--t1)!important;
    font-weight:600!important;border-left:3px solid #3B82F6!important;
}
.nav-section{font-size:10px;font-weight:700;color:var(--t3);text-transform:uppercase;letter-spacing:.12em;padding:8px 16px 2px;}
.sidebar-logo{padding:12px 14px 10px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.sidebar-profile{padding:12px 14px;border-top:1px solid var(--border);display:flex;align-items:center;gap:10px;}
.s-avatar{width:32px;height:32px;border-radius:50%;background:linear-gradient(135deg,#1D4ED8,#6366F1);display:flex;align-items:center;justify-content:center;font-weight:700;font-size:13px;color:white;flex-shrink:0;}
.s-name{font-size:13px;font-weight:600;color:var(--t1);}
.s-email{font-size:11px;color:var(--t3);}
.logo-icon{width:34px;height:34px;border-radius:9px;background:linear-gradient(135deg,#1D4ED8,#4F46E5);display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0;box-shadow:0 2px 10px rgba(29,78,216,0.45);}

.card{background:rgba(13,27,48,0.85);border:1px solid var(--border);border-radius:14px;padding:20px;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);}
.pipeline-step{background:rgba(13,27,48,0.85);border:1px solid var(--border);border-radius:12px;padding:20px;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);}
.pipeline-card{background:rgba(13,27,48,0.85);border:1px solid var(--border);border-radius:14px;padding:20px;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);height:100%;}

.ic-circle{width:42px;height:42px;border-radius:12px;display:flex;align-items:center;justify-content:center;font-size:19px;font-weight:800;color:white;flex-shrink:0;margin-bottom:12px;}
.ic-blue{background:linear-gradient(135deg,#1D4ED8,#3B82F6);box-shadow:0 4px 12px rgba(29,78,216,0.4);}
.ic-indigo{background:linear-gradient(135deg,#4338CA,#6366F1);box-shadow:0 4px 12px rgba(67,56,202,0.4);}
.ic-purple{background:linear-gradient(135deg,#6D28D9,#8B5CF6);box-shadow:0 4px 12px rgba(109,40,217,0.4);}
.ic-green{background:linear-gradient(135deg,#065F46,#10B981);box-shadow:0 4px 12px rgba(16,185,129,0.3);}
.ic-orange{background:linear-gradient(135deg,#B45309,#F59E0B);box-shadow:0 4px 12px rgba(245,158,11,0.3);}
.ic-sm{width:34px;height:34px;border-radius:9px;font-size:15px;margin-bottom:0;flex-shrink:0;}

.step-n{font-size:10px;color:#60A5FA;font-weight:700;letter-spacing:.08em;text-transform:uppercase;margin-bottom:6px;}
.step-t{font-size:15px;font-weight:700;color:var(--t1);margin-bottom:5px;}
.step-d{font-size:12px;color:var(--t2);line-height:1.55;}

.kb-item{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:10px;background:rgba(13,27,48,0.6);border:1px solid var(--border);margin-bottom:8px;}
.kb-badge{background:rgba(34,197,94,0.12);color:#4ADE80;font-size:11px;font-weight:700;padding:3px 10px;border-radius:20px;margin-left:auto;border:1px solid rgba(34,197,94,0.28);white-space:nowrap;}

.qs-row{display:flex;align-items:center;gap:12px;padding:11px 14px;border-radius:10px;background:rgba(13,27,48,0.55);border:1px solid var(--border);margin-bottom:8px;transition:background .15s;}
.qs-row:hover{background:rgba(37,99,235,0.10);border-color:rgba(59,130,246,0.3);}
.qs-title{font-size:13px;font-weight:600;color:var(--t1);}
.qs-desc{font-size:11px;color:var(--t3);margin-top:1px;}
.qs-arrow{margin-left:auto;color:var(--t3);font-size:14px;}
/* Quick-start wide action buttons */
.main .block-container [data-testid="stColumn"] .stButton>button:not([kind="primary"]){
    background:rgba(13,27,48,0.55)!important;border:1px solid var(--border)!important;
    color:var(--t1)!important;text-align:left!important;justify-content:flex-start!important;
    padding:11px 14px!important;border-radius:10px!important;margin-bottom:4px!important;
    font-size:13px!important;transition:background .15s,border-color .15s!important;
}
.main .block-container [data-testid="stColumn"] .stButton>button:not([kind="primary"]):hover{
    background:rgba(37,99,235,0.12)!important;border-color:rgba(59,130,246,0.35)!important;
}

.proj-row{display:flex;align-items:center;padding:13px 0;border-bottom:1px solid var(--border);gap:12px;}
.proj-badge{font-size:11px;padding:3px 10px;border-radius:20px;margin-left:auto;flex-shrink:0;font-weight:600;}

.history-item{padding:10px 12px;border-radius:8px;background:rgba(13,27,48,0.6);border:1px solid var(--border);margin-bottom:6px;}
.history-ts{font-size:10px;color:var(--t3);}
.history-action{font-size:12px;color:var(--t2);}
.history-summary{font-size:13px;color:var(--t1);font-weight:500;}

.ai-panel-wrap{background:rgba(10,21,40,0.9);border:1px solid var(--border);border-radius:14px;padding:14px;height:100%;-webkit-backdrop-filter:blur(12px);backdrop-filter:blur(12px);}

[data-testid="stMetric"]{background:rgba(13,27,48,0.85)!important;border:1px solid var(--border)!important;border-radius:12px!important;padding:16px!important;-webkit-backdrop-filter:blur(8px)!important;backdrop-filter:blur(8px)!important;}
[data-testid="stMetricLabel"]{color:var(--t2)!important;font-size:12px!important;}
[data-testid="stMetricValue"]{color:var(--t1)!important;}
h1,h2,h3,h4,p,label{color:var(--t1)!important;}
.stMarkdown p{color:var(--t1)!important;}
input,textarea,[data-testid="stTextInput"] input,[data-testid="stTextArea"] textarea{background:rgba(13,27,48,0.9)!important;border-color:var(--border)!important;color:var(--t1)!important;}
.stButton>button[kind="primary"]{background:linear-gradient(135deg,#2563EB,#6366F1)!important;color:white!important;border:none!important;border-radius:8px!important;font-weight:600!important;box-shadow:0 4px 16px rgba(37,99,235,0.32)!important;}
hr,[data-testid="stDivider"]{border-color:var(--border)!important;}
[data-testid="stExpander"]{background:rgba(13,27,48,0.85)!important;border:1px solid var(--border)!important;border-radius:10px!important;}
[data-testid="stSelectbox"]>div>div{background:rgba(13,27,48,0.9)!important;border-color:var(--border)!important;color:var(--t1)!important;}
[data-testid="stTabs"] [role="tablist"]{border-bottom:1px solid var(--border)!important;}
[data-testid="stTabs"] button[role="tab"]{color:var(--t2)!important;}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"]{color:#60A5FA!important;border-bottom:2px solid #3B82F6!important;}
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════
# Cached resource factories — loaded once per server lifetime
# ══════════════════════════════════════════════════════════════════════
@st.cache_resource
def _get_cached_store():
    from src.vectordb.store import get_vector_store
    return get_vector_store()

@st.cache_resource
def _get_cached_novelty_checker():
    from src.research.novelty_checker import NoveltyChecker
    return NoveltyChecker()

@st.cache_resource
def _get_cached_medical_agent():
    from src.agent.medical_agent import MedicalAgent
    return MedicalAgent()

@st.cache_resource
def _get_cached_rag_pipeline():
    from src.rag.pipeline import RAGPipeline
    return RAGPipeline()

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
        <p style="color:#8b949e;margin-top:.4rem;font-size:.85rem;">의학 논문 자동 생산 파이프라인</p>
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

# ══════════════════════════════════════════════════════════════════════
# 권한별 LLM 키 활성화 — admin 2명은 전역 모든 API full access,
# 일반 user는 본인 키 필수 (각 계정 귀속). [규칙: 데이터/API 계정 귀속]
# 주의: 단일 프로세스 동시 멀티유저 시 마지막 로그인 user 키가 전역에 남을 수 있음
#       (실사용 1인 세션 기준 안전). 진짜 동시 멀티테넌시는 별도 프로세스 분리 필요.
# ══════════════════════════════════════════════════════════════════════
_cur_email = st.session_state.get("user", {}).get("email", "")
try:
    from src.auth.users import is_admin as _is_admin_fn
    st.session_state["_is_admin"] = _is_admin_fn(_cur_email)
except Exception:
    st.session_state["_is_admin"] = False

if st.session_state.get("_is_admin"):
    # admin: 전역 .env/secrets 키 (모든 API) 그대로 사용 — full access
    st.session_state["_llm_ready"] = bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("OPENAI_API_KEY")
        or os.environ.get("GOOGLE_API_KEY")
    )
else:
    # 일반 user: 전역(admin) 키 격리 — 본인 키만 사용 (API 사용량 본인 귀속)
    # 매 rerun 상단 load_dotenv가 전역 키를 다시 넣으므로 여기서 제거 후 본인 키만 세팅
    for _gk in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GOOGLE_API_KEY"):
        os.environ.pop(_gk, None)
    try:
        from src.auth.users import get_llm_settings
        _us = get_llm_settings(_cur_email)
        _uk = (_us.get("api_key") or "").strip()
        _prov = (_us.get("provider") or "").lower()
        if _uk:
            if "anthro" in _prov or "claude" in _prov:
                os.environ["ANTHROPIC_API_KEY"] = _uk
            elif "openai" in _prov or "gpt" in _prov:
                os.environ["OPENAI_API_KEY"] = _uk
            elif "gemini" in _prov or "google" in _prov:
                os.environ["GOOGLE_API_KEY"] = _uk
            else:
                # provider 미지정이면 키 접두어로 추정
                if _uk.startswith("sk-ant"):
                    os.environ["ANTHROPIC_API_KEY"] = _uk
                elif _uk.startswith("sk-"):
                    os.environ["OPENAI_API_KEY"] = _uk
                else:
                    os.environ["GOOGLE_API_KEY"] = _uk
            st.session_state["_llm_ready"] = True
        else:
            st.session_state["_llm_ready"] = False
    except Exception:
        st.session_state["_llm_ready"] = False

# API 키 확인 — 권한별 안내
if not st.session_state.get("_llm_ready"):
    if st.session_state.get("_is_admin"):
        st.warning(
            "⚠️ **전역 LLM API 키가 설정되지 않았습니다.**  \n"
            f"`{str(_root / '.env')}` 또는 Streamlit Cloud Secrets에 "
            "`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` / `GOOGLE_API_KEY` 중 하나를 추가하세요.",
            icon="🔑",
        )
    else:
        st.warning(
            "🔑 **본인 LLM API 키를 등록해야 AI 기능을 사용할 수 있습니다.**  \n"
            "사이드바 하단 **AI 어시스턴트 설정**에서 본인 API 키를 입력하세요. "
            "(API 사용량은 본인 계정에 귀속됩니다.)",
            icon="🔑",
        )

# ══════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════
if "nav" not in st.session_state:
    st.session_state["nav"] = "홈"

# ── Session ID — persistent per browser session for continuity tracking ──
if "_session_id" not in st.session_state:
    import uuid as _uuid
    st.session_state["_session_id"] = _uuid.uuid4().hex[:12]

# ── 세션 시작 시 1회: self_model + 주기적 학습 트리거 (백그라운드) ────────
if "_bg_init_done" not in st.session_state:
    st.session_state["_bg_init_done"] = True
    import threading as _threading

    def _bg_session_init():
        try:
            from src.memory.self_model import refresh as _sm_refresh
            _sm_refresh()
        except Exception:
            pass
        try:
            import json as _json
            from pathlib import Path as _Path
            from datetime import datetime as _dt
            trend_state_path = _Path("data/knowledge_graph/trend_state.json")
            if trend_state_path.exists():
                ts = _json.loads(trend_state_path.read_text(encoding="utf-8"))
                last_run = ts.get("last_run", "")
                if last_run:
                    delta = (_dt.now() - _dt.fromisoformat(last_run)).total_seconds()
                    if delta < 86400:  # 24h 이내면 skip
                        return
            from src.knowledge.trend_learner import run_trend_learn
            from src.config.logging_config import get_logger as _gl
            _gl(__name__).info("[자동학습] 백그라운드 최신논문 학습 시작")
            _res = run_trend_learn(days=60, max_per_query=20)
            _gl(__name__).info("[자동학습] 완료: %s", _res)
        except Exception as _bge:
            try:
                from src.config.logging_config import get_logger as _gl
                _gl(__name__).warning("[자동학습] 실패(침묵 금지): %s", _bge)
            except Exception:
                pass

    _threading.Thread(target=_bg_session_init, daemon=True).start()

def _nav(p):
    st.session_state["nav"] = p
    st.rerun()


def _raw_data_available() -> bool:
    """data/raw에 자산화된 원시자료(.sav/.csv)가 있는지 (가벼운 체크, 로딩 안 함)."""
    from pathlib import Path as _P
    d = _P("data/raw")
    if not d.exists():
        return False
    for ext in ("*.sav", "*.csv", "*.xlsx"):
        if any(d.glob(ext)):
            return True
    return False


def _ensure_raw_df(dataset: str = "KYRBS"):
    """데이터프레임 단일 해결 경로 (전 페이지 공유) — 업로드 강요 금지.
    세션 raw_df/analysis_df 우선 → 없으면 자산화된 data/raw에서 자동 로드(_find_real_data).
    반환: DataFrame 또는 None(data/raw에도 없을 때만)."""
    df = st.session_state.get("analysis_df")
    if df is None:
        df = st.session_state.get("raw_df")
    if df is None:
        try:
            from src.research.research_pipeline import _find_real_data
            df = _find_real_data(dataset)
            if df is not None:
                st.session_state["raw_df"] = df
                st.session_state["raw_dataset"] = dataset
        except Exception:
            df = None
    return df

def _log(action, inp, summary, out=None, action_type: str = "general", why_better: str = ""):
    user_email = st.session_state.get("user", {}).get("email", "anonymous")
    page = st.session_state["nav"]
    from src.activity.logger import log_activity
    log_activity(user_email, page, action, inp, summary, out)
    try:
        from src.memory import change_log
        change_log.log(
            title=f"[{page}] {action}",
            description=str(summary)[:200] if summary else "",
            action_type=action_type,
            user_email=user_email,
            session_id=st.session_state.get("_session_id", ""),
            inputs=inp if isinstance(inp, dict) else {"input": str(inp)[:200]},
            outputs={"summary": str(summary)[:200], **(out if isinstance(out, dict) else {})},
            why_better=why_better,
        )
    except Exception:
        pass

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

def _show_topic_banner():
    """현재 선택된 주제와 단계별 진행 상태를 상단에 표시."""
    t = st.session_state.get("selected_topic")
    if not t:
        return
    has_novelty = "novelty_result" in st.session_state
    has_feasibility = "feasibility_result" in st.session_state
    has_draft = "draft" in st.session_state
    steps = [
        ("주제 선택", True),
        ("신규성", has_novelty),
        ("타당성", has_feasibility),
        ("논문 작성", has_draft),
    ]
    badges = " → ".join(
        f"<span style='padding:2px 9px;border-radius:20px;font-size:11px;font-weight:700;"
        f"background:{'rgba(34,197,94,.18)' if done else 'rgba(255,255,255,.06)'};"
        f"color:{'#4ADE80' if done else '#64748B'};"
        f"border:1px solid {'rgba(34,197,94,.35)' if done else 'rgba(255,255,255,.08)'};'>"
        f"{'✓ ' if done else ''}{label}</span>"
        for label, done in steps
    )
    nov_score = ""
    if has_novelty:
        sc = st.session_state["novelty_result"].get("novelty_score", "?")
        nov_score = f"<span style='font-size:11px;color:#60A5FA;margin-left:6px;'>신규성 {sc}/10</span>"
    title_safe = t.get('title', '')[:70].replace('"', '&quot;')
    # 들여쓰기 없는 단일 라인 HTML (Markdown 코드블록 오인식 방지)
    html = (
        '<div style="background:rgba(37,99,235,0.07);border:1px solid rgba(59,130,246,0.22);'
        'border-radius:10px;padding:10px 16px;margin-bottom:14px;display:flex;'
        'align-items:center;gap:12px;flex-wrap:wrap;">'
        '<span style="font-size:10px;color:#60A5FA;font-weight:700;text-transform:uppercase;'
        'letter-spacing:.08em;white-space:nowrap;">현재 프로젝트</span>'
        f'<span style="font-size:13px;color:#E5E7EB;font-weight:600;flex:1;min-width:0;'
        f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="{title_safe}">'
        f'{title_safe}</span>'
        f'{nov_score}'
        f'<div style="display:flex;gap:4px;flex-wrap:wrap;">{badges}</div>'
        '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)

def _next_step_btn(label: str, target: str, key: str):
    """다음 단계로 이동 버튼."""
    if st.button(f"▶ {label}", key=key, type="primary"):
        _nav(target)

# ══════════════════════════════════════════════════════════════════════
# 연구 플로우 — 중앙 정의 (사이드바·스텝바·다음단계 안내가 모두 이걸 참조)
# (단계번호, 표시라벨, 페이지키, 완료판정 함수)
# ══════════════════════════════════════════════════════════════════════
RESEARCH_FLOW = [
    ("1", "원시자료 업로드", "원시자료 업로드", lambda s: s.get("raw_df") is not None or _raw_data_available()),
    ("2", "연구 주제 생성", "연구 주제 생성", lambda s: bool(s.get("topics") or s.get("selected_topic"))),
    ("3", "신규성 확인", "신규성 확인", lambda s: "novelty_result" in s),
    ("4", "타당성 검증", "논문 설계 & 타당성", lambda s: "feasibility_result" in s),
    ("5", "데이터 분석", "데이터 분석", lambda s: s.get("stat_result_for_paper") is not None),
    ("6", "논문 작성", "논문 작성", lambda s: "draft" in s),
]
_FLOW_TARGETS = [t for _, _, t, _ in RESEARCH_FLOW]


def _flow_stepbar(current_target: str):
    """플로우 단계 진행 바 — 완료(초록)/현재(파랑)/대기(회색)를 상단에 일관 표시."""
    chips = []
    for n, label, target, done_fn in RESEARCH_FLOW:
        try:
            done = bool(done_fn(st.session_state))
        except Exception:
            done = False
        is_cur = (target == current_target)
        if is_cur:
            bg, fg, bd, mark = "rgba(59,130,246,.20)", "#60A5FA", "rgba(59,130,246,.45)", "▸"
        elif done:
            bg, fg, bd, mark = "rgba(34,197,94,.16)", "#4ADE80", "rgba(34,197,94,.35)", "✓"
        else:
            bg, fg, bd, mark = "rgba(255,255,255,.05)", "#64748B", "rgba(255,255,255,.08)", n
        chips.append(
            f'<span style="padding:3px 11px;border-radius:20px;font-size:11px;font-weight:700;'
            f'background:{bg};color:{fg};border:1px solid {bd};white-space:nowrap;">{mark} {label}</span>'
        )
    arrow = '<span style="color:#334155;font-size:11px;">→</span>'
    html = (
        '<div style="display:flex;align-items:center;gap:6px;flex-wrap:wrap;'
        'margin-bottom:14px;padding:8px 0;">' + arrow.join(chips) + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _flow_next(current_target: str):
    """현재 플로우 단계의 다음 단계로 가는 안내 버튼 자동 생성."""
    if current_target not in _FLOW_TARGETS:
        return
    idx = _FLOW_TARGETS.index(current_target)
    if idx + 1 >= len(RESEARCH_FLOW):
        return
    n, label, target, _ = RESEARCH_FLOW[idx + 1]
    st.divider()
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown(
            f"<div style='padding-top:6px;color:#94A3B8;font-size:13px;'>"
            f"다음 단계: <b style='color:#E5E7EB;'>STEP {n}. {label}</b></div>",
            unsafe_allow_html=True,
        )
    with c2:
        if st.button(f"{label} →", key=f"_flownext_{target}", type="primary", use_container_width=True):
            _nav(target)


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
        <div class="logo-icon">🔬</div>
        <span style="font-size:15px;font-weight:800;color:#E5E7EB;letter-spacing:-0.01em;">Medical-Agent</span>
    </div>
    """, unsafe_allow_html=True)
    st.markdown('<div style="padding:4px 4px 2px;">', unsafe_allow_html=True)
    # ── 모든 사용자 공통: 바이브 중심 (깔끔) ──
    _nb("🏠  홈", "홈")
    _nb("📝  논문 작업실", "논문 작업실")          # ★ 바이브 — AI 채팅으로 논문 작성
    _nb("✍️  글쓰기 스타일", "글쓰기 스타일")       # 스타일 학습 + 선택
    _nb("📜  작업 타임라인", "작업 타임라인")       # 본인 작업 이력

    # ── 관리자 전용: 기존 단위 기능은 토글로 접어둔다 (기본 OFF) ──
    # 기본 화면은 admin도 바이브(작업실) 중심으로 깔끔하게. 단위 기능 테스트가
    # 필요할 때만 '관리자 모드'를 켜서 옛 화면을 노출 → old/new 메뉴 혼재 해소.
    if st.session_state.get("_is_admin"):
        st.markdown('<div style="padding:8px 8px 2px;">', unsafe_allow_html=True)
        _admin_mode = st.toggle("🔧 관리자 모드 (단위 기능)", key="_admin_mode",
                                help="끄면 바이브 화면만(메인). 켜면 옛 단위 기능 화면을 테스트용으로 노출.")
        st.markdown('</div>', unsafe_allow_html=True)
        if _admin_mode:
            st.markdown('<div class="nav-section">연구 단계 (테스트)</div>', unsafe_allow_html=True)
            _nb("⚡  원스톱 자동 파이프라인", "논문 생산 파이프라인")
            for _n, _label, _target, _done_fn in RESEARCH_FLOW:
                try:
                    _done = bool(_done_fn(st.session_state))
                except Exception:
                    _done = False
                _mark = "✓" if _done else _n
                _nb(f"{_mark}  {_label}", _target)
            st.markdown('<div class="nav-section">도구 / 단위</div>', unsafe_allow_html=True)
            _nb("📄  기존 논문 개선", "기존 논문 개선")
            _nb("📤  논문 업로드 & 인제스트", "논문 업로드 & 인제스트")
            _nb("🤖  Agent Q&A", "Agent Q&A")
            _nb("⚡  워크플로우", "워크플로우")
            _nb("📓  Notebook 에디터", "Notebook 에디터")
            _nb("🔁  자동 학습 루프", "자동 학습 루프")
            st.markdown('<div class="nav-section">시스템</div>', unsafe_allow_html=True)
            _nb("🧬  자가 진단", "자가 진단")
            _nb("📚  지식베이스 관리", "지식베이스 관리")
            _nb("🧠  지식 위키 (누적)", "지식 위키")
    st.markdown('</div>', unsafe_allow_html=True)

    # ── LLM Provider 설정 ──────────────────────────────────────────
    st.markdown('<div class="nav-section">AI 어시스턴트</div>', unsafe_allow_html=True)
    st.markdown('<div style="padding:0 8px 8px;">', unsafe_allow_html=True)

    _PROVIDERS = {
        "🔄 자동": "🔄 자동 (무료 우선)",
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
            st.session_state["llm_settings"] = {"provider": "🔄 자동 (무료 우선)", "api_key": ""}

    _saved = st.session_state["llm_settings"]
    _cur_icon = next((k for k, v in _PROVIDERS.items() if v == _saved["provider"]), "🔄 자동")

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
# 논문 작업실은 자체 좌(채팅)/우(논문) 레이아웃이 있어 전역 AI 패널이 중복·충돌한다.
# 해당 페이지만 전체폭으로 쓰고, 나머지 페이지는 본문[13] + AI 패널[7] 분할 유지.
_FULL_WIDTH_PAGES = {"논문 작업실"}
if page in _FULL_WIDTH_PAGES:
    main_col = st.container()
    ai_col = None
else:
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
                <span style="font-size:27px;font-weight:800;color:#E5E7EB;letter-spacing:-0.02em;">Medical-Agent</span>
                <span style="font-size:20px;">✨</span>
            </div>
            <p style="color:#64748B;font-size:14px;margin:0;">의학 논문 자동 생산 파이프라인</p>
            """, unsafe_allow_html=True)
        with col_btn:
            st.markdown('<div style="margin-top:6px;"></div>', unsafe_allow_html=True)
            if st.button("✍️ 논문 작업실 열기", type="primary", use_container_width=True):
                _nav("논문 작업실")

        # ── chat-first 단일 진입 (조언 UX: 첫 화면 = "무슨 연구를 하고 싶나요?") ──
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-size:23px;font-weight:800;color:#E5E7EB;text-align:center;margin:16px 0 4px;'>"
            "무슨 연구를 하고 싶으세요?</div>"
            "<div style='text-align:center;color:#64748B;font-size:13px;margin-bottom:12px;'>"
            "주제를 한 줄로 적으면 작업실에서 AI가 연구질문·변수·분석법을 제안하고 같이 써내려갑니다.</div>",
            unsafe_allow_html=True)
        _hq1, _hq2 = st.columns([5, 1])
        with _hq1:
            _home_q = st.text_input("연구 주제", key="home_research_q", label_visibility="collapsed",
                                    placeholder="예: 청소년 제로칼로리 음료 섭취와 우울 증상의 연관성")
        with _hq2:
            _home_go = st.button("→ 시작", type="primary", use_container_width=True, key="home_go")

        def _start_research(_q: str):
            _q = (_q or "").strip()
            if not _q:
                return
            st.session_state["ws_title"] = _q
            st.session_state["ws_chat"] = [{
                "role": "assistant",
                "content": f"**\"{_q}\"** 연구를 시작합니다.\n\n무엇부터 도와드릴까요? — "
                           "*\"서론 써줘\"*, *\"방법 KYRBS 복합표본으로\"*, *\"신규성 확인\"*, "
                           "*\"이 주제 연구질문·변수·분석법 제안해줘\"* 처럼 말하면 오른쪽 논문에 반영됩니다.",
            }]
            _nav("논문 작업실")

        if _home_go:
            _start_research(_home_q)
        # 빠른 예시 (클릭 시 바로 시작)
        _ex1, _ex2, _ex3 = st.columns(3)
        for _col, _ex in zip([_ex1, _ex2, _ex3], [
            "청소년 스마트폰 과사용과 수면부족",
            "제로칼로리 음료와 청소년 우울",
            "아침결식과 학업스트레스·우울",
        ]):
            with _col:
                if st.button(f"💡 {_ex}", use_container_width=True, key=f"home_ex_{_ex[:6]}"):
                    _start_research(_ex)
        st.divider()

        # ── 현재 연구 진행 대시보드 (플로우 중심) ───────────────────────────
        st.markdown("<div style='height:14px'></div>", unsafe_allow_html=True)
        _done_flags = []
        for _fn in (f for *_, f in RESEARCH_FLOW):
            try:
                _done_flags.append(bool(_fn(st.session_state)))
            except Exception:
                _done_flags.append(False)
        _done_cnt = sum(_done_flags)
        _next_step = next(
            (RESEARCH_FLOW[i] for i, fl in enumerate(_done_flags) if not fl), None
        )
        _cur_title = st.session_state.get("selected_topic", {}).get("title", "") if st.session_state.get("selected_topic") else ""

        dash_l, dash_r = st.columns([3, 2])
        with dash_l:
            st.markdown(
                f"<div style='font-size:13px;color:#94A3B8;font-weight:700;"
                f"text-transform:uppercase;letter-spacing:.06em;margin-bottom:6px;'>"
                f"현재 연구 진행 — {_done_cnt}/{len(RESEARCH_FLOW)} 단계</div>",
                unsafe_allow_html=True,
            )
            if _cur_title:
                st.markdown(
                    f"<div style='font-size:14px;color:#E5E7EB;font-weight:600;margin-bottom:8px;'>📌 {_cur_title[:70]}</div>",
                    unsafe_allow_html=True,
                )
            st.progress(_done_cnt / len(RESEARCH_FLOW))
            _flow_stepbar(_next_step[2] if _next_step else "")
        with dash_r:
            st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
            if _next_step:
                _n, _label, _target, _ = _next_step
                st.markdown(
                    f"<div style='color:#94A3B8;font-size:12px;margin-bottom:6px;'>다음 할 일</div>",
                    unsafe_allow_html=True,
                )
                if st.button(f"▶ STEP {_n}. {_label}", type="primary", use_container_width=True, key="_dash_next"):
                    _nav(_target)
                if st.button("⚡ 원스톱 자동 (전체 한번에)", use_container_width=True, key="_dash_auto"):
                    _nav("논문 생산 파이프라인")
            else:
                st.success("✅ 모든 단계 완료 — 논문 초안까지 생성됨")
                if st.button("📝 논문 작성 결과 보기", type="primary", use_container_width=True, key="_dash_done"):
                    _nav("논문 작성")

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        for col, (ic_cls, num, title, desc) in zip([c1, c2, c3], [
            ("ic-circle ic-blue",  "01", "연구 주제 생성",     "KYRBS · KNHANES 데이터셋 + RAG 기반 주제 자동 생성"),
            ("ic-circle ic-indigo","02", "연구 설계 & 타당성", "PubMed 검색 · Claude 심층 분석 · 변수 타당성 검토"),
            ("ic-circle ic-purple","03", "논문 작성",          "조유선 스타일로 전체 논문 초안 자동 생성"),
        ]):
            with col:
                st.markdown(f"""
                <div class="pipeline-card">
                    <div class="{ic_cls}">{num}</div>
                    <div class="step-n">STEP {num}</div>
                    <div class="step-t">{title}</div>
                    <div class="step-d">{desc}</div>
                </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        col_l, col_r = st.columns(2)
        with col_l:
            st.markdown("""
            <div class="card" style="padding-bottom:14px;">
                <div style="font-size:15px;font-weight:700;color:#E5E7EB;margin-bottom:3px;">빠른 시작</div>
                <p style="color:#64748B;font-size:12px;margin-bottom:14px;">원하는 작업을 선택하세요</p>
            </div>""", unsafe_allow_html=True)
            for icon, lbl, dsc, tgt in [
                ("✍️", "논문 작업실",     "직접 쓰고 AI가 거든다 · 우측 실시간 프리뷰", "논문 작업실"),
                ("📝", "연구 주제 탐색",  "새로운 연구 아이디어 발굴",   "연구 주제 생성"),
                ("📊", "데이터 분석",     "통계 분석 및 변수 탐색",      "데이터 분석"),
                ("⚡", "원스톱 자동",     "초안 시드를 한번에 (보조)",   "논문 생산 파이프라인"),
            ]:
                if st.button(f"{icon}  {lbl}  —  {dsc}", key=f"_qs_{tgt}",
                             use_container_width=True):
                    _nav(tgt)

        with col_r:
            st.markdown("""
            <div class="card" style="margin-bottom:0;">
                <div style="font-size:15px;font-weight:700;color:#E5E7EB;margin-bottom:3px;">학습된 자료</div>
                <p style="color:#64748B;font-size:12px;margin-bottom:14px;">AI 기반 지식베이스 현황</p>
            </div>""", unsafe_allow_html=True)
            try:
                pp = Path("data/yoosun_cho_papers.json")
                if pp.exists():
                    cnt = len(json.loads(pp.read_text(encoding="utf-8")))
                    st.markdown(f"""
                    <div class="kb-item">
                        <div class="ic-circle ic-indigo ic-sm">📚</div>
                        <div style="flex:1;min-width:0;">
                            <div style="font-size:13px;font-weight:600;color:#E5E7EB;">조유선 교수 논문</div>
                            <div style="font-size:11px;color:#64748B;">총 {cnt}편 학습 완료</div>
                        </div>
                        <div class="kb-badge">READY</div>
                    </div>""", unsafe_allow_html=True)
            except Exception: pass
            try:
                lp = Path("data/libraries/dataset_kyrbs.json")
                if lp.exists():
                    ds_kyrbs = json.loads(lp.read_text(encoding="utf-8"))
                    n_vars = len(ds_kyrbs.get("variables", {}))
                    st.markdown(f"""
                    <div class="kb-item">
                        <div class="ic-circle ic-blue ic-sm">📊</div>
                        <div style="flex:1;min-width:0;">
                            <div style="font-size:13px;font-weight:600;color:#E5E7EB;">KYRBS 청소년건강행태조사</div>
                            <div style="font-size:11px;color:#64748B;">{n_vars}개 변수</div>
                        </div>
                        <div class="kb-badge">READY</div>
                    </div>""", unsafe_allow_html=True)
            except Exception: pass
            try:
                lp2 = Path("data/libraries/dataset_knhanes.json")
                if lp2.exists():
                    ds_knh = json.loads(lp2.read_text(encoding="utf-8"))
                    n_vars2 = len(ds_knh.get("variables", {}))
                    n_refs = len(ds_knh.get("papers_using_this", []))
                    st.markdown(f"""
                    <div class="kb-item">
                        <div class="ic-circle ic-purple ic-sm">🏥</div>
                        <div style="flex:1;min-width:0;">
                            <div style="font-size:13px;font-weight:600;color:#E5E7EB;">KNHANES 국민건강영양조사</div>
                            <div style="font-size:11px;color:#64748B;">{n_vars2}개 변수 · 참조논문 {n_refs}편</div>
                        </div>
                        <div class="kb-badge">READY</div>
                    </div>""", unsafe_allow_html=True)
            except Exception: pass
            try:
                cnt2 = _get_cached_store().count()
                db_lbl = "Supabase" if os.environ.get("SUPABASE_DB_URL") else "ChromaDB"
                st.markdown(f"""
                <div class="kb-item">
                    <div class="ic-circle ic-green ic-sm">🗄️</div>
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:13px;font-weight:600;color:#E5E7EB;">의학 지식베이스 ({db_lbl})</div>
                        <div style="font-size:11px;color:#64748B;">{cnt2:,}개 청크</div>
                    </div>
                    <div class="kb-badge">READY</div>
                </div>""", unsafe_allow_html=True)
            except Exception: pass
            if st.button("전체 학습 자료 보기 →", key="_kb_all", use_container_width=True):
                _nav("지식베이스 관리")

        st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
        recent = st.session_state.get("recent_projects", [])
        badge_colors = {
            "논문 작성 중": ("#8B5CF6","rgba(139,92,246,0.12)"),
            "데이터 분석 중": ("#3B82F6","rgba(59,130,246,0.12)"),
            "연구 설계 중": ("#10B981","rgba(16,185,129,0.12)"),
        }
        proj_html = ""
        if not recent:
            proj_html = '<div style="text-align:center;padding:28px;color:#4B5563;font-size:13px;">아직 진행 중인 프로젝트가 없습니다</div>'
        else:
            for proj in recent[:5]:
                fc, bg = badge_colors.get(proj.get("status",""), ("#64748B","rgba(100,116,139,0.12)"))
                proj_html += f"""
                <div class="proj-row">
                    <div style="flex:1;min-width:0;">
                        <div style="font-size:14px;font-weight:600;color:#E5E7EB;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{proj.get("title","")}</div>
                        <div style="font-size:11px;color:#4B5563;margin-top:2px;">{proj.get("updated","")}</div>
                    </div>
                    <div class="proj-badge" style="color:{fc};background:{bg};border:1px solid {fc}33;">{proj.get("status","")}</div>
                </div>"""
        st.markdown(f"""
        <div class="card">
            <div style="font-size:15px;font-weight:700;color:#E5E7EB;margin-bottom:14px;">최근 프로젝트</div>
            {proj_html}
        </div>""", unsafe_allow_html=True)

        page_context.update({"recent_projects": len(recent), "학습된_논문수": "14편"})

    # ── 논문 작업실 (좌: 작업 패널 / 우: 논문 프리뷰) ──────────────────────
    elif page == "논문 작업실":
        st.markdown(
            "<h2 style='color:#e6edf3;'>📝 논문 작업실 "
            "<span style='font-size:13px;color:#64748B;font-weight:400;'>— 왼쪽 AI와 대화하면 오른쪽 논문이 채워집니다</span></h2>",
            unsafe_allow_html=True,
        )

        _WS_KEYS = [
            ("title", "제목"), ("abstract", "Abstract"), ("introduction", "Introduction"),
            ("methods", "Methods"), ("results", "Results"), ("discussion", "Discussion"),
        ]
        _WS_LABEL2KEY = {lbl.lower(): k for k, lbl in _WS_KEYS}
        _WS_LABEL2KEY.update({k: k for k, _ in _WS_KEYS})  # key 자체도 허용
        # 섹션 초기화 — 기존 draft 있으면 파싱해 채움 (1회)
        if "ws_init" not in st.session_state:
            st.session_state["ws_init"] = True
            _existing = st.session_state.get("draft", "")
            _secs = {}
            if _existing:
                try:
                    from src.ingestion.paper_ingester import _split_into_sections
                    _secs = _split_into_sections(_existing)
                except Exception:
                    _secs = {}
            for _k, _ in _WS_KEYS:
                st.session_state.setdefault(f"ws_{_k}", _secs.get(_k, ""))
            if not st.session_state.get("ws_title"):
                _seltop = st.session_state.get("selected_topic", {}) or {}
                st.session_state["ws_title"] = st.session_state.get("topic_title", "") or _seltop.get("title", "")
        if "ws_chat" not in st.session_state:
            st.session_state["ws_chat"] = [{
                "role": "assistant",
                "content": "어떤 논문을 쓸까요? 예를 들어:\n\n"
                           "- *\"청소년 스마트폰 과사용과 수면부족 연구로 서론 써줘\"*\n"
                           "- *\"방법 섹션에 KYRBS 복합표본 분석 추가해\"*\n"
                           "- *\"결과를 더 간결하게 다듬어\"*\n\n"
                           "라고 말하면 오른쪽 논문에 바로 반영됩니다.",
            }]

        def _ws_preview():
            parts = []
            for _k, _label in _WS_KEYS:
                _v = (st.session_state.get(f"ws_{_k}") or "").strip()
                if not _v:
                    continue
                parts.append(f"# {_v}" if _k == "title" else f"## {_label}\n\n{_v}")
            return "\n\n".join(parts)

        def _ws_study_info():
            _sel = st.session_state.get("selected_topic", {}) or {}
            return {
                "title": st.session_state.get("ws_title", ""),
                "dataset": st.session_state.get("ws_dataset", "KYRBS"),
                "exposure": st.session_state.get("ws_exposure", _sel.get("exposure", "")),
                "outcome": st.session_state.get("ws_outcome", _sel.get("outcome", "")),
                "population": st.session_state.get("ws_population", _sel.get("population", "")),
                "summary": st.session_state.get("ws_summary", ""),
            }

        def _ws_parse_json(raw: str):
            """LLM JSON 파싱 — Gemini 등이 산문/마크다운을 섞어도 첫 {...} 블록을 추출."""
            import json as _json, re as _re
            raw = (raw or "").strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.lstrip().lower().startswith("json"):
                    raw = raw.lstrip()[4:]
            raw = raw.strip().rstrip("`").strip()
            try:
                return _json.loads(raw)
            except Exception:
                pass
            # 산문 속 첫 균형 잡힌 JSON 객체 추출
            m = _re.search(r"\{.*\}", raw, _re.DOTALL)
            if m:
                try:
                    return _json.loads(m.group(0))
                except Exception:
                    return None
            return None

        # 의도/섹션 휴리스틱 — LLM JSON 분류가 실패해도 한국어 키워드로 라우팅 (폴백)
        _WS_SEC_KW = {
            "title": ["제목", "title"],
            "abstract": ["초록", "요약", "abstract"],
            "introduction": ["서론", "introduction", "intro", "배경", "도입"],
            "methods": ["방법", "method", "methods", "분석방법", "연구방법"],
            "results": ["결과", "result", "results"],
            "discussion": ["고찰", "논의", "discussion", "결론", "conclusion"],
        }

        def _ws_classify_heuristic(msg: str) -> tuple:
            m = (msg or "").lower()
            sec = next((k for k, kws in _WS_SEC_KW.items() if any(w in m for w in kws)), None)
            def has(*ws): return any(w in m for w in ws)
            if has("신규성", "novelty", "독창"):
                intent = "novelty"
            elif has("검색", "찾아", "관련 논문", "레퍼런스", "참고문헌"):
                intent = "search"
            elif has("심사", "리뷰", "review", "평가받", "피드백"):
                intent = "review"
            elif has("주제 추천", "주제추천", "토픽", "아이디어", "주제 제안"):
                intent = "topics"
            elif has("다듬", "간결", "수정", "고쳐", "줄여", "늘려", "바꿔", "고치", "refine"):
                intent = "refine"
            elif has("써줘", "써 줘", "작성", "써보", "초안", "만들어", "추가", "넣어", "쓰자", "write"):
                intent = "write"
            elif sec:  # 섹션을 명시했으면 작성으로 간주
                intent = "write"
            else:
                intent = "chat"
            return intent, sec

        def _ws_agent(user_msg: str) -> dict:
            """채팅 메시지 → 의도 분류 → 기존 단위 기능을 채팅으로 호출 (전 기능 바이브).
            반환: {section(key 또는 None), content, reply}"""
            import json as _json
            from src.llm import get_llm_client
            _keys = [k for k, _ in _WS_KEYS]
            _study = _ws_study_info()
            _filled = {k: bool((st.session_state.get(f"ws_{k}") or "").strip()) for k in _keys}
            llm = get_llm_client(task="paper_writing")
            # 최근 대화 맥락 — 직전 턴들을 모든 프롬프트에 주입 (단기 컨텍스트)
            _recent = [m for m in st.session_state.get("ws_chat", [])[-7:-1]
                       if m.get("role") in ("user", "assistant")]
            _hist = "\n".join(f"{m['role']}: {str(m['content'])[:280]}" for m in _recent)
            # MemPalace식 의미 메모리 — 지금 질문과 관련된 '과거' 대화를 회수 (장기 컨텍스트)
            try:
                from src.memory.conversation_memory import recall_relevant as _recall
                _relevant = _recall(user_msg, n=3, owner_email=_u.get("email", ""))
            except Exception:
                _relevant = ""
            if _relevant:
                _hist = (_relevant + "\n" + _hist) if _hist else _relevant
            # OpenKB식 누적 지식 위키 — 축적된 연구 개념을 글쓰기에 주입 ("쓸수록 더 잘 씀")
            try:
                from src.knowledge.research_wiki import ResearchWiki
                _wiki_ctx = ResearchWiki(owner_email=_u.get("email", "")).build_context(
                    f"{user_msg} {st.session_state.get('ws_title', '')}", n=3)
            except Exception:
                _wiki_ctx = ""

            # 1) 의도 분류 — 어떤 기존 기능을 부를지
            _cls = (
                "Classify the user's request in a medical paper workspace. JSON only:\n"
                '{"intent":"write|refine|novelty|search|review|topics|chat",'
                '"section":"<key or null>","detail":"<key instruction>"}\n'
                "- write: 새 섹션 작성. refine: 기존 섹션 수정/다듬기. novelty: 신규성 확인(PubMed).\n"
                "- search: 관련 논문 검색. review: 동료심사. topics: 연구주제 추천. chat: 일반 질문/대화.\n"
                "이전 대화에서 사용자가 쓰자고 한 주제를 '오른쪽에 써줘'라고 하면 write로 분류.\n"
                f"sections={_keys}, filled={_json.dumps(_filled)}, study={_json.dumps(_study, ensure_ascii=False)}\n"
                f"RECENT CONVERSATION:\n{_hist}\n"
                f"request: {user_msg}"
            )
            _ic = _ws_parse_json(llm.generate(_cls, task="fast", max_tokens=200)) or {}
            _h_intent, _h_sec = _ws_classify_heuristic(user_msg)
            # LLM 분류가 파싱되면 사용, 아니면 휴리스틱으로 폴백 (chat 오분류 방지)
            _intent = _ic.get("intent") or _h_intent
            if _intent not in ("write", "refine", "novelty", "search", "review", "topics", "chat"):
                _intent = _h_intent
            # LLM이 chat이라 했지만 휴리스틱이 작성/수정이면 휴리스틱 우선 (서론 써줘 → write)
            if _intent == "chat" and _h_intent in ("write", "refine"):
                _intent = _h_intent
            _sec = _ic.get("section") if _ic.get("section") in _keys else _h_sec
            _detail = _ic.get("detail") or user_msg

            # 2) 의도별 핸들러 — 미리 만들어둔 단위 기능 호출
            try:
                if _intent in ("write", "refine"):
                    _cur = {k: (st.session_state.get(f"ws_{k}") or "")[:1500] for k in _keys}
                    _wp = (
                        "You write a section of a Korean medical research paper.\n"
                        f"STUDY: {_json.dumps(_study, ensure_ascii=False)}\n"
                        f"CURRENT SECTIONS: {_json.dumps(_cur, ensure_ascii=False)[:2000]}\n"
                        f"{(_wiki_ctx + chr(10)) if _wiki_ctx else ''}"
                        f"RECENT CONVERSATION (이 맥락의 주제를 이어서 작성):\n{_hist}\n"
                        f"REQUEST: {user_msg}\n"
                        f"Target section: {_sec or '(infer the most relevant)'}\n"
                        "Return ONLY JSON: {\"section\":\"<key>\",\"content\":\"<FULL new section text>\","
                        "\"reply\":\"<short Korean reply>\"}. Preserve statistics/facts."
                    )
                    _raw = llm.generate(_wp, task="paper_writing", max_tokens=3000)
                    _d = _ws_parse_json(_raw) or {}
                    _s = _d.get("section") if _d.get("section") in _keys else (_sec or "introduction")
                    _content = _d.get("content", "")
                    # JSON 파싱 실패 시에도 본문을 잃지 않도록 원문 텍스트를 섹션에 반영 (핵심)
                    if not _content:
                        _content = (_raw or "").strip()
                    if not _content:
                        return {"section": None, "content": "", "reply": "내용 생성에 실패했습니다. 다시 시도해 주세요."}
                    _label = next((lbl for k, lbl in _WS_KEYS if k == _s), _s)
                    return {"section": _s, "content": _content,
                            "reply": _d.get("reply") or f"✍️ **{_label}**에 반영했습니다."}

                if _intent == "novelty":
                    from src.research.novelty_checker import NoveltyChecker
                    _r = NoveltyChecker().check(
                        topic=_study["title"] or _detail, exposure=_study["exposure"],
                        outcome=_study["outcome"], population=_study["population"],
                    )
                    st.session_state["novelty_result"] = _r
                    return {"section": None, "content": "",
                            "reply": f"🔍 **신규성 {_r.get('novelty_score','?')}/10** (규칙기반 {_r.get('rule_based_score','?')})\n\n"
                                     f"{str(_r.get('llm_justification',''))[:400]}"}

                if _intent == "search":
                    from src.ingestion.evidence_reader import EvidenceReader
                    _ps = [p for p in EvidenceReader().search(_detail or _study["title"], max_per_source=5)[:6] if p]
                    _lines = [f"- {p.get('title','')} ({p.get('year','')}, {p.get('journal','')})" for p in _ps]
                    return {"section": None, "content": "",
                            "reply": "📚 **관련 논문**\n" + ("\n".join(_lines) if _lines else "검색 결과가 없습니다.")}

                if _intent == "review":
                    _draft = _ws_preview()
                    if not _draft.strip():
                        return {"section": None, "content": "", "reply": "먼저 논문 내용을 작성한 뒤 심사를 요청하세요."}
                    from src.research.peer_reviewer import PeerReviewer
                    _rv = PeerReviewer().review(_draft, _study["title"] or "Untitled",
                                                stat_result=st.session_state.get("stat_result_for_paper"))
                    _mc = "\n".join(f"- {c}" for c in (_rv.major_concerns or [])[:4])
                    return {"section": None, "content": "",
                            "reply": f"👥 **동료심사 {_rv.total_score}/100 ({_rv.grade})** — {_rv.accept_recommendation}\n\n"
                                     f"주요 지적:\n{_mc or '(없음)'}"}

                if _intent == "topics":
                    from src.research.research_pipeline import ResearchPipeline
                    _ts = ResearchPipeline(author_name=st.session_state.get("ws_style", "Yoosun Cho")).generate_topics(
                        _study["dataset"], focus=_detail, n_topics=3)
                    _lines = [f"- **{t.get('title','')}** ({t.get('exposure','')}→{t.get('outcome','')})" for t in _ts[:3]]
                    return {"section": None, "content": "", "reply": "💡 **추천 주제**\n" + "\n".join(_lines)}

                # chat — 일반 질문/대화 (대화 맥락 유지)
                _reply = llm.generate(
                    f"의학 논문 작성을 돕는 어시스턴트다. 현재 연구: {_json.dumps(_study, ensure_ascii=False)}.\n"
                    f"이전 대화:\n{_hist}\n"
                    f"사용자: {user_msg}\n한국어로 간결히 답하라. "
                    "사용자가 직전에 쓰자고 한 내용을 '오른쪽에 써줘'라고 하면 그 주제로 섹션을 작성하라.",
                    task="fast", max_tokens=700,
                )
                return {"section": None, "content": "", "reply": (_reply or "").strip()[:1000]}
            except Exception as _e:
                _es = str(_e).lower()
                if any(k in _es for k in ("429", "quota", "exceeded", "provider 실패", "rate", "resourceexhausted")):
                    return {"section": None, "content": "",
                            "reply": "⏳ **오늘 무료 LLM 쿼터가 소진됐습니다.**\n\n"
                                     "무료 Gemini는 모델당 하루 20요청(순환 포함 ~80/일)이 한도입니다. "
                                     "내일 리셋되거나, 사이드바에 **유료 API 키**(Gemini 유료는 매우 저렴)를 넣으면 "
                                     "바로 무제한에 가깝게 쓸 수 있습니다.\n\n_원문 오류: " + str(_e)[:120] + "_"}
                return {"section": None, "content": "", "reply": f"기능 실행 중 오류: {str(_e)[:200]}"}

        def _ws_stata(stata_code: str) -> dict:
            """통계 분석 코드(STATA/SPSS/SAS/R 등) → 분석 스펙 추출(LLM) → StatBridge 동등 분석 → Table/Figure.
            원천 언어 무관 — 통계 로직을 해석해 SW 실행 없이 같은 OR/CI/p-trend/forest 결과 생성.
            데이터는 이미 자산화된 data/raw에서 자동 로드. 반환: {error} 또는 {result, spec}"""
            _df = st.session_state.get("raw_df")
            if _df is None:
                # 이미 자산화된 원시자료(data/raw) 자동 로드 — 업로드 재요구하지 않음
                try:
                    from src.research.research_pipeline import _find_real_data
                    _df = _find_real_data(st.session_state.get("ws_dataset", "kyrbs"))
                    if _df is not None:
                        st.session_state["raw_df"] = _df
                        st.session_state["raw_dataset"] = st.session_state.get("ws_dataset", "KYRBS")
                except Exception:
                    pass
            if _df is None:
                return {"error": "data/raw에 원시자료가 없습니다 (KYRBS/KNHANES는 이미 자산화돼 있어야 합니다)."}
            if not stata_code.strip():
                return {"error": "분석 코드를 입력하세요."}
            from src.llm import get_llm_client
            _cols = list(_df.columns)[:60]
            _sp = (
                "Extract a statistical analysis spec from this analysis code. The code may be in "
                "STATA, SPSS, SAS, or R — interpret the statistical logic regardless of source language. "
                f"Available data columns: {_cols}.\n"
                'Return ONLY JSON: {"outcome":"col","predictors":["col"],"covariates":["col"],'
                '"analysis":"logistic|linear|chi2","weight_var":"col or null",'
                '"strata_var":"col or null","cluster_var":"col or null","subgroups":["col"]}\n'
                "Map variable names to the closest actual data columns above. "
                "Analysis code:\n" + stata_code[:2500]
            )
            try:
                _spec = _ws_parse_json(get_llm_client(task="fast").generate(_sp, task="fast", max_tokens=400)) or {}
            except Exception as _e:
                return {"error": f"스펙 추출 실패(크레딧/오류): {_e}"}
            if not _spec.get("outcome"):
                return {"error": "STATA 코드에서 결과변수(outcome)를 찾지 못했습니다."}
            # 데이터에 실제 존재하는 컬럼만 (graceful)
            for _f in ("predictors", "covariates", "subgroups"):
                _spec[_f] = [c for c in (_spec.get(_f) or []) if c in _df.columns]
            if _spec["outcome"] not in _df.columns:
                return {"error": f"결과변수 '{_spec['outcome']}'가 데이터에 없습니다. 사용 가능 컬럼: {_cols[:15]}"}
            for _f in ("weight_var", "strata_var", "cluster_var"):
                if _spec.get(_f) and _spec[_f] not in _df.columns:
                    _spec[_f] = None
            try:
                from src.data.stat_bridge import StatBridge
                _result = StatBridge().run(_df, _spec).to_dict()
            except Exception as _e:
                return {"error": f"통계 분석 실패: {_e}"}
            st.session_state["stat_result_for_paper"] = _result
            try:
                from src.export.publication_figure_generator import generate_figures_for_paper
                st.session_state["ws_figures"] = generate_figures_for_paper(_result, safe_title="workspace_stata")
            except Exception:
                st.session_state["ws_figures"] = {}
            return {"result": _result, "spec": _spec}

        # ── 상단: 연구 정보 · 스타일 (접이식) ──
        # ── 내 논문 (영속 저장/불러오기) — 세션·재시작에도 유지, 계정 귀속 ──
        from src.storage import working_paper_store as _wps
        _is_adm = st.session_state.get("_is_admin", False)
        _my_papers = _wps.list_papers(_u.get("email", ""), all_papers=_is_adm)
        _paper_opts = {"🆕 새 논문": None}
        for _pp in _my_papers:
            _lbl = (_pp["title"][:42] or "제목 없음")
            if _is_adm and _pp.get("owner_email"):
                _lbl += f"  · {_pp['owner_email']}"
            _paper_opts[_lbl] = _pp["id"]
        pcol1, pcol2, pcol3 = st.columns([4, 1, 1])
        with pcol1:
            _pick = st.selectbox("내 논문", list(_paper_opts.keys()), key="ws_paper_pick",
                                 label_visibility="collapsed")
        with pcol2:
            if st.button("📂 열기", key="ws_load_saved", use_container_width=True):
                _pid = _paper_opts.get(_pick)
                if _pid:
                    _rec = _wps.load_paper(_u.get("email", ""), _pid, all_papers=_is_adm)
                    if _rec:
                        from src.research.research_state import ResearchState as _RS, SECTION_KEYS as _SK
                        # 캐노니컬 AST(_state) 우선, 없으면 flat 섹션 + meta._status로 재구성(하위호환)
                        _state = (_rec.get("meta", {}) or {}).get("_state")
                        if _state:
                            _rs = _RS.from_dict(_state)
                        else:
                            _rs = _RS.from_dict({"sections": _rec.get("sections", {})})
                            for _k, _v in ((_rec.get("meta", {}) or {}).get("_status", {}) or {}).items():
                                _rs.set_status(_k, _v)
                        _rs.paper_id = _pid
                        _rs.to_session(st.session_state)   # ws_* + ws_status + stat 복원
                        for _k in _SK:
                            st.session_state[f"ws_lock_{_k}"] = _rs.status_of(_k) in ("verified", "locked")
                        st.toast(f"불러옴: {_rec.get('title', '')[:30]}")
                        st.rerun()
                else:
                    for _k, _ in _WS_KEYS:
                        st.session_state[f"ws_{_k}"] = ""
                    st.session_state["ws_paper_id"] = None
                    st.toast("새 논문 시작")
                    st.rerun()
        with pcol3:
            if st.button("🗑 삭제", key="ws_del_saved", use_container_width=True):
                _pid = _paper_opts.get(_pick)
                if _pid and _wps.delete_paper(_u.get("email", ""), _pid, all_papers=_is_adm):
                    st.session_state["ws_paper_id"] = None
                    st.toast("삭제됨")
                    st.rerun()

        with st.expander("📋 연구 정보 · 글쓰기 스타일 (AI 컨텍스트)", expanded=False):
            _sel = st.session_state.get("selected_topic", {}) or {}
            ci1, ci2 = st.columns(2)
            with ci1:
                st.text_input("노출변수", value=st.session_state.get("ws_exposure", _sel.get("exposure", "")), key="ws_exposure")
                st.text_input("결과변수", value=st.session_state.get("ws_outcome", _sel.get("outcome", "")), key="ws_outcome")
                st.text_input("대상", value=st.session_state.get("ws_population", _sel.get("population", "Korean adolescents")), key="ws_population")
            with ci2:
                st.text_input("데이터셋", value=st.session_state.get("ws_dataset", "KYRBS"), key="ws_dataset")
                try:
                    from src.profile.author_profile import list_styles as _ls
                    _stopts = [s["name"] for s in _ls(owner_email=_u.get("email", ""), all_styles=st.session_state.get("_is_admin", False))] or ["Yoosun Cho"]
                except Exception:
                    _stopts = ["Yoosun Cho"]
                st.selectbox("글쓰기 스타일", _stopts, key="ws_style")
            st.text_area("핵심 결과 요약 (통계 등)", value=st.session_state.get("ws_summary", ""), key="ws_summary", height=60)
            _exup = st.file_uploader("기존 논문 불러오기 (DOCX/PDF/TXT)", type=["txt", "docx", "pdf", "md"], key="ws_existing_up")
            if _exup is not None and st.button("📥 불러오기", key="ws_load_existing"):
                try:
                    from src.ingestion.paper_ingester import PaperIngester
                    _paper = PaperIngester().ingest_bytes(_exup.getvalue(), _exup.name)
                    for _k, _ in _WS_KEYS:
                        if _k in _paper.sections:
                            st.session_state[f"ws_{_k}"] = _paper.sections[_k]
                    if _paper.title:
                        st.session_state["ws_title"] = _paper.title
                    st.success(f"{len(_paper.sections)}개 섹션 로드 — 채팅으로 개선하거나 오른쪽에서 편집하세요")
                    st.rerun()
                except Exception as _e:
                    st.error(f"파싱 오류: {_e}")

        col_chat, col_paper = st.columns([45, 55], gap="large")

        # ═══════════ 좌측: AI 에이전트 채팅 + 통계 코드 (러버블식) ═══════════
        with col_chat:
            _ws_mode = st.radio(
                "작업 모드", ["💬 AI 채팅", "📊 통계 코드"], horizontal=True,
                key="ws_mode", label_visibility="collapsed",
            )
            if _ws_mode == "💬 AI 채팅":
                st.markdown("<div style='font-size:13px;font-weight:700;color:#E5E7EB;margin-bottom:6px;'>🤖 AI 에이전트</div>", unsafe_allow_html=True)
                _chatbox = st.container(height=400, border=True)
                with _chatbox:
                    for _m in st.session_state["ws_chat"]:
                        with st.chat_message(_m["role"]):
                            st.markdown(_m["content"])
                _p = st.chat_input("논문에게 요청하세요 — 예: 서론 써줘 / 결과 더 간결하게")
                if _p:
                    st.session_state["ws_chat"].append({"role": "user", "content": _p})
                    if not st.session_state.get("_llm_ready"):
                        st.session_state["ws_chat"].append({"role": "assistant", "content": "⚠️ AI 사용을 위해 API 키가 필요합니다 (사이드바 설정 또는 admin 전역 키)."})
                        st.rerun()
                    try:
                        with st.spinner("AI가 작업 중..."):
                            _res = _ws_agent(_p)
                        _reply = _res.get("reply", "반영했습니다.")
                        if _res.get("section") and _res.get("content"):
                            _sk = _res["section"]
                            # State Registry 규칙: 잠긴 섹션은 자동 생성이 덮어쓰지 못함 (drift 차단)
                            if bool(st.session_state.get(f"ws_lock_{_sk}", False)):
                                _lbl = next((l for k, l in _WS_KEYS if k == _sk), _sk)
                                _reply = (f"🔒 **{_lbl}**은(는) 잠금 상태라 덮어쓰지 않았습니다. "
                                          f"수정하려면 우측 편집뷰에서 잠금(🔒)을 해제하세요.")
                            else:
                                st.session_state[f"ws_{_sk}"] = _res["content"]
                        st.session_state["ws_chat"].append({"role": "assistant", "content": _reply})
                        # MemPalace식 의미 메모리에 이번 교환 저장 (다음에 의미검색으로 회수)
                        try:
                            from src.memory import conversation_memory as _cm
                            _cm.record(_p, _res.get("content") or _reply,
                                       topic=st.session_state.get("ws_title", "")[:50],
                                       context_type="paper_write", owner_email=_u.get("email", ""))
                        except Exception:
                            pass
                    except Exception as _e:
                        st.session_state["ws_chat"].append({"role": "assistant", "content": f"오류: {str(_e)[:200]}"})
                    st.rerun()
            else:
                # ── 📊 통계 코드 모드 (STATA/SPSS/SAS/R → 동등 분석 → 논문 표·그림) ──
                st.markdown("<div style='font-size:13px;font-weight:700;color:#E5E7EB;margin-bottom:6px;'>📊 통계 코드 → 논문 표·그림</div>", unsafe_allow_html=True)
                st.caption("STATA·SPSS·SAS·R 코드를 붙여넣고 Run하면 동일 통계 로직을 Python으로 해석해 OR/95%CI/p-trend·forest를 계산합니다. 데이터는 자산화된 data/raw에서 자동 로드(업로드 불필요).")
                _code = st.text_area(
                    "분석 코드", height=300, key="ws_stata_code",
                    placeholder=("* 예 (STATA)\n"
                                 "svyset psu [pweight=w], strata(strata)\n"
                                 "svy: logistic depression i.zcb_freq4 i.sex i.age_cat i.bmi_cat ..."),
                    label_visibility="collapsed",
                )
                if st.button("▶ Run — 코드 해석 후 분석 실행", type="primary", use_container_width=True, key="ws_stata_run"):
                    if not _code.strip():
                        st.warning("분석 코드를 입력하세요.")
                    elif not st.session_state.get("_llm_ready"):
                        st.warning("코드 해석에 LLM API 키가 필요합니다 (사이드바 설정 또는 admin 전역 키).")
                    else:
                        with st.spinner("코드 해석 → 동등 분석 실행 중 (실 데이터)..."):
                            _sr = _ws_stata(_code)
                        if _sr.get("error"):
                            st.error(_sr["error"])
                        else:
                            _spec = _sr.get("spec", {})
                            st.session_state["ws_paper_view"] = "📊 통계 결과"
                            st.success(f"✅ 분석 완료 — outcome={_spec.get('outcome')}, analysis={_spec.get('analysis')}. 오른쪽 '📊 통계 결과'에서 확인·복사·워드 저장하세요.")
                            st.rerun()

        # ═══════════ 우측: 논문 (편집/미리보기/통계 결과) ═══════════
        with col_paper:
            _filled = sum(1 for _k, _ in _WS_KEYS if (st.session_state.get(f"ws_{_k}") or "").strip())
            ph1, ph2 = st.columns([2, 3])
            with ph1:
                st.markdown(f"<div style='font-size:13px;font-weight:700;color:#E5E7EB;'>📑 논문 <span style='color:#64748B;font-weight:400;'>({_filled}/{len(_WS_KEYS)})</span></div>", unsafe_allow_html=True)
            with ph2:
                _paper_view = st.radio(
                    "뷰", ["📝 편집", "👁 미리보기", "📊 통계 결과"], horizontal=True,
                    key="ws_paper_view", label_visibility="collapsed",
                )
            with st.container(height=440, border=True):
                if _paper_view == "👁 미리보기":
                    _pv = _ws_preview()
                    st.markdown(_pv if _pv else "_아직 내용이 없습니다. 왼쪽 AI에게 요청하세요._")
                elif _paper_view == "📊 통계 결과":
                    _sr = st.session_state.get("stat_result_for_paper")
                    if not _sr:
                        st.markdown("_아직 통계 결과가 없습니다. 왼쪽 **📊 통계 코드** 모드에서 코드를 붙여넣고 Run 하세요._")
                    else:
                        try:
                            from src.export.table_builder import (
                                stat_result_to_table1_markdown,
                                stat_result_to_table2_markdown,
                            )
                            _t1 = stat_result_to_table1_markdown(_sr)
                            _t2 = stat_result_to_table2_markdown(_sr)
                            st.markdown(_t1)
                            st.markdown("")
                            st.markdown(_t2)
                            _figs = st.session_state.get("ws_figures") or {}
                            for _name, _fd in _figs.items():
                                if isinstance(_fd, dict) and _fd.get("png_bytes"):
                                    st.image(_fd["png_bytes"], caption=_fd.get("caption", _name), use_container_width=True)
                            with st.expander("📋 표 마크다운 복사 (논문 붙여넣기용)"):
                                st.code(_t1 + "\n\n" + _t2, language="markdown")
                        except Exception as _e:
                            st.error(f"표 생성 오류: {_e}")
                else:  # 📝 편집
                    # State Registry: 토글 키(ws_lock_*)가 잠금 진실원본. ws_status는 거기서 파생.
                    _stmap = st.session_state.setdefault("ws_status", {})
                    for _k, _label in _WS_KEYS:
                        _has = bool((st.session_state.get(f"ws_{_k}") or "").strip())
                        _locked = bool(st.session_state.get(f"ws_lock_{_k}", False))
                        _badge = "🔒 잠금" if _locked else ("🟡 초안" if _has else "")
                        _lc1, _lc2 = st.columns([5, 1])
                        with _lc1:
                            st.text_area(f"{_label} {_badge}", key=f"ws_{_k}", height=55 if _k == "title" else 110)
                        with _lc2:
                            st.markdown("<div style='height:26px;'></div>", unsafe_allow_html=True)
                            _locked = st.toggle("🔒", key=f"ws_lock_{_k}",
                                                help="켜면 잠금: 자동 생성이 이 섹션을 못 덮어씀 (drift 차단)")
                        _stmap[_k] = "locked" if _locked else ("draft" if _has else "empty")
            wsd1, wsd2, wsd3 = st.columns(3)
            with wsd1:
                if st.button("💾 저장", use_container_width=True, key="ws_save_draft",
                             help="계정에 영속 저장 — 다음 접속/재시작에도 유지"):
                    # State Registry를 단일 상태원본으로 사용 (JSON AST 영속화)
                    from src.research.research_state import ResearchState as _RS, SECTION_KEYS as _SK
                    _rs = _RS.from_session(st.session_state, owner_email=_u.get("email", ""))
                    _rs.paper_id = st.session_state.get("ws_paper_id")
                    _secs = {_k: _rs.get_section(_k) for _k in _SK}
                    _meta = {**_ws_study_info(),
                             "_status": {_k: _rs.status_of(_k) for _k in _SK},
                             "_state": _rs.to_dict()}  # 캐노니컬 AST
                    _pid = _wps.save_paper(_u.get("email", ""), _secs, meta=_meta,
                                           paper_id=_rs.paper_id)
                    st.session_state["ws_paper_id"] = _pid
                    st.session_state["draft"] = _ws_preview()
                    # OpenKB식 누적 위키 흡수 — LLM 호출이라 저장을 막지 않게 백그라운드 스레드로.
                    try:
                        _wtext = _ws_preview()
                        if len(_wtext) > 150:
                            import threading as _th
                            _w_email = _u.get("email", "")
                            _w_title = st.session_state.get("ws_title", "") or "논문 초안"
                            def _bg_wiki(_t=_wtext, _ti=_w_title, _e=_w_email):
                                try:
                                    from src.knowledge.research_wiki import ResearchWiki
                                    ResearchWiki(owner_email=_e).add_source(_t, title=_ti, source_type="draft")
                                except Exception:
                                    pass
                            _th.Thread(target=_bg_wiki, daemon=True).start()
                    except Exception:
                        pass
                    st.success("저장됨 (다음 접속에도 유지 · 지식 위키에 백그라운드 누적)")
            with wsd2:
                st.download_button("⬇ 논문 TXT", _ws_preview() or " ", file_name="paper_draft.txt",
                                   use_container_width=True, key="ws_dl_txt")
            with wsd3:
                _sr2 = st.session_state.get("stat_result_for_paper")
                _docx_bytes = b""
                if _sr2:
                    try:
                        from src.export.table_builder import stat_result_to_tables_docx_bytes
                        _docx_bytes = stat_result_to_tables_docx_bytes(_sr2)
                    except Exception:
                        _docx_bytes = b""
                st.download_button("⬇ 표 워드(DOCX)", _docx_bytes or b" ", file_name="tables.docx",
                                   use_container_width=True, disabled=not _docx_bytes, key="ws_dl_docx")

    # ── 글쓰기 스타일 (학습 + 관리) ───────────────────────────────────
    elif page == "글쓰기 스타일":
        st.markdown("<h2 style='color:#e6edf3;'>✍️ 글쓰기 스타일</h2>", unsafe_allow_html=True)
        st.info(
            "AI가 정해진 스타일로만 쓰는 게 아니라, **본인 논문을 학습시켜 본인 스타일**로 쓸 수 있습니다. "
            "조유선 스타일은 기본 제공(공용)이고, 본인 논문을 올리면 글쓰기 구조·문체·어휘를 추출해 "
            "'내 스타일'로 저장됩니다. (학습 = 추출/구조화, 적용 = 작성 시 템플릿 선택 — 분리 구조)"
        )
        _email = _u.get("email", "")
        _is_adm = st.session_state.get("_is_admin", False)

        from src.profile.author_profile import list_styles
        _tab_learn, _tab_manage = st.tabs(["🧠 내 스타일 학습", "📚 스타일 목록"])

        # ── A. 스타일 학습 (추출/구조화) ──
        with _tab_learn:
            st.markdown("#### 본인 논문으로 스타일 학습")
            _style_name = st.text_input(
                "스타일 이름", value=f"{_u.get('name','내') } 스타일",
                key="style_learn_name", help="이 이름으로 스타일이 저장됩니다 (예: '홍길동 스타일')",
            )
            _src_tab1, _src_tab2 = st.tabs(["파일 업로드", "텍스트 붙여넣기"])
            _paper_text = ""
            _paper_title = ""
            with _src_tab1:
                _sup = st.file_uploader("논문 파일 (DOCX/PDF/TXT)", type=["txt", "docx", "pdf", "md"], key="style_up")
                if _sup is not None:
                    try:
                        from src.ingestion.paper_ingester import PaperIngester
                        _p = PaperIngester().ingest_bytes(_sup.getvalue(), _sup.name)
                        _paper_text = _p.raw_text
                        _paper_title = _p.title or _sup.name
                        st.caption(f"불러옴: {_sup.name} ({len(_paper_text):,}자)")
                    except Exception as _e:
                        st.error(f"파싱 오류: {_e}")
            with _src_tab2:
                _pt = st.text_area("논문 전문 붙여넣기", height=220, key="style_paste")
                if _pt.strip():
                    _paper_text = _pt
                    _paper_title = _pt[:40]

            if st.button("🧠 이 논문으로 스타일 학습", type="primary", key="style_learn_btn"):
                if not _paper_text.strip():
                    st.warning("학습할 논문 내용을 입력하세요.")
                elif not st.session_state.get("_llm_ready"):
                    st.warning("LLM API 키가 필요합니다 (스타일 분석에 사용).")
                else:
                    try:
                        from src.profile.author_profile import AuthorProfile
                        with st.spinner("글쓰기 스타일 분석 중 (문체·방법론·구조·어휘 추출)..."):
                            _ap = AuthorProfile(_style_name, owner_email=_email)
                            _res = _ap.analyse_paper(_paper_text, paper_title=_paper_title)
                        st.success(f"✅ '{_style_name}' 스타일 학습 완료! 작성 시 선택할 수 있습니다.")
                        _prof = _ap.get_profile()
                        _an = _res.get("analysis", {})
                        cws, cme = st.columns(2)
                        with cws:
                            st.markdown("**문체 (writing_style)**")
                            st.json(_prof.get("writing_style", {}))
                        with cme:
                            st.markdown("**방법론 (methodology)**")
                            st.json(_prof.get("methodology", {}))
                        st.caption(f"학습 논문 누적: {len(_prof.get('papers_analysed', []))}편 (많을수록 정확)")
                    except Exception as _e:
                        st.error(f"스타일 학습 오류: {_e}")

        # ── 스타일 목록 ──
        with _tab_manage:
            st.markdown("#### 사용 가능한 스타일")
            _styles = list_styles(owner_email=_email, all_styles=_is_adm)
            if not _styles:
                st.caption("아직 스타일이 없습니다. '내 스타일 학습'에서 논문을 올려보세요.")
            for _s in _styles:
                _tag = "🌐 공용" if _s["shared"] else f"👤 {_s['owner']}"
                st.markdown(
                    f"- **{_s['name']}** ({_tag}) — 학습 논문 {_s['papers_analysed']}편"
                )

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
        _show_topic_banner()
        st.info("전체 논문 생산 프로세스 통합 관리. 각 단계를 순서대로 진행하세요.")
        # 단계별 상태 표시
        has_topic = bool(st.session_state.get("selected_topic"))
        has_novelty = "novelty_result" in st.session_state
        has_feas = "feasibility_result" in st.session_state
        has_draft = "draft" in st.session_state
        pipeline_steps = [
            ("1단계", "📚 연구 주제 생성", "연구 주제 생성", has_topic, "주제를 생성하고 하나를 선택하세요", "primary"),
            ("2단계", "🔍 신규성 확인", "신규성 확인", has_novelty, "PubMed로 기존 연구 유사도 확인", "secondary"),
            ("3단계", "✅ 타당성 검증", "논문 설계 & 타당성", has_feas, "데이터셋 변수 기반 연구 실현 가능성 확인", "secondary"),
            ("4단계", "📝 논문 작성", "논문 작성", has_draft, "조유선 스타일 논문 초안 자동 생성", "secondary"),
        ]
        for step_n, label, target, done, desc, btn_type in pipeline_steps:
            status_icon = "✅" if done else "⬜"
            sc1, sc2, sc3 = st.columns([1, 5, 2])
            with sc1:
                st.markdown(f"<div style='text-align:center;padding-top:8px;font-size:20px;'>{status_icon}</div>", unsafe_allow_html=True)
            with sc2:
                st.markdown(f"**{step_n}: {label}**  \n<span style='font-size:12px;color:#64748B;'>{desc}</span>", unsafe_allow_html=True)
            with sc3:
                if st.button(label if not done else f"{label} (재실행)", key=f"_pipe_{target}", use_container_width=True,
                             type="primary" if not done else "secondary"):
                    _nav(target)

        st.divider()
        st.markdown("### 원스톱 자동 파이프라인")

        # 자산화된 data/raw에서 자동 로드 (업로드 강요 금지 — 데이터 이미 있음)
        raw_df_available = _ensure_raw_df(st.session_state.get("auto_dataset", "KYRBS"))
        if raw_df_available is not None:
            ds_loaded = st.session_state.get("raw_dataset", "원시자료")
            st.success(f"실제 원시자료 준비됨: {ds_loaded} ({len(raw_df_available):,}명) — data/raw 자동로드")
        else:
            st.warning("data/raw에 원시자료가 없습니다 (scripts/download_kyrbs.py로 다운로드).")

        auto_col1, auto_col2 = st.columns(2)
        with auto_col1:
            auto_dataset = st.selectbox("데이터셋", ["KYRBS", "KNHANES"], key="auto_dataset")
            auto_focus = st.text_input("연구 포커스", placeholder="예: 수면 부족과 우울감", key="auto_focus")
        with auto_col2:
            auto_journal = st.text_input("목표 저널", value="J Korean Med Sci", key="auto_journal")
            auto_docx = st.checkbox("DOCX 저장", value=True, key="auto_docx")

        adv_col1, adv_col2, adv_col3 = st.columns(3)
        with adv_col1:
            auto_deep = st.checkbox(
                "🔬 Deep Research", value=False, key="auto_deep",
                help="자율 반복 PubMed 탐색으로 근거 보강 (Phase A, 추가 ~2분)",
            )
        with adv_col2:
            auto_parallel = st.checkbox(
                "⚡ 병렬 처리", value=True, key="auto_parallel",
                help="PMC 다운로드 + 신규성 확인 동시 실행 (Phase B)",
            )
        with adv_col3:
            auto_revise_full = st.checkbox(
                "🔄 자동 재작성", value=False, key="auto_revise_full",
                help="동료 심사 후 약점 섹션 자동 재작성 (추가 ~1분)",
            )

        if st.button("전체 자동 실행 (주제→통계→논문→동료심사)", type="primary", key="auto_run_full"):
            if not auto_focus:
                st.error("연구 포커스를 입력하세요.")
            elif raw_df_available is None:
                st.error("실제 원시자료를 먼저 업로드하세요 (왼쪽 사이드바 '📂 원시자료 업로드').")
            else:
                with st.spinner("전체 파이프라인 실행 중... (수 분 소요)"):
                    try:
                        from src.research.research_pipeline import ResearchPipeline
                        rp = ResearchPipeline()
                        full_result = rp.run_full(
                            dataset_name=auto_dataset,
                            focus=auto_focus,
                            study_info_template={"journal": auto_journal},
                            df=raw_df_available,
                            export_docx=auto_docx,
                            deep_research=auto_deep,
                            parallel=auto_parallel,
                            auto_revise=auto_revise_full,
                        )
                        st.session_state["draft"] = full_result["draft"]
                        st.session_state["peer_review"] = full_result["review"]
                        st.session_state["stat_result_for_paper"] = full_result["stat_result"]
                        if full_result.get("docx_path"):
                            st.session_state["draft_docx_path"] = full_result["docx_path"]

                        review = full_result["review"]
                        st.success(
                            f"완료! 논문 작성 완료 — 동료심사 {review.get('total_score',0)}/100점 "
                            f"({review.get('grade','?')})"
                        )
                        st.info("왼쪽 메뉴 '논문 작성'에서 초안 및 심사 결과를 확인하세요.")
                        _log("auto_run_full", {"focus": auto_focus, "dataset": auto_dataset}, "전체 자동 실행 완료")
                    except FileNotFoundError as e:
                        st.error(str(e))
                    except Exception as e:
                        st.error(f"오류: {e}")
                        import traceback; st.code(traceback.format_exc())

    # ── 연구 주제 생성 ────────────────────────────────────────────────
    elif page == "연구 주제 생성":
        st.markdown("<h2 style='color:#e6edf3;'>📚 연구 주제 생성</h2>", unsafe_allow_html=True)
        _flow_stepbar("연구 주제 생성")
        _show_topic_banner()

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
                        import traceback
                        st.error(f"오류: {e}")
                        st.code(traceback.format_exc())

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

        _flow_next("연구 주제 생성")
        _show_history("연구 주제 생성")

    # ── 신규성 확인 ───────────────────────────────────────────────────
    elif page == "신규성 확인":
        st.markdown("<h2 style='color:#e6edf3;'>🔍 신규성 확인 (PubMed)</h2>", unsafe_allow_html=True)
        _flow_stepbar("신규성 확인")
        _show_topic_banner()
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
                        # 방어적 타입 강제: Streamlit 세션 상태에 파일/객체가 들어올 수 있음
                        exposure_val = "" if exposure is None else str(exposure)
                        outcome_val = "" if outcome is None else str(outcome)
                        population_val = "" if population is None else str(population)

                        result = _get_cached_novelty_checker().check(
                            topic=str(title), exposure=exposure_val,
                            outcome=outcome_val, population=population_val,
                        )
                    except Exception as e:
                        # 특별히 closed-file 관련 ValueError가 올라오면 입력값을 강제 변환하고 재시도
                        msg = str(e)
                        if isinstance(e, ValueError) and ("closed file" in msg or "I/O operation on closed file" in msg):
                            _log.warning("Novelty check failed with closed-file error; coercing session_state fields and retrying")
                            try:
                                # coerce possible structured session values
                                sel = st.session_state.get("selected_topic", {}) or {}
                                title2 = str(sel.get("title", title)) if sel else str(title)
                                exposure2 = str(sel.get("exposure", exposure_val) if sel else exposure_val)
                                outcome2 = str(sel.get("outcome", outcome_val) if sel else outcome_val)
                                population2 = str(sel.get("population", population_val) if sel else population_val)
                                result = _get_cached_novelty_checker().check(
                                    topic=title2, exposure=exposure2, outcome=outcome2, population=population2
                                )
                            except Exception as e2:
                                st.error(f"오류(재시도 실패): {e2}")
                                import traceback; st.code(traceback.format_exc())
                                result = None
                        else:
                            st.error(f"오류: {e}")
                            import traceback; st.code(traceback.format_exc())
                            result = None

                    if result:
                        st.session_state["novelty_result"] = result
                        _log("check_novelty", {"title": title},
                             f"신규성 점수 {result.get('novelty_score',0)}/10: {title}", result)
                        page_context.update({
                            "novelty_score": result.get("novelty_score", 0),
                            "gap": result.get("gap_identified", ""),
                        })

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

        # 신규성 확인 완료 후 다음 단계 CTA
        if "novelty_result" in st.session_state:
            st.divider()
            nc1, nc2, nc3 = st.columns([2, 2, 2])
            with nc1:
                _next_step_btn("논문 타당성 검증", "논문 설계 & 타당성", "_nov_to_feas")
            with nc2:
                _next_step_btn("논문 작성 바로 이동", "논문 작성", "_nov_to_write")
            with nc3:
                if st.session_state.get("selected_topic") and st.button("🗑 주제 초기화", key="_nov_clear"):
                    for k in ["selected_topic", "novelty_result", "feasibility_result", "draft"]:
                        st.session_state.pop(k, None)
                    st.rerun()

        _flow_next("신규성 확인")
        _show_history("신규성 확인")

    # ── 논문 설계 & 타당성 ────────────────────────────────────────────
    elif page == "논문 설계 & 타당성":
        st.markdown("<h2 style='color:#e6edf3;'>🟢 논문 설계 & 타당성 검증</h2>", unsafe_allow_html=True)
        _flow_stepbar("논문 설계 & 타당성")
        _show_topic_banner()
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
                    st.session_state["feasibility_result"] = result  # 세션에 저장 → 배너 갱신
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

        # 타당성 검증 완료 후 다음 단계 CTA
        if "feasibility_result" in st.session_state:
            st.divider()
            fc1, fc2 = st.columns([2, 2])
            with fc1:
                _next_step_btn("논문 작성으로 이동", "논문 작성", "_feas_to_write")
            with fc2:
                _next_step_btn("데이터 분석 도구", "데이터 분석", "_feas_to_data")

        _flow_next("논문 설계 & 타당성")
        _show_history("논문 설계 & 타당성")

    # ── 원시자료 업로드 ───────────────────────────────────────────────
    elif page == "원시자료 업로드":
        st.markdown("<h2 style='color:#e6edf3;'>📂 KYRBS / KNHANES 원시자료 업로드</h2>", unsafe_allow_html=True)
        _flow_stepbar("원시자료 업로드")
        st.info("질병관리청 공식 원시자료(.sav) 또는 CSV를 업로드하면 표준 스키마로 자동 변환해 분석에 사용합니다.")

        # 다운로드 안내
        with st.expander("📋 원시자료 다운로드 방법 (클릭하여 열기)", expanded=False):
            from src.data.kyrbs_raw_loader import download_instructions
            st.markdown(download_instructions())

        st.divider()

        # 데이터셋 선택
        raw_dataset = st.radio("데이터셋 선택", ["KYRBS (청소년건강행태조사)", "KNHANES (국민건강영양조사)"], horizontal=True)
        is_kyrbs = "KYRBS" in raw_dataset

        uploaded_raw = st.file_uploader(
            "원시자료 파일 업로드 (.sav / .csv / .xlsx)",
            type=["sav", "csv", "xlsx", "xls"],
            help="질병관리청에서 다운로드한 원시자료 파일을 그대로 업로드하세요.",
        )

        if uploaded_raw is not None:
            with st.spinner(f"{'KYRBS' if is_kyrbs else 'KNHANES'} 원시자료 처리 중..."):
                try:
                    from src.data.kyrbs_raw_loader import KYRBSLoader, KNHANESLoader
                    loader = KYRBSLoader() if is_kyrbs else KNHANESLoader()
                    file_bytes = uploaded_raw.read()
                    df_raw, meta = loader.load_bytes(file_bytes, uploaded_raw.name)

                    # 세션에 저장
                    st.session_state["raw_df"] = df_raw
                    st.session_state["raw_meta"] = meta
                    st.session_state["raw_dataset"] = "KYRBS" if is_kyrbs else "KNHANES"
                    st.session_state["analysis_df"] = df_raw  # 통계 분석 탭과 공유

                    st.success(f"✅ 로드 완료: {df_raw.shape[0]:,}행 × {df_raw.shape[1]}열 (매핑 변수: {len(meta['mapped_vars'])}개)")

                    # 경고 표시
                    if meta.get("warnings"):
                        for w in meta["warnings"]:
                            st.warning(w)

                except ImportError as e:
                    st.error(str(e))
                    st.code("pip install pyreadstat")
                except Exception as e:
                    st.error(f"파일 처리 오류: {e}")
                    import traceback; st.code(traceback.format_exc())

        # 로드된 데이터 표시
        if "raw_df" in st.session_state:
            df_raw = st.session_state["raw_df"]
            meta = st.session_state["raw_meta"]
            ds_name = st.session_state.get("raw_dataset", "?")

            st.divider()
            st.markdown(f"### 로드된 {ds_name} 원시자료")

            # 주요 지표
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("총 대상자", f"{len(df_raw):,}명")
            m2.metric("매핑 변수", f"{len(meta['mapped_vars'])}개")
            m3.metric("원본 총 열", f"{meta.get('total_raw_cols', '?')}개")
            m4.metric("미매핑", f"{len(meta.get('unmapped_raw', []))}개")

            tab_preview, tab_vars, tab_desc, tab_manual = st.tabs([
                "📊 데이터 미리보기", "🔗 변수 매핑 결과", "📈 기술통계", "⚙️ 수동 변수 지정"
            ])

            with tab_preview:
                st.dataframe(df_raw.head(20), use_container_width=True)
                import io
                csv_buf = io.StringIO()
                df_raw.to_csv(csv_buf, index=False, encoding="utf-8-sig")
                st.download_button(
                    "📥 표준화 CSV 다운로드",
                    data=csv_buf.getvalue().encode("utf-8-sig"),
                    file_name=f"{ds_name}_standardized.csv",
                    mime="text/csv",
                )

            with tab_vars:
                st.markdown("**자동 매핑된 변수**")
                import pandas as pd
                mapping_rows = [
                    {"표준 변수명": k, "원시 컬럼명": v}
                    for k, v in meta.get("raw_to_std", {}).items()
                ]
                if mapping_rows:
                    st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True)
                else:
                    st.warning("매핑된 변수가 없습니다. 수동 지정 탭을 이용하세요.")

                if meta.get("warnings"):
                    st.markdown("**매핑 경고**")
                    for w in meta["warnings"]:
                        st.warning(w)

            with tab_desc:
                from src.data.kyrbs_raw_loader import KYRBSLoader as _KL
                desc = _KL().describe(df_raw)
                if desc:
                    desc_rows = []
                    for col, stats in desc.items():
                        row = {"변수": col}
                        if "mean" in stats:
                            row.update({"N": stats["n"], "결측": stats["missing"],
                                        "평균": stats["mean"], "표준편차": stats["std"],
                                        "최솟값": stats["min"], "최댓값": stats["max"]})
                        else:
                            row["N"] = stats.get("n", "")
                            row["결측"] = stats.get("missing", "")
                            row["범주"] = str(list(stats.get("categories", {}).keys())[:5])
                        desc_rows.append(row)
                    st.dataframe(pd.DataFrame(desc_rows), use_container_width=True)
                else:
                    st.info("기술통계 정보 없음")

            with tab_manual:
                st.markdown("자동 매핑에 실패한 변수를 직접 지정합니다.")

                # 원본 파일의 컬럼 목록을 보여주기 위해 재업로드가 필요하지만
                # 이미 raw_df가 있으면 컬럼 표시
                raw_cols_available = list(df_raw.columns)

                key_vars = {
                    "sex": "성별 (1=남/2=여)",
                    "weight_var": "표본 가중치",
                    "strata": "층화변수",
                    "cluster": "집락변수",
                    "depression": "우울감 경험 (이진)",
                    "suicidal": "자살 생각 (이진)",
                    "sleep_hours": "수면 시간",
                    "smoking": "흡연 여부",
                    "screen_time": "스크린 타임",
                }
                if not is_kyrbs:
                    key_vars = {
                        "sex": "성별",
                        "weight_var": "표본 가중치",
                        "strata": "층화변수",
                        "cluster": "집락변수",
                        "diabetes": "당뇨 여부",
                        "hypertension": "고혈압 여부",
                        "bmi": "체질량지수",
                        "sbp": "수축기 혈압",
                    }

                manual_map = {}
                for std_name, label in key_vars.items():
                    default = std_name if std_name in raw_cols_available else None
                    opts = ["(선택 안 함)"] + raw_cols_available
                    sel = st.selectbox(
                        f"{label} → 원시 컬럼",
                        opts,
                        index=(opts.index(default) if default in opts else 0),
                        key=f"manual_{std_name}",
                    )
                    if sel != "(선택 안 함)":
                        manual_map[std_name] = sel

                if st.button("수동 매핑 적용", type="primary"):
                    if manual_map:
                        from src.data.kyrbs_raw_loader import KYRBSLoader as _KL2
                        # 세션에서 원본 raw df가 있어야 함
                        # 이 경우 이미 표준화된 df를 다시 manual_map으로 덮어씀
                        for std, raw_col in manual_map.items():
                            if raw_col in df_raw.columns:
                                df_raw[std] = df_raw[raw_col]
                        st.session_state["raw_df"] = df_raw
                        st.session_state["analysis_df"] = df_raw
                        st.success(f"✅ 수동 매핑 적용: {list(manual_map.keys())}")
                        st.rerun()

            st.divider()
            if st.button("🔬 이 데이터로 StatBridge 통계 분석 시작", type="primary", key="raw_to_stat"):
                _nav("데이터 분석")

    # ── 데이터 분석 ───────────────────────────────────────────────────
    elif page == "데이터 분석":
        st.markdown("<h2 style='color:#e6edf3;'>🔵 데이터 분석</h2>", unsafe_allow_html=True)
        _flow_stepbar("데이터 분석")
        tab_lib, tab_run, tab_statbridge = st.tabs(["📚 데이터셋 라이브러리", "📊 통계 분석 실행", "🧬 StatBridge 논문통계"])

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

                def _show_figure(fig, label: str):
                    """그림을 인라인 표시 + PNG 다운로드 버튼."""
                    if fig is None:
                        return
                    from src.visualization import MedicalVisualizer
                    img_bytes = MedicalVisualizer.figure_bytes(fig, fmt="png", dpi=150)
                    st.image(img_bytes, use_container_width=True)
                    st.download_button(
                        label=f"⬇ PNG 다운로드 ({label})",
                        data=img_bytes,
                        file_name=f"{label}.png",
                        mime="image/png",
                    )

                if analysis_type == "기술통계 (Descriptive Stats)":
                    sel_cols = st.multiselect("분석할 변수", cols, default=cols[:5])
                    if st.button("▶ 실행", type="primary") and sel_cols:
                        from src.statistics.medical_stats import MedicalStatistics
                        from src.visualization import MedicalVisualizer
                        result_df = MedicalStatistics.descriptive_stats(df[sel_cols])
                        st.dataframe(result_df, use_container_width=True)
                        fig = MedicalVisualizer.auto_figure("descriptive", df, cols=sel_cols)
                        _show_figure(fig, f"descriptive_{'_'.join(sel_cols[:3])}")
                        _log("stats_descriptive", {"cols": sel_cols}, f"기술통계: {sel_cols}")

                elif analysis_type == "독립표본 t검정 (Independent t-test)":
                    val_col = st.selectbox("연속형 변수", cols)
                    grp_col = st.selectbox("그룹 변수 (2개 그룹)", cols)
                    if st.button("▶ 실행", type="primary"):
                        from src.statistics.medical_stats import MedicalStatistics
                        from src.visualization import MedicalVisualizer
                        res = MedicalStatistics.independent_t_test(df, val_col, grp_col)
                        st.json(res)
                        fig = MedicalVisualizer.auto_figure("ttest", df, result=res,
                                                            val_col=val_col, grp_col=grp_col)
                        _show_figure(fig, f"ttest_{val_col}_by_{grp_col}")
                        _log("stats_ttest", {"val": val_col, "grp": grp_col}, f"t-test: {val_col} by {grp_col}")

                elif analysis_type == "카이제곱 검정 (Chi-square)":
                    var1 = st.selectbox("변수 1", cols)
                    var2 = st.selectbox("변수 2", cols, index=min(1, len(cols)-1))
                    if st.button("▶ 실행", type="primary"):
                        from src.statistics.medical_stats import MedicalStatistics
                        from src.visualization import MedicalVisualizer
                        res = MedicalStatistics.chi_square_test(df, var1, var2)
                        st.json(res)
                        fig = MedicalVisualizer.auto_figure("chi2", df, result=res,
                                                            var1=var1, var2=var2)
                        _show_figure(fig, f"chi2_{var1}_vs_{var2}")
                        _log("stats_chi2", {"var1": var1, "var2": var2}, f"chi2: {var1} vs {var2}")

                elif analysis_type == "일원분산분석 (One-way ANOVA)":
                    val_col = st.selectbox("연속형 변수", cols)
                    grp_col = st.selectbox("그룹 변수", cols)
                    if st.button("▶ 실행", type="primary"):
                        from src.statistics.medical_stats import MedicalStatistics
                        from src.visualization import MedicalVisualizer
                        res = MedicalStatistics.one_way_anova(df, val_col, grp_col)
                        st.json(res)
                        fig = MedicalVisualizer.auto_figure("anova", df, result=res,
                                                            val_col=val_col, grp_col=grp_col)
                        _show_figure(fig, f"anova_{val_col}_by_{grp_col}")
                        _log("stats_anova", {"val": val_col, "grp": grp_col}, f"ANOVA: {val_col} by {grp_col}")

                elif analysis_type == "피어슨 상관 (Pearson Correlation)":
                    sel_cols = st.multiselect("변수 선택 (2개 이상)", cols, default=cols[:4])
                    if st.button("▶ 실행", type="primary") and len(sel_cols) >= 2:
                        from src.visualization import MedicalVisualizer
                        corr = df[sel_cols].corr()
                        st.dataframe(corr.style.background_gradient(cmap="coolwarm"), use_container_width=True)
                        fig = MedicalVisualizer.auto_figure("correlation", df, cols=sel_cols)
                        _show_figure(fig, f"corr_{'_'.join(sel_cols[:4])}")
                        _log("stats_corr", {"cols": sel_cols}, f"상관분석: {sel_cols}")

                elif analysis_type == "로지스틱 회귀 (Logistic Regression)":
                    outcome = st.selectbox("결과변수 (이진)", cols)
                    predictors = st.multiselect("예측변수", [c for c in cols if c != outcome])
                    if st.button("▶ 실행", type="primary") and predictors:
                        from src.statistics.medical_stats import MedicalStatistics
                        from src.visualization import MedicalVisualizer
                        res = MedicalStatistics.logistic_regression(df, outcome, predictors)
                        st.dataframe(res, use_container_width=True)
                        fig = MedicalVisualizer.auto_figure("logistic", df, result=res)
                        _show_figure(fig, f"logistic_{outcome}")
                        _log("stats_logistic", {"outcome": outcome, "predictors": predictors}, f"로지스틱: {outcome}")

                elif analysis_type == "선형 회귀 (Linear Regression)":
                    outcome = st.selectbox("결과변수", cols)
                    predictors = st.multiselect("예측변수", [c for c in cols if c != outcome])
                    if st.button("▶ 실행", type="primary") and predictors:
                        from src.statistics.medical_stats import MedicalStatistics
                        from src.visualization import MedicalVisualizer
                        res = MedicalStatistics.linear_regression(df, outcome, predictors)
                        st.json(res)
                        fig = MedicalVisualizer.auto_figure("linear", df, result=res,
                                                            outcome=outcome, predictors=predictors)
                        _show_figure(fig, f"linear_{outcome}")
                        _log("stats_linear", {"outcome": outcome, "predictors": predictors}, f"선형회귀: {outcome}")

        with tab_statbridge:
            st.markdown("**StatBridge** — KYRBS/KNHANES 데이터를 로지스틱 회귀로 분석해 논문에 바로 주입할 수 있는 OR/CI를 생성합니다.")
            sb_col1, sb_col2 = st.columns([1, 1])
            with sb_col1:
                sb_dataset = st.selectbox("데이터셋", ["KYRBS", "KNHANES"], key="sb_dataset")
                sb_n = st.slider("합성 데이터 크기 (실제 데이터 미업로드 시)", 1000, 10000, 5000, step=500)
                sb_outcome = st.selectbox("결과변수 (Outcome)", [
                    "depression", "suicidal", "obesity", "smoking", "alcohol", "sleep_hours",
                    "diabetes", "hypertension", "metabolic_syn",
                ], key="sb_outcome")
                sb_outcome_label = st.text_input("결과변수 한글명", value={
                    "depression": "우울감 경험", "suicidal": "자살 생각", "obesity": "비만",
                    "smoking": "흡연", "alcohol": "음주", "sleep_hours": "수면 시간",
                    "diabetes": "당뇨", "hypertension": "고혈압", "metabolic_syn": "대사 증후군",
                }.get(sb_outcome, sb_outcome))
            with sb_col2:
                if sb_dataset == "KYRBS":
                    all_preds = ["sex", "sleep_hours", "screen_time", "smoking", "alcohol", "stress", "physical_act", "bmi"]
                    all_covs = ["grade", "family_econ", "academic_perf"]
                else:
                    all_preds = ["sex", "age", "bmi", "smoking", "physical_act", "alcohol"]
                    all_covs = ["edu", "income"]
                sb_preds = st.multiselect("예측변수 (Predictors)", all_preds, default=all_preds[:4], key="sb_preds")
                sb_covs = st.multiselect("교란변수 (Covariates)", all_covs, default=all_covs[:2], key="sb_covs")
                sb_subgroup = st.multiselect("층화 분석 변수", ["sex", "grade"] if sb_dataset == "KYRBS" else ["sex", "age"], key="sb_subgroup")

            sb_df = st.session_state.get("analysis_df")
            if sb_df is None:
                sb_df = st.session_state.get("raw_df")
            # 세션 데이터 없으면 자산화된 data/raw에서 자동 로드 (업로드 불필요 — 데이터 이미 있음)
            if sb_df is None:
                try:
                    from src.research.research_pipeline import _find_real_data
                    sb_df = _find_real_data(sb_dataset)
                    if sb_df is not None:
                        st.session_state["raw_df"] = sb_df
                except Exception as _e:
                    st.caption(f"(data/raw 자동로드 시도 실패: {str(_e)[:80]})")
            if sb_df is not None:
                st.info(f"데이터 준비됨: {sb_df.shape[0]:,}행 × {sb_df.shape[1]}열 "
                        f"(data/raw 자동로드 — 업로드 불필요)")

            if st.button("🔬 StatBridge 분석 실행", type="primary", key="sb_run"):
                if not sb_preds:
                    st.error("예측변수를 하나 이상 선택하세요.")
                else:
                    with st.spinner("실제 로지스틱 회귀 분석 중..."):
                        try:
                            from src.data.stat_bridge import StatBridge
                            df_use = sb_df
                            if df_use is None:
                                st.error(
                                    "data/raw에서 원시자료를 찾지 못했습니다. "
                                    "KYRBS/KNHANES .sav가 data/raw에 있는지 확인하세요 "
                                    "(scripts/download_kyrbs.py로 재다운로드 가능)."
                                )
                                st.stop()
                            spec = {
                                "outcome": sb_outcome,
                                "outcome_label": sb_outcome_label,
                                "predictors": sb_preds,
                                "covariates": sb_covs,
                                "analysis": "logistic",
                                "weight_var": "weight_var",
                                "subgroups": sb_subgroup,
                            }
                            result = StatBridge().run(df_use, spec)
                            st.session_state["sb_result"] = result.to_dict()
                            st.success(f"✅ 분석 완료 — n={result.n_total:,}, {sb_outcome_label} {result.outcome_rate:.1f}%")
                        except Exception as e:
                            st.error(f"오류: {e}")
                            import traceback; st.code(traceback.format_exc())

            if "sb_result" in st.session_state:
                r = st.session_state["sb_result"]
                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("총 대상자", f"{r['n_total']:,}명")
                m2.metric("사건 수", f"{r['n_outcome']:,}명")
                m3.metric("발생률", f"{r['outcome_rate']:.1f}%")
                m4.metric("유의 변수", f"{sum(1 for v in r['model_vars'] if v.get('significant'))}개")

                st.markdown("**OR + 95% CI 결과표**")
                import pandas as pd
                rows = []
                for v in r.get("model_vars", []):
                    rows.append({
                        "변수": v.get("label", v.get("variable", "")),
                        "OR": v.get("or_value", ""),
                        "95% CI": f"{v.get('ci_lower','')}–{v.get('ci_upper','')}",
                        "p-value": v.get("p_formatted", v.get("p_value", "")),
                        "유의": "✅" if v.get("significant") else "",
                    })
                if rows:
                    st.dataframe(pd.DataFrame(rows), use_container_width=True)

                st.markdown("**논문 직접 삽입용 통계 요약 (한국어)**")
                st.text_area("논문 삽입 텍스트", value=r.get("paper_summary", ""), height=100, key="sb_summary_text")
                if st.button("📋 이 통계 결과를 '논문 작성'에 사용", key="sb_to_writer"):
                    st.session_state["stat_result_for_paper"] = r
                    _nav("논문 작성")

    # ── 논문 작성 ─────────────────────────────────────────────────────
    elif page == "논문 작성":
        st.markdown("<h2 style='color:#e6edf3;'>📝 조유선 스타일 논문 작성</h2>", unsafe_allow_html=True)
        _flow_stepbar("논문 작성")
        _show_topic_banner()
        st.info("조유선 교수 논문 스타일 시드를 기반으로 논문 초안을 생성합니다.")
        prev = st.session_state.get("selected_topic", {})
        c1, c2 = st.columns(2)
        with c1:
            topic_title = st.text_input("연구 제목", value=prev.get("title", ""))
            # ── 저널 선택 (레지스트리 연동) ─────────────────────────────
            try:
                from src.export.journal_registry import get_registry as _get_jreg
                _jreg = _get_jreg()
                _jlist = _jreg.list_journals()
                _jnames = [f"{j['name']} ({j['abbreviation']})" for j in _jlist] + ["✏️ 직접 입력"]
                _jids   = [j["id"] for j in _jlist] + ["__custom__"]
            except Exception:
                _jnames, _jids = ["✏️ 직접 입력"], ["__custom__"]
            _sel_idx = st.selectbox("목표 저널", range(len(_jnames)), format_func=lambda i: _jnames[i], index=0)
            if _jids[_sel_idx] == "__custom__":
                journal = st.text_input("저널명 직접 입력", placeholder="예: Nutrients, PLOS Medicine")
                journal_id = re.sub(r"[^a-z0-9_]", "_", journal.lower())[:40] if journal else "jkms"
            else:
                journal = _jlist[_sel_idx]["name"]
                journal_id = _jids[_sel_idx]
            # ────────────────────────────────────────────────────────────
            design = st.selectbox("연구 설계", ["Cross-sectional", "Cohort", "Case-control", "RCT"])
        with c2:
            dataset_name = st.text_input("데이터셋", value="KYRBS 2025 (제21차 청소년건강행태조사)")
            sample_size = st.text_input("표본 수", placeholder="예: 54,633")
            survey_year = st.text_input("조사 연도", value="2025")
        results_text = st.text_area("주요 결과 (통계값 포함)", placeholder="예: 스마트폰 주중 4시간 이상 사용군에서 수면 부족 OR=2.34...", height=120)
        section = st.selectbox("작성할 섹션", ["전체 논문", "Abstract", "Introduction", "Methods", "Results", "Discussion"])
        page_context.update({"title": topic_title, "journal": journal, "design": design, "dataset": dataset_name, "results_summary": results_text[:200]})

        # StatBridge 통계 결과가 전달된 경우 알림
        stat_result_for_paper = st.session_state.get("stat_result_for_paper")
        if stat_result_for_paper:
            st.success(f"✅ StatBridge 통계 결과 연동됨 — n={stat_result_for_paper.get('n_total',0):,}, 유의변수 {sum(1 for v in stat_result_for_paper.get('model_vars',[]) if v.get('significant'))}개")
            if st.button("❌ 통계 연동 해제"):
                del st.session_state["stat_result_for_paper"]
                st.rerun()

        pw_col1, pw_col2, pw_col3 = st.columns(3)
        with pw_col1:
            use_stat_inject = st.checkbox(
                "🧬 StatBridge 통계 주입 모드",
                value=stat_result_for_paper is not None,
                help="실제 OR/CI 통계값이 논문 본문에 자동 주입됩니다",
            )
            export_docx = st.checkbox("📄 DOCX 파일도 저장", value=True)
        with pw_col2:
            run_peer_review = st.checkbox("👥 작성 후 동료 심사 자동 실행", value=True)
        with pw_col3:
            auto_revise = st.checkbox(
                "🔄 자동 재작성 루프",
                value=False,
                help="동료 심사 점수 70점 미만 섹션을 자동으로 재작성합니다 (추가 ~1분)",
            )

        pw_adv1, pw_adv2 = st.columns(2)
        with pw_adv1:
            pw_deep = st.checkbox(
                "🔬 Deep Research (자율 탐색)", value=False, key="pw_deep",
                help="자율 반복 PubMed 탐색으로 근거 보강 (Phase A, 추가 ~2분)",
            )
        with pw_adv2:
            pw_parallel = st.checkbox(
                "⚡ 병렬 처리", value=True, key="pw_parallel",
                help="PMC 다운로드 + 신규성 확인 동시 실행 (Phase B)",
            )
        # ── 글쓰기 스타일 선택 (B: 템플릿 적용) ──
        try:
            from src.profile.author_profile import list_styles as _ls
            _avail = _ls(owner_email=_u.get("email", ""), all_styles=st.session_state.get("_is_admin", False))
            _style_opts = [s["name"] for s in _avail] or ["Yoosun Cho"]
        except Exception:
            _style_opts = ["Yoosun Cho"]
        pw_style = st.selectbox(
            "✍️ 글쓰기 스타일", _style_opts, key="pw_style",
            help="조유선(공용) 또는 본인이 학습시킨 스타일로 작성. '글쓰기 스타일'에서 본인 논문 학습 가능.",
        )

        if st.button("✍️ 논문 작성 시작", type="primary"):
            if not topic_title or not results_text:
                st.error("연구 제목과 주요 결과를 입력하세요.")
            else:
                with st.spinner(f"{pw_style} 스타일로 논문 작성 중... (1~2분 소요)"):
                    try:
                        from src.research.research_pipeline import ResearchPipeline
                        topic = {"title": topic_title, "exposure": prev.get("exposure",""), "outcome": prev.get("outcome",""), "population": prev.get("population","")}
                        study_info = {"dataset": dataset_name, "design": design, "sample_size": sample_size, "survey_year": survey_year, "journal": journal}
                        rp = ResearchPipeline(author_name=pw_style)

                        st.session_state["draft_journal_id"] = journal_id
                        if use_stat_inject and stat_result_for_paper:
                            draft, docx_path = rp.write_paper_with_stats(
                                topic, study_info, stat_result_for_paper,
                                export_docx=export_docx, journal_id=journal_id,
                                auto_revise=auto_revise,
                                deep_research=pw_deep, parallel=pw_parallel,
                            )
                            if docx_path:
                                st.session_state["draft_docx_path"] = docx_path
                        elif section == "전체 논문":
                            results = {"summary": results_text}
                            draft = rp.write_paper(topic, study_info, results)
                        else:
                            results = {"summary": results_text}
                            from src.research.paper_writer import PaperWriter
                            from src.profile.author_profile import AuthorProfile
                            from src.library.methods_library import MethodsLibrary
                            from src.library.dataset_library import DatasetLibrary as DL
                            writer = PaperWriter(AuthorProfile("Yoosun Cho"), MethodsLibrary(), DL(), _get_cached_rag_pipeline())
                            draft = writer.write_section(section, topic_title, study_info, results)

                        st.session_state["draft"] = draft
                        # Before/After 비교 UI — auto_revise 시 수정 전후 저장
                        if auto_revise and hasattr(rp, "pre_revise_draft") and hasattr(rp, "post_revise_draft"):
                            pre = rp.pre_revise_draft
                            post = rp.post_revise_draft
                            if pre and post and pre != post:
                                st.session_state["revision_pending"] = True
                                st.session_state["draft_before_revise"] = pre
                                st.session_state["draft_after_revise"] = post
                                st.session_state["draft"] = pre  # 기본값: 원본 유지 (사용자가 선택)
                            else:
                                st.session_state.pop("revision_pending", None)
                        else:
                            st.session_state.pop("revision_pending", None)
                        # 생성된 그림 정보 저장
                        if hasattr(rp, "last_figures") and rp.last_figures:
                            st.session_state["last_figures"] = rp.last_figures
                        from datetime import datetime
                        rp_list = st.session_state.get("recent_projects", [])
                        rp_list.insert(0, {"title": topic_title, "updated": datetime.now().strftime("%Y.%m.%d %H:%M"), "status": "논문 작성 중"})
                        st.session_state["recent_projects"] = rp_list[:10]
                        _log("write_paper", {"title": topic_title, "section": section}, f"{section} 작성 완료: {topic_title}", {"draft_len": len(draft)})
                        st.success("✅ 논문 작성 완료!")

                        if run_peer_review and section in ["전체 논문", "전체"]:
                            with st.spinner("동료 심사 실행 중..."):
                                review = rp.run_peer_review(draft, topic, stat_result=stat_result_for_paper)
                                st.session_state["peer_review"] = review
                    except Exception as e:
                        st.error(f"오류: {e}"); import traceback; st.code(traceback.format_exc())

        if "draft" in st.session_state:
            page_context["현재_초안_길이"] = f"{len(st.session_state['draft'])}자"
            st.divider()
            draft_tabs = st.tabs(["📝 논문 초안", "👥 동료 심사 결과"])
            with draft_tabs[0]:
                st.markdown("<h3 style='color:#e6edf3;'>생성된 논문 초안</h3>", unsafe_allow_html=True)

                # ── Before/After 수정 비교 프리뷰 ──────────────────────────────────
                if st.session_state.get("revision_pending"):
                    st.warning("⚠️ 자동 수정안이 생성되었습니다. 원본과 수정본을 비교하고 선택하세요.")
                    rev_col1, rev_col2 = st.columns(2)
                    with rev_col1:
                        st.markdown("**📄 원본 (수정 전)**")
                        st.text_area(
                            "원본",
                            value=st.session_state.get("draft_before_revise", ""),
                            height=400,
                            key="before_revise_view",
                            disabled=True,
                            label_visibility="collapsed",
                        )
                        if st.button("✅ 원본 유지", key="keep_original", use_container_width=True):
                            st.session_state["draft"] = st.session_state["draft_before_revise"]
                            st.session_state.pop("revision_pending", None)
                            st.success("원본이 확정되었습니다.")
                            st.rerun()
                    with rev_col2:
                        st.markdown("**✏️ 수정본 (AI 개선)**")
                        st.text_area(
                            "수정본",
                            value=st.session_state.get("draft_after_revise", ""),
                            height=400,
                            key="after_revise_view",
                            disabled=True,
                            label_visibility="collapsed",
                        )
                        if st.button("🚀 수정본 적용", key="accept_revision", use_container_width=True,
                                     type="primary"):
                            st.session_state["draft"] = st.session_state["draft_after_revise"]
                            st.session_state.pop("revision_pending", None)
                            st.success("수정본이 확정되었습니다.")
                            st.rerun()
                    # 수동 섹션 재작성 요청
                    st.divider()
                    st.markdown("**🔧 특정 섹션 수동 수정 요청**")
                    man_col1, man_col2 = st.columns([1, 2])
                    with man_col1:
                        man_section = st.selectbox(
                            "수정할 섹션",
                            ["Introduction", "Methods", "Results", "Discussion", "Abstract"],
                            key="manual_revise_section",
                        )
                    with man_col2:
                        man_goal = st.text_input(
                            "수정 목표 (예: '방법론 한계점 추가', '통계치 더 구체적으로')",
                            key="manual_revise_goal",
                        )
                    if st.button("✏️ 섹션 재작성 + 비교 프리뷰", key="manual_revise_btn"):
                        if man_goal.strip():
                            with st.spinner(f"{man_section} 재작성 중..."):
                                try:
                                    from src.llm import get_llm_client
                                    _llm = get_llm_client()
                                    _cur = st.session_state.get("draft", "")
                                    _prompt = (
                                        f"You are editing the {man_section} section of a medical paper.\n\n"
                                        f"GOAL: {man_goal}\n\n"
                                        f"CURRENT PAPER:\n{_cur[:8000]}\n\n"
                                        f"Rewrite ONLY the {man_section} section based on the goal. "
                                        f"Return the complete rewritten section only."
                                    )
                                    _new_section = _llm.generate(_prompt, task="paper_writing")
                                    import re as _re
                                    _new_draft = _re.sub(
                                        rf"(?i)(## {man_section}|# {man_section})[\s\S]*?(?=\n## |\n# |$)",
                                        f"## {man_section}\n{_new_section}\n\n",
                                        _cur, count=1,
                                    )
                                    if _new_draft == _cur:  # 섹션 헤더 없으면 뒤에 추가
                                        _new_draft = _cur + f"\n\n## {man_section} (수정)\n{_new_section}"
                                    st.session_state["draft_before_revise"] = _cur
                                    st.session_state["draft_after_revise"] = _new_draft
                                    st.session_state["revision_pending"] = True
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"재작성 오류: {e}")
                        else:
                            st.warning("수정 목표를 입력하세요.")
                    st.divider()

                draft_val = st.text_area("내용", value=st.session_state["draft"], height=500)
                if draft_val != st.session_state["draft"]:
                    st.session_state["draft"] = draft_val
                dl_col1, dl_col2, dl_col3, dl_col4, dl_col5 = st.columns(5)
                _safe_title = topic_title[:30]
                _dl_jid = st.session_state.get("draft_journal_id", "jkms")
                _xml_slug = re.sub(r"[^\w]", "_", topic_title)[:60]
                with dl_col1:
                    st.download_button("📥 TXT", data=st.session_state["draft"].encode("utf-8"),
                                       file_name=f"draft_{_safe_title}.txt", mime="text/plain")
                with dl_col2:
                    _docx_path = st.session_state.get("draft_docx_path")
                    if _docx_path:
                        try:
                            with open(_docx_path, "rb") as f:
                                docx_bytes = f.read()
                            st.download_button("📄 논문 DOCX", data=docx_bytes,
                                               file_name=f"draft_{_safe_title}_{_dl_jid}.docx",
                                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                        except Exception:
                            st.caption("DOCX 없음")
                    else:
                        st.caption("DOCX 없음")
                with dl_col3:
                    try:
                        from pathlib import Path as _Path
                        _tbl_path = _Path(f"data/drafts/tables/{_safe_title}_tables.docx")
                        if not _tbl_path.exists():
                            _tbl_candidates = list(_Path("data/drafts/tables").glob("*.docx"))
                            if _tbl_candidates:
                                _tbl_path = sorted(_tbl_candidates, key=lambda p: p.stat().st_mtime)[-1]
                        if _tbl_path.exists():
                            st.download_button("📊 Tables DOCX",
                                               data=_tbl_path.read_bytes(),
                                               file_name=f"tables_{_safe_title}.docx",
                                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                        else:
                            st.caption("Tables 없음")
                    except Exception:
                        st.caption("Tables 없음")
                with dl_col4:
                    try:
                        _xml_path = _Path(f"data/journals/references/{_xml_slug}.xml")
                        if _xml_path.exists():
                            st.download_button("📚 EndNote",
                                               data=_xml_path.read_bytes(),
                                               file_name=f"{_safe_title}.xml",
                                               mime="application/xml")
                        else:
                            st.caption("EndNote 없음")
                    except Exception:
                        st.caption("EndNote 없음")
                with dl_col5:
                    try:
                        _bib_path = _Path(f"data/journals/references/{_xml_slug}.bib")
                        if _bib_path.exists():
                            st.download_button("📖 BibTeX",
                                               data=_bib_path.read_bytes(),
                                               file_name=f"{_safe_title}.bib",
                                               mime="text/plain")
                        else:
                            st.caption("BibTeX 없음")
                    except Exception:
                        st.caption("BibTeX 없음")

                # ── 출판용 그림/표 갤러리 (FigureLabs 수준) ──────────────────────
                st.divider()
                st.markdown("**🖼️ 출판용 그림 & 표**")
                _last_figs = st.session_state.get("last_figures", {})
                _fig_names_kr = {
                    "forest_plot": "Forest Plot",
                    "roc_curve": "ROC Curve",
                    "prevalence_bar": "유병률 막대",
                    "subgroup_forest": "서브그룹 Forest",
                    "table1_image": "Table 1",
                    "table2_image": "Table 2",
                    "coefficient_plot": "계수 플롯",
                }
                if _last_figs:
                    _fig_cols = st.columns(min(4, len(_last_figs)))
                    for _fci, (_fk, _fmeta) in enumerate(_last_figs.items()):
                        _col = _fig_cols[_fci % len(_fig_cols)]
                        with _col:
                            _fname_kr = _fig_names_kr.get(_fk, _fk)
                            _png_bytes = _fmeta.get("png_bytes")
                            if _png_bytes:
                                st.image(_png_bytes, caption=_fname_kr, use_container_width=True)
                                st.download_button(
                                    f"⬇️ {_fname_kr} PNG",
                                    data=_png_bytes,
                                    file_name=f"{_fk}_{_safe_title}.png",
                                    mime="image/png",
                                    key=f"dl_fig_{_fk}",
                                )
                                _svg_path = _fmeta.get("svg_path")
                                if _svg_path:
                                    try:
                                        st.download_button(
                                            f"⬇️ {_fname_kr} SVG",
                                            data=_Path(_svg_path).read_bytes(),
                                            file_name=f"{_fk}_{_safe_title}.svg",
                                            mime="image/svg+xml",
                                            key=f"dl_svg_{_fk}",
                                        )
                                    except Exception:
                                        pass
                else:
                    # 기존 forest plot 폴백
                    fg_col1, fg_col2 = st.columns(2)
                    with fg_col1:
                        try:
                            _fig_dir = _Path("data/drafts/figures")
                            _fig_candidates = list(_fig_dir.glob("*_forest.png")) if _fig_dir.exists() else []
                            if _fig_candidates:
                                _fp = sorted(_fig_candidates, key=lambda p: p.stat().st_mtime)[-1]
                                st.image(_fp.read_bytes(), caption="Forest Plot", use_container_width=True)
                                st.download_button(
                                    "🌲 Forest Plot PNG",
                                    data=_fp.read_bytes(),
                                    file_name=f"forest_{_safe_title}.png",
                                    mime="image/png",
                                )
                            else:
                                st.caption("Forest Plot 없음")
                        except Exception:
                            st.caption("Forest Plot 없음")
                    with fg_col2:
                        try:
                            _cl_dir = _Path("data/drafts/cover_letters")
                            _cl_candidates = list(_cl_dir.glob("*.txt")) if _cl_dir.exists() else []
                            if _cl_candidates:
                                _clp = sorted(_cl_candidates, key=lambda p: p.stat().st_mtime)[-1]
                                st.download_button(
                                    "✉️ Cover Letter",
                                    data=_clp.read_bytes(),
                                    file_name=f"cover_{_safe_title}.txt",
                                    mime="text/plain",
                                )
                            else:
                                st.caption("Cover Letter 없음")
                        except Exception:
                            st.caption("Cover Letter 없음")

                # ── STATA do-file ──────────────────────────────────────────
                st.divider()
                stata_col1, stata_col2 = st.columns([1, 3])
                with stata_col1:
                    try:
                        _stata_dir = _Path("data/drafts/stata")
                        _stata_candidates = list(_stata_dir.glob("*.do")) if _stata_dir.exists() else []
                        if _stata_candidates:
                            _stata_path = sorted(_stata_candidates, key=lambda p: p.stat().st_mtime)[-1]
                            st.download_button(
                                "🔢 STATA do-file",
                                data=_stata_path.read_bytes(),
                                file_name=f"{_safe_title}.do",
                                mime="text/plain",
                            )
                        else:
                            # STATA 코드 즉시 생성 버튼
                            if st.button("🔢 STATA 코드 생성"):
                                try:
                                    from src.export.stata_exporter import generate_stata_code
                                    _topic_d = {"title": topic_title, "exposure": prev.get("exposure",""), "outcome": prev.get("outcome",""), "population": prev.get("population","")}
                                    _si_d = {"dataset": dataset_name, "design": design, "sample_size": sample_size}
                                    _spec = {"outcome": prev.get("outcome", "depression"), "predictors": ["sex", "sleep_hours", "screen_time"], "covariates": ["grade", "family_econ"], "analysis": "logistic"}
                                    _stata_code = generate_stata_code(_topic_d, _spec, _si_d)
                                    st.session_state["stata_code"] = _stata_code
                                except Exception as e:
                                    st.error(f"STATA 생성 오류: {e}")
                    except Exception:
                        st.caption("STATA 없음")
                with stata_col2:
                    if st.session_state.get("stata_code"):
                        st.download_button(
                            "💾 STATA 코드 다운로드",
                            data=st.session_state["stata_code"].encode("utf-8"),
                            file_name=f"{_safe_title}.do",
                            mime="text/plain",
                        )
                        with st.expander("STATA 코드 미리보기"):
                            st.code(st.session_state["stata_code"][:2000], language="stata")

            with draft_tabs[1]:
                pr = st.session_state.get("peer_review")
                if pr is None:
                    if st.button("👥 지금 동료 심사 실행", key="run_pr_now"):
                        with st.spinner("동료 심사 중..."):
                            try:
                                from src.research.research_pipeline import ResearchPipeline
                                topic_dict = {"title": topic_title, "exposure": prev.get("exposure",""), "outcome": prev.get("outcome",""), "population": prev.get("population","")}
                                pr = ResearchPipeline().run_peer_review(st.session_state["draft"], topic_dict, stat_result=stat_result_for_paper)
                                st.session_state["peer_review"] = pr
                                st.rerun()
                            except Exception as e:
                                st.error(f"동료 심사 오류: {e}")
                    else:
                        st.info("논문 작성 완료 후 자동으로 실행되거나 위 버튼으로 수동 실행할 수 있습니다.")
                else:
                    import pandas as pd
                    r1, r2, r3, r4 = st.columns(4)
                    r1.metric("종합 점수", f"{pr.get('total_score',0)}/100")
                    r2.metric("등급", pr.get("grade", "-"))
                    r3.metric("권고", pr.get("accept_recommendation", "-"))
                    r4.metric("섹션 수", len(pr.get("section_scores", {})))
                    st.divider()
                    section_rows = []
                    for k, v in pr.get("section_scores", {}).items():
                        section_rows.append({
                            "섹션": v.get("section", k),
                            "점수": f"{v.get('score',0)}/{v.get('max_score',0)}",
                            "강점": "; ".join(v.get("strengths", [])[:1]),
                            "약점": "; ".join(v.get("weaknesses", [])[:1]),
                        })
                    if section_rows:
                        st.dataframe(pd.DataFrame(section_rows), use_container_width=True)
                    if pr.get("major_concerns"):
                        st.markdown("**주요 지적사항**")
                        for c in pr["major_concerns"]:
                            st.markdown(f"- {c}")
                    if pr.get("suggested_analyses"):
                        st.markdown("**추가 분석 제안**")
                        for a in pr["suggested_analyses"]:
                            st.markdown(f"- {a}")
                    if pr.get("revised_abstract"):
                        with st.expander("개선된 Abstract 보기"):
                            st.text(pr["revised_abstract"])

                # ── 실 리뷰어 피드백 저장 (붙여넣기) ────────────────────────
                st.divider()
                st.markdown("#### 📋 실제 리뷰어 피드백 저장")
                st.caption("받은 리뷰어 코멘트를 붙여넣으면 다음 논문 작성 시 자동으로 반영됩니다.")
                with st.expander("리뷰어 피드백 입력", expanded=False):
                    fb_journal = st.text_input(
                        "저널명 (선택)",
                        value=st.session_state.get("journal_id_sel", ""),
                        key="fb_journal",
                        placeholder="예: JKMS, IJERPH, BMJ Open",
                    )
                    fb_decision = st.selectbox(
                        "심사 결과",
                        ["", "major_revision", "minor_revision", "reject", "accept"],
                        key="fb_decision",
                    )
                    fb_keywords = st.text_input(
                        "연구 키워드 (쉼표 구분)",
                        value=", ".join([
                            st.session_state.get("exposure_sel", ""),
                            st.session_state.get("outcome_sel", ""),
                        ]).strip(", "),
                        key="fb_keywords",
                        placeholder="예: smoking, obesity, adolescents, KYRBS",
                    )
                    fb_title = st.text_input(
                        "논문 제목 (선택)",
                        value=st.session_state.get("topic_title", ""),
                        key="fb_title",
                    )
                    fb_text = st.text_area(
                        "리뷰어 코멘트 (전문 붙여넣기)",
                        height=200,
                        key="fb_text",
                        placeholder="Reviewer 1:\n...\n\nReviewer 2:\n...",
                    )
                    if st.button("💾 피드백 저장", key="save_feedback_btn"):
                        if fb_text.strip():
                            try:
                                from src.memory.user_feedback_store import add_feedback
                                fid = add_feedback(
                                    feedback_text=fb_text,
                                    journal=fb_journal,
                                    topic_keywords=fb_keywords,
                                    paper_title=fb_title,
                                    decision=fb_decision,
                                )
                                st.success(f"피드백 저장 완료 (ID: {fid}). 다음 논문 작성 시 자동 반영됩니다.")
                            except Exception as _fb_e:
                                st.error(f"저장 오류: {_fb_e}")
                        else:
                            st.warning("리뷰어 코멘트를 입력해주세요.")

                    # 저장된 피드백 목록
                    try:
                        from src.memory.user_feedback_store import FeedbackStore
                        _all_fb = FeedbackStore().list_all()
                        if _all_fb:
                            st.markdown(f"**저장된 피드백: {len(_all_fb)}건**")
                            for _fb in reversed(_all_fb[-5:]):
                                _j = f"[{_fb.get('journal', '?')}]" if _fb.get("journal") else ""
                                _dec = f" ({_fb.get('decision', '')})" if _fb.get("decision") else ""
                                _preview = _fb.get("feedback_text", "")[:80].replace("\n", " ")
                                st.caption(f"• {_j}{_dec} {_preview}...")
                    except Exception:
                        pass

        _show_history("논문 작성")

    # ── 기존 논문 개선 ────────────────────────────────────────────────
    elif page == "기존 논문 개선":
        st.markdown("<h2 style='color:#e6edf3;'>📄 기존 논문 개선</h2>", unsafe_allow_html=True)
        st.info(
            "작성 중이거나 이전에 저장한 논문 파일(DOCX/PDF/TXT)을 업로드하면 "
            "섹션 파싱 → 개선 도구 연결 → 세션 저장까지 자동으로 처리합니다."
        )

        uploaded = st.file_uploader(
            "논문 파일 업로드",
            type=["txt", "docx", "pdf", "md"],
            key="improve_upload",
            help="Word(.docx), PDF, 텍스트 파일 모두 지원",
        )

        if uploaded is not None:
            with st.spinner("논문 파싱 중..."):
                try:
                    from src.ingestion.paper_ingester import PaperIngester
                    ingester = PaperIngester()
                    paper = ingester.ingest_bytes(uploaded.getvalue(), uploaded.name)
                    st.session_state["improve_paper"] = paper
                    st.success(
                        f"파싱 완료: **{paper.file_name}** "
                        f"({paper.char_count:,}자, 섹션 {len(paper.sections)}개 인식)"
                    )
                except Exception as _pe:
                    st.error(f"파싱 오류: {_pe}")

        paper = st.session_state.get("improve_paper")
        if paper is None:
            st.markdown("---")
            st.caption("파일을 업로드하거나, 아래에서 세션에 저장된 초안을 불러오세요.")
            if st.session_state.get("draft"):
                if st.button("현재 세션 초안 불러오기", key="load_session_draft"):
                    from src.ingestion.paper_ingester import IngestedPaper, _split_into_sections
                    raw = st.session_state["draft"]
                    secs = _split_into_sections(raw)
                    st.session_state["improve_paper"] = IngestedPaper(
                        raw_text=raw, sections=secs,
                        title=st.session_state.get("topic_title", ""),
                        file_name="session_draft.txt",
                        char_count=len(raw),
                    )
                    st.rerun()
        else:
            # 메타정보 표시
            c1, c2, c3 = st.columns(3)
            c1.metric("파일", paper.file_name)
            c2.metric("섹션 수", len(paper.sections))
            c3.metric("글자 수", f"{paper.char_count:,}")

            if paper.title:
                st.markdown(f"**추출된 제목:** {paper.title}")

            # 섹션 탭으로 표시
            section_keys = list(paper.sections.keys())
            if section_keys:
                tabs = st.tabs([k.upper() for k in section_keys] + ["전문"])
                for i, key in enumerate(section_keys):
                    with tabs[i]:
                        edited = st.text_area(
                            f"{key.upper()} 편집",
                            value=paper.sections[key],
                            height=300,
                            key=f"improve_sec_{key}",
                        )
                        paper.sections[key] = edited
                with tabs[-1]:
                    st.text_area("전문", value=paper.to_draft_string(), height=400, key="improve_full", disabled=True)
            else:
                edited_full = st.text_area("전문 (섹션 자동 분리 실패)", value=paper.raw_text, height=400, key="improve_raw")
                paper.raw_text = edited_full

            st.divider()
            st.markdown("#### 🛠 개선 도구 선택")
            tool_cols = st.columns(4)

            # 1. 동료 심사
            with tool_cols[0]:
                if st.button("👥 동료 심사", key="improve_pr", use_container_width=True):
                    with st.spinner("동료 심사 중..."):
                        try:
                            from src.research.research_pipeline import ResearchPipeline
                            _rp = ResearchPipeline()
                            _topic = {"title": paper.title or "Uploaded Paper",
                                      "exposure": "", "outcome": "", "population": ""}
                            _pr = _rp.run_peer_review(paper.to_draft_string(), _topic)
                            st.session_state["improve_peer_review"] = _pr
                        except Exception as _e:
                            st.error(f"동료 심사 오류: {_e}")

            # 2. 신규성 확인
            with tool_cols[1]:
                if st.button("🔍 신규성 확인", key="improve_nov", use_container_width=True):
                    with st.spinner("PubMed 신규성 확인 중..."):
                        try:
                            from src.research.novelty_checker import NoveltyChecker
                            _nov = NoveltyChecker().check(topic=paper.title or paper.raw_text[:200])
                            st.session_state["improve_novelty"] = _nov
                        except Exception as _e:
                            st.error(f"신규성 확인 오류: {_e}")

            # 3. 저널 DOCX 내보내기
            with tool_cols[2]:
                _imp_journal = st.text_input(
                    "저널 ID", value="jkms", key="improve_journal_id",
                    placeholder="jkms / ijerph / bmj_open", label_visibility="collapsed"
                )
                if st.button("📄 DOCX 내보내기", key="improve_docx", use_container_width=True):
                    with st.spinner("DOCX 생성 중..."):
                        try:
                            from src.export.journal_docx_exporter import JournalDocxExporter
                            _exp = JournalDocxExporter(_imp_journal)
                            _out = str(Path("data/drafts") / f"{Path(paper.file_name).stem}_{_imp_journal}.docx")
                            _exp.export(
                                title=paper.title or "Uploaded Paper",
                                sections=paper.sections,
                                output_path=_out,
                            )
                            st.success(f"DOCX 저장: {_out}")
                            with open(_out, "rb") as _f:
                                st.download_button("⬇ DOCX 다운로드", _f.read(),
                                                   file_name=Path(_out).name,
                                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                                   key="improve_docx_dl")
                        except Exception as _e:
                            st.error(f"DOCX 내보내기 오류: {_e}")

            # 4. 세션 초안에 저장
            with tool_cols[3]:
                if st.button("💾 세션 초안으로 저장", key="improve_to_draft", use_container_width=True):
                    st.session_state["draft"] = paper.to_draft_string()
                    st.session_state["topic_title"] = paper.title or "Uploaded Paper"
                    st.success("세션 초안에 저장됨. '논문 작성' 탭에서 이어서 작업 가능.")

            # 동료 심사 결과 표시
            _ipr = st.session_state.get("improve_peer_review")
            if _ipr:
                st.divider()
                st.markdown("#### 동료 심사 결과")
                _ic1, _ic2, _ic3 = st.columns(3)
                _ic1.metric("종합 점수", f"{_ipr.get('total_score', 0)}/100")
                _ic2.metric("등급", _ipr.get("grade", "-"))
                _ic3.metric("권고", _ipr.get("accept_recommendation", "-"))
                if _ipr.get("major_concerns"):
                    st.markdown("**주요 지적사항**")
                    for _c in _ipr["major_concerns"]:
                        st.markdown(f"- {_c}")

                # 섹션별 재작성
                st.markdown("#### ✏️ 섹션 재작성")
                _rsec = st.selectbox("재작성할 섹션", list(paper.sections.keys()) or ["introduction"], key="improve_rsec")
                _rgoal = st.text_input("재작성 목표", key="improve_rgoal",
                                       placeholder="예: 방법론 한계점 추가, 문헌 비교 보강")
                if st.button("섹션 재작성 실행", key="improve_rewrite"):
                    with st.spinner(f"{_rsec} 재작성 중..."):
                        try:
                            from src.llm import get_llm_client
                            _llm = get_llm_client()
                            _orig = paper.sections.get(_rsec, "")
                            _prompt = (
                                f"Rewrite the following {_rsec.upper()} section of a medical research paper.\n"
                                f"Goal: {_rgoal}\n\n"
                                f"ORIGINAL:\n{_orig[:3000]}\n\n"
                                f"Write only the improved section text. Keep all statistics intact."
                            )
                            _new = _llm.generate(_prompt, task="paper_writing", max_tokens=2000)
                            _ic1b, _ic2b = st.columns(2)
                            with _ic1b:
                                st.markdown("**원본**")
                                st.text_area("", _orig[:1500], height=300, disabled=True, key="imp_orig")
                            with _ic2b:
                                st.markdown("**재작성**")
                                st.text_area("", _new[:1500], height=300, key="imp_new")
                            if st.button("재작성본 적용", key="imp_apply"):
                                paper.sections[_rsec] = _new
                                st.success("적용됨.")
                        except Exception as _e:
                            st.error(f"재작성 오류: {_e}")

            # 신규성 결과 표시
            _inov = st.session_state.get("improve_novelty")
            if _inov:
                st.divider()
                st.markdown("#### 신규성 확인 결과")
                st.metric("신규성 점수", f"{_inov.get('novelty_score', 0)}/10")
                st.write(_inov.get("verdict", ""))

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
                        response = _get_cached_medical_agent().ask(prompt)
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
                        papers = _get_cached_novelty_checker().search_papers(search_query, max_results=n_papers)
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
                import tempfile
                reader = PDFReader(); chunker = TextChunker(); store = _get_cached_store(); total = 0
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
                        from src.ingestion.chunker import TextChunker
                        from src.notebooklm.paper_sync import PaperSync
                        papers = _get_cached_novelty_checker().search_papers(pm_q, max_results=pm_n)
                        if papers:
                            store = _get_cached_store(); chunker = TextChunker(); total = 0
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
                    added = _get_cached_store().add_chunks(TextChunker().chunk(txt_content, metadata={"filename": txt_title[:80], "source": "manual_input", "topic": txt_topic}))
                    st.success(f"✅ {added}개 청크 저장")
                    _log("text_ingest", {"title": txt_title}, f"텍스트 입력 → {added}청크")
                except Exception as e: st.error(f"오류: {e}")
        _show_history("논문 업로드 & 인제스트")

    # ── 지식베이스 관리 ───────────────────────────────────────────────
    elif page == "지식베이스 관리":
        st.markdown("<h2 style='color:#e6edf3;'>🧠 지식베이스 현황</h2>", unsafe_allow_html=True)
        db_type = "Supabase (클라우드)" if os.environ.get("SUPABASE_DB_URL") else "ChromaDB (로컬)"
        try:
            store = _get_cached_store()
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
            from src.storage.manager import StorageManager
            from datetime import datetime
            checker = _get_cached_novelty_checker(); sm = StorageManager(); total = 0
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

    # ── 작업 타임라인 ─────────────────────────────────────────────────
    elif page == "작업 타임라인":
        st.title("📜 작업 타임라인")
        st.caption("모든 에이전트 작업의 시간순 기록 — 연속성 및 변경 이력")

        user_email = _u.get("email", "")
        try:
            from src.memory import change_log as _cl
            col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
            with col_f1:
                _atype_filter = st.selectbox(
                    "작업 유형",
                    ["전체", "qa", "topic_generate", "novelty_check", "paper_write",
                     "learn", "workflow_step", "config_change", "mcp_tool", "general"],
                    key="_tl_type",
                )
            with col_f2:
                _n_filter = st.slider("최근 N개", 10, 200, 50, key="_tl_n")
            with col_f3:
                st.markdown("<div style='margin-top:28px;'></div>", unsafe_allow_html=True)
                _show_all = st.checkbox("전체 사용자 (admin)", value=False, key="_tl_all",
                                        disabled=(not st.session_state.get("_is_admin")),
                                        help="admin은 모든 사용자의 작업을 조회할 수 있습니다 (full access)")

            atype_arg = None if _atype_filter == "전체" else _atype_filter
            email_arg = None if _show_all else user_email
            entries = _cl.get_recent(n=_n_filter, user_email=email_arg, action_type=atype_arg)

            if not entries:
                st.info("아직 기록된 작업이 없습니다. 파이프라인을 사용하면 자동으로 기록됩니다.")
            else:
                st.caption(f"총 {len(entries)}개 항목")
                _TYPE_COLORS = {
                    "qa": "#3B82F6", "topic_generate": "#8B5CF6", "novelty_check": "#F59E0B",
                    "paper_write": "#10B981", "learn": "#06B6D4", "workflow_step": "#6366F1",
                    "config_change": "#EF4444", "mcp_tool": "#EC4899", "general": "#64748B",
                }
                for e in entries:
                    ts = str(e.get("timestamp", ""))[:16]
                    title = e.get("title", "")
                    atype = e.get("action_type", "general")
                    desc = e.get("description", "")
                    why = e.get("why_better", "")
                    u_email = e.get("user_email", "")
                    color = _TYPE_COLORS.get(atype, "#64748B")
                    impact = e.get("impact", {})
                    if isinstance(impact, str):
                        try:
                            import json as _j; impact = _j.loads(impact)
                        except Exception:
                            impact = {}
                    affected = impact.get("affected_modules", []) if isinstance(impact, dict) else []

                    with st.expander(f"**[{ts}]** {title}", expanded=False):
                        c1, c2 = st.columns([1, 4])
                        with c1:
                            st.markdown(
                                f'<span style="background:{color}22;color:{color};'
                                f'border:1px solid {color}44;border-radius:4px;'
                                f'padding:2px 8px;font-size:11px;font-weight:700;">{atype}</span>',
                                unsafe_allow_html=True,
                            )
                            if u_email:
                                st.caption(u_email.split("@")[0])
                        with c2:
                            if desc:
                                st.markdown(f"**내용:** {desc}")
                            if why:
                                st.markdown(f"**개선 이유:** {why}")
                            if affected:
                                st.markdown(f"**영향 모듈:** `{'`, `'.join(affected)}`")
                            inp = e.get("inputs", {})
                            out = e.get("outputs", {})
                            if isinstance(inp, dict) and inp:
                                st.caption(f"입력: {str(inp)[:150]}")
                            if isinstance(out, dict) and out:
                                st.caption(f"출력: {str(out.get('summary', out))[:150]}")
        except Exception as ex:
            st.error(f"타임라인 로드 오류: {ex}")

    # ── 자가 진단 & 자가발전 ──────────────────────────────────────────
    elif page == "자가 진단":
        st.markdown("<h2 style='color:#e6edf3;'>🧬 자가 진단 & 자가발전</h2>", unsafe_allow_html=True)
        st.caption("Medical-Agent가 스스로 품질을 진단하고 자동으로 개선합니다.")

        from src.diagnostics.self_auditor import get_last_audit, get_audit_history
        from src.diagnostics.improvement_engine import get_approval_queue, approve_item, reject_item

        last = get_last_audit()
        history = get_audit_history(10)
        scores = [h["overall_score"] for h in history]

        # ── 상단 메트릭 ───────────────────────────────────────────────
        c1, c2, c3, c4 = st.columns(4)
        if last:
            score = last["overall_score"]
            score_color = "#22C55E" if score >= 80 else "#F59E0B" if score >= 60 else "#EF4444"
            c1.markdown(f"""
            <div style="background:rgba(13,27,48,0.85);border:1px solid rgba(56,98,180,0.18);
                        border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">종합 점수</div>
                <div style="font-size:32px;font-weight:800;color:{score_color};">{score}</div>
                <div style="font-size:10px;color:#64748B;">/100</div>
            </div>""", unsafe_allow_html=True)

            rag_s = last.get("rag_health", {}).get("status", "?")
            rag_color = "#22C55E" if rag_s in ("excellent","good") else "#F59E0B" if rag_s == "fair" else "#EF4444"
            c2.markdown(f"""
            <div style="background:rgba(13,27,48,0.85);border:1px solid rgba(56,98,180,0.18);
                        border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">RAG 품질</div>
                <div style="font-size:18px;font-weight:700;color:{rag_color};">{rag_s.upper()}</div>
                <div style="font-size:10px;color:#64748B;">{last.get('rag_health',{}).get('doc_count',0):,} chunks</div>
            </div>""", unsafe_allow_html=True)

            n_issues = len(last.get("code_issues", []))
            n_high = sum(1 for i in last.get("code_issues", []) if i.get("severity") == "high")
            issue_color = "#22C55E" if n_high == 0 else "#F59E0B" if n_high < 3 else "#EF4444"
            c3.markdown(f"""
            <div style="background:rgba(13,27,48,0.85);border:1px solid rgba(56,98,180,0.18);
                        border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">코드 이슈</div>
                <div style="font-size:32px;font-weight:800;color:{issue_color};">{n_issues}</div>
                <div style="font-size:10px;color:#64748B;">high={n_high}</div>
            </div>""", unsafe_allow_html=True)

            n_gaps = len(last.get("llm_gaps", []))
            c4.markdown(f"""
            <div style="background:rgba(13,27,48,0.85);border:1px solid rgba(56,98,180,0.18);
                        border-radius:12px;padding:16px;text-align:center;">
                <div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">아키텍처 갭</div>
                <div style="font-size:32px;font-weight:800;color:#8B5CF6;">{n_gaps}</div>
                <div style="font-size:10px;color:#64748B;">{last.get('timestamp','')[:10]}</div>
            </div>""", unsafe_allow_html=True)
        else:
            st.info("아직 진단 이력이 없습니다. 아래 버튼으로 첫 번째 진단을 실행하세요.")

        # ── 점수 추세 ─────────────────────────────────────────────────
        if len(scores) >= 2:
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
            trend_arrow = "↑" if scores[0] > scores[-1] else "↓" if scores[0] < scores[-1] else "→"
            trend_color = "#22C55E" if scores[0] > scores[-1] else "#EF4444" if scores[0] < scores[-1] else "#94A3B8"
            st.markdown(
                f'<div style="font-size:12px;color:{trend_color};padding:4px 0;">'
                f'점수 추세: {" → ".join(str(s) for s in reversed(scores[-5:]))} {trend_arrow}</div>',
                unsafe_allow_html=True,
            )

        st.divider()

        # ── 진단 실행 버튼 ────────────────────────────────────────────
        col_run, col_quick, col_report = st.columns([2, 2, 2])
        run_full = col_run.button("🔬 전체 진단 실행", type="primary", use_container_width=True,
                                   help="LLM 아키텍처 평가 포함 (~2분)")
        run_quick = col_quick.button("⚡ 빠른 진단", use_container_width=True,
                                      help="코드 + RAG + LLM 연결만 (~30초)")

        if run_full or run_quick:
            with st.spinner("자가 진단 + 자동 개선 실행 중..."):
                try:
                    from src.diagnostics.self_auditor import SelfAuditor
                    from src.diagnostics.improvement_engine import ImprovementEngine
                    result = SelfAuditor().run_full_audit(with_llm_eval=run_full)
                    improvements = ImprovementEngine().run(result.to_dict())
                    auto_count = len(improvements.get("auto_applied", []))
                    queued_count = improvements.get("queued_count", 0)
                    st.success(
                        f"✅ 진단 완료 — 점수: {result.overall_score}/100 | "
                        f"자동 개선 {auto_count}건 적용 | 승인 대기 {queued_count}건"
                    )
                    st.rerun()
                except Exception as e:
                    st.error(f"진단 오류: {e}")
                    import traceback; st.code(traceback.format_exc())

        if last:
            tab1, tab2, tab3, tab4 = st.tabs(["🔍 코드 이슈", "🧠 아키텍처 갭", "⏳ 승인 큐", "📊 이력"])

            # ── 코드 이슈 탭 ──────────────────────────────────────────
            with tab1:
                issues = last.get("code_issues", [])
                if not issues:
                    st.success("✅ 코드 품질 이슈 없음")
                else:
                    sev_order = {"high": 0, "medium": 1, "low": 2}
                    for issue in sorted(issues, key=lambda x: sev_order.get(x.get("severity","low"), 2)):
                        sev = issue.get("severity", "low")
                        color = "#EF4444" if sev == "high" else "#F59E0B" if sev == "medium" else "#64748B"
                        st.markdown(f"""
                        <div style="background:rgba(13,27,48,0.7);border-left:3px solid {color};
                                    border-radius:6px;padding:8px 12px;margin-bottom:6px;">
                            <span style="font-size:10px;color:{color};font-weight:700;text-transform:uppercase;">{sev}</span>
                            <span style="font-size:11px;color:#64748B;margin-left:8px;">{issue.get('type','')}</span>
                            <div style="font-size:12px;color:#E5E7EB;margin-top:4px;">{issue.get('text','')}</div>
                            <div style="font-size:10px;color:#64748B;margin-top:2px;">{issue.get('file','')} L{issue.get('line','')}</div>
                        </div>""", unsafe_allow_html=True)

            # ── 아키텍처 갭 탭 ────────────────────────────────────────
            with tab2:
                gaps = last.get("llm_gaps", [])
                if not gaps:
                    st.info("LLM 평가 없음 — 전체 진단 실행 시 분석됩니다.")
                else:
                    for gap in sorted(gaps, key=lambda x: x.get("priority", 9)):
                        auto_label = "🤖 AUTO" if gap.get("auto") else "👤 MANUAL"
                        auto_color = "#22C55E" if gap.get("auto") else "#F59E0B"
                        cat = gap.get("category", "")
                        st.markdown(f"""
                        <div style="background:rgba(13,27,48,0.85);border:1px solid rgba(56,98,180,0.18);
                                    border-radius:10px;padding:14px;margin-bottom:10px;">
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                                <span style="font-size:11px;font-weight:700;color:#60A5FA;">P{gap.get('priority',0)}</span>
                                <span style="font-size:11px;color:{auto_color};font-weight:600;">{auto_label}</span>
                                <span style="font-size:10px;color:#64748B;background:rgba(255,255,255,0.06);
                                             padding:1px 8px;border-radius:10px;">{cat}</span>
                            </div>
                            <div style="font-size:13px;font-weight:600;color:#E5E7EB;margin-bottom:6px;">{gap.get('gap','')}</div>
                            <div style="font-size:11px;color:#94A3B8;margin-bottom:4px;">영향: {gap.get('impact','')}</div>
                            <div style="font-size:11px;color:#4ADE80;">해결책: {gap.get('solution','')}</div>
                        </div>""", unsafe_allow_html=True)

            # ── 승인 큐 탭 ────────────────────────────────────────────
            with tab3:
                pending = get_approval_queue()
                if not pending:
                    st.success("✅ 승인 대기 항목 없음")
                else:
                    st.caption(f"{len(pending)}건의 수동 검토 항목이 있습니다.")
                    for item in pending:
                        with st.expander(f"[P{item.get('priority',0)}] {item.get('gap','')[:60]}", expanded=False):
                            st.markdown(f"**카테고리:** {item.get('category','')}")
                            st.markdown(f"**영향:** {item.get('impact','')}")
                            st.markdown(f"**해결책:** {item.get('solution','')}")
                            st.caption(f"큐 등록: {item.get('queued_at','')}")
                            col_a, col_r = st.columns(2)
                            with col_a:
                                if st.button("✅ 승인 (구현 진행)", key=f"_approve_{item['id']}",
                                             use_container_width=True, type="primary"):
                                    approve_item(item["id"])
                                    st.success("승인됨 — 다음 세션에서 구현 예정")
                                    st.rerun()
                            with col_r:
                                if st.button("❌ 거부", key=f"_reject_{item['id']}",
                                             use_container_width=True):
                                    reject_item(item["id"])
                                    st.rerun()

            # ── 이력 탭 ───────────────────────────────────────────────
            with tab4:
                if not history:
                    st.info("진단 이력 없음")
                else:
                    for h in history:
                        s = h["overall_score"]
                        sc = "#22C55E" if s >= 80 else "#F59E0B" if s >= 60 else "#EF4444"
                        st.markdown(f"""
                        <div style="display:flex;align-items:center;gap:14px;padding:10px 14px;
                                    background:rgba(13,27,48,0.6);border:1px solid rgba(56,98,180,0.18);
                                    border-radius:8px;margin-bottom:6px;">
                            <span style="font-size:20px;font-weight:800;color:{sc};min-width:36px;">{s}</span>
                            <div style="flex:1;">
                                <div style="font-size:12px;color:#E5E7EB;">{h.get('timestamp','')[:16]}</div>
                                <div style="font-size:11px;color:#64748B;">
                                    이슈:{len(h.get('code_issues',[]))} |
                                    RAG:{h.get('rag_health',{}).get('status','?')} |
                                    갭:{len(h.get('llm_gaps',[]))} |
                                    {h.get('duration_sec',0):.0f}초
                                </div>
                            </div>
                        </div>""", unsafe_allow_html=True)

        _show_history("자가 진단")

    # ── 지식 위키 (OpenKB식 누적) ──────────────────────────────────────
    elif page == "지식 위키":
        st.markdown("<h2 style='color:#e6edf3;'>🧠 지식 위키 (누적)</h2>", unsafe_allow_html=True)
        st.info("논문을 쓰고 자료를 흡수할수록 연구 개념이 **누적**됩니다(OpenKB/Karpathy식). "
                "축적된 지식은 작업실 글쓰기에 자동 주입돼 '쓸수록 더 잘 쓰는' 흐름을 만듭니다.")
        from src.knowledge.research_wiki import ResearchWiki
        _rw = ResearchWiki(owner_email=_u.get("email", ""))
        _wt1, _wt2, _wt3, _wt4 = st.tabs(["📑 개념 목록", "➕ 자료 흡수", "🩺 건강검사(lint)", "🔬 최신논문 자동학습"])
        with _wt1:
            _pages = _rw.list_pages()
            if not _pages:
                st.caption("아직 누적된 개념이 없습니다. 작업실에서 논문을 저장하거나 '자료 흡수'로 추가하세요.")
            else:
                st.caption(f"누적 개념 {len(_pages)}개")
                _sel = st.selectbox("개념 선택", [p["slug"] for p in _pages],
                                    format_func=lambda s: next((p["title"] for p in _pages if p["slug"] == s), s),
                                    key="wiki_sel")
                if _sel:
                    st.markdown(_rw.get_page(_sel))
        with _wt2:
            _src = st.text_area("자료 텍스트 (논문 단락/노트/초록 등)", height=180, key="wiki_src")
            _stitle = st.text_input("제목", key="wiki_src_title")
            if st.button("➕ 위키에 흡수", type="primary", key="wiki_add_btn"):
                if not _src.strip():
                    st.warning("자료 텍스트를 입력하세요.")
                elif not st.session_state.get("_llm_ready"):
                    st.warning("개념 추출에 LLM 키가 필요합니다.")
                else:
                    with st.spinner("개념 추출 → 누적 중..."):
                        _r = _rw.add_source(_src, title=_stitle or _src[:40])
                    if _r.get("error"):
                        st.error(_r["error"])
                    else:
                        st.success(f"흡수 완료 — 개념 {len(_r.get('concepts_updated', []))}개 갱신")
                        st.rerun()
        with _wt3:
            _lint = _rw.lint()
            c1, c2 = st.columns(2)
            c1.metric("누적 개념", _lint["n_concepts"])
            c2.metric("요약 페이지", _lint["n_summaries"])
            if _lint["orphans"]:
                st.warning(f"고립 개념(피링크 0): {', '.join(_lint['orphans'][:10])}")
            if _lint["stale"]:
                st.info(f"오래된 개념(60일+): {', '.join(_lint['stale'][:10])}")
            if not _lint["orphans"] and not _lint["stale"]:
                st.success("건강 양호 — 고립/노화 개념 없음")

        with _wt4:
            st.caption("PubMed 최신논문(60일)을 KYRBS/KNHANES 온톨로지로 크롤링 → RAG·그래프·인사이트로 "
                       "자동 학습합니다(LLM-무관, 쿼터와 무관). 백그라운드로 하루 1회 + 아래 버튼으로 즉시 실행.")
            try:
                from src.knowledge.trend_learner import get_last_run_info, run_trend_learn
                _info = get_last_run_info()
            except Exception as _e:
                _info = {"last_run": "오류", "run_count": 0, "ingested_count": 0}
                st.error(f"자동학습 모듈 로드 실패: {_e}")
            a1, a2, a3 = st.columns(3)
            a1.metric("누적 학습 논문", f"{_info['ingested_count']:,}")
            a2.metric("실행 횟수", _info["run_count"])
            a3.metric("마지막 실행", str(_info["last_run"])[:16])
            # 최근 자동학습 인사이트
            try:
                import json as _j
                from pathlib import Path as _PathL
                _ins = _j.loads(_PathL("data/agent_self/insights.json").read_text(encoding="utf-8")) if _PathL("data/agent_self/insights.json").exists() else []
                _ins = _ins if isinstance(_ins, list) else _ins.get("insights", [])
                _auto = [i for i in _ins if "auto_learn" in str(i.get("tags", []))][-3:]
                if _auto:
                    st.markdown("**최근 자동학습 인사이트:**")
                    for _i in reversed(_auto):
                        st.markdown(f"- {str(_i.get('insight',''))[:200]}")
            except Exception:
                pass
            if st.button("🔄 지금 최신논문 학습 (1~2분)", type="primary", key="trend_now"):
                with st.spinner("PubMed 크롤링 → RAG·그래프·인사이트 학습 중..."):
                    try:
                        _r = run_trend_learn(days=30, max_per_query=10)
                        st.success(f"학습 완료 — 신규 {_r.get('new_papers', _r.get('added', '?'))}편 흡수. "
                                   f"누적 {get_last_run_info()['ingested_count']:,}편")
                        st.rerun()
                    except Exception as _e:
                        st.error(f"학습 실패: {str(_e)[:200]}")

    else:
        st.info(f"페이지를 찾을 수 없습니다: {page}")

# ══════════════════════════════════════════════════════════════════════
# AI PANEL (right column)
# ══════════════════════════════════════════════════════════════════════
if ai_col is not None:
    with ai_col:
        st.markdown('<div class="ai-panel-wrap">', unsafe_allow_html=True)
        from app.ai_panel import render_ai_panel
        render_ai_panel(page, page_context, user_email=_u.get("email", ""))
        st.markdown('</div>', unsafe_allow_html=True)
