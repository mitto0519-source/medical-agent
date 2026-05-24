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
    """논문 텍스트 → 섹션 인식 청크 리스트 [{text, metadata}, ...]."""
    from src.ingestion.chunker import TextChunker

    base = dict(base_meta or {})
    text = (text or "").strip()
    if not text:
        return []

    # 1) 섹션 분할: 본문이 길면 paper_ingester 섹션분할, 짧으면 구조화 초록
    sections: Dict[str, str] = {}
    if structured and len(text) > 600:
        try:
            from src.ingestion.paper_ingester import _split_into_sections
            sections = {k: v for k, v in (_split_into_sections(text) or {}).items() if v and v.strip()}
        except Exception:
            sections = {}
    if not sections:
        sections = _split_structured_abstract(text)

    # 2) 섹션별 메타 부여 + 청킹 (짧은 섹션은 통째로 = 의미단위 보존)
    out: List[dict] = []
    tc = TextChunker(chunk_size=700, overlap=80)
    for sec, body in sections.items():
        body = (body or "").strip()
        if len(body) < 20:
            continue
        meta = {
            **base,
            "section": sec,
            "rhetorical_role": _ROLE_BY_SECTION.get(sec, "other"),
            "citation_density": _citation_density(body),
            "statistical_method": _detect(body, _STAT_METHODS),
            "evidence_level": _detect(body, _EVIDENCE) or base.get("evidence_level", ""),
        }
        if len(body) <= 900:
            out.append({"text": body, "metadata": meta})
        else:
            out.extend(tc.chunk(body, metadata=meta))
    return out
