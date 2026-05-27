"""Peer Reviewer — LLM 기반 논문 품질 평가 + 개선 피드백.

의학 저널 편집자 관점에서 논문 초안을 평가하고 섹션별 피드백을 생성한다.
KYRBS/KNHANES 공중보건 논문에 특화된 루브릭 사용.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from src.config.logging_config import get_logger
from src.config.models import get_model
from src.llm import get_llm_client

_log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Score rubric definitions
# ---------------------------------------------------------------------------

RUBRIC = {
    "originality": {
        "label": "독창성",
        "desc": "연구 질문의 참신성, 기존 문헌과의 차별점",
        "max": 20,
    },
    "methodology": {
        "label": "연구 방법론",
        "desc": "연구 설계 적절성, 통계 방법 타당성, 편향 통제",
        "max": 25,
    },
    "results_clarity": {
        "label": "결과 명확성",
        "desc": "데이터 제시 방식, 통계치 보고 완성도, 표/그림 활용",
        "max": 20,
    },
    "clinical_relevance": {
        "label": "임상/공중보건 관련성",
        "desc": "연구 결과의 실용적 의미, 정책적 시사점",
        "max": 20,
    },
    "writing_quality": {
        "label": "논문 작성 품질",
        "desc": "논리 흐름, 문장 명확성, 섹션 구조",
        "max": 15,
    },
}

TOTAL_MAX = sum(v["max"] for v in RUBRIC.values())  # 100


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class SectionFeedback:
    section: str
    score: int
    max_score: int
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    @property
    def pct(self) -> float:
        return self.score / self.max_score * 100 if self.max_score else 0.0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReviewResult:
    total_score: int
    max_score: int
    grade: str                          # A/B/C/D/F
    accept_recommendation: str          # accept | major_revision | minor_revision | reject
    section_scores: dict[str, SectionFeedback] = field(default_factory=dict)
    key_strengths: list[str] = field(default_factory=list)
    major_concerns: list[str] = field(default_factory=list)
    minor_concerns: list[str] = field(default_factory=list)
    suggested_analyses: list[str] = field(default_factory=list)
    revised_abstract: Optional[str] = None
    error: Optional[str] = None

    @property
    def pct(self) -> float:
        return self.total_score / self.max_score * 100 if self.max_score else 0.0

    def summary_ko(self) -> str:
        lines = [
            f"종합 점수: {self.total_score}/{self.max_score} ({self.pct:.1f}%) — 등급: {self.grade}",
            f"처리 권고: {self.accept_recommendation}",
        ]
        if self.major_concerns:
            lines.append("주요 지적:")
            for c in self.major_concerns:
                lines.append(f"  · {c}")
        if self.suggested_analyses:
            lines.append("추가 분석 제안:")
            for a in self.suggested_analyses:
                lines.append(f"  · {a}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        d = {
            "total_score": self.total_score,
            "max_score": self.max_score,
            "pct": round(self.pct, 1),
            "grade": self.grade,
            "accept_recommendation": self.accept_recommendation,
            "section_scores": {k: v.to_dict() for k, v in self.section_scores.items()},
            "key_strengths": self.key_strengths,
            "major_concerns": self.major_concerns,
            "minor_concerns": self.minor_concerns,
            "suggested_analyses": self.suggested_analyses,
            "summary": self.summary_ko(),
            "error": self.error,
        }
        if self.revised_abstract:
            d["revised_abstract"] = self.revised_abstract
        return d


# ---------------------------------------------------------------------------
# Peer Reviewer
# ---------------------------------------------------------------------------

class PeerReviewer:
    """의학 저널 편집자 관점에서 논문 초안을 평가하는 LLM 기반 리뷰어.

    Usage:
        reviewer = PeerReviewer()
        result = reviewer.review(paper_text, topic, stat_result=None)
    """

    def __init__(self, llm_client=None, api_key: str | None = None):
        self._client = llm_client or get_llm_client(api_key=api_key)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def review(
        self,
        paper_text: str,
        topic: str,
        dataset: str = "KYRBS/KNHANES",
        stat_result: dict | None = None,
        suggest_revision: bool = True,
    ) -> ReviewResult:
        """논문 전체 텍스트를 평가하고 ReviewResult를 반환.

        Args:
            paper_text: 전체 논문 초안 (섹션 포함)
            topic: 연구 주제
            dataset: 사용 데이터셋 이름
            stat_result: StatBridge.to_dict() 결과 (있으면 통계 검증에 활용)
            suggest_revision: True면 revised abstract 생성
        """
        try:
            raw = self._call_reviewer(paper_text, topic, dataset, stat_result)
            result = self._parse_review(raw)
            if suggest_revision and result.total_score < 80:
                result.revised_abstract = self._revise_abstract(paper_text, result)
            # ★ STROBE 정형 체크리스트 — free-form 리뷰에 정량 보완
            try:
                from src.research.reporting_checklist import auto_check, format_checklist_report
                sections = {"Introduction": "", "Methods": "", "Results": "", "Discussion": "",
                            "Abstract": paper_text[:2000]}
                # 본문에서 섹션 단순 분리 (헤딩 기반)
                import re as _re
                for sec in list(sections.keys()):
                    pat = _re.compile(rf"\b{sec}\b\s*\n", _re.IGNORECASE)
                    m = pat.search(paper_text)
                    if m:
                        nxt = paper_text.find("\n\n", m.end())
                        sections[sec] = paper_text[m.end(): nxt if nxt > 0 else len(paper_text)]
                checklist = auto_check(sections, abstract=sections["Abstract"],
                                        study_type="cross_sectional")
                # ReviewResult에 보고서 append
                summary = format_checklist_report(checklist, verbose=True)
                if hasattr(result, "summary") and isinstance(result.summary, str):
                    result.summary = (result.summary + "\n\n" + summary)
                elif hasattr(result, "comments") and isinstance(result.comments, list):
                    result.comments.append(summary)
            except Exception:
                pass
            return result
        except Exception as e:
            _log.error("PeerReviewer.review failed: %s", e, exc_info=True)
            return ReviewResult(
                total_score=0, max_score=TOTAL_MAX, grade="N/A",
                accept_recommendation="error", error=str(e),
            )

    def quick_score(self, paper_text: str, topic: str) -> int:
        """빠른 점수만 반환 (0-100). 상세 리뷰 없음."""
        result = self.review(paper_text, topic, suggest_revision=False)
        return result.total_score

    # ------------------------------------------------------------------
    # LLM calls
    # ------------------------------------------------------------------

    def _call_reviewer(
        self,
        paper_text: str,
        topic: str,
        dataset: str,
        stat_result: dict | None,
    ) -> str:
        provider, model_id = get_model(task="paper_review")
        system = self._build_system()

        stat_block = ""
        if stat_result:
            stat_block = f"""
