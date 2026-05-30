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
        "description": "KYRBS/KNHANES 원시자료로 즉시 회귀 분석. "
                        "outcome/exposure/covariates 자유 조합 가능 — 사용자가 '공변량에 BMI 추가' "
                        "또는 'outcome을 스트레스로 변경' 같이 요청하면 즉시 이 tool 호출 후 "
                        "patch_preview로 Results/Methods 갱신. 결과: aOR, 95% CI, P, all_vars_or.",
        "input_schema": {
            "type": "object",
            "properties": {
                "outcome": {"type": "string",
                             "description": "결과변인. depression/stress/sleep_satis/insufficient_sleep/suicide_ideation 등 KYRBS 표준 컬럼명"},
                "exposure": {"type": "string",
                              "description": "주요 노출. zcb_freq/ssb_freq/screen_time/smartphone_hours/smoking/alcohol/physical_act 등"},
                "covariates": {"type": "array", "items": {"type": "string"},
                                "description": "공변량 리스트. 미지정 시 표준 11개 (sex,age,school_type,family_econ,academic_perf,bmi,smoking,alcohol,physical_act,screen_time,breakfast). "
                                                "사용자 요청에 따라 자유롭게 추가/제거."},
                "years": {"type": "array", "items": {"type": "integer"},
                           "description": "차수 연도 (예: [2024] 또는 [2020,2021,2022,2023,2024,2025]). 미지정 시 가장 최근 1년."},
                "dataset": {"type": "string", "enum": ["KYRBS", "KNHANES"],
                             "description": "데이터셋 종류. 기본 KYRBS."},
                "analysis": {"type": "string", "enum": ["logistic", "linear", "gee_logistic"],
                              "description": "분석 종류. 기본 logistic."},
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
    {
        "name": "find_components",
        "description": "ComponentLibrary에서 reusable microcomponent 양식 N개 sample. "
                        "kind: hedging|stat_report|transition|topic_sentence|"
                        "methods_boilerplate|mechanism_phrase|limitation|"
                        "figure_caption_pattern|table_caption_pattern|"
                        "subgroup_sentence|citation_cluster_pattern. "
                        "patch_preview 전에 호출해서 양식을 골라 조합하라.",
        "input_schema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string",
                          "description": "components 종류"},
                "n": {"type": "integer", "description": "상위 N. 기본 5."},
                "author_style": {"type": "string",
                                  "description": "특정 저자 양식만 (예: yoosun_cho). 선택."},
                "contains": {"type": "string",
                              "description": "본문에 포함될 키워드. 선택."},
            },
            "required": ["kind"],
        },
    },
    {
        "name": "cross_modal_query",
        "description": "KnowledgeOrchestrator 통합 검색 — vector top-K + graph neighbors "
                        "+ top concepts + suggested citations 한 번에. "
                        "복합 정보가 필요한 작성 단계 진입 시 호출.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "k": {"type": "integer", "description": "기본 8."},
                "intent": {"type": "string",
                            "description": "evidence|definition|citation|stat_method|figure_example"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "apply_author_style",
        "description": "★ ② Style layer — 합성된 substance text에 저자 voice 입힘. "
                        "Content components로 draft 만든 다음, 본 tool로 yoosun_cho 양식 "
                        "(hedging/transition/단락 전개) 입혀라. 숫자/인용/통계는 보존됨.",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "스타일 입힐 본문"},
                "author_style": {"type": "string",
                                  "description": "yoosun_cho (기본) 또는 다른 author"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "run_plan",
        "description": "★ Planner DAG 실행 — section 단위 multi-step 자동 처리. "
                        "section 지정 시 evidence→components→compose→style→patch→verify DAG "
                        "자동 생성·실행. roles(researcher/writer/stylist/critic)로 dispatch.",
        "input_schema": {
            "type": "object",
            "properties": {
                "section": {"type": "string",
                             "description": "Introduction|Methods|Results|Discussion"},
                "goal": {"type": "string",
                          "description": "이 section의 작성 목표 (예: ZCB-depression intro)"},
                "outcome": {"type": "string", "description": "Results/Methods용 (depression 등)"},
                "exposure": {"type": "string", "description": "zcb_freq 등"},
            },
            "required": ["section", "goal"],
        },
    },
    {
        "name": "dispatch_role",
        "description": "Multi-agent role에 직접 위임 — researcher/writer/stylist/critic/"
                        "statistician/citation_auditor. specialized prompt + 도구 제한.",
        "input_schema": {
            "type": "object",
            "properties": {
                "role": {"type": "string",
                          "description": "planner|researcher|writer|stylist|critic|statistician|citation_auditor"},
                "message": {"type": "string", "description": "role에 전달할 본문"},
            },
            "required": ["role", "message"],
        },
    },
    {
        "name": "procedural_recall",
        "description": "행동 전략 메모리 회수 — 'reviewer는 X를 본다' 같은 누적 규칙. "
                        "context를 주면 trigger 매칭된 rule 반환. 적용 후 report_outcome 호출.",
        "input_schema": {
            "type": "object",
            "properties": {
                "context": {"type": "string"},
                "domain": {"type": "string",
                            "description": "journal_review|stat_method|figure_style|... 선택"},
            },
            "required": ["context"],
        },
    },
    {
        "name": "consensus_search",
        "description": "같은 query를 여러 retrieval strategy로 병렬 호출 → consensus rerank "
                        "+ contradiction detect. critical evidence가 필요할 때.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n_samples": {"type": "integer",
                                "description": "consensus 반복 횟수 (기본 3)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "causal_check",
        "description": "본문의 causal claim 추출 + study_design 적합성 평가 "
                        "(strong/weak/neutral 분류, STROBE 권고 위반 검출).",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string"},
                "study_design": {"type": "string",
                                  "description": "cross_sectional(기본)|cohort|rct|case_control|review"},
            },
            "required": ["text"],
        },
    },
    {
        "name": "external_evidence",
        "description": "RAG에서 단일 claim을 지지/반박하는 ref 검색 → consensus verdict. "
                       "강한 인과 진술 보강 시.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "k": {"type": "integer", "description": "검색 수 (기본 5)"},
            },
            "required": ["claim"],
        },
    },
    {
        "name": "longitudinal_trend",
        "description": "eval metric의 시계열 trend + regression alert. "
                        "'지난주보다 좋아졌나' 자가 진단 용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string",
                            "description": "특정 metric 지정 시 그 trend만. 없으면 전체 summary"},
                "days": {"type": "integer", "description": "기간 (기본 30)"},
            },
        },
    },
    {
        "name": "sandbox_run",
        "description": "Python 코드를 격리 subprocess에서 실행 → stdout/stderr/exit. "
                        "통계 코드 검증·새 logic 테스트용.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "timeout_sec": {"type": "integer", "description": "기본 30"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "slash_run",
        "description": "의학 논문 도메인 슬래시 커맨드 (/research-question, /study-design, "
                        "/run-analysis, /draft-section, /strobe-review, /submit-journal, "
                        "/research-pulse) 실행. 사용자 의도 명확한 다단계 워크플로우.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slash": {"type": "string"},
                "args": {"type": "object",
                          "description": "각 슬래시별 인자 (topic/exposure/outcome/sections/text 등)"},
            },
            "required": ["slash"],
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
            if name == "find_components":
                return _h_find_components(inputs)
            if name == "cross_modal_query":
                return _h_cross_modal(inputs)
            if name == "apply_author_style":
                return _h_apply_style(inputs)
            if name == "run_plan":
                return _h_run_plan(inputs, get_project, set_project, append_chat_event)
            if name == "dispatch_role":
                return _h_dispatch_role(inputs, get_project)
            if name == "procedural_recall":
                return _h_procedural(inputs)
            if name == "consensus_search":
                return _h_consensus(inputs)
            if name == "causal_check":
                return _h_causal(inputs)
            if name == "external_evidence":
                return _h_external_ev(inputs)
            if name == "longitudinal_trend":
                return _h_longitudinal(inputs)
            if name == "sandbox_run":
                return _h_sandbox(inputs)
            if name == "slash_run":
                return _h_slash(inputs)
            return f"unknown tool: {name}"
        except Exception as e:
            return f"ERROR in {name}: {e}"
    return handle


