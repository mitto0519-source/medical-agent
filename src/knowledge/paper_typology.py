"""Paper Typology — 12,301편 본문에서 섹션별 의학적 사고흐름·전개·골격을 유형화.

사용자 비전 (2026-06-01):
    "시드를 자산화 구조화해서 논문 쓰는 기본 골격과 구조, 의학적 사고흐름과
     전개 방식들을 여러 유형화 표현법으로 익혀라.
     → 그 다음 AI 같지 않도록 필터링 → 그 다음 조유선 스타일로 최종 변환."

지금까지: paper_writer가 RAG에서 발췌 N개 끌어와 user_prompt에 박는 게 끝.
        → 발췌 ≠ 자산화. 자산화는 "유형 카탈로그".

본 모듈은 12,301편 본문(data/oa_papers/*.txt)에서 섹션별로 자동 분류해
유형 카탈로그를 빌드한다:

    Introduction 도입 유형:
        gap-statement-first         "Although ... remains poorly understood."
        public-health-burden-first  "Globally, X affects N million ..."
        clinical-relevance-first    "X is a leading cause of ..."
        trend-rising-first          "The prevalence of X has risen sharply ..."
        biological-mechanism-first  "X is regulated by ... pathway."

    Methods 기술 유형:
        cohort-design-first         "We conducted a population-based cohort study ..."
        survey-design-first         "Data came from the nationally representative ..."
        case-control-first          "We performed a matched case-control analysis ..."
        cross-sectional-first       "This cross-sectional analysis used ..."

    Results 보고 유형:
        descriptive-first           "Among the N participants (mean age ...) ..."
        main-effect-first           "In the fully adjusted model, X was associated ..."
        forest-narrative            "The association was consistent across subgroups ..."

    Discussion 전개 유형:
        headline-finding-first      "In this large nationally representative study ..."
        comparison-first            "Our findings extend prior reports from ..."
        mechanism-first             "Several biological mechanisms may explain ..."
        policy-translation-first    "These findings have direct implications for ..."

빌드 방법:
    각 본문에서 IMRAD 섹션 분리 → 섹션 첫 단락 (~400자) 추출 → 유형 패턴
    (정규식 + 키워드 N) 매칭 → 카탈로그에 (typology, excerpt, pmcid) 누적.
    LLM 호출 0, 휴리스틱만 — 12,301편을 1분 이내 처리.

API:
    build_typology_catalog(force=False) -> Catalog  # 첫 호출은 빌드, 이후 캐시
    get_typology_block(section, n_per_type=2)        # paper_writer가 user_prompt에 박을 텍스트
"""
from __future__ import annotations

import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_OA_DIR = Path("data/oa_papers")
_MANIFEST = _OA_DIR / "manifest.sqlite"
_CATALOG_PATH = Path("data/medical_knowledge_seed/typology_catalog.json")


# ── 섹션 헤딩 검출 (case-insensitive, 라인 단위) ────────────────────────

_SECTION_PATTERNS = {
    "introduction": re.compile(r"^\s*(?:\d+\.?\s*)?(?:Introduction|Background)\s*$",
                                re.IGNORECASE | re.MULTILINE),
    "methods":      re.compile(r"^\s*(?:\d+\.?\s*)?(?:Methods?|Materials and Methods|"
                                r"Patients and Methods|Study Design)\s*$",
                                re.IGNORECASE | re.MULTILINE),
    "results":      re.compile(r"^\s*(?:\d+\.?\s*)?(?:Results?|Findings)\s*$",
                                re.IGNORECASE | re.MULTILINE),
    "discussion":   re.compile(r"^\s*(?:\d+\.?\s*)?(?:Discussion|General Discussion)\s*$",
                                re.IGNORECASE | re.MULTILINE),
    "conclusion":   re.compile(r"^\s*(?:\d+\.?\s*)?(?:Conclusions?)\s*$",
                                re.IGNORECASE | re.MULTILINE),
}

_NEXT_SECTION_HEADS = re.compile(
    r"^\s*(?:\d+\.?\s*)?(?:Methods?|Materials and Methods|Results?|"
    r"Findings|Discussion|Conclusions?|References?|Acknowledg|Funding|"
    r"Author Contributions|Competing Interests|Supplementary)\s*$",
    re.IGNORECASE | re.MULTILINE,
)


# ── 유형 분류 룰 (섹션별) ──────────────────────────────────────────────

