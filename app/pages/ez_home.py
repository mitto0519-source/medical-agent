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
    """research_state.stat_result에서 figure 1종 생성. (png_bytes, caption) 반환."""
    try:
        from src.export.publication_figure_generator import (
            make_forest_plot, make_subgroup_forest, make_coefficient_plot,
            make_roc_curve, make_prevalence_bar, make_table1_image, make_table2_image)
        from pathlib import Path
        rs = project.get("research_state") or {}
        stat_result = rs.get("stat_result") or {}
        if not stat_result:
            return None
        out_dir = Path(f"data/drafts/figures/{project.get('id','tmp')}")
        out_dir.mkdir(parents=True, exist_ok=True)
        fn = {
            "forest": make_forest_plot,
            "subgroup": make_subgroup_forest,
            "coef": make_coefficient_plot,
            "roc": make_roc_curve,
            "prev": make_prevalence_bar,
            "table1": make_table1_image,
            "table2": make_table2_image,
        }.get(figure_type)
        if not fn:
            return None
        result = fn(stat_result, out_dir)
        if result is None:
            return None
        png_bytes, _svg_path, _png_path, caption = result[:4] if len(result) >= 4 else (result + ("",))
        return png_bytes, caption
    except Exception as e:
        return None


def _strip_korean_prelude(text: str) -> str:
    """Manuscript는 영어만 허용 — LLM이 앞에 붙인 한국어 해설 제거.

    첫 번째 영어 markdown 헤더('## Title' / '# Title' / 'Title:' 등) 이후만 살림.
    """
    if not text:
        return text
    import re
    # IMRAD 구조 첫 marker
    patterns = [
        r"(##?\s*Title\b)",
        r"(##?\s*Abstract\b)",
        r"(\*\*Title:?\*\*)",
        r"(^Title:\s)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.MULTILINE)
        if m:
            return text[m.start():].strip()
    return text


def _hits_to_references(rag_context: str) -> list:
    """RAG context에서 PMID를 뽑아 Reference 객체 list로 변환.

    citation_workflow.Reference 사용 — minimal metadata지만 inline citation에 충분.
    """
    if not rag_context:
        return []
    import re
    try:
        from src.export.citation_workflow import Reference
    except Exception:
        return []
    pmids = re.findall(r"PMID:(\d+)", rag_context)
    refs = []
    seen = set()
    for pmid in pmids:
        if pmid in seen:
            continue
        seen.add(pmid)
        refs.append(Reference(pmid=pmid, title=f"PubMed {pmid}",
                                citation_key=f"PMID{pmid}"))
    return refs


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


def _build_full_system(project: dict, user_msg: str) -> str:
    """단일 코어 system prompt 합성 (CLAUDE.md 규칙 12) + RAG retrieve + per-user style.

    2026-06-13: owner_email 양식 양식 양식 양식 — yoosun 단일 시드 양식 양식 양식 양식
    사용자 본인 문체 프로파일 (StyleProfiler)이 있으면 system prompt에 자동 inject.
    """
    import streamlit as _st
    owner_email = (_st.session_state.get("user") or {}).get("email") or \
                   _st.session_state.get("user_email", "") or ""
    try:
        from src.agent.persona import get_system_prompt
        base_sys = get_system_prompt(task="paper_writing", owner_email=owner_email or None)
    except Exception:
        base_sys = "당신은 의학 연구 코파일럿입니다."
    try:
        from app.agentic_loop import build_system_with_preview
        full_sys = build_system_with_preview(base_sys, project, user_msg)
    except Exception:
        full_sys = base_sys

    # ★ RAG retrieve (paper-grounded) — 사용자 정직 진단 2026-06-12에 추가.
    # 이전엔 ChromaDB 인덱스만 있고 query → inject 회로가 끊겨 답변 generic.
    rag_ctx = _rag_retrieve(user_msg, top_k=5)
    if rag_ctx:
        full_sys = (full_sys +
            "\n\n--- RETRIEVED MEDICAL EVIDENCE (cite by PMID inline as [PMID:xxx]) ---\n"
            + rag_ctx +
            "\n--- END EVIDENCE ---")

    rule_overlay = (
        "\n\n--- RULE-8 (vibe paper) ---\n"
        "사용자 주제가 모호하면 PICO·데이터·통계·하위군 중 짧은 역질문 2-3개로 좁히세요.\n"
        "'알아서 해' '그냥 해' '한번에' 같은 trigger를 들으면 그때 자동 파이프라인을 진행합니다.\n"
        "응답은 한국어 대화체, 동료 의학연구자 어투, 마크다운 짧게.\n"
        "위 RETRIEVED MEDICAL EVIDENCE를 참고해 답변에 PMID 인라인 인용을 넣으세요."
    )
    return full_sys + rule_overlay


def _stream_reply(project: dict, user_msg: str, extra_system: str = "", max_tokens: int = 1200):
    """generator — token 단위 yield. failover 클라이언트의 generate_streamed 사용.

    extra_system: Go wide / Go deep / Full IMRAD 등 트리거가 추가하는 system prompt overlay.
    max_tokens: Full IMRAD는 4500+ 권장, 일반 대화 1200.
    """
    try:
        from src.llm import get_llm_client
    except Exception as e:
        yield f"(LLM 클라이언트 import 실패: {e})"
        return

    full_sys = _build_full_system(project, user_msg)
    if extra_system:
        full_sys = full_sys + "\n\n--- TASK OVERLAY ---\n" + extra_system
    history = "\n".join(
        f"{'사용자' if m['role']=='user' else '코파일럿'}: {m['content']}"
        for m in project.get("messages", [])[-10:])
    prompt = f"{history}\n사용자: {user_msg}\n코파일럿:"

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
        yield f"(LLM 호출 실패: {e})"


def _post_turn_hooks(project: dict, user_msg: str, full_reply: str, owner_email: str = ""):
    """Delegate → src.service.chat.post_turn_hooks."""
    from src.service.chat import post_turn_hooks
    post_turn_hooks(project, user_msg, full_reply, owner_email=owner_email)


def _render_msg(role: str, content: str):
    """단일 메시지를 chat bubble HTML 로 렌더."""
    safe = (content or "").replace("<", "&lt;").replace(">", "&gt;")
    cls = "msg-user" if role == "user" else "msg-asst"
    st.markdown(f"<div class='{cls}'>{safe}</div>", unsafe_allow_html=True)


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
                    # 각 stage event를 chat에 표시 + 단계별 sections/manuscript에 박음
                    from src.service.paper import autopilot_run as _autopilot
                    reply_lines: list[str] = []
                    progress_box = st.empty()
                    try:
                        for event in _autopilot(project, user_msg):
                            stage = event.get("stage", "?")
                            status = event.get("status", "?")
                            msg = event.get("message", "")
                            reply_lines.append(f"[{stage}/{status}] {msg}")
                            progress_box.markdown(
                                "<div class='msg-asst'>" +
                                "<br>".join(l.replace("<", "&lt;").replace(">", "&gt;") for l in reply_lines) +
                                "</div>", unsafe_allow_html=True)
                            # Save manuscript_text to sections live → 우측 프리뷰 즉시 표시
                            mt = event.get("manuscript_text")
                            if mt:
                                project.setdefault("sections", {})["full"] = mt
                                project.setdefault("research_state", {})["manuscript_text"] = mt
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
                    tool_log: list[str] = []
                    body_buf: list[str] = []
                    confidence_msg = ""

                    _mt = 4500 if full else 2000
                    for evt in stream_turn(
                            project, user_msg,
                            owner_email=owner_email,
                            save_project_fn=_save_project,
                            max_tokens=_mt, max_iters=6):
                        et = evt.type
                        d = evt.data or {}
                        if et == "status":
                            tool_log.append(f"⏱ {d.get('msg','')}")
                            activity.markdown(
                                "<div class='msg-asst' style='font-size:0.78rem;"
                                "background:#F1F5F9;padding:6px 10px;'>" +
                                "<br>".join(l.replace("<","&lt;") for l in tool_log[-6:]) +
                                "</div>", unsafe_allow_html=True)
                        elif et == "tool_start":
                            tool_log.append(f"🔧 {d.get('tool','?')} start")
                            activity.markdown(
                                "<div class='msg-asst' style='font-size:0.78rem;"
                                "background:#F1F5F9;padding:6px 10px;'>" +
                                "<br>".join(l.replace("<","&lt;") for l in tool_log[-6:]) +
                                "</div>", unsafe_allow_html=True)
                        elif et == "tool_result":
                            tool_log.append(f"✓ {d.get('tool','?')}")
                            activity.markdown(
                                "<div class='msg-asst' style='font-size:0.78rem;"
                                "background:#F1F5F9;padding:6px 10px;'>" +
                                "<br>".join(l.replace("<","&lt;") for l in tool_log[-6:]) +
                                "</div>", unsafe_allow_html=True)
                        elif et == "token":
                            body_buf.append(d.get("text", ""))
                            safe = "".join(body_buf).replace("<","&lt;").replace(">","&gt;")
                            preview_ph.markdown(
                                f"<div class='msg-asst'>{safe}▌</div>",
                                unsafe_allow_html=True)
                        elif et == "warning":
                            st.markdown(
                                f"<div class='msg-asst' style='font-size:0.78rem;"
                                f"background:#FEF3C7;border-left:3px solid #F59E0B;"
                                f"padding:4px 8px;'>⚠ {d.get('kind','')}: "
                                f"{(d.get('msg','') or '')[:200].replace('<','&lt;')}</div>",
                                unsafe_allow_html=True)
                        elif et == "badge":
                            kind = d.get("kind", "")
                            val = d.get("value", "")
                            confidence_msg = f"🏷️ {kind}={val}"
                            st.markdown(
                                f"<div class='msg-asst' style='font-size:0.78rem;"
                                f"background:#ECFDF5;border-left:3px solid #10B981;"
                                f"padding:4px 8px;'>{confidence_msg}</div>",
                                unsafe_allow_html=True)
                        elif et == "error":
                            st.markdown(
                                f"<div class='msg-asst' style='font-size:0.82rem;"
                                f"background:#FEE2E2;border-left:3px solid #DC2626;"
                                f"padding:6px 10px;'>❌ {d.get('where','?')}: "
                                f"{(d.get('msg','') or '')[:200]}</div>",
                                unsafe_allow_html=True)
                        elif et == "done":
                            elapsed = d.get("elapsed_ms", 0)
                            tool_log.append(f"✓ done ({elapsed}ms)")
                            activity.markdown(
                                "<div class='msg-asst' style='font-size:0.78rem;"
                                "background:#F1F5F9;padding:6px 10px;'>" +
                                "<br>".join(l.replace("<","&lt;") for l in tool_log[-6:]) +
                                "</div>", unsafe_allow_html=True)

                    reply = (badge + "".join(body_buf)).strip()
                    safe = reply.replace("<","&lt;").replace(">","&gt;")
                    preview_ph.markdown(
                        f"<div class='msg-asst'>{safe}</div>",
                        unsafe_allow_html=True)

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

            # Manuscript body
            html_parts = [f"<div class='preview-box'><h1>{project.get('title','')[:80]}</h1>"]
            for key in ["abstract", "introduction", "methods", "results", "discussion", "conclusion"]:
                if key in sections and sections[key]:
                    body = str(sections[key]).replace("<", "&lt;").replace(">", "&gt;")
                    body_html = "".join(f"<p>{para}</p>" for para in body.split("\n\n") if para.strip())
                    html_parts.append(f"<h2>{key.capitalize()}</h2>{body_html}")

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
    try:
        qp = st.query_params
        url_pid = qp.get("pid") if hasattr(qp, "get") else None
        if isinstance(url_pid, list):
            url_pid = url_pid[0] if url_pid else None
    except Exception:
        url_pid = None

    # 2) URL 우선, 없으면 session_state
    active = url_pid or st.session_state.get("sg_active_project")

    # 3) 둘 다 없거나 "new"면 새 UUID
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
