"""Intent Sensor — 사용자 prompt의 explicit 요구 + implicit 의도·뉘앙스·페르소나 센싱.

배경 (2026-05-30 사용자 요구):
    "GEO의 핵심은 프롬프트(맥락) 이해를 통해 고객의 니즈를 알아채는 센싱이 1순위.
     LLM이 의도와 맥락을 센싱해서 그 사람이 정말 필요로 하는 것이 무엇이고,
     어떤 뉘앙스로 어떻게 표현하고 싶어하는지를 예측해서 논문에 심어줘야 한다."

설계:
    표층 prompt에 드러나지 않은 implicit 신호를 5차원으로 분리해서 system_prompt에 주입.
    LLM은 이를 보고 단순 요구 응답이 아니라 사용자 페르소나·맥락·강조 의도까지 반영한 산출물 생성.

    5차원:
    1. explicit_request — 표면 요구 ("Discussion 다시 써줘")
    2. implicit_emphasis — 강조하고 싶은 포인트 (직전 대화·키워드 빈도에서 유추)
    3. implicit_avoidance — 회피하고 싶은 양식 (이전 거부 표현·"좀" "너무" 양식)
    4. reader_assumption — 가정 독자 (저널·reviewer·임상의·정책결정자 중)
    5. voice_tone — 톤 (formal academic / critical / explanatory / cautious)

    추가:
    - prior_conversation_signal — 직전 대화에서 잡힌 신호 (frustration/satisfaction/specific terminology)
    - user_persona_inferred — 사용자가 자주 쓰는 도메인 어휘·관심 주제

호출:
    sig = sense(prompt, prior_messages=messages, project=project, owner_email=email)
    sig.to_system_block()  # 양식 system_prompt에 주입

이 모듈은 빠른 휴리스틱 (regex + 빈도) 기반이라 외부 LLM 호출 없음 — agentic loop 매 step에 안전하게.
복잡한 의도 추론은 build_system_with_preview에 이미 있는 trigger_analyzer + cognitive_activation이 수행.
"""
from __future__ import annotations

import json
import os
import re
import statistics
import threading
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_INTENT_DIR = Path(os.environ.get("AGENT_SELF_DIR", "data/agent_self"))
_INTENT_FILE = _INTENT_DIR / "current_intent.json"
_PATTERNS_FILE = _INTENT_DIR / "intent_patterns.json"
_LOCK = threading.Lock()


# ── Signal patterns (data/agent_self/intent_patterns.json으로 외부화 가능) ──
#
# 다른 도메인(예: 정신과·소아과·간호·정책)에서도 쓰려면 intent_patterns.json에
# {"emphasis": [["regex", "label"], ...], "avoidance": [...], "reader": [...], "tone": [...]}
# 양식으로 두면 부팅 시 자동 로드. 없으면 아래 기본(공중보건/의학 도메인) 사용.

# 강조 신호 — 사용자가 무엇을 부각하고 싶어하는지
_EMPHASIS_MARKERS_DEFAULT = [
    (r"꼭|반드시|특히|중요", "must_include"),
    (r"강조|부각|살려|돋보이게", "emphasize"),
    (r"\bvs\.?\b|대비|비교|차이|gap", "contrast"),
    (r"임상적|policy|정책|clinical|implication", "clinical_policy_focus"),
    (r"새로운|신규|novel|first|첫", "novelty_claim"),
    (r"여성|남성|sex.?specific|성별", "subgroup_sex"),
    (r"연령|age|adolescent|청소년|elderly|노인", "subgroup_age"),
    (r"interaction|상호작용|moderator|effect modif", "interaction_focus"),
]

# 회피 신호 — 사용자가 빼고 싶어하는 양식
_AVOIDANCE_MARKERS_DEFAULT = [
    (r"너무\s*(많아|길어|장황|복잡|formal|academic)", "too_verbose"),
    (r"AI.?스러|로봇|뻔한|cliche|기계적", "anti_ai_tone"),
    (r"단순|간결|짧게|줄여|brief", "want_concise"),
    (r"빼|제거|delete|remove", "remove_something"),
    (r"\b좀\b|약간|조금", "soften_intensity"),
    (r"환자.?중심|patient.?centric|독자.?친화", "reader_friendly"),
]