def _h_patch_preview(inputs, get_project, set_project, append_chat_event):
    """patch_preview — before/after 메타도 함께 저장해서 chat에 diff 렌더 가능하게."""
    proj = get_project()
    sections = proj.setdefault("sections", {})
    content = inputs.get("content", "")
    append = inputs.get("append", True)
    section = inputs.get("section") or ""
    subsection = inputs.get("subsection") or ""
    abstract_field = inputs.get("abstract_field") or ""
    supplement_block = inputs.get("supplement_block") or ""

    target = ""
    before = ""
    after = ""
    if abstract_field:
        ab = sections.setdefault("Abstract", {})
        if not isinstance(ab, dict):
            ab = {"Background": str(ab)}
            sections["Abstract"] = ab
        before = str(ab.get(abstract_field, "") or "")
        after = (before + "\n\n" + content).strip() if append and before else content
        ab[abstract_field] = after
        target = f"Abstract.{abstract_field}"
    elif section:
        if subsection:
            sec = sections.setdefault(section, {})
            if not isinstance(sec, dict):
                sec = {"_intro": str(sec)}
                sections[section] = sec
            before = str(sec.get(subsection, "") or "")
            after = (before + "\n\n" + content).strip() if append and before else content
            sec[subsection] = after
            target = f"{section}.{subsection}"
        else:
            raw = sections.get(section)
            if isinstance(raw, dict):
                before = str(raw.get("_appended", "") or "")
                after = (before + "\n\n" + content).strip() if append and before else content
                raw["_appended"] = after
            else:
                before = str(raw or "")
                after = (before + "\n\n" + content).strip() if append and before else content
                sections[section] = after
            target = section
    elif supplement_block:
        supp = proj.setdefault("supplement", {})
        before = str(supp.get(supplement_block, "") or "")
        after = (before + "\n\n" + content).strip() if append and before else content
        supp[supplement_block] = after
        target = f"Supplement.{supplement_block}"

    set_project(proj)
    # before/after 메타를 chat event에 저장 → rich diff 렌더 가능
    append_chat_event("preview_patched",
                       {"target": target,
                        "before": before[-800:],
                        "after": after[-800:],
                        "added": content[:600],
                        "append": append})

    # 자가학습 — 검증된 patch는 conversation_memory에 PROJECT_FACT 등급으로 저장
    try:
        from src.memory import conversation_memory as cm
        cm.record(
            user_message=f"patch_preview({target})",
            agent_response=f"[patched] {content[:400]}",
            topic=target,
            context_type="research",
            owner_email=str(proj.get("owner", "")) or "",
        )
    except Exception:
        pass

    return (f"OK — patched {target} ({len(content)} chars). "
            f"Preview docx 갱신됨. before_len={len(before)} after_len={len(after)}.")


