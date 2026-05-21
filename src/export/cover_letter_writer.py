"""Cover Letter Writer — 저널 제출용 커버 레터 자동 생성.

저널명 + 연구 주제 + 동료 심사 결과를 기반으로
영문 학술 커버 레터를 LLM으로 생성하고 파일로 저장한다.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

from src.config.logging_config import get_logger
from src.llm import get_llm_client

_log = get_logger(__name__)
_COVER_DIR = Path("data/drafts/cover_letters")


class CoverLetterWriter:
    """연구 파이프라인 결과 → 저널 제출용 커버 레터 생성."""

    def __init__(self, llm_client=None):
        self._llm = llm_client or get_llm_client(task="standard")

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def generate(
        self,
        topic: Dict,
        study_info: Dict,
        journal_name: str = "Journal of Korean Medical Science",
        review_result: Optional[Dict] = None,
        author_name: str = "Yoosun Cho",
        affiliation: str = "",
    ) -> str:
        """커버 레터 영문 텍스트 생성.

        Returns: 완성된 커버 레터 문자열
        """
        n_total_raw = study_info.get("sample_size", "")
        dataset = study_info.get("dataset", "KYRBS")
        design = study_info.get("design", "cross-sectional study")
        # n_total_raw may be a string ("54633") — format safely
        try:
            n_total_display = f"{int(str(n_total_raw).replace(',', '')):,}" if n_total_raw else ""
        except (ValueError, TypeError):
            n_total_display = str(n_total_raw)

        strengths_block = ""
        if review_result:
            ks = review_result.get("key_strengths", [])
            if ks:
                strengths_block = "PAPER STRENGTHS (from peer review):\n" + "\n".join(
                    f"- {s}" for s in ks[:3]
                )

        n_suffix = f" (n={n_total_display})" if n_total_display else ""
        prompt = f"""Write a professional academic cover letter for journal submission.

JOURNAL: {journal_name}
MANUSCRIPT TITLE: {topic.get("title", "")}
AUTHORS: {author_name}
AFFILIATION: {affiliation or "Department of Public Health"}
STUDY DESIGN: {design}
DATASET: {dataset}{n_suffix}
EXPOSURE: {topic.get("exposure", "")}
OUTCOME: {topic.get("outcome", "")}
POPULATION: {topic.get("population", "")}
{strengths_block}

Write a complete, professional cover letter (300-400 words) including:
1. Salutation to Editor-in-Chief
2. Why this manuscript is appropriate for this journal
3. Significance and novelty of the findings
4. Statement that this manuscript has not been published or submitted elsewhere
5. Ethics and data availability statement
6. Conflicts of interest declaration
7. Closing with author contact information

Use formal academic English. Replace no text with placeholders."""

        try:
            letter = self._llm.generate(user_message=prompt, max_tokens=1500, task="general")
            _log.info("커버 레터 생성 완료 (%d자)", len(letter))
            return letter
        except Exception as e:
            _log.error("커버 레터 생성 실패: %s", e)
            return f"[Cover letter generation failed: {e}]"

    def save(self, letter_text: str, safe_title: str) -> str:
        """data/drafts/cover_letters/{safe_title}_cover.txt 저장. 경로 반환."""
        _COVER_DIR.mkdir(parents=True, exist_ok=True)
        out = _COVER_DIR / f"{safe_title}_cover.txt"
        out.write_text(letter_text, encoding="utf-8")
        _log.info("커버 레터 저장: %s", out)
        return str(out)


# ── 편의 함수 ─────────────────────────────────────────────────────────────────

def generate_cover_letter(
    topic: Dict,
    study_info: Dict,
    journal_name: str = "Journal of Korean Medical Science",
    review_result: Optional[Dict] = None,
    llm_client=None,
    save: bool = True,
) -> tuple:
    """커버 레터 생성 + 저장.

    Returns: (letter_text: str, saved_path: str | None)
    """
    writer = CoverLetterWriter(llm_client)
    letter = writer.generate(
        topic=topic,
        study_info=study_info,
        journal_name=journal_name,
        review_result=review_result,
        author_name=study_info.get("authors", "Yoosun Cho"),
        affiliation=study_info.get("affiliation", ""),
    )
    path = None
    if save:
        safe_title = "".join(
            c if c.isalnum() or c in " _-" else "_"
            for c in topic.get("title", "draft")
        )[:60]
        path = writer.save(letter, safe_title)
    return letter, path
