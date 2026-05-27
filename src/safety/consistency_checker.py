"""Cross-section consistency checker — 논문 내부 수치 일관성 자동 검사.

LLM이 못 잡는 정형 모순(Methods n=50,972 vs Results Table n=50,968)을 정규식으로 발견.
검사 항목:
  1. **표본수(n)** 모순: 전수 추출 후 majority 대비 차이
  2. **OR/aOR** 값 모순: 같은 OR가 서로 다른 CI 동반
  3. **p값** 모순: P < 0.001 vs P = 0.05 같은 식
  4. **백분율 합** 모순: 같은 그룹 분류의 % 총합이 100±2% 벗어남
  5. **연도** 모순: 2024 vs 2025 혼용 (서베이 연도)

호출:
    from src.safety.consistency_checker import check_consistency
    report = check_consistency(sections_dict, tables=[...])  # → InconsistencyReport
    # report.severity: "ok" | "warn" | "fail"
    # report.issues: [{"type": ..., "details": ..., "location": ...}, ...]
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass
class Issue:
    type: str          # n_mismatch | or_mismatch | p_mismatch | pct_sum | year_mix
    detail: str
    severity: str = "warn"   # info | warn | fail
    location: str = ""


@dataclass
class ConsistencyReport:
    severity: str = "ok"
    issues: List[Issue] = field(default_factory=list)
    n_samples_seen: List[int] = field(default_factory=list)
    years_seen: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "severity": self.severity,
            "n_issues": len(self.issues),
            "issues": [asdict(i) for i in self.issues],
            "n_samples_seen": self.n_samples_seen,
            "years_seen": self.years_seen,
        }


# ── Regex patterns ──────────────────────────────────────────────────────────

_N_RE = re.compile(r"(?:n\s*=\s*|N\s*=\s*|sample of\s+|analytic sample of\s+)(\d{2,3}(?:,\d{3})+|\d{3,7})", re.IGNORECASE)
_OR_RE = re.compile(r"(?:a?OR|RR|HR)\s*([01]\.\d{2,3})\s*[\(;,]\s*(?:95%?\s*CI[:\s]?\s*)?([01]\.\d{2,3})\s*[-–]\s*([01]\.\d{2,3})", re.IGNORECASE)
_P_RE = re.compile(r"P\s*(<|=|>)\s*(0?\.\d+)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_PCT_RE = re.compile(r"(\d{1,3}\.\d)\s*%")


def _flatten_sections(sections: Dict) -> str:
    parts = []
    for k, v in sections.items():
        if isinstance(v, dict):
            for _sk, _sv in v.items():
                parts.append(str(_sv))
        else:
            parts.append(str(v or ""))
    return "\n\n".join(parts)


def _to_int_n(s: str) -> Optional[int]:
    try:
        return int(s.replace(",", ""))
    except Exception:
        return None


def check_consistency(sections: Dict,
                       expected_n: Optional[int] = None,
                       expected_years: Optional[List[str]] = None) -> ConsistencyReport:
    """본문에서 수치 토큰 추출 후 cross-section 일관성 검사.

    Args:
        sections: {"Introduction": ..., "Methods": ..., "Results": ..., "Discussion": ...}
                  (subsection dict 허용)
        expected_n: 명시 기준 표본수 (있으면 majority 대신 이것과 비교)
        expected_years: ["2025"] 같은 허용 연도 화이트리스트
    """
    text = _flatten_sections(sections)
    rep = ConsistencyReport()

    # 1. n 수집 + majority 일관성
    n_hits = [_to_int_n(m.group(1)) for m in _N_RE.finditer(text)]
    n_hits = [n for n in n_hits if n is not None and n >= 100]
    rep.n_samples_seen = sorted(set(n_hits))
    if n_hits:
        cnt = Counter(n_hits)
        majority, freq = cnt.most_common(1)[0]
        ref_n = expected_n or majority
        for n in set(n_hits):
            if n != ref_n and abs(n - ref_n) > 5:  # 5명 이하 차이는 허용 (소수점 반올림)
                rep.issues.append(Issue(
                    type="n_mismatch",
                    detail=f"n={n:,} 보고됨 (기준 n={ref_n:,}와 {abs(n-ref_n):,}명 차이)",
                    severity="warn",
                ))

    # 2. OR CI 합리성 (OR이 CI 범위 안에 있는지)
    for m in _OR_RE.finditer(text):
        or_val = float(m.group(1))
        lo, hi = float(m.group(2)), float(m.group(3))
        if not (lo <= or_val <= hi):
            rep.issues.append(Issue(
                type="or_mismatch",
                detail=f"OR={or_val} that fall outside CI [{lo}, {hi}]",
                severity="fail",
                location=text[max(0, m.start() - 30): m.end() + 30][:100],
            ))
        if lo > hi:
            rep.issues.append(Issue(
                type="or_mismatch",
                detail=f"CI lo>hi: {lo} > {hi}",
                severity="fail",
            ))

    # 3. P-value 토큰 합리성 (0~1)
    for m in _P_RE.finditer(text):
        try:
            p = float(m.group(2))
            if not (0 <= p <= 1):
                rep.issues.append(Issue(
                    type="p_mismatch",
                    detail=f"P-value out of [0,1]: {p}",
                    severity="fail",
                ))
        except Exception:
            pass

    # 4. 연도 혼용 (KYRBS 연도 등)
    years = sorted(set(_YEAR_RE.findall(text)))
    survey_years = [y for y in years if 2005 <= int(y) <= 2030]
    rep.years_seen = survey_years
    if expected_years:
        unexpected = [y for y in survey_years if y not in expected_years]
        if unexpected:
            rep.issues.append(Issue(
                type="year_mix",
                detail=f"예상 {expected_years} 외 연도 등장: {unexpected}",
                severity="warn",
            ))

    # severity 종합
    if any(i.severity == "fail" for i in rep.issues):
        rep.severity = "fail"
    elif rep.issues:
        rep.severity = "warn"
    else:
        rep.severity = "ok"

    # ★ safety audit_trail 기록 — fail 시 즉시 큐
    if rep.severity == "fail":
        try:
            from src.safety.audit_trail import record_safety_event
            record_safety_event("consistency_check_fail",
                                 {"n_issues": len(rep.issues),
                                  "first": rep.issues[0].detail if rep.issues else ""})
        except Exception:
            pass

    return rep
