"""Author Profile — Yoosun Cho Style Seed

Supabase (cloud) with local JSON fallback.
Cloud: ma_author_profiles table (slug PRIMARY KEY)
Local: data/author_profiles/{slug}.json
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger
from src.llm import get_llm_client

_log = get_logger(__name__)


def _clean_llm_response(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        parts = text.split("```")
        if len(parts) > 2 and parts[1].strip().lower().startswith("json"):
            text = "```".join(parts[2:]).strip()
        elif len(parts) > 1:
            text = parts[1].strip()
    if text.lower().startswith("json"):
        text = text[4:].strip()
    return text.strip().rstrip("```").strip()


def _cloud():
    from src.cloud.db import cloud_available
    return cloud_available()


def _engine():
    from src.cloud.db import get_engine
    return get_engine()


class AuthorProfile:
    """저자 스타일 시드 저장소 — Supabase + 로컬 JSON 이중 저장."""

    def __init__(
        self,
        author_name: str,
        profile_dir: str = "data/author_profiles",
        api_key: Optional[str] = None,
        owner_email: str = "",
    ):
        self.author_name = author_name
        self._slug = author_name.lower().replace(" ", "_")
        self._path = Path(profile_dir) / f"{self._slug}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._client = get_llm_client(api_key=api_key)
        self._profile = self._load()
        # 스타일 소유자 — 비어있으면 공용(조유선 시드 등 모두 사용 가능)
        if owner_email and not self._profile.get("owner_email"):
            self._profile["owner_email"] = owner_email

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict:
        # ── Cloud read ─────────────────────────────────────────────────
        if _cloud():
            try:
                from sqlalchemy import text
                with _engine().connect() as conn:
                    row = conn.execute(
                        text("SELECT * FROM ma_author_profiles WHERE slug = :slug"),
                        {"slug": self._slug},
                    ).mappings().first()
                if row:
                    return {
                        "author_name": row["author_name"],
                        "writing_style": row["writing_style"] or {},
                        "methodology": row["methodology"] or {},
                        "paper_structure": row["paper_structure"] or {},
                        "vocabulary": row["vocabulary"] or [],
                        "citation_style": row["citation_style"] or {},
                        "study_focus": row["study_focus"] or [],
                        "raw_examples": row["raw_examples"] or [],
                        "papers_analysed": row["papers_analysed"] or [],
                        "system_prompt": row["system_prompt"] or "",
                    }
            except Exception as e:
                _log.warning(f"Cloud author_profile load failed: {e}")

        # ── Local fallback ─────────────────────────────────────────────
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                pass

        return {
            "author_name": self.author_name,
            "owner_email": "",          # 비어있으면 공용 스타일 (조유선 시드 등)
            "writing_style": {},
            "methodology": {},
            "paper_structure": {},
            "vocabulary": [],
            "citation_style": {},
            "study_focus": [],
            "raw_examples": [],
            "papers_analysed": [],
            "system_prompt": "",
        }

    def save(self):
        # ── Always write local JSON ────────────────────────────────────
        self._path.write_text(
            json.dumps(self._profile, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # ── Cloud UPSERT ───────────────────────────────────────────────
        if _cloud():
            try:
                from sqlalchemy import text
                p = self._profile
                with _engine().begin() as conn:
                    conn.execute(text("""
                        INSERT INTO ma_author_profiles
                            (slug, author_name, writing_style, methodology, paper_structure,
                             vocabulary, citation_style, study_focus, raw_examples,
                             papers_analysed, system_prompt, updated_at)
                        VALUES
                            (:slug, :author_name,
                             CAST(:writing_style AS jsonb), CAST(:methodology AS jsonb),
                             CAST(:paper_structure AS jsonb), CAST(:vocabulary AS jsonb),
                             CAST(:citation_style AS jsonb), CAST(:study_focus AS jsonb),
                             CAST(:raw_examples AS jsonb), CAST(:papers_analysed AS jsonb),
                             :system_prompt, NOW())
                        ON CONFLICT (slug) DO UPDATE SET
                            author_name     = EXCLUDED.author_name,
                            writing_style   = EXCLUDED.writing_style,
                            methodology     = EXCLUDED.methodology,
                            paper_structure = EXCLUDED.paper_structure,
                            vocabulary      = EXCLUDED.vocabulary,
                            citation_style  = EXCLUDED.citation_style,
                            study_focus     = EXCLUDED.study_focus,
                            raw_examples    = EXCLUDED.raw_examples,
                            papers_analysed = EXCLUDED.papers_analysed,
                            system_prompt   = EXCLUDED.system_prompt,
                            updated_at      = NOW()
                    """), {
                        "slug": self._slug,
                        "author_name": self.author_name,
                        "writing_style": json.dumps(p.get("writing_style", {}), ensure_ascii=False),
                        "methodology": json.dumps(p.get("methodology", {}), ensure_ascii=False),
                        "paper_structure": json.dumps(p.get("paper_structure", {}), ensure_ascii=False),
                        "vocabulary": json.dumps(p.get("vocabulary", []), ensure_ascii=False),
                        "citation_style": json.dumps(p.get("citation_style", {}), ensure_ascii=False),
                        "study_focus": json.dumps(p.get("study_focus", []), ensure_ascii=False),
                        "raw_examples": json.dumps(p.get("raw_examples", []), ensure_ascii=False),
                        "papers_analysed": json.dumps(p.get("papers_analysed", []), ensure_ascii=False),
                        "system_prompt": p.get("system_prompt", ""),
                    })
            except Exception as e:
                _log.warning(f"Cloud author_profile save failed: {e}")

    # ------------------------------------------------------------------
    # Style extraction from paper text
    # ------------------------------------------------------------------

    def analyse_paper(self, paper_text: str, paper_title: str = "") -> Dict:
        if paper_title and paper_title in self._profile["papers_analysed"]:
            return {"status": "already_analysed", "title": paper_title}

        prompt = f"""You are a writing-style analyst specialising in academic medical research.