# 독자 가정 — 누가 읽을 것을 가정하는가
_READER_MARKERS_DEFAULT = [
    (r"NEJM|Lancet|JAMA|JKMS|high.?impact|top.?journal", "top_journal_reviewer"),
    (r"reviewer|reviewer.?comment|peer.?review|동료심사", "reviewer_focus"),
    (r"임상의|physician|practitioner|clinician", "clinician"),
    (r"정책|policy.?maker|public.?health|보건당국", "policy_maker"),
    (r"general.?public|일반\s*독자|lay.?audience", "lay_audience"),
    (r"thesis|학위논문|박사|defense", "thesis_committee"),
]

# 톤 신호
_TONE_MARKERS_DEFAULT = [
    (r"strong|강하게|단호|definitive|확실", "assertive"),
    (r"cautious|조심|hedging|약화|tentative", "cautious"),
    (r"비판|critical|limitation|반박|반대|counter", "critical"),
    (r"설명|explanatory|clarify|풀어서|쉽게", "explanatory"),
    (r"흥미|engaging|narrative|이야기", "engaging"),
]


def _load_external_patterns() -> dict:
    """data/agent_self/intent_patterns.json에서 도메인별 패턴 로드. 없으면 기본."""
    if not _PATTERNS_FILE.exists():
        return {}
    try:
        d = json.loads(_PATTERNS_FILE.read_text(encoding="utf-8"))
        return {k: [(p, l) for p, l in v] for k, v in d.items() if isinstance(v, list)}
    except Exception as e:
        _log.debug("intent_patterns.json 로드 실패(기본 사용): %s", e)
        return {}


_EXT = _load_external_patterns()
_EMPHASIS_MARKERS = _EXT.get("emphasis", _EMPHASIS_MARKERS_DEFAULT)
_AVOIDANCE_MARKERS = _EXT.get("avoidance", _AVOIDANCE_MARKERS_DEFAULT)
_READER_MARKERS = _EXT.get("reader", _READER_MARKERS_DEFAULT)
_TONE_MARKERS = _EXT.get("tone", _TONE_MARKERS_DEFAULT)


@dataclass
class IntentSignal:
    explicit_request: str = ""
    implicit_emphasis: List[str] = field(default_factory=list)
    implicit_avoidance: List[str] = field(default_factory=list)
    reader_assumption: List[str] = field(default_factory=list)
    voice_tone: List[str] = field(default_factory=list)
    prior_conversation_signal: dict = field(default_factory=dict)
    user_persona_inferred: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_system_block(self) -> str:
        """system_prompt에 주입할 한국어 블록 — LLM이 의도 센싱 결과를 보고 작동."""
        if not (self.implicit_emphasis or self.implicit_avoidance
                or self.reader_assumption or self.voice_tone
                or self.prior_conversation_signal or self.user_persona_inferred):
            return ""

        lines = ["# ★ USER INTENT SENSING (사용자가 명시하지 않았지만 감지된 의도)",
                 ""]
        if self.explicit_request:
            lines.append(f"## Explicit request\n{self.explicit_request[:300]}\n")
        if self.implicit_emphasis:
            lines.append("## 강조하고 싶어하는 포인트 (살려라)")
            for e in self.implicit_emphasis:
                lines.append(f"- {e}")
            lines.append("")
        if self.implicit_avoidance:
            lines.append("## 회피하고 싶어하는 양식 (피해라)")
            for a in self.implicit_avoidance:
                lines.append(f"- {a}")
            lines.append("")
        if self.reader_assumption:
            lines.append("## 가정 독자 (이 사람에게 가닿게 써라)")
            for r in self.reader_assumption:
                lines.append(f"- {r}")
            lines.append("")
        if self.voice_tone:
            lines.append("## 원하는 톤")
            for t in self.voice_tone:
                lines.append(f"- {t}")
            lines.append("")
        if self.prior_conversation_signal:
            lines.append("## 직전 대화에서 감지된 신호")
            for k, v in self.prior_conversation_signal.items():
                lines.append(f"- {k}: {v}")
            lines.append("")
        if self.user_persona_inferred:
            lines.append("## 사용자 페르소나 (반복 등장 어휘·관심 주제)")
            for k, v in self.user_persona_inferred.items():
                if isinstance(v, list) and v:
                    lines.append(f"- {k}: {', '.join(map(str, v[:8]))}")
                elif v:
                    lines.append(f"- {k}: {v}")
            lines.append("")
        lines.append("→ 위 의도/페르소나를 반영해 단어가 아니라 **의미·강조점·뉘앙스** 단위로 재창조하라.")
        lines.append("→ 표면 요구만 만족하지 말고, 사용자가 직접 말하지 않은 implicit 신호까지 살려라.")
        return "\n".join(lines)


