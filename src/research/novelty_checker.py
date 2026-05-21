"""Novelty Checker — PubMed 검색 + 규칙기반 유사도 평가 + LLM 복합 검증"""

import json
import time
from typing import Dict, List, Tuple
import requests
import os
from src.llm import get_llm_client
from src.config.logging_config import get_logger

_log = get_logger(__name__)

BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

# Weighted dimensions for similarity scoring
_WEIGHTS = {
    "exposure": 0.30,
    "outcome": 0.30,
    "population": 0.20,
    "dataset": 0.10,
    "design": 0.10,
}

_DATASET_KEYWORDS: Dict[str, List[str]] = {
    "KYRBS": ["kyrbs", "korea youth risk behavior", "청소년건강행태", "youth risk behavior survey"],
    "KNHANES": ["knhanes", "korea national health", "국민건강영양조사", "national health and nutrition"],
    "NHIS": ["nhis", "national health insurance", "건강보험공단"],
    "KDCA": ["kdca", "korea disease control", "질병관리청"],
}


# ──────────────────────────────────────────────────────────────────────
# PubMed helpers
# ──────────────────────────────────────────────────────────────────────

def _pubmed_request(url: str, params: dict, retries: int = 3) -> requests.Response:
    """PubMed API 요청 — 일시적 오류 시 지수 백오프 재시도."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            if attempt == retries - 1:
                raise
            time.sleep(2 ** attempt)
        except requests.HTTPError as e:
            if resp.status_code == 429:  # rate limit
                time.sleep(5 * (attempt + 1))
            else:
                raise


def _pubmed_search(query: str, max_results: int = 30) -> List[str]:
    resp = _pubmed_request(f"{BASE}/esearch.fcgi", {
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json",
    })
    return resp.json()["esearchresult"]["idlist"]


def _fetch_abstracts(pmids: List[str]) -> str:
    if not pmids:
        return ""
    resp = _pubmed_request(f"{BASE}/efetch.fcgi", {
        "db": "pubmed", "id": ",".join(pmids),
        "rettype": "abstract", "retmode": "text",
    })
    return resp.text


def _fetch_papers_structured(pmids: List[str]) -> List[Dict]:
    """PubMed PMIDs를 구조화된 논문 dict 목록으로 반환."""
    if not pmids:
        return []
    resp = requests.get(f"{BASE}/efetch.fcgi", params={
        "db": "pubmed", "id": ",".join(pmids),
        "rettype": "xml", "retmode": "xml",
    }, timeout=30)
    resp.raise_for_status()

    import xml.etree.ElementTree as ET
    root = ET.fromstring(resp.text)
    papers = []
    for article in root.findall(".//PubmedArticle"):
        try:
            title_el = article.find(".//ArticleTitle")
            title = title_el.text or "" if title_el is not None else ""

            abstract_parts = article.findall(".//AbstractText")
            abstract = " ".join(
                (el.text or "") for el in abstract_parts if el.text
            )

            year_el = article.find(".//PubDate/Year")
            year = year_el.text if year_el is not None else ""

            pmid_el = article.find(".//PMID")
            pmid = pmid_el.text if pmid_el is not None else ""

            journal_el = article.find(".//Journal/Title")
            journal = journal_el.text if journal_el is not None else ""

            authors = []
            for auth in article.findall(".//Author")[:5]:
                last = auth.findtext("LastName", "")
                fore = auth.findtext("ForeName", "")
                if last:
                    authors.append(f"{last} {fore}".strip())

            doi_el = article.find(".//ArticleId[@IdType='doi']")
            doi = doi_el.text if doi_el is not None else ""

            papers.append({
                "pmid": pmid, "title": title, "abstract": abstract,
                "year": year, "journal": journal, "authors": authors, "doi": doi,
            })
        except Exception:
            continue
    return papers


# ──────────────────────────────────────────────────────────────────────
# Rule-based similarity engine
# ──────────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> List[str]:
    import re
    tokens = re.split(r"[\s,;/()\-]+", text.lower())
    return [t for t in tokens if len(t) > 2]


def _compute_dimension_similarity(proposed_value: str, paper_text: str) -> Tuple[float, str]:
    """Return (score 0-1, match_level: 'exact'|'high'|'partial'|'low'|'none')."""
    if not proposed_value.strip():
        return 0.0, "none"
    paper_lower = paper_text.lower()
    if proposed_value.lower() in paper_lower:
        return 1.0, "exact"
    tokens = _tokenize(proposed_value)
    if not tokens:
        return 0.0, "none"
    matched = sum(1 for t in tokens if t in paper_lower)
    ratio = matched / len(tokens)
    if ratio >= 0.7:
        return 0.8, "high"
    elif ratio >= 0.4:
        return 0.5, "partial"
    elif ratio >= 0.2:
        return 0.2, "low"
    return 0.0, "none"


def _detect_dataset(paper_text: str) -> List[str]:
    text_lower = paper_text.lower()
    found = []
    for ds_name, keywords in _DATASET_KEYWORDS.items():
        if any(kw.lower() in text_lower for kw in keywords):
            found.append(ds_name)
    return found


def _rule_based_similarity(
    proposed_exposure: str,
    proposed_outcome: str,
    proposed_population: str,
    proposed_dataset: str,
    proposed_design: str,
    paper: Dict,
) -> Dict:
    """규칙기반으로 제안 연구와 기존 논문 간 차원별 유사도 계산."""
    combined_text = f"{paper.get('title', '')} {paper.get('abstract', '')}"

    exp_score, exp_level = _compute_dimension_similarity(proposed_exposure, combined_text)
    out_score, out_level = _compute_dimension_similarity(proposed_outcome, combined_text)
    pop_score, pop_level = _compute_dimension_similarity(proposed_population, combined_text)

    paper_datasets = _detect_dataset(combined_text)
    ds_score = 1.0 if any(
        proposed_dataset.upper() == d.upper() for d in paper_datasets
    ) else 0.0
    ds_level = "exact" if ds_score == 1.0 else "none"

    design_score, design_level = _compute_dimension_similarity(proposed_design, combined_text)

    overall = (
        exp_score * _WEIGHTS["exposure"] +
        out_score * _WEIGHTS["outcome"] +
        pop_score * _WEIGHTS["population"] +
        ds_score * _WEIGHTS["dataset"] +
        design_score * _WEIGHTS["design"]
    )

    _dim_label = {
        "exposure": f"노출변수 '{proposed_exposure}'",
        "outcome": f"결과변수 '{proposed_outcome}'",
        "population": f"대상 '{proposed_population}'",
        "dataset": f"데이터셋 '{proposed_dataset}'",
        "design": f"연구설계 '{proposed_design}'",
    }

    similar_aspects = []
    different_aspects = []
    for dim, score, level, val in [
        ("exposure", exp_score, exp_level, proposed_exposure),
        ("outcome", out_score, out_level, proposed_outcome),
        ("population", pop_score, pop_level, proposed_population),
        ("dataset", ds_score, ds_level, proposed_dataset),
        ("design", design_score, design_level, proposed_design),
    ]:
        if not val.strip():
            continue
        entry = {
            "dimension": dim,
            "label": _dim_label[dim],
            "match_level": level,
            "score": round(score, 2),
        }
        if score >= 0.5:
            similar_aspects.append(entry)
        else:
            different_aspects.append(entry)

    from src.research.paper_writer import format_vancouver
    return {
        "paper_title": paper.get("title", ""),
        "pmid": paper.get("pmid", ""),
        "year": paper.get("year", ""),
        "journal": paper.get("journal", ""),
        "authors": paper.get("authors", []),
        "doi": paper.get("doi", ""),
        "vancouver_ref": format_vancouver(paper),
        "overall_similarity": round(overall, 3),
        "dimensions": {
            "exposure": {"score": round(exp_score, 2), "level": exp_level},
            "outcome": {"score": round(out_score, 2), "level": out_level},
            "population": {"score": round(pop_score, 2), "level": pop_level},
            "dataset": {"score": round(ds_score, 2), "level": ds_level, "detected": paper_datasets},
            "design": {"score": round(design_score, 2), "level": design_level},
        },
        "similar_aspects": similar_aspects,
        "different_aspects": different_aspects,
    }


def _aggregate_similarity(matrix: List[Dict]) -> Dict:
    """전체 논문에 대한 유사도 통계 집계."""
    if not matrix:
        return {
            "max": 0.0, "avg": 0.0,
            "high_similarity_count": 0,
            "very_high_similarity_count": 0,
            "total_papers": 0,
            "frequently_similar_dimensions": [],
        }
    scores = [p["overall_similarity"] for p in matrix]
    dim_sim_counts: Dict[str, int] = {}
    for p in matrix:
        for asp in p.get("similar_aspects", []):
            d = asp["dimension"]
            dim_sim_counts[d] = dim_sim_counts.get(d, 0) + 1
    threshold = max(len(matrix) * 0.25, 2)
    frequently_similar = [
        d for d, c in sorted(dim_sim_counts.items(), key=lambda x: -x[1])
        if c >= threshold
    ]
    return {
        "max": round(max(scores), 3),
        "avg": round(sum(scores) / len(scores), 3),
        "high_similarity_count": sum(1 for s in scores if s >= 0.5),
        "very_high_similarity_count": sum(1 for s in scores if s >= 0.7),
        "total_papers": len(matrix),
        "frequently_similar_dimensions": frequently_similar,
    }


def _compute_rule_score(stats: Dict) -> float:
    """규칙기반 신규성 점수 (0-10, 높을수록 신규)."""
    if stats["total_papers"] == 0:
        return 9.0
    base = round(10 * (1 - stats["avg"]), 1)
    if stats["max"] >= 0.8:
        base = min(base, 4.0)
    elif stats["max"] >= 0.7:
        base = min(base, 5.5)
    elif stats["max"] >= 0.5:
        base = min(base, 7.0)
    if stats["very_high_similarity_count"] >= 3:
        base = min(base, 4.5)
    return base


# ──────────────────────────────────────────────────────────────────────
# Main class
# ──────────────────────────────────────────────────────────────────────

class NoveltyChecker:
    """연구 주제의 신규성을 PubMed + 규칙기반 유사도 + LLM으로 복합 검증."""

    def __init__(self, api_key=None):
        self._client = get_llm_client(api_key=api_key)

    def check(
        self,
        topic: str,
        exposure: str,
        outcome: str,
        population: str = "",
        dataset: str = "KYRBS",
        design: str = "",
    ) -> Dict:
        """주제 신규성 복합 검증.

        Returns
        -------
        {
          "novelty_score": 0-10,
          "rule_based_score": 0-10,
          "is_novel": bool,
          "recommendation": "proceed / modify / abandon",
          "similarity_matrix": [per-paper breakdown],
          "similarity_stats": {max, avg, counts, ...},
          "overall_similar_aspects": [what matches existing lit],
          "overall_different_aspects": [what is genuinely new],
          "gap_identified": "...",
          "suggested_angle": "...",
          "llm_justification": "...",
          "similar_papers": [titles]
        }
        """
        # 1. PubMed 검색
        query = f'("{exposure}"[Title/Abstract]) AND ("{outcome}"[Title/Abstract])'
        if population:
            query += f' AND ("{population}"[Title/Abstract])'
        _log.info("PubMed 검색: %s...", query[:80])
        pmids = _pubmed_search(query, max_results=20)
        time.sleep(0.35)

        papers = []
        if pmids:
            papers = _fetch_papers_structured(pmids[:15])
            time.sleep(0.35)

        # 2. 규칙기반 유사도 매트릭스
        similarity_matrix = [
            _rule_based_similarity(
                proposed_exposure=exposure,
                proposed_outcome=outcome,
                proposed_population=population,
                proposed_dataset=dataset,
                proposed_design=design,
                paper=p,
            )
            for p in papers
        ]
        similarity_matrix.sort(key=lambda x: x["overall_similarity"], reverse=True)
        stats = _aggregate_similarity(similarity_matrix)
        rule_score = _compute_rule_score(stats)

        # 3. 집계 — 자주 유사/차별되는 차원
        dim_similar_cnt: Dict[str, int] = {}
        dim_diff_cnt: Dict[str, int] = {}
        for p in similarity_matrix[:8]:
            for asp in p.get("similar_aspects", []):
                d = asp["dimension"]
                dim_similar_cnt[d] = dim_similar_cnt.get(d, 0) + 1
            for asp in p.get("different_aspects", []):
                d = asp["dimension"]
                dim_diff_cnt[d] = dim_diff_cnt.get(d, 0) + 1

        _dim_labels = {
            "exposure": f"노출변수: {exposure}",
            "outcome": f"결과변수: {outcome}",
            "population": f"대상: {population}",
            "dataset": f"데이터셋: {dataset}",
            "design": f"연구설계: {design}",
        }
        agg_similar = [_dim_labels[d] for d, c in dim_similar_cnt.items() if c >= 2]
        agg_different = [_dim_labels[d] for d, c in dim_diff_cnt.items() if c >= 2]

        # 4. LLM 최종 평가
        top_txt = "\n\n".join(
            f"[{i+1}] {p['paper_title']} ({p['year']}, {p['journal']})\n"
            f"  전체 유사도: {p['overall_similarity']:.2f}\n"
            f"  유사 측면: {', '.join(a['label'] for a in p['similar_aspects']) or '없음'}\n"
            f"  차별 측면: {', '.join(a['label'] for a in p['different_aspects']) or '없음'}"
            for i, p in enumerate(similarity_matrix[:8])
        ) if similarity_matrix else "관련 논문 없음 — 매우 신규 주제."

        prompt = f"""You are a senior medical research methodologist evaluating research novelty.

