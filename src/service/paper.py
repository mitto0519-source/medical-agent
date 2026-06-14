"""Paper service — pure-logic IMRAD authoring helpers extracted from ez_home.

All functions take plain data and return plain data. No Streamlit imports.
Per FRONTEND_MIGRATION_SPEC Phase 1: Streamlit page imports these; FastAPI later imports the same.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── Trigger detectors (chat-first UX) ─────────────────────────────────────────
def is_go_wide_trigger(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return any(k in t for k in (
        "여러 방향", "여러 변형", "3가지", "5가지", "3-5개",
        "다양한 pico", "여러 pico", "wide", "go wide", "동시 탐색",
        "병렬 탐색", "비교해줘", "변형 만들어", "옵션 펼쳐", "여러 옵션",
    ))


def is_go_deep_trigger(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return any(k in t for k in (
        "이 방향 깊게", "깊게 다듬", "구체화", "정밀하게",
        "go deep", "deep dive", "더 자세히", "더 깊게",
        "전문가 토론", "관점 비교", "다각도", "비판적으로",
    ))


def is_full_paper_trigger(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return any(k in t for k in (
        "논문 작성", "논문 써", "논문 만들", "manuscript", "full draft",
        "full paper", "전체 논문", "본문 작성", "본문 써", "imrad",
        "실제 논문으로", "완성된 논문", "drafting", "지금까지로 논문",
    ))


def is_autopilot_trigger(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower()
    return any(k in t for k in (
        "알아서 해", "알아서해", "go ahead", "그냥 해", "그냥해",
        "전체 진행", "끝까지", "한번에", "full run", "auto run",
    ))


def detect_figure_request(text: str) -> Optional[str]:
    """Natural-language → figure kind. forest|subgroup|coef|roc|prev|table1|table2|None."""
    if not text:
        return None
    t = text.strip().lower()
    if any(k in t for k in ["forest plot", "forest 그", "forest plot 만"]):
        return "subgroup" if ("subgroup" in t or "하위군" in t) else "forest"
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


# ── System prompts (English manuscript, Korean chat) ──────────────────────────
def go_wide_prompt(user_msg: str) -> str:
    return (
        "사용자가 던진 의학 연구 주제를 받아 3-5개의 PICO 변형을 카드로 제시하세요. "
        "각 카드 구조:\n\n"
        "### Variant {n}: <짧은 제목>\n"
        "- **P**opulation: ...\n"
        "- **I/E**xposure/Intervention: ...\n"
        "- **C**omparison: ...\n"
        "- **O**utcome: ...\n"
        "- **Dataset hint**: KYRBS / KNHANES / NHIS / HIRA / PubMed RCT meta\n"
        "- **연구 가치**: 한 줄로 왜 흥미로운지\n\n"
        "변형은 서로 다른 축(다른 outcome / 다른 population age / 다른 exposure 지표)을 잡아 정말 wide하게 펼치세요. "
        "복붙이 아니라 진짜 다른 방향이어야 합니다. 마지막에 '어느 방향을 깊게 다듬어볼까요?'로 마무리."
    )


def go_deep_prompt(user_msg: str, project: dict) -> str:
    return (
        "선택된 PICO 또는 직전 응답을 더 깊게 다듬기 위해 다음 3관점을 한 번의 응답 안에서 내부 토론하세요:\n\n"
        "**<Epidemiologist>**: 역학·인과추론 관점 (confounder, bias, generalizability)\n"
        "**<Biostatistician>**: 통계 방법 관점 (model choice, sample size, multiple testing)\n"
        "**<Clinician>**: 임상 적용 관점 (clinical relevance, effect size 해석, 임상 의사결정에 어떤 의미)\n\n"
        "각 관점이 한 두 문장씩 의견 제시 → 합의점 + 남은 disagreement 정리. "
        "마지막에 '다음 단계' 한 줄 (어떤 데이터 확보, 어떤 분석 모델, 어떤 sensitivity)."
    )


def full_paper_prompt(project: dict) -> str:
    rs = project.get("research_state") or {}
    target_journal = rs.get("target_journal", "")
    reference_style = rs.get("reference_style", "Vancouver")
    journal_hint = (
        f"Target journal: {target_journal}. Reference style: {reference_style}."
        if target_journal
        else "Reference style: Vancouver (default; change when target journal is set)."
    )
    return f"""You are writing a FULL medical research manuscript, not just an abstract.

