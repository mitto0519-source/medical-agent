"""JournalRegistry — 저널별 투고 서식 DB.

로컬 data/journals/styles/ 에서 로드.
등록 안 된 저널은 LLM 보조 + Author Guidelines URL로 자동 구조화 후 저장.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_STYLES_DIR = Path("data/journals/styles")
_STYLES_DIR.mkdir(parents=True, exist_ok=True)

# 표준 저널 ID → 별칭 매핑 (대소문자/공백 무관 검색용)
_ALIASES: Dict[str, str] = {
    "jkms": "jkms",
    "j korean med sci": "jkms",
    "journal of korean medical science": "jkms",
    "kjpm": "kjpm",
    "epidemiology and health": "kjpm",
    "epih": "kjpm",
    "ijerph": "ijerph",
    "int j environ res public health": "ijerph",
    "plos one": "plos_one",
    "plos_one": "plos_one",
    "bmj open": "bmj_open",
    "bmj_open": "bmj_open",
}


@dataclass
class JournalStyle:
    id: str
    name: str
    abbreviation: str
    publisher: str = ""
    impact_factor: float = 0.0
    reference_style: str = "Vancouver"   # Vancouver | APA | AMA | NLM
    max_abstract_words: int = 250
    max_references: int = 50
    language: str = "English"
    formatting: Dict = field(default_factory=lambda: {
        "font_name": "Times New Roman",
        "font_size_pt": 12,
        "line_spacing": 2.0,
        "margin_top_cm": 2.54,
        "margin_bottom_cm": 2.54,
        "margin_left_cm": 2.54,
        "margin_right_cm": 2.54,
        "abstract_structure": ["Background", "Methods", "Results", "Conclusion"],
        "section_order": ["Abstract", "Introduction", "Methods", "Results", "Discussion", "References"],
        "page_numbers": True,
        "double_blind": False,
        "keywords_max": 6,
        "title_max_words": 25,
    })
    submission_url: str = ""
    author_guidelines_url: str = ""

    # ── 편의 프로퍼티 ────────────────────────────────────────────────────────
    @property
    def font_name(self) -> str:
        return self.formatting.get("font_name", "Times New Roman")

    @property
    def font_size(self) -> float:
        return self.formatting.get("font_size_pt", 12)

    @property
    def line_spacing(self) -> float:
        return self.formatting.get("line_spacing", 2.0)

    @property
    def margins_cm(self) -> Dict[str, float]:
        f = self.formatting
        return {
            "top": f.get("margin_top_cm", 2.54),
            "bottom": f.get("margin_bottom_cm", 2.54),
            "left": f.get("margin_left_cm", 2.54),
            "right": f.get("margin_right_cm", 2.54),
        }

    @property
    def abstract_structure(self) -> List[str]:
        return self.formatting.get(
            "abstract_structure", ["Background", "Methods", "Results", "Conclusion"]
        )

    @property
    def section_order(self) -> List[str]:
        return self.formatting.get(
            "section_order",
            ["Abstract", "Introduction", "Methods", "Results", "Discussion", "References"],
        )

    @property
    def methods_section_name(self) -> str:
        return self.formatting.get("methods_section_name", "Methods")

    @property
    def conclusions_required(self) -> bool:
        return self.formatting.get("conclusions_required", False)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "JournalStyle":
        return cls(
            id=d.get("id", "unknown"),
            name=d.get("name", "Unknown Journal"),
            abbreviation=d.get("abbreviation", ""),
            publisher=d.get("publisher", ""),
            impact_factor=float(d.get("impact_factor", 0.0)),
            reference_style=d.get("reference_style", "Vancouver"),
            max_abstract_words=int(d.get("max_abstract_words", 250)),
            max_references=int(d.get("max_references", 50)),
            language=d.get("language", "English"),
            formatting=d.get("formatting", {}),
            submission_url=d.get("submission_url", ""),
            author_guidelines_url=d.get("author_guidelines_url", ""),
        )


class JournalRegistry:
    """저널 스타일 레지스트리.

    Usage:
        reg = JournalRegistry()
        style = reg.get("jkms")           # 등록된 저널
        style = reg.get("PLOS Medicine")  # 미등록 → LLM 보조 생성 + 자동 저장
        journals = reg.list_journals()
    """

    def __init__(self, styles_dir: str | Path = _STYLES_DIR, llm_client=None):
        self._dir = Path(styles_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, JournalStyle] = {}
        self._llm = llm_client
        self._load_all()

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def get(self, journal_name: str) -> JournalStyle:
        """저널명으로 스타일 반환. 미등록이면 자동 생성."""
        key = self._normalize(journal_name)
        # 별칭 테이블 조회
        canonical = _ALIASES.get(key)
        if canonical and canonical in self._cache:
            return self._cache[canonical]
        # 직접 캐시 조회
        if key in self._cache:
            return self._cache[key]
        # 부분 일치 검색
        for cid, style in self._cache.items():
            if key in self._normalize(style.name) or key in self._normalize(style.abbreviation):
                return style
        # 미등록 → 자동 생성
        _log.info("저널 '%s' 미등록 — 자동 생성 시도", journal_name)
        return self._auto_create(journal_name)

    def register(self, style: JournalStyle, overwrite: bool = False):
        """새 저널 스타일 등록 + 파일 저장."""
        path = self._dir / f"{style.id}.json"
        if path.exists() and not overwrite:
            _log.debug("저널 '%s' 이미 존재 (overwrite=False)", style.id)
            return
        path.write_text(json.dumps(style.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        self._cache[style.id] = style
        _log.info("저널 등록 완료: %s (%s)", style.name, style.id)

    def list_journals(self) -> List[Dict]:
        """등록된 모든 저널 목록 반환."""
        return [
            {
                "id": s.id,
                "name": s.name,
                "abbreviation": s.abbreviation,
                "impact_factor": s.impact_factor,
                "reference_style": s.reference_style,
            }
            for s in self._cache.values()
        ]

    def get_default(self) -> JournalStyle:
        """기본 스타일 (JKMS) 반환."""
        return self._cache.get("jkms") or JournalStyle(id="default", name="Generic Medical Journal", abbreviation="Generic")

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _load_all(self):
        for p in self._dir.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                style = JournalStyle.from_dict(data)
                self._cache[style.id] = style
            except Exception as e:
                _log.warning("저널 스타일 로드 실패 %s: %s", p.name, e)
        _log.debug("저널 레지스트리 로드: %d개", len(self._cache))

    @staticmethod
    def _normalize(name: str) -> str:
        return re.sub(r"\s+", " ", name.lower().strip())

    def _auto_create(self, journal_name: str) -> JournalStyle:
        """LLM 보조로 저널 스타일을 추론 생성 후 저장."""
        safe_id = re.sub(r"[^a-z0-9_]", "_", self._normalize(journal_name))[:40].strip("_")
        if not safe_id:
            safe_id = "unknown_journal"

        # LLM 없으면 기본 스타일로 생성
        if self._llm is None:
            try:
                from src.llm import get_llm_client
                self._llm = get_llm_client()
            except Exception:
                pass

        formatting = {
            "font_name": "Times New Roman",
            "font_size_pt": 12,
            "line_spacing": 2.0,
            "margin_top_cm": 2.54,
            "margin_bottom_cm": 2.54,
            "margin_left_cm": 2.54,
            "margin_right_cm": 2.54,
            "abstract_structure": ["Background", "Methods", "Results", "Conclusion"],
            "section_order": ["Abstract", "Introduction", "Methods", "Results", "Discussion", "References"],
            "page_numbers": True,
            "double_blind": False,
            "keywords_max": 6,
            "title_max_words": 25,
        }
        ref_style = "Vancouver"
        max_abstract = 250

        if self._llm:
            try:
                prompt = f"""You are a medical journal editor. Fill in the formatting requirements for this journal: "{journal_name}"

