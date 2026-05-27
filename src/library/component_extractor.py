"""ComponentExtractor — 논문 본문에서 reusable microcomponent 추출.

정규식 기반 (LLM 비용 0). KnowledgeOrchestrator.ingest 안에서 자동 호출.

추출 대상 (`COMPONENT_KINDS`):
  - hedging, stat_report, transition, topic_sentence, methods_boilerplate,
    mechanism_phrase, limitation, figure_caption_pattern, table_caption_pattern,
    subgroup_sentence, citation_cluster_pattern

호출:
    from src.library.component_extractor import extract_all
    comps = extract_all(text, source_pmid="38123456", author_style="yoosun_cho")
    # comps: List[PaperComponent]
    from src.library.components import get_library
    get_library().add_many(comps)
"""
from __future__ import annotations

import re
from typing import List, Optional

from src.config.logging_config import get_logger
from src.library.components import PaperComponent, make_component

_log = get_logger(__name__)


# ── Regex patterns (literature-aware) ────────────────────────────────────────

_HEDGING_VOCAB = [
    r"\bremains? (?:largely )?(?:underexplored|uncharacterized|unclear)\b",
    r"\b(?:may|might|could) (?:be|reflect|suggest|underlie|mediate)\b",
    r"\bis consistent with\b", r"\bis in line with\b", r"\bappears? to\b",
    r"\b(?:potentially|possibly) (?:mediated|driven|explained)\b",
    r"\baligns? with\b", r"\bvaries? from (?:moderate|low|substantial)\b",
    r"\bindependently associated with\b", r"\bshows? comparable\b",
]
_HEDGING_RE = re.compile("|".join(_HEDGING_VOCAB), re.IGNORECASE)

# aOR 1.27 (95% CI 1.03-1.56; P = 0.026)
_STAT_REPORT_RE = re.compile(
    r"\b(?:a?OR|RR|HR|β)\s*[=:]?\s*[01]\.\d{2,3}"
    r"\s*[\(;,]\s*(?:95%?\s*CI[:\s]?\s*)?[01]\.\d{2,3}\s*[-–to]+\s*[01]\.\d{2,3}"
    r"(?:[;,)]\s*(?:P\s*(?:for\s*(?:trend|interaction)\s*)?[<=]\s*0?\.\d+)?\)?",
    re.IGNORECASE,
)

# Transition (단어 시작)
_TRANSITION_VOCAB = [
    r"^However,", r"^Moreover,", r"^Furthermore,", r"^Nevertheless,",
    r"^In contrast,", r"^Conversely,", r"^Although ", r"^Whereas ",
    r"^Compared with ", r"^In line with ", r"^Consistent with ",
    r"^Similar (?:trends|findings|patterns) ", r"^Across diverse populations,",
    r"^Of note,", r"^Importantly,",
]
_TRANSITION_RE = re.compile("|".join(_TRANSITION_VOCAB))

# Methods boilerplate
_METHODS_RE = re.compile(
    r"(?:Survey-weighted|Multivariable|Multivariate|Cox proportional hazards|"
    r"Generalized estimating equations?|Propensity score-matched|"
    r"Logistic regression) (?:was|were) (?:used to|fit to|applied to|estimated)"
    r"[^.]{0,200}\.",
    re.IGNORECASE,
)

# Mechanism phrase
_MECHANISM_VOCAB = [
    r"\bmediated through (?:the )?[a-z\- ]+\b",
    r"\bdriven by (?:the )?[a-z\- ]+\b",
    r"\bvia (?:the )?[a-z\- ]+ (?:pathway|axis|signaling|circuit)\b",
    r"\bgut[- ]brain axis\b", r"\bHPA axis\b",
    r"\bserotonergic (?:signaling|pathway)\b",
    r"\bdopamin(?:e|ergic) (?:reward|signaling)\b",
    r"\binflammator(?:y|y cytokine) (?:pathway|cascade)\b",
]
_MECHANISM_RE = re.compile("|".join(_MECHANISM_VOCAB), re.IGNORECASE)

