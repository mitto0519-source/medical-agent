"""Hierarchical Chunker — 논문용 '구조 인식' 청킹 + 풍부한 메타데이터.

조언 #1(RAG 재설계): 일반 token chunk는 논문에서 실패한다("청크 20만개 넣어도 이상한 논문").
의미구조(섹션/하위) 단위로 나누고, 각 청크에 검색·필터에 쓸 메타를 붙인다:
  section, rhetorical_role, citation_density, statistical_method, evidence_level (+ base meta).
→ RAG가 "문장 검색기"가 아니라 "Methods의 logistic 회귀 블록만" 같은 구조 검색이 됨.
LLM 불필요 — 정규식/휴리스틱 (크레딧 0이어도 작동).
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

_STAT_METHODS = {
    "logistic regression": ["logistic", "odds ratio", "adjusted or", " aor", "95% ci"],
    "cox regression": ["cox", "hazard ratio", "proportional hazard"],
    "linear regression": ["linear regression", "beta coefficient", "β ="],
    "chi-square": ["chi-square", "chi square", "χ2", "pearson chi"],
    "t-test": ["t-test", "student's t", "independent t"],
    "anova": ["anova", "analysis of variance"],
    "mixed model": ["mixed model", "multilevel", "random effect", "gee", "generalized estimating"],
    "propensity": ["propensity", "iptw", "psm", "inverse probability"],
    "survey design": ["complex sample", "survey weight", "svyset", "svy:", "strata", "psu", "weighted"],
    "meta-analysis": ["meta-analysis", "pooled estimate", "forest plot", "i2 statistic", "heterogeneity"],
}
_EVIDENCE = {
    "rct": ["randomized", "randomised", "rct", "placebo", "double-blind"],
    "cohort": ["cohort", "prospective", "follow-up", "longitudinal"],
    "case-control": ["case-control", "case control"],
    "cross-sectional": ["cross-sectional", "cross sectional", "kyrbs", "knhanes", "nationwide survey"],
    "meta-analysis": ["meta-analysis", "systematic review", "prisma"],
}
_ROLE_BY_SECTION = {
    "abstract": "summary", "introduction": "background", "methods": "method",
    "results": "finding", "discussion": "interpretation", "conclusion": "interpretation",
    "title": "title",
}


def _citation_density(text: str) -> float:
    """100단어당 인용 개수 (대략). 0~5로 캡."""
    words = max(len(text.split()), 1)
    cites = len(re.findall(r"\[\d+\]|\(\w+ et al\.?,?\s*\d{4}\)|et al\.|\(\d{4}\)", text))
    return round(min(cites / words * 100, 5.0), 2)


def _detect(text: str, table: Dict[str, list]) -> str:
    low = text.lower()
    for label, kws in table.items():
        if any(k in low for k in kws):
            return label
    return ""


def _split_structured_abstract(text: str) -> Dict[str, str]:
    """구조화 초록(Background:/Methods:/Results:/Conclusion:) 분할. 없으면 abstract 단일."""
    secs: Dict[str, str] = {}
    pat = re.compile(
        r"(Background|Objectives?|Introduction|Aim[s]?|Methods?|Materials?|Results?|"
        r"Findings?|Conclusions?|Discussion)\s*[:：]", re.I)
    parts = pat.split(text)
    if len(parts) > 2:
        i = 1
        while i < len(parts) - 1:
            label = parts[i].lower().strip()
            body = parts[i + 1].strip()
            if label.startswith(("background", "objective", "introduction", "aim")):
                key = "introduction"
            elif label.startswith(("method", "material")):
                key = "methods"
            elif label.startswith(("result", "finding")):
                key = "results"
            else:
                key = "discussion"
            secs[key] = (secs.get(key, "") + " " + body).strip()
            i += 2
    if not secs:
        secs["abstract"] = text.strip()
    return secs


def chunk_paper(text: str, base_meta: Optional[dict] = None,
                structured: bool = True) -> List[dict]:
    """논문 텍스트 → 섹션 인식 청크 리스트 [{text, metadata}, ...].

    FIX-10 (2026-06-14): 5 키 → schema_v2.CHUNK_META_FIELDS 전체 추출.
    빈 필드는 null (거짓 채움 금지). 추출기는 regex/사전 기반 (빠르게, 보수적).
    """
    from src.ingestion.chunker import TextChunker

    base = dict(base_meta or {})
    text = (text or "").strip()
    if not text:
        return []

    # 1) 섹션 분할
    sections: Dict[str, str] = {}
    if structured and len(text) > 600:
        try:
            from src.ingestion.paper_ingester import _split_into_sections
            sections = {k: v for k, v in (_split_into_sections(text) or {}).items() if v and v.strip()}
        except Exception:
            sections = {}
    if not sections:
        sections = _split_structured_abstract(text)

    # 2) 섹션별 메타 부여 + 청킹
    out: List[dict] = []
    tc = TextChunker(chunk_size=700, overlap=80)
    for sec, body in sections.items():
        body = (body or "").strip()
        if len(body) < 20:
            continue
        meta = _build_full_meta(base, sec, body)
        if len(body) <= 900:
            out.append({"text": body, "metadata": meta})
        else:
            for chunk in tc.chunk(body, metadata=meta):
                # TextChunker가 metadata 복제할 때 deepcopy 안 하므로 명시 갱신
                out.append(chunk)
    return out


# ──────────────────────────────────────────────────────────────────────
# FIX-10 — extraction helpers (schema_v2 메타 채우기)
# ──────────────────────────────────────────────────────────────────────

import re as _re

# Effect measure detection
_EFFECT_PATTERNS = [
    (r"\baOR\s*[=:]?\s*([\d.]+)\b", "aOR"),
    (r"\bOR\s*[=:]?\s*([\d.]+)\b", "OR"),
    (r"\baHR\s*[=:]?\s*([\d.]+)\b", "aHR"),
    (r"\bHR\s*[=:]?\s*([\d.]+)\b", "HR"),
    (r"\baRR\s*[=:]?\s*([\d.]+)\b", "aRR"),
    (r"\bRR\s*[=:]?\s*([\d.]+)\b", "RR"),
    (r"\bIRR\s*[=:]?\s*([\d.]+)\b", "IRR"),
    (r"\bSMD\s*[=:]?\s*([\d.-]+)\b", "SMD"),
    (r"\bMD\s*[=:]?\s*([\d.-]+)\b", "MD"),
    (r"\bAUC\s*[=:]?\s*([\d.]+)\b", "AUC"),
]
_CI_PATTERN = _re.compile(r"95\s*%?\s*CI\s*[:=]?\s*\[?\s*([\d.]+)\s*[-–to,]\s*([\d.]+)", _re.IGNORECASE)
_P_PATTERN = _re.compile(r"\bp\s*[<>=]\s*(0?\.\d+)\b", _re.IGNORECASE)
_N_PATTERN = _re.compile(r"\bn\s*=\s*(\d[\d,]*)\b", _re.IGNORECASE)

# Study design detection
_DESIGN_PATTERNS = {
    "cross-sectional":   r"\bcross[-\s]?sectional\b",
    "cohort":            r"\bcohort\s+(?:study|design)\b",
    "case-control":      r"\bcase[-\s]?control\b",
    "randomized":        r"\brandomi[sz]ed\b.{0,30}\btrial\b",
    "systematic-review": r"\bsystematic\s+review\b",
    "meta-analysis":     r"\bmeta[-\s]?analysis\b",
    "target-trial":      r"\btarget[-\s]?trial\b",
    "MR":                r"\bmendelian[-\s]?randomi[sz]ation\b",
    "ITS":               r"\binterrupted[-\s]?time[-\s]?series\b",
}

# Discipline keyword detection (subset of schema_v2.DISCIPLINES)
_DISCIPLINE_KW = {
    "cardiology": ["cardiovascular", "heart failure", "coronary", "stroke", "myocardial"],
    "endocrinology": ["diabetes", "insulin", "thyroid", "obesity", "metabolic"],
    "psychiatry": ["depression", "anxiety", "PHQ", "GAD-7", "psychiatric", "mental health"],
    "nephrology": ["kidney", "renal", "eGFR", "dialysis", "CKD"],
    "neurology": ["stroke", "dementia", "alzheimer", "parkinson", "neurodegenerat"],
    "oncology": ["cancer", "tumor", "neoplasm", "carcinoma", "malignan"],
    "pulmonology": ["asthma", "COPD", "lung", "pulmonary"],
    "nutrition": ["dietary", "nutrition", "intake", "consumption", "food", "beverage"],
    "epidemiology": ["population", "prevalence", "incidence", "epidemiolog"],
    "pediatrics": ["adolescent", "child", "pediatric", "youth"],
    "preventive-medicine": ["screening", "prevention", "vaccination", "lifestyle"],
}


def _detect_effect(body: str) -> tuple[str | None, dict | None]:
    """Returns (effect_measure, {value, ci_low, ci_high, p} or None)."""
    for pat, measure in _EFFECT_PATTERNS:
        m = _re.search(pat, body, _re.IGNORECASE)
        if not m:
            continue
        est = {"value": float(m.group(1))}
        ci = _CI_PATTERN.search(body)
        if ci:
            try:
                est["ci_low"] = float(ci.group(1))
                est["ci_high"] = float(ci.group(2))
            except ValueError:
                pass
        p = _P_PATTERN.search(body)
        if p:
            try:
                est["p"] = float(p.group(1))
            except ValueError:
                pass
        return measure, est
    return None, None


def _detect_design(body: str) -> str | None:
    for label, pat in _DESIGN_PATTERNS.items():
        if _re.search(pat, body, _re.IGNORECASE):
            return label
    return None


def _detect_disciplines(body: str, base: dict) -> list:
    found = []
    text_lower = body.lower()
    for disc, kws in _DISCIPLINE_KW.items():
        if any(kw in text_lower for kw in kws):
            found.append(disc)
    # Inherit from base if no hit
    if not found and base.get("discipline"):
        return base["discipline"] if isinstance(base["discipline"], list) else [base["discipline"]]
    return found


def _detect_sample_size(body: str) -> int | None:
    m = _N_PATTERN.search(body)
    if not m:
        return None
    try:
        return int(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _extract_concept_cuis(body: str) -> dict:
    """ontology.extract_concepts → schema_v2 canonical axis별 CUI(or concept_id) list.

    FIX-10b: `axis` 우선 (canonical), `domain_id` fallback. axis 키는 schema_v2
    chunk meta 필드명과 매핑 (exposure / outcome / population / disease / mechanism / ...).
    """
    try:
        from src.knowledge.medical_ontology import get_ontology
        ont = get_ontology()
        concepts = ont.extract_concepts(body)
        out: dict = {}
        for c in concepts:
            axis_full = c.get("axis") or c.get("domain_id", "")
            axis_key = axis_full.lower().replace("d_", "")
            cid = c.get("cui") or c.get("concept_id") or c.get("label", "")
            if axis_key and cid:
                out.setdefault(axis_key, []).append(cid)
        return out
    except Exception:
        return {}


def _build_full_meta(base: dict, sec: str, body: str) -> dict:
    """schema_v2.CHUNK_META_FIELDS 전체를 채우는 메타 생성기."""
    measure, estimate = _detect_effect(body)
    design = _detect_design(body)
    disciplines = _detect_disciplines(body, base)
    n = _detect_sample_size(body)
    concept_buckets = _extract_concept_cuis(body)

    meta = {
        # provenance (from base)
        "pmid": base.get("pmid"),
        "pmcid": base.get("pmcid"),
        "doi": base.get("doi"),
        "journal": base.get("journal"),
        "year": base.get("year"),
        "section_char_span": base.get("section_char_span"),
        # section / rhetorical
        "section": sec,
        "subsection": base.get("subsection"),
        "rhetorical_role": _ROLE_BY_SECTION.get(sec, "other"),
        # study identification
        "study_design": design or base.get("study_design"),
        # extracted concepts (axis-keyed lists) — flat join for ChromaDB compat
        "population": ",".join(concept_buckets.get("population", [])) or None,
        "exposure":   ",".join(concept_buckets.get("exposure", [])) or None,
        "outcome":    ",".join(concept_buckets.get("outcome", [])) or None,
        "intervention": ",".join(concept_buckets.get("intervention", [])) or None,
        "biomarker":  ",".join(concept_buckets.get("biomarker_lab", [])) or None,
        "drug":       ",".join(concept_buckets.get("drug", [])) or None,
        "gene":       ",".join(concept_buckets.get("genetics", [])) or None,
        # statistical
        "statistical_method": _detect(body, _STAT_METHODS) or None,
        "effect_measure": measure,
        "effect_estimate": str(estimate) if estimate else None,
        "sample_size": n,
        "events": None,
        "follow_up": None,
        "covariates": None,
        # evidence
        "evidence_level": _detect(body, _EVIDENCE) or base.get("evidence_level") or None,
        "risk_of_bias": None,
        # cross-axis
        "discipline": ",".join(disciplines) if disciplines else None,
        "mechanism": ",".join(concept_buckets.get("mechanism", [])) or None,
        # text features
        "citation_density": _citation_density(body),
    }
    # Validate (warnings only, not enforcement — preserve current behavior)
    try:
        from src.knowledge.schema_v2 import validate_chunk_meta
        errs = validate_chunk_meta(meta)
        if errs:
            meta["_meta_warnings"] = ";".join(errs)[:200]
    except Exception:
        pass
    # Strip None values (ChromaDB metadata limits)
    return {k: v for k, v in meta.items() if v is not None}