# DataFrame 캐시 — 14초 KYRBS 로드를 매번 반복 안 하도록 (2026-05-30)
# key: (dataset_kind, tuple(years)) → df
_KYRBS_DF_CACHE: dict = {}


def _load_kyrbs_cached(years: list[int], dataset_kind: str = "KYRBS"):
    """절대경로 + 캐시. years=None/empty면 가장 최근 단일."""
    from pathlib import Path as _P
    import re as _re_cache
    from src.data.kyrbs_raw_loader import KYRBSLoader, KNHANESLoader
    import pandas as _pd_cache

    cache_key = (dataset_kind, tuple(sorted(years or [])))
    if cache_key in _KYRBS_DF_CACHE:
        return _KYRBS_DF_CACHE[cache_key]

    _project_root = _P(__file__).resolve().parent.parent
    raw_dir = _project_root / "data" / "raw"
    uploads_dir = _project_root / "data" / "uploads"

    available: dict = {}
    if dataset_kind == "KYRBS":
        for y in range(2005, 2026):
            cand = raw_dir / f"kyrbs{y}.sav"
            if cand.exists():
                available[y] = cand
        if uploads_dir.exists():
            for p in uploads_dir.glob("*.sav"):
                m = _re_cache.search(r"(20[0-2]\d)", p.name)
                if m:
                    available.setdefault(int(m.group(1)), p)
    else:
        for p in (raw_dir / "knhanes").glob("*.sav"):
            m = _re_cache.search(r"(20[0-2]\d)", p.name)
            if m:
                available[int(m.group(1))] = p

    if not available:
        raise FileNotFoundError(
            f"{dataset_kind} .sav 파일 없음. 로컬 docker (localhost:8501)에서 사용하거나 "
            f"ez_home에 .sav 첨부 필요.")

    target_years = [y for y in (years or []) if y in available] or [max(available.keys())]
    loader = KYRBSLoader() if dataset_kind == "KYRBS" else KNHANESLoader()
    dfs = []
    for y in sorted(target_years):
        df_y, _ = loader.load(available[y])
        df_y["__survey_year"] = y
        dfs.append(df_y)
    df = _pd_cache.concat(dfs, ignore_index=True) if len(dfs) > 1 else dfs[0]
    _KYRBS_DF_CACHE[cache_key] = (df, target_years)
    return df, target_years


