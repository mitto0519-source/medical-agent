"""Citation Manager — Vancouver 형식 인용 관리 + PubMed/CrossRef 조회.

기능:
  - PubMed PMID / DOI → 메타데이터 자동 조회
  - Vancouver 형식 포맷팅 (JKMS 스타일)
  - 참고문헌 목록 누적 관리 + 중복 제거
  - 논문 텍스트에서 [1], [2] 인라인 번호 매핑
  - JSON/BibTeX 내보내기
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PUBMED_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
_CROSSREF_BASE = "https://api.crossref.org/works"


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class Citation:
    key: str                        # 고유 식별자 (PMID, DOI, or auto)
    authors: List[str] = field(default_factory=list)
    title: str = ""
    journal: str = ""
    year: int = 0
    volume: str = ""
    issue: str = ""
    pages: str = ""
    doi: str = ""
    pmid: str = ""
    abstract: str = ""

    def format_vancouver(self, index: int) -> str:
        """Vancouver 스타일 참고문헌 포맷 (ICMJE 기준)."""
        if len(self.authors) > 6:
            author_str = ", ".join(self.authors[:6]) + ", et al"
        elif self.authors:
            author_str = ", ".join(self.authors)
        else:
            author_str = "Unknown"

        parts = [f"{index}. {author_str}."]
        if self.title:
            parts.append(f" {self.title.rstrip('.')}.")
        if self.journal:
            parts.append(f" {self.journal}.")
        if self.year:
            parts.append(f" {self.year}")
        if self.volume:
            parts.append(f";{self.volume}")
        if self.issue:
            parts.append(f"({self.issue})")
        if self.pages:
            parts.append(f":{self.pages}")
        if self.doi:
            parts.append(f". doi:{self.doi}")
        return "".join(parts).strip()

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------------------
# CitationManager
# ---------------------------------------------------------------------------

class CitationManager:
    """논문 참고문헌 목록 관리자.

    Usage:
        cm = CitationManager()
        c = cm.lookup_pmid("12345678")
        c = cm.lookup_doi("10.1234/example")
        cm.add(c)
        refs = cm.format_all()        # ["1. Author et al. ...", ...]
        text = cm.inject_numbers(text) # [Author, YYYY] → [1]
    """

    def __init__(self, cache_path: str | None = "data/citation_cache.json"):
        self._refs: Dict[str, Citation] = {}   # key → Citation
        self._order: List[str] = []            # insertion order → numbering
        self._cache_path = Path(cache_path) if cache_path else None
        self._cache: Dict[str, dict] = {}
        self._load_cache()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, citation: Citation) -> int:
        """참고문헌 추가. 중복이면 기존 번호 반환. Returns 1-based index."""
        if citation.key in self._refs:
            return self._order.index(citation.key) + 1
        self._refs[citation.key] = citation
        self._order.append(citation.key)
        return len(self._order)

    def add_from_dict(self, data: dict) -> Citation:
        """딕셔너리에서 Citation 생성 후 추가."""
        key = data.get("pmid") or data.get("doi") or data.get("key") or f"ref_{len(self._refs)}"
        c = Citation(
            key=key,
            authors=data.get("authors", []),
            title=data.get("title", ""),
            journal=data.get("journal", ""),
            year=int(data.get("year", 0)),
            volume=str(data.get("volume", "")),
            issue=str(data.get("issue", "")),
            pages=str(data.get("pages", "")),
            doi=data.get("doi", ""),
            pmid=data.get("pmid", ""),
            abstract=data.get("abstract", ""),
        )
        self.add(c)
        return c

    def lookup_pmid(self, pmid: str) -> Optional[Citation]:
        """PubMed PMID로 메타데이터 조회."""
        cache_key = f"pmid:{pmid}"
        if cache_key in self._cache:
            return Citation(**self._cache[cache_key])
        try:
            import urllib.request
            url = (
                f"{_PUBMED_BASE}/efetch.fcgi"
                f"?db=pubmed&id={pmid}&retmode=xml&rettype=abstract"
            )
            with urllib.request.urlopen(url, timeout=10) as r:
                xml = r.read().decode("utf-8")
            c = self._parse_pubmed_xml(xml, pmid)
            if c:
                self._cache[cache_key] = asdict(c)
                self._save_cache()
            return c
        except Exception as e:
            _log.warning("PubMed 조회 실패 (PMID=%s): %s", pmid, e)
            return None

    def lookup_doi(self, doi: str) -> Optional[Citation]:
        """CrossRef DOI로 메타데이터 조회."""
        cache_key = f"doi:{doi}"
        if cache_key in self._cache:
            return Citation(**self._cache[cache_key])
        try:
            import urllib.request
            url = f"{_CROSSREF_BASE}/{doi}"
            req = urllib.request.Request(url, headers={"User-Agent": "MedicalAgent/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read().decode("utf-8"))
            c = self._parse_crossref(data.get("message", {}), doi)
            if c:
                self._cache[cache_key] = asdict(c)
                self._save_cache()
            return c
        except Exception as e:
            _log.warning("CrossRef 조회 실패 (DOI=%s): %s", doi, e)
            return None

    def search_pubmed(self, query: str, max_results: int = 5) -> List[Citation]:
        """PubMed 키워드 검색 → Citation 목록."""
        try:
            import urllib.request, urllib.parse
            search_url = (
                f"{_PUBMED_BASE}/esearch.fcgi"
                f"?db=pubmed&term={urllib.parse.quote(query)}&retmax={max_results}&retmode=json"
            )
            with urllib.request.urlopen(search_url, timeout=10) as r:
                result = json.loads(r.read())
            ids = result.get("esearchresult", {}).get("idlist", [])
            citations = []
            for pmid in ids:
                c = self.lookup_pmid(pmid)
                if c:
                    citations.append(c)
                time.sleep(0.34)  # NCBI rate limit: 3/sec
            return citations
        except Exception as e:
            _log.warning("PubMed 검색 실패 (%s): %s", query, e)
            return []

    def format_all(self) -> List[str]:
        """전체 참고문헌 목록 (Vancouver 형식) 반환."""
        lines = []
        for i, key in enumerate(self._order, start=1):
            c = self._refs[key]
            lines.append(c.format_vancouver(i))
        return lines

    def format_text(self) -> str:
        """References 섹션 전체 텍스트."""
        return "\n".join(self.format_all())

    def get_by_index(self, index: int) -> Optional[Citation]:
        """1-based index로 Citation 조회."""
        if 1 <= index <= len(self._order):
            return self._refs[self._order[index - 1]]
        return None

    def inject_numbers(self, text: str) -> str:
        """논문 텍스트의 [Author, YYYY] 패턴을 [N] 번호로 교체.

        예: [Kim et al., 2020] → [3]
        """
        def replace(m):
            raw = m.group(0)
            for i, key in enumerate(self._order, start=1):
                c = self._refs[key]
                if str(c.year) in raw:
                    for auth in c.authors[:1]:
                        surname = auth.split()[-1] if auth else ""
                        if surname and surname.lower() in raw.lower():
                            return f"[{i}]"
            return raw

        pattern = r"\[[A-Z][^\]]{3,50},?\s*\d{4}\]"
        return re.sub(pattern, replace, text)

    def clear(self):
        self._refs.clear()
        self._order.clear()

    def to_list(self) -> List[dict]:
        return [self._refs[k].to_dict() for k in self._order]

    def export_bibtex(self) -> str:
        """BibTeX 형식으로 내보내기."""
        lines = []
        for key in self._order:
            c = self._refs[key]
            bkey = re.sub(r"\W+", "", key)
            first_author = c.authors[0].split()[-1] if c.authors else "Unknown"
            entry_key = f"{first_author}{c.year}"
            lines.append(f"@article{{{entry_key},")
            lines.append(f"  author = {{{' and '.join(c.authors)}}},")
            if c.title:
                lines.append(f"  title = {{{c.title}}},")
            if c.journal:
                lines.append(f"  journal = {{{c.journal}}},")
            if c.year:
                lines.append(f"  year = {{{c.year}}},")
            if c.volume:
                lines.append(f"  volume = {{{c.volume}}},")
            if c.pages:
                lines.append(f"  pages = {{{c.pages}}},")
            if c.doi:
                lines.append(f"  doi = {{{c.doi}}},")
            lines.append("}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_pubmed_xml(self, xml: str, pmid: str) -> Optional[Citation]:
        try:
            from xml.etree import ElementTree as ET
            root = ET.fromstring(xml)
            article = root.find(".//PubmedArticle/MedlineCitation/Article")
            if article is None:
                return None

            title_el = article.find("ArticleTitle")
            title = title_el.text or "" if title_el is not None else ""

            journal_el = article.find("Journal/Title")
            journal = journal_el.text or "" if journal_el is not None else ""

            year_el = article.find("Journal/JournalIssue/PubDate/Year")
            year = int(year_el.text) if year_el is not None and year_el.text else 0

            vol_el = article.find("Journal/JournalIssue/Volume")
            volume = vol_el.text or "" if vol_el is not None else ""

            issue_el = article.find("Journal/JournalIssue/Issue")
            issue = issue_el.text or "" if issue_el is not None else ""

            pages_el = article.find("Pagination/MedlinePgn")
            pages = pages_el.text or "" if pages_el is not None else ""

            authors = []
            for auth_el in article.findall("AuthorList/Author"):
                last = auth_el.findtext("LastName", "")
                fore = auth_el.findtext("ForeName", "")
                initials = auth_el.findtext("Initials", "")
                name = f"{last} {initials}".strip() if initials else last
                if name:
                    authors.append(name)

            doi = ""
            for id_el in root.findall(".//ArticleId"):
                if id_el.get("IdType") == "doi":
                    doi = id_el.text or ""

            return Citation(
                key=f"pmid:{pmid}",
                authors=authors,
                title=title,
                journal=journal,
                year=year,
                volume=volume,
                issue=issue,
                pages=pages,
                doi=doi,
                pmid=pmid,
            )
        except Exception as e:
            _log.warning("PubMed XML 파싱 실패: %s", e)
            return None

    def _parse_crossref(self, msg: dict, doi: str) -> Optional[Citation]:
        try:
            authors = []
            for a in msg.get("author", []):
                name = f"{a.get('family', '')} {a.get('given', '')[:1]}".strip()
                if name:
                    authors.append(name)

            title_list = msg.get("title", [])
            title = title_list[0] if title_list else ""

            journal_list = msg.get("container-title", [])
            journal = journal_list[0] if journal_list else ""

            date_parts = msg.get("published-print", msg.get("published-online", {})).get("date-parts", [[0]])
            year = date_parts[0][0] if date_parts and date_parts[0] else 0

            volume = str(msg.get("volume", ""))
            issue = str(msg.get("issue", ""))
            pages = str(msg.get("page", ""))

            return Citation(
                key=f"doi:{doi}",
                authors=authors,
                title=title,
                journal=journal,
                year=year,
                volume=volume,
                issue=issue,
                pages=pages,
                doi=doi,
            )
        except Exception as e:
            _log.warning("CrossRef 파싱 실패: %s", e)
            return None

    # ------------------------------------------------------------------
    # Cache persistence
    # ------------------------------------------------------------------

    def _load_cache(self):
        if self._cache_path and self._cache_path.exists():
            try:
                self._cache = json.loads(self._cache_path.read_text(encoding="utf-8"))
            except Exception:
                self._cache = {}

    def _save_cache(self):
        if self._cache_path:
            try:
                self._cache_path.parent.mkdir(parents=True, exist_ok=True)
                self._cache_path.write_text(
                    json.dumps(self._cache, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception as e:
                _log.warning("citation cache 저장 실패: %s", e)