Analyse the following paper text by {self.author_name} and extract these style characteristics in JSON:

{{
  "writing_style": {{
    "sentence_length": "short/medium/long/varied",
    "voice": "active/passive/mixed",
    "tone": "formal/semi-formal/objective",
    "hedging_language": ["list of hedging phrases used"],
    "transition_phrases": ["commonly used transitions"],
    "paragraph_structure": "description of how paragraphs are built"
  }},
  "methodology": {{
    "study_designs": ["cohort", "cross-sectional", etc.],
    "statistical_tests": ["list of tests used"],
    "covariate_handling": "how covariates are selected and reported",
    "subgroup_analysis": "approach to subgroup analyses",
    "sensitivity_analysis": "sensitivity analysis approach",
    "reporting_style": "how results are reported (OR, HR, β, etc.)"
  }},
  "paper_structure": {{
    "abstract_style": "structured/unstructured, typical sections",
    "introduction_pattern": "how intro is built (funnel/direct/etc.)",
    "methods_detail_level": "high/medium — level of methods detail",
    "results_flow": "how results are presented",
    "discussion_structure": "how discussion is organised"
  }},
  "vocabulary": ["list of 20 characteristic words/phrases"],
  "study_focus": ["list of research topics/themes in this paper"],
  "citation_style": {{
    "in_text_format": "numbered/author-year",
    "reference_density": "high/medium/low",
    "typical_journals_cited": []
  }}
}}

Return ONLY the JSON object, no explanation.

PAPER TEXT:
{paper_text[:8000]}
"""
        raw = self._client.generate(prompt)
        raw = _clean_llm_response(raw)

        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            analysis = {"raw": raw}

        self._merge(analysis)
        if len(self._profile["raw_examples"]) < 10:
            self._profile["raw_examples"].append(paper_text[:1500])
        if paper_title:
            self._profile["papers_analysed"].append(paper_title)

        self._rebuild_system_prompt()
        self.save()

        return {"status": "analysed", "title": paper_title, "analysis": analysis}

    # ------------------------------------------------------------------
    # System prompt generation
    # ------------------------------------------------------------------

    def _rebuild_system_prompt(self):
        p = self._profile
        ws = p.get("writing_style", {})
        meth = p.get("methodology", {})
        vocab = p.get("vocabulary", [])[:30]
        focus = p.get("study_focus", [])
        examples = p.get("raw_examples", [])

        example_block = ""
        if examples:
            example_block = "\n\nEXAMPLE WRITING FROM THIS AUTHOR:\n" + "\n---\n".join(examples[:2])

        prompt = f"""You are writing a medical research paper AS {p['author_name']}.
