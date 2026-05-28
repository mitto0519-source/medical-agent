"""Cognitive Activation Engine — vision 다이어그램의 핵심 누락 컴포넌트.

5 layer 구조:
  1. Fragment Trigger Layer — 키워드/의미/상황/감정/형태 fragment 감지
  2. Activation Propagation — fragment → memory/knowledge graph 활성화 확산
  3. Multi-layer Retrieval Router — 상황/주제/시간/목표/우선순위 기반 routing
  4. Context Flow Preserver — 대화 흐름 추적, 주제 전환 감지, 미해결 thread 추적
  5. Retrieval Policy Mixer — 현재 상태·목표·과거 패턴 기반 가중치 동적 조정

본 모듈은 `build_system_with_preview`보다 한 단계 위 — 사용자 메시지가 들어오면 즉시
어떤 memory/knowledge/component를 활성화할지 결정한 뒤 LLM context로 합성.

호출:
    from src.agent.cognitive_activation import activate
    ctx = activate(user_msg="ZCB depression Methods 채워줘", project=proj)
    # ctx = {"fragments":[...], "activated_memories":[...], "retrieval_plan":{...},
    #         "context_flow":{...}, "policy":{...}}
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── Layer 1: Fragment Trigger ───────────────────────────────────────────────

@dataclass
class Fragment:
    kind: str          # keyword | meaning | situation | emotion | form
    text: str
    weight: float = 0.5
    source: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


_KEYWORD_TRIGGERS = re.compile(
    r"\b(KYRBS|KNHANES|ZCB|depression|introduction|methods|results|discussion|"
    r"abstract|figure|table|reference|citation|STROBE|aOR|95%\s*CI|"
    r"yoosun|cho|gut.brain|adolescent|consort|prisma)\b",
    re.IGNORECASE)

_SITUATION_TRIGGERS = re.compile(
    r"\b(써|작성|수정|보강|재작성|분석|검증|확인|보여|만들|추가|채워|"
    r"compose|write|revise|analyze|check|verify|show|build|add|fill)\b",
    re.IGNORECASE)

_EMOTION_TRIGGERS = re.compile(
    r"(.*\?|좀\s|진행|시급|빨리|급해|please|urgent|asap|"
    r"틀렸|틀린|왜|불만|싫|좋아|마음에)", re.IGNORECASE)

_FORM_TRIGGERS = re.compile(
    r"\b(docx|pdf|json|csv|sav|markdown|figure|table|chart|graph|"
    r"png|svg|excel|word)\b", re.IGNORECASE)


def extract_fragments(text: str) -> List[Fragment]:
    """Layer 1 — 사용자 메시지에서 fragment 추출."""
    if not text:
        return []
    frags: List[Fragment] = []
    for m in _KEYWORD_TRIGGERS.finditer(text):
        frags.append(Fragment(kind="keyword", text=m.group(0).lower(),
                                weight=0.8, source="regex"))
    for m in _SITUATION_TRIGGERS.finditer(text):
        frags.append(Fragment(kind="situation", text=m.group(0),
                                weight=0.6, source="regex"))
    for m in _EMOTION_TRIGGERS.finditer(text):
        frags.append(Fragment(kind="emotion", text=m.group(0)[:40],
                                weight=0.5, source="regex"))
    for m in _FORM_TRIGGERS.finditer(text):
        frags.append(Fragment(kind="form", text=m.group(0).lower(),
                                weight=0.7, source="regex"))
    # meaning fragment — 단어 3 단위 첫 토큰 (단순)
    toks = [t for t in re.findall(r"[A-Za-z가-힣]{3,}", text)][:8]
    if toks:
        frags.append(Fragment(kind="meaning", text=" ".join(toks)[:200],
                                weight=0.4, source="tok"))
    return frags


# ── Layer 2: Activation Propagation ─────────────────────────────────────────

def propagate_activation(fragments: List[Fragment],
                          *, owner: Optional[str] = None) -> Dict:
    """Layer 2 — fragment를 memory/graph로 확산해 activated entity 수집.

    Returns:
        {"memories": [...], "graph_concepts": [...], "components": [...]}
    """
    activated: Dict[str, List] = {"memories": [], "graph_concepts": [], "components": []}
    if not fragments:
        return activated

    # 키워드 fragment를 query로 묶어 검색
    kw_text = " ".join(f.text for f in fragments if f.kind in ("keyword", "meaning"))
    if not kw_text.strip():
        return activated

    # conversation_memory recall
    try:
        from src.memory import conversation_memory as cm
        recalled = cm.recall_relevant(kw_text, n=5, owner_email=owner) or ""
        if recalled:
            activated["memories"].append({"source": "conversation",
                                            "text": recalled[:1500]})
    except Exception:
        pass

    # graph concept neighbors (medical_graph)
    try:
        from src.knowledge.medical_graph import get_graph
        g = get_graph()
        if g and hasattr(g, "_G"):
            for f in fragments:
                if f.kind == "keyword":
                    node = f"concept:{f.text.lower()}"
                    if g._G.has_node(node):
                        nbrs = list(g._G.neighbors(node))[:5]
                        activated["graph_concepts"].append(
                            {"concept": f.text.lower(), "neighbors": nbrs})
    except Exception:
        pass

    # component samples (style + content)
    try:
        from src.library.components import get_library
        lib = get_library()
        for kind in ("hedging", "stat_report", "transition"):
            samples = lib.sample(kind, n=2)
            if samples:
                activated["components"].append(
                    {"kind": kind, "samples": [s["text"][:200] for s in samples]})
    except Exception:
        pass

    return activated


# ── Layer 3: Multi-layer Retrieval Router ───────────────────────────────────

def route_retrieval(fragments: List[Fragment],
                     *, current_goal: str = "",
                     time_context: str = "now") -> Dict:
    """Layer 3 — fragment 종합 → 어떤 retrieval strategy 우선할지 결정.

    Returns: {"primary": "rag|graph|component|stat", "secondary": [...], "rationale": ""}
    """
    has_stat = any(f.kind == "keyword" and re.search(r"aOR|OR|CI|p.value|kyrbs",
                                                       f.text, re.IGNORECASE) for f in fragments)
    has_evidence = any(f.kind == "keyword" and f.text in
                        ("introduction", "discussion", "depression") for f in fragments)
    has_form = any(f.kind == "form" for f in fragments)
    has_style = any(f.kind == "keyword" and f.text in ("yoosun", "cho") for f in fragments)

    if has_stat:
        return {"primary": "stat", "secondary": ["rag", "component"],
                 "rationale": "stat/CI/aOR keyword → KYRBS run_stat 우선"}
    if has_evidence:
        return {"primary": "rag", "secondary": ["graph", "component"],
                 "rationale": "Introduction/Discussion → evidence retrieval 우선"}
    if has_style:
        return {"primary": "component",
                 "secondary": ["rag"],
                 "rationale": "yoosun/style → ComponentLibrary 우선"}
    if has_form:
        return {"primary": "export", "secondary": ["component"],
                 "rationale": "form keyword → export builder"}
    return {"primary": "rag", "secondary": ["graph"],
             "rationale": "기본 evidence retrieval"}


# ── Layer 4: Context Flow Preserver ─────────────────────────────────────────

def track_context_flow(messages: List[Dict],
                        *, max_thread_age: int = 6) -> Dict:
    """Layer 4 — 대화 흐름 분석. 주제 전환, 미해결 thread, 연속성 강도."""
    if not messages:
        return {"thread_depth": 0, "topic_shift": False,
                 "unresolved_threads": [], "continuity_score": 1.0}

    # 최근 메시지의 키워드 vs 그 이전
    def _kws(m):
        c = m.get("content", "") if isinstance(m, dict) else ""
        return set(t.lower() for t in re.findall(r"[A-Za-z가-힣]{4,}", c))[:30] if False \
            else set(re.findall(r"[A-Za-z가-힣]{4,}", c.lower()))

    recent = messages[-3:]
    earlier = messages[-(max_thread_age + 3):-3] if len(messages) > 3 else []
    recent_kw = set().union(*(_kws(m) for m in recent)) if recent else set()
    earlier_kw = set().union(*(_kws(m) for m in earlier)) if earlier else set()
    overlap = len(recent_kw & earlier_kw) / max(1, len(recent_kw | earlier_kw))
    topic_shift = overlap < 0.2 and len(earlier_kw) > 5

    # 미해결 thread — assistant 응답 없는 user 마지막
    unresolved = []
    for i, m in enumerate(messages[-10:]):
        if isinstance(m, dict) and m.get("role") == "user":
            nxt = messages[-10 + i + 1] if -10 + i + 1 < len(messages) else None
            if not nxt or (isinstance(nxt, dict) and nxt.get("role") not in ("assistant",)):
                unresolved.append(str(m.get("content", ""))[:120])

    return {
        "thread_depth": len(messages),
        "topic_shift": topic_shift,
        "topic_overlap": round(overlap, 3),
        "unresolved_threads": unresolved[-3:],
        "continuity_score": round(overlap, 3),
    }


# ── Layer 5: Retrieval Policy Mixer ─────────────────────────────────────────

def mix_policy(fragments: List[Fragment], context_flow: Dict,
                *, base_weights: Optional[Dict[str, float]] = None) -> Dict:
    """Layer 5 — 동적 가중치 결정. 현재 상태 + 목표 + 과거 패턴 반영."""
    w = dict(base_weights or {"rag": 1.0, "graph": 0.7, "component": 0.8,
                                "stat": 0.6, "memory": 0.9})

    # emotion fragment 많으면 memory 가중 ↑ (사용자가 과거 맥락 기대)
    n_emotion = sum(1 for f in fragments if f.kind == "emotion")
    if n_emotion >= 2:
        w["memory"] = w.get("memory", 0.9) + 0.3

    # topic shift 발생 시 memory 가중 ↓ (새 주제니까)
    if context_flow.get("topic_shift"):
        w["memory"] = max(0.3, w.get("memory", 0.9) - 0.4)
        w["rag"] = w.get("rag", 1.0) + 0.2

    # form fragment 있으면 component/export 가중 ↑
    if any(f.kind == "form" for f in fragments):
        w["component"] = w.get("component", 0.8) + 0.3

    # 정규화 (max=1.0)
    if w:
        mx = max(w.values()) or 1.0
        w = {k: round(v / mx, 3) for k, v in w.items()}
    return w


# ── Public entry ────────────────────────────────────────────────────────────

def activate(user_msg: str, *, project: Optional[Dict] = None,
              owner: Optional[str] = None) -> Dict:
    """5 layer 종합 — 사용자 메시지 → 활성화 컨텍스트."""
    project = project or {}
    messages = project.get("messages", []) if isinstance(project, dict) else []

    fragments = extract_fragments(user_msg)
    activated = propagate_activation(fragments, owner=owner)
    routing = route_retrieval(fragments,
                                current_goal=project.get("title", ""),
                                time_context="now")
    flow = track_context_flow(messages)
    policy = mix_policy(fragments, flow)

    result = {
        "fragments": [f.to_dict() for f in fragments],
        "activated": activated,
        "retrieval_plan": routing,
        "context_flow": flow,
        "policy_weights": policy,
        "ts": time.time(),
    }

    try:
        from src.runtime import events as _events
        _events.append("cognitive_activation",
                        {"n_fragments": len(fragments),
                         "primary": routing.get("primary"),
                         "topic_shift": flow.get("topic_shift"),
                         "top_weight": max(policy.values()) if policy else 0},
                        actor="cognitive_activation")
    except Exception:
        pass
    return result


def to_system_prompt_block(activation: Dict) -> str:
    """activate() 결과를 LLM system prompt 블록으로 직렬화."""
    parts = ["", "# COGNITIVE ACTIVATION (auto)"]
    frags = activation.get("fragments", [])
    if frags:
        parts.append("Fragments detected: " +
                      ", ".join(f"{f['kind']}={f['text'][:30]}" for f in frags[:6]))
    routing = activation.get("retrieval_plan", {})
    if routing:
        parts.append(f"Retrieval strategy: primary={routing.get('primary')} "
                      f"secondary={routing.get('secondary')} ({routing.get('rationale')})")
    flow = activation.get("context_flow", {})
    if flow:
        parts.append(f"Context flow: depth={flow.get('thread_depth')} "
                      f"overlap={flow.get('topic_overlap')} "
                      f"shift={flow.get('topic_shift')}")
        if flow.get("unresolved_threads"):
            parts.append(f"  Unresolved: {flow['unresolved_threads']}")
    activated = activation.get("activated", {})
    if activated.get("graph_concepts"):
        parts.append(f"Graph concepts activated: "
                      + ", ".join(c["concept"] for c in activated["graph_concepts"][:5]))
    if activated.get("components"):
        parts.append("Style/content components available:")
        for c in activated["components"][:3]:
            parts.append(f"  - {c['kind']}: {c['samples'][0][:80] if c['samples'] else ''}…")
    return "\n".join(parts)