CRITICAL RULES:
1. **NEVER fabricate numbers.** All sample sizes, prevalence, OR, 95% CI, p-values, table values MUST come from actual stat_bridge output or cited papers (verbatim). If a number is unknown, STOP and ASK the user instead of inventing.
2. **All manuscript sections MUST be in ENGLISH.** Chat replies stay Korean, but Title/Abstract/Introduction/Methods/Results/Discussion/Conclusion/References/Tables/Figure captions are all English.
3. **Complete IMRAD structure required.** Do NOT stop at abstract. Generate in order: Title → Abstract → Introduction → Methods → Results → Discussion → Conclusion → References. If a section requires data not yet provided, mark `[NEEDS DATA: <specific question>]` inline and continue with remaining sections.
4. **Reference style follows the target journal**, not Vancouver by default. {journal_hint}
5. Use in-text citation markers [n] (Vancouver/AMA) or (Author, year) (Harvard/APA) consistent with the chosen style. Each citation MUST correspond to a real PMID/DOI that will be verified post-hoc.
6. Tables/Figures are described in numbered placeholders (Table 1, Figure 1) with full captions and footnotes; actual data values come from stat_bridge.

OUTPUT FORMAT (English manuscript):

## Title
<concise informative title, ≤25 words>

## Abstract
**Background:** ...
**Objective:** ...
**Methods:** ...
**Results:** ...
**Conclusion:** ...

## 1. Introduction
<3-5 paragraphs: rationale, gap, objective>

## 2. Methods
### 2.1 Study design
### 2.2 Data source and study population
### 2.3 Variables
### 2.4 Statistical analysis
### 2.5 Ethics

## 3. Results
### 3.1 Baseline characteristics (Table 1)
### 3.2 Primary outcome
### 3.3 Secondary outcomes and subgroup analyses
### 3.4 Sensitivity analyses

## 4. Discussion
### 4.1 Main findings
### 4.2 Comparison with prior literature
### 4.3 Mechanistic interpretation
### 4.4 Strengths and limitations

## 5. Conclusion

## References
<numbered list, {reference_style} style>

## Tables
Table 1. <caption>...

## Figure legends
Figure 1. <caption>...

