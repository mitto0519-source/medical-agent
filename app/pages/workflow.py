"""
단계별 연구 워크플로우 페이지
각 단계에서 사람이 검수·승인 후 다음 단계로 진행
"""

import streamlit as st
from streamlit.runtime.scriptrunner_utils.script_run_context import get_script_run_ctx
import json
import uuid
from pathlib import Path
import sys, os
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.chdir(str(Path(__file__).parent.parent.parent))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'
from dotenv import load_dotenv
load_dotenv()

def _is_streamlit_running() -> bool:
    try:
        return get_script_run_ctx() is not None
    except Exception:
        return False


from src.research.research_workflow import ResearchWorkflow, STAGES, STAGE_LABELS

def run_workflow_page():
        st.set_page_config(page_title="단계별 연구 워크플로우", page_icon="🔬", layout="wide")
        st.title("🔬 단계별 연구 워크플로우")
        st.caption("각 단계에서 검수·승인 후 다음 단계로 진행됩니다.")
        
        # ── 워크플로우 선택/생성 ──────────────────────────────────────────────
        with st.sidebar:
        st.header("워크플로우 관리")
        existing = sorted(Path("data/workflows").glob("*.json")) if Path("data/workflows").exists() else []
        existing_ids = [p.stem for p in existing if not p.stem.endswith("_analysis")]
        
        mode = st.radio("", ["기존 불러오기", "새로 시작"])
        
        if mode == "새로 시작":
        new_id = st.text_input("워크플로우 이름", value=f"study_{str(uuid.uuid4())[:8]}")
        dataset = st.selectbox("데이터셋", ["KYRBS"])
        if st.button("시작", type="primary"):
            st.session_state["wf_id"] = new_id
            st.session_state["wf_dataset"] = dataset
            st.rerun()
        else:
        if existing_ids:
            sel = st.selectbox("워크플로우 선택", existing_ids)
            if st.button("불러오기"):
                st.session_state["wf_id"] = sel
                st.rerun()
        else:
            st.info("저장된 워크플로우가 없습니다.")
        
        if "wf_id" in st.session_state:
        st.divider()
        st.caption(f"현재: `{st.session_state['wf_id']}`")
        
        # ── 워크플로우 로드 ────────────────────────────────────────────────────
        if "wf_id" not in st.session_state:
        st.info("왼쪽에서 워크플로우를 시작하거나 불러오세요.")
        st.stop()
        
        wf = ResearchWorkflow(
        workflow_id=st.session_state["wf_id"],
        dataset_name=st.session_state.get("wf_dataset", "KYRBS"),
        )
        
        # ── 진행 상태 표시 ────────────────────────────────────────────────────
        st.subheader("진행 상태")
        cols = st.columns(len(STAGES))
        for i, (stage, label) in enumerate(STAGE_LABELS.items()):
        data = wf.stage_data(stage)
        if not data:
        icon = "⬜"
        elif data.get("approved"):
        icon = "✅"
        elif data.get("rejection_feedback"):
        icon = "🔴"
        else:
        icon = "🟡"
        cols[i].markdown(f"**{icon}**  \n{label.split(':')[1].strip()}")
        
        st.divider()
        current = wf.current_stage()
        
        # ════════════════════════════════════════════════════════════════════════
        # STAGE 1: 주제 제안
        # ════════════════════════════════════════════════════════════════════════
        st.header(STAGE_LABELS["topic_proposal"])
        
        if not wf.stage_data("topic_proposal"):
        focus = st.text_input("연구 포커스", placeholder="예: 청소년 스마트폰 사용과 정신건강")
        n = st.slider("제안 주제 수", 3, 8, 5)
        if st.button("🚀 주제 생성", type="primary", disabled=not focus):
        with st.spinner("Claude가 KYRBS 변수를 기반으로 주제를 생성 중..."):
            topics = wf.propose_topics(focus, n)
        st.success(f"{len(topics)}개 주제 생성 완료")
        st.rerun()
        
        else:
        data = wf.stage_data("topic_proposal")
        topics = data["topics"]
        
        if data.get("approved"):
        sel = data.get("selected_topic", {})
        st.success(f"✅ 선택된 주제: **{sel.get('title', '')}**")
        else:
        st.info("아래에서 주제를 하나 선택하고 승인하세요.")
        for i, t in enumerate(topics):
            with st.expander(f"[{i+1}] {t.get('title', '')}", expanded=(i == 0)):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**노출:** `{t.get('exposure', '')}`")
                    st.markdown(f"**결과:** `{t.get('outcome', '')}`")
                    st.markdown(f"**설계:** {t.get('suggested_design', '')}")
                with c2:
                    st.markdown(f"**대상:** {t.get('population', '')}")
                    covs = t.get('covariates', [])
                    st.markdown(f"**공변량:** {', '.join([f'`{c}`' for c in covs[:6]])}")
                st.markdown(f"**근거:** {t.get('rationale', '')}")
                st.markdown(f"**신규성:** {t.get('novelty_hint', '')}")
                st.markdown(f"**통계 주의:** {t.get('analysis_note', '')}")
        
                if st.button(f"이 주제 선택 & 승인", key=f"sel_{i}", type="primary"):
                    wf.select_topic(i)
                    wf.approve("topic_proposal")
                    st.rerun()
        
        st.divider()
        if st.button("🔄 주제 다시 생성"):
            focus = data["focus"]
            with st.spinner("재생성 중..."):
                wf.propose_topics(focus, len(topics))
            st.rerun()
        
        if not wf.is_approved("topic_proposal"):
        st.stop()
        
        st.divider()
        
        # ════════════════════════════════════════════════════════════════════════
        # STAGE 2: 변수 계획
        # ════════════════════════════════════════════════════════════════════════
        st.header(STAGE_LABELS["variable_plan"])
        
        if not wf.stage_data("variable_plan"):
        if st.button("📋 변수 계획 생성", type="primary"):
        with st.spinner("변수별 코딩 방법, 결측 처리, 재범주화 계획 생성 중..."):
            var_plan = wf.plan_variables()
        st.rerun()
        else:
        data = wf.stage_data("variable_plan")
        plan = data["plan"]
        
        # 노출변수
        if "exposure_variable" in plan:
        ev = plan["exposure_variable"]
        with st.expander("📌 노출변수 (Exposure)", expanded=not data.get("approved")):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**변수명:** `{ev.get('name', '')}`")
                st.markdown(f"**레이블:** {ev.get('label', '')}")
                st.markdown(f"**원래 코딩:**")
                st.code(str(ev.get('original_coding', '')))
            with c2:
                st.markdown(f"**분석용 코딩:**")
                st.code(str(ev.get('analysis_coding', '')))
                st.markdown(f"**기준 범주:** `{ev.get('reference_category', '')}`")
                st.markdown(f"**근거:** {ev.get('rationale', '')}")
        
        # 결과변수
        if "outcome_variable" in plan:
        ov = plan["outcome_variable"]
        with st.expander("🎯 결과변수 (Outcome)", expanded=not data.get("approved")):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**변수명:** `{ov.get('name', '')}`")
                st.markdown(f"**레이블:** {ov.get('label', '')}")
                st.code(str(ov.get('original_coding', '')))
            with c2:
                st.code(str(ov.get('analysis_coding', '')))
                st.markdown(f"**기준 범주:** `{ov.get('reference_category', '')}`")
        
        # 공변량
        covs = plan.get("covariates", [])
        if covs:
        with st.expander(f"🔧 공변량 ({len(covs)}개)", expanded=False):
            for cv in covs:
                if isinstance(cv, dict):
                    st.markdown(f"- **`{cv.get('name', '')}`** ({cv.get('label', '')}): {cv.get('analysis_coding', '')}")
                else:
                    st.markdown(f"- {cv}")
        
        # 제외 기준
        excl = plan.get("exclusion_criteria", [])
        if excl:
        with st.expander("🚫 제외 기준"):
            for e in excl:
                st.markdown(f"- {e}")
        
        # 분석 주의사항
        notes = plan.get("analysis_notes", [])
        if notes:
        with st.expander("⚠️ 분석 주의사항"):
            for n in notes:
                st.markdown(f"- {n}")
        
        if not data.get("approved"):
        st.divider()
        modifications = st.text_area(
            "수정 사항 (없으면 비워두세요)",
            placeholder="예: 노출변수를 3범주 대신 2범주로 변경 (≥4시간 vs <4시간)...",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ 승인", type="primary"):
                wf.approve("variable_plan", modifications)
                st.rerun()
        with col_b:
            feedback = st.text_input("반려 사유")
            if st.button("🔴 반려 후 재생성"):
                wf.reject("variable_plan", feedback)
                with st.spinner("재생성 중..."):
                    wf.plan_variables()
                st.rerun()
        else:
        st.success("✅ 변수 계획 승인됨")
        
        if not wf.is_approved("variable_plan"):
        st.stop()
        
        st.divider()
        
        # ════════════════════════════════════════════════════════════════════════
        # STAGE 3: 통계 분석 계획 (SAP)
        # ════════════════════════════════════════════════════════════════════════
        st.header(STAGE_LABELS["analysis_plan"])
        
        if not wf.stage_data("analysis_plan"):
        if st.button("📊 통계 분석 계획 생성", type="primary"):
        with st.spinner("모델 스펙, 서브그룹, 민감도 분석 계획 생성 중..."):
            sap = wf.plan_analysis()
        st.rerun()
        else:
        data = wf.stage_data("analysis_plan")
        sap = data["sap"]
        
        if "primary_analysis" in sap:
        pa = sap["primary_analysis"]
        with st.expander("📌 1차 분석", expanded=not data.get("approved")):
            st.markdown(f"**방법:** {pa.get('method', '')}")
            st.markdown(f"**선택 근거:** {pa.get('justification', '')}")
            st.markdown(f"**R 모델 공식:**")
            st.code(pa.get('model_formula', ''), language="r")
            st.markdown(f"**기준 범주:** `{pa.get('reference_category', '')}`")
            st.markdown(f"**효과 측정치:** {pa.get('effect_measure', '')}")
            st.markdown(f"**복합표본 처리:**")
            st.code(pa.get('complex_survey_handling', ''), language="r")
        
        if "model_sequence" in sap:
        with st.expander("📋 모델 순서 (단계별 조정)"):
            for k, v in sap["model_sequence"].items():
                st.markdown(f"- **{k}:** {v}")
        
        if "subgroup_analyses" in sap:
        with st.expander(f"🔍 서브그룹 분석 ({len(sap['subgroup_analyses'])}개)"):
            for sg in sap["subgroup_analyses"]:
                if isinstance(sg, dict):
                    st.markdown(f"- **{sg.get('variable', '')}**: {sg.get('method', '')}")
        
        if "sensitivity_analyses" in sap:
        with st.expander("🔄 민감도 분석"):
            for sa in sap["sensitivity_analyses"]:
                st.markdown(f"- {sa}")
        
        if "tables_planned" in sap:
        with st.expander("📄 예정 Table 구조"):
            for tbl in sap["tables_planned"]:
                if isinstance(tbl, dict):
                    for k, v in tbl.items():
                        st.markdown(f"**{k}:** {v}")
                    st.divider()
        
        if "r_packages_needed" in sap:
        st.markdown(f"**필요 R 패키지:** `{', '.join(sap['r_packages_needed'])}`")
        
        if not data.get("approved"):
        st.divider()
        modifications = st.text_area(
            "수정 사항 (없으면 비워두세요)",
            placeholder="예: 서브그룹 분석에 BMI category 추가...",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ 승인", key="approve_sap", type="primary"):
                wf.approve("analysis_plan", modifications)
                st.rerun()
        with col_b:
            feedback = st.text_input("반려 사유", key="reject_sap_reason")
            if st.button("🔴 반려 후 재생성", key="reject_sap"):
                wf.reject("analysis_plan", feedback)
                with st.spinner("재생성 중..."):
                    wf.plan_analysis()
                st.rerun()
        else:
        st.success("✅ 통계 분석 계획 승인됨")
        
        if not wf.is_approved("analysis_plan"):
        st.stop()
        
        st.divider()
        
        # ════════════════════════════════════════════════════════════════════════
        # STAGE 4: R 코드
        # ════════════════════════════════════════════════════════════════════════
        st.header(STAGE_LABELS["r_code"])
        
        if not wf.stage_data("r_code"):
        if st.button("💻 R 코드 생성", type="primary"):
        with st.spinner("실행 가능한 R 분석 코드 생성 중..."):
            r_code = wf.generate_r_code()
        st.rerun()
        else:
        data = wf.stage_data("r_code")
        r_code = data["r_code"]
        
        st.info(f"📁 R 코드 저장 위치: `{data['r_file']}`")
        st.code(r_code, language="r")
        
        st.download_button(
        "📥 R 코드 다운로드",
        data=r_code.encode("utf-8"),
        file_name=f"{wf.workflow_id}_analysis.R",
        mime="text/plain",
        )
        
        if not data.get("approved"):
        st.divider()
        st.warning("⚠️ 이 R 코드를 실제 KYRBS 데이터로 실행하세요. 결과를 5단계에서 붙여넣습니다.")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ 코드 확인 완료 → 5단계로", type="primary"):
                wf.approve("r_code")
                st.rerun()
        with col_b:
            if st.button("🔄 코드 재생성"):
                with st.spinner("재생성 중..."):
                    wf.generate_r_code()
                st.rerun()
        else:
        st.success("✅ R 코드 확인 완료")
        
        if not wf.is_approved("r_code"):
        st.stop()
        
        st.divider()
        
        # ════════════════════════════════════════════════════════════════════════
        # STAGE 5: 결과 검증
        # ════════════════════════════════════════════════════════════════════════
        st.header(STAGE_LABELS["result_verification"])
        
        if not wf.stage_data("result_verification"):
        st.info("R 분석 결과를 아래에 붙여넣으세요. (콘솔 출력, CSV 내용, 또는 직접 입력 모두 가능)")
        results_input = st.text_area(
        "R 실행 결과",
        height=300,
        placeholder="""예:
        Table 1: n=54,633 (weighted)
        Smartphone <2h: 28.3%, 2-4h: 41.2%, ≥4h: 30.5%
        Sleep insufficient: 68.4%
        
        Model 3 (fully adjusted):
        Smartphone 2-4h: OR=1.52 (1.38-1.68), p<0.001
        Smartphone ≥4h: OR=2.34 (1.89-2.91), p<0.001
        P for trend: <0.001
        
        Subgroup (sex):
        Male ≥4h: OR=1.98 (1.55-2.53)
        Female ≥4h: OR=2.67 (2.15-3.32)
        P for interaction: 0.03"""
        )
        if st.button("🔍 결과 검증 시작", type="primary", disabled=not results_input):
        with st.spinner("AI가 통계 오류, 방향성, 타당성 검증 중..."):
            verification = wf.verify_results(results_input)
        st.rerun()
        else:
        data = wf.stage_data("result_verification")
        v = data["verification"]
        
        # 전체 판정
        check = v.get("plausibility_check", {})
        overall = check.get("overall", "unknown")
        if overall == "pass":
        st.success(f"✅ 통계 검증 결과: **통과**")
        elif overall == "warning":
        st.warning(f"⚠️ 통계 검증 결과: **주의 필요**")
        else:
        st.error(f"❌ 통계 검증 결과: **재검토 필요**")
        
        issues = check.get("issues", [])
        if issues:
        st.subheader("발견된 문제점")
        for issue in issues:
            st.markdown(f"- ⚠️ {issue}")
        
        # 상세 검증
        with st.expander("📋 항목별 검증 결과", expanded=True):
        specific = v.get("specific_checks", {})
        if isinstance(specific, dict):
            for k, val in specific.items():
                st.markdown(f"- **{k}:** {val}")
        elif isinstance(specific, list):
            for item in specific:
                if isinstance(item, dict):
                    for k, val in item.items():
                        st.markdown(f"- **{k}:** {val}")
        
        # 구조화된 결과
        with st.expander("📊 구조화된 결과 (논문 작성에 사용됨)", expanded=True):
        sr = v.get("structured_results", {})
        st.json(sr)
        
        # 경고
        warnings = v.get("warnings", [])
        if warnings:
        with st.expander("⚠️ 논문 작성 전 확인 필요"):
            for w in warnings:
                st.markdown(f"- {w}")
        
        # 추가 분석 권고
        recs = v.get("recommendations", [])
        if recs:
        with st.expander("💡 추가 분석 권고"):
            for r in recs:
                st.markdown(f"- {r}")
        
        if not data.get("approved"):
        st.divider()
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("✅ 결과 확인 완료 → 논문 작성", type="primary"):
                wf.approve("result_verification")
                st.rerun()
        with col_b:
            if st.button("🔄 다른 결과 붙여넣기"):
                del wf.state["stages"]["result_verification"]
                wf._save()
                st.rerun()
        else:
        st.success("✅ 결과 검증 승인됨 → 논문 작성 가능")
        
        if not wf.is_approved("result_verification"):
        st.stop()
        
        st.divider()
        
        # ════════════════════════════════════════════════════════════════════════
        # STAGE 6: 논문 작성
        # ════════════════════════════════════════════════════════════════════════
        st.header(STAGE_LABELS["paper_draft"])
        
        if not wf.stage_data("paper_draft"):
        st.info("검증된 실제 통계 결과를 기반으로 조유선 스타일 논문을 작성합니다.")
        if st.button("✍️ 논문 작성 시작", type="primary"):
        with st.spinner("조유선 스타일로 논문 작성 중... (약 2분 소요)"):
            paper = wf.write_paper()
        st.rerun()
        else:
        data = wf.stage_data("paper_draft")
        paper = data["draft"]
        st.success(f"✅ 논문 저장 위치: `{data['file']}`")
        st.text_area("논문 초안", value=paper, height=600)
        st.download_button(
        "📥 논문 다운로드 (TXT)",
        data=paper.encode("utf-8"),
        file_name=f"{wf.workflow_id}_paper.txt",
        mime="text/plain",
        )
        if st.button("🔄 논문 재작성"):
        del wf.state["stages"]["paper_draft"]
        wf._save()
        st.rerun()

if _is_streamlit_running():
    run_workflow_page()