## Actual Statistical Results (for validation)
{json.dumps(stat_result, ensure_ascii=False, indent=2)[:1500]}
"""

        prompt = f"""You are reviewing the following Korean public health paper for submission to a Korean medical journal.

TOPIC: {topic}
DATASET: {dataset}
{stat_block}

PAPER DRAFT:
{paper_text[:6000]}

---

Evaluate this paper using the following rubric. Respond in valid JSON only.

Rubric (total 100 points):
{json.dumps({k: {"label": v["label"], "desc": v["desc"], "max": v["max"]} for k, v in RUBRIC.items()}, ensure_ascii=False)}

Required JSON response format:
{{
  "scores": {{
    "originality": <int 0-20>,
    "methodology": <int 0-25>,
    "results_clarity": <int 0-20>,
    "clinical_relevance": <int 0-20>,
    "writing_quality": <int 0-15>
  }},
  "section_feedback": {{
    "originality": {{
      "strengths": ["..."],
      "weaknesses": ["..."],
      "suggestions": ["..."]
    }},
    "methodology": {{...}},
    "results_clarity": {{...}},
    "clinical_relevance": {{...}},
    "writing_quality": {{...}}
  }},
  "key_strengths": ["top 2-3 overall strengths"],
  "major_concerns": ["top 2-3 issues requiring revision"],
  "minor_concerns": ["minor stylistic/formatting issues"],
  "suggested_analyses": ["additional statistical tests or sensitivity analyses to strengthen the paper"],
  "accept_recommendation": "accept|minor_revision|major_revision|reject"
}}

