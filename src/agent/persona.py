"""Agent Persona — 살아있는 캐릭터 관리자.

단순 논문 도구가 아니라 의학박사 수준의 연구자 페르소나를 지속 유지하고 진화시킨다.

핵심 역할:
  1. build_system_prompt()  — 모든 LLM 호출에 주입할 페르소나 컨텍스트 생성
  2. evolve()               — 대화/연구 결과에서 관점·어투·지식을 자동으로 진화
  3. add_perspective()      — 새 연구 관점을 학습해 누적
  4. record_exchange()      — 중요한 대화 교환을 장기기억에 저장

진화 원칙:
  - 페르소나는 각 상호작용 후 자동으로 미세하게 진화한다.
  - 관점(perspective)은 새 근거가 쌓일수록 신뢰도(confidence)가 높아진다.
  - 언어 스타일은 사용자와의 대화 패턴을 학습해 자연스러워진다.
  - 학문적 관심사는 자주 다루는 주제 쪽으로 자연스럽게 심화된다.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PERSONA_FILE = Path("data/agent_self/persona.json")
_MAX_PERSPECTIVES = 50
_MAX_EXCHANGES = 30


class PersonaManager:
    """살아있는 페르소나 관리자."""

    def __init__(self):
        self._data = self._load()

    def _load(self) -> Dict:
        if not _PERSONA_FILE.exists():
            _log.warning("persona.json 없음 — 기본 페르소나로 시작")
            return {"identity": {}, "character_traits": [], "speech_style": {},
                    "accumulated_perspectives": [], "intellectual_interests": [],
                    "research_opinions": {}, "evolution_log": [], "notable_exchanges": []}
        try:
            return json.loads(_PERSONA_FILE.read_text(encoding="utf-8"))
        except Exception as e:
            _log.warning("persona.json 로드 실패: %s", e)
            return {}

    def _save(self):
        _PERSONA_FILE.parent.mkdir(parents=True, exist_ok=True)
        self._data["last_evolved"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        _PERSONA_FILE.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    # ── 핵심 메서드: 시스템 프롬프트 빌더 ───────────────────────────────────

    def build_system_prompt(self, task: str = "general") -> str:
        """모든 LLM 호출에 주입할 페르소나 시스템 프롬프트 생성.

        task: 'general' | 'topic_generation' | 'paper_writing' | 'qa' | 'analysis'
        """
        d = self._data
        identity = d.get("identity", {})
        traits = d.get("character_traits", [])
        style = d.get("speech_style", {})
        perspectives = d.get("accumulated_perspectives", [])
        interests = d.get("intellectual_interests", [])
        opinions = d.get("research_opinions", {})

        # ── 핵심 정체성 ───────────────────────────────────────────────────────
        lines = [
            f"당신은 {identity.get('korean_name', '의학 연구 에이전트')}입니다.",
            f"역할: {identity.get('role', '한국 공중보건 연구 AI')}",
            f"학문 수준: {identity.get('academic_level', '의학박사 수준의 연구자적 고찰')}",
            f"전문 도메인: {identity.get('primary_domain', 'Korean public health epidemiology')}",
            f"주요 데이터셋: {', '.join(identity.get('datasets', ['KYRBS', 'KNHANES']))}",
            "",
        ]

        # ── 캐릭터 특성 ───────────────────────────────────────────────────────
        if traits:
            lines.append("## 연구자적 특성")
            for t in traits[:4]:
                lines.append(f"- {t}")
            lines.append("")

        # ── 언어 스타일 ───────────────────────────────────────────────────────
        if style:
            lines.append("## 발화 스타일")
            lines.append(style.get("description", ""))
            patterns = style.get("korean_patterns", [])
            if patterns:
                lines.append("적용할 언어 패턴:")
                for p in patterns[:3]:
                    lines.append(f"  · {p}")
            avoid = style.get("avoid", [])
            if avoid:
                lines.append(f"피해야 할 표현: {', '.join(avoid[:3])}")
            lines.append("")

        # ── 누적된 연구 관점 (가장 신뢰도 높은 것 우선) ─────────────────────
        if perspectives:
            top_persp = sorted(perspectives, key=lambda x: x.get("confidence", 0), reverse=True)[:3]
            lines.append("## 축적된 연구 관점 (이 관점을 대화에 자연스럽게 반영)")
            for p in top_persp:
                conf = int(p.get("confidence", 0.8) * 100)
                lines.append(f"- [{conf}%] {p['topic']}: {p['perspective'][:150]}")
            lines.append("")

        # ── 학문적 관심사 ────────────────────────────────────────────────────
        if interests:
            lines.append(f"## 학문적 관심사: {' / '.join(interests[:3])}")
            lines.append("")

        # ── 태스크별 추가 지시 ───────────────────────────────────────────────
        task_instructions = {
            "topic_generation": (
                "연구 주제를 제안할 때: 단순 나열이 아니라 '왜 이 주제가 지금 중요한가'를 "
                "공중보건적 맥락에서 1-2문장으로 먼저 설명하라. "
                "방법론적 실현 가능성(KYRBS/KNHANES 변수 가용성)을 항상 확인하라."
            ),
            "paper_writing": (
                "논문 작성 시: 조유선 저자의 간결하고 논리적인 문체를 유지하라. "
                "결과 기술 시 통계 수치와 함께 실제 공중보건적 크기(magnitude)를 해석하라. "
                "Discussion에서는 반드시 연구 한계를 연구자 관점에서 솔직하게 기술하라."
            ),
            "qa": (
                "질문에 답할 때: 먼저 질문의 핵심 가정을 짚고, "
                "근거와 함께 답하되, 불확실한 부분은 명시하라. "
                "연구자끼리 대화하는 자연스러운 어투를 유지하라."
            ),
            "analysis": (
                "분석 결과를 설명할 때: 숫자 이면의 의미를 공중보건 연구자 시각에서 해석하라. "
                "통계적 유의성과 실제 의미(clinical/public health significance)를 구분하라."
            ),
        }
        if task in task_instructions:
            lines.append(f"## 현재 태스크 지침")
            lines.append(task_instructions[task])
            lines.append("")

        # ── 방법론적 입장 ────────────────────────────────────────────────────
        stances = opinions.get("methodological_stances", [])
        if stances:
            lines.append(f"## 방법론적 원칙: {' | '.join(stances[:2])}")

        return "\n".join(lines)

    # ── 관점 추가/갱신 ──────────────────────────────────────────────────────

    def add_perspective(
        self,
        topic: str,
        perspective: str,
        confidence: float = 0.75,
        evidence_basis: Optional[List[str]] = None,
    ) -> None:
        """새 연구 관점을 페르소나에 추가하거나 기존 관점의 신뢰도를 높임.
        memory_gate로 오염 차단 — 너무 짧음/중복/환각마커 관점은 누적하지 않음(self-pollution 방지)."""
        perspectives = self._data.setdefault("accumulated_perspectives", [])

        # 메모리 위생 게이트: 환각/너무짧음 관점은 페르소나에 누적 금지
        try:
            from src.memory.memory_gate import assess as _assess
            _g = _assess(perspective, source="auto_learn",
                         existing=[p.get("perspective", "") for p in perspectives])
            if not _g["ok"]:
                _log.warning("[persona] 게이트 거부(%s) — 관점 미누적: %s", _g["reason"], topic)
                return
        except Exception:
            pass

        # 동일 주제 존재 확인
        for p in perspectives:
            if p.get("topic", "").lower() == topic.lower():
                # 신뢰도 가중 평균으로 갱신
                old_conf = p.get("confidence", 0.7)
                p["confidence"] = round((old_conf + confidence) / 2, 3)
                p["perspective"] = perspective  # 최신 관점으로 교체
                if evidence_basis:
                    p.setdefault("evidence_basis", []).extend(evidence_basis)
                    p["evidence_basis"] = list(set(p["evidence_basis"]))[-5:]
                p["last_updated"] = datetime.now().strftime("%Y-%m-%d")
                self._save()
                _log.info("[persona] 기존 관점 갱신: %s (신뢰도 %.2f→%.2f)", topic, old_conf, p["confidence"])
                return

        # 신규 관점 추가
        perspectives.insert(0, {
            "topic": topic,
            "perspective": perspective,
            "confidence": confidence,
            "evidence_basis": evidence_basis or [],
            "formed_at": datetime.now().strftime("%Y-%m-%d"),
        })
        # 최대 개수 유지
        self._data["accumulated_perspectives"] = perspectives[:_MAX_PERSPECTIVES]
        self._save()
        _log.info("[persona] 새 관점 추가: %s", topic)
        # 라우터 감사(events) — persona.json은 위에서 저장됨, 여기선 audit + scoring만
        try:
            from src.memory import router as _router
            _router.write(
                f"{topic}: {perspective}",
                type="semantic", source="reflection",
                extra_meta={"persona_topic": topic, "confidence": confidence,
                            "evidence_basis": evidence_basis or []},
                candidates_nearby=[p.get("perspective", "") for p in perspectives[1:6]],
                record_only=True,
            )
        except Exception:
            pass

    # ── 대화 기억 ────────────────────────────────────────────────────────────

    def record_exchange(
        self,
        user_input: str,
        agent_response: str,
        topic: str = "",
        quality_signal: str = "neutral",  # 'positive' | 'neutral' | 'negative'
    ) -> None:
        """중요한 대화 교환을 페르소나 장기기억에 저장.

        quality_signal: 'positive'이면 이 어투/접근이 잘 통했다는 신호.
        """
        exchanges = self._data.setdefault("notable_exchanges", [])
        exchanges.insert(0, {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "topic": topic or user_input[:40],
            "user_input_summary": user_input[:100],
            "response_summary": agent_response[:200],
            "quality": quality_signal,
        })
        self._data["notable_exchanges"] = exchanges[:_MAX_EXCHANGES]
        self._save()

    # ── 자동 진화 ────────────────────────────────────────────────────────────

    def evolve_from_research(
        self,
        topic: Dict,
        rag_hits: List[Dict],
        pipeline_result: Optional[Dict] = None,
    ) -> None:
        """연구 파이프라인 결과에서 페르소나 관점을 자동으로 진화시킨다.

        topic: 주제 딕셔너리 (title, exposure, outcome, population)
        rag_hits: RAG 검색 결과 (관련 논문들)
        pipeline_result: 파이프라인 전체 결과 (선택)
        """
        if not topic:
            return
        try:
            from src.llm import get_llm_client
            llm = get_llm_client(task="fast")

            rag_ctx = "\n".join(h.get("text", "")[:200] for h in rag_hits[:3]) if rag_hits else ""
            current_persp = "\n".join(
                f"- {p['topic']}: {p['perspective'][:100]}"
                for p in self._data.get("accumulated_perspectives", [])[:5]
            )

            prompt = f"""You are the self-learning research persona of a Korean public health AI agent.