def _h_kyrbs_stat(inputs):
    """KYRBS/KNHANES 즉시 통계 — 캐시 + 다년도 + 유동 covariates (2026-05-30 강화).

    inputs:
      outcome, exposure (필수)
      covariates: list[str] — 미지정 시 표준 11개 자동
      years: list[int] | None — 미지정 시 최근 1년
      dataset: "KYRBS"|"KNHANES" — 기본 KYRBS
      analysis: "logistic"|"linear"|"gee_logistic" — 기본 logistic
    """
    from src.data.stat_bridge import StatBridge
    try:
        years = inputs.get("years") or []
        dataset_kind = inputs.get("dataset") or "KYRBS"
        df, used_years = _load_kyrbs_cached(years, dataset_kind=dataset_kind)
    except Exception as e:
        return json.dumps({"error": f"{type(e).__name__}: {str(e)[:200]}",
                            "hint": "ez_home 📎 파일 첨부로 .sav 업로드하거나 localhost:8501 사용"},
                           ensure_ascii=False)

    outcome = inputs["outcome"]
    exposure = inputs["exposure"]
    # 기본 11 covariates — 미지정 시 자동
    default_covs = ["sex", "age", "school_type", "family_econ", "academic_perf",
                     "bmi", "smoking", "alcohol", "physical_act",
                     "screen_time", "breakfast"]
    requested = inputs.get("covariates") or default_covs
    covariates = [c for c in requested if c in df.columns and c != exposure]
    analysis = inputs.get("analysis") or "logistic"

    spec = {"outcome": outcome, "predictors": [exposure],
             "covariates": covariates,
             "weight_var": "weight_var" if "weight_var" in df.columns else None,
             "strata_var": "strata" if "strata" in df.columns else None,
             "cluster_var": "cluster" if "cluster" in df.columns else None,
             "analysis": analysis}
    try:
        r = StatBridge().run(df, spec).to_dict()
    except Exception as e:
        return json.dumps({
            "error": f"StatBridge 실패: {type(e).__name__}: {str(e)[:200]}",
            "spec": spec,
            "available_cols_sample": [c for c in df.columns[:40]],
        }, ensure_ascii=False)

    vars_ = r.get("model_vars", [])
    tgt = next((v for v in vars_ if exposure in str(v.get("variable", "")).lower()), None)

    # 모든 covariates의 aOR도 같이 반환 — LLM이 Table 1 만들 때 사용
    cov_or = [{
        "variable": v.get("variable"), "label": v.get("label"),
        "aOR": v.get("or_value"),
        "ci_low": v.get("ci_lower"), "ci_high": v.get("ci_upper"),
        "p": v.get("p_value"),
        "significant": v.get("significant"),
    } for v in vars_ if v.get("or_value") is not None]

    out = {
        "n": int(r.get("n_total") or len(df)),
        "outcome": outcome, "exposure": exposure,
        "years_used": used_years,
        "dataset": dataset_kind,
        "covariates_used": covariates,
        "covariates_dropped": [c for c in requested if c not in covariates],
        "analysis": analysis,
        "design": "svy-style (pweight + cluster)" if spec["weight_var"] else "unweighted",
        "pseudo_r2": (r.get("model_metrics") or {}).get("pseudo_r2"),
        "all_vars_or": cov_or,
    }
    if tgt:
        out.update({
            "aOR": tgt.get("or_value"),
            "ci_low": tgt.get("ci_lower"), "ci_high": tgt.get("ci_upper"),
            "p_value": tgt.get("p_value"),
            "significant": tgt.get("significant"),
        })
    else:
        out["warning"] = f"{exposure}에 해당하는 추정치 없음. 결과 변수명 후보: {[v.get('variable') for v in vars_[:6]]}"
    return json.dumps(out, ensure_ascii=False)


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


