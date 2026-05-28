"""Trigger Analyzer — 사용자 입력의 의도/주제/감정/우선순위/긴급도 자동 분류.

Vision 다이어그램 입력 소스의 "트리거 분석기" 컴포넌트. Cognitive Activation 의
fragment trigger와 보완 — fragment는 토큰 수준, trigger는 메시지 수준 의도.

분류 5축:
  · intent       — write/revise/analyze/verify/explain/ask/configure
  · topic        — paper_section / data / citation / figure / system / meta
  · sentiment    — positive | neutral | negative | urgent | frustrated
  · priority     — low | normal | high | blocking
  · urgency_sec  — 예상 처리 기한 (초 단위 heuristic)

LLM 없이 정규식 + 키워드 기반 (비용 0). 모호 시 LLM 호출 옵션 (`use_llm=True`).

호출:
    from src.agent.trigger_analyzer import analyze
    t = analyze("ZCB Methods 좀 빨리 채워줘")
    # {"intent":"write", "topic":"paper_section.methods", "sentiment":"urgent",
    #  "priority":"high", "urgency_sec": 300, ...}
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── Intent classification ───────────────────────────────────────────────────

_INTENT_PATTERNS = [
    ("write",     r"\b(써|작성|만들|채워|넣어|compose|write|build|create|make|fill)\b"),
    ("revise",    r"\b(수정|고쳐|바꿔|재작성|개선|보강|refactor|revise|edit|fix|improve|update)\b"),
    ("analyze",   r"\b(분석|돌려|돌려봐|통계|계산|run|analyze|compute|calculate|stat)\b"),
    ("verify",    r"\b(검증|확인|체크|맞나|맞는지|verify|check|validate|test|confirm)\b"),
    ("explain",   r"\b(설명|왜|어떻게|explain|why|how|describe|tell)\b"),
    ("ask",       r"^(.*\?$|뭐|뭐야|있어|없어|언제|어디|누가|what|where|when|who|which|is\s+there)\b"),
    ("configure", r"\b(설정|구성|토글|enable|disable|config|set\s+|change\s+to)\b"),
    ("delete",    r"\b(지워|삭제|제거|delete|remove|clear)\b"),
    ("show",      r"\b(보여|보여줘|show|display|list|view)\b"),
]

_TOPIC_PATTERNS = [
    ("paper_section.abstract",     r"\babstract\b|초록"),
    ("paper_section.introduction", r"\bintro(?:duction)?\b|서론"),
    ("paper_section.methods",      r"\bmethods?\b|방법|연구\s*설계"),
    ("paper_section.results",      r"\bresults?\b|결과"),
    ("paper_section.discussion",   r"\bdiscussion\b|고찰|토의"),
    ("data.kyrbs",                 r"\bkyrbs\b|청소년"),
    ("data.knhanes",               r"\bknhanes\b|국민건강"),
    ("citation",                   r"\b(citation|reference|인용|레퍼런스|참고문헌|pubmed|doi|pmid)\b"),
    ("figure",                     r"\bfigure|fig\.|그림|forest\s+plot|roc"),
    ("table",                      r"\btable\b|표\b|table\s*1|table\s*2"),
    ("style.yoosun",               r"\byoosun|조유선"),
    ("safety",                     r"\b(safety|환각|hallucin|grounding|strobe|consistency)\b"),
    ("system",                     r"\b(streamlit|docker|backlog|heartbeat|sandbox|deploy|배포|server)\b"),
    ("meta",                       r"\b(memory|agent|tool|prompt|vision|architecture|메모리|아키텍처)\b"),
]

_URGENT_PATTERNS = re.compile(
    r"(빨리|급해|시급|asap|urgent|now|즉시|right\s+now|당장)", re.IGNORECASE)
_FRUSTRATED_PATTERNS = re.compile(
    r"(왜\s|틀렸|틀린|안되|안돼|안나와|이상해|망|broken|wrong|fail(?:ed)?|fuck|shit|sigh)",
    re.IGNORECASE)
_POSITIVE_PATTERNS = re.compile(
    r"(좋아|좋다|nice|good|great|thanks|감사|좋습니다|excellent|좋은|마음에)",
    re.IGNORECASE)


@dataclass
class TriggerAnalysis:
    text: str
    intent: str = "unknown"
    intent_confidence: float = 0.0
    topics: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    priority: str = "normal"
    urgency_sec: int = 3600          # 기본 1h
    is_question: bool = False
    is_imperative: bool = False
    estimated_ttft_sec: int = 5      # time-to-first-token 예측
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict:
        return asdict(self)


def analyze(text: str, *, use_llm: bool = False) -> TriggerAnalysis:
    """사용자 메시지 분석. LLM 없이도 작동, use_llm=True면 모호 시 LLM."""
    text = (text or "").strip()
    a = TriggerAnalysis(text=text[:600])

    if not text:
        return a

    # intent 매칭 — 첫 매칭 + score
    text_low = text.lower()
    matches: List[tuple] = []
    for label, pat in _INTENT_PATTERNS:
        if re.search(pat, text_low):
            matches.append(label)
    if matches:
        a.intent = matches[0]
        a.intent_confidence = round(1.0 if len(matches) == 1 else 0.7, 2)
    a.is_question = "?" in text or text_low.startswith(("뭐", "what", "why", "how", "where"))
    a.is_imperative = bool(re.search(r"(해줘|줘|만들어|보여|줘봐|줘$|please)", text_low))

    # topic 다중 매칭
    for label, pat in _TOPIC_PATTERNS:
        if re.search(pat, text_low):
            a.topics.append(label)

    # sentiment
    if _URGENT_PATTERNS.search(text):
        a.sentiment = "urgent"
    elif _FRUSTRATED_PATTERNS.search(text):
        a.sentiment = "frustrated"
    elif _POSITIVE_PATTERNS.search(text):
        a.sentiment = "positive"

    # priority + urgency_sec
    if a.sentiment in ("urgent", "frustrated"):
        a.priority = "high"
        a.urgency_sec = 300       # 5min
    if any(t.startswith("safety") or t.startswith("system") for t in a.topics):
        a.priority = "high"
        a.urgency_sec = min(a.urgency_sec, 600)
    if "delete" == a.intent or "configure" == a.intent:
        a.priority = "high"
        a.urgency_sec = min(a.urgency_sec, 300)
    if a.is_question and not a.is_imperative:
        a.priority = "low"
        a.urgency_sec = 7200      # 2h

    # TTFT 추정 — 단순 (write/revise는 느림, ask/show는 빠름)
    a.estimated_ttft_sec = {
        "write": 8, "revise": 6, "analyze": 10, "verify": 5,
        "explain": 4, "ask": 3, "show": 2, "configure": 1, "delete": 1,
    }.get(a.intent, 5)

    # LLM 보강 옵션
    if use_llm and a.intent_confidence < 0.5:
        try:
            from src.llm import get_llm_client
            client = get_llm_client(task="fast")
            prompt = (f"Classify the user request below. Reply with JSON only:\n"
                       f'{{"intent":"write|revise|analyze|verify|explain|ask|configure|show|delete",'
                       f'"topic":"...","sentiment":"positive|neutral|urgent|frustrated"}}\n\n'
                       f"User: {text[:500]}")
            r = client.generate(prompt, max_tokens=200)
            import json as _j
            try:
                d = _j.loads(re.search(r"\{[\s\S]*\}", r).group(0))
                a.intent = d.get("intent", a.intent)
                a.intent_confidence = 0.85
                if d.get("topic"):
                    a.topics.append(d["topic"])
                if d.get("sentiment"):
                    a.sentiment = d["sentiment"]
            except Exception:
                pass
        except Exception:
            pass

    # events
    try:
        from src.runtime import events as _events
        _events.append("trigger_analyzed",
                        {"intent": a.intent, "topics": a.topics[:5],
                         "sentiment": a.sentiment, "priority": a.priority,
                         "urgency_sec": a.urgency_sec},
                        actor="trigger_analyzer")
    except Exception:
        pass
    return a
