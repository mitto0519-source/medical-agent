"""Auto-learning — LLM이 파이프라인 결과를 보고 스스로 인사이트를 기록.

파이프라인의 각 단계(주제 생성, 신규성 확인, 논문 작성) 완료 후 자동 호출.
LLM이 결과를 보고 '배울 것이 있는가?'를 스스로 판단하고 agent_insight에 기록.

- 기록 여부를 LLM이 직접 결정 (trivial한 결과는 skip)
- Haiku 사용 (빠르고 저렴)
- 실패해도 파이프라인 본 작업에 영향 없음 (완전 독립)
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PROMPT_TEMPLATE = """You are the self-learning memory of a medical research AI pipeline.
Analyze the completed action below and decide if there is something genuinely worth recording as a reusable insight.

ACTION: {action}
INPUTS: {inputs}
OUTPUTS: {outputs}

RECENT INSIGHT TITLES (avoid near-duplicates):
{recent_titles}

Record ONLY if the result reveals:
- A repeating pattern worth remembering
- A mistake or failure to prevent
- An optimization that improved results
- An important architectural or behavioral decision
Skip trivial, expected, or already-recorded observations.

Return JSON:
{{
  "should_record": true/false,
  "category": "pattern|mistake|optimization|next_action|decision",
  "title": "concise title (max 60 chars, Korean or English)",
  "insight": "what was learned (max 200 chars)",
  "why_matters": "why this matters for future runs (max 100 chars)",
  "how_to_apply": "how to apply this knowledge (max 100 chars)",
  "confidence": 0.0-1.0,
  "tags": ["tag1", "tag2"]
}}
Return JSON only."""


def reflect_and_record(
    action: str,
    inputs: Dict[str, Any],
    outputs: Dict[str, Any],
) -> Optional[object]:
    """파이프라인 결과를 LLM이 분석 후 인사이트 자동 기록.

    Returns:
        Insight 객체 (기록된 경우) 또는 None (skip 또는 오류)
    """
    try:
        from src.memory.agent_insight import get_all, record

        recent_titles = [e.get("title", "") for e in get_all(n=8)]

        prompt = _PROMPT_TEMPLATE.format(
            action=action,
            inputs=json.dumps(inputs, ensure_ascii=False)[:600],
            outputs=json.dumps(outputs, ensure_ascii=False)[:900],
            recent_titles=json.dumps(recent_titles, ensure_ascii=False)[:400],
        )

        from src.llm import get_llm_client
        llm = get_llm_client(task="fast")
        raw = llm.generate(prompt, max_tokens=512, task="fast")

        from src.research.research_pipeline import _clean_llm_response
        cleaned = _clean_llm_response(raw)
        if not cleaned:
            return None

        data = json.loads(cleaned)
        if not data.get("should_record"):
            _log.debug("[auto_learn] skip — LLM decided nothing to record for '%s'", action)
            return None

        insight = record(
            title=data["title"][:80],
            insight=data["insight"][:300],
            category=data.get("category", "pattern"),
            why_matters=data.get("why_matters", "")[:150],
            how_to_apply=data.get("how_to_apply", "")[:150],
            confidence=float(data.get("confidence", 0.8)),
            tags=data.get("tags", [action]),
            source="llm_reflection",
        )
        _log.info("[auto_learn] recorded: [%s] %s", insight.category, insight.title)
        return insight

    except Exception as e:
        _log.debug("[auto_learn] non-critical failure for '%s': %s", action, e)
        return None