def _match_markers(text: str, markers: list[tuple[str, str]]) -> List[str]:
    text_low = text or ""
    hits = []
    for pat, label in markers:
        if re.search(pat, text_low, re.IGNORECASE):
            hits.append(label)
    return hits


def _infer_user_persona(prior_messages: list, current_prompt: str) -> dict:
    """직전 user 메시지들 + 현재 prompt에서 반복 등장하는 도메인 어휘·관심 주제 추출."""
    user_texts = [current_prompt]
    for m in (prior_messages or [])[-20:]:
        if isinstance(m, dict) and m.get("role") == "user":
            c = str(m.get("content", ""))
            if c:
                user_texts.append(c)
    blob = " ".join(user_texts)

    # 의학 도메인 키워드 빈도
    domain_kw = re.findall(
        r"\b(KYRBS|KNHANES|depression|stress|sleep|smoking|alcohol|BMI|obesity|"
        r"adolescent|청소년|우울|스트레스|수면|비만|zcb|음료|sugar|sweetener|"
        r"physical.?activity|운동|interaction|상호작용|aOR|95.?CI|P.?value|"
        r"subgroup|stratif|sensitivity|mediation|매개|moderation|조절)\b",
        blob, re.IGNORECASE)
    kw_counter = Counter(k.lower() for k in domain_kw)

    # 영문/한글 비율
    en_chars = len(re.findall(r"[a-zA-Z]", blob))
    ko_chars = len(re.findall(r"[가-힣]", blob))
    lang_ratio = (
        "kor_dominant" if ko_chars > en_chars * 1.5 else
        "eng_dominant" if en_chars > ko_chars * 1.5 else
        "mixed"
    )

    # 스타일 신호 — Yoosun 양식 hedging/표현 사용 흔적
    yoosun_indicators = bool(re.search(r"yoosun|조유선|hedg|consistent with|associated with",
                                         blob, re.IGNORECASE))

    return {
        "top_domain_keywords": [k for k, _ in kw_counter.most_common(8)],
        "language_pref": lang_ratio,
        "yoosun_style_inferred": yoosun_indicators,
    }


def _scan_prior_conversation(prior_messages: list) -> dict:
    """직전 대화에서 frustration/satisfaction/specific 요청 신호 추출."""
    out = {}
    if not prior_messages:
        return out
    recent = prior_messages[-10:]
    user_texts = " ".join(str(m.get("content", "")) for m in recent
                           if isinstance(m, dict) and m.get("role") == "user")
    if re.search(r"왜이래|안돼|에러|틀려|이상해|wrong|wtf", user_texts):
        out["frustration_detected"] = True
    if re.search(r"좋|good|perfect|완벽|딱|괜찮", user_texts):
        out["satisfaction_detected"] = True
    if re.search(r"다시|재작|rewrite|redo", user_texts):
        out["redo_request"] = True
    if re.search(r"AI.?스러|로봇|뻔한", user_texts):
        out["anti_ai_complaint"] = True
    return out


# ── 영구 "현재 의도" 저장 (2026-05-30 업그레이드) ──────────────────────────
# process-level 캐시 → 디스크 + Supabase 영구화. container 재시작에도 살아남음.
# 또한 owner_email별로 분리 저장해서 multi-user 환경에서도 의도 격리.
_CURRENT_INTENT: Optional["IntentSignal"] = None


def _persist_to_disk(sig: "IntentSignal", owner_email: str = "") -> None:
    """current intent를 디스크에 저장 — container restart에도 살아남음."""
    try:
        with _LOCK:
            _INTENT_DIR.mkdir(parents=True, exist_ok=True)
            data = {"owner_email": owner_email,
                    "intent": sig.to_dict(),
                    "ts": __import__("time").time()}
            _INTENT_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
    except Exception as e:
        _log.debug("intent disk persist 실패: %s", e)


