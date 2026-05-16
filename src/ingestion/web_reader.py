"""Web content reader — URL → clean text for ingestion

Supports
--------
- General web pages (HTML → main text via BeautifulSoup)
- arXiv papers (auto-downloads the PDF)
- PubMed abstracts (extracts abstract + metadata)
- Direct PDF URLs (downloads and reads via PyMuPDF)
"""

import os
import re
import tempfile
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import urlparse

import requests


def _get(url: str, timeout: int = 30) -> requests.Response:
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MedicalAgent/1.0)"}
    resp = requests.get(url, headers=headers, timeout=timeout)
    resp.raise_for_status()
    return resp


def _html_to_text(html: str) -> str:
    """Extract readable text from HTML, stripping nav/header/footer noise."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")

    # Remove non-content tags
    for tag in soup(["script", "style", "nav", "header", "footer",
                     "aside", "form", "noscript", "iframe"]):
        tag.decompose()

    # Prefer <article> or <main> if present
    body = soup.find("article") or soup.find("main") or soup.body or soup

    lines = []
    for elem in body.find_all(["p", "h1", "h2", "h3", "h4", "li", "td", "th"]):
        text = elem.get_text(separator=" ", strip=True)
        if text and len(text) > 20:
            lines.append(text)

    return "\n\n".join(lines)


def _read_arxiv(arxiv_id: str) -> Dict:
    """Download and read an arXiv paper PDF."""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    resp = _get(pdf_url)

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        import fitz
        doc = fitz.open(tmp_path)
        pages = [page.get_text("text").strip() for page in doc]
        doc.close()
        full_text = "\n\n".join(p for p in pages if p)
    finally:
        os.unlink(tmp_path)

    # Get metadata from arXiv API
    api_url = f"https://export.arxiv.org/abs/{arxiv_id}"
    try:
        meta_resp = _get(api_url)
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(meta_resp.text, "html.parser")
        title_tag = soup.find("h1", class_="title")
        title = title_tag.get_text(strip=True).replace("Title:", "").strip() if title_tag else arxiv_id
    except Exception:
        title = arxiv_id

    return {
        "title": title,
        "full_text": full_text,
        "source_url": f"https://arxiv.org/abs/{arxiv_id}",
        "source_type": "arxiv",
    }


def _read_pubmed(pmid: str) -> Dict:
    """Fetch PubMed abstract via NCBI API."""
    url = (
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={pmid}&rettype=abstract&retmode=text"
    )
    resp = _get(url)
    text = resp.text.strip()

    # Try to extract title from first non-empty line
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    title = lines[0] if lines else f"PubMed_{pmid}"

    return {
        "title": title,
        "full_text": text,
        "source_url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        "source_type": "pubmed",
    }


def _read_pdf_url(url: str) -> Dict:
    """Download a PDF from a URL and read it."""
    resp = _get(url)
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = tmp.name

    try:
        import fitz
        doc = fitz.open(tmp_path)
        meta = doc.metadata or {}
        pages = [page.get_text("text").strip() for page in doc]
        doc.close()
        full_text = "\n\n".join(p for p in pages if p)
        title = meta.get("title") or Path(urlparse(url).path).stem
    finally:
        os.unlink(tmp_path)

    return {
        "title": title,
        "full_text": full_text,
        "source_url": url,
        "source_type": "pdf_url",
    }


def _read_html_url(url: str) -> Dict:
    """Read a general web page."""
    resp = _get(url)
    resp.encoding = resp.apparent_encoding or "utf-8"
    full_text = _html_to_text(resp.text)

    # Try to get <title>
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(resp.text, "html.parser")
        title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else url
    except Exception:
        title = url

    return {
        "title": title,
        "full_text": full_text,
        "source_url": url,
        "source_type": "web",
    }


class WebReader:
    """Fetch web content and convert to a document dict for the RAG pipeline.

    Automatically detects:
    - arXiv URLs / IDs  → downloads the full PDF
    - PubMed URLs / PMIDs → fetches the abstract
    - Direct .pdf URLs  → downloads and reads PDF
    - All other URLs    → HTML text extraction
    """

    # Patterns for URL type detection
    _ARXIV_URL  = re.compile(r"arxiv\.org/(abs|pdf)/(\d{4}\.\d{4,5})(v\d+)?", re.I)
    _ARXIV_ID   = re.compile(r"^(\d{4}\.\d{4,5})(v\d+)?$")
    _PUBMED_URL = re.compile(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", re.I)
    _PMID       = re.compile(r"^PMID?:?\s*(\d+)$", re.I)

    def read(self, url_or_id: str) -> Dict:
        """Fetch content from a URL or identifier.

        Args:
            url_or_id: Full URL, arXiv ID (e.g. "2401.12345"), or PMID

        Returns:
            Document dict compatible with TextChunker.chunk_document()
        """
        s = url_or_id.strip()

        # arXiv ID shorthand
        m = self._ARXIV_ID.match(s)
        if m:
            result = _read_arxiv(m.group(1))
            return self._wrap(result, s)

        # PubMed PMID shorthand
        m = self._PMID.match(s)
        if m:
            result = _read_pubmed(m.group(1))
            return self._wrap(result, s)

        # Full URL
        parsed = urlparse(s)
        if not parsed.scheme:
            s = "https://" + s

        # arXiv URL
        m = self._ARXIV_URL.search(s)
        if m:
            result = _read_arxiv(m.group(2))
            return self._wrap(result, s)

        # PubMed URL
        m = self._PUBMED_URL.search(s)
        if m:
            result = _read_pubmed(m.group(1))
            return self._wrap(result, s)

        # Direct PDF link
        if s.lower().endswith(".pdf") or "application/pdf" in self._content_type(s):
            result = _read_pdf_url(s)
            return self._wrap(result, s)

        # General HTML
        result = _read_html_url(s)
        return self._wrap(result, s)

    def _content_type(self, url: str) -> str:
        try:
            r = requests.head(url, timeout=10,
                              headers={"User-Agent": "Mozilla/5.0"}, allow_redirects=True)
            return r.headers.get("Content-Type", "")
        except Exception:
            return ""

    @staticmethod
    def _wrap(result: Dict, original_input: str) -> Dict:
        """Normalise to the standard document dict shape."""
        filename = re.sub(r"[^\w\-.]", "_", result["title"])[:80] + ".web"
        word_count = len(result["full_text"].split())
        return {
            "path": original_input,
            "filename": filename,
            "title": result["title"],
            "full_text": result["full_text"],
            "page_count": max(1, word_count // 400),
            "file_type": result["source_type"],
            "metadata": {"source_url": result["source_url"]},
        }
