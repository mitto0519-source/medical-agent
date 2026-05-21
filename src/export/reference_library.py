"""ReferenceLibrary — 논문 인용 관리 + EndNote XML / BibTeX 내보내기.

기능:
  - PubMed PMID → 완전 메타데이터 조회
  - 인용 목록을 논문별로 로컬 JSON 저장 (data/journals/references/)
  - Vancouver / APA / AMA 스타일 자동 포맷
  - EndNote XML (.xml) 내보내기 (Word + EndNote 호환)
  - BibTeX (.bib) 내보내기 (Zotero, Mendeley 호환)
  - Word 필드코드 형식 참고문헌 생성
"""
from __future__ import annotations

import json
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_REF_DIR = Path("data/journals/references")
_REF_DIR.mkdir(parents=True, exist_ok=True)

_PUBMED_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_PUBMED_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"


# ─── 데이터 모델 ─────────────────────────────────────────────────────────────

@dataclass
class Reference:
    pmid: str = ""
    doi: str = ""
    title: str = ""
    authors: List[str] = field(default_factory=list)
    journal: str = ""
    year: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""
    abstract: str = ""
    citation_key: str = ""    # BibTeX key (e.g. "cho2024smartphone")

    def __post_init__(self):
        if not self.citation_key and self.authors and self.year:
            last = self.authors[0].split()[-1].lower() if self.authors else "unknown"
            word = re.sub(r"\W", "", self.title.split()[0].lower()) if self.title else "ref"
            self.citation_key = f"{last}{self.year}{word}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Reference":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# ─── 포맷터 ──────────────────────────────────────────────────────────────────

def _fmt_authors_vancouver(authors: List[str], max_authors: int = 6) -> str:
    """Last FM, Last FM, ... et al."""
    if not authors:
        return ""
    shown = authors[:max_authors]
    suffix = " et al" if len(authors) > max_authors else ""
    return ", ".join(shown) + suffix


def _fmt_authors_apa(authors: List[str]) -> str:
    """Last, F. M., & Last, F. M."""
    if not authors:
        return ""
    parts = []
    for a in authors[:20]:
        tokens = a.strip().split()
        if len(tokens) >= 2:
            last = tokens[0]
            initials = "".join(t[0] + "." for t in tokens[1:])
            parts.append(f"{last}, {initials}")
        else:
            parts.append(a)
    if len(parts) > 1:
        return ", ".join(parts[:-1]) + ", & " + parts[-1]
    return parts[0] if parts else ""


def format_vancouver(ref: Reference, index: int = 1) -> str:
    authors = _fmt_authors_vancouver(ref.authors)
    vol_issue = ref.volume + (f"({ref.issue})" if ref.issue else "")
    location = f"{vol_issue}:{ref.pages}".strip(":") if (vol_issue or ref.pages) else ""
    parts = []
    if authors:
        parts.append(authors + ".")
    if ref.title:
        parts.append(ref.title.rstrip(".") + ".")
    j = ref.journal + "." if ref.journal else ""
    if ref.year:
        j += f" {ref.year};"
    if location:
        j += location + "."
    if j:
        parts.append(j)
    if ref.doi:
        parts.append(f"doi:{ref.doi}")
    elif ref.pmid:
        parts.append(f"PMID:{ref.pmid}")
    return f"{index}. " + " ".join(parts)


def format_apa(ref: Reference) -> str:
    authors = _fmt_authors_apa(ref.authors)
    journal_part = ref.journal
    if ref.volume:
        journal_part += f", {ref.volume}"
        if ref.issue:
            journal_part += f"({ref.issue})"
    if ref.pages:
        journal_part += f", {ref.pages}"
    doi_part = f" https://doi.org/{ref.doi}" if ref.doi else ""
    return f"{authors} ({ref.year}). {ref.title}. {journal_part}.{doi_part}"


def format_reference(ref: Reference, style: str = "Vancouver", index: int = 1) -> str:
    if style.lower() in ("apa",):
        return format_apa(ref)
    return format_vancouver(ref, index)


# ─── PubMed 조회 ─────────────────────────────────────────────────────────────