Write only the JSON object, no markdown fences."""

        resp = self._client.generate(
            user_message=prompt,
            system_prompt=system,
            max_tokens=4000,
            task="paper_review",
        )
        return resp if isinstance(resp, str) else str(resp)

    def _revise_abstract(self, paper_text: str, review: ReviewResult) -> str:
        """리뷰 피드백을 반영한 개선된 abstract 생성."""
        provider, model_id = get_model(task="paper_writing")
        system = self._build_system()

        concerns = "\n".join(f"- {c}" for c in review.major_concerns)
        abstract_match = re.search(
            r"(Abstract|초록)(.*?)(Introduction|서론|Background)",
            paper_text, re.DOTALL | re.IGNORECASE
        )
        orig_abstract = abstract_match.group(2).strip() if abstract_match else paper_text[:800]

        prompt = f"""Revise the following abstract to address the reviewer's major concerns.
Keep it under 250 words. Maintain structured format (Background/Objective/Methods/Results/Conclusion).

ORIGINAL ABSTRACT:
{orig_abstract}

REVIEWER'S MAJOR CONCERNS TO ADDRESS:
{concerns}

Write only the revised abstract text."""

        try:
            return self._client.generate(
                user_message=prompt,
                system_prompt=system,
                max_tokens=600,
                task="paper_writing",
            )
        except Exception as e:
            _log.warning("Abstract revision failed: %s", e)
            return ""

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    def _parse_review(self, raw: str) -> ReviewResult:
        # Strip markdown fences if present
        raw = re.sub(r"```json\s*", "", raw)
        raw = re.sub(r"```\s*", "", raw)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON block
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    # JSON이 잘린 경우: scores만 추출해서 부분 복구
                    data = self._extract_partial_json(raw)
            else:
                data = self._extract_partial_json(raw)
            if data is None:
                raise ValueError(f"Cannot parse LLM reviewer output: {raw[:200]}")

        scores_raw = data.get("scores", {})
        feedback_raw = data.get("section_feedback", {})

        section_scores = {}
        total = 0
        for key, rubric_info in RUBRIC.items():
            score = int(scores_raw.get(key, 0))
            score = min(score, rubric_info["max"])
            fb = feedback_raw.get(key, {})
            section_scores[key] = SectionFeedback(
                section=rubric_info["label"],
                score=score,
                max_score=rubric_info["max"],
                strengths=fb.get("strengths", []),
                weaknesses=fb.get("weaknesses", []),
                suggestions=fb.get("suggestions", []),
            )
            total += score

        grade = self._score_to_grade(total)
        rec = data.get("accept_recommendation", "major_revision")

        return ReviewResult(
            total_score=total,
            max_score=TOTAL_MAX,
            grade=grade,
            accept_recommendation=rec,
            section_scores=section_scores,
            key_strengths=data.get("key_strengths", []),
            major_concerns=data.get("major_concerns", []),
            minor_concerns=data.get("minor_concerns", []),
            suggested_analyses=data.get("suggested_analyses", []),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_partial_json(raw: str) -> Optional[dict]:
        """잘린 JSON에서 scores 블록만 정규식으로 추출해 부분 복구."""
        data: dict = {}
        # scores 블록 추출
        scores_match = re.search(r'"scores"\s*:\s*\{([^}]+)\}', raw, re.DOTALL)
        if scores_match:
            try:
                scores_raw = json.loads("{" + scores_match.group(1) + "}")
                data["scores"] = scores_raw
            except Exception:
                # 개별 점수 추출
                scores_raw = {}
                for key in ["originality", "methodology", "results_clarity", "clinical_relevance", "writing_quality"]:
                    m = re.search(rf'"{key}"\s*:\s*(\d+)', raw)
                    if m:
                        scores_raw[key] = int(m.group(1))
                if scores_raw:
                    data["scores"] = scores_raw
        # recommendation 추출
        rec_m = re.search(r'"accept_recommendation"\s*:\s*"([^"]+)"', raw)
        if rec_m:
            data["accept_recommendation"] = rec_m.group(1)
        return data if data else None

    @staticmethod
    def _build_system() -> str:
        return (
            "You are a senior editor at a top-tier Korean public health journal "
            "(e.g., Journal of Korean Medical Science, Korean Journal of Preventive Medicine). "
            "You specialize in cross-sectional survey studies using KYRBS and KNHANES. "
            "Your reviews are constructive, specific, and actionable. "
            "You always respond in valid JSON when asked."
        )

    @staticmethod
    def _score_to_grade(score: int) -> str:
        if score >= 90:
            return "A+"
        elif score >= 85:
            return "A"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 65:
            return "C"
        elif score >= 50:
            return "D"
        return "F"
