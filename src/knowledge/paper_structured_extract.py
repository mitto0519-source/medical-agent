"""Per-paper structured clinical extraction — RAG raw chunk를 대체.

사용자 비전 (2026-06-05): RAG에서 abstract 박는 게 아니라, 의사 사고 단위로
구조화된 필드를 추출해 prompt에 박는다. 12,500+ OA papers 전체 1회 추출 →
JSONL 캐시 → paper_writer가 raw chunk 대신 이 필드를 retrieve.

추출 필드 (의사 reasoning 핵심 6개):
    pico              : Population / Intervention / Comparator / Outcome
    grade             : evidence quality (high/moderate/low/very-low)
    excluded_subgroup : RCT가 cover 못한 환자군 (age/comorbidity/Rx 등)
    limitation        : 가장 큰 methodological flaw 1문장
    practice_impl     : "이 결과가 임상에서 어떻게 적용되나" 1문장
    conflict          : conflict of interest (if any)

사용:
    extract_one(pmcid)          → dict (LLM 호출 1회, ~$0.001 Gemini Flash 기준)
    batch_extract(limit=None)   → 전체 PMC oa_papers 대상 idempotent batch
    structured_retrieve(query)  → ChromaDB 양식 구조화 필드 검색
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.llm import get_llm_client

_log = get_logger(__name__)

_OA_DIR = Path("data/oa_papers")
_CACHE_DB = Path("data/medical_knowledge_seed/structured.sqlite")

_PROMPT = """Extract 6 clinical reasoning fields from this medical paper.
Return ONLY a valid JSON object with these exact keys (no other text):

{
  "pico": {
    "population": "specific cohort with key inclusion criteria (1 line)",
    "intervention": "treatment / exposure / test studied (1 line)",
    "comparator": "control or comparator (or null if single-arm)",
    "outcome": "primary outcome with timeframe (1 line)"
  },
  "grade": "high | moderate | low | very-low",
  "excluded_subgroup": "patient group NOT covered by this study (1 sentence, or null)",
  "limitation": "single most important methodological limitation (1 sentence)",
  "practice_implication": "what changes at the bedside if findings are correct (1 sentence)",
  "conflict": "conflict of interest statement (or null)"
}

If a field cannot be determined from the text, use null. Do NOT hallucinate."""


def _init_cache():
    _CACHE_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_CACHE_DB))
    conn.execute("""CREATE TABLE IF NOT EXISTS structured (
        pmcid TEXT PRIMARY KEY,
        pico_json TEXT, grade TEXT, excluded_subgroup TEXT,
        limitation TEXT, practice_implication TEXT, conflict TEXT,
        extracted_at REAL, source_chars INTEGER
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grade ON structured(grade)")
    conn.commit()
    return conn


def extract_one(pmcid: str, *, llm=None, max_input_chars: int = 6000) -> Optional[Dict]:
    txt_path = _OA_DIR / f"{pmcid}.txt"
    if not txt_path.exists():
        return None
    text = txt_path.read_text(encoding="utf-8", errors="ignore")[:max_input_chars]
    if len(text) < 500:
        return None
    llm = llm or get_llm_client(task="qa")
    try:
        raw = llm.generate(text, system_prompt=_PROMPT, max_tokens=900) or ""
    except Exception as e:
        _log.warning("[extract] %s LLM fail: %s", pmcid, e)
        return None
    # parse JSON (LLM 종종 ```json wrap)
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"): raw = raw[4:]
        raw = raw.strip("` \n")
    try:
        d = json.loads(raw)
    except Exception:
        # 양식 잘못 — 일부 회복 시도
        s = raw.find("{"); e = raw.rfind("}")
        if s >= 0 and e > s:
            try: d = json.loads(raw[s:e+1])
            except Exception: return None
        else: return None
    d["pmcid"] = pmcid
    d["source_chars"] = len(text)
    return d


def save_one(d: Dict):
    conn = _init_cache()
    conn.execute("""INSERT OR REPLACE INTO structured
        (pmcid, pico_json, grade, excluded_subgroup, limitation,
         practice_implication, conflict, extracted_at, source_chars)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (d.get("pmcid"),
         json.dumps(d.get("pico", {}), ensure_ascii=False),
         d.get("grade"),
         d.get("excluded_subgroup"),
         d.get("limitation"),
         d.get("practice_implication"),
         d.get("conflict"),
         time.time(),
         d.get("source_chars", 0)))
    conn.commit()
    conn.close()


def batch_extract(*, limit: Optional[int] = None, skip_existing: bool = True) -> Dict:
    """전체 OA papers에 대해 idempotent 추출."""
    conn = _init_cache()
    cur = conn.cursor()
    cur.execute("SELECT pmcid FROM structured")
    done = {r[0] for r in cur.fetchall()}
    conn.close()

    pmcids: List[str] = []
    manifest = sqlite3.connect(str(_OA_DIR / "manifest.sqlite"))
    for row in manifest.execute("SELECT pmcid FROM papers"):
        pmcid = row[0]
        if skip_existing and pmcid in done:
            continue
        pmcids.append(pmcid)
    if limit:
        pmcids = pmcids[:limit]

    llm = get_llm_client(task="qa")
    t0 = time.time()
    ok, fail = 0, 0
    for i, pmcid in enumerate(pmcids, 1):
        d = extract_one(pmcid, llm=llm)
        if d:
            save_one(d); ok += 1
        else: fail += 1
        if i % 25 == 0:
            _log.info("[extract] %d/%d ok=%d fail=%d (%.0fs)",
                       i, len(pmcids), ok, fail, time.time() - t0)
    _log.info("[extract] done: ok=%d fail=%d / %.0fs", ok, fail, time.time() - t0)
    return {"ok": ok, "fail": fail, "skipped_existing": len(done), "elapsed": time.time() - t0}


def structured_retrieve(*, grade_min: Optional[str] = None,
                         pmcids: Optional[List[str]] = None,
                         limit: int = 8) -> List[Dict]:
    """저장된 구조화 필드 검색. paper_writer가 RAG raw chunk 대신 호출."""
    if not _CACHE_DB.exists():
        return []
    conn = sqlite3.connect(str(_CACHE_DB))
    conn.row_factory = sqlite3.Row
    q = "SELECT * FROM structured WHERE 1=1"
    args = []
    if grade_min:
        order = ["high", "moderate", "low", "very-low"]
        idx = order.index(grade_min)
        q += f" AND grade IN ({','.join('?' * (idx+1))})"
        args.extend(order[:idx+1])
    if pmcids:
        q += f" AND pmcid IN ({','.join('?' * len(pmcids))})"
        args.extend(pmcids)
    q += " LIMIT ?"
    args.append(limit)
    rows = conn.execute(q, args).fetchall()
    out = []
    for r in rows:
        out.append({
            "pmcid": r["pmcid"],
            "pico": json.loads(r["pico_json"] or "{}"),
            "grade": r["grade"],
            "excluded_subgroup": r["excluded_subgroup"],
            "limitation": r["limitation"],
            "practice_implication": r["practice_implication"],
        })
    conn.close()
    return out


__all__ = ["extract_one", "save_one", "batch_extract", "structured_retrieve"]