PROPOSED STUDY:
- Topic: {topic}
- Exposure: {exposure}
- Outcome: {outcome}
- Population: {population}
- Dataset: {dataset}
- Design: {design or 'not specified'}

RULE-BASED SIMILARITY ANALYSIS:
- Papers found: {len(papers)}
- Average similarity: {stats['avg']:.2f} / 1.0
- Max similarity: {stats['max']:.2f} / 1.0
- High-similarity papers (≥0.5): {stats['high_similarity_count']}
- Very high-similarity (≥0.7): {stats['very_high_similarity_count']}
- Rule-based novelty score: {rule_score}/10
- Frequently similar dimensions: {', '.join(stats.get('frequently_similar_dimensions', [])) or 'none'}

TOP SIMILAR PAPERS WITH DIMENSION BREAKDOWN:
{top_txt}

Evaluate novelty. Your score must be consistent with the rule-based score ({rule_score}/10) — you may adjust ±2 points if you have strong justification. Return JSON ONLY:
{{
  "novelty_score": <integer 0-10>,
  "is_novel": <true if score >= 5>,
  "recommendation": "proceed / modify / abandon",
  "gap_identified": "<specific gap this study fills — 1 sentence>",
  "suggested_angle": "<concrete differentiation strategy — 1-2 sentences>",
  "llm_justification": "<why this score — 2-3 sentences citing specific papers>",
  "overall_similar_aspects": ["<shared with existing lit — be specific, list all>"],
  "overall_different_aspects": ["<what is genuinely new — be specific, list all>"],
  "similar_papers": ["<most similar paper title 1>", "<title 2>", ...]
}}"""

        try:
            raw = self._client.generate(prompt)
        except Exception as e:
            return {
                "novelty_score": int(rule_score),
                "rule_based_score": rule_score,
                "is_novel": rule_score >= 5,
                "recommendation": "manual_review",
                "gap_identified": "",
                "suggested_angle": "",
                "llm_justification": f"LLM 호출 실패 — 규칙기반 점수 사용: {e}",
                "overall_similar_aspects": agg_similar,
                "overall_different_aspects": agg_different,
                "similar_papers": [],
                "similarity_matrix": similarity_matrix,
                "similarity_stats": stats,
            }
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        try:
            llm_result = json.loads(raw)
        except Exception:
            llm_result = {
                "novelty_score": int(rule_score),
                "is_novel": rule_score >= 5,
                "recommendation": "manual_review",
                "gap_identified": "",
                "suggested_angle": "",
                "llm_justification": raw[:300],
                "overall_similar_aspects": agg_similar,
                "overall_different_aspects": agg_different,
                "similar_papers": [],
            }

        return {
            **llm_result,
            "rule_based_score": rule_score,
            "similarity_matrix": similarity_matrix,
            "similarity_stats": stats,
            "overall_similar_aspects": llm_result.get("overall_similar_aspects", agg_similar),
            "overall_different_aspects": llm_result.get("overall_different_aspects", agg_different),
            "found_papers": papers,  # 실제 PubMed 논문 dicts (pmid/title/authors/journal/year/doi 포함)
        }

    def search_papers(self, query: str, max_results: int = 10) -> List[Dict]:
        """PubMed 검색 → 구조화된 논문 dict 목록."""
        pmids = _pubmed_search(query, max_results=max_results)
        time.sleep(0.35)
        if not pmids:
            return []
        papers = _fetch_papers_structured(pmids)
        time.sleep(0.35)
        return papers