TYPOLOGIES = {
    "introduction": {
        "gap-statement-first": [
            r"\b(?:remains?|is) (?:poorly|not (?:well|fully)) (?:understood|characteri[sz]ed)\b",
            r"\b(?:little|limited|few(?:er)?|no) (?:is |are )?known (?:about|regarding)\b",
            r"\b(?:gap|lack)s? in (?:the |our |current )?(?:literature|knowledge|evidence|understanding)\b",
            r"\b(?:has|have) not been (?:thoroughly |adequately |systematically )?(?:examined|investigated|studied|established)\b",
        ],
        "public-health-burden-first": [
            r"\b(?:globally|worldwide|in [A-Z][a-z]+),?\s+\w+ (?:affects?|accounts? for)\b",
            r"\b(?:leading|major) (?:cause|contributor) of (?:morbidity|mortality|disability)\b",
            r"\b(?:public[- ]health (?:burden|concern|priority|problem))\b",
            r"\baffects? (?:more than |approximately |over |about )?\d{1,3}(?:[,.]\d{3})* (?:million|billion|adolescents?|adults?|children|patients?)\b",
        ],
        "clinical-relevance-first": [
            r"\b(?:is|are) (?:a|the) leading cause of\b",
            r"\bclinical(?:ly)?\s+(?:significant|relevant|important)\b",
            r"\b(?:diagnosis|treatment|management) of \w+ remains?\b",
            r"\bassociated with (?:increased |higher )?risk of (?:morbidity|mortality|hospitalization)\b",
        ],
        "trend-rising-first": [
            r"\b(?:rapidly|sharply|substantially|dramatically) (?:increas|ris)(?:ed|ing|en)\b",
            r"\b(?:prevalence|incidence|consumption|use) of \w+ has (?:risen|increased|grown)\b",
            r"\b(?:in recent (?:decades|years))\b",
            r"\b(?:more than (?:doubled|tripled))\b",
        ],
        "biological-mechanism-first": [
            r"\b(?:regulated|mediated|modulated) by (?:the |a )?\w+(?: pathway| signaling| axis)\b",
            r"\b(?:gut[- ]?brain|hypothalamic-pituitary|inflammatory|metabolic) (?:axis|pathway|cascade)\b",
            r"\b(?:upregulat|downregulat|express(?:es|ed|ion))\b",
        ],
    },
    "methods": {
        "cohort-design-first": [
            r"\b(?:prospective|retrospective|population[- ]based) cohort study\b",
            r"\bwe (?:conducted|performed|followed) a (?:prospective |retrospective )?cohort\b",
            r"\bparticipants were followed (?:for|up)\b",
        ],
        "survey-design-first": [
            r"\b(?:nationally|nationwide|national(?:ly)?) representative (?:survey|sample|cohort|cross-sectional)\b",
            r"\bdata (?:came|were (?:obtained|drawn)) from the\b.{0,80}\bsurvey\b",
            r"\b(?:complex|stratified|multistage) (?:sampling|survey) design\b",
            r"\b(?:NHANES|KYRBS|KNHANES|HSE|HRS|MEPS|BRFSS)\b",
        ],
        "case-control-first": [
            r"\b(?:matched |nested |population[- ]based )?case[- ]control (?:study|analysis|design)\b",
            r"\b(?:cases were matched to controls)\b",
            r"\bincidence-density sampling\b",
        ],
        "cross-sectional-first": [
            r"\bcross[- ]sectional (?:study|analysis|design|survey)\b",
            r"\bthis (?:study )?(?:used|was) a cross-sectional\b",
        ],
        "rct-first": [
            r"\b(?:randomi[sz]ed|randomi[sz]ation) (?:controlled )?(?:trial|study)\b",
            r"\b(?:double|single|triple)-blind(?:ed)?\b",
            r"\b(?:placebo|sham)-controlled\b",
        ],
    },
    "results": {
        "descriptive-first": [
            r"\b(?:among|of) (?:the )?[\d,]+ (?:participants?|adolescents?|patients?|adults?|individuals?)\b",
            r"\bmean (?:age |± )?\d",
            r"\b(?:baseline characteristics|participant characteristics)\b",
        ],
        "main-effect-first": [
            r"\bin the (?:fully |multivariable[- ])?adjusted model\b",
            r"\b(?:adjusted )?(?:odds ratio|hazard ratio|risk ratio)s? (?:was|were|for)\b",
            r"\b(?:was|were) (?:significantly |independently )?associated with\b.{0,40}\b\d",
        ],
        "forest-narrative": [
            r"\b(?:consistent|similar) (?:patterns?|associations?) (?:were observed |across )(?:subgroups?|strata|sex|age)\b",
            r"\bsubgroup analys[ie]s (?:showed|revealed|demonstrated)\b",
            r"\bp(?: |-)(?:for |interaction)\b",
        ],
        "trend-test-first": [
            r"\bp (?:for |-)trend\b",
            r"\bdose[- ]?response (?:relationship|pattern|trend)\b",
            r"\blinear trend (?:was |across categories)\b",
        ],
    },
    "discussion": {
        "headline-finding-first": [
            r"^\s*(?:In|Among) (?:this |a )?(?:large |nationally representative )?\b",
            r"\bwe (?:found|observed|demonstrated|showed) that\b",
            r"\b(?:the )?main finding(?:s)? of this study\b",
        ],
        "comparison-first": [
            r"\b(?:consistent|in agreement|in line) with (?:prior|previous|earlier) (?:studies|reports|literature|findings)\b",
            r"\b(?:our|the present) (?:findings?|results?) (?:extend|support|confirm|replicate)\b",
            r"\b(?:in contrast to|unlike) (?:prior|previous) (?:studies|reports)\b",
        ],
        "mechanism-first": [
            r"\bseveral (?:biological |plausible |potential )?mechanisms (?:may|might|could) explain\b",
            r"\b(?:one|a) (?:plausible|potential) (?:explanation|mechanism) (?:is|involves)\b",
            r"\b(?:biologically )?plausible (?:mechanism|pathway)s?\b",
        ],
        "policy-translation-first": [
            r"\b(?:these|our) findings (?:have|carry) (?:important |direct )?(?:implications|relevance) for\b",
            r"\b(?:public health|clinical|policy) (?:implications|recommendations|practice)\b",
            r"\b(?:should|need to|warrant|merit) (?:be )?(?:considered|targeted|prioriti[sz]ed)\b",
        ],
        "limitation-first": [
            r"\b(?:several |a few |some )?(?:potential |notable )?limitations\b",
            r"\b(?:our|this) (?:study|analysis) (?:has|carries) (?:several |notable )?limitations\b",
        ],
    },
}


