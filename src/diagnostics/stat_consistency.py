"""Stat Consistency Checker — 논문 텍스트 통계값 ↔ 실제 분석결과 대조.

미싱링크 보강: CapabilityBench는 "OR이라는 글자가 있나"만 봤다(정규식 존재 확인).
이 모듈은 "그 OR 값이 실제 StatBridge 결과와 맞나"를 대조한다.
→ 환각된 통계(stat엔 OR=2.3인데 논문엔 OR=3.5)와 누락을 탐지.

LLM 무관 — 순수 정규식/수치 대조. 크레딧 없이도 작동.
"""
from __future__ import annotations

import re
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_TOL = 0.05  # OR 값 일치 허용 오차 (반올림 표기 차이 흡수)


def _extract_or_values(text: str) -> List[float]:
    """논문 텍스트에서 OR 맥락의 숫자를 모두 추출."""
    vals: List[float] = []
    # aOR=2.34, OR 2.34, OR = 2.34, odds ratio 2.34
    for m in re.finditer(r'(?:a?OR|odds\s+ratio)\s*[=:]?\s*(\d+\.\d+)', text, re.I):
        vals.append(round(float(m.group(1)), 2))
    # "2.34 (95% CI 1.20–3.50)" — CI 앞 숫자
    for m in re.finditer(r'(\d+\.\d+)\s*\(\s*95\s*%\s*CI', text, re.I):
        vals.append(round(float(m.group(1)), 2))
    return vals


def _value_present(target: float, candidates: List[float], tol: float = _TOL) -> bool:
    """target이 candidates 중 하나와 tol 이내로 일치하는가."""
    return any(abs(target - c) <= tol for c in candidates)


def verify_stat_consistency(draft: str, stat_result: Dict) -> Dict:
    """논문 초안의 통계값이 실제 분석결과와 일치하는지 검증.

    Returns
    -------
    {
      "score": 0-100,           # 유의 변수 OR 반영률
      "checked": int,           # 검증한 유의 변수 수
      "matched": [{label, or}], # 논문에 정확히 반영된 것
      "missing": [{label, or}], # 분석엔 있으나 논문에 누락된 것
      "hallucinated": [float],  # 논문엔 있으나 분석엔 없는 OR (환각 의심)
      "note": str,
    }
    """
    model_vars = stat_result.get("model_vars", []) or []
    sig_vars = [v for v in model_vars if v.get("significant")]

    text_ors = _extract_or_values(draft)

    if not sig_vars:
        return {
            "score": 100.0, "checked": 0,
            "matched": [], "missing": [], "hallucinated": [],
            "note": "유의한 독립변수 없음 — 대조 생략",
        }

    matched, missing = [], []
    stat_or_values = []
    for v in sig_vars:
        or_val = v.get("or_value")
        if or_val is None:
            continue
        or_val = round(float(or_val), 2)
        stat_or_values.append(or_val)
        label = v.get("label") or v.get("variable") or "?"
        entry = {"label": label, "or": f"{or_val:.2f}"}
        if _value_present(or_val, text_ors):
            matched.append(entry)
        else:
            missing.append(entry)

    # 환각 의심: 논문 텍스트의 OR 중 어떤 분석결과와도 안 맞는 값
    hallucinated = sorted({
        c for c in text_ors
        if not _value_present(c, stat_or_values)
    })

    checked = len(matched) + len(missing)
    score = round(len(matched) / checked * 100, 1) if checked else 100.0

    note_parts = []
    if missing:
        note_parts.append(f"누락 {len(missing)}건")
    if hallucinated:
        note_parts.append(f"환각의심 {len(hallucinated)}건")
    note = "통계 일치 양호" if not note_parts else " / ".join(note_parts)

    result = {
        "score": score,
        "checked": checked,
        "matched": matched,
        "missing": missing,
        "hallucinated": hallucinated,
        "note": note,
    }
    if missing or hallucinated:
        _log.warning(
            "[StatConsistency] 일치율 %.0f%% — 누락 %d, 환각의심 %d",
            score, len(missing), len(hallucinated),
        )
    else:
        _log.info("[StatConsistency] 통계 일치율 %.0f%% (%d변수)", score, checked)
    return result


def format_consistency_report(result: Dict) -> str:
    """검증 결과를 사람이 읽는 리포트로."""
    lines = [f"통계 일치율: {result['score']:.0f}% ({result['checked']}개 유의변수 검증)"]
    if result["missing"]:
        lines.append("⚠️ 논문에 누락된 분석결과:")
        for m in result["missing"]:
            lines.append(f"  - {m['label']}: OR={m['or']} (분석엔 있으나 본문 미반영)")
    if result["hallucinated"]:
        lines.append("⚠️ 환각 의심 (분석결과에 없는 OR이 본문에 등장):")
        for h in result["hallucinated"]:
            lines.append(f"  - OR={h:.2f}")
    if not result["missing"] and not result["hallucinated"]:
        lines.append("✅ 본문 통계값이 실제 분석결과와 일치")
    return "\n".join(lines)