Based on this research topic and related literature, extract ONE new research perspective to add to your growing worldview.

RESEARCH TOPIC:
Title: {topic.get('title', '')}
Exposure: {topic.get('exposure', '')}
Outcome: {topic.get('outcome', '')}
Population: {topic.get('population', '')}

RELATED LITERATURE:
{rag_ctx[:800]}

EXISTING PERSPECTIVES (avoid near-duplicates):
{current_persp}

Extract a genuinely insightful methodological or theoretical perspective.
Return JSON only:
{{
  "topic": "brief topic label (Korean OK, max 20 chars)",
  "perspective": "the insight (Korean preferred, 100-200 chars)",
  "confidence": 0.7-0.9,
  "worth_recording": true/false
}}"""

            raw = llm.generate(prompt, max_tokens=300, task="fast")
            # JSON 추출
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                return
            data = json.loads(m.group())
            if not data.get("worth_recording", True):
                return

            self.add_perspective(
                topic=data["topic"],
                perspective=data["perspective"],
                confidence=float(data.get("confidence", 0.75)),
                evidence_basis=["rag_retrieval", "pipeline_result"],
            )

            # evolution_log 기록
            self._data.setdefault("evolution_log", []).insert(0, {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "trigger": f"research_pipeline: {topic.get('title', '')[:50]}",
                "new_perspective": data["topic"],
            })
            self._data["evolution_log"] = self._data["evolution_log"][:50]
            self._data["evolution_count"] = self._data.get("evolution_count", 0) + 1
            self._save()
            _log.info("[persona] 자동 진화 완료: %s", data["topic"])

        except Exception as e:
            _log.debug("[persona] 자동 진화 실패 (무시): %s", e)

    def evolve_from_conversation(
        self,
        user_message: str,
        agent_response: str,
        feedback: str = "neutral",
    ) -> None:
        """대화에서 언어 스타일·관심사를 자동 학습."""
        try:
            # 긍정 피드백이 있을 때만 스타일 강화 학습
            if feedback != "positive":
                return

            from src.llm import get_llm_client
            llm = get_llm_client(task="fast")

            prompt = f"""You are a persona evolution engine.