Respond in JSON only:
{{
  "reference_style": "Vancouver|APA|AMA|NLM",
  "max_abstract_words": <int>,
  "max_references": <int or 0 if unlimited>,
  "font_name": "Times New Roman|Arial|Calibri",
  "font_size_pt": <10|11|12>,
  "line_spacing": <1.0|1.5|2.0>,
  "abstract_structure": ["Background","Methods","Results","Conclusion"],
  "double_blind": <true|false>,
  "keywords_max": <int>,
  "impact_factor": <float or 0>
}}
If unknown, use sensible defaults for a general medical journal."""
                raw = self._llm.generate(user_message=prompt, max_tokens=400, task="general")
                raw = re.sub(r"```json|```", "", raw).strip()
                llm_data = json.loads(raw)
                ref_style = llm_data.get("reference_style", "Vancouver")
                max_abstract = int(llm_data.get("max_abstract_words", 250))
                formatting.update({
                    "font_name": llm_data.get("font_name", "Times New Roman"),
                    "font_size_pt": llm_data.get("font_size_pt", 12),
                    "line_spacing": llm_data.get("line_spacing", 2.0),
                    "abstract_structure": llm_data.get("abstract_structure", formatting["abstract_structure"]),
                    "double_blind": llm_data.get("double_blind", False),
                    "keywords_max": llm_data.get("keywords_max", 6),
                })
                impact_factor = float(llm_data.get("impact_factor", 0.0))
                max_refs = int(llm_data.get("max_references", 50))
            except Exception as e:
                _log.warning("LLM 저널 추론 실패 (%s): %s", journal_name, e)
                impact_factor = 0.0
                max_refs = 50
        else:
            impact_factor = 0.0
            max_refs = 50

        style = JournalStyle(
            id=safe_id,
            name=journal_name,
            abbreviation=journal_name,
            impact_factor=impact_factor,
            reference_style=ref_style,
            max_abstract_words=max_abstract,
            max_references=max_refs,
            formatting=formatting,
        )
        self.register(style)
        return style


# 싱글턴 인스턴스
_registry: Optional[JournalRegistry] = None


def get_registry() -> JournalRegistry:
    global _registry
    if _registry is None:
        _registry = JournalRegistry()
    return _registry