You must precisely match this author's personal style and methodology. Do NOT deviate.

WRITING STYLE:
- Sentence length: {ws.get('sentence_length', 'varied')}
- Voice: {ws.get('voice', 'mixed')}
- Tone: {ws.get('tone', 'formal')}
- Hedging phrases: {', '.join(ws.get('hedging_language', [])[:8])}
- Typical transitions: {', '.join(ws.get('transition_phrases', [])[:8])}

METHODOLOGY PREFERENCES:
- Study designs: {', '.join(meth.get('study_designs', []))}
- Statistical tests: {', '.join(meth.get('statistical_tests', []))}
- Covariate handling: {meth.get('covariate_handling', '')}
- Results reporting: {meth.get('reporting_style', '')}

CHARACTERISTIC VOCABULARY (use naturally):
{', '.join(vocab)}

RESEARCH FOCUS AREAS:
{', '.join(focus[:10])}
{example_block}

RULES:
1. Write in English unless instructed otherwise
2. Use the exact statistical reporting format this author uses
3. Match the paragraph length and sentence rhythm
4. Apply the same level of hedging/precision
5. Structure each section exactly as this author does
6. NEVER add content the author would not write
"""
        p["system_prompt"] = prompt

    # ------------------------------------------------------------------
    # Getters
    # ------------------------------------------------------------------

    def get_system_prompt(self) -> str:
        if not self._profile.get("system_prompt"):
            self._rebuild_system_prompt()
        return self._profile["system_prompt"]

    def get_profile(self) -> Dict:
        return self._profile

    def get_papers_analysed(self) -> List[str]:
        return self._profile.get("papers_analysed", [])

    def summary(self) -> str:
        p = self._profile
        return (
            f"Author: {p['author_name']}\n"
            f"Papers analysed: {len(p.get('papers_analysed', []))}\n"
            f"Study designs: {p.get('methodology', {}).get('study_designs', [])}\n"
            f"Stat methods: {p.get('methodology', {}).get('statistical_tests', [])}\n"
            f"Focus areas: {p.get('study_focus', [])[:5]}\n"
        )

    # ------------------------------------------------------------------
    # Merge helpers
    # ------------------------------------------------------------------

    def _merge(self, analysis: Dict):
        for section in ("writing_style", "methodology", "paper_structure", "citation_style"):
            if section in analysis and isinstance(analysis[section], dict):
                existing = self._profile.get(section, {})
                for k, v in analysis[section].items():
                    if isinstance(v, list):
                        existing.setdefault(k, [])
                        existing[k] = list(dict.fromkeys(existing[k] + v))[:20]
                    elif v and not existing.get(k):
                        existing[k] = v
                self._profile[section] = existing

        if "vocabulary" in analysis:
            self._profile["vocabulary"] = list(
                dict.fromkeys(self._profile.get("vocabulary", []) + analysis["vocabulary"])
            )[:60]

        if "study_focus" in analysis:
            self._profile["study_focus"] = list(
                dict.fromkeys(self._profile.get("study_focus", []) + analysis["study_focus"])
            )[:30]


# ──────────────────────────────────────────────────────────────────────
# 스타일 레지스트리 — 사용 가능한 스타일 목록 (B: 템플릿 선택용)
# ──────────────────────────────────────────────────────────────────────

def list_styles(
    owner_email: str = "",
    include_shared: bool = True,
    all_styles: bool = False,
    profile_dir: str = "data/author_profiles",
) -> List[Dict]:
    """선택 가능한 저자 스타일 목록.

    - all_styles=True (admin): 전체 스타일
    - 그 외: 공용 스타일(owner 없음, 조유선 시드 등) + owner_email 본인 스타일
    각 항목: {name, slug, owner, shared, papers_analysed}
    """
    styles: List[Dict] = []
    d = Path(profile_dir)
    if not d.exists():
        return styles
    for f in sorted(d.glob("*.json")):
        try:
            p = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        owner = p.get("owner_email", "")
        shared = not owner
        if not all_styles:
            if shared:
                if not include_shared:
                    continue
            elif owner != owner_email:
                continue
        styles.append({
            "name": p.get("author_name", f.stem),
            "slug": f.stem,
            "owner": owner,
            "shared": shared,
            "papers_analysed": len(p.get("papers_analysed", [])),
        })
    return styles