def _fetch_pubmed_xml(pmids: List[str]) -> str:
    """PubMed EFetch API로 XML 반환."""
    import urllib.request, urllib.parse
    params = urllib.parse.urlencode({
        "db": "pubmed", "id": ",".join(pmids),
        "rettype": "xml", "retmode": "xml",
    })
    url = f"{_PUBMED_EFETCH}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        _log.warning("PubMed EFetch 실패: %s", e)
        return ""


def _parse_pubmed_xml(xml_str: str) -> List[Reference]:
    """PubMed XML → Reference 리스트."""
    refs = []
    try:
        root = ET.fromstring(xml_str)
    except ET.ParseError:
        return refs

    for article in root.findall(".//PubmedArticle"):
        try:
            medline = article.find("MedlineCitation")
            art = medline.find("Article") if medline is not None else None
            if art is None:
                continue

            pmid_el = medline.find("PMID") if medline is not None else None
            pmid = pmid_el.text.strip() if pmid_el is not None else ""

            title_el = art.find("ArticleTitle")
            title = "".join(title_el.itertext()).strip() if title_el is not None else ""

            # 저자
            authors = []
            for author in art.findall(".//Author"):
                last = author.findtext("LastName", "")
                fore = author.findtext("ForeName", "")
                initials = author.findtext("Initials", "")
                if last:
                    name = last + (" " + (fore or initials) if (fore or initials) else "")
                    authors.append(name)

            # 저널
            journal_el = art.find("Journal")
            journal = ""
            year = ""
            volume = ""
            issue = ""
            if journal_el is not None:
                journal = journal_el.findtext("Title", "") or journal_el.findtext("ISOAbbreviation", "")
                ji = journal_el.find("JournalIssue")
                if ji is not None:
                    volume = ji.findtext("Volume", "")
                    issue = ji.findtext("Issue", "")
                    pub_date = ji.find("PubDate")
                    if pub_date is not None:
                        year = pub_date.findtext("Year", "") or pub_date.findtext("MedlineDate", "")[:4]

            # 페이지
            pages = art.findtext(".//MedlinePgn", "")

            # 초록
            abstract_texts = []
            for ab in art.findall(".//AbstractText"):
                label = ab.get("Label", "")
                text = "".join(ab.itertext()).strip()
                if label:
                    abstract_texts.append(f"{label}: {text}")
                else:
                    abstract_texts.append(text)
            abstract = " ".join(abstract_texts)

            # DOI
            doi = ""
            for loc in article.findall(".//ArticleId"):
                if loc.get("IdType") == "doi":
                    doi = loc.text.strip() if loc.text else ""

            refs.append(Reference(
                pmid=pmid, doi=doi, title=title, authors=authors,
                journal=journal, year=year, volume=volume, issue=issue,
                pages=pages, abstract=abstract[:500],
            ))
        except Exception as e:
            _log.debug("PubMed XML 파싱 오류: %s", e)

    return refs


def search_pubmed(query: str, max_results: int = 10) -> List[str]:
    """PubMed ESearch로 PMID 목록 반환."""
    import urllib.request, urllib.parse
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query,
        "retmax": max_results, "retmode": "json",
    })
    url = f"{_PUBMED_ESEARCH}?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        return data.get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        _log.warning("PubMed ESearch 실패: %s", e)
        return []


# ─── 내보내기 ─────────────────────────────────────────────────────────────────

