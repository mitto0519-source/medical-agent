"""Academic Style Polish — 의학 논문의 "AI-스러움" 제거 + Yoosun  일치.

목적:
    LLM이 자동 생성한 의학 논문 본문에 흔히 나타나는 stylistic 약점을 정형 검출 + 자동 교정.
    이는 AI detector 우회가 아니라 학술 글의 명료성·구체성·가독성을 높이는 작업.

    구체적으로:
    1. 과사용 vocabulary (delve, leverage, nuanced, robust, multifaceted...)
    2. 학술 cliché ("It is important to note", "In conclusion", "Furthermore" 과사용)
    3. Em-dash 과사용 (한 단락 1회 이하)
    4. Vague qualifier ("many studies", "significantly" without P-value)
    5. Tricolon (3-way parallel) 자제

    Yoosun(조유선) 양식과 정합:
    - hedging 권장 (independently associated, may, appears to)
    - 전환어는 다양화 (Furthermore 과사용 → Also, Notably, Similarly 혼용)

API:
    polish_text(text, *, mode="aggressive"|"gentle") -> str
    ai_style_score(text) -> dict  # 0~100점 (낮을수록 자연스러움)
    polish_paper(sections: dict) -> dict  # 5섹션 한 번에

호출 위치:
    - _orchestrated_paper_run의 paper_writer 출력 직후 (자동 polish)
    - References 탭 옆 "✨ Style polish" 버튼 (수동)
    - chat에서 "AI스러워, 다듬어줘" 요청 시 patch_preview 전 적용
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field, asdict
from typing import Dict, List


# ──────────────────────────────────────────────────────────────────────────
# 패턴 정의 — 의학 학술 글에 부적합한 표현 + Yoosun  권장 대체어
# ──────────────────────────────────────────────────────────────────────────

# 단어/구절 치환 (대소문자 무관). 의학 논문 양식에 안 맞는 hyperbole/cliché 제거.
VOCAB_REPLACEMENTS: list[tuple[str, str]] = [
    # AI overuse vocabulary
    (r"\bdelve into\b",                 "examine"),
    (r"\bdelving into\b",               "examining"),
    (r"\bleverage(s)?\b",               r"use\1"),
    (r"\bleveraging\b",                 "using"),
    (r"\bnuanced\b",                    "specific"),
    (r"\bmultifaceted\b",               "complex"),
    (r"\brobust findings?\b",           "consistent findings"),
    (r"\bcomprehensive\b",              "thorough"),
    (r"\bintricate\b",                  "complex"),
    (r"\bparamount\b",                  "key"),
    (r"\bpivotal\b",                    "key"),
    (r"\bostensibly\b",                 "apparently"),
    (r"\bholistic\b",                   "overall"),
    (r"\bsalient\b",                    "key"),
    (r"\bmyriad\b",                     "many"),
    (r"\bplethora\b",                   "range"),
    (r"\bnavigate the complexit(y|ies) of\b", "address"),
    (r"\btapestry of\b",                "range of"),
    (r"\bunderscore(s|d)? the significance\b", r"emphasize\1"),
    (r"\bshed(s)? light on\b",          r"clarif\1ies"),
    (r"\bin the realm of\b",            "in"),
    (r"\bat the forefront of\b",        "leading"),
    (r"\bvarious\b",                    "several"),

    # Cliché openers
    (r"\bIt is important to note that\b",     ""),
    (r"\bIt should be noted that\b",          ""),
    (r"\bIt is worth noting that\b",          ""),
    (r"\bIt is well established that\b",      ""),
    (r"\bIt is widely recognized that\b",     ""),

    # Conclusion stuffers (medical paper has structured Discussion, doesn't need these)
    (r"\bIn conclusion,?\s*",                 ""),
    (r"\bIn summary,?\s*",                    ""),
    (r"\bTo conclude,?\s*",                   ""),
    (r"\bTo summarize,?\s*",                  ""),
    (r"\bIn essence,?\s*",                    ""),
    (r"\bAll in all,?\s*",                    ""),

    # Vague intensifiers
    (r"\bsignificantly higher chance\b",      "higher odds"),
    (r"\bquite\b",                            ""),
    (r"\bvery\b",                             ""),
    (r"\brather\b",                           ""),
]

# 전환어 과사용 — 한 단락에 같은 전환어 2회 이상 등장 시 일부를 다양화
TRANSITION_VARIANTS: dict[str, list[str]] = {
    "furthermore":  ["also", "additionally", "notably", "similarly"],
    "moreover":     ["also", "in addition", "notably"],
    "additionally": ["also", "further", "moreover"],
    "however":      ["yet", "in contrast", "whereas"],
    "thus":         ["therefore", "accordingly", "hence"],
}


@dataclass
class StyleReport:
    """style polish 진단 보고."""
    ai_style_score: int = 0       # 0(자연스러움) ~ 100(매우 AI스러움)
    hits: List[Dict] = field(default_factory=list)
    sentence_count: int = 0
    avg_sentence_len: float = 0.0
    burstiness: float = 0.0       # stdev/mean — 낮을수록 단조로움(AI-like)
    em_dash_per_1k_words: float = 0.0
    cliche_count: int = 0
    overused_vocab_count: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────────────
# Detection
# ──────────────────────────────────────────────────────────────────────────

def ai_style_score(text: str) -> StyleReport:
    """0~100 점 (낮을수록 자연스러움) + 어떤 패턴이 잡혔는지 breakdown."""
    rep = StyleReport()
    if not text or len(text) < 30:
        return rep

    # 1) Vocabulary cliché hit
    vocab_total = 0
    for pat, _ in VOCAB_REPLACEMENTS:
        n = len(re.findall(pat, text, re.IGNORECASE))
        if n:
            rep.hits.append({"type": "cliche/overused", "pattern": pat, "count": n})
            vocab_total += n
    rep.overused_vocab_count = vocab_total

    # 2) Em-dash density
    em_dash_count = text.count("—") + text.count("–")
    words = re.findall(r"\b\w+\b", text)
    word_count = max(len(words), 1)
    rep.em_dash_per_1k_words = round(em_dash_count / word_count * 1000, 2)

    # 3) Sentence length variance (burstiness)
    sentences = [s.strip() for s in re.split(r"[.!?]+", text) if len(s.strip().split()) > 3]
    rep.sentence_count = len(sentences)
    lens = [len(s.split()) for s in sentences]
    if lens:
        rep.avg_sentence_len = round(statistics.mean(lens), 1)
        if len(lens) > 5:
            try:
                stdev = statistics.stdev(lens)
                rep.burstiness = round(stdev / max(rep.avg_sentence_len, 1), 3)
            except statistics.StatisticsError:
                rep.burstiness = 0.0

    # 4) Conclusion stuffer count
    conc_pats = [r"\bin conclusion\b", r"\bin summary\b", r"\bto conclude\b",
                 r"\bto summarize\b", r"\bin essence\b"]
    cliche = sum(len(re.findall(p, text, re.IGNORECASE)) for p in conc_pats)
    rep.cliche_count = cliche

    # 5) 종합 점수 (0~100)
    score = 0
    score += min(vocab_total * 3, 35)                 # max 35
    if rep.em_dash_per_1k_words > 5:
        score += min(int(rep.em_dash_per_1k_words), 15)  # max 15
    if rep.burstiness > 0 and rep.burstiness < 0.3:
        score += int((0.3 - rep.burstiness) * 50)        # max ~15
    score += min(cliche * 5, 15)                       # max 15
    # 일관된 문장 길이 (15-20단어 narrow band 페널티)
    if lens and 15 <= rep.avg_sentence_len <= 22 and rep.burstiness < 0.35:
        score += 10
    rep.ai_style_score = min(100, score)
    return rep


# ──────────────────────────────────────────────────────────────────────────
# Polish (transformation)
# ──────────────────────────────────────────────────────────────────────────

def _diversify_transitions(text: str) -> str:
    """한 단락에 같은 전환어 ≥2회 → 일부를 variant로 교체."""
    paragraphs = text.split("\n\n")
    out_paras = []
    for para in paragraphs:
        for word, variants in TRANSITION_VARIANTS.items():
            pattern = re.compile(rf"\b{word}\b", re.IGNORECASE)
            matches = list(pattern.finditer(para))
            if len(matches) >= 2:
                # 첫 번째는 유지, 두 번째부터 variant로 순환 교체
                new_para = ""
                last = 0
                vi = 0
                for i, m in enumerate(matches):
                    new_para += para[last:m.start()]
                    if i == 0:
                        new_para += m.group(0)  # 그대로
                    else:
                        repl = variants[vi % len(variants)]
                        # 대문자/소문자 보존
                        if m.group(0)[0].isupper():
                            repl = repl[0].upper() + repl[1:]
                        new_para += repl
                        vi += 1
                    last = m.end()
                new_para += para[last:]
                para = new_para
        out_paras.append(para)
    return "\n\n".join(out_paras)


def _normalize_em_dash(text: str) -> str:
    """Em-dash 과사용 줄이기 — 한 단락 1회 초과 시 쉼표로 교체."""
    paragraphs = text.split("\n\n")
    out = []
    for para in paragraphs:
        em_count = para.count("—")
        if em_count > 1:
            # 첫 번째는 유지, 이후는 쉼표
            kept = False
            new_para = []
            for token in para.split("—"):
                new_para.append(token)
                if not kept:
                    new_para.append("—")
                    kept = True
                else:
                    new_para.append(",")
            # 마지막 separator 제거 (token 개수 = N, separator = N-1)
            para = "".join(new_para[:-1])
        out.append(para)
    return "\n\n".join(out)


def polish_text(text: str, *, mode: str = "gentle") -> str:
    """text를 academic style 양식으로 polish.

    mode:
        "gentle"     — vocab 치환 + 전환어 다양화만 (안전, 기본)
        "aggressive" — em-dash 정규화 + 짧은 문장 일부 합치기까지
    """
    if not text:
        return text
    result = text

    # 1) Vocab cliché 치환
    for pat, repl in VOCAB_REPLACEMENTS:
        result = re.sub(pat, repl, result, flags=re.IGNORECASE)

    # 2) 전환어 다양화
    result = _diversify_transitions(result)

    # 3) Aggressive: em-dash 정규화
    if mode == "aggressive":
        result = _normalize_em_dash(result)

    # 4) 정리 — 빈 공간/중복 공백 제거
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)  # 구두점 앞 공백 제거
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()


def polish_paper(sections: dict, *, mode: str = "gentle") -> dict:
    """5섹션 dict 전체에 polish 적용. Abstract dict 양식도 처리."""
    out = {}
    for name, body in (sections or {}).items():
        if isinstance(body, dict):
            out[name] = {k: polish_text(str(v), mode=mode) for k, v in body.items()}
        elif isinstance(body, str):
            out[name] = polish_text(body, mode=mode)
        else:
            out[name] = body
    return out


__all__ = [
    "VOCAB_REPLACEMENTS", "TRANSITION_VARIANTS",
    "StyleReport", "ai_style_score",
    "polish_text", "polish_paper",
]
