"""Provenance Guard — "근거 없는 문장은 출력 금지" 하드 검증 레이어.

핵심 원칙 (외부 진단 2026-06-13):
  논문 에이전트의 killer 리스크 = 조작된 인용·통계. 검증 패스로 차단해야
  "툭툭 완성"이 위험 아니라 자산이 된다.

3축:
  1. citation_provenance  — 모든 [PMID:xxx]가 실재 (graph.json 또는 RAG hit)
  2. stat_provenance      — 모든 OR/CI/p/n 숫자가 stat_result에서 추적
  3. claim_provenance     — 강한 주장 문장(causes/significantly/first study to)이
                              RAG context에서 근거 인용을 동반

usage:
    from src.safety.provenance_guard import audit, AuditResult
    audit_result = audit(draft, stat_result=stats, rag_context=rag_ctx,
                          rag_pmids=["38542705", "40871678"])
    if not audit_result.ok:
        # reject 또는 사용자에 inline 경고
        for issue in audit_result.issues:
            print(issue.severity, issue.kind, issue.detail)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

ROOT = Path(__file__).resolve().parent.parent.parent

# 강한 주장 패턴 — 근거 동반 필수
_STRONG_CLAIM_PATTERNS = [
    r"\bcauses?\b",
    r"\b(?:significantly|substantially)\s+(?:improves?|increases?|reduces?|decreases?)\b",
    r"\bfor the first time\b(?!\s+to our knowledge)",
    r"\bdefinitely\s+(?:shows?|proves?|demonstrates?)\b",
    r"\bproves?\s+that\b",
    r"\beradicates?\b",
    r"\brevolutioniz(?:es?|ed|ing)\b",
]


@dataclass
class Issue:
    severity: str        # "block" | "warn" | "info"
    kind: str            # "fabricated_citation" | "untraceable_stat" | "unsupported_claim"
    detail: str
    location_excerpt: str = ""


@dataclass
class AuditResult:
    ok: bool
    issues: List[Issue] = field(default_factory=list)
    citation_realism_rate: float = 1.0
    stat_traceability_rate: float = 1.0
    strong_claim_count: int = 0
    citations_total: int = 0
    stats_total: int = 0

    def summary(self) -> str:
        return (
            f"provenance: {'OK' if self.ok else 'BLOCK'} | "
            f"citation_realism={self.citation_realism_rate:.1%} "
            f"({self.citations_total} cites) | "
            f"stat_traceability={self.stat_traceability_rate:.1%} "
            f"({self.stats_total} stats) | "
            f"strong_claims={self.strong_claim_count} | "
            f"issues={len(self.issues)}"
        )


# ──────────────────────────────────────────────────────────────────────
# Axis 1: citation provenance
# ──────────────────────────────────────────────────────────────────────

def _load_graph_pmids() -> set:
    try:
        import json
        g = json.loads((ROOT / "data" / "knowledge_graph" / "graph.json")
                          .read_text(encoding="utf-8"))
        return {str(n["pmid"]) for n in g.get("nodes", [])
                if n.get("type") == "paper" and n.get("pmid")}
    except Exception:
        return set()


def _check_citation_provenance(draft: str, rag_pmids: List[str]) -> tuple[float, List[Issue], int]:
    pmids_in_text = set(re.findall(r"\[PMID:(\d+)\]", draft))
    if not pmids_in_text:
        return 1.0, [], 0
    known = _load_graph_pmids() | set(str(p) for p in (rag_pmids or []))
    real = pmids_in_text & known
    fake = pmids_in_text - known
    issues: List[Issue] = []
    for pmid in sorted(fake):
        # 본문에서 해당 PMID가 등장한 첫 위치
        m = re.search(rf"\[PMID:{re.escape(pmid)}\]", draft)
        excerpt = draft[max(0, (m.start() if m else 0) - 60):
                          (m.end() if m else 60) + 60] if m else ""
        issues.append(Issue(
            severity="block",
            kind="fabricated_citation",
            detail=f"PMID:{pmid} 가 graph + RAG 양쪽에 없음 — 환각 의심",
            location_excerpt=excerpt,
        ))
    rate = len(real) / len(pmids_in_text)
    return rate, issues, len(pmids_in_text)


# ──────────────────────────────────────────────────────────────────────
# Axis 2: stat provenance
# ──────────────────────────────────────────────────────────────────────

_NUMBER_NEAR_STAT = re.compile(
    r"(?:OR|aOR|HR|RR|odds ratio)\s*[=:]?\s*([\d.]+)|"
    r"95%\s*CI\s*[:=]?\s*\[?([\d.,\s-]+)\]?|"
    r"p\s*[<>=]\s*(0?\.\d+)|"
    r"n\s*=\s*([\d,]+)",
    re.IGNORECASE,
)


def _check_stat_provenance(draft: str, stat_result: Optional[dict]) -> tuple[float, List[Issue], int]:
    matches = _NUMBER_NEAR_STAT.findall(draft)
    flat = [v.strip(", []") for tup in matches for v in tup if v.strip(", []")]
    if not flat:
        return 1.0, [], 0
    if not stat_result:
        # 통계 결과 미제공 — 숫자가 검증 불가
        return 0.0, [Issue(
            severity="warn", kind="untraceable_stat",
            detail=f"{len(flat)}개 통계 숫자가 본문에 있지만 stat_result 미제공 — 모두 검증 불가",
        )], len(flat)

    # 양식 양식 양식 양식 양식 양식: stat_consistency 모듈에 위임
    try:
        from src.diagnostics.stat_consistency import verify_stat_consistency
        rep = verify_stat_consistency(draft, stat_result)
        rate = rep.get("score", 0.0) / 100.0 if rep.get("score", 0.0) > 1 else rep.get("score", 0.0)
        issues: List[Issue] = []
        for h in rep.get("hallucinated_values", []) or []:
            issues.append(Issue(severity="block", kind="untraceable_stat",
                                  detail=f"숫자 {h}가 stat_result에 없음 — 환각 의심"))
        return rate, issues, len(flat)
    except Exception as e:
        return 0.0, [Issue(severity="warn", kind="untraceable_stat",
                              detail=f"stat_consistency 호출 실패: {e}")], len(flat)


# ──────────────────────────────────────────────────────────────────────
# Axis 3: claim provenance
# ──────────────────────────────────────────────────────────────────────

def _check_claim_provenance(draft: str) -> tuple[int, List[Issue]]:
    issues: List[Issue] = []
    count = 0
    for pat in _STRONG_CLAIM_PATTERNS:
        for m in re.finditer(pat, draft, re.IGNORECASE):
            count += 1
            # 같은 문장 안에 [PMID:xxx] 또는 [n] 있나
            sent_start = draft.rfind(".", 0, m.start()) + 1
            sent_end = draft.find(".", m.end())
            if sent_end == -1:
                sent_end = len(draft)
            sentence = draft[sent_start:sent_end]
            has_cite = bool(re.search(r"\[(?:PMID:)?\d+\]", sentence))
            if not has_cite:
                issues.append(Issue(
                    severity="warn", kind="unsupported_claim",
                    detail=f"강한 주장 '{m.group(0)}'에 인용 없음 — 근거 부재",
                    location_excerpt=sentence.strip()[:120],
                ))
    return count, issues


# ──────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────

def audit(draft: str, *, stat_result: Optional[dict] = None,
            rag_context: str = "", rag_pmids: Optional[List[str]] = None,
            block_threshold: float = 0.7) -> AuditResult:
    """3축 검증 후 AuditResult 반환.

    Args:
        draft: 검증 대상 manuscript draft
        stat_result: 통계 분석 결과 dict (없으면 stat_provenance 0점)
        rag_context: RAG retrieve 결과 (PMID 추출 보조)
        rag_pmids: RAG hit PMID 명시 (graph 외 추가 화이트리스트)
        block_threshold: citation_realism이 이 값 미만이면 ok=False (block)
    """
    # RAG context에서 PMID 추출
    if rag_context and not rag_pmids:
        rag_pmids = list(set(re.findall(r"PMID:(\d+)", rag_context)))

    cite_rate, cite_issues, cite_total = _check_citation_provenance(draft, rag_pmids or [])
    stat_rate, stat_issues, stat_total = _check_stat_provenance(draft, stat_result)
    claim_count, claim_issues = _check_claim_provenance(draft)

    all_issues = cite_issues + stat_issues + claim_issues
    has_block = any(i.severity == "block" for i in all_issues)
    cite_pass = cite_rate >= block_threshold
    ok = cite_pass and not has_block

    return AuditResult(
        ok=ok,
        issues=all_issues,
        citation_realism_rate=cite_rate,
        stat_traceability_rate=stat_rate,
        strong_claim_count=claim_count,
        citations_total=cite_total,
        stats_total=stat_total,
    )
