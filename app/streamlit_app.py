"""
Medical-Agent Streamlit UI
조유선 스타일 연구 파이프라인 웹 인터페이스
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

# Streamlit Cloud: st.secrets → os.environ bridge
try:
    for _k, _v in st.secrets.items():
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:
    pass
import json
from pathlib import Path

# ── 페이지 설정 ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Medical-Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ════════════════════════════════════════════════════════════════════════
# 로그인 게이트 — 이메일 기반 접근 제어
# ════════════════════════════════════════════════════════════════════════
def _login_gate():
    """이메일로 접근 권한 확인. 통과 시 session_state["user"] 설정."""
    if "user" in st.session_state:
        return True

    st.markdown("""
    <div style="max-width:400px;margin:80px auto;padding:2rem;
                border:1px solid #e0e0e0;border-radius:12px;
                box-shadow:0 4px 16px rgba(0,0,0,0.08);">
        <h2 style="text-align:center;margin-bottom:0.2rem;">🔬 Medical-Agent</h2>
        <p style="text-align:center;color:#666;margin-bottom:1.5rem;font-size:0.9rem;">
            연구 파이프라인 접근 권한이 필요합니다
        </p>
    </div>
    """, unsafe_allow_html=True)

    with st.form("login_form"):
        email = st.text_input("이메일 주소", placeholder="your@email.com")
        submitted = st.form_submit_button("접속", use_container_width=True, type="primary")

    if submitted:
        if not email or "@" not in email:
            st.error("올바른 이메일 주소를 입력하세요.")
            return False

        from src.auth.users import get_user_by_email
        user = get_user_by_email(email.strip().lower())

        if not user:
            st.error("등록되지 않은 이메일입니다. 관리자에게 문의하세요.")
            return False

        st.session_state["user"] = user
        st.rerun()

    return False


if not _login_gate():
    st.stop()

# ── CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.stButton > button { width: 100%; }
.success-box { padding: 1rem; border-left: 4px solid #28a745; background: #f0fff4; border-radius: 4px; margin: 0.5rem 0; }
.info-box { padding: 1rem; border-left: 4px solid #007bff; background: #f0f8ff; border-radius: 4px; margin: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ── 사이드바 ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🔬 Medical-Agent")
    st.caption("Yoosun Cho 스타일 연구 파이프라인")

    # 로그인 사용자 표시
    _u = st.session_state.get("user", {})
    role_badge = "👑" if _u.get("role") == "super_admin" else "👤"
    st.caption(f"{role_badge} {_u.get('name', '')} ({_u.get('email', '')})")
    if st.button("로그아웃", key="__logout__"):
        del st.session_state["user"]
        st.rerun()

    st.divider()

    page = st.radio(
        "메뉴",
        [
            "🏠 홈",
            "── 논문 생산 ──",
            "📚 연구 주제 생성",
            "🔍 신규성 확인",
            "✅ 타당성 검증",
            "📝 논문 작성",
            "📊 데이터셋 라이브러리",
            "🤖 Agent Q&A",
            "☁️ NotebookLM 허브",
            "── 자산화/학습 ──",
            "📥 논문 업로드 & 인제스트",
            "🧠 지식베이스 현황",
            "👤 저자 프로필 구축",
            "🔄 자동 학습 루프",
        ],
        label_visibility="collapsed",
    )
    st.divider()

    # 시스템 상태
    st.caption("시스템 상태")
    try:
        from src.vectordb.store import get_vector_store
        import os
        store = get_vector_store()
        chunk_count = store.count()
        db_label = "Supabase" if os.environ.get("SUPABASE_DB_URL") else "ChromaDB"
        st.success(f"{db_label}: {chunk_count}개 청크")
    except Exception as e:
        st.error(f"ChromaDB 오류: {e}")

    try:
        from src.library.dataset_library import DatasetLibrary
        lib = DatasetLibrary()
        datasets = lib.list_datasets()
        st.success(f"데이터셋: {', '.join(datasets) or '없음'}")
    except Exception as e:
        st.error(f"라이브러리 오류")

    try:
        from src.profile.author_profile import AuthorProfile
        profile = AuthorProfile("Yoosun Cho")
        papers_n = profile._profile.get("papers_analysed", 0)
        st.success(f"스타일 시드: {papers_n}개 논문")
    except Exception:
        st.warning("스타일 시드 없음")


# 구분선 메뉴 항목은 클릭 시 홈으로 리다이렉트
if page in ("── 논문 생산 ──", "── 자산화/학습 ──"):
    page = "🏠 홈"

# ════════════════════════════════════════════════════════════════════════
# 홈
# ════════════════════════════════════════════════════════════════════════
if page == "🏠 홈":
    st.title("🔬 Medical-Agent")
    st.subheader("조유선 스타일 의학 논문 자동 생산 파이프라인")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.info("**1단계** 연구 주제 생성\n\nKYRBS 데이터셋 + RAG 기반 주제 자동 생성")
    with col2:
        st.info("**2단계** 신규성 + 타당성 확인\n\nPubMed 검색 + Claude 분석")
    with col3:
        st.info("**3단계** 논문 작성\n\n조유선 스타일로 전체 논문 초안 생성")

    st.divider()
    st.markdown("### 빠른 시작")
    st.markdown("왼쪽 메뉴에서 **📚 연구 주제 생성**을 선택하세요.")

    st.markdown("### 학습된 자료")
    try:
        papers_path = Path("data/yoosun_cho_papers.json")
        if papers_path.exists():
            with open(papers_path, encoding="utf-8") as f:
                papers = json.load(f)
            st.markdown(f"- 조유선 교수 논문: **{len(papers)}편** 학습 완료")

        lib_path = Path("data/libraries/dataset_kyrbs.json")
        if lib_path.exists():
            with open(lib_path, encoding="utf-8") as f:
                kyrbs = json.load(f)
            n_vars = len(kyrbs.get("variables", {}))
            st.markdown(f"- KYRBS 2025 변수: **{n_vars}개** 등록 완료")
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════
# 연구 주제 생성
# ════════════════════════════════════════════════════════════════════════
elif page == "📚 연구 주제 생성":
    st.title("📚 연구 주제 생성")

    col1, col2 = st.columns([2, 1])
    with col1:
        dataset = st.selectbox("데이터셋", ["KYRBS"], help="사용할 데이터셋 선택")
        focus = st.text_input("연구 포커스", placeholder="예: 청소년 비만과 정신건강, 스마트폰 사용과 수면")
    with col2:
        n_topics = st.slider("생성할 주제 수", 1, 10, 5)
        use_evidence = st.checkbox("오픈 에비던스 검색 포함", value=True)

    if st.button("🚀 주제 생성", type="primary"):
        if not focus:
            st.error("연구 포커스를 입력하세요.")
        else:
            with st.spinner(f"Claude가 {n_topics}개 주제를 생성 중..."):
                try:
                    from src.research.research_pipeline import ResearchPipeline
                    rp = ResearchPipeline()

                    topics = rp.generate_topics(
                        dataset_name=dataset,
                        focus=focus,
                        n_topics=n_topics,
                        reference_query=focus if use_evidence else None,
                    )

                    st.session_state["topics"] = topics
                    st.success(f"✅ {len(topics)}개 주제 생성 완료!")

                except Exception as e:
                    st.error(f"오류: {e}")

    if "topics" in st.session_state:
        st.divider()
        st.subheader("생성된 주제 목록")

        for i, t in enumerate(st.session_state["topics"]):
            with st.expander(f"[{i+1}] {t.get('title', '제목 없음')}", expanded=(i == 0)):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**노출변수:** {t.get('exposure', '-')}")
                    st.markdown(f"**결과변수:** {t.get('outcome', '-')}")
                with c2:
                    st.markdown(f"**대상:** {t.get('population', '-')}")
                    st.markdown(f"**설계:** {t.get('suggested_design', '-')}")
                st.markdown(f"**근거:** {t.get('rationale', '-')}")

                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"🔍 신규성 확인", key=f"nov_{i}"):
                        st.session_state["selected_topic"] = t
                        st.session_state["goto"] = "novelty"
                        st.rerun()
                with col_b:
                    if st.button(f"📝 이 주제로 논문 작성", key=f"write_{i}"):
                        st.session_state["selected_topic"] = t
                        st.session_state["goto"] = "write"
                        st.rerun()


# ════════════════════════════════════════════════════════════════════════
# 신규성 확인
# ════════════════════════════════════════════════════════════════════════
elif page == "🔍 신규성 확인":
    st.title("🔍 신규성 확인 (PubMed)")

    topic_from_prev = st.session_state.get("selected_topic")
    default_title = topic_from_prev.get("title", "") if topic_from_prev else ""
    default_exposure = topic_from_prev.get("exposure", "") if topic_from_prev else ""
    default_outcome = topic_from_prev.get("outcome", "") if topic_from_prev else ""
    default_population = topic_from_prev.get("population", "") if topic_from_prev else ""

    title = st.text_input("연구 제목", value=default_title)
    col1, col2 = st.columns(2)
    with col1:
        exposure = st.text_input("노출변수", value=default_exposure)
        outcome = st.text_input("결과변수", value=default_outcome)
    with col2:
        population = st.text_input("대상 집단", value=default_population)

    if st.button("🔍 PubMed 신규성 확인", type="primary"):
        if not title:
            st.error("연구 제목을 입력하세요.")
        else:
            with st.spinner("PubMed 검색 + Claude 분석 중..."):
                try:
                    from src.research.novelty_checker import NoveltyChecker
                    checker = NoveltyChecker()
                    result = checker.check(
                        topic=title,
                        exposure=exposure,
                        outcome=outcome,
                        population=population,
                    )

                    score = result.get("novelty_score", 0)
                    color = "🟢" if score >= 7 else "🟡" if score >= 4 else "🔴"
                    st.metric("신규성 점수", f"{color} {score}/10")

                    col_r, col_s = st.columns(2)
                    with col_r:
                        st.markdown(f"**권고:** {result.get('recommendation', '-')}")
                        st.markdown(f"**연구 공백:** {result.get('gap_identified', '-')}")
                    with col_s:
                        st.markdown(f"**제안 각도:** {result.get('suggested_angle', '-')}")

                    if result.get("similar_papers"):
                        st.subheader("유사 논문")
                        for p in result["similar_papers"][:5]:
                            st.markdown(f"- {p}")

                    st.session_state["novelty_result"] = result

                except Exception as e:
                    st.error(f"오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# 타당성 검증
# ════════════════════════════════════════════════════════════════════════
elif page == "✅ 타당성 검증":
    st.title("✅ 타당성 검증")

    topic_from_prev = st.session_state.get("selected_topic", {})
    topic_json = st.text_area(
        "주제 JSON (연구 주제 생성에서 자동 입력됩니다)",
        value=json.dumps(topic_from_prev, ensure_ascii=False, indent=2) if topic_from_prev else '{"title": "", "exposure": "", "outcome": "", "population": ""}',
        height=200,
    )
    dataset = st.selectbox("데이터셋", ["KYRBS"])

    if st.button("✅ 타당성 검증", type="primary"):
        try:
            topic = json.loads(topic_json)
            with st.spinner("데이터셋 변수 기반 타당성 분석 중..."):
                from src.research.research_pipeline import ResearchPipeline
                rp = ResearchPipeline()
                result = rp.validate_feasibility(topic, dataset)

                feasible = result.get("is_feasible")
                confidence = result.get("confidence", "?")
                icon = "✅" if feasible else "❌"
                st.metric("타당성", f"{icon} {'가능' if feasible else '어려움'} (신뢰도: {confidence})")

                col1, col2 = st.columns(2)
                with col1:
                    avail = result.get("available_variables", [])
                    st.markdown(f"**사용 가능한 변수 ({len(avail)}개):**")
                    for v in avail:
                        st.markdown(f"  ✅ `{v}`")
                with col2:
                    missing = result.get("missing_variables", [])
                    st.markdown(f"**부족한 변수 ({len(missing)}개):**")
                    for v in missing:
                        st.markdown(f"  ❌ `{v}`")

                st.markdown(f"**판정:** {result.get('verdict', '-')}")

                if result.get("modifications_needed"):
                    st.subheader("수정 권고")
                    for m in result["modifications_needed"]:
                        st.markdown(f"- {m}")

        except Exception as e:
            st.error(f"오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# 논문 작성
# ════════════════════════════════════════════════════════════════════════
elif page == "📝 논문 작성":
    st.title("📝 조유선 스타일 논문 작성")
    st.info("조유선 교수 논문 스타일 시드(11편 분석)를 기반으로 논문 초안을 생성합니다.")

    topic_from_prev = st.session_state.get("selected_topic", {})

    col1, col2 = st.columns(2)
    with col1:
        topic_title = st.text_input("연구 제목", value=topic_from_prev.get("title", ""))
        journal = st.text_input("목표 저널", placeholder="예: Nutrients, IJERPH, BMC Public Health")
        design = st.selectbox("연구 설계", ["Cross-sectional", "Cohort", "Case-control", "RCT"])
    with col2:
        dataset_name = st.text_input("데이터셋", value="KYRBS 2025 (제21차 청소년건강행태조사)")
        sample_size = st.text_input("표본 수", placeholder="예: 54,633")
        survey_year = st.text_input("조사 연도", value="2025")

    st.subheader("주요 결과 입력")
    results_text = st.text_area(
        "분석 결과 (통계값 포함)",
        placeholder="예: 스마트폰 주중 4시간 이상 사용군에서 수면 부족 OR=2.34 (95% CI: 1.89-2.91, p<0.001)...",
        height=150,
    )

    section = st.selectbox("작성할 섹션", ["전체 논문", "Abstract", "Introduction", "Methods", "Results", "Discussion"])

    if st.button("✍️ 논문 작성 시작", type="primary"):
        if not topic_title or not results_text:
            st.error("연구 제목과 주요 결과를 입력하세요.")
        else:
            with st.spinner("조유선 스타일로 논문 작성 중... (1-2분 소요)"):
                try:
                    from src.research.research_pipeline import ResearchPipeline

                    rp = ResearchPipeline()
                    topic = {
                        "title": topic_title,
                        "exposure": topic_from_prev.get("exposure", ""),
                        "outcome": topic_from_prev.get("outcome", ""),
                        "population": topic_from_prev.get("population", ""),
                    }
                    study_info = {
                        "dataset": dataset_name,
                        "design": design,
                        "sample_size": sample_size,
                        "survey_year": survey_year,
                        "journal": journal,
                    }
                    results = {"summary": results_text}

                    if section == "전체 논문":
                        draft = rp.write_paper(topic, study_info, results)
                    else:
                        from src.research.paper_writer import PaperWriter
                        from src.profile.author_profile import AuthorProfile
                        from src.library.methods_library import MethodsLibrary
                        from src.library.dataset_library import DatasetLibrary
                        from src.rag.pipeline import RAGPipeline

                        author = AuthorProfile("Yoosun Cho")
                        methods = MethodsLibrary()
                        datasets = DatasetLibrary()
                        rag = RAGPipeline()
                        writer = PaperWriter(author, methods, datasets, rag)

                        fn_map = {
                            "Abstract": writer.write_abstract,
                            "Introduction": writer.write_introduction,
                            "Methods": writer.write_methods,
                            "Results": writer.write_results,
                            "Discussion": writer.write_discussion,
                        }
                        fn = fn_map[section]
                        draft = fn(topic=topic_title, study_info=study_info, results=results)

                    st.session_state["draft"] = draft
                    st.success("✅ 논문 작성 완료!")

                except Exception as e:
                    st.error(f"오류: {e}")
                    import traceback
                    st.code(traceback.format_exc())

    if "draft" in st.session_state:
        st.divider()
        st.subheader("생성된 논문 초안")
        st.text_area("논문 내용", value=st.session_state["draft"], height=600)
        st.download_button(
            "📥 TXT로 다운로드",
            data=st.session_state["draft"].encode("utf-8"),
            file_name=f"draft_{topic_title[:30]}.txt",
            mime="text/plain",
        )


# ════════════════════════════════════════════════════════════════════════
# 데이터셋 라이브러리
# ════════════════════════════════════════════════════════════════════════
elif page == "📊 데이터셋 라이브러리":
    st.title("📊 데이터셋 라이브러리")

    try:
        from src.library.dataset_library import DatasetLibrary
        lib = DatasetLibrary()
        datasets = lib.list_datasets()

        if not datasets:
            st.warning("등록된 데이터셋이 없습니다.")
        else:
            selected_ds = st.selectbox("데이터셋 선택", datasets)
            ds = lib.get_dataset(selected_ds)

            col1, col2, col3 = st.columns(3)
            col1.metric("변수 수", len(ds.get("variables", {})))
            col2.metric("교란변수", len(ds.get("common_confounders", [])))
            col3.metric("분석 주의사항", len(ds.get("analysis_notes", [])))

            st.markdown(f"**설명:** {ds.get('description', '-')}")

            # 변수 검색
            st.subheader("변수 검색")
            search = st.text_input("변수명 또는 레이블 검색", placeholder="예: bmi, 흡연, smoking")

            variables = ds.get("variables", {})
            if search:
                variables = {k: v for k, v in variables.items()
                             if search.lower() in k.lower() or search.lower() in v.get("label", "").lower()}

            st.caption(f"{len(variables)}개 변수 표시")

            for var_name, var_info in variables.items():
                with st.expander(f"`{var_name}` — {var_info.get('label', '')} ({var_info.get('type', '')})", expanded=False):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**타입:** {var_info.get('type', '-')}")
                        st.markdown(f"**단위:** {var_info.get('unit', '-') or '-'}")
                        st.markdown(f"**결측 처리:** {var_info.get('missing_strategy', '-')}")
                    with c2:
                        st.markdown(f"**처리 방법:** {var_info.get('processing', '-')}")
                        if var_info.get("cutoffs"):
                            st.markdown(f"**코딩:** {var_info.get('cutoffs', {})}")
                    if var_info.get("notes"):
                        st.info(var_info["notes"])

            # 교란변수
            if ds.get("common_confounders"):
                st.subheader("공통 교란변수")
                st.markdown(", ".join(f"`{c}`" for c in ds["common_confounders"]))

            # 분석 주의사항
            if ds.get("analysis_notes"):
                st.subheader("분석 주의사항")
                for note in ds["analysis_notes"]:
                    st.markdown(f"⚠️ {note}")

    except Exception as e:
        st.error(f"라이브러리 로드 오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# Agent Q&A
# ════════════════════════════════════════════════════════════════════════
elif page == "🤖 Agent Q&A":
    st.title("🤖 Medical Agent Q&A")
    st.info("학습된 논문과 데이터베이스를 기반으로 질문에 답합니다.")

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    if prompt := st.chat_input("질문을 입력하세요..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            with st.spinner("답변 생성 중..."):
                try:
                    from src.agent.medical_agent import MedicalAgent
                    agent = MedicalAgent()
                    response = agent.ask(prompt)
                    answer = response.get("answer", response.get("raw", str(response)))
                    st.markdown(answer)
                    st.session_state.messages.append({"role": "assistant", "content": answer})

                    if response.get("sources"):
                        with st.expander("참고 문헌"):
                            for s in response["sources"][:3]:
                                st.markdown(f"- {s.get('filename', s.get('source', ''))}")

                except Exception as e:
                    err_msg = f"오류: {e}"
                    st.error(err_msg)
                    st.session_state.messages.append({"role": "assistant", "content": err_msg})


# ════════════════════════════════════════════════════════════════════════
# NotebookLM 허브
# ════════════════════════════════════════════════════════════════════════
elif page == "☁️ NotebookLM 허브":
    st.title("☁️ NotebookLM Research Hub")
    st.caption(
        "논문 레퍼런스를 NotebookLM(기본)에 동기화하고, "
        "서버 다운 시 로컬 ChromaDB 자동 폴백."
    )

    # ── 상태 카드 ─────────────────────────────────────────────────────
    try:
        from src.storage.manager import StorageManager
        sm = StorageManager()
        stat = sm.status()

        col1, col2, col3 = st.columns(3)
        nlm_color = "🟢" if stat["notebooklm"] == "online" else "🔴"
        col1.metric("NotebookLM", f"{nlm_color} {stat['notebooklm']}")
        col2.metric("로컬 ChromaDB", f"{stat['local_chromadb_chunks']}개 청크")
        col3.metric("활성 스토리지", stat["active_storage"])

        st.divider()

    except Exception as e:
        st.error(f"스토리지 초기화 오류: {e}")
        st.stop()

    # ── 탭 구성 ───────────────────────────────────────────────────────
    tab_papers, tab_query, tab_notebooks = st.tabs(
        ["📄 논문 추가", "🔎 노트북 쿼리", "📋 노트북 목록"]
    )

    # ── 탭 1: 논문 추가 ───────────────────────────────────────────────
    with tab_papers:
        st.subheader("PubMed 검색 → NotebookLM 동기화")
        st.caption("YouTube → NotebookLM 패턴과 동일. PubMed 논문을 소스로 업로드합니다.")

        topic_input = st.text_input(
            "연구 주제",
            placeholder="예: 청소년 비만과 수면 부족",
            key="nlm_topic",
        )
        search_query = st.text_input(
            "PubMed 검색어",
            placeholder="예: adolescent obesity sleep Korea KYRBS",
            key="nlm_query",
        )
        n_papers = st.slider("최대 논문 수", 3, 20, 10)

        col_a, col_b = st.columns(2)
        with col_a:
            add_text = st.toggle("텍스트 소스로 추가 (추상 포함)", value=True)
        with col_b:
            add_url = st.toggle("PubMed URL 소스도 추가", value=False)

        if st.button("🔍 검색 후 NotebookLM에 동기화", type="primary", disabled=not (topic_input and search_query)):
            with st.spinner(f"PubMed 검색 중: {search_query}..."):
                try:
                    from src.research.novelty_checker import NoveltyChecker
                    checker = NoveltyChecker()
                    papers = checker.search_papers(search_query, max_results=n_papers)

                    if not papers:
                        st.warning("PubMed 검색 결과가 없습니다.")
                    else:
                        st.success(f"✅ {len(papers)}편 검색 완료")
                        with st.expander("검색된 논문 목록", expanded=True):
                            for i, p in enumerate(papers, 1):
                                st.markdown(f"**{i}.** {p.get('title','?')} ({p.get('year','?')})")

                        with st.spinner("NotebookLM에 동기화 중..."):
                            result = sm.store_papers(papers, topic=topic_input)

                            if add_url and stat["notebooklm"] == "online":
                                from src.notebooklm.paper_sync import PaperSync
                                ps = PaperSync()
                                nb_id = ps.get_or_create_topic_notebook(topic_input)
                                if nb_id:
                                    url_count = 0
                                    for p in papers:
                                        if p.get("pmid"):
                                            ps.add_pubmed_url(nb_id, p["pmid"])
                                            url_count += 1
                                    st.info(f"PubMed URL {url_count}개 추가")

                        st.success(
                            f"NotebookLM: {result['nlm']}편 / "
                            f"로컬 ChromaDB: {result['local']}편 저장"
                        )
                        st.session_state["nlm_last_topic"] = topic_input

                except Exception as e:
                    st.error(f"오류: {e}")
                    import traceback
                    st.code(traceback.format_exc())

        st.divider()
        st.subheader("로컬 PDF → NotebookLM 동기화")
        pdf_dir = st.text_input(
            "PDF 폴더 경로",
            value="data/papers/BRCT",
            key="nlm_pdf_dir",
        )
        pdf_topic = st.text_input("PDF 연구 주제", key="nlm_pdf_topic")

        if st.button("📂 PDF 폴더 동기화", disabled=not pdf_topic):
            with st.spinner("PDF 업로드 중..."):
                try:
                    result = sm.sync_pdf_dir(pdf_dir, pdf_topic)
                    st.success(
                        f"NotebookLM: {result['nlm']}개 / "
                        f"로컬: {result['local']}개 문서 동기화 완료"
                    )
                except Exception as e:
                    st.error(f"오류: {e}")

    # ── 탭 2: 노트북 쿼리 ─────────────────────────────────────────────
    with tab_query:
        st.subheader("NotebookLM 노트북 쿼리")

        notebooks = sm.get_topic_notebooks()
        if not notebooks:
            st.info("동기화된 주제가 없습니다. '논문 추가' 탭에서 먼저 동기화하세요.")
        else:
            topic_options = [n["topic"] for n in notebooks]
            selected_topic = st.selectbox(
                "주제 선택",
                topic_options,
                index=0,
                key="nlm_select_topic",
            )

            query_mode = st.radio(
                "쿼리 모드",
                ["자유 질문", "연구 전방위 분석"],
                horizontal=True,
            )

            if query_mode == "자유 질문":
                user_q = st.text_area(
                    "질문",
                    placeholder="예: 이 논문들의 핵심 연구 공백은?",
                    height=100,
                )
                if st.button("🔎 쿼리 실행", type="primary", disabled=not user_q):
                    with st.spinner("NotebookLM 분석 중 (Google 비용 부담)..."):
                        try:
                            result = sm.search(user_q, topic=selected_topic)
                            st.markdown(f"**출처:** `{result['source']}`")
                            st.markdown("---")
                            st.markdown(result["answer"])
                        except Exception as e:
                            st.error(f"오류: {e}")

            else:
                if st.button("🧪 연구 전방위 분석 실행", type="primary"):
                    with st.spinner("5개 분석 질문 실행 중..."):
                        try:
                            analysis = sm.analyze_topic(selected_topic)
                            if "error" in analysis:
                                st.error(analysis["error"])
                            else:
                                label_map = {
                                    "gap": "연구 공백",
                                    "methods": "주요 방법론",
                                    "exposure_outcome": "노출·결과변수 패턴",
                                    "novelty_angle": "신규 연구 각도",
                                    "key_findings": "핵심 발견",
                                }
                                for key, label in label_map.items():
                                    with st.expander(f"**{label}**", expanded=(key == "gap")):
                                        st.markdown(analysis.get(key, "-"))
                        except Exception as e:
                            st.error(f"오류: {e}")

    # ── 탭 3: 노트북 목록 ─────────────────────────────────────────────
    with tab_notebooks:
        st.subheader("관리 중인 NotebookLM 노트북")

        notebooks = sm.get_topic_notebooks()
        if not notebooks:
            st.info("아직 생성된 노트북이 없습니다.")
        else:
            for nb in notebooks:
                nb_url = (
                    f"https://notebooklm.google.com/notebook/{nb['notebook_id']}"
                    if nb["notebook_id"]
                    else "#"
                )
                st.markdown(
                    f"- **{nb['topic']}** — "
                    f"[NotebookLM에서 열기]({nb_url})"
                )

        if stat["notebooklm"] == "online":
            st.divider()
            if st.button("☁️ NotebookLM 전체 노트북 목록 새로고침"):
                with st.spinner("목록 가져오는 중..."):
                    try:
                        from src.notebooklm.client import NLMClient
                        client = NLMClient()
                        all_nbs = client.list_notebooks()
                        st.caption(f"NotebookLM 계정에 총 {len(all_nbs)}개 노트북")
                        for nb in all_nbs:
                            prefix = "[MA] " if nb["title"].startswith("[MA]") else ""
                            st.markdown(
                                f"- {prefix}**{nb['title']}** "
                                f"(소스 {nb['source_count']}개)"
                            )
                    except Exception as e:
                        st.error(f"오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# 📥 논문 업로드 & 인제스트
# ════════════════════════════════════════════════════════════════════════
elif page == "📥 논문 업로드 & 인제스트":
    st.title("📥 논문 업로드 & 인제스트")
    st.caption("PDF 파일 또는 PubMed URL을 지식베이스(DB)에 학습시킵니다.")

    tab_pdf, tab_pubmed, tab_text = st.tabs(["PDF 파일 업로드", "PubMed 검색 학습", "텍스트 직접 입력"])

    with tab_pdf:
        st.subheader("PDF 파일 → 지식베이스")
        uploaded = st.file_uploader("PDF 파일 선택 (복수 가능)", type=["pdf"], accept_multiple_files=True)
        topic_tag = st.text_input("주제 태그 (메타데이터용)", placeholder="예: 청소년 비만, BRCT, 유방암")

        if st.button("📚 인제스트 시작", type="primary", disabled=not uploaded):
            from src.ingestion.pdf_reader import PDFReader
            from src.ingestion.chunker import TextChunker
            from src.vectordb.store import get_vector_store
            import tempfile, os

            reader = PDFReader()
            chunker = TextChunker()
            store = get_vector_store()

            total_chunks = 0
            for uf in uploaded:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uf.read())
                    tmp_path = tmp.name
                try:
                    with st.spinner(f"처리 중: {uf.name}"):
                        pages = reader.read(tmp_path)
                        text = " ".join(p.get("text", "") for p in pages)
                        chunks = chunker.chunk(text, metadata={
                            "filename": uf.name,
                            "source": "pdf_upload",
                            "topic": topic_tag,
                        })
                        added = store.add_chunks(chunks)
                        total_chunks += added
                        st.success(f"✅ {uf.name} → {added}개 청크 학습")
                except Exception as e:
                    st.error(f"❌ {uf.name}: {e}")
                finally:
                    os.unlink(tmp_path)

            if total_chunks:
                st.balloons()
                st.success(f"총 {total_chunks}개 청크 지식베이스에 추가 완료!")

    with tab_pubmed:
        st.subheader("PubMed 검색 → 지식베이스 학습")
        pm_query = st.text_input("검색어", placeholder="adolescent obesity sleep Korea KYRBS")
        pm_n = st.slider("최대 논문 수", 5, 50, 20)
        pm_topic = st.text_input("주제 태그", placeholder="예: 청소년 수면")
        also_nlm = st.checkbox("NotebookLM에도 동기화", value=True)

        if st.button("🔍 검색 후 학습", type="primary", disabled=not pm_query):
            with st.spinner(f"PubMed 검색 중..."):
                try:
                    from src.research.novelty_checker import NoveltyChecker
                    from src.vectordb.store import get_vector_store
                    from src.ingestion.chunker import TextChunker

                    checker = NoveltyChecker()
                    papers = checker.search_papers(pm_query, max_results=pm_n)

                    if not papers:
                        st.warning("결과 없음")
                    else:
                        store = get_vector_store()
                        chunker = TextChunker()
                        total = 0
                        for p in papers:
                            from src.notebooklm.paper_sync import PaperSync
                            text = PaperSync._format_paper_text(p)
                            chunks = chunker.chunk(text, metadata={
                                "filename": p.get("title", "paper")[:80],
                                "source": f"pubmed:{p.get('pmid','')}",
                                "topic": pm_topic,
                            })
                            total += store.add_chunks(chunks)

                        if also_nlm:
                            from src.storage.manager import StorageManager
                            sm = StorageManager()
                            nlm_r = sm.store_papers(papers, topic=pm_topic)
                            st.info(f"NotebookLM: {nlm_r['nlm']}편 동기화")

                        st.success(f"✅ {len(papers)}편 / {total}개 청크 학습 완료")
                        with st.expander("학습된 논문 목록"):
                            for p in papers:
                                st.markdown(f"- **{p.get('title','')}** ({p.get('year','')})")
                except Exception as e:
                    st.error(f"오류: {e}")
                    import traceback; st.code(traceback.format_exc())

    with tab_text:
        st.subheader("텍스트 직접 입력 → 지식베이스")
        txt_title = st.text_input("제목 / 출처")
        txt_content = st.text_area("내용 (논문 전문, 초록 등)", height=300)
        txt_topic = st.text_input("주제 태그", key="txt_topic")

        if st.button("💾 저장", type="primary", disabled=not (txt_title and txt_content)):
            try:
                from src.ingestion.chunker import TextChunker
                from src.vectordb.store import get_vector_store
                store = get_vector_store()
                chunker = TextChunker()
                chunks = chunker.chunk(txt_content, metadata={
                    "filename": txt_title[:80],
                    "source": "manual_input",
                    "topic": txt_topic,
                })
                added = store.add_chunks(chunks)
                st.success(f"✅ {added}개 청크 저장 완료")
            except Exception as e:
                st.error(f"오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# 🧠 지식베이스 현황 대시보드
# ════════════════════════════════════════════════════════════════════════
elif page == "🧠 지식베이스 현황":
    st.title("🧠 지식베이스 현황")

    import os
    db_type = "Supabase (클라우드)" if os.environ.get("SUPABASE_DB_URL") else "ChromaDB (로컬)"

    try:
        from src.vectordb.store import get_vector_store
        store = get_vector_store()

        col1, col2, col3 = st.columns(3)
        col1.metric("DB 유형", db_type)
        col2.metric("총 청크 수", f"{store.count():,}개")

        sources = store.list_sources()
        col3.metric("학습된 문서 수", f"{len(sources)}개")

        st.divider()

        if sources:
            st.subheader("학습된 문서 목록")
            search_src = st.text_input("문서명 검색", placeholder="필터링...")
            filtered = [s for s in sources if not search_src or search_src.lower() in s.lower()]
            for s in filtered:
                st.markdown(f"- `{s}`")
        else:
            st.info("아직 학습된 문서가 없습니다. '📥 논문 업로드 & 인제스트'에서 시작하세요.")

        st.divider()
        st.subheader("의미 검색 테스트")
        test_q = st.text_input("검색어 입력", placeholder="예: 청소년 비만 위험요인")
        if test_q:
            hits = store.search(test_q, n_results=5)
            for i, h in enumerate(hits, 1):
                with st.expander(f"[{i}] {h.get('metadata',{}).get('filename','?')} (유사도: {h.get('score',0):.3f})"):
                    st.text(h["text"][:500])

    except Exception as e:
        st.error(f"DB 연결 오류: {e}")

    st.divider()
    st.subheader("NotebookLM 현황")
    try:
        from src.storage.manager import StorageManager
        sm = StorageManager()
        stat = sm.status()
        nlm_color = "🟢" if stat["notebooklm"] == "online" else "🔴"
        st.metric("NotebookLM", f"{nlm_color} {stat['notebooklm']}")
        notebooks = sm.get_topic_notebooks()
        if notebooks:
            st.markdown(f"**동기화된 주제**: {len(notebooks)}개")
            for nb in notebooks:
                st.markdown(f"- {nb['topic']}")
        else:
            st.info("동기화된 NotebookLM 노트북 없음")
    except Exception as e:
        st.error(f"NotebookLM 오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# 👤 저자 프로필 구축
# ════════════════════════════════════════════════════════════════════════
elif page == "👤 저자 프로필 구축":
    st.title("👤 저자 프로필 구축")
    st.caption("논문 텍스트를 분석하여 저자의 문체/방법론 스타일 시드를 구축합니다.")

    try:
        from src.profile.author_profile import AuthorProfile
        profile = AuthorProfile("Yoosun Cho")
        papers_n = profile._profile.get("papers_analysed", 0)
        st.metric("현재 학습된 논문 수", f"{papers_n}편")
    except Exception as e:
        st.error(f"프로필 로드 오류: {e}")
        st.stop()

    st.divider()
    tab_upload, tab_text_prof, tab_summary = st.tabs(["논문 텍스트로 학습", "직접 입력", "현재 프로필 확인"])

    with tab_upload:
        st.subheader("PDF에서 저자 스타일 학습")
        pdf_files = st.file_uploader("논문 PDF (복수 선택 가능)", type=["pdf"], accept_multiple_files=True, key="prof_pdf")

        if st.button("🧠 스타일 분석 시작", type="primary", disabled=not pdf_files):
            from src.ingestion.pdf_reader import PDFReader
            import tempfile, os

            reader = PDFReader()
            results = []
            for uf in pdf_files:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                    tmp.write(uf.read())
                    tmp_path = tmp.name
                try:
                    with st.spinner(f"분석 중: {uf.name}"):
                        pages = reader.read(tmp_path)
                        text = " ".join(p.get("text", "") for p in pages)
                        if len(text) < 200:
                            st.warning(f"텍스트가 너무 짧음: {uf.name}")
                            continue
                        result = profile.analyse_paper(text, title=uf.name)
                        results.append(result)
                        icon = "✅" if result.get("status") == "analysed" else "⏭️"
                        st.markdown(f"{icon} {uf.name}")
                except Exception as e:
                    st.error(f"❌ {uf.name}: {e}")
                finally:
                    os.unlink(tmp_path)

            if results:
                analysed = sum(1 for r in results if r.get("status") == "analysed")
                st.success(f"✅ {analysed}편 스타일 학습 완료!")
                st.rerun()

    with tab_text_prof:
        st.subheader("논문 텍스트 직접 입력")
        ptitle = st.text_input("논문 제목")
        ptext = st.text_area("논문 텍스트 (Abstract + Introduction 등)", height=300)

        if st.button("📖 스타일 학습", type="primary", disabled=not (ptitle and ptext)):
            with st.spinner("분석 중..."):
                try:
                    result = profile.analyse_paper(ptext, title=ptitle)
                    if result.get("status") == "analysed":
                        st.success("✅ 스타일 학습 완료!")
                    else:
                        st.warning(f"스킵됨: {result.get('reason','')}")
                    st.rerun()
                except Exception as e:
                    st.error(f"오류: {e}")

    with tab_summary:
        st.subheader("현재 저자 프로필 요약")
        try:
            summary = profile.summary()
            st.markdown(summary)
        except Exception as e:
            st.error(f"오류: {e}")


# ════════════════════════════════════════════════════════════════════════
# 🔄 자동 학습 루프
# ════════════════════════════════════════════════════════════════════════
elif page == "🔄 자동 학습 루프":
    st.title("🔄 자동 학습 루프")
    st.caption("PubMed 키워드를 설정하면 검색 → 인제스트 → NotebookLM 동기화를 자동으로 실행합니다.")

    LOOP_CFG = Path("data/auto_learn_config.json")

    def _load_loop_cfg():
        if LOOP_CFG.exists():
            return json.loads(LOOP_CFG.read_text(encoding="utf-8"))
        return {"jobs": []}

    def _save_loop_cfg(cfg):
        LOOP_CFG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

    cfg = _load_loop_cfg()

    # ── 키워드 등록 ───────────────────────────────────────────────────
    st.subheader("키워드 등록")
    with st.form("add_job"):
        col1, col2, col3 = st.columns([3, 2, 1])
        with col1:
            kw = st.text_input("PubMed 검색어", placeholder="adolescent obesity sleep Korea")
        with col2:
            topic = st.text_input("주제 태그", placeholder="청소년 수면")
        with col3:
            n_max = st.number_input("최대 논문 수", 5, 50, 20)
        submitted = st.form_submit_button("➕ 추가")

    if submitted and kw and topic:
        cfg["jobs"].append({"keyword": kw, "topic": topic, "max": int(n_max), "last_run": None})
        _save_loop_cfg(cfg)
        st.success(f"✅ '{kw}' 등록됨")
        st.rerun()

    # ── 등록된 키워드 목록 ────────────────────────────────────────────
    st.subheader("등록된 학습 키워드")
    if not cfg["jobs"]:
        st.info("등록된 키워드가 없습니다. 위에서 추가하세요.")
    else:
        for i, job in enumerate(cfg["jobs"]):
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.markdown(f"**{job['keyword']}** `{job['topic']}` (최대 {job['max']}편)")
            with col2:
                last = job.get("last_run") or "미실행"
                st.caption(f"마지막 실행: {last}")
            with col3:
                if st.button("삭제", key=f"del_{i}"):
                    cfg["jobs"].pop(i)
                    _save_loop_cfg(cfg)
                    st.rerun()

    st.divider()

    # ── 즉시 실행 ─────────────────────────────────────────────────────
    st.subheader("즉시 실행")
    if cfg["jobs"] and st.button("▶️ 전체 키워드 지금 실행", type="primary"):
        from src.research.novelty_checker import NoveltyChecker
        from src.storage.manager import StorageManager
        from datetime import datetime

        checker = NoveltyChecker()
        sm = StorageManager()
        total_papers = 0

        for job in cfg["jobs"]:
            with st.spinner(f"수집 중: {job['keyword']}"):
                try:
                    papers = checker.search_papers(job["keyword"], max_results=job["max"])
                    if papers:
                        result = sm.store_papers(papers, topic=job["topic"])
                        total_papers += len(papers)
                        st.success(
                            f"✅ {job['keyword']}: {len(papers)}편 수집 "
                            f"(NLM: {result['nlm']}, Local: {result['local']})"
                        )
                    else:
                        st.warning(f"'{job['keyword']}': 결과 없음")
                    job["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M")
                except Exception as e:
                    st.error(f"'{job['keyword']}' 오류: {e}")

        _save_loop_cfg(cfg)
        st.success(f"✅ 전체 완료: {total_papers}편 학습")

    st.divider()
    st.subheader("Streamlit Cloud 자동 실행 안내")
    st.info(
        "Streamlit Cloud에서는 백그라운드 스케줄러가 실행되지 않습니다.\n\n"
        "**로컬에서 정기 실행:** `python run_auto_learn.py` 를 Windows 작업 스케줄러 또는 cron에 등록하세요."
    )
