"""Tool Registry — Medical-Agent의 모든 사용자-노출 능력 단일 진입점.

설계 (2026-05-27, 사용자 비전):
  채팅 메시지 → LLM tool selection → registry[tool] 실행 → ToolResult → Streamlit @st.dialog 렌더 + 다운로드

각 도구는:
  - 명확한 입력 schema (LLM tool-calling 호환)
  - dict ToolResult 반환: {kind, summary, payload, downloads}
  - 위험 작업(파일 삭제 등)은 비허용 — 화이트리스트만

ToolResult.kind:
  'stat'   → 통계 결과 (StatBridge OR/CI/forest)
  'figure' → 시각화 (PNG/PDF bytes + caption)
  'export' → DOCX/EndNote/BibTeX bytes
  'note'   → 텍스트 응답 (no UI 부산물)

Streamlit 통합:
  from src.tools import TOOLS, render_result
  result = TOOLS["stat_logistic"](outcome="depression", exposure="zero_freq", ...)
  render_result(result)  # st.dialog 자동 띄움 + 다운로드 버튼 자동
"""
from __future__ import annotations

import io
from typing import Any, Callable

# ── ToolResult 표준 ──────────────────────────────────────────────────────────

def tool_result(kind: str, summary: str, payload: dict = None,
                downloads: list = None) -> dict:
    """모든 도구의 표준 반환 형식.
    downloads: [{"label": "CSV", "data": bytes_or_str, "filename": "x.csv", "mime": "text/csv"}]
    """
    return {
        "kind": kind, "summary": summary,
        "payload": payload or {}, "downloads": downloads or [],
    }


# ── 도구 구현 (기존 src/* 모듈 래핑) ──────────────────────────────────────────

def stat_logistic(df_key: str, outcome: str, exposure: str,
                  covariates: list = None, subgroup: dict = None,
                  **kwargs) -> dict:
    """Survey-weighted logistic regression (StatBridge 래핑).

    df_key: session_state에서 데이터프레임 식별 (예: 'raw_df')
    outcome/exposure/covariates: Stata 변수명 그대로
    subgroup: {"var": "sex", "value": 2} 같은 stratification (옵션)
    """
    try:
        import streamlit as st
        df = st.session_state.get(df_key)
        if df is None:
            return tool_result("note", f"데이터프레임 '{df_key}' 없음 — 먼저 원시자료 로드 필요.")
    except Exception:
        return tool_result("note", "Streamlit 컨텍스트 외부에서 호출됨.")

    from src.data.stat_bridge import StatBridge
    spec = {"outcome": outcome, "predictors": [exposure],
            "covariates": covariates or [], "analysis": "logistic"}
    if subgroup:
        spec["subset"] = subgroup
    r = StatBridge().run(df, spec).to_dict()
    return tool_result(
        "stat", summary=f"Logistic({outcome}~{exposure}): n={r.get('n_total')}, "
                        f"vars={len(r.get('model_vars', []))}",
        payload={"stat_result": r},
    )


def figure_forest(stat_result: dict, title: str = "", **kwargs) -> dict:
    """Forest plot from StatBridge result."""
    from src.export.figure_builder import stat_result_to_forest_plot
    png = stat_result_to_forest_plot(stat_result, title=title or "Adjusted OR")
    if not png:
        return tool_result("note", "Forest plot 생성 불가 (유효 변수 0).")
    return tool_result(
        "figure", summary=f"Forest plot ({len(stat_result.get('model_vars', []))} vars)",
        payload={"caption": title},
        downloads=[{"label": "PNG", "data": png, "filename": "forest.png", "mime": "image/png"}],
    )


def figure_bar(data: dict, title: str = "", xlabel: str = "", ylabel: str = "",
               **kwargs) -> dict:
    from src.export.figure_builder import bar_chart
    png = bar_chart(data, title=title, xlabel=xlabel, ylabel=ylabel)
    return tool_result(
        "figure", summary=f"Bar chart ({len(data)} categories)",
        payload={"caption": title},
        downloads=[{"label": "PNG", "data": png, "filename": "bar.png", "mime": "image/png"}],
    )