def to_endnote_xml(refs: List[Reference], library_name: str = "Medical-Agent Library") -> str:
    """Reference 목록 → EndNote XML 문자열."""
    xml_lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        "<xml>", "<records>",
    ]
    for i, r in enumerate(refs, 1):
        xml_lines += [
            f"<record>",
            f"  <source-app name=\"EndNote\" version=\"20\"/>",
            f"  <rec-number>{i}</rec-number>",
            f"  <foreign-keys><key app=\"EN\" db-id=\"{r.pmid or i}\"/></foreign-keys>",
            f"  <ref-type name=\"Journal Article\">17</ref-type>",
            f"  <contributors><authors>",
        ]
        for author in r.authors:
            xml_lines.append(f"    <author><style face=\"normal\" font=\"default\">{author}</style></author>")
        xml_lines += [
            f"  </authors></contributors>",
            f"  <titles>",
            f"    <title><style face=\"normal\" font=\"default\">{_xml_escape(r.title)}</style></title>",
            f"    <secondary-title><style face=\"normal\" font=\"default\">{_xml_escape(r.journal)}</style></secondary-title>",
            f"  </titles>",
            f"  <periodical><full-title><style face=\"normal\" font=\"default\">{_xml_escape(r.journal)}</style></full-title></periodical>",
            f"  <pages><style face=\"normal\" font=\"default\">{r.pages}</style></pages>",
            f"  <volume><style face=\"normal\" font=\"default\">{r.volume}</style></volume>",
            f"  <number><style face=\"normal\" font=\"default\">{r.issue}</style></number>",
            f"  <dates><year><style face=\"normal\" font=\"default\">{r.year}</style></year></dates>",
            f"  <electronic-resource-num><style face=\"normal\" font=\"default\">{r.doi}</style></electronic-resource-num>",
            f"  <accession-num><style face=\"normal\" font=\"default\">{r.pmid}</style></accession-num>",
            f"  <abstract><style face=\"normal\" font=\"default\">{_xml_escape(r.abstract)}</style></abstract>",
            f"  <urls><related-urls><url><style face=\"normal\" font=\"default\">https://pubmed.ncbi.nlm.nih.gov/{r.pmid}/</style></url></related-urls></urls>",
            f"</record>",
        ]
    xml_lines += ["</records>", "</xml>"]
    return "\n".join(xml_lines)


def to_bibtex(refs: List[Reference]) -> str:
    """Reference 목록 → BibTeX 문자열."""
    lines = []
    for r in refs:
        key = r.citation_key or f"ref{r.pmid}"
        authors_bib = " and ".join(r.authors)
        lines += [
            f"@article{{{key},",
            f"  author = {{{authors_bib}}},",
            f"  title = {{{r.title}}},",
            f"  journal = {{{r.journal}}},",
            f"  year = {{{r.year}}},",
            f"  volume = {{{r.volume}}},",
            f"  number = {{{r.issue}}},",
            f"  pages = {{{r.pages}}},",
            f"  doi = {{{r.doi}}},",
            f"  pmid = {{{r.pmid}}},",
            "}",
            "",
        ]
    return "\n".join(lines)


def _xml_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


# ─── 라이브러리 클래스 ────────────────────────────────────────────────────────