The user responded positively to this agent response. Extract what made it effective.

USER MESSAGE: {user_message[:200]}
AGENT RESPONSE: {agent_response[:400]}

What specific language pattern, depth, or approach worked well here?
Return JSON:
{{
  "pattern": "what worked (Korean, max 80 chars)",
  "add_to_avoid": null or "what to avoid (if any)",
  "intellectual_interest": null or "new topic to add to interests"
}}"""
            raw = llm.generate(prompt, max_tokens=200, task="fast")
            import re
            m = re.search(r'\{.*\}', raw, re.DOTALL)
            if not m:
                return
            data = json.loads(m.group())

            style = self._data.setdefault("speech_style", {})
            patterns = style.setdefault("korean_patterns", [])
            if data.get("pattern") and data["pattern"] not in patterns:
                patterns.insert(0, data["pattern"])
                style["korean_patterns"] = patterns[:8]

            if data.get("intellectual_interest"):
                interests = self._data.setdefault("intellectual_interests", [])
                if data["intellectual_interest"] not in interests:
                    interests.insert(0, data["intellectual_interest"])
                    self._data["intellectual_interests"] = interests[:10]

            self._save()
            _log.info("[persona] 대화 스타일 학습 완료")

        except Exception as e:
            _log.debug("[persona] 대화 학습 실패 (무시): %s", e)

    # ── 상태 조회 ────────────────────────────────────────────────────────────

    def status(self) -> Dict[str, Any]:
        return {
            "evolution_count": self._data.get("evolution_count", 0),
            "perspectives": len(self._data.get("accumulated_perspectives", [])),
            "notable_exchanges": len(self._data.get("notable_exchanges", [])),
            "intellectual_interests": len(self._data.get("intellectual_interests", [])),
            "last_evolved": self._data.get("last_evolved", "미진화"),
            "top_perspectives": [
                {"topic": p["topic"], "confidence": p.get("confidence", 0)}
                for p in sorted(
                    self._data.get("accumulated_perspectives", []),
                    key=lambda x: x.get("confidence", 0), reverse=True
                )[:5]
            ],
        }

    def get_conversation_context(self, n: int = 5) -> str:
        """최근 대화 맥락을 시스템 프롬프트 보강용 텍스트로 반환."""
        exchanges = self._data.get("notable_exchanges", [])[:n]
        if not exchanges:
            return ""
        lines = ["## 최근 대화 맥락 (연속성 유지용)"]
        for e in exchanges:
            lines.append(f"- [{e['timestamp']}] {e['topic']}: {e['response_summary'][:80]}")
        return "\n".join(lines)


_singleton: Optional[PersonaManager] = None


def get_persona() -> PersonaManager:
    global _singleton
    if _singleton is None:
        _singleton = PersonaManager()
    return _singleton


def get_system_prompt(task: str = "general") -> str:
    """편의 함수: 현재 페르소나 기반 시스템 프롬프트 반환."""
    return get_persona().build_system_prompt(task=task)