def _persist_to_supabase(sig: "IntentSignal", owner_email: str = "") -> None:
    """Supabase ma_intent_history에 누적 저장 — owner별 의도 추적."""
    try:
        from src.cloud.db import cloud_available, get_engine
        if not cloud_available():
            return
        import sqlalchemy as sa
        with get_engine().begin() as conn:
            conn.execute(sa.text(
                "CREATE TABLE IF NOT EXISTS ma_intent_history ("
                "id bigserial PRIMARY KEY, owner_email text, "
                "emphasis jsonb, avoidance jsonb, reader jsonb, tone jsonb, "
                "persona jsonb, ts timestamp DEFAULT now())"))
            conn.execute(sa.text(
                "INSERT INTO ma_intent_history "
                "(owner_email, emphasis, avoidance, reader, tone, persona) "
                "VALUES (:oe, :em, :av, :rd, :tn, :ps)"),
                {"oe": owner_email,
                 "em": json.dumps(sig.implicit_emphasis, ensure_ascii=False),
                 "av": json.dumps(sig.implicit_avoidance, ensure_ascii=False),
                 "rd": json.dumps(sig.reader_assumption, ensure_ascii=False),
                 "tn": json.dumps(sig.voice_tone, ensure_ascii=False),
                 "ps": json.dumps(sig.user_persona_inferred, ensure_ascii=False)})
    except Exception as e:
        _log.debug("intent Supabase 누적 실패: %s", e)


def _load_from_disk() -> Optional["IntentSignal"]:
    """디스크의 current_intent.json 로드 — container restart 직후 사용."""
    if not _INTENT_FILE.exists():
        return None
    try:
        data = json.loads(_INTENT_FILE.read_text(encoding="utf-8"))
        i = data.get("intent") or {}
        return IntentSignal(
            explicit_request=i.get("explicit_request", ""),
            implicit_emphasis=i.get("implicit_emphasis", []),
            implicit_avoidance=i.get("implicit_avoidance", []),
            reader_assumption=i.get("reader_assumption", []),
            voice_tone=i.get("voice_tone", []),
            prior_conversation_signal=i.get("prior_conversation_signal", {}),
            user_persona_inferred=i.get("user_persona_inferred", {}),
        )
    except Exception:
        return None


def set_current(sig: "IntentSignal", *, owner_email: str = "") -> None:
    global _CURRENT_INTENT
    _CURRENT_INTENT = sig
    _persist_to_disk(sig, owner_email=owner_email)
    _persist_to_supabase(sig, owner_email=owner_email)


def get_current() -> Optional["IntentSignal"]:
    """메모리 우선 + 디스크 폴백 — container restart 직후에도 직전 의도 복원."""
    global _CURRENT_INTENT
    if _CURRENT_INTENT is not None:
        return _CURRENT_INTENT
    sig = _load_from_disk()
    if sig is not None:
        _CURRENT_INTENT = sig
    return _CURRENT_INTENT


def clear_current() -> None:
    global _CURRENT_INTENT
    _CURRENT_INTENT = None
    try:
        if _INTENT_FILE.exists():
            _INTENT_FILE.unlink()
    except Exception:
        pass


def sense_and_imprint(prompt: str, *,
                       prior_messages: Optional[list] = None,
                       project: Optional[dict] = None,
                       owner_email: Optional[str] = None,
                       deep: bool = False) -> "IntentSignal":
    """sense 호출 + 영구 저장 한 줄로. 사용자 prompt 진입점에서 호출.

    deep=True면 LLM 의도 추론(sense_deep) 추가 — 미묘한 의도(비꼬는 톤, 함축적 회피 등) 잡힘.
    cheap model (task='fast') 사용 — 약 1-2초.
    """
    sig = sense(prompt, prior_messages=prior_messages,
                 project=project, owner_email=owner_email)
    if deep:
        try:
            deep_sig = sense_deep(prompt, prior_messages=prior_messages)
            sig = merge_signals(sig, deep_sig)
        except Exception as e:
            _log.debug("sense_deep 실패, 휴리스틱만 사용: %s", e)
    set_current(sig, owner_email=owner_email or "")
    return sig


