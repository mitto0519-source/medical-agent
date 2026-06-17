"""Confidence Propagation Engine — per-component confidence aggregation.

MASTER_UPGRADE §3 #6: schema_v2.edge_confidence + peer_reviewer rubric already exist as primitives.
This module composes them into a per-Claim and per-Manuscript overall confidence.

Components (each 0.0-1.0):
    citation  — fraction of PMIDs that exist in our graph / verified upstream
    stat      — provenance + assumption pass rate (CI present, n adequate, design matches)
    novelty   — schema_v2.edge_confidence on the novel finding edge
    claim     — sentence-level grounding (does it have any evidence/dataset link?)

Overall = weighted geometric mean (so a single low-confidence component drags the total).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


_DEFAULT_WEIGHTS = {"citation": 0.30, "stat": 0.35, "novelty": 0.15, "claim": 0.20}


@dataclass
class ConfidenceReport:
    overall: float = 0.0
    components: Dict[str, float] = field(default_factory=dict)
    weights: Dict[str, float] = field(default_factory=lambda: dict(_DEFAULT_WEIGHTS))
    issues: List[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return {"overall": self.overall, "components": self.components,
                 "weights": self.weights, "issues": self.issues, "note": self.note}

    def as_block(self) -> str:
        lines = [f"Confidence overall: {self.overall:.2f}",
                  f"  citation : {self.components.get('citation',0):.2f}",
                  f"  stat     : {self.components.get('stat',0):.2f}",
                  f"  novelty  : {self.components.get('novelty',0):.2f}",
                  f"  claim    : {self.components.get('claim',0):.2f}"]
        if self.issues:
            lines.append("Issues:")
            for i in self.issues[:5]:
                lines.append(f"  - {i}")
        return "\n".join(lines)


# ── Component calculators ────────────────────────────────────────────────────

def citation_confidence(draft: str, *, verified_pmids: Optional[set] = None) -> float:
    """Fraction of inline PMIDs that exist in verified_pmids (e.g. RAG hits or graph)."""
    if not draft:
        return 0.0
    pmids = set(re.findall(r"PMID:?(\d+)", draft))
    if not pmids:
        return 0.0
    if not verified_pmids:
        return 0.5  # exist but unverified
    hits = pmids & set(str(p) for p in verified_pmids)
    return len(hits) / len(pmids) if pmids else 0.0


def stat_confidence(stat_result: Optional[dict]) -> float:
    """Has CI? Has p? n adequate? Design matches outcome? Each yes = +0.25."""
    if not isinstance(stat_result, dict):
        return 0.0
    score = 0.0
    if stat_result.get("ci_low") is not None and stat_result.get("ci_high") is not None:
        score += 0.25
    if stat_result.get("p") is not None or stat_result.get("p_value") is not None:
        score += 0.25
    n = stat_result.get("n") or stat_result.get("sample_size") or 0
    try:
        if int(n) >= 100:
            score += 0.25
    except Exception:
        pass
    design = (stat_result.get("design") or "").lower()
    if design in ("logistic", "cox", "linear", "glm", "cross_sectional", "longitudinal",
                   "case_control", "cohort", "rct"):
        score += 0.25
    return score


def novelty_confidence(novelty_result: Optional[dict]) -> float:
    """novelty_checker output → score in [0,1]. Falls back to 0.5 if structured score missing."""
    if not isinstance(novelty_result, dict):
        return 0.5
    s = novelty_result.get("novelty_score")
    try:
        v = float(s)
        return max(0.0, min(1.0, v))
    except Exception:
        return 0.5


def claim_confidence(claims: Optional[List[Dict]]) -> float:
    """Fraction of claims with at least one PMID or dataset link."""
    if not claims:
        return 0.0
    grounded = sum(1 for c in claims
                    if (c.get("pmids") or c.get("dataset_label") or c.get("node_id")))
    return grounded / len(claims)


# ── Aggregator ───────────────────────────────────────────────────────────────

def aggregate(*, draft: str = "",
                stat_result: Optional[dict] = None,
                novelty_result: Optional[dict] = None,
                verified_pmids: Optional[set] = None,
                claims: Optional[List[Dict]] = None,
                weights: Optional[Dict[str, float]] = None) -> ConfidenceReport:
    """Compose 4 components → ConfidenceReport. Empty inputs → 0 with explanatory issue."""
    w = dict(_DEFAULT_WEIGHTS)
    if weights:
        w.update(weights)

    comp = {
        "citation": citation_confidence(draft, verified_pmids=verified_pmids),
        "stat": stat_confidence(stat_result),
        "novelty": novelty_confidence(novelty_result),
        "claim": claim_confidence(claims),
    }

    # ★ 친절한 한국어 메시지 (의학 연구자가 의미 + 다음 행동 즉시 인지)
    issues: List[str] = []
    if comp["citation"] < 0.6:
        rate = int(comp["citation"] * 100)
        issues.append(
            f"📚 **인용 검증 부족** ({rate}%) — 본문에 박힌 PMID 중 절반 이상이 "
            f"RAG/그래프에서 미확인. 가짜 인용(hallucination) 위험. "
            f"→ 인용을 PubMed에서 직접 확인하거나, '/pubmed_search 주제'로 실시간 검증 권장."
        )
    if comp["stat"] < 0.5:
        issues.append(
            "📊 **통계 정보 미완** — 신뢰구간(95% CI)/p값/표본수(n)/연구설계 중 일부 누락. "
            "→ 본문에 'aOR 1.04 (95% CI 1.02-1.06, p=0.001, n=12,345)' 양식으로 채우거나 "
            "/stat_run 으로 stat_bridge 분석 실행."
        )
    if comp["novelty"] < 0.3:
        issues.append(
            "🔍 **신규성 낮음** — 비슷한 주제 선행 연구 많음. "
            "→ 각도 재구성 권장 (예: 다른 outcome, 다른 subgroup, 또는 mediator 분석). "
            "/novelty 명령으로 gap 분석 가능."
        )
    if comp["claim"] < 0.5:
        rate = int((1 - comp["claim"]) * 100)
        issues.append(
            f"💭 **근거 없는 문장 {rate}%** — 절반 이상의 문장에 인용·데이터 출처 없음. "
            f"→ 주장마다 [PMID:xxx] 인라인 인용 추가, 통계는 본인 분석 결과 직접 박기."
        )

    # Weighted geometric mean (penalizes single low component)
    eps = 1e-6
    log_sum = 0.0
    w_sum = 0.0
    for k, v in comp.items():
        wk = w.get(k, 0.0)
        log_sum += wk * math.log(max(v, eps))
        w_sum += wk
    overall = math.exp(log_sum / w_sum) if w_sum else 0.0

    return ConfidenceReport(
        overall=round(overall, 3),
        components={k: round(v, 3) for k, v in comp.items()},
        weights=w,
        issues=issues,
        note="weighted geometric mean (single low component caps overall)",
    )


__all__ = ["ConfidenceReport", "citation_confidence", "stat_confidence",
            "novelty_confidence", "claim_confidence", "aggregate"]
