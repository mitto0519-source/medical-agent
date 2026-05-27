"""Agentic loop for the Sapphire workspace — VS Code / Claude Code 양식 그대로.

설계 (사용자 요구):
  · 사용자는 우측 preview(docx)를 본다
  · LLM은 **chat 전체 로그 + 현재 preview snapshot**을 보면서 응답한다
  · 모든 step이 시간순 chat에 기록됨:
    🧑 user · 🤖 assistant text · 🛠️ tool_use · 📥 tool_result · ⚙️ system note

도구 (LLM이 직접 호출):
  - kyrbs_stat       : KYRBS 2025 통계 분석 (StatBridge svy logistic)
  - pubmed_search    : PubMed 신규성/유사논문 검색
  - strobe_check     : 현재 본문 STROBE 22항목
  - consistency_check: 본문 정형 모순 검출
  - rag_search       : 누적 RAG에서 컨텍스트 검색
  - patch_preview    : 결과를 docx preview의 특정 섹션/abstract field/supplement에 patch

각 tool 실행 후 결과는 chat에 tool_result로 기록 → LLM 재호출 → 최종 assistant text.
"""
from __future__ import annotations

import json
from typing import Callable, Dict, List

# ── Tool schemas (Anthropic tool_use 양식) ───────────────────────────────────

TOOL_SCHEMAS: List[dict] = [
    {
        "name": "patch_preview",
        "description": "현재 우측 docx preview에 내용을 patch. section/subsection 또는 "
                        "abstract_field 또는 supplement_block 중 하나를 지정.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string",
                            "enum": ["Introduction", "Methods", "Results", "Discussion", ""],
                            "description": "메인 섹션 이름. abstract_field/supplement_block 쓸 땐 빈 문자열."},
                "subsection": {"type": "string",
                                "description": "Methods 등의 subsection (Study population 등). 선택."},
                "abstract_field": {"type": "string",
                                    "enum": ["Background", "Methods", "Results", "Conclusion", ""],
                                    "description": "Abstract의 inline 라벨 필드."},
                "supplement_block": {"type": "string",
                                      "description": "Supplement 탭의 새 블록 이름."},
                "content": {"type": "string", "description": "patch할 본문 (Markdown 가능)."},
                "append": {"type": "boolean", "description": "기존 내용에 누적할지(true) 덮어쓸지(false). 기본 true."},
            },
            "required": ["content"],
        },
    },
    {
        "name": "kyrbs_stat",
        "description": "KYRBS 2025 원시자료(n=54,170)로 survey-weighted logistic 회귀 즉시 실행. "
                        "결과(aOR, 95% CI, P)를 반환.",
        "input_schema": {
            "type": "object",
            "properties": {
                "outcome": {"type": "string", "description": "depression/stress/sleep_satis 등 표준 컬럼명"},
                "exposure": {"type": "string", "description": "zcb_freq/ssb_freq/screen_time 등"},
                "covariates": {"type": "array", "items": {"type": "string"},
                                "description": "공변량 리스트. 미지정 시 ['sex','age','school_type']."},
            },
            "required": ["outcome", "exposure"],
        },
    },
    {
        "name": "pubmed_search",
        "description": "PubMed에서 유사 논문 검색 + 신규성 평가. 결과 abstract와 메타 반환.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "검색 키워드 (영문)"},
                "max_results": {"type": "integer", "description": "최대 결과 수. 기본 10."},
                "years": {"type": "integer", "description": "최근 N년. 기본 5."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "strobe_check",
        "description": "현재 preview의 본문에 대해 STROBE 22항목 체크리스트 실행. "
                        "어떤 항목이 누락됐는지 반환.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "consistency_check",
        "description": "현재 preview 본문에서 n/OR-CI/P-value/연도 모순을 정형 검출.",
        "input_schema": {"type": "object", "properties": {}},
    },
    {
        "name": "rag_search",
        "description": "누적 의학 RAG(PubMed/PMC)에서 컨텍스트 검색. multi-stage rerank.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n": {"type": "integer", "description": "상위 N. 기본 5."},
            },
            "required": ["query"],
        },
    },
]


