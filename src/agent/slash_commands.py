"""의학 논문 도메인 슬래시 커맨드 — agent-skills (Addy Osmani) 패턴 적용.

7 슬래시 (의학 논문 lifecycle):
  /research-question — 가설 + novelty 평가
  /study-design     — KYRBS/KNHANES design + STROBE 검증
  /run-analysis     — StatBridge 회귀 + figure
  /draft-section    — content + style 2-layer 합성
  /strobe-review    — 22항목 + consistency + causal
  /submit-journal   — docx + figure + EndNote XML
  /research-pulse   — 진행 상태 요약 (project + backlog + memory)

각 슬래시는 multi-step 워크플로우 — Planner DAG 호출 또는 직접 dispatch.

호출:
    from src.agent.slash_commands import run_slash, list_slashes
    out = run_slash("/research-question",
                     {"topic": "ZCB depression adolescents"})
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@dataclass
class SlashResult:
    slash: str
    ok: bool
    steps: List[Dict] = field(default_factory=list)
    output: Optional[Dict] = None
    error: str = ""
    elapsed_sec: float = 0.0

    def to_dict(self) -> Dict:
        return asdict(self)


# ── 핸들러들 ────────────────────────────────────────────────────────────────

def _h_research_question(args: Dict) -> SlashResult:
    """가설 정의 + PubMed novelty 평가."""
    res = SlashResult(slash="/research-question", ok=True)
    topic = args.get("topic") or args.get("query", "")
    if not topic:
        res.ok = False; res.error = "topic 필요"
        return res
    t0 = time.time()
    try:
        from src.research.novelty_checker import NoveltyChecker
        novelty = NoveltyChecker().check(topic, max_results=10, years=5)
        res.steps.append({"step": "novelty", "ok": True,
                            "score": novelty.get("novelty_score"),
                            "n_similar": len(novelty.get("similar_papers", []))})
    except Exception as e:
        res.steps.append({"step": "novelty", "ok": False, "error": str(e)[:200]})

    try:
        from src.knowledge.orchestrator import get_orchestrator
        cm = get_orchestrator().query(topic, k=5)
        res.steps.append({"step": "cross_modal", "ok": True,
                            "n_hits": cm.get("n_hits"),
                            "top_concepts": cm.get("top_concepts", [])[:3]})
        res.output = {"topic": topic,
                       "novelty": novelty if 'novelty' in dir() else None,
                       "cross_modal": cm}
    except Exception as e:
        res.steps.append({"step": "cross_modal", "ok": False, "error": str(e)[:200]})

    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


def _h_study_design(args: Dict) -> SlashResult:
    """KYRBS/KNHANES design + STROBE 검증."""
    res = SlashResult(slash="/study-design", ok=True)
    t0 = time.time()
    sections = args.get("sections", {})
    if not sections:
        res.error = "sections 필요 (Introduction/Methods 등 dict)"
        res.ok = False
        return res
    try:
        from src.research.reporting_checklist import auto_check
        rep = auto_check(sections, abstract=str(sections.get("Abstract", "")),
                          study_design=args.get("study_design", "cross_sectional"))
        res.steps.append({"step": "strobe", "ok": True,
                            "score": rep.get("score"), "total": rep.get("total"),
                            "missing": rep.get("missing", [])[:8]})
        res.output = {"strobe_report": rep}
    except Exception as e:
        res.steps.append({"step": "strobe", "ok": False, "error": str(e)[:200]})
        res.ok = False
    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


def _h_run_analysis(args: Dict) -> SlashResult:
    """StatBridge 회귀 (KYRBS 2025)."""
    res = SlashResult(slash="/run-analysis", ok=True)
    t0 = time.time()
    outcome = args.get("outcome", "depression")
    exposure = args.get("exposure")
    if not exposure:
        res.ok = False; res.error = "exposure 필요"
        return res
    try:
        from pathlib import Path as _P
        from src.data.kyrbs_raw_loader import KYRBSLoader
        from src.data.stat_bridge import StatBridge
        df, _m = KYRBSLoader().load(_P("data/raw/kyrbs2025.sav"))
        covs = args.get("covariates") or [c for c in ["sex","age","school_type","family_econ",
                                                        "academic_perf","bmi","smoking","alcohol",
                                                        "physical_act","screen_time","breakfast"]
                                            if c in df.columns]
        spec = {"outcome": outcome, "predictors": [exposure], "covariates": covs,
                 "weight_var": "weight_var" if "weight_var" in df.columns else None,
                 "strata_var":  "strata"     if "strata"     in df.columns else None,
                 "cluster_var": "cluster"    if "cluster"    in df.columns else None,
                 "analysis": "logistic"}
        r = StatBridge().run(df, spec).to_dict()
        vars_ = r.get("model_vars", [])
        tgt = next((v for v in vars_ if exposure in str(v.get("variable","")).lower()), None)
        res.steps.append({"step": "stat", "ok": True,
                            "n": len(df), "n_cov": len(covs),
                            "aOR": tgt.get("or_value") if tgt else None,
                            "ci_low": tgt.get("ci_lower") if tgt else None,
                            "ci_high": tgt.get("ci_upper") if tgt else None,
                            "p_value": tgt.get("p_value") if tgt else None})
        res.output = {"stat_result": r, "target_var": tgt}
    except Exception as e:
        res.steps.append({"step": "stat", "ok": False, "error": str(e)[:200]})
        res.ok = False
    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


def _h_draft_section(args: Dict) -> SlashResult:
    """content + style 2-layer 합성 → planner DAG로 실행."""
    res = SlashResult(slash="/draft-section", ok=True)
    t0 = time.time()
    section = args.get("section", "Introduction")
    goal = args.get("goal", section)
    pace_mode = args.get("pace_mode", "proactive")
    try:
        from src.agent.planner import get_planner
        from src.agent.roles import role_for_action, dispatch_role
        ctx = {"section": section, "outcome": args.get("outcome"),
                "exposure": args.get("exposure"), "pace_mode": pace_mode}
        graph = get_planner().plan(goal, context=ctx)
        # dispatch 단계만 (실 패치는 사용자 승인 후)
        steps = []
        for node in graph.nodes.values():
            role = role_for_action(node.action)
            steps.append({"node": node.id, "action": node.action, "role": role,
                            "rationale": node.rationale})
        res.steps.append({"step": "plan", "ok": True, "graph_id": graph.id,
                            "n_nodes": len(graph.nodes), "nodes": steps})
        res.output = {"graph_id": graph.id, "pace_mode": pace_mode,
                       "steps_preview": steps}
    except Exception as e:
        res.steps.append({"step": "plan", "ok": False, "error": str(e)[:200]})
        res.ok = False
    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


def _h_strobe_review(args: Dict) -> SlashResult:
    """STROBE 22 + consistency + causal 통합 검사."""
    res = SlashResult(slash="/strobe-review", ok=True)
    t0 = time.time()
    paper_text = args.get("text") or ""
    if not paper_text and args.get("sections"):
        paper_text = "\n\n".join(str(v) for v in args["sections"].values()
                                    if isinstance(v, str))
    if not paper_text:
        res.ok = False; res.error = "text 또는 sections 필요"
        return res

    # 1) STROBE
    try:
        from src.research.reporting_checklist import auto_check
        sec = args.get("sections") or {"Paper": paper_text}
        strobe = auto_check(sec, abstract=str(sec.get("Abstract", paper_text[:1500])),
                              study_design=args.get("study_design", "cross_sectional"))
        res.steps.append({"step": "strobe", "ok": True,
                            "score": strobe.get("score"), "missing": strobe.get("missing", [])[:6]})
    except Exception as e:
        res.steps.append({"step": "strobe", "ok": False, "error": str(e)[:200]})

    # 2) Consistency
    try:
        from src.safety.consistency_checker import check_consistency
        cc = check_consistency({"Paper": paper_text})
        res.steps.append({"step": "consistency", "ok": True,
                            "severity": cc.severity, "n_issues": len(cc.issues)})
    except Exception as e:
        res.steps.append({"step": "consistency", "ok": False, "error": str(e)[:200]})

    # 3) Causal
    try:
        from src.safety.causal_checker import check_causal_claims
        ca = check_causal_claims(paper_text,
                                    study_design=args.get("study_design", "cross_sectional"))
        res.steps.append({"step": "causal", "ok": True,
                            "severity": ca.severity, "n_strong": ca.n_strong,
                            "n_weak": ca.n_weak})
    except Exception as e:
        res.steps.append({"step": "causal", "ok": False, "error": str(e)[:200]})

    res.output = {"summary": {"strobe": res.steps[0] if res.steps else None,
                                "consistency": res.steps[1] if len(res.steps) > 1 else None,
                                "causal": res.steps[2] if len(res.steps) > 2 else None}}
    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


def _h_submit_journal(args: Dict) -> SlashResult:
    """docx + figure + EndNote XML 패키지 생성."""
    res = SlashResult(slash="/submit-journal", ok=True)
    t0 = time.time()
    project = args.get("project") or {}
    if not project:
        res.ok = False; res.error = "project 필요"
        return res
    try:
        from src.export.word_exporter import WordExporter
        path = WordExporter().export(
            topic=project.get("topic") or {"title": project.get("title", "Untitled")},
            sections=project.get("sections", {}),
            references=project.get("references", []),
            back_matter=project.get("back_matter", {}),
            keywords=project.get("keywords", []),
            figures=project.get("figures_bin", []),
            tables=project.get("tables", []),
        )
        res.steps.append({"step": "docx", "ok": True, "path": str(path)})
        res.output = {"docx_path": str(path)}
    except Exception as e:
        res.steps.append({"step": "docx", "ok": False, "error": str(e)[:200]})
        res.ok = False
    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


def _h_research_pulse(args: Dict) -> SlashResult:
    """진행 상태 요약 — project/backlog/memory/OA 한 줄."""
    res = SlashResult(slash="/research-pulse", ok=True)
    t0 = time.time()
    pulse: Dict = {}
    try:
        from src.ingestion.oa_bulk_fetcher import manifest_stats
        ms = manifest_stats()
        pulse["oa"] = {"papers": ms["total_papers"], "chars": ms["total_chars"]}
    except Exception:
        pass
    try:
        from src.library.components import get_library
        pulse["components"] = get_library().stats().get("total", 0)
    except Exception:
        pass
    try:
        from src.runtime.backlog import status
        pulse["backlog"] = status(limit=100).get("counts", {})
    except Exception:
        pass
    try:
        from src.memory import stats as ms_mem
        pulse["memory"] = {k: v for k, v in ms_mem().items() if isinstance(v, (int, dict))}
    except Exception:
        pass
    try:
        from src.runtime.notifier import stats as nstats
        pulse["notifications"] = nstats()
    except Exception:
        pass
    try:
        from src.diagnostics.longitudinal_eval import summary
        pulse["longitudinal"] = {k: summary(days=30).get(k) for k in
                                    ("n_runs", "avg_pass_rate", "alerts")}
    except Exception:
        pass
    res.output = pulse
    res.steps.append({"step": "snapshot", "ok": True, "keys": list(pulse.keys())})
    res.elapsed_sec = round(time.time() - t0, 2)
    _emit_event(res)
    return res


_HANDLERS: Dict[str, Callable[[Dict], SlashResult]] = {
    "/research-question": _h_research_question,
    "/study-design":      _h_study_design,
    "/run-analysis":      _h_run_analysis,
    "/draft-section":     _h_draft_section,
    "/strobe-review":     _h_strobe_review,
    "/submit-journal":    _h_submit_journal,
    "/research-pulse":    _h_research_pulse,
}


def list_slashes() -> List[Dict]:
    return [{"slash": s, "description": h.__doc__ or ""}
             for s, h in _HANDLERS.items()]


def run_slash(slash: str, args: Optional[Dict] = None) -> Dict:
    args = args or {}
    h = _HANDLERS.get(slash)
    if not h:
        return {"ok": False, "error": f"unknown slash: {slash}",
                 "available": list(_HANDLERS.keys())}
    try:
        return h(args).to_dict()
    except Exception as e:
        import traceback
        return {"ok": False, "slash": slash, "error": str(e)[:200],
                 "trace": traceback.format_exc()[-500:]}


def _emit_event(res: SlashResult):
    try:
        from src.runtime import events as _ev
        _ev.append("slash_command",
                    {"slash": res.slash, "ok": res.ok, "steps": len(res.steps),
                     "elapsed_sec": res.elapsed_sec},
                    actor="slash_commands")
    except Exception:
        pass
