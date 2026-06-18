"""Multi-agent role 분리 — planner/critic/statistician/citation_auditor 등.

외부 진단 (2026-05-28): "single brain + tools 구조 → multi-agent로 격상".

각 role은 specialized system prompt + 도구 제한. Planner DAG의 노드 executor가
역할별 agent로 dispatch (action → role mapping).

기존 `src/agent/agent_pool.py`는 threadpool 분담만 했음. 본 모듈은 **명시적 role
+ specialized prompt + per-role decision policy**.

호출:
    from src.agent.roles import dispatch_role
    out = dispatch_role("statistician", {"outcome":"depression","exposure":"zcb_freq"})
    out = dispatch_role("critic", {"text": draft, "section": "Discussion"})
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class RoleSpec:
    """role 정의."""
    name: str
    description: str
    system_prompt: str
    allowed_tools: List[str] = field(default_factory=list)
    fallback_llm_task: str = "standard"


# ── Role registry ─────────────────────────────────────────────────────────────

ROLES: Dict[str, RoleSpec] = {
    "planner": RoleSpec(
        name="planner",
        description="Goal을 받아 execution DAG로 분해. 직접 실행 X.",
        system_prompt=(
            "You are the PLANNER agent. Decompose the goal into a DAG of small tasks "
            "(gather_evidence/find_components/run_stat/compose/apply_author_style/"
            "patch_preview/verify_consistency/strobe_check). Output JSON list of nodes "
            "with id/action/args/deps/rationale. Do NOT execute tools yourself."),
        allowed_tools=[],
        fallback_llm_task="standard",
    ),
    "statistician": RoleSpec(
        name="statistician",
        description="StatBridge 결과 해석, 통계 보고  작성. 환각 차단.",
        system_prompt=(
            "You are the STATISTICIAN agent. ALWAYS report numbers with 95% CI and P-value. "
            "Never invent statistics. Use exact format: aOR 1.27 (95% CI 1.03-1.56; P = 0.026). "
            "If KYRBS data needed, call kyrbs_stat tool. Cite the actual n and design."),
        allowed_tools=["kyrbs_stat", "find_components", "patch_preview"],
        fallback_llm_task="paper_writing",
    ),
    "citation_auditor": RoleSpec(
        name="citation_auditor",
        description="reference 실존·DOI·orphan 검증. 새 ref 추가 안 함.",
        system_prompt=(
            "You are the CITATION AUDITOR. Verify every [n] in the draft maps to a real "
            "reference. Use pubmed_search/rag_search to find existing refs. "
            "NEVER invent DOI or PMID. Report orphan citations and year inconsistencies."),
        allowed_tools=["pubmed_search", "rag_search", "cross_modal_query"],
        fallback_llm_task="qa",
    ),
    "critic": RoleSpec(
        name="critic",
        description="작성된 draft를 STROBE/일관성/논리 측면에서 비판.",
        system_prompt=(
            "You are the CRITIC agent. Review the given draft for: STROBE compliance, "
            "internal consistency (n/OR/CI/P-value), logical flow, missing limitations. "
            "Always run strobe_check and consistency_check. Be specific about line numbers/sections."),
        allowed_tools=["strobe_check", "consistency_check", "find_components"],
        fallback_llm_task="paper_review",
    ),
    "writer": RoleSpec(
        name="writer",
        description="Content layer 합성 (substance). Style layer는 stylist에 위임.",
        system_prompt=(
            "You are the WRITER agent (① content layer). Given evidence + components, "
            "compose a coherent paragraph preserving all citations and statistics. "
            "Do NOT apply author style here — that's the stylist's job. Output plain substance."),
        allowed_tools=["find_components", "cross_modal_query", "patch_preview"],
        fallback_llm_task="paper_writing",
    ),
    "stylist": RoleSpec(
        name="stylist",
        description="② Style layer — substance에 author voice 입힘.",
        system_prompt=(
            "You are the STYLIST agent (② style layer). Apply Yoosun Cho style "
            "(hedging vocab, evidence-first sentences, topic→evidence→limitation→transition). "
            "PRESERVE every number, citation, and statistical token exactly."),
        allowed_tools=["apply_author_style", "find_components", "patch_preview"],
        fallback_llm_task="paper_writing",
    ),
    "researcher": RoleSpec(
        name="researcher",
        description="신규성/유사논문 탐색. PubMed + RAG + citation_graph.",
        system_prompt=(
            "You are the RESEARCHER agent. Find recent similar studies, evaluate novelty, "
            "suggest missing seminal references. Use pubmed_search + cross_modal_query."),
        allowed_tools=["pubmed_search", "cross_modal_query", "rag_search"],
        fallback_llm_task="standard",
    ),
    # ★ KNOWLEDGE_ACQUISITION_SPEC §11/§12 — 선언적 config 보강 (khoj 빌더 X, 단순 정리).
    "novelty_hunter": RoleSpec(
        name="novelty_hunter",
        description="활성 주제의 novelty 변화 추적 — 새 evidence 등장 시 재평가.",
        system_prompt=(
            "You are the NOVELTY_HUNTER agent. Continuously compare the user's research topic "
            "against fresh evidence (last 180 days). If a similar study just appeared, surface "
            "it with exact PMID + distance score (novelty shift). Do not invent citations."),
        allowed_tools=["pubmed_search", "rag_search", "external_evidence",
                        "consensus_search", "novelty"],
        fallback_llm_task="standard",
    ),
    "trend_scout": RoleSpec(
        name="trend_scout",
        description="필드 단위 트렌드 study — 노출/결과 변수의 신규 측정·방법 출현.",
        system_prompt=(
            "You are the TREND_SCOUT agent. Identify newly emerging measurement methods, "
            "outcome definitions, or sub-population analyses in the user's research field "
            "(180-day window). Output: top-5 trend signals with provenance pins (PMID + "
            "year + change vs prior baseline). Honor cost cap."),
        allowed_tools=["pubmed_search", "longitudinal_trend", "external_evidence",
                        "rag_search"],
        fallback_llm_task="standard",
    ),
    "deep_researcher": RoleSpec(
        name="deep_researcher",
        description="딥리서치 루프 — 검색→공백탐지→라이브획득→내재화→재검색→합성.",
        system_prompt=(
            "You are the DEEP_RESEARCHER agent. Treat the question as a multi-iteration "
            "loop: (1) local RAG retrieve, (2) detect coverage gaps, (3) acquire via "
            "evidence_reader (PubMed/Crossref/EuropePMC) only if gap, (4) ingest to RAG "
            "(self-reinforcement), (5) re-retrieve, (6) synthesize with provenance. "
            "Respect max_iters and cost_cap; emit one summary per iteration. Never invent."),
        allowed_tools=["rag_search", "pubmed_search", "external_evidence",
                        "consensus_search", "cross_modal_query", "patch_preview"],
        fallback_llm_task="standard",
    ),
}


# Action → role mapping (Planner DAG node의 action을 어느 role이 처리할지)
ACTION_TO_ROLE: Dict[str, str] = {
    "gather_evidence": "researcher",
    "find_components": "writer",        # 또는 stylist (kind에 따라)
    "run_stat":        "statistician",
    "compose":         "writer",
    "apply_author_style": "stylist",
    "patch_preview":   "writer",
    "verify_consistency": "critic",
    "strobe_check":    "critic",
    "pubmed_search":   "researcher",
    "rag_search":      "researcher",
    "cross_modal_query": "researcher",
    # ★ §11/§12 신규 action 매핑
    "novelty_check":   "novelty_hunter",
    "trend_study":     "trend_scout",
    "deep_research":   "deep_researcher",
    "currency_study":  "trend_scout",
}


def role_for_action(action: str) -> str:
    return ACTION_TO_ROLE.get(action, "writer")


def dispatch_role(role_name: str, inputs: Dict[str, Any]) -> Dict[str, Any]:
    """role에 위임 — specialized system prompt로 LLM 호출 + 허용 tool만 사용 가능.

    실 LLM tool-use loop는 ClaudeClient.generate_with_tools에 위임 (이미 구현됨).
    본 helper는 role spec을 fetch + system prompt + 도구 화이트리스트 적용.

    Returns: {"role": role_name, "text": ..., "trace": [...], "tools_used": [...]}
    """
    role = ROLES.get(role_name)
    if not role:
        return {"role": role_name, "error": f"unknown role: {role_name}", "text": ""}

    try:
        from src.runtime import events as _events
        _events.append("role_dispatch",
                        {"role": role_name, "input_keys": list(inputs.keys())},
                        actor="roles")
    except Exception:
        pass

    user_msg = inputs.get("message") or json.dumps(inputs, ensure_ascii=False)[:1500]

    # 도구 호출 가능한 role은 ClaudeClient.generate_with_tools 사용
    if role.allowed_tools:
        try:
            from app.agentic_loop import TOOL_SCHEMAS, make_tool_handler
            from src.llm.claude_client import ClaudeClient

            # 허용된 도구만 노출
            allowed = set(role.allowed_tools)
            schemas = [s for s in TOOL_SCHEMAS if s.get("name") in allowed]

            # 최소 project 컨텍스트 (write 도구가 작동하려면 필요)
            proj_state: Dict = inputs.get("project") or {"sections": {}}
            chat_events: List = []
            handler = make_tool_handler(
                lambda: proj_state, lambda p: proj_state.update(p),
                lambda t, p: chat_events.append({"type": t, **p}))

            # RULE-12: 직접 ClaudeClient X — get_llm_client(failover+persona)
            from src.llm import get_llm_client
            cc = get_llm_client(task=role.fallback_llm_task)
            result = cc.generate_with_tools(
                user_message=user_msg, tools=schemas,
                tool_handler=handler, system_prompt=role.system_prompt,
                max_tokens=2500, max_iters=4, task=role.fallback_llm_task)
            return {
                "role": role_name, "text": result.get("text", ""),
                "trace": result.get("trace", []),
                "tools_used": [t.get("tool") for t in result.get("trace", [])],
                "chat_events": chat_events[:20],
            }
        except Exception as e:
            _log.warning("role %s tool-use fail: %s", role_name, e)

    # 도구 없거나 실패 → 단순 generate
    try:
        from src.llm import get_llm_client
        client = get_llm_client(task=role.fallback_llm_task)
        out = client.generate(user_msg, system_prompt=role.system_prompt, max_tokens=2000)
        return {"role": role_name, "text": out or "", "trace": [], "tools_used": []}
    except Exception as e:
        return {"role": role_name, "error": str(e)[:200], "text": ""}


def role_stats() -> Dict:
    """role registry 요약."""
    return {
        "n_roles": len(ROLES),
        "roles": [{"name": r.name, "description": r.description,
                    "n_tools": len(r.allowed_tools),
                    "tools": r.allowed_tools} for r in ROLES.values()],
        "action_mapping": ACTION_TO_ROLE,
    }