# Limitation boilerplate
_LIMITATION_VOCAB = [
    r"^(?:As a |Given the )?(?:cross-sectional|retrospective|observational) (?:design|study|nature)[^.]{0,200}\.",
    r"reverse causation cannot be excluded[^.]{0,160}\.",
    r"residual (?:unmeasured )?confound(?:ing|ers)[^.]{0,160}\.",
    r"self-report(?:ed)?[^.]{0,160}misclassif[^.]{0,80}\.",
    r"generaliz(?:ab)?(?:ility)? (?:of these findings )?(?:beyond|to)[^.]{0,160}\.",
]
_LIMITATION_RE = re.compile("|".join(_LIMITATION_VOCAB), re.IGNORECASE | re.MULTILINE)

# Figure caption
_FIG_CAPTION_RE = re.compile(
    r"\b(?:Figure|Fig\.?)\s*\d+\.\s*[A-Z][^.]{8,200}\.",
)
_TBL_CAPTION_RE = re.compile(
    r"\bTable\s*\d+\.\s*[A-Z][^.]{8,200}\.",
)

# Subgroup / interaction
_SUBGROUP_RE = re.compile(
    r"(?:A )?(?:significant )?interaction (?:was observed |emerged )?"
    r"(?:by [a-z]+ )?\(P (?:for interaction )?[=<]\s*0?\.\d+\)[^.]{0,160}\.",
    re.IGNORECASE,
)

# Citation cluster — [1, 2], [3-7], [12, 14, 15]
_CITE_CLUSTER_RE = re.compile(r"\[\d+(?:\s*[,-–]\s*\d+){0,8}\]")

# Topic sentence (단락 시작, 일반화 명제) — 단순 휴리스틱: 단락 첫 문장 + 키워드
_TOPIC_HINTS = re.compile(
    r"\b(?:Adolescents|Patients|Participants|Children|Women|Men|Studies)\s+"
    r"(?:are|were|have|exhibit|demonstrate|show|report)\b",
    re.IGNORECASE,
)


# ── Extractor ────────────────────────────────────────────────────────────────

def _sentences(text: str) -> List[str]:
    """단순 sentence split — `. `, `.\n` 기준."""
    parts = re.split(r"(?<=[.!?])\s+(?=[A-Z])", text or "")
    return [s.strip() for s in parts if 10 < len(s) < 600]


def _section_guess(idx: int, total: int) -> str:
    """본문 위치로 section 추정. fallback only."""
    if total < 4:
        return ""
    q = idx / total
    if q < 0.20:
        return "introduction"
    if q < 0.45:
        return "methods"
    if q < 0.70:
        return "results"
    return "discussion"


