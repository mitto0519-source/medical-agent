"""
단계별 연구 워크플로우 페이지
각 단계에서 사람이 검수·승인 후 다음 단계로 진행
"""

import os
import sys
import uuid
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
os.chdir(str(Path(__file__).parent.parent.parent))
os.environ['HF_HUB_DISABLE_SYMLINKS_WARNING'] = '1'

load_dotenv()

from src.research.research_workflow import ResearchWorkflow, STAGES, STAGE_LABELS

try:
    from app.styles.sapphire_glass import inject_sapphire_glass
except Exception:
    inject_sapphire_glass = None


def _setup_session_state():
    st.session_state.setdefault('wf_id', '')
    st.session_state.setdefault('wf_dataset', 'KYRBS')
    st.session_state.setdefault('workflow_focus', '')
    st.session_state.setdefault('workflow_n', 5)


def _render_sidebar():
    st.sidebar.header('워크플로우 관리')
    existing_paths = sorted(Path('data/workflows').glob('*.json')) if Path('data/workflows').exists() else []
    existing_ids = [p.stem for p in existing_paths if not p.stem.endswith('_analysis')]

    mode = st.sidebar.radio(
        '워크플로우 모드',
        ['기존 불러오기', '새로 시작'],
        label_visibility='collapsed',
    )

    if mode == '새로 시작':
        st.session_state['wf_id'] = st.sidebar.text_input(
            '워크플로우 이름',
            value=st.session_state['wf_id'] or f'study_{str(uuid.uuid4())[:8]}',
        )
        st.session_state['wf_dataset'] = st.sidebar.selectbox('데이터셋', ['KYRBS'])
        if st.sidebar.button('시작', type='primary'):
            st.rerun()
    else:
        if existing_ids:
            selected = st.sidebar.selectbox('워크플로우 선택', existing_ids, index=0)
            if st.sidebar.button('불러오기'):
                st.session_state['wf_id'] = selected
                st.rerun()
        else:
            st.sidebar.info('저장된 워크플로우가 없습니다.')

    if st.session_state['wf_id']:
        st.sidebar.divider()
        st.sidebar.caption(f"현재 워크플로우: `{st.session_state['wf_id']}`")


def _render_stage_status(wf: ResearchWorkflow):
    st.subheader('진행 상태')
    cols = st.columns(len(STAGES))
    for stage, col in zip(STAGES, cols):
        label = STAGE_LABELS.get(stage, stage)
        data = wf.stage_data(stage)
        if not data:
            icon = '⬜'
        elif data.get('approved'):
            icon = '✅'
        elif data.get('rejection_feedback'):
            icon = '🔴'
        else:
            icon = '🟡'
        col.markdown(f"**{icon}**  {label.split(':', 1)[-1].strip()}")


def _render_topic_stage(wf: ResearchWorkflow):
    st.header(STAGE_LABELS['topic_proposal'])
    if not wf.stage_data('topic_proposal'):
        focus = st.text_input('연구 포커스', placeholder='예: 청소년 스마트폰 사용과 정신건강')
        n_topics = st.slider('제안 주제 수', 1, 8, 5)
        if st.button('🚀 주제 생성', type='primary', disabled=not focus):
            with st.spinner('주제를 생성 중입니다...'):
                topics = wf.propose_topics(focus, n_topics)
            st.success(f'✅ {len(topics)}개 주제 생성 완료')
            st.rerun()
    else:
        data = wf.stage_data('topic_proposal')
        topics = data.get('topics', [])
        if data.get('approved'):
            selected = data.get('selected_topic')
            st.success(f"선택된 주제: **{selected.get('title','')}**")
        else:
            st.info('주제를 하나 선택하고 승인하세요.')
            for i, topic in enumerate(topics):
                with st.expander(f"[{i+1}] {topic.get('title','제목 없음')}", expanded=(i == 0)):
                    st.write(f"**노출:** {topic.get('exposure','')}")
                    st.write(f"**결과:** {topic.get('outcome','')}")
                    st.write(f"**대상:** {topic.get('population','')}")
                    st.write(f"**근거:** {topic.get('rationale','')}")
                    if st.button('이 주제 선택 & 승인', key=f'select_topic_{i}', type='primary'):
                        wf.select_topic(i)
                        wf.approve('topic_proposal')
                        st.rerun()
            if st.button('🔄 주제 다시 생성'):
                with st.spinner('주제를 다시 생성 중입니다...'):
                    wf.propose_topics(data.get('focus',''), len(topics))
                st.rerun()


def _render_variable_stage(wf: ResearchWorkflow):
    st.header(STAGE_LABELS['variable_plan'])
    if not wf.stage_data('variable_plan'):
        if st.button('📋 변수 계획 생성', type='primary'):
            with st.spinner('변수 계획을 생성 중입니다...'):
                wf.plan_variables()
            st.rerun()
    else:
        data = wf.stage_data('variable_plan')
        plan = data.get('plan', {})
        if 'exposure_variable' in plan:
            ev = plan['exposure_variable']
            st.markdown('**Exposure**')
            st.write(ev)
        if 'outcome_variable' in plan:
            ov = plan['outcome_variable']
            st.markdown('**Outcome**')
            st.write(ov)
        if data.get('approved'):
            st.success('변수 계획 승인됨')
        else:
            modifications = st.text_area('수정 사항', placeholder='예: 노출 변수를 재코딩합니다.')
            col1, col2 = st.columns(2)
            with col1:
                if st.button('✅ 승인', type='primary'):
                    wf.approve('variable_plan', modifications)
                    st.rerun()
            with col2:
                feedback = st.text_input('반려 사유')
                if st.button('🔴 반려 후 재생성'):
                    wf.reject('variable_plan', feedback)
                    with st.spinner('재생성 중...'):
                        wf.plan_variables()
                    st.rerun()


def run_workflow_page():
    st.set_page_config(page_title='단계별 연구 워크플로우', page_icon='🔬', layout='wide')
    if inject_sapphire_glass is not None:
        try:
            inject_sapphire_glass()
        except Exception:
            pass
    st.title('🔬 단계별 연구 워크플로우')
    st.caption('각 단계에서 검수·승인 후 다음 단계로 진행됩니다.')

    _setup_session_state()
    _render_sidebar()

    if not st.session_state['wf_id']:
        st.info('왼쪽에서 워크플로우를 선택하거나 생성하세요.')
        st.stop()

    wf = ResearchWorkflow(
        workflow_id=st.session_state['wf_id'],
        dataset_name=st.session_state['wf_dataset'],
    )

    _render_stage_status(wf)
    st.divider()

    _render_topic_stage(wf)
    if not wf.is_approved('topic_proposal'):
        st.stop()

    st.divider()
    _render_variable_stage(wf)

    if wf.is_approved('variable_plan'):
        st.divider()
        st.markdown('### 다음 단계: 통계 분석 계획 생성')
        if not wf.stage_data('analysis_plan'):
            if st.button('📊 통계 분석 계획 생성', type='primary'):
                with st.spinner('통계 분석 계획을 생성 중입니다...'):
                    wf.plan_analysis()
                st.rerun()
        else:
            st.success('통계 분석 계획이 생성되었습니다.')


run_workflow_page()
