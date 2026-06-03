"""Anti-AI Filter — LLM 생성 본문에서 AI 흔적(LLM-스러움)을 탐지 + 정리.

사용자 비전 (2026-06-01):
    "자산화 → AI 같지 않도록 필터링 → 조유선 스타일로 최종 변환" 의 2단계.
    style_polish(cliché 정리)와는 별개로, 더 본질적인 AI 흔적을 잡는다.

스타일 폴리시와 차이:
    style_polish.py (이미 있음) → "furthermore/moreover" 같은 학술 cliché
    anti_ai_filter.py (본 모듈) → 더 본질적 AI 신호:
        1. 일반화 도입 ("It is well known that...", "In recent years,...")
        2. Hedging 클러스터 ("may suggest that this could potentially indicate...")
        3. 메타 phrase ("In conclusion", "In summary", "To this end")
        4. AI 클리셰 ("sheds light on", "paves the way", "underscores the importance")
        5. 과한 transition ("Additionally", "Furthermore", "Moreover" 빈도)
        6. 단조 문장 리듬 (모든 문장이 25±3 단어)
        7. 트라이콜론 리스트 과사용 ("X, Y, and Z")
        8. 추상화 (구체 숫자·이름 부재)

산출:
    AIScore(score: 0-100 — 높을수록 AI-스러움)
    filter_text(text, mode='gentle'|'aggressive') -> 정리된 텍스트
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── AI 흔적 패턴 (가중치 포함) ───────────────────────────────────────────

# 일반화·동어반복적 도입 (LLM이 즐겨 쓰는 안전한 문장 첫머리)
_GENERIC_OPENERS = [
    r"\bIt is (?:well[- ]?known|widely (?:accepted|recogni[sz]ed|established)|important to note|worth noting|crucial to (?:note|understand))\b",
    r"\b(?:In recent (?:years|decades),?\s+\w+ (?:has|have) (?:become|emerged|gained|been))\b",
    r"\b(?:Over the (?:past|last) (?:few |several )?(?:years|decades),?\s+\w+)\b",
    r"\b(?:With the (?:increasing|growing|rising) (?:prevalence|incidence|interest|attention))\b",
    r"\bAs (?:we|the world|society|the field) (?:moves?|progresses?|evolves?) (?:toward|into)\b",
]

# 과한 hedging 클러스터 — 동사 3개 이상 hedge가 한 문장 내
_HEDGE_CLUSTER = re.compile(
    r"\b(?:may|might|could|would|appear[s]? to|seem[s]? to|suggest[s]? that|"
    r"indicate[s]? that|imply (?:that)?|possibly|potentially|presumably)\b",
    re.IGNORECASE,
)

# 메타 phrase 잔재 — 본문에 절대 들어가면 안 되는 LLM 메타
_META_PHRASES = [
    r"\bIn (?:conclusion|summary|essence|brief|short)\b,?",
    r"\bTo (?:this end|that end|conclude|summari[sz]e|recap)\b,?",
    r"\bAt this juncture\b,?",
    r"\bWith that (?:said|in mind)\b,?",
    r"\bMoving forward\b,?",
    r"\bGoing forward\b,?",
    r"\bIt should be noted that\b",
    r"\bIt is (?:also )?important to (?:note|highlight|emphasi[sz]e|consider) that\b",
    r"\bIt is worth (?:noting|highlighting|mentioning|considering) that\b",
]

# AI 클리셰 — 학술 글에 어울리지 않는 LLM 즐겨 쓰는 표현
_AI_CLICHES = [
    r"\bsheds? light on\b",
    r"\bpave[s]? the way\b",
    r"\bunderscore[s]? the importance\b",
    r"\bhighlight[s]? the (?:significance|importance|critical (?:role|need))\b",
    r"\bplays? a (?:crucial|critical|pivotal|key|vital|important) role\b",
    r"\bin the (?:realm|landscape|world|field) of\b",
    r"\bnavigate[s]? the (?:complex(?:ities)?|challenges)\b",
    r"\bcomprehensive understanding\b",
    r"\bdelve[s]? into\b",
    r"\btapestry of\b",
    r"\brich tapestry\b",
    r"\bmyriad (?:of |challenges|factors)\b",
    r"\ba testament to\b",
    r"\bunderscores? the need\b",
]

# 과한 transition (한 문단에 2개 이상이면 AI)
_OVERUSED_TRANSITIONS = [
    "Additionally,", "Furthermore,", "Moreover,",
    "Subsequently,", "Consequently,", "Nevertheless,",
    "In addition,", "On the other hand,",
]

# 트라이콜론 리스트 — "X, Y, and Z"  자체는 정상이나
# 한 단락에 3+개 양식이면 AI 정형 
_TRICOLON = re.compile(r"\b\w+, \w+,? (?:and|or) \w+\b", re.IGNORECASE)


@dataclass
class AIScore:
    score: float = 0.0          # 0-100, 높을수록 AI-스러움
    generic_openers: int = 0
    hedge_clusters: int = 0
    meta_phrases: int = 0
    ai_cliches: int = 0
    transition_overuse: int = 0
    tricolon_density: float = 0.0     # per 100 sentences
    sentence_rhythm_var: float = 0.0  # std/mean
    details: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "generic_openers": self.generic_openers,
            "hedge_clusters": self.hedge_clusters,
            "meta_phrases": self.meta_phrases,
            "ai_cliches": self.ai_cliches,
            "transition_overuse": self.transition_overuse,
            "tricolon_density": round(self.tricolon_density, 2),
            "sentence_rhythm_var": round(self.sentence_rhythm_var, 3),
            "details": self.details[:30],
        }


# ── 문장 단위 분해 ─────────────────────────────────────────────────────

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z\(])")


def _sentences(text: str) -> List[str]:
    if not text:
        return []
    return [s.strip() for s in _SENT_SPLIT.split(text) if len(s.strip()) > 8]


# ── 점수 산출 ──────────────────────────────────────────────────────────

def ai_score(text: str) -> AIScore:
    """본문에서 AI-스러움 점수 산출.

    component contribution:
        generic_openers     × 4
        hedge_clusters      × 3   (한 문장에 hedge ≥3)
        meta_phrases        × 6   (가장 분명한 AI 흔적)
        ai_cliches          × 5
        transition_overuse  × 3
        tricolon_density    ×10   (> 0.3 per sent)
        sentence_rhythm_var ×15   (std/mean < 0.25 = 단조)
    """
    s = AIScore()
    if not text or len(text) < 80:
        return s

    sents = _sentences(text)
    n_sents = max(1, len(sents))

    # 1. Generic openers
    for pat in _GENERIC_OPENERS:
        for m in re.finditer(pat, text, re.IGNORECASE):
            s.generic_openers += 1
            s.details.append(f"generic_opener: '{m.group(0)[:60]}'")

    # 2. Hedge clusters (한 문장 내 hedge 3+)
    for sent in sents:
        hedges = _HEDGE_CLUSTER.findall(sent)
        if len(hedges) >= 3:
            s.hedge_clusters += 1
            s.details.append(f"hedge_cluster ({len(hedges)}): '{sent[:80]}'")

    # 3. Meta phrases
    for pat in _META_PHRASES:
        for m in re.finditer(pat, text, re.IGNORECASE):
            s.meta_phrases += 1
            s.details.append(f"meta_phrase: '{m.group(0)}'")

    # 4. AI cliches
    for pat in _AI_CLICHES:
        for m in re.finditer(pat, text, re.IGNORECASE):
            s.ai_cliches += 1
            s.details.append(f"ai_cliche: '{m.group(0)}'")

    # 5. Transition 과사용
    transition_count = 0
    for t in _OVERUSED_TRANSITIONS:
        transition_count += text.count(t)
    # 100 문장당 transition 5+ = 과사용
    if transition_count > n_sents * 0.05:
        s.transition_overuse = transition_count
        s.details.append(f"transition_overuse: {transition_count} in {n_sents} sentences")

    # 6. Tricolon density
    tri_count = len(_TRICOLON.findall(text))
    s.tricolon_density = tri_count / n_sents
    if s.tricolon_density > 0.3:
        s.details.append(f"tricolon_dense: {tri_count}/{n_sents}")

    # 7. Sentence rhythm variance (단조 = AI)
    if n_sents >= 5:
        lens = [len(sent.split()) for sent in sents]
        mean = sum(lens) / len(lens)
        if mean > 0:
            variance = sum((l - mean) ** 2 for l in lens) / len(lens)
            std = variance ** 0.5
            s.sentence_rhythm_var = std / mean
            if s.sentence_rhythm_var < 0.25:
                s.details.append(f"monotone_rhythm: std/mean={s.sentence_rhythm_var:.3f}")

    # ── 종합 점수 (0-100) ──
    raw = (
        s.generic_openers * 4
        + s.hedge_clusters * 3
        + s.meta_phrases * 6
        + s.ai_cliches * 5
        + (3 if s.transition_overuse > 0 else 0)
        + (max(0.0, (s.tricolon_density - 0.3)) * 30)
        + (max(0.0, (0.25 - s.sentence_rhythm_var)) * 60 if s.sentence_rhythm_var > 0 else 0)
    )
    s.score = min(100.0, raw * 2.0)   # scale
    return s


# ── 자동 정리 ──────────────────────────────────────────────────────────

def filter_text(text: str, *, mode: str = "gentle") -> Tuple[str, AIScore, AIScore]:
    """AI 흔적을 자동 정리.

    mode='gentle' : meta_phrases + ai_cliches만 제거 (보수적)
    mode='aggressive' : 위 + generic_openers 제거 + transition 일부 절단

    Returns: (정리된 텍스트, before_score, after_score)
    """
    before = ai_score(text)
    out = text

    # 1. Meta phrases 제거 (선두 또는 단락 시작)
    for pat in _META_PHRASES:
        out = re.sub(pat, "", out, flags=re.IGNORECASE)

    # 2. AI cliche 제거 → 더 직접적 표현으로
    cliche_replace = {
        r"\bsheds? light on\b": "clarifies",
        r"\bpave[s]? the way\b": "supports future",
        r"\bunderscore[s]? the (?:importance|need)\b": "supports the need",
        r"\bhighlight[s]? the (?:significance|importance)\b": "supports",
        r"\bplays? a (?:crucial|critical|pivotal|key|vital) role\b": "is central",
        r"\bin the (?:realm|landscape|world|field) of\b": "in",
        r"\bcomprehensive understanding\b": "understanding",
        r"\bdelve[s]? into\b": "examines",
    }
    for pat, repl in cliche_replace.items():
        out = re.sub(pat, repl, out, flags=re.IGNORECASE)

    if mode == "aggressive":
        # 3. Generic opener 절단 — 문장 통째 제거
        for pat in _GENERIC_OPENERS:
            out = re.sub(pat + r"[^.!?]*[.!?]\s*", "", out, flags=re.IGNORECASE)

        # 4. Transition 일부 절단 (문장 첫 단어)
        for t in _OVERUSED_TRANSITIONS:
            # 한 문단에 같은 transition 2번 이상이면 두 번째부터 제거
            parts = out.split(t)
            if len(parts) > 2:
                out = parts[0] + t + "".join(parts[1:])
                # 추가 발생분 제거
                for extra in parts[2:]:
                    out = out.replace(t + extra[:1], extra[:1], 1) if extra else out

    # 정리 후 중복 공백 / 빈 줄 정돈
    out = re.sub(r"[ \t]+\n", "\n", out)
    out = re.sub(r"\n{3,}", "\n\n", out)
    out = re.sub(r"  +", " ", out)
    out = out.strip()

    after = ai_score(out)
    return out, before, after


__all__ = ["AIScore", "ai_score", "filter_text"]