# ── Tool handlers (LLM이 호출 → 실제 함수 실행) ──────────────────────────────

def make_tool_handler(get_project: Callable[[], dict],
                       set_project: Callable[[dict], None],
                       append_chat_event: Callable[[str, dict], None]) -> Callable:
    """tool_handler factory — workspace의 project state에 바인딩.

    Args:
        get_project: 현재 project dict 반환 (sections/tables/...)
        set_project: project dict 저장
        append_chat_event: chat에 system event 추가 (type, payload)
    """
    def handle(name: str, inputs: dict) -> str:
        try:
            if name == "patch_preview":
                return _h_patch_preview(inputs, get_project, set_project, append_chat_event)
            if name == "kyrbs_stat":
                return _h_kyrbs_stat(inputs)
            if name == "pubmed_search":
                return _h_pubmed_search(inputs)
            if name == "strobe_check":
                return _h_strobe(get_project())
            if name == "consistency_check":
                return _h_consistency(get_project())
            if name == "rag_search":
                return _h_rag(inputs)
            return f"unknown tool: {name}"
        except Exception as e:
            return f"ERROR in {name}: {e}"
    return handle


def _h_patch_preview(inputs, get_project, set_project, append_chat_event):
    proj = get_project()
    sections = proj.setdefault("sections", {})
    content = inputs.get("content", "")
    append = inputs.get("append", True)
    section = inputs.get("section") or ""
    subsection = inputs.get("subsection") or ""
    abstract_field = inputs.get("abstract_field") or ""
    supplement_block = inputs.get("supplement_block") or ""

    target = ""
    if abstract_field:
        ab = sections.setdefault("Abstract", {})
        if not isinstance(ab, dict):
            ab = {"Background": str(ab)}
            sections["Abstract"] = ab
        old = ab.get(abstract_field, "")
        ab[abstract_field] = (old + "\n\n" + content).strip() if append and old else content
        target = f"Abstract.{abstract_field}"
    elif section:
        if subsection:
            sec = sections.setdefault(section, {})
            if not isinstance(sec, dict):
                sec = {"_intro": str(sec)}
                sections[section] = sec
            old = sec.get(subsection, "")
            sec[subsection] = (old + "\n\n" + content).strip() if append and old else content
            target = f"{section}.{subsection}"
        else:
            old = sections.get(section, "")
            if isinstance(old, dict):
                old["_appended"] = (old.get("_appended", "") + "\n\n" + content).strip()
            else:
                sections[section] = (old + "\n\n" + content).strip() if append and old else content
            target = section
    elif supplement_block:
        supp = proj.setdefault("supplement", {})
        old = supp.get(supplement_block, "")
        supp[supplement_block] = (old + "\n\n" + content).strip() if append and old else content
        target = f"Supplement.{supplement_block}"

    set_project(proj)
    append_chat_event("preview_patched",
                       {"target": target, "len": len(content),
                        "preview": content[:120]})
    return (f"OK — patched {target} ({len(content)} chars). "
            f"Preview docx 갱신됨.")


def _h_kyrbs_stat(inputs):
    from pathlib import Path as _P
    from src.data.kyrbs_raw_loader import KYRBSLoader
    from src.data.stat_bridge import StatBridge

    sav = _P("data/raw/kyrbs2025.sav")
    if not sav.exists():
        return "ERROR: kyrbs2025.sav 없음"
    df, _ = KYRBSLoader().load(sav)
    outcome = inputs["outcome"]
    exposure = inputs["exposure"]
    covariates = inputs.get("covariates") or ["sex", "age", "school_type"]
    spec = {"outcome": outcome, "predictors": [exposure],
             "covariates": [c for c in covariates if c in df.columns],
             "weight_var": "weight_var" if "weight_var" in df.columns else None,
             "strata_var": "strata" if "strata" in df.columns else None,
             "cluster_var": "cluster" if "cluster" in df.columns else None,
             "analysis": "logistic"}
    r = StatBridge().run(df, spec).to_dict()
    vars_ = r.get("model_vars", [])
    tgt = next((v for v in vars_ if exposure in str(v.get("variable", "")).lower()), None)
    if not tgt:
        return f"WARN: {exposure}에 해당하는 추정치 없음. vars={[v.get('variable') for v in vars_[:6]]}"
    return json.dumps({
        "n": len(df), "outcome": outcome, "exposure": exposure,
        "aOR": tgt.get("or_value"),
        "ci_low": tgt.get("ci_lower"), "ci_high": tgt.get("ci_upper"),
        "p_value": tgt.get("p_value"),
        "n_covariates": len(spec["covariates"]),
        "design": "svy-style (pweight + cluster)" if spec["weight_var"] else "unweighted",
    }, ensure_ascii=False)