If any required data is missing, STOP that section and write `[NEEDS DATA: question to user]`. Do NOT fabricate numbers to fill gaps."""


# ── Text cleanup ──────────────────────────────────────────────────────────────
def strip_korean_prelude(text: str) -> str:
    """Manuscripts are English-only. Drop any Korean preamble before first English heading."""
    if not text:
        return text
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


def hits_to_references(rag_context: str) -> List:
    """Extract PMIDs from RAG context → list[citation_workflow.Reference]."""
    if not rag_context:
        return []
    try:
        from src.export.citation_workflow import Reference
    except Exception as e:
        _log.warning("Reference import fail: %s", e)
        return []
    pmids = re.findall(r"PMID:(\d+)", rag_context)
    refs: List = []
    seen: set = set()
    for pmid in pmids:
        if pmid in seen:
            continue
        seen.add(pmid)
        refs.append(Reference(pmid=pmid, title=f"PubMed {pmid}", citation_key=f"PMID{pmid}"))
    return refs


# ── IMRAD post-processing chain ──────────────────────────────────────────────
def post_process_imrad(draft: str, rag_context: str) -> Tuple[str, Dict]:
    """Language-clean + citation-numbering + citation-integrity + physician-review."""
    meta: Dict = {"steps": [], "warnings": []}

    before_len = len(draft)
    draft = strip_korean_prelude(draft)
    if len(draft) != before_len:
        meta["steps"].append(f"strip_korean_prelude: removed {before_len - len(draft)} chars")

    refs = hits_to_references(rag_context)
    meta["refs_count"] = len(refs)

    if refs:
        try:
            from src.export.citation_workflow import convert_pmid_inline_to_numbered, reference_list_markdown
            draft, ordered_pmid, n_converted = convert_pmid_inline_to_numbered(draft, refs)
            if n_converted:
                meta["steps"].append(f"pmid_to_numbered: {n_converted} PMIDs → [n]")
                meta["pmid_cited"] = [r.pmid for r in ordered_pmid]
                ref_block = "\n\n## References\n\n" + reference_list_markdown(ordered_pmid)
                if "## References" not in draft:
                    draft = draft.rstrip() + ref_block
        except Exception as e:
            meta["warnings"].append(f"pmid_to_numbered: {str(e)[:120]}")

    if refs and not any("pmid_to_numbered" in s for s in meta["steps"]):
        try:
            from src.export.citation_workflow import place_citations
            sections = {"manuscript": draft}
            new_secs, ordered = place_citations(sections, refs)
            draft = new_secs.get("manuscript", draft)
            meta["steps"].append(f"place_citations: {len(ordered)} refs cited")
            meta["cited_refs"] = [r.pmid for r in ordered]
        except Exception as e:
            meta["warnings"].append(f"place_citations: {str(e)[:120]}")

    try:
        from src.safety.citation_grounding import verify_citation_integrity
        rep = verify_citation_integrity(draft, refs="", check_dois=False, check_rag=False)
        meta["citation_check"] = {
            "ok": rep.ok,
            "orphan_citations": len(rep.orphan_citations),
            "orphan_references": len(rep.orphan_references),
            "summary": rep.summary[:200],
        }
    except Exception as e:
        meta["warnings"].append(f"citation_integrity: {str(e)[:120]}")

    try:
        from src.safety.physician_review import review_required
        needs, reasons = review_required(draft)
        meta["physician_review"] = {"needs": needs, "reasons": reasons[:5]}
    except Exception as e:
        meta["warnings"].append(f"physician_review: {str(e)[:120]}")

    return draft, meta


def enrich_imrad(draft: str, project: dict, user_msg: str) -> Tuple[str, Dict]:
    """Novelty section + figure legends inject."""
    meta: Dict = {"steps": [], "warnings": []}
    rs = project.get("research_state") or {}
    pico = rs.get("pico") or {}

    try:
        from src.research.novelty_checker import NoveltyChecker
        nc = NoveltyChecker()
        nov = nc.check(
            topic=project.get("title", "")[:120] or user_msg[:120],
            exposure=pico.get("I", "") or pico.get("E", ""),
            outcome=pico.get("O", ""),
            population=pico.get("P", ""),
            dataset=rs.get("dataset", "KYRBS"),
            design=rs.get("design", "cross-sectional"),
        )
        score = float(nov.get("novelty_score", 0) or 0)
        gap = nov.get("novelty_gap", "") or nov.get("gap_summary", "")
        block = (
            f"\n\n## Novelty and contribution\n\n"
            f"Novelty score: {score:.2f}/1.0 (based on PubMed prior-work scan).\n\n"
            f"{(gap or 'See gap analysis in supplementary materials.')[:600]}\n"
        )
        if "## 2. Methods" in draft:
            draft = draft.replace("## 2. Methods", block + "\n## 2. Methods", 1)
        elif "## Methods" in draft:
            draft = draft.replace("## Methods", block + "\n## Methods", 1)
        else:
            draft = draft.rstrip() + block
        meta["steps"].append(f"novelty: score={score:.2f}")
        meta["novelty_score"] = score
    except Exception as e:
        meta["warnings"].append(f"novelty: {str(e)[:120]}")

    try:
        from src.export.publication_figure_generator import generate_figures_for_paper
        stat_result = rs.get("stat_result") or {}
        if stat_result:
            try:
                figs = generate_figures_for_paper(
                    stat_result=stat_result,
                    safe_title=str(project.get("id", "paper"))[:40],
                ) or {}
                figs_made = list(figs.keys())
                meta["steps"].append(f"figures: {len(figs_made)} generated")
                meta["figures"] = figs_made
            except Exception as e:
                meta["warnings"].append(f"figure_gen: {str(e)[:120]}")
        figure_block = (
            "\n\n## Figure legends\n\n"
            "Figure 1. Forest plot — adjusted odds ratios (aOR) with 95% confidence intervals for the primary association across subgroups.\n\n"
            "Figure 2. Subgroup analyses — stratified by sex, school grade, and sleep duration.\n\n"
            "Figure 3. Sensitivity analyses — varying exposure threshold and covariate set.\n"
        )
        if "## Figure legends" not in draft:
            draft = draft.rstrip() + figure_block
            meta["steps"].append("figure_legends: appended")
    except Exception as e:
        meta["warnings"].append(f"figure_block: {str(e)[:120]}")

    return draft, meta


def autopilot_run(project: dict, user_msg: str):
    """Real autopilot — generator yielding status events, terminal event has manuscript_text.

    Each yield: {"stage", "status", "message", "data"?, "manuscript_text"?}
    Stages: pico → novelty → stat → write → polish → save

    No Streamlit calls inside. ez_home wraps each event with st.status / preview update.
    """
    rs = project.setdefault("research_state", {})
    pico = rs.get("pico") or {}
    topic = project.get("title", "") or user_msg[:120]

    yield {"stage": "pico", "status": "running",
            "message": f"📋 PICO 합의: {topic[:80]}"}

    # 1) Novelty
    try:
        from src.research.novelty_checker import NoveltyChecker
        nc = NoveltyChecker()
        nov = nc.check(
            topic=topic[:120],
            exposure=pico.get("I", "") or pico.get("E", ""),
            outcome=pico.get("O", ""),
            population=pico.get("P", ""),
            dataset=rs.get("dataset", "KYRBS"),
            design=rs.get("design", "cross-sectional"),
        )
        rs["novelty"] = nov
        score = float(nov.get("novelty_score", 0) or 0)
        yield {"stage": "novelty", "status": "done",
                "message": f"🔍 신규성 검토 완료 (score={score:.2f}/1.0)",
                "data": {"score": score}}
    except Exception as e:
        _log.warning("autopilot novelty fail: %s", e)
        yield {"stage": "novelty", "status": "skip",
                "message": f"⚠ novelty skip: {str(e)[:80]}"}

    # 2) Stat (survey-weighted if KYRBS/KNHANES + design columns present)
    stat_result = None
    try:
        from src.service.data import load_dataset
        from src.service.stats import analyze
        ds = rs.get("dataset", "KYRBS")
        year = rs.get("year")
        df, dmeta = load_dataset(ds, year=year)
        if df is None:
            yield {"stage": "stat", "status": "skip",
                    "message": f"⚠ 데이터 로드 실패: {dmeta.get('error','no data')[:80]}"}
        else:
            spec = rs.get("stat_spec") or {
                "design": "logistic",
                "outcome": pico.get("O", "M_SAD"),
                "exposure": pico.get("I", "") or pico.get("E", "F_CAFFEINE"),
                "covariates": ["AGE", "SEX", "GRADE"],
                "strata": "STRATA", "cluster": "CLUSTER", "weight": "W",
            }
            stat_result = analyze(spec, df=df)
            rs["stat_result"] = stat_result
            engine = stat_result.get("engine", "?") if isinstance(stat_result, dict) else "?"
            yield {"stage": "stat", "status": "done",
                    "message": f"📊 통계 완료 (engine={engine}, n_rows={len(df):,})",
                    "data": {"stat_result": stat_result}}
    except Exception as e:
        _log.warning("autopilot stat fail: %s", e)
        yield {"stage": "stat", "status": "skip",
                "message": f"⚠ 통계 skip: {str(e)[:80]}"}

    # 3) Writer — full IMRAD via paper_writer
    manuscript_text = ""
    try:
        from src.research.paper_writer import PaperWriter
        pw = PaperWriter()
        manuscript_text = pw.write_full(
            topic=topic,
            stat_result=stat_result or {},
            rag_pipeline=None,
            target_journal=rs.get("target_journal", ""),
        ) or ""
        rs["manuscript_text"] = manuscript_text
        yield {"stage": "write", "status": "done",
                "message": f"✍️ 초안 작성 완료 ({len(manuscript_text):,}자)",
                "manuscript_text": manuscript_text}
    except Exception as e:
        _log.warning("autopilot write fail: %s", e)
        yield {"stage": "write", "status": "fail",
                "message": f"⚠ 초안 작성 실패: {str(e)[:120]}"}

    # 4) Polish (post_process_imrad — citation/cleanup)
    if manuscript_text:
        try:
            from src.service.rag import retrieve_as_text_block
            rag_ctx = retrieve_as_text_block(topic + " " + user_msg, top_k=5)
            improved, meta = post_process_imrad(manuscript_text, rag_ctx)
            improved, meta2 = enrich_imrad(improved, project, user_msg)
            rs["manuscript_text"] = improved
            rs["post_meta"] = {**meta, "enrich": meta2}
            manuscript_text = improved
            yield {"stage": "polish", "status": "done",
                    "message": (f"🧹 인용 + 신규성 + 그림 캡션 통합 완료 "
                                  f"(refs={meta.get('refs_count', 0)})"),
                    "manuscript_text": improved}
        except Exception as e:
            _log.warning("autopilot polish fail: %s", e)
            yield {"stage": "polish", "status": "skip",
                    "message": f"⚠ polish skip: {str(e)[:80]}"}

    # 5) Save to working_paper_store
    try:
        from src.storage.working_paper_store import save as wps_save
        wps_save(project_id=project.get("id"),
                  owner_email=project.get("owner_email", ""),
                  manuscript_text=manuscript_text,
                  meta={"title": topic, "stage": "autopilot_done"})
        yield {"stage": "save", "status": "done",
                "message": "💾 저장 완료 — 우측 프리뷰 + 재세션 복원 활성"}
    except Exception as e:
        _log.warning("autopilot save fail: %s", e)
        yield {"stage": "save", "status": "skip",
                "message": f"⚠ 저장 skip: {str(e)[:80]}"}

    # Terminal — caller can read .manuscript_text from project["research_state"]


def generate_figure(project: dict, figure_type: str) -> Optional[Tuple[bytes, str]]:
    """Generate one publication figure from research_state.stat_result. Returns (png_bytes, caption)."""
    try:
        from src.export.publication_figure_generator import (
            make_forest_plot, make_subgroup_forest, make_coefficient_plot,
            make_roc_curve, make_prevalence_bar, make_table1_image, make_table2_image,
        )
        from pathlib import Path
        rs = project.get("research_state") or {}
        stat_result = rs.get("stat_result") or {}
        if not stat_result:
            return None
        out_dir = Path(f"data/drafts/figures/{project.get('id', 'tmp')}")
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
        if len(result) >= 4:
            png_bytes, _svg_path, _png_path, caption = result[:4]
        else:
            png_bytes = result[0]
            caption = ""
        return png_bytes, caption
    except Exception as e:
        _log.warning("generate_figure(%s) fail: %s", figure_type, e)
        return None
