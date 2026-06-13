"""Sapphire action dialogs — 러버블  부가기능 모달.

기존 단위 기능(신규성 확인 / 통계 / STROBE / Figure / 인용 등)을 **페이지 이동 없이**
현재 ez_home/workspace 위에 `st.dialog`로 팝업한다. 결과를 inline 표시 +
"chat에 결과 삽입" 버튼으로 현재 흐름에 흡수.

호출 양식 (러버블 양식):
    from app.sapphire_actions import open_action
    if st.button("🔬 신규성 확인"):
        open_action("novelty")   # 모달 open

각 action은 `@st.dialog`로 감싼 함수. dialog 내부에서 기존 src.* 모듈 직접 호출.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import streamlit as st


# ── Action dispatcher ────────────────────────────────────────────────────────

ACTIONS = {
    "kyrbs_quick":   "📊 KYRBS 2025 빠른 분석",
    "novelty":       "🔬 신규성 확인 (PubMed)",
    "strobe":        "📑 STROBE 체크리스트",
    "yoosun":        "📝 Yoosun 스타일 재작성",
    "stat":          "🧮 통계 분석 (StatBridge)",
    "figure":        "🎨 Figure 생성",
    "citation":      "📚 인용/레퍼런스 관리",
    "consistency":   "🔍 본문 일관성 검사",
    "wiki":          "🧠 지식 위키 검색",
    "learn":         "🎓 PubMed 자동 학습",
}


def open_action(action_key: str, **ctx) -> None:
    """모달 열기. ctx는 dialog 함수에 넘기는 컨텍스트 (e.g. project=...)."""
    st.session_state["_sg_active_action"] = action_key
    st.session_state["_sg_action_ctx"] = ctx
    st.rerun()


def render_open_action_if_any() -> None:
    """페이지 진입 시 호출 — pending action이 있으면 해당 dialog 호출."""
    key = st.session_state.pop("_sg_active_action", None)
    ctx = st.session_state.pop("_sg_action_ctx", {}) or {}
    if not key:
        return
    fn = _DIALOG_REGISTRY.get(key)
    if fn is None:
        st.warning(f"unknown action: {key}")
        return
    fn(**ctx)


# ── Preview patch helpers — 모달 결과를 docx 프리뷰에 즉시 반영 ──────────────

def patch_preview(*, section: str = None, subsection: str = None,
                   abstract_field: str = None, append: bool = True,
                   content: str = "", supplement_block: str = None) -> None:
    """현재 프로젝트(session_state['sg_project'])의 sections에 content를 patch.

    - section: "Introduction"/"Methods"/"Results"/"Discussion"
    - subsection: section이 dict일 때 sub-key (예: "Study population")
    - abstract_field: "Background"/"Methods"/"Results"/"Conclusion"
    - supplement_block: Supplement 탭에 추가 (key=block 이름)
    - append=True면 기존에 누적, False면 덮어쓰기
    """
    proj = st.session_state.setdefault("sg_project", {})
    sections = proj.setdefault("sections", {})

    if abstract_field:
        ab = sections.setdefault("Abstract", {})
        if not isinstance(ab, dict):
            ab = {"Background": str(ab)}
            sections["Abstract"] = ab
        old = ab.get(abstract_field, "")
        ab[abstract_field] = (old + "\n\n" + content).strip() if append and old else content
    elif section:
        if subsection:
            sec = sections.setdefault(section, {})
            if not isinstance(sec, dict):
                sec = {"_intro": str(sec)}
                sections[section] = sec
            old = sec.get(subsection, "")
            sec[subsection] = (old + "\n\n" + content).strip() if append and old else content
        else:
            old = sections.get(section, "")
            if isinstance(old, dict):
                old["_appended"] = (old.get("_appended", "") + "\n\n" + content).strip()
            else:
                sections[section] = (old + "\n\n" + content).strip() if append and old else content

    if supplement_block:
        supp = proj.setdefault("supplement", {})
        old = supp.get(supplement_block, "")
        supp[supplement_block] = (old + "\n\n" + content).strip() if append and old else content

    # 저장 (workspace의 _save_project가 처리)
    pid = st.session_state.get("sg_active_project")
    if pid and pid != "new":
        try:
            from app.pages.project_workspace import _save_project
            _save_project(pid, proj)
        except Exception:
            pass


# ── Floating Action Button (FAB) ─────────────────────────────────────────────

def render_fab(actions: list[tuple[str, str]] | None = None,
                position: str = "bottom-right") -> None:
    """우하단 플로팅 액션 버튼. 클릭 시 quick action 메뉴 펼침.

    Streamlit은 진짜 floating div를 native로 못 만들어서 (st.button은 layout 내),
    expander + custom CSS로 우하단 sticky하게 만든다.

    Args:
        actions: [(action_key, label), ...]. None이면 ACTIONS 전체.
    """
    if actions is None:
        actions = list(ACTIONS.items())

    st.markdown("""