def _h_find_components(inputs):
    """ComponentLibrary 검색 — WritingOrchestrator.gather_components 위임.
    layer 정보(content/style) 함께 반환해서 LLM이 pipeline 단계 인식."""
    from src.agent.writing_orchestrator import get_writing_orchestrator
    from src.library.components import kind_layer
    kind = inputs["kind"]
    hits = get_writing_orchestrator().gather_components(
        kind=kind,
        n=int(inputs.get("n", 5)),
        author_style=inputs.get("author_style"),
        contains=inputs.get("contains"),
    )
    layer = kind_layer(kind)
    return json.dumps({
        "layer": layer,
        "kind": kind,
        "n": len(hits),
        "hint": ("content layer — substance/내용. draft 작성에 활용." if layer == "content"
                  else ("style layer — author voice. draft 합성 후 입힐 양식 풀."
                          if layer == "style" else "unknown kind")),
        "components": [{"id": h["id"], "text": h["text"][:400],
                         "source_pmid": h.get("source_pmid", ""),
                         "n_uses": h.get("n_uses", 0)}
                        for h in hits],
    }, ensure_ascii=False)


def _h_cross_modal(inputs):
    """KnowledgeOrchestrator 통합 검색."""
    from src.agent.writing_orchestrator import (
        get_writing_orchestrator, KnowledgeRequest)
    req = KnowledgeRequest(
        intent=inputs.get("intent", "evidence"),
        query=inputs["query"],
        k=int(inputs.get("k", 8)),
    )
    resp = get_writing_orchestrator().ask_knowledge(req)
    return json.dumps(resp.to_dict(), ensure_ascii=False)[:6000]


def _h_apply_style(inputs):
    """② Style layer — substance text에 저자 voice 입힘."""
    from src.agent.writing_orchestrator import get_writing_orchestrator
    styled = get_writing_orchestrator().apply_author_style(
        text=inputs.get("text", ""),
        author_style=inputs.get("author_style", "yoosun_cho"),
    )
    return styled[:4000]


def _h_run_plan(inputs, get_project, set_project, append_chat_event):
    """Planner DAG 생성 + 실행 — node action을 roles.dispatch_role로 위임."""
    from src.agent.planner import get_planner
    from src.agent.roles import role_for_action, dispatch_role
    section = inputs.get("section", "Introduction")
    goal = inputs.get("goal", section)
    ctx = {"section": section,
           "outcome": inputs.get("outcome"), "exposure": inputs.get("exposure")}
    proj = get_project()

    planner = get_planner()
    graph = planner.plan(goal, context=ctx)

    def _exec_node(node):
        # node.action → role → 실 호출
        role = role_for_action(node.action)
        # role에 필요한 메시지 합성
        msg = (f"DAG node {node.id} action={node.action} args={json.dumps(node.args, ensure_ascii=False)} "
                f"rationale={node.rationale}. Use the allowed tools to produce the expected output.")
        result = dispatch_role(role, {"message": msg, "project": proj})
        return {"role": role, "node_action": node.action,
                "text": (result.get("text") or "")[:600],
                "tools_used": result.get("tools_used", [])}

    executed = planner.execute(graph, executor=_exec_node)
    summary = {
        "graph_id": executed.id, "state": executed.state,
        "n_nodes": len(executed.nodes),
        "n_done": sum(1 for n in executed.nodes.values() if n.state == "done"),
        "n_failed": sum(1 for n in executed.nodes.values() if n.state == "failed"),
        "steps": [{"id": n.id, "action": n.action, "state": n.state,
                    "role": role_for_action(n.action),
                    "output_preview": str(n.output)[:200] if n.output else ""}
                   for n in executed.nodes.values()],
    }
    return json.dumps(summary, ensure_ascii=False)[:6000]


def _h_dispatch_role(inputs, get_project):
    from src.agent.roles import dispatch_role
    r = dispatch_role(inputs["role"], {"message": inputs.get("message", ""),
                                          "project": get_project()})
    return json.dumps({"role": r.get("role"),
                        "text": (r.get("text") or "")[:1500],
                        "tools_used": r.get("tools_used", []),
                        "error": r.get("error", "")}, ensure_ascii=False)


