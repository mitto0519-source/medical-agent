"""PMC Open Access Full-Text Downloader.

PubMed Central에서 오픈액세스 논문 전문을 다운로드하고
ChromaDB RAG 인덱스에 자동 등록한다.

저장 위치: data/pmc_papers/{pmcid}.txt
이미 존재하는 파일은 재다운로드하지 않는다.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional
from urllib import request as urllib_request
from urllib.error import URLError

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PAPERS_DIR = Path("data/pmc_papers")
_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
_DELAY = 0.4   # NCBI rate limit: 3 req/sec (without API key)


def _get(url: str, timeout: int = 20) -> str:
    with urllib_request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


class PMCDownloader:
    """PMC 오픈액세스 논문 전문 다운로더 + RAG 자동 인덱싱."""

    def __init__(self, papers_dir: Path = _PAPERS_DIR):
        self._dir = Path(papers_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    # ── 검색 ──────────────────────────────────────────────────────────────────

    def search_open_access(
        self, query: str, max_results: int = 10
    ) -> List[str]:
        """쿼리에 맞는 PMC 오픈액세스 논문 PMCID 목록 반환."""
        encoded = urllib_request.quote(f"{query} open access[filter]")
        url = (
            f"{_ESEARCH}?db=pmc&term={encoded}"
            f"&retmax={max_results}&retmode=xml"
        )
        try:
            xml_text = _get(url)
        except URLError as e:
            _log.warning("PMC esearch 실패: %s", e)
            return []

        try:
            root = ET.fromstring(xml_text)
            ids = [el.text for el in root.findall(".//Id") if el.text]
            _log.info("PMC 검색 '%s': %d편 발견", query[:50], len(ids))
            return ids
        except ET.ParseError as e:
            _log.warning("PMC esearch XML 파싱 실패: %s", e)
            return []

    # ── 다운로드 ──────────────────────────────────────────────────────────────

    def download_full_text(self, pmcid: str) -> Optional[str]:
        """PMCID로 논문 전문 텍스트 반환. 캐시 있으면 캐시 사용."""
        cached = self._dir / f"{pmcid}.txt"
        if cached.exists() and cached.stat().st_size > 200:
            return cached.read_text(encoding="utf-8")

        url = f"{_EFETCH}?db=pmc&id={pmcid}&rettype=full&retmode=xml"
        try:
            xml_text = _get(url, timeout=30)
        except URLError as e:
            _log.warning("PMC efetch 실패 (PMCID=%s): %s", pmcid, e)
            return None

        text = self._parse_xml_to_text(xml_text, pmcid)
        if not text or len(text) < 200:
            _log.debug("PMCID=%s: 전문 텍스트 너무 짧음 (%d자)", pmcid, len(text or ""))
            return None

        cached.write_text(text, encoding="utf-8")
        _log.info("PMC 전문 저장: %s (%d자)", cached.name, len(text))
        return text

    # ── 자동 RAG 인덱싱 ───────────────────────────────────────────────────────

    def auto_download_for_topic(
        self, query: str, max_papers: int = 8
    ) -> int:
        """쿼리로 논문 검색 → 다운로드 → RAG 인덱싱. 새로 인덱싱된 편수 반환."""
        pmcids = self.search_open_access(query, max_results=max_papers * 2)
        if not pmcids:
            return 0

        indexed = 0
        for pmcid in pmcids:
            if indexed >= max_papers:
                break

            cached = self._dir / f"{pmcid}.txt"
            already_cached = cached.exists() and cached.stat().st_size > 200

            text = self.download_full_text(pmcid)
            if not text:
                time.sleep(_DELAY)
                continue

            # 새로 다운로드한 경우만 RAG에 등록
            if not already_cached:
                try:
                    from src.rag.pipeline import RAGPipeline
                    rag = RAGPipeline()
                    rag.ingest_file(str(cached))
                    _log.info("RAG 인덱싱 완료: PMCID=%s", pmcid)
                    indexed += 1
                except Exception as e:
                    _log.warning("RAG 인덱싱 실패 (PMCID=%s): %s", pmcid, e)
            else:
                indexed += 1  # 캐시된 것도 카운트

            time.sleep(_DELAY)

        _log.info("PMC 자동 다운로드 완료: '%s' → %d편 준비", query[:50], indexed)
        return indexed

    # ── XML 파싱 헬퍼 ─────────────────────────────────────────────────────────

    @staticmethod
    def _parse_xml_to_text(xml_text: str, pmcid: str) -> str:
        """PubMed Central XML → 평문 텍스트 변환."""
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            # XML 파싱 실패 시 정규식으로 태그 제거
            return re.sub(r"<[^>]+>", " ", xml_text)

        parts = []

        # 제목
        for el in root.iter("article-title"):
            if el.text:
                parts.append(f"TITLE: {el.text.strip()}")
                break

        # 저널명
        for el in root.iter("journal-title"):
            if el.text:
                parts.append(f"JOURNAL: {el.text.strip()}")
                break

        # 초록
        abstract_parts = []
        for el in root.iter("abstract"):
            abstract_parts.append(_el_text(el))
        if abstract_parts:
            parts.append("ABSTRACT:\n" + "\n".join(abstract_parts))

        # 본문 섹션
        body_parts = []
        for body in root.iter("body"):
            for sec in body.iter("sec"):
                title_el = sec.find("title")
                sec_title = title_el.text.strip() if (title_el is not None and title_el.text) else ""
                paras = []
                for p in sec.findall("p"):
                    paras.append(_el_text(p))
                if paras:
                    body_parts.append(
                        (f"\n{sec_title}\n" if sec_title else "\n")
                        + "\n".join(paras)
                    )
        if body_parts:
            parts.append("FULL TEXT:\n" + "\n".join(body_parts))

        result = "\n\n".join(parts)
        return result if result else re.sub(r"<[^>]+>", " ", xml_text)


def _el_text(el) -> str:
    """XML 요소에서 재귀적으로 텍스트 추출."""
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        parts.append(_el_text(child))
        if child.tail:
            parts.append(child.tail)
    return " ".join(p.strip() for p in parts if p.strip())


# 편의 함수

def download_pmc_for_topic(query: str, max_papers: int = 8) -> int:
    """주제 쿼리로 PMC 전문 자동 다운로드 + RAG 인덱싱. 새 편수 반환."""
    return PMCDownloader().auto_download_for_topic(query, max_papers=max_papers)