def sense_deep(prompt: str, *,
                prior_messages: Optional[list] = None) -> "IntentSignal":
    """LLM 기반 의도 추론 — 휴리스틱이 못 잡는 미묘한 신호 (비꼬는 톤·함축적 의도·이중 메시지).

    cheap model (fast task) 사용 — 1-2초 비용으로 깊이 있는 추론.
    실패하면 빈 IntentSignal 반환 (graceful).
    """
    sig = IntentSignal(explicit_request=(prompt or "")[:500])
    try:
        from src.llm import get_llm_client
        client = get_llm_client(task="fast")
        recent = ""
        if prior_messages:
            for m in (prior_messages or [])[-4:]:
                if isinstance(m, dict):
                    recent += f"\n{m.get('role', '?')}: {str(m.get('content', ''))[:200]}"
        sys_p = (
            "You analyze a user request for an academic medical paper. "
            "Detect IMPLICIT intent the user did not say out loud: tone, hidden emphasis, "
            "avoidance, sarcasm, reader assumption. "
            "Return ONLY a JSON object with keys: emphasis (list), avoidance (list), "
            "reader (list), tone (list). No prose."
        )
        usr = f"Request:\n{prompt}\n\nRecent conversation:{recent}\n\nReturn JSON only."
        out = client.generate(usr, system_prompt=sys_p, max_tokens=300, task="fast")
        # JSON 파싱
        m = re.search(r"\{[\s\S]*\}", out or "")
        if m:
            d = json.loads(m.group(0))
            sig.implicit_emphasis = list(d.get("emphasis") or [])[:10]
            sig.implicit_avoidance = list(d.get("avoidance") or [])[:10]
            sig.reader_assumption = list(d.get("reader") or [])[:10]
            sig.voice_tone = list(d.get("tone") or [])[:10]
    except Exception as e:
        _log.debug("sense_deep LLM 호출 실패: %s", e)
    return sig


def merge_signals(a: "IntentSignal", b: "IntentSignal") -> "IntentSignal":
    """두 IntentSignal 합치기 — 휴리스틱(a) + LLM 추론(b)."""
    def _u(x, y):  # 중복 제거 + 순서 보존
        seen = set()
        out = []
        for it in list(x) + list(y):
            if it not in seen:
                seen.add(it); out.append(it)
        return out
    return IntentSignal(
        explicit_request=a.explicit_request or b.explicit_request,
        implicit_emphasis=_u(a.implicit_emphasis, b.implicit_emphasis),
        implicit_avoidance=_u(a.implicit_avoidance, b.implicit_avoidance),
        reader_assumption=_u(a.reader_assumption, b.reader_assumption),
        voice_tone=_u(a.voice_tone, b.voice_tone),
        prior_conversation_signal={**a.prior_conversation_signal,
                                     **b.prior_conversation_signal},
        user_persona_inferred={**a.user_persona_inferred,
                                **b.user_persona_inferred},
    )


def sense(prompt: str, *,
          prior_messages: Optional[list] = None,
          project: Optional[dict] = None,
          owner_email: Optional[str] = None) -> IntentSignal:
    """사용자 prompt + 컨텍스트에서 의도·뉘앙스·페르소나를 5+2차원으로 추출.

    빠른 휴리스틱만 — agentic loop 매 step에 안전하게 호출 가능 (외부 LLM 호출 없음).
    더 깊은 의도 추론은 build_system_with_preview의 trigger_analyzer + cognitive_activation에서.
    """
    sig = IntentSignal()
    sig.explicit_request = (prompt or "")[:500]

    text_blob = prompt or ""
    sig.implicit_emphasis = _match_markers(text_blob, _EMPHASIS_MARKERS)
    sig.implicit_avoidance = _match_markers(text_blob, _AVOIDANCE_MARKERS)
    sig.reader_assumption = _match_markers(text_blob, _READER_MARKERS)
    sig.voice_tone = _match_markers(text_blob, _TONE_MARKERS)

    sig.prior_conversation_signal = _scan_prior_conversation(prior_messages or [])
    sig.user_persona_inferred = _infer_user_persona(prior_messages or [], prompt or "")

    return sig


__all__ = ["IntentSignal", "sense", "sense_deep", "sense_and_imprint",
           "merge_signals", "set_current", "get_current", "clear_current"]
