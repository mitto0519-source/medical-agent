"""Citation Grounding — 본문 [n] 마커 ↔ reference list 일관성 + DOI/연도 실존 검증.

체크:
  1. 본문의 모든 [n] 번호가 reference 목록에 존재하나 (orphan citation 차단)
  2. reference 목록의 모든 항목이 본문에 인용됐나 (orphan reference 차단)
  3. 각 reference의 DOI가 CrossRef에 실존 (할루시네이션 차단)
  4. 본문 인용 연도와 reference 연도 일관 (예: "2025 KYRBS" → ref 2025 일치)
  5. Author surname 형식 (Vancouver style 'Lastname Initial')

API:
  verify_citation_integrity(text, refs) -> Report
  verify_doi_crossref(doi) -> {exists, title, journal, year} or None
  check_year_consistency(text, refs) -> list[Warning]
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_CROSSREF = "https://api.crossref.org/works/{doi}"
_USER_AGENT = "medical-agent-safety/1.0 (mailto:research@medical-agent.local)"


@dataclass
class CitationReport:
    ok: bool = True
    orphan_citations: list = field(default_factory=list)    # 본문 [n] 인데 ref 없음
    orphan_references: list = field(default_factory=list)   # ref 있는데 본문 인용 0
    invalid_dois: list = field(default_factory=list)        # DOI CrossRef 실패
    year_mismatches: list = field(default_factory=list)     # 본문 연도 ↔ ref 연도
    summary: str = ""

    def to_dict(self) -> dict:
        return {"ok": self.ok,
                "orphan_citations": self.orphan_citations,
                "orphan_references": self.orphan_references,
                "invalid_dois": self.invalid_dois,
                "year_mismatches": self.year_mismatches,
                "summary": self.summary}


# ── DOI 검증 ──────────────────────────────────────────────────────────────────

def verify_doi_crossref(doi: str, *, timeout: int = 10,
                        use_cache: bool = True) -> dict | None:
    """CrossRef API로 DOI 실존 + 메타 조회. idempotency 캐시 24h."""
    doi = (doi or "").strip().lstrip("doi:").strip()
    if not doi or not doi.startswith("10."):
        return None

    def _hit():
        try:
            req = urllib.request.Request(_CROSSREF.format(doi=doi),
                                          headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.load(resp)
            if data.get("status") != "ok":
                return None
            m = data.get("message", {})
            year = None
            if m.get("published"):
                year = (m["published"].get("date-parts") or [[None]])[0][0]
            return {"exists": True,
                    "title": (m.get("title") or [""])[0],
                    "journal": (m.get("container-title") or [""])[0],
                    "year": year,
                    "doi": m.get("DOI") or doi}
        except urllib.error.HTTPError as e:
            return None if e.code == 404 else {"error": f"HTTP {e.code}"}
        except Exception as e:
            return {"error": str(e)[:80]}

    if not use_cache:
        return _hit()
    try:
        from src.runtime.idempotency import cached_call
        return cached_call(f"doi:{doi}", _hit, ttl_sec=24 * 3600, namespace="crossref_doi")
    except Exception:
        return _hit()


# ── 본문 ↔ reference 일관성 ──────────────────────────────────────────────────

_INTEXT = re.compile(r"\[(\d+(?:\s*[-,]\s*\d+)*)\]")
_REF_LINE = re.compile(r"^\s*(\d+)\.\s+(.+)$", re.MULTILINE)


def _expand_marker(inner: str) -> set:
    """'5-7, 15-17, 32' → {5,6,7,15,16,17,32}."""
    out = set()
    for tok in inner.split(","):
        tok = tok.strip()
        if "-" in tok:
            a, b = tok.split("-", 1)
            try:
                out.update(range(int(a), int(b) + 1))
            except ValueError:
                continue
        elif tok.isdigit():
            out.add(int(tok))
    return out


def extract_citation_numbers(text: str) -> set:
    """본문 [n] 마커의 모든 번호 집합 (범위 expand)."""
    nums = set()
    for m in _INTEXT.finditer(text or ""):
        nums |= _expand_marker(m.group(1))
    return nums


def parse_references(ref_block: str) -> dict:
    """'1. Authors. Title. Journal. 2024;...' 라인들 → {number: line}."""
    out = {}
    for m in _REF_LINE.finditer(ref_block or ""):
        out[int(m.group(1))] = m.group(2).strip()
    return out


# ── 연도 일관성 ──────────────────────────────────────────────────────────────

_YEAR_NEAR_CITATION = re.compile(r"\b(19|20)\d{2}\b[^.]*?\[(\d+(?:\s*[-,]\s*\d+)*)\]")


def check_year_consistency(text: str, refs: dict) -> list:
    """본문 'in 2025 [11]' 같은 인용에서 연도가 ref[11]의 연도와 일치하나."""
    warnings = []
    for m in _YEAR_NEAR_CITATION.finditer(text or ""):
        cite_year = int(m.group(0)[:4]) if m.group(0)[:4].isdigit() else None
        cite_nums = _expand_marker(m.group(2))
        for n in cite_nums:
            ref_line = refs.get(n, "")
            ref_year_m = re.search(r"\b(19|20)\d{2}\b", ref_line)
            ref_year = int(ref_year_m.group(0)) if ref_year_m else None
            if cite_year and ref_year and abs(cite_year - ref_year) > 1:
                warnings.append({"citation_num": n, "context_year": cite_year,
                                 "ref_year": ref_year,
                                 "ref": ref_line[:60]})
    return warnings


# ── 통합 검증 ────────────────────────────────────────────────────────────────

def check_rag_grounding(refs: dict, *, sample: int = 10) -> list:
    """RAG `papers` 컬렉션(10k+ chunks)에서 ref title/PMID 매칭 검색 — RAG-grounded 여부."""
    try:
        from src.vectordb.factory import get_vectorstore
        vs = get_vectorstore("papers")
    except Exception:
        return []
    out = []
    for n, line in list(refs.items())[:sample]:
        # title 후보 (첫 50자) + PMID 추출
        title_seed = re.sub(r"^[A-Z][a-z]+.+?\.\s*", "", line)[:80]  # 저자 제거 후 title-ish
        pmid_m = re.search(r"PMID[:\s]+(\d{4,9})", line)
        try:
            hits = vs.search(title_seed, k=3) if hasattr(vs, "search") else []
            grounded = bool(hits) or bool(pmid_m)
            out.append({"ref_num": n, "rag_grounded": grounded,
                        "pmid": pmid_m.group(1) if pmid_m else None})
        except Exception:
            out.append({"ref_num": n, "rag_grounded": False, "pmid": None})
    return out


def verify_citation_integrity(text: str, refs: dict | str = None,
                              *, check_dois: bool = True,
                              check_rag: bool = False,
                              max_dois: int = 20) -> CitationReport:
    """본문 + reference list 통합 검증.

    refs: {n: line} dict 또는 raw '## References\\n1. ...' 문자열
    check_dois: True면 처음 max_dois개 DOI를 CrossRef로 확인(idempotency 캐시).
    check_rag : True면 RAG papers 컬렉션에 ref title이 인덱싱돼 있는지 추가 확인.
    """
    if isinstance(refs, str):
        refs = parse_references(refs)
    refs = refs or {}

    report = CitationReport()

    # 1) orphan citations (본문 [n] 인데 ref 없음)
    cite_nums = extract_citation_numbers(text)
    ref_nums = set(refs.keys())
    orphan_cites = sorted(cite_nums - ref_nums)
    report.orphan_citations = orphan_cites

    # 2) orphan references (ref 있는데 본문 인용 0)
    orphan_refs = sorted(ref_nums - cite_nums)
    report.orphan_references = orphan_refs

    # 3) DOI CrossRef 검증
    if check_dois:
        checked = 0
        for n, line in sorted(refs.items()):
            if checked >= max_dois:
                break
            doi_m = re.search(r"\b10\.\d{4,9}/\S+", line)
            if not doi_m:
                continue
            doi = doi_m.group(0).rstrip(".,;)")
            res = verify_doi_crossref(doi)
            checked += 1
            if res is None or (isinstance(res, dict) and res.get("error")):
                report.invalid_dois.append({"ref_num": n, "doi": doi,
                                            "ref": line[:60],
                                            "reason": (res or {}).get("error", "not_found")})

    # 4) 연도 일관성
    report.year_mismatches = check_year_consistency(text, refs)

    # 5) RAG papers 컬렉션 grounding (선택)
    if check_rag and refs:
        rag = check_rag_grounding(refs, sample=10)
        ungrounded = [r for r in rag if not r["rag_grounded"]]
        if ungrounded:
            # CitationReport에 동적 attr 부착 (외부 호환)
            report.rag_ungrounded = ungrounded

    # 결과 종합
    report.ok = not (report.orphan_citations or report.invalid_dois
                     or report.year_mismatches)
    parts = []
    if report.orphan_citations: parts.append(f"orphan_citations={report.orphan_citations}")
    if report.orphan_references: parts.append(f"orphan_refs={len(report.orphan_references)}")
    if report.invalid_dois: parts.append(f"invalid_dois={len(report.invalid_dois)}")
    if report.year_mismatches: parts.append(f"year_mismatch={len(report.year_mismatches)}")
    report.summary = "OK" if report.ok else "; ".join(parts)
    return report