class ReferenceLibrary:
    """논문별 인용 관리 라이브러리.

    Usage:
        lib = ReferenceLibrary("paper_slug")
        lib.add_from_pmids(["39012345", "38991234"])
        lib.add_manual(Reference(title="...", authors=[...], ...))
        formatted = lib.format_list("Vancouver")
        lib.save()  # data/journals/references/{slug}.json
        xml_str = lib.export_endnote_xml()
        bib_str = lib.export_bibtex()
    """

    def __init__(self, paper_slug: str = "default"):
        self.slug = re.sub(r"[^\w\-]", "_", paper_slug)[:80]
        self._refs: List[Reference] = []
        self._path = _REF_DIR / f"{self.slug}.json"
        if self._path.exists():
            self._load()

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def add_from_pmids(self, pmids: List[str]) -> int:
        """PMID 목록으로 PubMed 조회 후 추가. 추가된 수 반환."""
        if not pmids:
            return 0
        existing_pmids = {r.pmid for r in self._refs}
        new_pmids = [p for p in pmids if p not in existing_pmids]
        if not new_pmids:
            return 0
        xml_str = _fetch_pubmed_xml(new_pmids)
        new_refs = _parse_pubmed_xml(xml_str)
        self._refs.extend(new_refs)
        _log.info("PubMed에서 %d개 인용 추가 (요청=%d)", len(new_refs), len(new_pmids))
        return len(new_refs)

    def search_and_add(self, query: str, max_results: int = 5) -> int:
        """PubMed 검색 후 상위 결과 추가."""
        pmids = search_pubmed(query, max_results)
        time.sleep(0.5)
        return self.add_from_pmids(pmids)

    def add_manual(self, ref: Reference):
        """수동 Reference 추가."""
        self._refs.append(ref)

    def add_from_dict(self, d: dict):
        self._refs.append(Reference.from_dict(d))

    def format_list(self, style: str = "Vancouver") -> str:
        """전체 참고문헌 목록을 지정 스타일로 포맷."""
        lines = []
        for i, r in enumerate(self._refs, 1):
            lines.append(format_reference(r, style, i))
        return "\n".join(lines)

    def export_endnote_xml(self) -> str:
        """EndNote XML 문자열 반환."""
        return to_endnote_xml(self._refs, self.slug)

    def export_bibtex(self) -> str:
        """BibTeX 문자열 반환."""
        return to_bibtex(self._refs)

    def save(self):
        """data/journals/references/{slug}.json에 저장."""
        data = [r.to_dict() for r in self._refs]
        self._path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _log.info("레퍼런스 라이브러리 저장: %s (%d개)", self._path, len(self._refs))

    def save_endnote_xml(self) -> Path:
        """EndNote XML 파일로 저장, 경로 반환."""
        out = _REF_DIR / f"{self.slug}.xml"
        out.write_text(self.export_endnote_xml(), encoding="utf-8")
        _log.info("EndNote XML 저장: %s", out)
        return out

    def save_bibtex(self) -> Path:
        """BibTeX 파일로 저장, 경로 반환."""
        out = _REF_DIR / f"{self.slug}.bib"
        out.write_text(self.export_bibtex(), encoding="utf-8")
        _log.info("BibTeX 저장: %s", out)
        return out

    def get_refs(self) -> List[Reference]:
        return list(self._refs)

    def __len__(self) -> int:
        return len(self._refs)

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _load(self):
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            self._refs = [Reference.from_dict(d) for d in data]
        except Exception as e:
            _log.warning("레퍼런스 라이브러리 로드 실패 %s: %s", self._path, e)


# ─── 인라인 인용 삽입 ─────────────────────────────────────────────────────────

def insert_inline_citations(paper_text: str, ref_lib: "ReferenceLibrary") -> str:
    """논문 텍스트 문장 뒤에 [n] 인용 번호 자동 삽입.

    각 참고문헌의 title 키워드를 추출해, 해당 키워드를 2개 이상 포함하는 문장 뒤에
    [n] 삽입. 이미 [숫자] 패턴이 있는 문장은 건너뜀.
    """
    refs = ref_lib.get_refs() if hasattr(ref_lib, "get_refs") else []
    if not refs:
        return paper_text

    # 참고문헌별 핵심 키워드 집합 (index 1-based)
    ref_kw: List[tuple] = []
    for i, ref in enumerate(refs, 1):
        words: set = set()
        if ref.title:
            words.update(
                w.lower()
                for w in re.findall(r"\b[a-zA-Z가-힣]{4,}\b", ref.title)
            )
        # 저자성 + 연도 조합 (Lee2023 같은 패턴)
        if ref.authors and ref.year:
            last = ref.authors[0].split()[-1].lower() if ref.authors else ""
            if last:
                words.add(last)
        ref_kw.append((i, words))

    # 문장 단위 분리 (마침표/물음표/느낌표 뒤 공백)
    sentences = re.split(r"(?<=[.!?])\s+", paper_text)
    result = []
    for sent in sentences:
        # 이미 인용 번호 있으면 건너뜀
        if re.search(r"\[\d+[\d,\s]*\]", sent):
            result.append(sent)
            continue
        sent_lower = sent.lower()
        sent_words = set(re.findall(r"\b[a-zA-Z가-힣]{4,}\b", sent_lower))
        matched = []
        for idx, kw_set in ref_kw:
            if kw_set and len(kw_set & sent_words) >= 2:
                matched.append(idx)
        if matched:
            citation = "[" + ",".join(str(m) for m in matched[:3]) + "]"
            result.append(sent.rstrip() + " " + citation)
        else:
            result.append(sent)

    return " ".join(result)