<style>
.sg-fab-wrap {
    position: fixed; bottom: 28px; right: 28px; z-index: 9999;
}
.sg-fab-wrap [data-testid="stExpander"] {
    background: rgba(124, 58, 237, 0.16) !important;
    border: 1px solid rgba(124, 58, 237, 0.50) !important;
    border-radius: 18px !important;
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    box-shadow: 0 12px 40px rgba(124, 58, 237, 0.40);
    min-width: 240px;
}
.sg-fab-wrap .streamlit-expanderHeader {
    background: linear-gradient(135deg, #3B82F6, #8B5CF6) !important;
    color: white !important;
    font-weight: 600 !important;
    border-radius: 18px !important;
    padding: 14px 20px !important;
}
.sg-fab-wrap .stButton > button {
    background: transparent !important;
    border: none !important;
    text-align: left !important;
    padding: 10px 14px !important;
    border-radius: 10px !important;
}
.sg-fab-wrap .stButton > button:hover {
    background: rgba(255,255,255,0.08) !important;
    transform: none !important;
}
</style>
<div class='sg-fab-wrap' id='sg-fab-anchor'></div>
""", unsafe_allow_html=True)

    # Streamlit limitation: native floating은 어려우니 우하단 가까이 columns 끝에 expander 배치
    _c1, _c2, _c3 = st.columns([4, 4, 2])
    with _c3:
        with st.expander("✨ Actions"):
            for key, label in actions:
                if st.button(label, key=f"sg_fab_{key}", use_container_width=True):
                    open_action(key)


# ── Dialog implementations (각 기능 = 한 dialog) ─────────────────────────────

@st.dialog("🔬 신규성 확인 — PubMed")
def _dlg_novelty(**ctx):
    st.caption("PubMed에서 최근 5년 유사 논문을 검색하고 신규성을 평가합니다.")
    query = st.text_input("연구 주제 / 키워드",
                           value=ctx.get("query", ""),
                           placeholder="예: zero-calorie beverage depression adolescents",
                           key="dlg_novelty_q")
    years = st.slider("최근 N년", 1, 10, 5, key="dlg_novelty_years")
    max_n = st.slider("결과 수", 5, 30, 10, key="dlg_novelty_n")

    c1, c2 = st.columns([1, 1])
    with c1:
        run = st.button("🔍 검색 + 신규성 평가", use_container_width=True, type="primary")
    with c2:
        if st.button("닫기", use_container_width=True):
            st.rerun()

    if run and query:
        with st.spinner("PubMed 검색 + LLM 신규성 평가…"):
            try:
                from src.research.novelty_checker import NoveltyChecker
                result = NoveltyChecker().check(query, max_results=max_n, years=years)
                st.session_state["_sg_last_novelty"] = result
                st.session_state["_sg_last_novelty_query"] = query
            except Exception as e:
                st.error(f"신규성 확인 실패: {e}")
                return

    result = st.session_state.get("_sg_last_novelty")
    if result:
        st.success(f"신규성 점수: {result.get('novelty_score', 'N/A')}")
        st.write(result.get("summary", ""))
        with st.expander("유사 논문 목록"):
            for r in (result.get("similar_papers") or [])[:max_n]:
                st.markdown(f"- **{r.get('title', '?')}** "
                             f"({r.get('year', '?')}) — {r.get('authors', '')[:80]}")
        st.divider()
        st.markdown("**📌 결과를 docx preview에 즉시 반영**")
        b1, b2 = st.columns(2)
        with b1:
            if st.button("→ Introduction 끝에 추가", use_container_width=True, type="primary"):
                block = (f"\n\n[Novelty assessment — {st.session_state.get('_sg_last_novelty_query', '')}] "
                          f"Score: {result.get('novelty_score', 'N/A')}. "
                          f"{result.get('summary', '')[:400]}")
                patch_preview(section="Introduction", append=True, content=block)
                st.toast("Introduction에 신규성 보고 추가됨", icon="✅")
                st.rerun()
        with b2:
            if st.button("→ Supplement에 저장", use_container_width=True):
                similar = "\n".join(f"- {r.get('title', '?')} ({r.get('year', '?')})"
                                     for r in (result.get("similar_papers") or [])[:max_n])
                patch_preview(supplement_block="Novelty assessment",
                              content=f"Score: {result.get('novelty_score', 'N/A')}\n\n"
                                       f"Summary: {result.get('summary', '')}\n\n"
                                       f"Similar papers:\n{similar}")
                st.toast("Supplement에 저장됨", icon="✅")
                st.rerun()


@st.dialog("📊 KYRBS 2025 빠른 분석")
def _dlg_kyrbs_quick(**ctx):
    st.caption("KYRBS 2025 원시자료(n=54,170)에서 기본 통계 + Table 1을 즉시 생성.")
    outcome = st.selectbox("결과 변수", ["depression", "stress", "sleep_satis",
                                          "suicidal", "smoking", "alcohol"], key="dlg_k_out")
    exposure = st.selectbox("노출 변수 (선택)", ["", "zcb_freq", "ssb_freq",
                                                  "caffeine_freq", "screen_time",
                                                  "physical_act", "sleep_hours"],
                              key="dlg_k_exp")

    c1, c2 = st.columns([1, 1])
    with c1:
        run = st.button("▶ 분석 실행", use_container_width=True, type="primary")
    with c2:
        if st.button("닫기", use_container_width=True, key="dlg_k_close"):
            st.rerun()

    if run:
        with st.spinner("KYRBS 2025 로드 + 통계 분석…"):
            try:
                from pathlib import Path as _P
                from src.data.kyrbs_raw_loader import KYRBSLoader
                from src.data.stat_bridge import StatBridge

                df, _ = KYRBSLoader().load(_P("data/raw/kyrbs2025.sav"))
                if exposure:
                    spec = {"outcome": outcome, "predictors": [exposure],
                             "covariates": ["sex", "age", "school_type"],
                             "weight_var": "weight_var",
                             "strata_var": "strata", "cluster_var": "cluster",
                             "analysis": "logistic"}
                    r = StatBridge().run(df, spec).to_dict()
                    st.session_state["_sg_last_kyrbs"] = {
                        "n": len(df), "outcome": outcome, "exposure": exposure,
                        "result": r,
                    }
                else:
                    st.session_state["_sg_last_kyrbs"] = {
                        "n": len(df), "outcome": outcome, "exposure": None,
                        "desc": str(df[outcome].describe()) if outcome in df.columns else "",
                    }
            except Exception as e:
                st.error(f"분석 실패: {e}")
                return

    last = st.session_state.get("_sg_last_kyrbs")
    if last:
        st.metric("표본수", f"{last['n']:,}")
        if last.get("exposure"):
            r = last["result"]
            vars_ = r.get("model_vars", [])
            target_var = next((v for v in vars_
                                if last["exposure"] in str(v.get("variable", "")).lower()), None)
            if target_var:
                lo, hi = target_var.get("ci_lower", 0), target_var.get("ci_upper", 0)
                st.metric(f"aOR ({last['exposure']} → {last['outcome']})",
                           f"{target_var.get('or_value', 0):.3f}",
                           help=f"95% CI [{lo:.3f}, {hi:.3f}]")
                p = target_var.get("p_value")
                st.caption(f"P-value: {p:.3f}" if p else "N/A")

                st.divider()
                st.markdown("**📌 결과를 docx preview에 반영**")
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("→ Results 끝에 통계 요약 추가", use_container_width=True,
                                  type="primary"):
                        block = (f"In the fully adjusted model, {last['exposure']} was associated "
                                  f"with {last['outcome']} (aOR {target_var.get('or_value', 0):.2f}; "
                                  f"95% CI {lo:.2f}-{hi:.2f}; "
                                  f"P {'< 0.001' if (p and p < 0.001) else f'= {p:.3f}'}).")
                        patch_preview(section="Results", append=True, content=block)
                        st.toast("Results에 통계 요약 추가됨", icon="✅")
                        st.rerun()
                with b2:
                    if st.button("→ Table 2 데이터로 저장", use_container_width=True):
                        proj = st.session_state.setdefault("sg_project", {})
                        tables = proj.setdefault("tables", [])
                        tables.append({
                            "type": "regression", "n": len(tables) + 1,
                            "caption": f"Adjusted Odds Ratios for {last['outcome']}",
                            "data": [{"variable": v.get("variable"),
                                       "or": v.get("or_value"),
                                       "ci_low": v.get("ci_lower"),
                                       "ci_high": v.get("ci_upper"),
                                       "p_value": v.get("p_value")} for v in vars_],
                        })
                        st.toast("Table 2로 저장됨", icon="✅")
                        st.rerun()
        elif last.get("desc"):
            st.code(last["desc"], language=None)


@st.dialog("📑 STROBE 체크리스트")
def _dlg_strobe(**ctx):
    st.caption("현재 논문 본문에 대해 STROBE 22항목을 자동 검사합니다.")
    paper_text = st.text_area("논문 본문 (Methods/Results/Discussion 포함)",
                                value=ctx.get("paper_text", ""),
                                height=240, key="dlg_strobe_text")

    c1, c2 = st.columns([1, 1])
    with c1:
        run = st.button("✓ STROBE 검사", use_container_width=True, type="primary")
    with c2:
        if st.button("닫기", use_container_width=True, key="dlg_strobe_close"):
            st.rerun()

    if run and paper_text:
        try:
            from src.research.reporting_checklist import check_strobe, format_checklist_report
            # 본문에서 섹션 분리 (휴리스틱)
            import re as _re
            sections = {}
            for sec in ("Introduction", "Methods", "Results", "Discussion"):
                m = _re.search(rf"\b{sec}\b", paper_text, _re.IGNORECASE)
                if m:
                    nxt = paper_text.find("\n\n", m.end())
                    sections[sec] = paper_text[m.end(): nxt if nxt > 0 else len(paper_text)]
            r = check_strobe(sections, abstract=paper_text[:2000])
            pct = r["score"] / r["total"] * 100
            st.metric("STROBE Score", f"{r['score']}/{r['total']}", f"{pct:.0f}%")
            st.code(format_checklist_report(r, verbose=True), language=None)
        except Exception as e:
            st.error(f"STROBE 검사 실패: {e}")


@st.dialog("📝 Yoosun 스타일 재작성")
def _dlg_yoosun(**ctx):
    st.caption("입력 본문을 Yoosun Cho 스타일(hedging vocab + topic→evidence→limitation→transition)로 재작성.")
    src = st.text_area("재작성할 본문", value=ctx.get("text", ""), height=200,
                        key="dlg_yoosun_src")

    c1, c2 = st.columns([1, 1])
    with c1:
        run = st.button("✨ 재작성", use_container_width=True, type="primary")
    with c2:
        if st.button("닫기", use_container_width=True, key="dlg_yoosun_close"):
            st.rerun()

    if run and src:
        with st.spinner("Yoosun 스타일 prompt 합성 + LLM 호출…"):
            try:
                from src.agent.prompt_loader import load_yoosun_with_exemplars
                from src.llm import get_llm_client
                client = get_llm_client(task="paper_writing")
                # FIX-1: per-user StyleProfile 우선 (yoosun 폴백)
                _owner = (st.session_state.get("user") or {}).get("email") or \
                          st.session_state.get("user_email", "") or None
                sys_prompt = load_yoosun_with_exemplars(owner_email=_owner)
                out = client.generate(
                    f"Rewrite the following paragraph in Yoosun Cho style "
                    f"(preserve all numbers, citations, statistics):\n\n{src}",
                    system_prompt=sys_prompt, max_tokens=2000)
                st.text_area("재작성 결과", value=out, height=200, key="dlg_yoosun_out")
                if st.button("📋 작업실 chat으로 보내기"):
                    st.session_state["sg_initial_prompt"] = out
                    st.session_state["sg_active_project"] = "new"
                    st.rerun()
            except Exception as e:
                st.error(f"재작성 실패: {e}")


@st.dialog("🔍 본문 일관성 검사")
def _dlg_consistency(**ctx):
    st.caption("n / OR-CI / P값 / 연도 모순을 정규식으로 자동 검출.")
    paper = st.text_area("논문 본문", value=ctx.get("text", ""), height=240,
                          key="dlg_cc_text")

    c1, c2 = st.columns([1, 1])
    with c1:
        run = st.button("🔎 검사", use_container_width=True, type="primary")
    with c2:
        if st.button("닫기", use_container_width=True, key="dlg_cc_close"):
            st.rerun()

    if run and paper:
        try:
            from src.safety.consistency_checker import check_consistency
            rep = check_consistency({"Paper": paper})
            color = {"ok": "🟢", "warn": "🟡", "fail": "🔴"}[rep.severity]
            st.metric("Severity", f"{color} {rep.severity.upper()}",
                       f"{len(rep.issues)} issues")
            if rep.n_samples_seen:
                st.caption(f"n 토큰 발견: {rep.n_samples_seen}")
            if rep.years_seen:
                st.caption(f"연도 발견: {rep.years_seen}")
            for it in rep.issues:
                st.warning(f"**{it.type}**: {it.detail}")
        except Exception as e:
            st.error(f"일관성 검사 실패: {e}")


@st.dialog("🎨 Figure 생성")
def _dlg_figure(**ctx):
    st.caption("StatBridge 결과 → publication-grade figure 자동 생성.")
    fig_type = st.selectbox("Figure 종류",
                              ["forest_plot", "roc_curve", "prevalence_bar",
                               "kaplan_meier", "coefficient_plot"],
                              key="dlg_fig_type")
    st.info("Workspace에서 통계 분석 후 그 결과로 figure 생성하는 게 정상 흐름입니다.")
    if st.button("닫기", use_container_width=True, key="dlg_fig_close"):
        st.rerun()


@st.dialog("📚 인용/레퍼런스 관리")
def _dlg_citation(**ctx):
    st.caption("PubMed 검색 → Vancouver 양식 → EndNote XML/BibTeX 일괄 생성.")
    q = st.text_input("PubMed 검색어", key="dlg_cite_q")
    n = st.slider("결과 수", 5, 50, 10, key="dlg_cite_n")
    if st.button("🔍 검색", type="primary", use_container_width=True):
        try:
            from src.export.reference_library import search_pubmed
            results = search_pubmed(q, max_results=n)
            for r in (results or [])[:n]:
                st.markdown(f"- **{r.get('title', '?')}** ({r.get('year', '?')})")
                st.caption(r.get("authors", "")[:120])
        except Exception as e:
            st.error(f"검색 실패: {e}")
    if st.button("닫기", use_container_width=True, key="dlg_cite_close"):
        st.rerun()


@st.dialog("🎓 PubMed 자동 학습")
def _dlg_learn(**ctx):
    st.caption("Europe PMC OA Subset에서 무료 풀텍스트 논문을 증분 수집 → ChromaDB 인덱싱.")
    n_target = st.number_input("이번 배치 수집 편수", 100, 5000, 500,
                                  step=100, key="dlg_learn_n")
    st.warning("⚠️ 5만편 학습 인프라는 현재 부재. Phase 1 (OA bulk fetcher) 구현 후 활성화 예정.")
    if st.button("닫기", use_container_width=True, key="dlg_learn_close"):
        st.rerun()


@st.dialog("🧠 지식 위키 검색")
def _dlg_wiki(**ctx):
    st.caption("누적 지식 위키에서 개념·메서드·증례 검색.")
    q = st.text_input("검색어", key="dlg_wiki_q")
    if st.button("🔎 검색", type="primary", use_container_width=True):
        try:
            from src.knowledge.research_wiki import ResearchWiki
            wiki = ResearchWiki()
            ctx_txt = wiki.build_context(q, max_chars=2000) if hasattr(wiki, "build_context") else ""
            st.code(ctx_txt or "(검색 결과 없음)", language=None)
        except Exception as e:
            st.error(f"검색 실패: {e}")
    if st.button("닫기", use_container_width=True, key="dlg_wiki_close"):
        st.rerun()


@st.dialog("🧮 통계 분석 (StatBridge)")
def _dlg_stat(**ctx):
    st.caption("StatBridge로 logistic/GEE/Cox/PSM 등 회귀 분석을 즉시 실행.")
    st.info("Workspace의 chat에서 'KYRBS 통계 보강' 모드로 호출하는 것이 정상 흐름입니다.")
    if st.button("닫기", use_container_width=True, key="dlg_stat_close"):
        st.rerun()


_DIALOG_REGISTRY = {
    "kyrbs_quick":  _dlg_kyrbs_quick,
    "novelty":      _dlg_novelty,
    "strobe":       _dlg_strobe,
    "yoosun":       _dlg_yoosun,
    "stat":         _dlg_stat,
    "figure":       _dlg_figure,
    "citation":     _dlg_citation,
    "consistency":  _dlg_consistency,
    "wiki":         _dlg_wiki,
    "learn":        _dlg_learn,
}