def _h_pubmed_search(inputs):
    from src.research.novelty_checker import NoveltyChecker
    q = inputs["query"]
    n = inputs.get("max_results", 10)
    yrs = inputs.get("years", 5)
    result = NoveltyChecker().check(q, max_results=n, years=yrs)
    return json.dumps({
        "novelty_score": result.get("novelty_score"),
        "summary": (result.get("summary") or "")[:600],
        "similar_papers": [{"title": p.get("title", "")[:120],
                              "year": p.get("year"),
                              "authors": (p.get("authors") or "")[:100]}
                            for p in (result.get("similar_papers") or [])[:n]],
    }, ensure_ascii=False)


def _h_strobe(project):
    from src.research.reporting_checklist import check_strobe, format_checklist_report
    sections = project.get("sections", {}) or {}
    abstract = sections.get("Abstract") or ""
    r = check_strobe(sections, abstract=abstract)
    return format_checklist_report(r, verbose=True)


def _h_consistency(project):
    from src.safety.consistency_checker import check_consistency
    rep = check_consistency(project.get("sections") or {})
    return json.dumps(rep.to_dict(), ensure_ascii=False)


def _h_rag(inputs):
    from src.rag.pipeline import RAGPipeline
    hits = RAGPipeline().search_multistage(inputs["query"],
                                              n_final=inputs.get("n", 5),
                                              n_pool=20)
    return json.dumps([{
        "text": (h.get("text") or "")[:300],
        "score": h.get("final_score"),
        "metadata": h.get("metadata", {}),
    } for h in hits], ensure_ascii=False)


# ── System prompt — preview snapshot 포함 ────────────────────────────────────

def build_system_with_preview(base_prompt: str, project: dict) -> str:
    """LLM이 매 호출마다 현재 preview snapshot을 보도록 system prompt 끝에 첨부."""
    sections = project.get("sections", {}) or {}
    parts = ["", "# CURRENT PREVIEW (docx state — 사용자가 실제로 보고 있는 본문)", ""]
    # Abstract
    ab = sections.get("Abstract")
    if ab:
        parts.append("## Abstract")
        if isinstance(ab, dict):
            for k in ("Background", "Methods", "Results", "Conclusion"):
                v = ab.get(k)
                if v:
                    parts.append(f"**{k}**: {str(v)[:600]}")
        else:
            parts.append(str(ab)[:1000])
    for sec in ("Introduction", "Methods", "Results", "Discussion"):
        body = sections.get(sec)
        if not body:
            continue
        parts.append(f"## {sec}")
        if isinstance(body, dict):
            for sk, sv in body.items():
                parts.append(f"### {sk}\n{str(sv)[:600]}")
        else:
            parts.append(str(body)[:1200])
    tables = project.get("tables", [])
    if tables:
        parts.append(f"## Tables ({len(tables)} 개) 등록됨")
    supp = project.get("supplement", {}) or {}
    if supp:
        parts.append(f"## Supplement blocks: {list(supp.keys())}")

    parts.append("")
    parts.append("→ 위 preview를 보고 부족한 부분이 있으면 `patch_preview` tool을 호출해 직접 채워라. "
                  "통계 결과가 필요하면 `kyrbs_stat`, 인용이 필요하면 `pubmed_search`/`rag_search`, "
                  "보고 양식 검증은 `strobe_check`, 정합성은 `consistency_check`.")
    return (base_prompt or "") + "\n\n" + "\n".join(parts)
