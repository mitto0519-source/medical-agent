"""Novelty Checker — PubMed 검색으로 연구 주제 신규성 검증"""

import time
from typing import Dict, List
import requests
import os
import anthropic


BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _pubmed_search(query: str, max_results: int = 30) -> List[str]:
    resp = requests.get(f"{BASE}/esearch.fcgi", params={
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json",
    }, timeout=30)
    resp.raise_for_status()
    return resp.json()["esearchresult"]["idlist"]


def _fetch_abstracts(pmids: List[str]) -> str:
    if not pmids:
        return ""
    resp = requests.get(f"{BASE}/efetch.fcgi", params={
        "db": "pubmed", "id": ",".join(pmids),
        "rettype": "abstract", "retmode": "text",
    }, timeout=30)
    resp.raise_for_status()
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
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "journal": journal,
                "authors": authors,
                "doi": doi,
            })
        except Exception:
            continue
    return papers


class NoveltyChecker:
    """연구 주제의 신규성을 PubMed 검색으로 확인."""

    def __init__(self, api_key=None):
        self._client = anthropic.Anthropic(
            api_key=api_key or os.environ.get("ANTHROPIC_API_KEY")
        )

    def check(self, topic: str, exposure: str, outcome: str,
              population: str = "") -> Dict:
        """주제 신규성 검증.

        Returns
        -------
        {
          "is_novel": bool,
          "novelty_score": 0-10,
          "similar_papers": [...],
          "gap_identified": "...",
          "recommendation": "proceed / modify / abandon",
          "suggested_angle": "..."
        }
        """
        query = f'("{exposure}"[Title/Abstract]) AND ("{outcome}"[Title/Abstract])'
        if population:
            query += f' AND ("{population}"[Title/Abstract])'

        print(f"  PubMed 검색: {query[:80]}...")
        pmids = _pubmed_search(query, max_results=20)
        time.sleep(0.35)

        abstracts = ""
        if pmids:
            abstracts = _fetch_abstracts(pmids[:10])
            time.sleep(0.35)

        prompt = f"""You are a medical research expert evaluating novelty.

PROPOSED RESEARCH TOPIC:
- Topic: {topic}
- Exposure/Intervention: {exposure}
- Outcome: {outcome}
- Population: {population}

EXISTING LITERATURE FROM PUBMED ({len(pmids)} papers found):
{abstracts[:5000] if abstracts else 'No papers found — highly novel topic.'}

Evaluate novelty and return JSON ONLY:
{{
  "is_novel": true/false,
  "novelty_score": 0-10,
  "similar_papers": ["title1", "title2", ...],
  "gap_identified": "specific gap this study can fill",
  "recommendation": "proceed / modify / abandon",
  "suggested_angle": "how to differentiate from existing work",
  "key_differences": ["what makes this study unique vs existing"]
}}
"""
        response = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=1000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[-1].text.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        import json
        try:
            return json.loads(raw)
        except Exception:
            return {"raw": raw, "is_novel": None, "recommendation": "manual_review"}

    def search_papers(self, query: str, max_results: int = 10) -> List[Dict]:
        """PubMed 검색 → 구조화된 논문 dict 목록 반환.

        NotebookLM 소스 추가 및 StorageManager에서 사용.
        """
        pmids = _pubmed_search(query, max_results=max_results)
        time.sleep(0.35)
        if not pmids:
            return []
        papers = _fetch_papers_structured(pmids)
        time.sleep(0.35)
        return papers
