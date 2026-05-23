"""Open Evidence Reader — 오픈 에비던스 소스 통합 검색

지원 소스
---------
PubMed          — 초록 + 메타데이터 (NCBI E-utilities)
PubMed Central  — 전문 오픈액세스 논문 (PMC OAI)
Europe PMC      — PMC + Preprints + Patents
Semantic Scholar — AI 기반 논문 검색 (무료 API)
arXiv           — Preprint (의생명 포함)
bioRxiv/medRxiv — 바이오/의학 preprint
CrossRef        — DOI → 메타데이터
Unpaywall       — DOI → 오픈액세스 PDF URL
"""

import time
import requests
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

HEADERS = {"User-Agent": "MedicalAgent/1.0 (research; contact: research@example.com)"}

_SS_KEY = None  # Semantic Scholar API key (optional, set via SEMANTIC_SCHOLAR_API_KEY)


def _get_with_retry(url: str, params: dict, headers: dict, timeout: int = 20,
                    max_retries: int = 3) -> requests.Response:
    """GET 요청 with 429/503 지수 백오프 재시도."""
    import os
    h = dict(headers)
    ss_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")
    if ss_key and "semanticscholar" in url:
        h["x-api-key"] = ss_key

    delay = 2.0
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, params=params, headers=h, timeout=timeout)
            if resp.status_code == 429:
                wait = delay * (2 ** attempt)
                _log.warning("429 rate limit (%s), %.1fs 후 재시도 (%d/%d)", url, wait, attempt + 1, max_retries)
                time.sleep(wait)
                continue
            if resp.status_code in (503, 502):
                time.sleep(delay)
                continue
            return resp
        except requests.Timeout:
            _log.warning("Timeout (%s), 재시도 %d/%d", url, attempt + 1, max_retries)
            time.sleep(delay)
    # 마지막 시도
    return requests.get(url, params=params, headers=h, timeout=timeout)


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------

def search_pubmed(query: str, max_results: int = 20) -> List[Dict]:
    """PubMed 검색 → 초록 포함 결과 반환."""
    base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

    search = requests.get(f"{base}/esearch.fcgi", params={
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json",
        "sort": "relevance",
    }, headers=HEADERS, timeout=20)
    search.raise_for_status()
    pmids = search.json()["esearchresult"]["idlist"]
    if not pmids:
        return []

    time.sleep(0.35)
    fetch = requests.get(f"{base}/esummary.fcgi", params={
        "db": "pubmed", "id": ",".join(pmids), "retmode": "json",
    }, headers=HEADERS, timeout=20)
    fetch.raise_for_status()
    summary = fetch.json().get("result", {})

    results = []
    for pmid in pmids:
        item = summary.get(pmid, {})
        results.append({
            "source": "pubmed",
            "pmid": pmid,
            "title": item.get("title", ""),
            "authors": [a.get("name", "") for a in item.get("authors", [])],
            "journal": item.get("fulljournalname", ""),
            "year": item.get("pubdate", "")[:4],
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            "doi": next((id_["value"] for id_ in item.get("articleids", []) if id_["idtype"] == "doi"), ""),
        })
    return results


# ---------------------------------------------------------------------------
# Semantic Scholar (무료 API, 매우 강력)
# ---------------------------------------------------------------------------

def search_semantic_scholar(query: str, max_results: int = 10,
                            fields: str = "title,authors,year,abstract,openAccessPdf,citationCount,journal") -> List[Dict]:
    """Semantic Scholar API 검색 (무료, 오픈액세스 PDF 링크 포함). 429 자동 재시도."""
    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    resp = _get_with_retry(url, params={
        "query": query,
        "limit": max_results,
        "fields": fields,
    }, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    papers = resp.json().get("data", [])

    results = []
    for p in papers:
        oa_pdf = (p.get("openAccessPdf") or {}).get("url", "")
        results.append({
            "source": "semantic_scholar",
            "paper_id": p.get("paperId", ""),
            "title": p.get("title", ""),
            "authors": [a.get("name", "") for a in p.get("authors", [])],
            "year": str(p.get("year", "")),
            "abstract": p.get("abstract", ""),
            "journal": (p.get("journal") or {}).get("name", ""),
            "citation_count": p.get("citationCount", 0),
            "open_access_pdf": oa_pdf,
            "url": f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}",
        })
    return results


# ---------------------------------------------------------------------------
# Europe PMC
# ---------------------------------------------------------------------------