def extract_all(text: str, *, source_pmid: str = "",
                 author_style: str = "", max_per_kind: int = 30) -> List[PaperComponent]:
    """단일 논문 본문 → microcomponent list."""
    text = (text or "").strip()
    if not text:
        return []

    comps: List[PaperComponent] = []
    sents = _sentences(text)
    total = max(1, len(sents))

    # 1) stat_report — 통계 보고 토큰을 포함한 문장
    for s in sents:
        for m in _STAT_REPORT_RE.finditer(s):
            comps.append(make_component(
                "stat_report", m.group(0),
                source_pmid=source_pmid, author_style=author_style,
                source_section="results",
            ))
            if sum(1 for c in comps if c.kind == "stat_report") >= max_per_kind:
                break

    # 2) hedging
    for s in sents:
        for m in _HEDGING_RE.finditer(s):
            # match 주변 ±60자
            start = max(0, m.start() - 40)
            end = min(len(s), m.end() + 40)
            comps.append(make_component(
                "hedging", s[start:end].strip(),
                source_pmid=source_pmid, author_style=author_style,
            ))
            if sum(1 for c in comps if c.kind == "hedging") >= max_per_kind:
                break

    # 3) transition
    for i, s in enumerate(sents):
        if _TRANSITION_RE.search(s):
            comps.append(make_component(
                "transition", s.split(",")[0] + ",",
                source_pmid=source_pmid, author_style=author_style,
                source_section=_section_guess(i, total),
            ))
            if sum(1 for c in comps if c.kind == "transition") >= max_per_kind:
                break

    # 4) methods boilerplate
    for m in _METHODS_RE.finditer(text):
        comps.append(make_component(
            "methods_boilerplate", m.group(0),
            source_pmid=source_pmid, author_style=author_style,
            source_section="methods",
        ))
        if sum(1 for c in comps if c.kind == "methods_boilerplate") >= max_per_kind:
            break

    # 5) mechanism phrase
    for m in _MECHANISM_RE.finditer(text):
        start = max(0, m.start() - 30)
        end = min(len(text), m.end() + 60)
        comps.append(make_component(
            "mechanism_phrase", text[start:end].strip(),
            source_pmid=source_pmid, author_style=author_style,
            source_section="discussion",
        ))
        if sum(1 for c in comps if c.kind == "mechanism_phrase") >= max_per_kind:
            break

    # 6) limitation
    for m in _LIMITATION_RE.finditer(text):
        comps.append(make_component(
            "limitation", m.group(0),
            source_pmid=source_pmid, author_style=author_style,
            source_section="discussion",
        ))
        if sum(1 for c in comps if c.kind == "limitation") >= max_per_kind:
            break

    # 7) figure / table caption
    for m in _FIG_CAPTION_RE.finditer(text):
        comps.append(make_component(
            "figure_caption_pattern", m.group(0),
            source_pmid=source_pmid, author_style=author_style,
        ))
    for m in _TBL_CAPTION_RE.finditer(text):
        comps.append(make_component(
            "table_caption_pattern", m.group(0),
            source_pmid=source_pmid, author_style=author_style,
        ))

    # 8) subgroup
    for m in _SUBGROUP_RE.finditer(text):
        comps.append(make_component(
            "subgroup_sentence", m.group(0),
            source_pmid=source_pmid, author_style=author_style,
            source_section="results",
        ))

    # 9) citation cluster pattern (패턴만 기록 — 본문 컨텍스트는 의미 적음)
    seen = set()
    for m in _CITE_CLUSTER_RE.finditer(text):
        pat = m.group(0)
        if pat in seen:
            continue
        seen.add(pat)
        comps.append(make_component(
            "citation_cluster_pattern", pat,
            source_pmid=source_pmid, author_style=author_style,
        ))
        if len(seen) >= max_per_kind:
            break

    # 10) topic sentence — 단락 시작 + 일반화 명제
    paragraphs = re.split(r"\n\s*\n", text)
    for p in paragraphs:
        p_sents = _sentences(p)
        if not p_sents:
            continue
        first = p_sents[0]
        if _TOPIC_HINTS.search(first) and 60 < len(first) < 280:
            comps.append(make_component(
                "topic_sentence", first,
                source_pmid=source_pmid, author_style=author_style,
            ))
            if sum(1 for c in comps if c.kind == "topic_sentence") >= max_per_kind:
                break

    return comps


def extract_and_store(text: str, *, source_pmid: str = "",
                       author_style: str = "") -> int:
    """추출 + ComponentLibrary 저장. 추가된 개수 반환."""
    from src.library.components import get_library
    comps = extract_all(text, source_pmid=source_pmid, author_style=author_style)
    if not comps:
        return 0
    n = get_library().add_many(comps)
    try:
        from src.runtime import events as _events
        _events.append("components_extracted",
                        {"pmid": source_pmid, "n_extracted": len(comps),
                         "n_added": n,
                         "by_kind": _count_by_kind(comps)},
                        actor="component_extractor")
    except Exception:
        pass
    return n


def _count_by_kind(comps: List[PaperComponent]) -> dict:
    out: dict = {}
    for c in comps:
        out[c.kind] = out.get(c.kind, 0) + 1
    return out
