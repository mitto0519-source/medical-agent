"""Europe PMC OA Subset bulk fetcher — 무료 풀텍스트 5만편 학습 인프라 Phase 1.

사용자 목표: 5만편 이상 풀텍스트로 의미있는 ontology/지식 그래프 구성.
선택된 소스 (사용자 응답):
  1. Europe PMC OA Subset (권장) — REST API
  2. PubMed Central FTP (oa_bulk) — 대량 tarball
  3. Semantic Scholar (메타+초록 보조)

본 모듈은 (1) Europe PMC 부터 시작. fetch_oa_batch()가 backlog handler에서 호출됨.
디스크 절약: 풀텍스트 XML 저장 X, **본문 텍스트만** + figure/table 캡션 별도 추출.

저장:
    data/oa_papers/{pmcid}.txt        # 본문 텍스트
    data/oa_papers/{pmcid}.meta.json  # 제목·저자·연도·journal + figure/table 캡션 리스트
    data/oa_papers/manifest.sqlite    # query → pmcid 매핑 + fetched_at + chunked_at

heartbeat가 idempotency_cache + budget 검사 후 호출.
"""
from __future__ import annotations

import io
import json
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_OUT_DIR = Path("data/oa_papers")
_MANIFEST_DB = _OUT_DIR / "manifest.sqlite"
_EPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"
_EPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{src}/{eid}/fullTextXML"


def _ua() -> dict:
    return {"User-Agent": "medical-agent-oa/1.0 (research)"}


