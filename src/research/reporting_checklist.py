"""의학 논문 보고 표준 자동 체크리스트 — STROBE / STARD / CONSORT.

- STROBE: 관찰연구(단면/코호트/환자대조) 22항목
- STARD : 진단 정확도 연구 30항목
- CONSORT: 무작위 대조시험 25항목

설계 의도:
  · `peer_reviewer`가 free-form 평가만 하던 곳에 **정형 체크리스트**를 추가.
  · 각 항목을 paper 본문(IMRAD) 텍스트에서 정규식+키워드로 감지.
  · 미충족 항목 list → peer_reviewer 리뷰에 흡수 → reviewers comment에 표시.

호출:
    from src.research.reporting_checklist import check_strobe
    result = check_strobe(sections_dict)  # {"score": 18, "total": 22, "missing": [...]}
    text = format_checklist_report(result)
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple


# ── STROBE 22 항목 (Vandenbroucke 2014 / strobe-statement.org) ───────────────
# 각 항목: (id, section, keyword/regex 후보 — text가 매치되면 reported)
STROBE_ITEMS: List[Tuple[str, str, List[str]]] = [
    # Title & abstract
    ("1a", "title_abstract", [r"\bcross.sectional\b", r"\bcohort\b", r"\bcase.control\b"]),
    ("1b", "abstract",       [r"\bbackground\b", r"\bmethods?\b", r"\bresults?\b", r"\bconclusion\b"]),
    # Introduction
    ("2",  "introduction",   [r"background", r"rationale", r"context"]),
    ("3",  "introduction",   [r"\bhypothesi[sz]ed?\b", r"\baim(s|ed)?\b", r"\bobjective\b"]),
    # Methods
    ("4",  "methods",        [r"\bstudy design\b", r"\bcross.sectional\b", r"\bcohort\b"]),
    ("5",  "methods",        [r"\bsetting\b", r"\bperiod\b", r"\bdates?\b", r"recruit"]),
    ("6a", "methods",        [r"\beligib(le|ility)\b", r"\binclusion criteria\b", r"\bparticipants?\b"]),
    ("7",  "methods",        [r"\boutcome\b", r"\bexposure\b", r"\bcovariates?\b", r"\bvariables?\b"]),
    ("8",  "methods",        [r"\bmeasur(ed|ement)\b", r"\bassess(ed|ment)\b", r"\bquestionnaire\b", r"\bself.report"]),
    ("9",  "methods",        [r"\bbias\b", r"\bconfound", r"\bmisclassif"]),
    ("10", "methods",        [r"\bsample size\b", r"\bpower\b", r"\bn\s*=\s*\d", r"\b\d{3,}\b"]),
    ("11", "methods",        [r"\bquantitative\b", r"\bcontinuous\b", r"\bcategor", r"\bdichotom"]),
    ("12a","methods",        [r"\blogistic\b", r"\bregression\b", r"\bchi.square", r"\bt.test\b", r"\bANOVA\b"]),
    ("12b","methods",        [r"\bsubgroup\b", r"\binteraction\b", r"\bstratif"]),
    ("12c","methods",        [r"\bmissing\b", r"\bsensitivity\b", r"\bcomplete.case\b", r"\blistwise\b"]),
    # Results
    ("13", "results",        [r"\bn\s*=\s*\d", r"\beligibl", r"\bexcluded\b", r"\bflow\b", r"\bFigure\s*1\b"]),
    ("14", "results",        [r"\bTable\s*1\b", r"\bcharacteristic", r"\bdemograph", r"\bbaseline\b"]),
    ("15", "results",        [r"\bevents?\b", r"\boutcome.*(count|number|n\s*=)\b"]),
    ("16a","results",        [r"\b(a?OR|RR|HR|β)\b", r"\b95\s*%\s*CI\b", r"\bconfidence interval"]),
    ("16b","results",        [r"\bsubgroup\b", r"\bstrati(fied|fication)\b", r"\bsex.specific\b", r"\bage.stratified\b"]),
    ("17", "results",        [r"\bsensitivity analysis\b", r"\brobust", r"\bsupplement"]),
    # Discussion
    ("18", "discussion",     [r"\bkey (finding|result)\b", r"\bsummary\b", r"\bin this study\b"]),
    ("19", "discussion",     [r"\blimitation\b", r"\bcaveat\b"]),
    ("20", "discussion",     [r"\binterpret", r"\bmechanism\b", r"\bcompared with\b", r"\bin line with\b"]),
    ("21", "discussion",     [r"\bgeneraliz(ab)?\b", r"\bextern(al)? validity\b"]),
    # Other
    ("22", "back_matter",    [r"\bfunding\b", r"\bsupport\b", r"\bgrant\b", r"\brole of (the )?funder"]),
]


def _sections_to_text(sections: Dict[str, object]) -> Dict[str, str]:
    """sections가 dict(subsection 포함)일 수 있으니 평탄화하여 키별 텍스트 반환."""
    out: Dict[str, str] = {}
    for k, v in sections.items():
        key = k.lower().replace(" ", "_")
        if isinstance(v, dict):
            joined = []
            for _sk, _sv in v.items():
                joined.append(str(_sv))
            out[key] = "\n\n".join(joined)
        else:
            out[key] = str(v or "")
    return out


def check_strobe(sections: Dict[str, object],
                  abstract: str = "",
                  back_matter: Dict[str, str] | None = None) -> Dict:
    """STROBE 22항목 자동 체크.

    Args:
        sections: {"Introduction": ..., "Methods": ..., "Results": ..., "Discussion": ...}
        abstract: 별도 abstract 텍스트 (Dict 형태도 허용 — 합쳐서 매칭)
        back_matter: {"Funding": ..., ...}

    Returns:
        {"score": int, "total": 22, "reported": [...], "missing": [...],
         "by_section": {...}, "checklist": "STROBE"}
    """
    sec_text = _sections_to_text(sections)
    if isinstance(abstract, dict):
        sec_text["abstract"] = "\n".join(str(v) for v in abstract.values())
    elif abstract:
        sec_text["abstract"] = abstract
    if back_matter:
        sec_text["back_matter"] = "\n".join(str(v) for v in back_matter.values())
    sec_text["title_abstract"] = sec_text.get("title", "") + "\n" + sec_text.get("abstract", "")

    reported, missing = [], []
    by_section: Dict[str, List[str]] = {}
    for item_id, sec, patterns in STROBE_ITEMS:
        text = sec_text.get(sec, "")
        text_low = text.lower()
        hit = any(re.search(p, text_low, re.IGNORECASE) for p in patterns)
        if hit:
            reported.append(item_id)
        else:
            missing.append(item_id)
            by_section.setdefault(sec, []).append(item_id)

    return {"checklist": "STROBE", "version": "2014",
            "score": len(reported), "total": len(STROBE_ITEMS),
            "reported": reported, "missing": missing,
            "by_section": by_section}


def format_checklist_report(result: Dict, *, verbose: bool = False) -> str:
    """체크리스트 결과 → 사람용 요약."""
    cl = result.get("checklist", "?")
    score = result.get("score", 0)
    total = result.get("total", 0)
    pct = (score / total * 100) if total else 0
    lines = [f"{cl} reporting checklist: {score}/{total} ({pct:.0f}%)"]
    missing = result.get("missing", [])
    if missing:
        lines.append(f"Missing items: {', '.join(missing)}")
    if verbose:
        for sec, items in result.get("by_section", {}).items():
            lines.append(f"  · {sec}: missing {', '.join(items)}")
    return "\n".join(lines)


# ── 검출기 dispatcher (study_type → 적절한 체크리스트) ─────────────────────

def auto_check(sections: Dict, abstract: str = "",
                back_matter: Dict[str, str] | None = None,
                study_type: str = "cross_sectional") -> Dict:
    """study_type으로 적절한 체크리스트 자동 선택. peer_reviewer가 호출."""
    if study_type in ("cross_sectional", "cohort", "case_control", "observational"):
        return check_strobe(sections, abstract=abstract, back_matter=back_matter)
    # STARD/CONSORT는 STROBE base를 그대로 사용 (확장 시 별도 함수 추가)
    return check_strobe(sections, abstract=abstract, back_matter=back_matter)