def search_europe_pmc(query: str, max_results: int = 10) -> List[Dict]:
    """Europe PMC 검색 (preprint 포함)."""
    resp = requests.get("https://www.ebi.ac.uk/europepmc/webservices/rest/search", params={
        "query": query,
        "resultType": "core",
        "pageSize": max_results,
        "format": "json",
        "sort": "RELEVANCE",
    }, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    items = resp.json().get("resultList", {}).get("result", [])

    results = []
    for item in items:
        results.append({
            "source": "europe_pmc",
            "pmid": item.get("pmid", ""),
            "pmcid": item.get("pmcid", ""),
            "title": item.get("title", ""),
            "authors": item.get("authorString", ""),
            "journal": item.get("journalTitle", ""),
            "year": str(item.get("pubYear", "")),
            "abstract": item.get("abstractText", ""),
            "is_open_access": item.get("isOpenAccess") == "Y",
            "url": f"https://europepmc.org/article/{item.get('source', 'MED')}/{item.get('id', '')}",
        })
    return results


# ---------------------------------------------------------------------------
# Unpaywall — DOI → open access PDF
# ---------------------------------------------------------------------------

def get_open_access_pdf(doi: str, email: str = "research@example.com") -> Optional[str]:
    """DOI로 오픈액세스 PDF URL 조회."""
    if not doi:
        return None
    try:
        resp = requests.get(
            f"https://api.unpaywall.org/v2/{doi}",
            params={"email": email},
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            best = data.get("best_oa_location") or {}
            return best.get("url_for_pdf") or best.get("url")
    except Exception as exc:
        _log.warning("Unpaywall 조회 실패: %s", exc, exc_info=True)
    return None


# ---------------------------------------------------------------------------
# CrossRef — DOI → full metadata
# ---------------------------------------------------------------------------

def get_crossref_metadata(doi: str) -> Dict:
    """DOI로 CrossRef에서 메타데이터 조회."""
    try:
        resp = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers=HEADERS, timeout=15,
        )
        if resp.status_code == 200:
            msg = resp.json().get("message", {})
            return {
                "title": (msg.get("title") or [""])[0],
                "journal": (msg.get("container-title") or [""])[0],
                "year": str((msg.get("published", {}).get("date-parts") or [[""]])[0][0]),
                "doi": doi,
                "url": msg.get("URL", ""),
                "abstract": msg.get("abstract", ""),
            }
    except Exception as exc:
        _log.warning("CrossRef 메타데이터 조회 실패: %s", exc, exc_info=True)
    return {}


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------

class EvidenceReader:
    """오픈 에비던스 통합 검색기.

    사용법:
        reader = EvidenceReader()
        results = reader.search("breast density mammography AI", sources=["pubmed", "semantic_scholar"])
        full_text = reader.fetch_full_text(doi="10.xxxx/xxxx")
    """

    def search(
        self,
        query: str,
        max_per_source: int = 10,
        sources: Optional[List[str]] = None,
        open_access_only: bool = False,
    ) -> List[Dict]:
        """멀티소스 통합 검색.

        sources: ["pubmed", "semantic_scholar", "europe_pmc"]
                 None이면 전부 검색
        """
        if sources is None:
            sources = ["pubmed", "semantic_scholar", "europe_pmc"]

        all_results = []

        if "pubmed" in sources:
            try:
                results = search_pubmed(query, max_results=max_per_source)
                all_results.extend(results)
                time.sleep(0.35)
            except Exception as e:
                _log.warning("[PubMed 오류] %s", e)

        if "semantic_scholar" in sources:
            try:
                results = search_semantic_scholar(query, max_results=max_per_source)
                if open_access_only:
                    results = [r for r in results if r.get("open_access_pdf")]
                all_results.extend(results)
                time.sleep(0.5)
            except Exception as e:
                _log.warning("[Semantic Scholar 오류] %s", e)

        if "europe_pmc" in sources:
            try:
                results = search_europe_pmc(query, max_results=max_per_source)
                if open_access_only:
                    results = [r for r in results if r.get("is_open_access")]
                all_results.extend(results)
            except Exception as e:
                _log.warning("[Europe PMC 오류] %s", e)

        # 중복 제거 (제목 기준)
        seen_titles = set()
        deduped = []
        for r in all_results:
            t = r.get("title", "").lower().strip()[:80]
            if t and t not in seen_titles:
                seen_titles.add(t)
                deduped.append(r)

        return deduped

    def fetch_full_text(self, doi: Optional[str] = None,
                        pmid: Optional[str] = None) -> Optional[str]:
        """DOI 또는 PMID로 전문 텍스트 가져오기 (오픈액세스 한정)."""
        from src.ingestion.web_reader import WebReader
        web = WebReader()

        if doi:
            pdf_url = get_open_access_pdf(doi)
            if pdf_url:
                try:
                    doc = web.read(pdf_url)
                    return doc["full_text"]
                except Exception:
                    pass

        if pmid:
            try:
                doc = web.read(f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/")
                return doc["full_text"]
            except Exception:
                pass

        return None

    def search_and_summarise(self, query: str, n: int = 5) -> str:
        """검색 결과를 텍스트 요약으로 반환 (RAG 컨텍스트 삽입용)."""
        results = [r for r in self.search(query, max_per_source=n)[:n*2] if r is not None]
        lines = [f"EVIDENCE SEARCH: '{query}'\n"]
        for i, r in enumerate(results, 1):
            title = r.get("title", "No title")
            year = r.get("year", "")
            journal = r.get("journal", "")
            abstract = (r.get("abstract") or "")[:300]
            lines.append(f"{i}. {title} ({journal}, {year})")
            if abstract:
                lines.append(f"   Abstract: {abstract}...")
            if r.get("open_access_pdf"):
                lines.append(f"   PDF: {r['open_access_pdf']}")
            lines.append("")
        return "\n".join(lines)
