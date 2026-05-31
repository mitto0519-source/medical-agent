"""Yoosun Finalize — 3단계: anti-AI 정리된 본문 → Yoosun 스타일 최종 변환.

사용자 비전 (2026-06-01) 3단계 파이프라인의 마지막:
    1단계: 자산화 (typology + humanize 카탈로그)
    2단계: anti-AI 필터 (style_polish + anti_ai_filter)
    3단계: 본 모듈 — Yoosun voice/cadence/hedging으로 최종 변환

지금까지 paper_writer가 system_prompt에 yoosun 양식을 박는 게 전부였음.
그것만으로는 LLM이 본문을 쓰면서 yoosun 양식을 절반만 따르고 절반은 generic.
이 stage는 별도 LLM 호출로 *완성된 본문* → *Yoosun voice 본문*만 변환한다.

흐름:
    원본 본문 (anti-AI 필터 통과)
      → yoosun_cho.json raw_examples 2-3개 + 본문을 LLM에 전달
      → "Rewrite the following passage in the EXACT voice/cadence/sentence rhythm
         of the author below. Preserve all numbers and citations." 지시
      → 변환된 본문 반환

검증:
    finalize(text) → 변환 후 텍스트 + ai_score 감소량

API:
    finalize(text, section_label='Discussion') -> str
    finalize_paper(sections: dict) -> dict
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PROFILE_PATH = Path("data/author_profiles/yoosun_cho.json")


def _load_exemplars(n: int = 2, per_chars: int = 700) -> str:
    """yoosun raw_examples 짧게 — system_prompt에 박지 않고 user_prompt에."""
    try:
        if not _PROFILE_PATH.exists():
            return ""
        d = json.loads(_PROFILE_PATH.read_text(encoding="utf-8"))
        exs = d.get("raw_examples") or []
        if not exs:
            return ""
        picks = exs[:n]
        block = "## AUTHOR'S VOICE — verbatim exemplars (mimic exactly)\n\n"
        for i, ex in enumerate(picks, 1):
            block += f"### Ex{i}\n{str(ex)[:per_chars]}\n\n"
        return block
    except Exception:
        return ""


def finalize(
    text: str,
    *,
    section_label: str = "section",
    llm_client=None,
    max_tokens: int = 4500,
    preserve_numbers: bool = True,
) -> str:
    """본문 한 섹션을 Yoosun voice로 변환.

    Args:
        text: 원본 본문 (anti-AI 필터 후)
        section_label: 'Introduction' / 'Methods' / 'Results' / 'Discussion' / 'Abstract'
        llm_client: 미지정 시 get_llm_client(task='paper_writing')
        preserve_numbers: True면 OR/CI/P 값 보존 강제 prompt

    Returns: Yoosun voice로 변환된 본문 (실패 시 원본)
    """
    if not text or len(text) < 80:
        return text

    if llm_client is None:
        try:
            from src.llm import get_llm_client
            llm_client = get_llm_client(task="paper_writing")
        except Exception as e:
            _log.warning("[YoosunFinalize] llm import 실패: %s", e)
            return text

    exemplars = _load_exemplars()
    if not exemplars:
        _log.warning("[YoosunFinalize] yoosun raw_examples 없음 — 원본 반환")
        return text

    preserve_clause = (
        "PRESERVE EXACTLY (do NOT change): all numbers, OR/HR/RR/CI/P values, "
        "n counts, percentages, study names (KYRBS/KNHANES/NHANES), reference "
        "citations [N], variable names, statistical method names. Only change "
        "voice, sentence structure, verb selection, and hedging.\n\n"
    ) if preserve_numbers else ""

    user_prompt = (
        f"{exemplars}\n"
        f"## TASK\n"
        f"Rewrite the following {section_label} in the EXACT voice/cadence/sentence "
        f"rhythm of the author shown above. Match: opening verbs, hedging style, "
        f"topic-sentence structure, sentence length variation, choice of qualifiers.\n\n"
        f"{preserve_clause}"
        f"Do NOT add a meta preamble. Output ONLY the rewritten {section_label} text.\n\n"
        f"## ORIGINAL {section_label.upper()}\n{text}\n"
    )

    sys_prompt = (
        "You are an expert academic-style transformer. Your sole job is to "
        "rewrite biomedical paper sections in a specific author's voice while "
        "preserving every factual claim, number, and citation. Do not editorialize. "
        "Do not add a preamble. Output only the rewritten section text."
    )

    try:
        out = llm_client.generate(
            user_prompt,
            system_prompt=sys_prompt,
            max_tokens=max_tokens,
        ) or ""
        out = out.strip()
        # 빈 응답 → 원본 보존
        if len(out) < len(text) * 0.4:
            _log.warning("[YoosunFinalize] 출력 짧음(%d vs %d) — 원본 반환",
                          len(out), len(text))
            return text
        return out
    except Exception as e:
        _log.warning("[YoosunFinalize] LLM 실패: %s — 원본 반환", e)
        return text


def finalize_paper(
    sections: Dict[str, str],
    *,
    llm_client=None,
    section_keys: Optional[list] = None,
) -> Dict[str, str]:
    """5섹션 dict를 모두 Yoosun voice로 변환.

    Args:
        sections: {'Abstract': '...', 'Introduction': '...', ...}
        section_keys: 변환할 키 (None이면 모두)
    """
    if section_keys is None:
        section_keys = ["Abstract", "Introduction", "Methods", "Results", "Discussion"]
    out: Dict[str, str] = {}
    for k in section_keys:
        body = sections.get(k) or sections.get(k.lower())
        if not body:
            out[k] = body or ""
            continue
        _log.info("[YoosunFinalize] %s 변환 중 (%d자)", k, len(body))
        out[k] = finalize(body, section_label=k, llm_client=llm_client)
    # 변환 안 한 키는 그대로 보존
    for k, v in sections.items():
        if k not in out:
            out[k] = v
    return out


__all__ = ["finalize", "finalize_paper"]
