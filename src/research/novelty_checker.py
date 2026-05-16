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