def figure_scatter(x: list, y: list, title: str = "", xlabel: str = "", ylabel: str = "",
                   **kwargs) -> dict:
    from src.export.figure_builder import scatter_plot
    png = scatter_plot(x, y, title=title, xlabel=xlabel, ylabel=ylabel)
    return tool_result(
        "figure", summary=f"Scatter ({len(x)} points)",
        payload={"caption": title},
        downloads=[{"label": "PNG", "data": png, "filename": "scatter.png", "mime": "image/png"}],
    )


def export_table_docx(stat_result: dict, **kwargs) -> dict:
    from src.export.table_builder import stat_result_to_tables_docx_bytes
    data = stat_result_to_tables_docx_bytes(stat_result)
    return tool_result(
        "export", summary=f"Table 1/2 Word ({len(data):,} B)",
        downloads=[{"label": "DOCX", "data": data, "filename": "tables.docx",
                    "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}],
    )


def export_citations(refs_text: str, paper_sections: dict = None, **kwargs) -> dict:
    """레퍼런스 목록 → 차용 검수 + Word + EndNote 풀셋."""
    from src.export.citation_workflow import (
        parse_reference_input, resolve_references, screen_applicability,
        place_citations, build_cited_docx, endnote_bytes, bibtex_bytes,
    )
    entries = parse_reference_input(refs_text)
    if not entries:
        return tool_result("note", "레퍼런스를 한 줄에 하나씩 입력하세요.")
    refs = resolve_references(entries)
    paper_text = " ".join((paper_sections or {}).values())
    screened = screen_applicability(refs, paper_text or " ".join(entries))
    usable = [s["ref"] for s in screened if s["usable"]]
    if not usable:
        return tool_result("note", "차용 가능 레퍼런스가 0개 — 본문/임계값 확인 필요.",
                           payload={"screened": [(s["ref"].title[:60], s["score"]) for s in screened]})
    new_secs, ordered = place_citations(paper_sections or {}, usable)
    docx = build_cited_docx("Paper", new_secs, ordered)

    # safety wiring: citation grounding + physician review
    safety_notes = []
    try:
        from src.safety import verify_citation_integrity, queue_for_review, record_safety_event
        # ref dict {n: vancouver_line}
        from src.export.reference_library import format_vancouver as _fv
        ref_dict = {i: _fv(r, i) for i, r in enumerate(ordered, 1)}
        body_combined = " ".join(new_secs.values())
        report = verify_citation_integrity(body_combined, ref_dict, check_dois=False)
        if not report.ok:
            safety_notes.append(f"citation 검증: {report.summary}")
            record_safety_event("citation_grounding_failed",
                                {"summary": report.summary,
                                 "orphan_cites": report.orphan_citations})
        # 임상 키워드 자동 큐
        qr = queue_for_review(body_combined[:4000], source="llm",
                              owner_email=kwargs.get("owner_email", ""))
        if qr.get("queued"):
            safety_notes.append(f"physician review 큐 등록 (triggers={qr.get('triggers', [])})")
    except Exception as _e:
        safety_notes.append(f"safety 검증 건너뜀: {str(_e)[:80]}")

    return tool_result(
        "export",
        summary=(f"인용 풀셋: 차용 {len(usable)}개 / {len(refs)} 후보 · Word + EndNote 생성"
                 + ((" · " + " · ".join(safety_notes)) if safety_notes else "")),
        payload={"ordered_count": len(ordered), "safety_notes": safety_notes},
        downloads=[
            {"label": "Word", "data": docx, "filename": "paper_with_citations.docx",
             "mime": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            {"label": "EndNote XML", "data": endnote_bytes(ordered), "filename": "references.xml",
             "mime": "application/xml"},
            {"label": "BibTeX", "data": bibtex_bytes(ordered), "filename": "references.bib",
             "mime": "text/plain"},
        ],
    )


def memory_search(query: str, n: int = 5, **kwargs) -> dict:
    """누적 메모리 의미 검색 (conversation_memory + research_wiki)."""
    from src.memory import conversation_memory as cm
    try:
        import streamlit as st
        owner = (st.session_state.get("user") or {}).get("email", "")
    except Exception:
        owner = ""
    result = cm.recall_relevant(query, n=n, owner_email=owner)
    return tool_result(
        "note", summary=f"관련 기억 {len(result.splitlines())}건",
        payload={"recall": result[:5000]},
    )


# ── 화이트리스트 레지스트리 ──────────────────────────────────────────────────

TOOLS: dict = {
    "stat_logistic":    stat_logistic,
    "figure_forest":    figure_forest,
    "figure_bar":       figure_bar,
    "figure_scatter":   figure_scatter,
    "export_table":     export_table_docx,
    "export_citations": export_citations,
    "memory_search":    memory_search,
}

# OpenAI/Anthropic tool-calling schema (LLM이 어떤 도구를 부를지 판단)
TOOL_SPECS = [
    {"name": "stat_logistic",
     "description": "Survey-weighted logistic regression. outcome/exposure/covariates 지정.",
     "input_schema": {"type": "object",
        "properties": {
            "df_key": {"type": "string", "default": "raw_df"},
            "outcome": {"type": "string"},
            "exposure": {"type": "string"},
            "covariates": {"type": "array", "items": {"type": "string"}},
            "subgroup": {"type": "object"},
        }, "required": ["outcome", "exposure"]}},
    {"name": "figure_forest",
     "description": "통계 결과를 forest plot으로 시각화.",
     "input_schema": {"type": "object",
        "properties": {"stat_result": {"type": "object"}, "title": {"type": "string"}},
        "required": ["stat_result"]}},
    {"name": "export_citations",
     "description": "레퍼런스 목록 차용검수 + 본문 [n] 삽입 + Word/EndNote 풀셋.",
     "input_schema": {"type": "object",
        "properties": {"refs_text": {"type": "string"},
                       "paper_sections": {"type": "object"}},
        "required": ["refs_text"]}},
    {"name": "memory_search",
     "description": "장기 기억 의미검색.",
     "input_schema": {"type": "object",
        "properties": {"query": {"type": "string"}, "n": {"type": "integer", "default": 5}},
        "required": ["query"]}},
]


# ── Streamlit 자동 렌더 ──────────────────────────────────────────────────────

def render_result(result: dict, dialog_title: str = None) -> None:
    """ToolResult를 Streamlit UI에 자동 렌더 — @st.dialog 팝업 + 다운로드.

    호출부:
        r = TOOLS["stat_logistic"](...)
        render_result(r)
    """
    try:
        import streamlit as st
    except Exception:
        return  # not in streamlit

    kind = result.get("kind", "note")
    title = dialog_title or {
        "stat":   "📊 통계 결과",
        "figure": "📈 시각화",
        "export": "📥 내보내기",
        "note":   "📝 결과",
    }.get(kind, "결과")

    # st.dialog 지원하면 modal, 아니면 컨테이너로 fallback
    has_dialog = hasattr(st, "dialog")

    def _body():
        st.markdown(f"**{result.get('summary', '')}**")
        if kind == "stat":
            sr = result["payload"].get("stat_result", {})
            if sr.get("model_vars"):
                import pandas as pd
                df = pd.DataFrame(sr["model_vars"])
                st.dataframe(df, use_container_width=True, hide_index=True)
        elif kind == "figure":
            for dl in result.get("downloads", []):
                if dl.get("mime", "").startswith("image"):
                    st.image(dl["data"], caption=result["payload"].get("caption", ""),
                             use_container_width=True)
                    break
        elif kind == "note":
            for k, v in (result.get("payload") or {}).items():
                st.markdown(f"**{k}:**")
                st.text(str(v)[:2000])

        # 다운로드 버튼들
        dls = result.get("downloads") or []
        if dls:
            cols = st.columns(len(dls))
            for col, dl in zip(cols, dls):
                with col:
                    st.download_button(
                        dl.get("label", "Download"),
                        dl["data"],
                        file_name=dl.get("filename", "download.bin"),
                        mime=dl.get("mime", "application/octet-stream"),
                        use_container_width=True,
                        key=f"dl_{dl.get('filename', id(dl))}",
                    )

    if has_dialog:
        @st.dialog(title, width="large")
        def _show():
            _body()
        _show()
    else:
        with st.container(border=True):
            st.subheader(title)
            _body()
