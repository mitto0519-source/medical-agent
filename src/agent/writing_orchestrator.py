"""Writing Orchestrator — 논문 작성 흐름 관리.

A2A (Agent-to-Agent) 구조:
  ┌─────────────────────┐         KnowledgeRequest          ┌────────────────────────┐
  │ WritingOrchestrator │ ───────────────────────────────▶ │ KnowledgeOrchestrator  │
  │   (이 모듈)          │                                    │ (src.knowledge.orch.)  │
  │                     │ ◀─────────────────────────────── │                        │
  │  - intent 분류       │         KnowledgeResponse          │  - graph/vector/      │
  │  - section 계획       │                                    │    ontology/citation  │
  │  - patch 적용         │                                    │  - cross-modal query  │
  └─────────────────────┘                                    └────────────────────────┘
         │ patch_preview                                              ▲ ingest
         ▼                                                            │
   project["sections"]                                          새 논문 (OA/PDF/...)

설계 의도 (사용자 진단 2026-05-28):
  "논문 분석-분해-학습 하는 Orchestrator → 작성하는 Agent에게 A2A로 적시에 정보 공급"
  단순한 ad-hoc tool dispatch가 아니라 두 orchestrator 간 명시적 contract가 필요.

사용:
    wo = WritingOrchestrator()
    plan = wo.plan_section(project, section="Introduction", goal="...")
    # plan = [{"action": "gather_evidence", "query": "...", "n": 5}, ...]
    for step in plan:
        wo.execute_step(step, project)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── A2A Contract — Knowledge ↔ Writing ───────────────────────────────────────

@dataclass
class KnowledgeRequest:
    """WritingOrchestrator → KnowledgeOrchestrator 요청 schema."""
    intent: str                           # "evidence" | "definition" | "citation" | "stat_method" | "figure_example"
    query: str
    section_target: str = ""              # 결과를 어디에 patch할지 (Introduction/Methods/etc)
    k: int = 5
    must_include_concepts: List[str] = field(default_factory=list)
    must_include_years: Optional[List[int]] = None
    context_hint: str = ""                # 추가 컨텍스트 (현재 docx 일부 등)


@dataclass
class KnowledgeResponse:
    """KnowledgeOrchestrator → WritingOrchestrator 응답 schema."""
    intent: str
    query: str
    n_hits: int
    hits: List[Dict] = field(default_factory=list)
    top_concepts: List[Dict] = field(default_factory=list)
    suggested_citations: List[Dict] = field(default_factory=list)   # [{pmid, title, year, doi}]
    error: str = ""

    def to_dict(self) -> Dict:
        return asdict(self)


# ── WritingOrchestrator ──────────────────────────────────────────────────────

@dataclass
class WritingPlanStep:
    action: str         # "gather_evidence" | "patch_preview" | "verify_consistency" | "run_stat"
    args: Dict = field(default_factory=dict)
    rationale: str = ""


class WritingOrchestrator:
    """사용자 의도를 받아 multi-step 계획 → KnowledgeOrchestrator 위임 → patch."""

    _instance: Optional["WritingOrchestrator"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self._korch = None

    @property
    def korch(self):
        if self._korch is None:
            from src.knowledge.orchestrator import get_orchestrator
            self._korch = get_orchestrator()
        return self._korch

    # ── A2A 핵심 메서드 ─────────────────────────────────────────────────────

    def ask_knowledge(self, req: KnowledgeRequest) -> KnowledgeResponse:
        """A2A: KnowledgeOrchestrator에 정보 요청. 단일 진입점."""
        try:
            from src.runtime import events as _events
            _events.append("a2a_request",
                            {"intent": req.intent, "query": req.query[:160],
                             "k": req.k, "target": req.section_target},
                            actor="writing_orchestrator")
        except Exception:
            pass

        if not self.korch:
            return KnowledgeResponse(intent=req.intent, query=req.query, n_hits=0,
                                       error="korch unavailable")

        # 1) cross-modal vector + graph query
        try:
            result = self.korch.query(req.query, k=req.k)
        except Exception as e:
            return KnowledgeResponse(intent=req.intent, query=req.query, n_hits=0,
                                       error=str(e)[:200])

        hits = result.get("hits", [])

        # 2) must_include filter
        if req.must_include_concepts:
            wanted = {c.lower() for c in req.must_include_concepts}
            hits = [h for h in hits
                     if any(str(c).lower() in wanted for c in h.get("concepts", []))]
        if req.must_include_years:
            wanted_y = set(req.must_include_years)
            hits = [h for h in hits
                     if h.get("year") and int(h["year"]) in wanted_y]

        # 3) 인용 후보 (제목/연도 있는 hit만)
        citations = [{"pmid": h.get("pmid", ""), "title": h.get("title", ""),
                       "year": h.get("year")}
                      for h in hits if h.get("pmid") and h.get("title")][:5]

        resp = KnowledgeResponse(
            intent=req.intent, query=req.query, n_hits=len(hits),
            hits=hits[:req.k], top_concepts=result.get("top_concepts", []),
            suggested_citations=citations,
        )

        try:
            _events.append("a2a_response",
                            {"intent": req.intent, "n_hits": resp.n_hits,
                             "n_citations": len(resp.suggested_citations)},
                            actor="writing_orchestrator")
        except Exception:
            pass
        return resp

    # ── Plan 수립 (LLM 도움 없이 룰 기반 단계 분해) ────────────────────────

    def plan_section(self, project: Dict, section: str, goal: str = "") -> List[WritingPlanStep]:
        """섹션별 multi-step plan. 룰 기반(LLM 없이도 동작)."""
        title = project.get("title", "")
        sec_l = section.lower()

        if sec_l in ("introduction", "intro"):
            return [
                WritingPlanStep("gather_evidence",
                                 {"intent": "definition", "query": title + " definition epidemiology",
                                  "k": 4, "section_target": section},
                                 "Introduction은 정의 + 역학 평가가 필요"),
                WritingPlanStep("gather_evidence",
                                 {"intent": "evidence", "query": title + " adolescent depression",
                                  "k": 6, "section_target": section},
                                 "선행연구 6편으로 hypothesis 유도"),
                WritingPlanStep("patch_preview",
                                 {"section": section,
                                  "content": "_auto_compose_intro_"},
                                 "수집된 evidence를 Yoosun 스타일 단락으로 합성"),
            ]
        if sec_l == "methods":
            return [
                WritingPlanStep("gather_evidence",
                                 {"intent": "stat_method", "query": goal + " survey weighted logistic",
                                  "k": 3, "section_target": section},
                                 "사용할 통계방법 사례 확보"),
                WritingPlanStep("run_stat", {"outcome": project.get("outcome", "depression"),
                                                "exposure": project.get("exposure", "zcb_freq")},
                                 "KYRBS 실제 분석"),
                WritingPlanStep("patch_preview", {"section": section, "content": "_auto_compose_methods_"},
                                 "Methods 단락 합성"),
            ]
        if sec_l == "results":
            return [
                WritingPlanStep("run_stat", {"outcome": project.get("outcome", "depression"),
                                                "exposure": project.get("exposure", "zcb_freq")},
                                 "주요 결과 산출"),
                WritingPlanStep("patch_preview", {"section": "Results", "content": "_auto_compose_results_"},
                                 "aOR/CI 보고 양식으로 patch"),
                WritingPlanStep("verify_consistency", {},
                                 "n/OR-CI/P 정형 일관성 검사"),
            ]
        if sec_l == "discussion":
            return [
                WritingPlanStep("gather_evidence",
                                 {"intent": "evidence", "query": title + " mechanism gut-brain",
                                  "k": 5, "section_target": section},
                                 "기전 해석 위한 ref"),
                WritingPlanStep("patch_preview", {"section": section, "content": "_auto_compose_discussion_"},
                                 "Discussion 단락 합성"),
                WritingPlanStep("verify_consistency", {}, "전체 정합성 재검사"),
            ]
        # default: 단순 evidence + patch
        return [
            WritingPlanStep("gather_evidence",
                             {"intent": "evidence", "query": goal or title, "k": 5,
                              "section_target": section},
                             "기본 evidence 수집"),
            WritingPlanStep("patch_preview",
                             {"section": section, "content": "_auto_compose_generic_"},
                             "수집 결과로 patch"),
        ]

    def execute_step(self, step: WritingPlanStep, project: Dict,
                       on_patch=None) -> Dict:
        """plan_section의 한 step 실행. 반환은 dict (chat에 표시 가능)."""
        if step.action == "gather_evidence":
            req = KnowledgeRequest(
                intent=step.args.get("intent", "evidence"),
                query=step.args.get("query", ""),
                section_target=step.args.get("section_target", ""),
                k=int(step.args.get("k", 5)),
                must_include_concepts=step.args.get("must_include_concepts", []) or [],
            )
            resp = self.ask_knowledge(req)
            return {"step": "gather_evidence", "rationale": step.rationale,
                     "response": resp.to_dict()}
        if step.action == "patch_preview":
            # _auto_compose_* placeholder: 실 LLM 호출이 필요한 자리.
            # 본 메서드는 룰 기반이므로 evidence를 plain하게 합성.
            content = step.args.get("content", "")
            if isinstance(content, str) and content.startswith("_auto_compose_"):
                content = "(plan placeholder — LLM이 다음 step에서 실 본문 작성 필요)"
            sec = step.args.get("section", "Notes")
            if on_patch:
                on_patch(sec, content)
            return {"step": "patch_preview", "section": sec,
                     "len": len(content), "rationale": step.rationale}
        if step.action == "verify_consistency":
            try:
                from src.safety.consistency_checker import check_consistency
                rep = check_consistency(project.get("sections") or {})
                return {"step": "verify_consistency", "severity": rep.severity,
                         "n_issues": len(rep.issues)}
            except Exception as e:
                return {"step": "verify_consistency", "error": str(e)[:200]}
        if step.action == "run_stat":
            try:
                from pathlib import Path as _P
                from src.data.kyrbs_raw_loader import KYRBSLoader
                from src.data.stat_bridge import StatBridge
                df, _m = KYRBSLoader().load(_P("data/raw/kyrbs2025.sav"))
                spec = {"outcome": step.args.get("outcome"),
                         "predictors": [step.args.get("exposure")],
                         "covariates": ["sex", "age", "school_type"],
                         "weight_var": "weight_var",
                         "strata_var": "strata", "cluster_var": "cluster",
                         "analysis": "logistic"}
                r = StatBridge().run(df, spec).to_dict()
                exp = step.args.get("exposure")
                vars_ = r.get("model_vars", [])
                tgt = next((v for v in vars_ if exp in str(v.get("variable", "")).lower()),
                           None)
                if tgt:
                    return {"step": "run_stat", "aOR": tgt.get("or_value"),
                             "ci_low": tgt.get("ci_lower"),
                             "ci_high": tgt.get("ci_upper"),
                             "p_value": tgt.get("p_value")}
                return {"step": "run_stat", "warn": "target var not found"}
            except Exception as e:
                return {"step": "run_stat", "error": str(e)[:200]}
        return {"step": step.action, "warn": "unknown action"}


def get_writing_orchestrator() -> WritingOrchestrator:
    return WritingOrchestrator()
