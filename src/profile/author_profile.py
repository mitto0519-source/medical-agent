"""Author Profile — Yoosun Cho Style Seed

저자의 논문 스타일, 방법론 선호, 문체, 어투를 추출하고
JSON으로 영구 저장. 논문 생성 시 이 프로파일을 기준으로 삼음.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

import anthropic


class AuthorProfile:
    """저자 스타일 시드 저장소.

    저장 항목
    ---------
    - writing_style   : 문체, 어투, 문장 구조 특성
    - methodology     : 선호 연구 설계, 통계 방법론
    - paper_structure : 섹션 구성 방식, 분량 배분
    - vocabulary      : 자주 쓰는 표현, 핵심 단어
    - citation_style  : 인용 스타일, 레퍼런스 패턴
    - study_focus     : 연구 관심 분야, 주제 패턴
    - raw_examples    : 실제 Abstract/Introduction 예시 텍스트
    """

    def __init__(
        self,
        author_name: str,
        profile_dir: str = "data/author_profiles",
        api_key: Optional[str] = None,
    ):
        self.author_name = author_name
        self._slug = author_name.lower().replace(" ", "_")
        self._path = Path(profile_dir) / f"{self._slug}.json"
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._client = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self._profile = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "author_name": self.author_name,
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
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._profile, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Style extraction from paper text
    # ------------------------------------------------------------------

    def analyse_paper(self, paper_text: str, paper_title: str = "") -> Dict:
        """Claude로 논문 한 편을 분석해서 스타일 요소 추출."""

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

        response = self._client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2000,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": prompt}],
        )

        raw = response.content[-1].text if response.content else "{}"
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip().rstrip("```").strip()

        try:
            analysis = json.loads(raw)
        except json.JSONDecodeError:
            analysis = {"raw": raw}

        # Merge into cumulative profile
        self._merge(analysis)

        # Save example text (first 1500 chars of abstract/intro)
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
        """Build the Claude system prompt that enforces this author's style."""
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
        """Return the Claude system prompt encoding this author's style."""
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
        """Incrementally merge a new paper's analysis into cumulative profile."""
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
