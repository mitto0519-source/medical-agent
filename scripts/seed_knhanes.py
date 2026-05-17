"""KNHANES 데이터셋 시드 & 동기화 스크립트.

기능:
  1. data/libraries/dataset_knhanes.json → DatasetLibrary + Supabase 등록
  2. PubMed에서 KNHANES 사용 논문 자동 수집 (최신 200편)
  3. data/raw/knhanes/ 의 실제 데이터 파일 처리 (CSV/SAS 자동 감지)
  4. Supabase ma_datasets 테이블 동기화

사용법:
    python scripts/seed_knhanes.py                   # 전체 실행
    python scripts/seed_knhanes.py --refs-only        # PubMed 참조논문만 업데이트
    python scripts/seed_knhanes.py --sync-only        # Supabase 동기화만
    python scripts/seed_knhanes.py --parse-raw        # 로컬 CSV 데이터 변수 추출

KNHANES 원시데이터 다운로드:
    https://knhanes.kdca.go.kr/knhanes/sub03/sub03_02_02.do
    → data/raw/knhanes/ 에 저장 후 --parse-raw 옵션 실행
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
EMAIL = "mitto0519@gmail.com"
RAW_DIR = ROOT / "data" / "raw" / "knhanes"
LIB_DIR = ROOT / "data" / "libraries"
DS_FILE = LIB_DIR / "dataset_knhanes.json"

KNHANES_QUERIES = [
    'Korea National Health and Nutrition Examination Survey[Title/Abstract]',
    'KNHANES[Title/Abstract] AND Korea[Title/Abstract]',
    'Korean National Health Nutrition Examination Survey[Title/Abstract]',
]

# ── NCBI helpers ─────────────────────────────────────────────────────────────

def _load_env():
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"\''))


def _ncbi_get(url: str) -> bytes:
    api_key = os.environ.get("NCBI_API_KEY", "")
    sep = "&" if "?" in url else "?"
    full = f"{url}{sep}email={EMAIL}" + (f"&api_key={api_key}" if api_key else "")
    for attempt in range(3):
        try:
            with urllib.request.urlopen(full, timeout=30) as r:
                return r.read()
        except Exception as e:
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)
    return b""


def _search(query: str, retmax: int = 200) -> list[str]:
    params = urllib.parse.urlencode({
        "db": "pubmed", "term": query, "retmax": retmax, "retmode": "json",
    })
    data = json.loads(_ncbi_get(f"{EUTILS}/esearch.fcgi?{params}"))
    return data["esearchresult"]["idlist"]


def _fetch_xml(pmids: list[str]) -> list[dict]:
    if not pmids:
        return []
    ids = ",".join(pmids)
    params = urllib.parse.urlencode({"db": "pubmed", "id": ids,
                                     "rettype": "abstract", "retmode": "xml"})
    xml_bytes = _ncbi_get(f"{EUTILS}/efetch.fcgi?{params}")

    papers = []
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return papers

    for article in root.findall(".//PubmedArticle"):
        pmid_el = article.find(".//PMID")
        pmid = pmid_el.text if pmid_el is not None else ""

        title_el = article.find(".//ArticleTitle")
        title = "".join(title_el.itertext()) if title_el is not None else ""

        abstract_parts = []
        for ab in article.findall(".//AbstractText"):
            label = ab.get("Label", "")
            text = "".join(ab.itertext())
            abstract_parts.append(f"{label}: {text}" if label else text)
        abstract = " ".join(abstract_parts)

        year_el = article.find(".//PubDate/Year")
        if year_el is None:
            year_el = article.find(".//ArticleDate/Year")
        year = year_el.text if year_el is not None else ""

        journal_el = article.find(".//Journal/Title")
        journal = journal_el.text if journal_el is not None else ""

        authors = []
        for au in article.findall(".//Author")[:6]:
            ln = au.findtext("LastName", "")
            fn = au.findtext("ForeName", "") or au.findtext("Initials", "")
            if ln:
                authors.append(f"{ln} {fn}".strip())

        doi = ""
        for aid in article.findall(".//ArticleId"):
            if aid.get("IdType") == "doi":
                doi = aid.text or ""

        if title and abstract:
            papers.append({
                "pmid": pmid,
                "title": title,
                "abstract": abstract,
                "year": year,
                "journal": journal,
                "authors": authors,
                "doi": doi,
            })
    return papers


# ── Dataset library ───────────────────────────────────────────────────────────

def register_dataset():
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    """dataset_knhanes.json 을 읽어 Supabase 에만 직접 등록.

    DatasetLibrary._save() 를 호출하지 않으므로 JSON 원본(waves/sampling_design/
    download_info 등 확장 필드) 이 보존된다.
    """
=======
    """dataset_knhanes.json -> Supabase 등록. 로컬 JSON은 원본 그대로 보존."""
>>>>>>> Stashed changes
=======
    """dataset_knhanes.json -> Supabase 등록. 로컬 JSON은 원본 그대로 보존."""
>>>>>>> Stashed changes
=======
    """dataset_knhanes.json -> Supabase 등록. 로컬 JSON은 원본 그대로 보존."""
>>>>>>> Stashed changes
    print("[1/4] 데이터셋 라이브러리 등록...", flush=True)
    # JSON is the authoritative source — do NOT modify it via DatasetLibrary
    # (DatasetLibrary._save() strips extra fields like waves/download_info)
    ds_data = json.loads(DS_FILE.read_text(encoding="utf-8"))
    n_vars = len(ds_data.get("variables", {}))
    n_notes = len(ds_data.get("analysis_notes", []))
    n_refs = len(ds_data.get("papers_using_this", []))
<<<<<<< Updated upstream
<<<<<<< Updated upstream
<<<<<<< Updated upstream
    print(f"   KNHANES: 변수 {n_vars}개 / 분석노트 {n_notes}개 / 참조 {n_refs}편")
=======
    print(f"   KNHANES: {n_vars}개 변수 / 분석 노트 {n_notes}개 / 참조 {n_refs}편")
>>>>>>> Stashed changes
=======
    print(f"   KNHANES: {n_vars}개 변수 / 분석 노트 {n_notes}개 / 참조 {n_refs}편")
>>>>>>> Stashed changes
=======
    print(f"   KNHANES: {n_vars}개 변수 / 분석 노트 {n_notes}개 / 참조 {n_refs}편")
>>>>>>> Stashed changes


def fetch_pubmed_refs(max_papers: int = 300):
    """PubMed에서 KNHANES 사용 논문 수집 후 dataset library에 추가."""
    print("[2/4] PubMed 참조 논문 수집...", flush=True)

    delay = 0.4
    all_pmids: set[str] = set()

    for q in KNHANES_QUERIES:
        try:
            pmids = _search(q, retmax=100)
            all_pmids.update(pmids)
            print(f"   '{q[:50]}...' -> {len(pmids)} hits")
            time.sleep(delay)
        except Exception as e:
            print(f"   ERROR: {e}")

    pmid_list = list(all_pmids)[:max_papers]
    print(f"   총 {len(pmid_list)}개 PMID 수집; 상세 정보 가져오는 중...")

    papers = []
    for i in range(0, len(pmid_list), 50):
        batch = pmid_list[i:i + 50]
        papers.extend(_fetch_xml(batch))
        time.sleep(delay)

    # Save refs to dataset json
    ds_data = json.loads(DS_FILE.read_text(encoding="utf-8"))
    existing = set(ds_data.get("papers_using_this", []))

    new_refs = []
    for p in papers:
        authors_str = ", ".join(p["authors"][:3])
        if len(p["authors"]) > 3:
            authors_str += " et al"
        ref = f"{authors_str}. {p['title']}. {p['journal']}. {p['year']}."
        if p.get("doi"):
            ref += f" doi:{p['doi']}"
        if ref not in existing:
            new_refs.append(ref)
            existing.add(ref)

    ds_data["papers_using_this"] = list(existing)
    # Write back to JSON only — do NOT use DatasetLibrary (would strip extra fields)
    DS_FILE.write_text(json.dumps(ds_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"   새 참조 논문 {len(new_refs)}편 추가 (총 {len(existing)}편)")

    # Save raw paper data for RAG/seed
    refs_cache = ROOT / "data" / "raw" / "knhanes" / "pubmed_refs.json"
    refs_cache.parent.mkdir(parents=True, exist_ok=True)
    refs_cache.write_text(
        json.dumps(papers, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"   원본 데이터 저장: {refs_cache}")

    return papers


def parse_raw_data():
    """data/raw/knhanes/ 의 CSV/SAS 파일에서 변수명/레이블 자동 추출."""
    print("[3/4] 원시 데이터 파싱...", flush=True)

    if not RAW_DIR.exists() or not any(RAW_DIR.iterdir()):
        print("   data/raw/knhanes/ 비어있음. KNHANES 원시데이터 다운로드 필요:")
        print("   -> https://knhanes.kdca.go.kr/knhanes/sub03/sub03_02_02.do")
        print("   -> 다운로드 후 data/raw/knhanes/ 에 저장 후 --parse-raw 재실행")
        return None

    detected = {"csv": [], "sas": [], "sav": []}
    for f in RAW_DIR.glob("**/*"):
        ext = f.suffix.lower()
        if ext == ".csv":
            detected["csv"].append(f)
        elif ext in (".sas7bdat", ".sas"):
            detected["sas"].append(f)
        elif ext == ".sav":
            detected["sav"].append(f)

    print(f"   발견: CSV {len(detected['csv'])}개, SAS {len(detected['sas'])}개, SAV {len(detected['sav'])}개")

    all_vars: dict[str, dict] = {}

    # Parse CSV headers
    for csv_file in detected["csv"]:
        try:
            with open(csv_file, encoding="utf-8-sig") as f:
                header = f.readline().strip()
            cols = [c.strip().strip('"') for c in header.split(",")]
            for col in cols:
                if col and col not in all_vars:
                    all_vars[col] = {
                        "label": col,
                        "type": "unknown",
                        "unit": "",
                        "source_file": csv_file.name,
                    }
            print(f"   {csv_file.name}: {len(cols)}개 컬럼")
        except Exception as e:
            print(f"   ERROR {csv_file.name}: {e}")

    # Parse SAS files (requires pyreadstat)
    if detected["sas"]:
        try:
            import pyreadstat
            for sas_file in detected["sas"]:
                try:
                    _, meta = pyreadstat.read_sas7bdat(str(sas_file), metadataonly=True)
                    for col, label in (meta.column_labels or {}).items():
                        if col not in all_vars:
                            all_vars[col] = {
                                "label": label or col,
                                "type": "unknown",
                                "unit": "",
                                "source_file": sas_file.name,
                            }
                    print(f"   {sas_file.name}: {len(meta.column_names or [])}개 변수")
                except Exception as e:
                    print(f"   ERROR {sas_file.name}: {e}")
        except ImportError:
            print("   SAS 파일 처리: pip install pyreadstat 필요")

    if all_vars:
        out = ROOT / "data" / "raw" / "knhanes" / "extracted_variables.json"
        out.write_text(json.dumps(all_vars, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"   추출된 변수 {len(all_vars)}개 -> {out}")

        # Merge newly found vars into dataset_knhanes.json
        ds_data = json.loads(DS_FILE.read_text(encoding="utf-8"))
        new_count = 0
        for var, info in all_vars.items():
            if var not in ds_data["variables"]:
                ds_data["variables"][var] = {
                    "label": info["label"],
                    "type": info.get("type", "unknown"),
                    "unit": "",
                    "processing": "",
                    "cutoffs": {},
                    "missing_strategy": "exclude",
                    "notes": f"source: {info.get('source_file', '')}",
                }
                new_count += 1
        DS_FILE.write_text(json.dumps(ds_data, ensure_ascii=False, indent=2), encoding="utf-8")
        if new_count:
            print(f"   새 변수 {new_count}개 데이터셋에 추가")

    return all_vars


def sync_to_supabase():
    """data/libraries/dataset_knhanes.json -> Supabase 강제 동기화."""
    print("[4/4] Supabase 동기화...", flush=True)
    try:
        from src.cloud.db import cloud_available, get_engine
        from sqlalchemy import text

        if not cloud_available():
            print("   SUPABASE_DB_URL 미설정 — 로컬 JSON만 사용")
            return

        ds_data = json.loads(DS_FILE.read_text(encoding="utf-8"))
        with get_engine().begin() as conn:
            conn.execute(text("""
                INSERT INTO ma_datasets
                    (name, full_name, description, variables, analysis_notes,
                     common_confounders, papers_using_this, updated_at)
                VALUES
                    (:name, :full_name, :description,
                     CAST(:variables AS jsonb), CAST(:analysis_notes AS jsonb),
                     CAST(:common_confounders AS jsonb), CAST(:papers_using_this AS jsonb),
                     NOW())
                ON CONFLICT (name) DO UPDATE SET
                    full_name          = EXCLUDED.full_name,
                    description        = EXCLUDED.description,
                    variables          = EXCLUDED.variables,
                    analysis_notes     = EXCLUDED.analysis_notes,
                    common_confounders = EXCLUDED.common_confounders,
                    papers_using_this  = EXCLUDED.papers_using_this,
                    updated_at         = NOW()
            """), {
                "name": ds_data["name"],
                "full_name": ds_data.get("full_name", ""),
                "description": ds_data.get("description", ""),
                "variables": json.dumps(ds_data.get("variables", {}), ensure_ascii=False),
                "analysis_notes": json.dumps(ds_data.get("analysis_notes", []), ensure_ascii=False),
                "common_confounders": json.dumps(ds_data.get("common_confounders", []), ensure_ascii=False),
                "papers_using_this": json.dumps(ds_data.get("papers_using_this", []), ensure_ascii=False),
            })
        print("   Supabase 동기화 완료")
    except Exception as e:
        print(f"   Supabase 동기화 오류: {e}")


def run(refs_only: bool = False, sync_only: bool = False, parse_raw: bool = False):
    _load_env()

    if sync_only:
        sync_to_supabase()
        return

    if refs_only:
        fetch_pubmed_refs()
        sync_to_supabase()
        return

    register_dataset()
    papers = fetch_pubmed_refs()

    if parse_raw:
        parse_raw_data()

    sync_to_supabase()

    print("\nKNHANES 시드 완료.")
    print("  DatasetLibrary에서 lib.get_context('KNHANES') 로 연구파이프라인에 주입 가능")
    print("  원시데이터 경로: data/raw/knhanes/")
    print("  PubMed 참조 캐시: data/raw/knhanes/pubmed_refs.json")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KNHANES 데이터셋 시드 & 동기화")
    parser.add_argument("--refs-only", action="store_true", help="PubMed 참조논문만 업데이트")
    parser.add_argument("--sync-only", action="store_true", help="Supabase 동기화만 실행")
    parser.add_argument("--parse-raw", action="store_true", help="data/raw/knhanes/ CSV/SAS 파싱 포함")
    args = parser.parse_args()

    run(refs_only=args.refs_only, sync_only=args.sync_only, parse_raw=args.parse_raw)