@dataclass
class TypologyHit:
    pmcid: str = ""
    excerpt: str = ""
    section: str = ""
    typology: str = ""


@dataclass
class TypologyCatalog:
    built_at: str = ""
    n_papers_scanned: int = 0
    n_papers_with_sections: int = 0
    section_counts: Dict[str, int] = field(default_factory=dict)
    by_section_type: Dict[str, Dict[str, List[Dict]]] = field(
        default_factory=lambda: defaultdict(lambda: defaultdict(list)))

    def stats(self) -> Dict[str, Dict[str, int]]:
        return {sec: {ty: len(v) for ty, v in d.items()}
                for sec, d in self.by_section_type.items()}


# ── 본문 → 섹션 첫 단락 추출 ──────────────────────────────────────────

def _extract_section_lead(text: str, section: str, *, lead_chars: int = 600) -> str:
    """본문에서 section 헤딩 직후 첫 단락 ~lead_chars 추출."""
    pat = _SECTION_PATTERNS.get(section)
    if not pat:
        return ""
    m = pat.search(text)
    if not m:
        return ""
    start = m.end()
    rest = text[start:]
    # 다음 섹션 헤딩까지 자름
    nm = _NEXT_SECTION_HEADS.search(rest)
    block = rest[:nm.start()] if nm else rest
    # 빈 줄 무시하고 첫 단락 ~lead_chars
    block = block.lstrip("\n\r ")
    return block[:lead_chars].strip()


def _classify_typology(section: str, lead_text: str) -> List[str]:
    """lead_text에 매칭되는 typology 목록 반환 (다중 가능)."""
    rules = TYPOLOGIES.get(section, {})
    matched = []
    for typology, patterns in rules.items():
        for p in patterns:
            if re.search(p, lead_text, re.IGNORECASE | re.DOTALL):
                matched.append(typology)
                break
    return matched


# ── 카탈로그 빌드 ──────────────────────────────────────────────────────