def _h_procedural(inputs):
    from src.memory.procedural import find_applicable
    rules = find_applicable(inputs.get("context", ""),
                              domain=inputs.get("domain"),
                              limit=5)
    return json.dumps({"n": len(rules), "rules": rules}, ensure_ascii=False)


def _h_consensus(inputs):
    from src.llm.tool_consensus import consensus_call, parallel_branches, contradiction_check
    from src.rag.pipeline import RAGPipeline
    q = inputs["query"]
    n = int(inputs.get("n_samples", 3))
    rag = RAGPipeline()
    cons = consensus_call(rag.search, {"query": q, "n_results": 5}, n=n)
    branches = parallel_branches([
        ("dense", lambda: rag.search(q, n_results=5)),
        ("multistage", lambda: rag.search_multistage(q, n_final=5, n_pool=20)
            if hasattr(rag, "search_multistage") else []),
    ])
    # ★ contradiction check across all results (organism flow — 추가 검증)
    all_outputs = list(cons.get("raw", [])) + list(branches.get("results", {}).values())
    cc = contradiction_check([o for o in all_outputs if o]) if len(all_outputs) >= 2 else {}
    return json.dumps({
        "consensus": {"agreement": cons["agreement"],
                       "contradiction": cons["contradiction"], "n": cons["n"]},
        "branches": {"n_ok": len(branches["results"]),
                      "elapsed_sec": branches["elapsed_sec"]},
        "cross_contradiction": cc,
        "answer_preview": str(cons["answer"])[:600],
    }, ensure_ascii=False)


def _h_causal(inputs):
    from src.safety.causal_checker import check_causal_claims
    rep = check_causal_claims(inputs["text"],
                                study_design=inputs.get("study_design", "cross_sectional"))
    return json.dumps(rep.to_dict(), ensure_ascii=False)[:4000]


def _h_external_ev(inputs):
    from src.safety.causal_checker import external_evidence_consensus
    r = external_evidence_consensus(inputs["claim"], k=int(inputs.get("k", 5)))
    return json.dumps(r, ensure_ascii=False)[:3000]


def _h_longitudinal(inputs):
    from src.diagnostics.longitudinal_eval import trend, summary
    m = inputs.get("metric")
    days = int(inputs.get("days", 30))
    if m:
        return json.dumps(trend(m, days=days), ensure_ascii=False)
    return json.dumps(summary(days=days), ensure_ascii=False)[:4000]


def _h_slash(inputs):
    """의학 논문 도메인 슬래시 커맨드 dispatch."""
    from src.agent.slash_commands import run_slash
    r = run_slash(inputs.get("slash", ""), inputs.get("args") or {})
    return json.dumps(r, ensure_ascii=False, default=str)[:5000]


def _h_sandbox(inputs):
    from src.runtime.sandbox import run_python, regression_compare
    r = run_python(inputs["code"], timeout_sec=int(inputs.get("timeout_sec", 30)))
    # 같은 입력의 직전 실행 결과가 session에 있으면 regression 비교
    sess_key = f"_sandbox_last_{hash(inputs['code'])}"
    reg = None
    try:
        # session_state 없을 수도 (mcp/cli 경로) — file fallback
        from pathlib import Path as _P
        cache = _P("data/runtime/sandbox_last.json")
        prev = {}
        if cache.exists():
            import json as _j
            try:
                prev = _j.loads(cache.read_text(encoding="utf-8"))
            except Exception:
                prev = {}
        if sess_key in prev and r["ok"]:
            reg = regression_compare(prev[sess_key], r["stdout"])
        # 갱신
        prev[sess_key] = r["stdout"][:5000]
        cache.parent.mkdir(parents=True, exist_ok=True)
        import json as _j
        cache.write_text(_j.dumps(prev, ensure_ascii=False)[:200000], encoding="utf-8")
    except Exception:
        pass
    return json.dumps({"ok": r["ok"], "exit": r["exit_code"],
                        "stdout": r["stdout"][:2000],
                        "stderr": r["stderr"][:1500],
                        "elapsed_sec": r["elapsed_sec"],
                        "regression_vs_prev": reg}, ensure_ascii=False)


# ── System prompt — preview snapshot 포함 ────────────────────────────────────