def _init_manifest() -> sqlite3.Connection:
    _OUT_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_MANIFEST_DB))
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS papers(
        pmcid TEXT PRIMARY KEY,
        pmid TEXT,
        title TEXT,
        year INTEGER,
        journal TEXT,
        query TEXT,
        fetched_at REAL,
        chunked_at REAL,
        n_chars INTEGER,
        n_figures INTEGER,
        n_tables INTEGER,
        status TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_query ON papers(query)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_chunked ON papers(chunked_at)")
    c.commit()
    return c


def _search_oa(query: str, *, n_target: int = 100, page_size: int = 25,
                year_min: Optional[int] = None) -> list[dict]:
    """Europe PMC OA Subset 검색 — OPEN_ACCESS 필터 + HAS_FT 필터."""
    q = f'({query}) AND OPEN_ACCESS:Y AND HAS_FT:Y'
    if year_min:
        q += f' AND FIRST_PDATE:[{year_min}-01-01 TO 3000-12-31]'

    results: list = []
    cursor = "*"
    while len(results) < n_target:
        params = {"query": q, "format": "json", "pageSize": min(page_size, n_target - len(results)),
                   "cursorMark": cursor, "resultType": "core"}
        url = f"{_EPMC_SEARCH}?{urllib.parse.urlencode(params)}"
        try:
            req = urllib.request.Request(url, headers=_ua())
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
        except Exception as e:
            _log.warning("OA search 실패: %s", e)
            break
        hits = data.get("resultList", {}).get("result", []) or []
        if not hits:
            break
        results.extend(hits)
        next_cursor = data.get("nextCursorMark")
        if not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
        time.sleep(0.3)   # rate limit courtesy
    return results[:n_target]


def _fetch_fulltext(pmcid: str, source: str = "PMC") -> Optional[str]:
    """XML 본문 fetch → 텍스트만 추출. 실패 시 None."""
    # Europe PMC 풀텍스트는 PMCID 기준
    eid = pmcid.replace("PMC", "") if pmcid.startswith("PMC") else pmcid
    url = _EPMC_FULLTEXT.format(src=source, eid=eid)
    try:
        req = urllib.request.Request(url, headers=_ua())
        with urllib.request.urlopen(req, timeout=60) as resp:
            xml = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        _log.debug("fulltext fetch fail %s: %s", pmcid, e)
        return None
    return xml


_TAG_RE = re.compile(r"<[^>]+>")
_FIG_RE = re.compile(r"<fig[^>]*>(.*?)</fig>", re.DOTALL | re.IGNORECASE)
_TBL_RE = re.compile(r"<table-wrap[^>]*>(.*?)</table-wrap>", re.DOTALL | re.IGNORECASE)
_CAPTION_RE = re.compile(r"<caption[^>]*>(.*?)</caption>", re.DOTALL | re.IGNORECASE)


def _extract_text_and_meta(xml: str) -> dict:
    """JATS XML → 본문 텍스트 + figure/table 캡션 리스트.
    완벽한 파싱은 아니지만 ontology 학습용 텍스트 추출엔 충분."""
    figs = []
    for m in _FIG_RE.finditer(xml):
        cap = _CAPTION_RE.search(m.group(1))
        figs.append(_TAG_RE.sub(" ", cap.group(1)).strip()[:400] if cap else "")
    tbls = []
    for m in _TBL_RE.finditer(xml):
        cap = _CAPTION_RE.search(m.group(1))
        tbls.append(_TAG_RE.sub(" ", cap.group(1)).strip()[:400] if cap else "")
    # 본문 — fig/table을 제거한 뒤 태그 strip
    body = _FIG_RE.sub(" ", xml)
    body = _TBL_RE.sub(" ", body)
    body = _TAG_RE.sub(" ", body)
    body = re.sub(r"\s+", " ", body).strip()
    return {"body": body, "figures": figs, "tables": tbls}


def fetch_oa_batch(query: str, *, n_target: int = 100,
                    year_min: Optional[int] = None,
                    skip_if_exists: bool = True) -> dict:
    """한 query에 대해 OA 풀텍스트 N편 수집 → 디스크 저장 + manifest 기록.

    Returns: {"fetched": N, "skipped": M, "failed": K, "query": q}
    """
    c = _init_manifest()
    hits = _search_oa(query, n_target=n_target, year_min=year_min)
    if not hits:
        return {"fetched": 0, "skipped": 0, "failed": 0, "query": query,
                "reason": "no_hits"}

    fetched, skipped, failed = 0, 0, 0
    for hit in hits:
        pmcid = hit.get("pmcid") or ""
        if not pmcid:
            continue
        if skip_if_exists:
            row = c.execute("SELECT 1 FROM papers WHERE pmcid=?", (pmcid,)).fetchone()
            if row:
                skipped += 1
                continue
        xml = _fetch_fulltext(pmcid, source=hit.get("source", "PMC"))
        if not xml:
            failed += 1
            continue
        try:
            extracted = _extract_text_and_meta(xml)
        except Exception as e:
            _log.debug("extract fail %s: %s", pmcid, e)
            failed += 1
            continue
        # 저장
        body_path = _OUT_DIR / f"{pmcid}.txt"
        meta_path = _OUT_DIR / f"{pmcid}.meta.json"
        try:
            body_path.write_text(extracted["body"][:5_000_000], encoding="utf-8")
            meta = {
                "pmcid": pmcid, "pmid": hit.get("pmid", ""),
                "title": hit.get("title", "")[:500],
                "year": int(hit.get("pubYear", 0) or 0) or None,
                "journal": hit.get("journalTitle", "")[:200],
                "authors": hit.get("authorString", "")[:1000],
                "doi": hit.get("doi", ""),
                "figures": extracted["figures"][:50],
                "tables": extracted["tables"][:50],
                "query": query,
                "fetched_at": time.time(),
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                                  encoding="utf-8")
            c.execute(
                "INSERT OR REPLACE INTO papers"
                "(pmcid, pmid, title, year, journal, query, fetched_at, n_chars, n_figures, n_tables, status) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (pmcid, meta["pmid"], meta["title"], meta["year"], meta["journal"],
                 query, meta["fetched_at"], len(extracted["body"]),
                 len(extracted["figures"]), len(extracted["tables"]), "FETCHED"),
            )
            c.commit()
            fetched += 1
        except Exception as e:
            _log.warning("save fail %s: %s", pmcid, e)
            failed += 1
        time.sleep(0.2)   # rate limit courtesy

    _log.info("OA bulk %s: fetched=%d skipped=%d failed=%d", query, fetched, skipped, failed)
    return {"fetched": fetched, "skipped": skipped, "failed": failed,
            "query": query, "out_dir": str(_OUT_DIR)}


def manifest_stats() -> dict:
    """전체 수집 현황 — /backlog 페이지가 표시."""
    if not _MANIFEST_DB.exists():
        return {"total": 0, "by_query": [], "by_year": []}
    c = sqlite3.connect(str(_MANIFEST_DB))
    total = c.execute("SELECT COUNT(*) FROM papers").fetchone()[0]
    chunked = c.execute("SELECT COUNT(*) FROM papers WHERE chunked_at IS NOT NULL").fetchone()[0]
    by_query = c.execute(
        "SELECT query, COUNT(*) FROM papers GROUP BY query ORDER BY 2 DESC LIMIT 20"
    ).fetchall()
    by_year = c.execute(
        "SELECT year, COUNT(*) FROM papers WHERE year IS NOT NULL "
        "GROUP BY year ORDER BY year DESC LIMIT 20"
    ).fetchall()
    total_chars = c.execute("SELECT SUM(n_chars) FROM papers").fetchone()[0] or 0
    c.close()
    return {
        "total_papers": total,
        "chunked_papers": chunked,
        "pending_chunk": total - chunked,
        "total_chars": total_chars,
        "by_query": [{"query": q, "n": n} for q, n in by_query],
        "by_year": [{"year": y, "n": n} for y, n in by_year],
    }