def build_typology_catalog(*, force: bool = False, limit: Optional[int] = None,
                             max_per_typology: int = 20) -> TypologyCatalog:
    """data/oa_papers 전체를 스캔해 typology 카탈로그 빌드.

    max_per_typology: 각 (section, typology)당 보관할 발췌 max — 메모리 절약.
    """
    import time as _t
    from datetime import datetime as _dt

    if _CATALOG_PATH.exists() and not force:
        try:
            d = json.loads(_CATALOG_PATH.read_text(encoding="utf-8"))
            cat = TypologyCatalog(
                built_at=d.get("built_at", ""),
                n_papers_scanned=d.get("n_papers_scanned", 0),
                n_papers_with_sections=d.get("n_papers_with_sections", 0),
                section_counts=d.get("section_counts", {}),
            )
            cat.by_section_type = defaultdict(lambda: defaultdict(list))
            for sec, types in d.get("by_section_type", {}).items():
                for ty, hits in types.items():
                    cat.by_section_type[sec][ty] = hits
            _log.info("[Typology] cached catalog loaded: %s",
                       sum(len(v) for d_ in cat.by_section_type.values() for v in d_.values()))
            return cat
        except Exception as e:
            _log.warning("[Typology] cache load failed: %s — rebuilding", e)

    if not _OA_DIR.exists():
        raise FileNotFoundError(f"OA papers dir not found: {_OA_DIR}")

    cat = TypologyCatalog(built_at=_dt.utcnow().isoformat() + "Z")
    section_counts: Dict[str, int] = defaultdict(int)
    txt_files = sorted(_OA_DIR.glob("PMC*.txt"))
    if limit:
        txt_files = txt_files[:limit]

    t0 = _t.time()
    n_with_section = 0
    for i, tp in enumerate(txt_files):
        if i % 1000 == 0:
            _log.info("[Typology] %d/%d scanned (%.1fs)", i, len(txt_files), _t.time() - t0)
        try:
            text = tp.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        pmcid = tp.stem
        had_section = False
        for sec in ("introduction", "methods", "results", "discussion"):
            lead = _extract_section_lead(text, sec)
            if not lead or len(lead) < 80:
                continue
            had_section = True
            section_counts[sec] += 1
            types = _classify_typology(sec, lead)
            for ty in types:
                bucket = cat.by_section_type[sec][ty]
                if len(bucket) < max_per_typology:
                    bucket.append({
                        "pmcid": pmcid,
                        "excerpt": lead[:500],
                    })
        if had_section:
            n_with_section += 1

    cat.n_papers_scanned = len(txt_files)
    cat.n_papers_with_sections = n_with_section
    cat.section_counts = dict(section_counts)

    # 저장
    _CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "built_at": cat.built_at,
        "n_papers_scanned": cat.n_papers_scanned,
        "n_papers_with_sections": cat.n_papers_with_sections,
        "section_counts": cat.section_counts,
        "by_section_type": {sec: {ty: hits for ty, hits in d.items()}
                              for sec, d in cat.by_section_type.items()},
    }
    _CATALOG_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                              encoding="utf-8")
    _log.info("[Typology] catalog saved: %s (%.1fs)", _CATALOG_PATH, _t.time() - t0)
    return cat


# ── paper_writer가 user_prompt에 박을 typology 블록 ─────────────────────

def get_typology_block(section: str, *, n_per_type: int = 1,
                        catalog: Optional[TypologyCatalog] = None) -> str:
    """section의 모든 유형 × n_per_type 예문을 짧은 user_prompt 블록으로.

    paper_writer가 작성 시 "이 섹션의 가능한 도입/전개 유형 N가지"를 시드 본문
    예문으로 학습 시드처럼 박는다. 단순 RAG 발췌와 차이:
        - 유형별로 정리 (gap-first / burden-first / clinical-first ...)
        - LLM이 유형을 선택해 그 양식을 따를 수 있게 함
    """
    if catalog is None:
        try:
            catalog = build_typology_catalog()
        except Exception as e:
            _log.warning("[Typology] block build failed: %s", e)
            return ""
    types = catalog.by_section_type.get(section) or {}
    if not types:
        return ""
    lines = [f"## SECTION TYPOLOGY — {section.upper()} (choose one rhetorical mode)",
             ""]
    for ty, hits in types.items():
        if not hits:
            continue
        lines.append(f"### Mode: {ty}")
        for h in hits[:n_per_type]:
            ex = (h.get("excerpt") or "")[:380].replace("\n", " ").strip()
            lines.append(f"  [{h.get('pmcid','?')}] {ex}")
        lines.append("")
    lines.append("Pick ONE mode that fits the study aim and mirror its rhetorical "
                   "rhythm — opening verb, topic-sentence structure, hedging cadence. "
                   "Do NOT copy verbatim; absorb the structural pattern.")
    return "\n".join(lines)


__all__ = [
    "build_typology_catalog", "get_typology_block",
    "TypologyCatalog", "TypologyHit", "TYPOLOGIES",
]