def build_system_with_preview(base_prompt: str, project: dict,
                                user_msg: str = "") -> str:
    """★ 유기체 흐름 ([[feedback_organism_flow]]) — LLM이 매 호출마다 다음을 모두 봄:
    1. trigger_analyzer 결과 (intent/topic/sentiment/priority)
    2. cognitive_activation 5-layer (fragments → routing → flow → policy)
    3. recall_all_layers 5층 메모리 (working/episodic/semantic/procedural/goal)
    4. 현재 preview snapshot (docx state)
    5. change_log 최근 + longitudinal trend
    """
    sections = project.get("sections", {}) or {}
    owner = str(project.get("owner") or "anonymous")
    parts: list = []

    # 1. Trigger analyzer
    try:
        from src.agent.trigger_analyzer import analyze as _trig
        t = _trig(user_msg) if user_msg else None
        if t:
            parts.append("# TRIGGER ANALYSIS (auto)")
            parts.append(f"intent={t.intent}({t.intent_confidence}) "
                          f"topics={t.topics[:5]} sentiment={t.sentiment} "
                          f"priority={t.priority} urgency_sec={t.urgency_sec}")
            parts.append("")
    except Exception:
        pass

    # 2. Cognitive activation 5-layer
    try:
        from src.agent.cognitive_activation import activate as _activate, to_system_prompt_block
        if user_msg:
            act = _activate(user_msg, project=project, owner=owner)
            block = to_system_prompt_block(act)
            if block:
                parts.append(block)
                parts.append("")
    except Exception:
        pass

    # 3. Recall 5층 메모리 (facade)
    try:
        from src.memory import recall_all_layers
        if user_msg:
            layers = recall_all_layers(user_msg, owner=owner, n_per_layer=3)
            non_empty = {k: v for k, v in layers.items() if v}
            if non_empty:
                parts.append("# 5-LAYER MEMORY RECALL")
                for k, v in non_empty.items():
                    if k == "episodic" and isinstance(v, str):
                        parts.append(f"## {k}\n{v[:600]}")
                    else:
                        import json as _j
                        parts.append(f"## {k}\n{_j.dumps(v, ensure_ascii=False, default=str)[:600]}")
                parts.append("")
    except Exception:
        pass

    # 4. PREVIEW snapshot
    parts.append("# CURRENT PREVIEW (docx state — 사용자가 실제로 보고 있는 본문)")
    parts.append("")
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
    parts.append("=" * 60)
    parts.append("★★ MANDATORY BEHAVIOR — 매 응답에 반드시 지킬 것 ★★")
    parts.append("=" * 60)
    parts.append(
        "1) **사용자의 모든 요청(단어 한 글자라도)은 즉시 `patch_preview` tool로 preview에 반영하라.**\n"
        "   - '좀 더 자세히' → 해당 섹션 expand patch\n"
        "   - 'X 추가해줘' → 해당 위치 append patch\n"
        "   - '다시 써줘' → overwrite patch\n"
        "   - 답변 텍스트보다 preview 갱신이 우선. 텍스트 답변은 1-2문장 요약만.\n"
        "2) **인용·근거가 필요한 변경은 patch_preview 직전에 `rag_search` 또는 `cross_modal_query`를 호출**해서 "
        "   24,000+편 OA seed에서 evidence 가져온 뒤 patch에 포함하라. 환각 금지.\n"
        "3) **통계 변경 요청은 `kyrbs_stat`을 즉시 호출** — 이후 결과를 patch_preview로 Results+Methods 갱신.\n"
        "   다음 패턴은 무조건 kyrbs_stat 즉시 호출:\n"
        "   • 'outcome을 X로 바꿔' / 'X로 결과변인 변경' → outcome=X\n"
        "   • 'BMI 추가/제외' / '공변량에 X 넣어/빼' → covariates 조정\n"
        "   • '2023년으로' / '2020~2024 합쳐' → years 지정\n"
        "   • '단순 logistic 말고 GEE로' → analysis='gee_logistic'\n"
        "   결과 받은 후 Methods의 'Statistical analysis' 절·Results 본문·Table 1 모두 즉시 patch_preview.\n"
        "4) **요청이 모호하면** Methods → Results → Discussion 순서로 부족한 곳부터 patch.\n"
        "5) 한 응답에 patch_preview를 0번 호출하면 그 응답은 실패로 간주된다. 최소 1번 호출 필수.\n"
    )
    parts.append("")

    # ── ★ INTENT SENSING (2026-05-30) — 사용자 의도/뉘앙스/페르소나 5+2차원 센싱 ──
    # 결과는 system_prompt에 주입 + 아래 RAG/components 검색 키워드를 intent로 augment.
    intent_emphasis_kws: list[str] = []
    intent_persona_kws: list[str] = []
    intent_voice: list[str] = []
    try:
        from src.agent.intent_sensor import sense as _intent_sense
        sig = _intent_sense(user_msg or "",
                             prior_messages=project.get("messages") or [],
                             project=project, owner_email=owner)
        intent_block = sig.to_system_block()
        if intent_block:
            parts.append(intent_block)
            parts.append("")
        # 이후 RAG / components 검색 query에 주입할 의도 키워드 추출
        intent_emphasis_kws = list(sig.implicit_emphasis or [])
        intent_persona_kws = list((sig.user_persona_inferred or {}).get("top_domain_keywords", []))
        intent_voice = list(sig.voice_tone or [])
    except Exception:
        pass

    # ── AUTO RAG EVIDENCE (사용자 user_msg에 대한 5개 hit 자동 사전 주입) ──
    # 사용자가 patch 요청만 해도 LLM이 항상 evidence를 곁들이도록 미리 가져온다.
    # 2026-05-30: intent emphasis + persona keywords로 query augment → 통일된 톤·관심으로 검색
    if user_msg:
        try:
            from src.vectordb.store import get_vector_store
            store = get_vector_store()
            # 의도 키워드로 augment된 쿼리
            aug_kws = (intent_persona_kws[:3] + intent_emphasis_kws[:2])
            aug_query = user_msg
            if aug_kws:
                aug_query = user_msg + " " + " ".join(aug_kws)
            hits = store.search(aug_query, n_results=5) or []
            if hits:
                parts.append("# AUTO-PULLED RAG EVIDENCE (24K OA seed — 위 요청 관련)")
                for i, h in enumerate(hits[:5], 1):
                    md = h.get("metadata") or {}
                    src = md.get("source") or md.get("doi") or md.get("pmid") or md.get("title", "")
                    score = h.get("score", 0) or h.get("final_score", 0)
                    snippet = (h.get("text") or "")[:280]
                    parts.append(f"[{i}] (score={score:.3f}) {snippet}…")
                    if src:
                        parts.append(f"    src: {str(src)[:120]}")
                parts.append("→ 이 evidence를 patch_preview 내용에 인용/근거로 활용하라.")
                parts.append("")
        except Exception:
            pass

        # ── AUTO COMPONENTS (재사용 가능한 양식 시드 — ComponentLibrary) ──
        try:
            from src.library.components import get_library as _get_comp_lib
            comp_hint = _get_comp_lib().sample(
                kind="topic_sentence", n=3, contains=user_msg[:60])
            if comp_hint:
                parts.append("# AUTO-PULLED COMPONENT TEMPLATES (Yoosun-style topic sentences)")
                for c in comp_hint[:3]:
                    parts.append(f"- {str(c.get('text', '') or c)[:200]}")
                parts.append("")
        except Exception:
            pass

    # ★ 공유 코어 — VS Code/Streamlit 어디서 호출되든 같은 메모리/이력 보게 함
    try:
        from src.memory import conversation_memory as cm
        if user_msg:
            recalled_str = cm.recall_relevant(user_msg, n=5, owner_email=owner) or ""
            if recalled_str.strip():
                parts.append("")
                parts.append("# CROSS-SESSION MEMORY (VS Code · Streamlit 공유 — recall_relevant)")
                parts.append(recalled_str[:1500])
    except Exception:
        pass

    try:
        from src.memory.change_log import get_recent
        hist = get_recent(n=5) or []
        if hist:
            parts.append("")
            parts.append("# RECENT WORK LOG (양쪽 entry — change_log)")
            for h in hist:
                title = str(h.get("title", "?"))[:80]
                action = h.get("action_type", "")
                ts = str(h.get("timestamp", ""))[:19]
                parts.append(f"- [{ts}] ({action}) {title}")
    except Exception:
        pass

    return (base_prompt or "") + "\n\n" + "\n".join(parts)
