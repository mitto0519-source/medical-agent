"""Humanize Extractor — 12,301편 본문에서 문장 단위 humanization signal을 학습.

사용자 비전 (2026-06-01):
    "단순히 template 잡는 것 이상으로 — 문장을 의학적 논문구조로 표현하는 방법,
     통계 table & figure 해석하는 방법, 인사이트 통합 표현, 문체 강조점 디테일,
     humanize 포인트를 다른 논문에서 대량 학습해야 한다."

typology(paper_typology.py)는 섹션별 도입/전개 유형 = 골격.
본 모듈은 더 미시적인 단위 = 문장 단위 humanization signal:

    1. STATISTICAL REPORTING — "X was associated with a [N]% higher odds (aOR, 1.10; 95% CI, 1.05-1.16)"
       → OR/HR/RR + CI + P 문장 패턴 (수십 양식)

    2. FIGURE/TABLE CITATION — "As shown in Table 2, ..." / "Figure 1 illustrates ..."
       → 본문에서 표/그림 인용하는 자연 문장 패턴

    3. HEDGED CLAIM — "These findings suggest, while ..., they may also ..."
       → may / might / appear / seem / indicate / suggest 다양성

    4. EMPHASIS INJECTION — "Importantly," / "Of note," / "Notably," / "Crucially,"
       → 강조 부사구 (LLM이 잘 못 씀)

    5. METHODOLOGICAL DECISION — "We chose to ... because ..." / "We restricted ... to ..."
       → 작가의 결정·근거 표현 (humanization 핵심 신호)

    6. SYNTHETIC BRIDGE — "Taken together," / "Collectively," / "In aggregate,"
       → 여러 finding 통합 문장

    7. SPECIFIC DETAIL — "Of these, 12 had missing data" / "We further excluded 86 ..."
       → 구체 숫자 디테일 (LLM은 추상화 경향)

API:
    build_humanize_catalog(force=False, limit=None) → HumanizeCatalog
    get_humanize_block(*, sample_per_kind=2) → paper_writer system_prompt 박을 블록
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_OA_DIR = Path("data/oa_papers")
_CATALOG_PATH = Path("data/medical_knowledge_seed/humanize_catalog.json")


# ── 문장 단위 분류 패턴 (휴리스틱, LLM 0) ──────────────────────────────

SENT_PATTERNS = {
    # 1. 통계 보고 — OR/HR/RR + CI/P
    "statistical_reporting": [
        r"\b(?:adjusted )?(?:odds|hazard|risk|incidence|prevalence)\s+ratios?\b.{0,80}\b\d+\.\d{1,3}\b",
        r"\b(?:aOR|aHR|OR|HR|RR|PR)\s*[,=:]?\s*\d+\.\d{1,3}\b.{0,40}\b(?:95\s*%?\s*CI|confidence interval)\b",
        r"\b\d+\.\d{1,3}\s*\(\s*95\s*%?\s*CI[,:]?\s*\d+\.\d{1,3}[\-–,\s]+\d+\.\d{1,3}\s*\)",
        r"\bP\s*(?:value)?\s*[<>=]\s*\.?\d+\.?\d*",
    ],
    # 2. Figure/Table 인용
    "figure_table_citation": [
        r"\b(?:as )?(?:shown|presented|illustrated|displayed|summarized) in (?:Table|Fig(?:ure)?)\s*\d",
        r"\b(?:Table|Fig(?:ure)?)\s*\d[A-Z]?\s+(?:shows|illustrates|presents|displays|summarizes)",
        r"\b(?:see|refer to)\s+(?:Table|Fig(?:ure)?|Supplement(?:ary)?)\s*(?:Table|Fig(?:ure)?)?\s*\d",
        r"\(\s*(?:Table|Fig(?:ure)?|Supplement(?:ary)?[^)]*)\s*\d[A-Z]?\s*\)",
    ],
    # 3. Hedged claim — 다양한 hedging 동사
    "hedged_claim": [
        r"\b(?:our|these|the present|the current)\s+(?:findings?|results?)\s+(?:suggest|indicate|imply|point to)\b",
        r"\b(?:may|might|could|appear(?:s)? to|seem(?:s)? to)\s+(?:reflect|account for|explain|underlie|contribute to)\b",
        r"\bremains? to be (?:determined|established|elucidated|investigated)\b",
        r"\b(?:although|while|whereas)\s+\w+.{0,80}\b(?:cannot|may not|does not|remains)\b",
    ],
    # 4. 강조 부사구 (humanization key signal)
    "emphasis_injection": [
        r"(?:^|\.\s|\;\s)(?:Importantly|Notably|Of note|Crucially|"
        r"Interestingly|Critically|Strikingly|Surprisingly|"
        r"Remarkably|Curiously),\s+[A-Z]",
    ],
    # 5. Methodological decision (작가의 결정 — 강력한 humanization)
    "methodological_decision": [
        r"\bwe\s+(?:chose|opted|decided|elected)\s+to\s+\w+.{0,60}\bbecause\b",
        r"\bwe\s+(?:restricted|limited|further excluded|additionally excluded)\s+\w+",
        r"\bwe\s+(?:performed|conducted|undertook)\s+\w+\s+(?:analyses?|sensitivity)\s+to\s+(?:assess|examine|test|address)\b",
        r"\bto\s+(?:assess|address|account for)\s+\w+,\s+we\s+(?:additionally|further|also)\s+\w+",
    ],
    # 6. Synthetic bridge (여러 finding 통합)
    "synthetic_bridge": [
        r"(?:^|\.\s)(?:Taken together|Collectively|In aggregate|Overall|"
        r"In sum|Together|On balance),\s+(?:these|our)\s+(?:findings?|results?|data|observations?)",
        r"\b(?:these|our)\s+(?:findings?|results?)\s+(?:are consistent with|extend|build on|complement)\b",
    ],
    # 7. Specific detail (구체 숫자 디테일)
    "specific_detail": [
        r"\bof\s+(?:these|whom|which),?\s+\d{1,4}\s+(?:had|were|reported|experienced|developed)\b",
        r"\b(?:we\s+(?:further\s+)?excluded|after excluding)\s+\d{1,4}\s+(?:participants?|adolescents?|adults?|patients?)\b",
        r"\b\d{1,4}\s+(?:were|had)\s+(?:missing|incomplete|unavailable|unable to)\b",
    ],
}


@dataclass
class HumanizeCatalog:
    built_at: str = ""
    n_papers_scanned: int = 0
    by_kind: Dict[str, List[Dict]] = field(default_factory=lambda: defaultdict(list))

    def stats(self) -> Dict[str, int]:
        return {k: len(v) for k, v in self.by_kind.items()}


# ── 문장 추출 (period boundary, 약식) ──────────────────────────────────

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\(])")


def _split_sentences(text: str) -> List[str]:
    """간이 sentence tokenization — period + 다음 대문자."""
    if not text:
        return []
    sents = _SENT_SPLIT.split(text)
    return [s.strip() for s in sents if len(s.strip()) > 30 and len(s.strip()) < 600]


def _classify_sentence(sent: str) -> List[str]:
    """문장에 매칭되는 모든 humanize kind 반환 (다중 가능)."""
    matched: List[str] = []
    for kind, patterns in SENT_PATTERNS.items():
        for p in patterns:
            if re.search(p, sent, re.IGNORECASE | re.DOTALL):
                matched.append(kind)
                break
    return matched


# ── 카탈로그 빌드 ──────────────────────────────────────────────────────

def build_humanize_catalog(*, force: bool = False, limit: Optional[int] = None,
                            max_per_kind: int = 80) -> HumanizeCatalog:
    """data/oa_papers 전체 본문에서 humanize 문장을 카탈로그."""
    import time as _t
    from datetime import datetime as _dt

    if _CATALOG_PATH.exists() and not force:
        try:
            d = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
            cat = HumanizeCatalog(
                built_at=d.get("built_at", ""),
                n_papers_scanned=d.get("n_papers_scanned", 0),
            )
            cat.by_kind = defaultdict(list)
            for k, v in d.get("by_kind", {}).items():
                cat.by_kind[k] = v
            _log.info("[Humanize] cached: total=%d kinds",
                       sum(len(v) for v in cat.by_kind.values()))
            return cat
        except Exception as e:
            _log.warning("[Humanize] cache load failed: %s — rebuilding", e)

    if not _OA_DIR.exists():
        raise FileNotFoundError(f"OA papers dir not found: {_OA_DIR}")

    cat = HumanizeCatalog(built_at=_dt.utcnow().isoformat() + "Z")
    txt_files = sorted(_OA_DIR.glob("PMC*.txt"))
    if limit:
        txt_files = txt_files[:limit]

    t0 = _t.time()
    # 카운트로 max 충족 후 빠른 종료
    kind_full = {k: False for k in SENT_PATTERNS}
    for i, tp in enumerate(txt_files):
        if i % 1000 == 0:
            _log.info("[Humanize] %d/%d (%.1fs) collected=%s",
                       i, len(txt_files), _t.time() - t0,
                       {k: len(v) for k, v in cat.by_kind.items()})
        if all(kind_full.values()):
            _log.info("[Humanize] all kinds saturated at %d papers", i)
            break
        try:
            text = tp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        pmcid = tp.stem
        for sent in _split_sentences(text):
            kinds = _classify_sentence(sent)
            for k in kinds:
                bucket = cat.by_kind[k]
                if len(bucket) < max_per_kind:
                    bucket.append({"pmcid": pmcid, "text": sent[:480]})
                    if len(bucket) >= max_per_kind:
                        kind_full[k] = True

    cat.n_papers_scanned = i + 1 if txt_files else 0

    _CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "built_at": cat.built_at,
        "n_papers_scanned": cat.n_papers_scanned,
        "by_kind": {k: v for k, v in cat.by_kind.items()},
    }
    _CATALOG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    _log.info("[Humanize] saved: %s (%.1fs) totals=%s",
               _CATALOG_PATH, _t.time() - t0, cat.stats())
    return cat


# ── system_prompt에 박을 humanize 블록 ─────────────────────────────────

def get_humanize_block(*, sample_per_kind: int = 2,
                        catalog: Optional[HumanizeCatalog] = None,
                        kinds: Optional[List[str]] = None) -> str:
    """paper_writer가 system_prompt에 박을 humanization 문장 카탈로그.

    LLM이 본문 작성 시 이 예문들의 cadence·디테일·hedging·강조 부사구를
    내부 reference로 사용. 단순 RAG 발췌나 typology 도입부와 다른 차원 =
    문장 단위 humanization 신호.
    """
    if catalog is None:
        try:
            catalog = build_humanize_catalog()
        except Exception:
            return ""
    if kinds is None:
        kinds = list(SENT_PATTERNS.keys())
    lines = ["## HUMANIZATION SIGNALS — sentence patterns from 12,301 PMC papers",
             "Mirror these *types* of sentences when appropriate. Do NOT copy verbatim.",
             "These are what make academic prose read as human-written, not LLM-generated.",
             ""]
    label_map = {
        "statistical_reporting": "Statistical reporting (OR/CI/P)",
        "figure_table_citation": "Figure/Table citation",
        "hedged_claim": "Hedged claim",
        "emphasis_injection": "Emphasis injection (Importantly, Of note, ...)",
        "methodological_decision": "Methodological decision (we chose ... because ...)",
        "synthetic_bridge": "Synthetic bridge (Taken together, Collectively)",
        "specific_detail": "Specific detail (Of these, N had ...)",
    }
    for k in kinds:
        hits = catalog.by_kind.get(k) or []
        if not hits:
            continue
        lines.append(f"### {label_map.get(k, k)}")
        for h in hits[:sample_per_kind]:
            ex = (h.get("text") or "").replace("\n", " ").strip()[:300]
            lines.append(f"  • [{h.get('pmcid','?')}] {ex}")
        lines.append("")
    return "\n".join(lines)


__all__ = [
    "build_humanize_catalog", "get_humanize_block",
    "HumanizeCatalog", "SENT_PATTERNS",
]
