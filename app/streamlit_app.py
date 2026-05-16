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
import json
from pathlib import Path

# ── 페이지 설정 ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Medical-Agent",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

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
    st.divider()

    page = st.radio(
        "메뉴",
        ["🏠 홈", "📚 연구 주제 생성", "🔍 신규성 확인", "✅ 타당성 검증", "📝 논문 작성", "📊 데이터셋 라이브러리", "🤖 Agent Q&A"],
        label_visibility="collapsed",
    )
    st.divider()

    # 시스템 상태
    st.caption("시스템 상태")
    try:
        from src.vectordb.store import VectorStore
        store = VectorStore()
        chunk_count = store.count()
        st.success(f"ChromaDB: {chunk_count}개 청크")
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
