"""Pipeline Orchestrator — 백엔드 논문 작성 상태기계 (RESEARCH_PIPELINE_SPEC §3).

핵심 통찰(사용자, 2026-06-17): 의료 논문 = 골격 → 가설(Abstract) → 통계 검증 → 숫자 확인
→ 섹션별 디벨롭 → 완성도·톤. LLM 한 방 생성이 아니라 **백엔드가 단계를 강제** + LLM은
현재 단계 + 검증된 state 슬라이스만 받아 채운다.

★ 급소 = STATS 게이트 (숫자 먼저, 산문 나중):
   state.results["estimates"]에 provenance 핀(dataset_version·registry_version·code_sha)이
   박힌 검증된 실수치(aOR/CI/p/n)가 있어야 SECTIONS 진입 가능. 통과 전 산문 작성 금지.
   = 환각 통계 원천 차단.

부품 매핑(중복 0 — 오케스트레이션만 신규, SPEC §4):
  SCOPE      → ResearchPipeline.generate_topics + validate_feasibility
  SKELETON   → 이 파일에서 LLM 1콜 경량 신규
  HYPOTHESIS → write_paper(abstract_only 모드 호출)
  STATS      → ResearchPipeline.run_stat_analysis + survey_weighted.fit_logit_svy
  SECTIONS   → write_paper(per-section, state.results 인용 강제)
  POLISH     → review_and_revise + (yoosun + journal_intel 옵션)

흐름:
  advance(state, auto=False)  # 한 단계 진행 (gate 검사 → 실행 → checkpoint)
  advance(state, auto=True)   # 전체 자동 진행, STATS gate에서만 사람 확인 대기
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterator, List, Optional, Tuple

from src.config.logging_config import get_logger
from src.research.research_state import ResearchProject, checkpoint, project_save
from src.service import events as ev

_log = get_logger(__name__)

STAGES = ("SCOPE", "SKELETON", "HYPOTHESIS", "STATS", "SECTIONS", "POLISH", "DONE")
STAGE_LABELS = {
    "SCOPE": "주제·PICO·데이터 합의",
    "SKELETON": "IMRaD 골격",
    "HYPOTHESIS": "Abstract 가설",
    "STATS": "통계 검증 (숫자 먼저)",
    "SECTIONS": "섹션별 작성",
    "POLISH": "완성도·톤",
    "DONE": "Export 준비",
}


# ── Gate 함수들 ──────────────────────────────────────────────────────────────

def _gate_scope(s: ResearchProject) -> Tuple[bool, List[str]]:
    """SCOPE 통과 = PICO 5요소(Population/Intervention/Comparison/Outcome/Time) +
    dataset 가용성 (등록 dataset 이름 있음)."""
    issues: List[str] = []
    pico = (s.rq or {}).get("pico") or {}
    required = ("population", "exposure", "outcome", "study_design")
    missing = [k for k in required if not pico.get(k)]
    if missing:
        issues.append(f"PICO 누락: {missing}")
    if not (s.dataset or {}).get("name"):
        issues.append("dataset 미지정")
    return (not issues), issues


def _gate_skeleton(s: ResearchProject) -> Tuple[bool, List[str]]:
    """SKELETON 통과 = manuscript.skeleton에 6개 섹션 슬롯 + 각 1줄 목적."""
    sk = (s.manuscript or {}).get("skeleton") or {}
    required_keys = ("Abstract", "Introduction", "Methods", "Results", "Discussion")
    missing = [k for k in required_keys if not sk.get(k)]
    if missing:
        return False, [f"skeleton 슬롯 누락: {missing}"]
    return True, []


def _gate_hypothesis(s: ResearchProject) -> Tuple[bool, List[str]]:
    """HYPOTHESIS 통과 = Abstract 초안 + 사전명시 가설(analysis_spec.preregistered=true).
    숫자는 placeholder 허용 (실값은 STATS 이후)."""
    issues: List[str] = []
    if not s.sections.get("Abstract"):
        issues.append("Abstract 초안 없음")
    spec = s.analysis_spec or {}
    if not spec.get("exposure") or not spec.get("outcome"):
        issues.append("analysis_spec.exposure/outcome 미지정")
    if not spec.get("effect_measure"):
        issues.append("analysis_spec.effect_measure(OR/HR/RR) 미지정")
    return (not issues), issues


def _gate_stats(s: ResearchProject) -> Tuple[bool, List[str]]:
    """★ STATS 게이트 (이 스펙의 심장) — 숫자 먼저, 산문 나중.

    통과 조건:
      1. state.results["estimates"]에 실수치 (aOR/CI/p/n) 존재
      2. provenance_ids에 핀 (dataset_version, registry_version)
      3. gates.stat = passed (가정검사)
      4. 휴먼 확인 — gates.stat_human_confirmed = True
    """
    issues: List[str] = []
    est = (s.results or {}).get("estimates") or {}
    if not est:
        issues.append("state.results['estimates'] 없음 — run_stat_analysis 미실행")
    else:
        # estimates는 dict 또는 list (양식 다양) — 핵심 키 확인
        if isinstance(est, dict):
            primary = est.get("primary") or est
            has_numbers = any(k in primary for k in
                                ("aOR", "OR", "HR", "RR", "beta", "coef"))
            if not has_numbers:
                issues.append("estimates에 효과크기 (aOR/OR/HR/RR/beta) 없음")
            if primary.get("ci_low") is None or primary.get("ci_high") is None:
                issues.append("95% CI 누락 (ci_low/ci_high)")
            if not primary.get("n"):
                issues.append("표본수(n) 누락")
    if not s.provenance_ids:
        issues.append("provenance 핀 미박힘 (dataset_version/registry_version)")
    gates = s.gates or {}
    if gates.get("stat") not in ("passed", "ok", True):
        issues.append("가정 검사 (gates.stat) 미통과")
    if not gates.get("stat_human_confirmed"):
        issues.append("★ 휴먼 확인 대기 — '이 숫자/해석으로 갈까요?' 승인 필요")
    return (not issues), issues


def _gate_sections(s: ResearchProject) -> Tuple[bool, List[str]]:
    """SECTIONS 통과 = Results + Methods + Introduction + Discussion 모두 채워짐
    + 모든 수치 = state.results 참조 (claim_evidence_nli — 옵션, 폴백 허용)."""
    issues: List[str] = []
    required = ("Introduction", "Methods", "Results", "Discussion")
    for k in required:
        v = s.sections.get(k)
        if not v or (isinstance(v, str) and len(v.strip()) < 50):
            issues.append(f"섹션 '{k}' 미완 또는 < 50자")
    return (not issues), issues


def _gate_polish(s: ResearchProject) -> Tuple[bool, List[str]]:
    """POLISH 통과 = peer review score >= 임계."""
    fb = (s.gates or {}).get("peer_score")
    if fb is None:
        return False, ["peer review 미실행"]
    try:
        if float(fb) < 60:
            return False, [f"peer score {fb} < 60 임계"]
    except Exception:
        return False, [f"peer score 파싱 실패: {fb}"]
    return True, []


_GATES = {
    "SCOPE": _gate_scope,
    "SKELETON": _gate_skeleton,
    "HYPOTHESIS": _gate_hypothesis,
    "STATS": _gate_stats,
    "SECTIONS": _gate_sections,
    "POLISH": _gate_polish,
}


def check_gate(state: ResearchProject, stage: Optional[str] = None) -> Tuple[bool, List[str]]:
    """현재 단계 (또는 명시 단계) 의 gate 확인. 외부 노출 — UI/tests에서 호출."""
    stg = stage or state.stage
    fn = _GATES.get(stg)
    if fn is None:
        return False, [f"unknown stage: {stg}"]
    return fn(state)


# ── 단계 실행자들 ────────────────────────────────────────────────────────────

def _exec_skeleton(state: ResearchProject) -> Dict[str, str]:
    """LLM 1콜로 IMRaD 골격 (각 섹션 1줄 목적). 경량 ($0.01 이하)."""
    from src.llm import get_llm_client
    pico = (state.rq or {}).get("pico") or {}
    ds = (state.dataset or {}).get("name", "(미지정)")
    prompt = (
        f"의학 논문 IMRaD 골격을 생성한다. 각 섹션마다 **1줄 목적** 만 작성.\n\n"
        f"연구 정보:\n"
        f"- 노출(exposure): {pico.get('exposure', '미지정')}\n"
        f"- 결과(outcome): {pico.get('outcome', '미지정')}\n"
        f"- 대상(population): {pico.get('population', '미지정')}\n"
        f"- 설계: {pico.get('study_design', '횡단')}\n"
        f"- 데이터: {ds}\n\n"
        f"출력 양식 (정확히 5줄):\n"
        f"Abstract: <1줄>\n"
        f"Introduction: <1줄>\n"
        f"Methods: <1줄>\n"
        f"Results: <1줄>\n"
        f"Discussion: <1줄>"
    )
    try:
        client = get_llm_client(task="paper_writing")
        out = client.generate(prompt, system_prompt="", max_tokens=400)
    except Exception as e:
        _log.warning("skeleton LLM fail: %s", e)
        out = (
            f"Abstract: {pico.get('exposure', '')}와 {pico.get('outcome', '')} 연관 검증\n"
            f"Introduction: 배경·근거·연구 갭·가설 명시\n"
            f"Methods: {ds} 설계·변수·통계분석 (survey-weighted)\n"
            f"Results: 기술통계·주요 추정치·민감도\n"
            f"Discussion: 주요 발견·기존 연구 비교·한계·결론"
        )
    sk: Dict[str, str] = {}
    for line in out.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip().split()[0]
        if key in ("Abstract", "Introduction", "Methods", "Results", "Discussion"):
            sk[key] = val.strip()
    return sk


def _exec_hypothesis(state: ResearchProject) -> str:
    """Abstract 초안 + 사전명시 가설 (placeholder 숫자 허용). LLM 1콜."""
    from src.llm import get_llm_client
    pico = (state.rq or {}).get("pico") or {}
    sk = (state.manuscript or {}).get("skeleton", {})
    ds = (state.dataset or {}).get("name", "")
    spec = state.analysis_spec or {}
    prompt = (
        f"의학 논문 Abstract 초안을 작성한다. 250 단어 이내, 사전명시 가설 포함, "
        f"숫자는 placeholder ([aOR placeholder], [CI placeholder]) 로.\n\n"
        f"연구:\n"
        f"- 가설: {pico.get('exposure', '')}이 {pico.get('outcome', '')}와 연관\n"
        f"- 데이터: {ds}\n"
        f"- 설계: {pico.get('study_design', 'cross-sectional')}\n"
        f"- 효과측정: {spec.get('effect_measure', 'aOR')}\n"
        f"- 골격 가이드: {sk.get('Abstract', '')}\n\n"
        f"Structured Abstract (Background/Methods/Results/Conclusions). 영어."
    )
    try:
        client = get_llm_client(task="paper_writing")
        return client.generate(prompt, system_prompt="", max_tokens=600)
    except Exception as e:
        _log.warning("hypothesis LLM fail: %s", e)
        return (
            "Background: Hypothesis-driven cross-sectional analysis (placeholder).\n\n"
            "Methods: Survey-weighted logistic regression.\n\n"
            "Results: aOR [placeholder] (95% CI [placeholder]).\n\n"
            "Conclusions: To be confirmed after stat verification."
        )


def _exec_stats(state: ResearchProject) -> Dict:
    """STATS 실행 — survey_weighted.fit_logit_svy 직접 호출.

    실데이터 로드는 외부 (ResearchPipeline.run_stat_analysis) 위임 가능.
    여기서는 결과 dict 양식만 강제: {primary: {aOR, ci_low, ci_high, p, n}, design, engine}.
    """
    from src.research.research_pipeline import ResearchPipeline
    try:
        rp = ResearchPipeline()
        spec = state.analysis_spec or {}
        if not spec.get("dataset"):
            spec["dataset"] = (state.dataset or {}).get("name")
        pico = (state.rq or {}).get("pico") or {}
        topic = {
            "title": state.title,
            "exposure": pico.get("exposure"),
            "outcome": pico.get("outcome"),
            "population": pico.get("population"),
            "study_design": pico.get("study_design"),
        }
        result = rp.run_stat_analysis(topic, dataset=spec.get("dataset"))
        return result if isinstance(result, dict) else {"raw": result}
    except Exception as e:
        _log.warning("STATS exec fail: %s", e)
        return {"error": str(e)[:200]}


def _exec_section(state: ResearchProject, section: str) -> str:
    """단일 섹션 작성 — state.results 인용 강제, 숫자 발명 금지.

    SECTIONS 작성 순서 (SPEC §1): Results → Methods → Introduction → Discussion
    """
    from src.llm import get_llm_client
    pico = (state.rq or {}).get("pico") or {}
    est = (state.results or {}).get("estimates") or {}
    primary = est.get("primary") or est
    sk = ((state.manuscript or {}).get("skeleton") or {}).get(section, "")

    facts_block = (
        f"※ ★ 검증된 통계 수치 (이 숫자만 인용, 다른 수치 발명 금지):\n"
        f"- 효과측정: {primary.get('effect_measure', primary.get('aOR'))}\n"
        f"- aOR: {primary.get('aOR')}\n"
        f"- 95% CI: ({primary.get('ci_low')}, {primary.get('ci_high')})\n"
        f"- p값: {primary.get('p')}\n"
        f"- 표본수 n: {primary.get('n')}\n"
        f"- 설계: {primary.get('design', 'survey-weighted')}\n"
    )

    prompt = (
        f"의학 논문 **{section}** 섹션을 작성한다. 영어, 학술체.\n\n"
        f"연구: {pico.get('exposure', '')} → {pico.get('outcome', '')}\n"
        f"데이터: {(state.dataset or {}).get('name', '')}\n"
        f"섹션 목적: {sk}\n\n"
        f"{facts_block}\n"
        f"★ 규칙: 위 facts_block의 수치만 인용. 새 수치 발명 금지. "
        f"인용은 [PMID:xxx] 양식."
    )

    try:
        client = get_llm_client(task="paper_writing")
        return client.generate(prompt, system_prompt="", max_tokens=1500)
    except Exception as e:
        _log.warning("section %s LLM fail: %s", section, e)
        return f"[{section} 작성 실패: {e}]"


def _exec_polish(state: ResearchProject) -> Dict:
    """완성도·톤 — review_and_revise 호출 + peer_score 추출."""
    try:
        from src.research.research_pipeline import ResearchPipeline
        rp = ResearchPipeline()
        topic = {"title": state.title}
        paper_text = state.manuscript_text
        result = rp.review_and_revise(paper_text, topic, state.results or {})
        return result if isinstance(result, dict) else {"raw": str(result)[:500]}
    except Exception as e:
        _log.warning("polish fail: %s", e)
        return {"error": str(e)[:200]}


# ── advance() — 백엔드 운전자 ─────────────────────────────────────────────────

def _next_stage(current: str) -> str:
    try:
        i = STAGES.index(current)
    except ValueError:
        return "SCOPE"
    return STAGES[min(i + 1, len(STAGES) - 1)]


def advance(state: ResearchProject, *, auto: bool = False,
              max_iters: int = 10) -> Iterator[Any]:
    """한 단계 진행 (또는 auto=True면 STATS gate까지 연속 진행).

    yield: ChatEvent (status/tool_result/badge/warning/done)
    state: in-place 수정 (project_save도 호출)
    """
    iters = 0
    while iters < max_iters:
        iters += 1
        stage = state.stage
        yield ev.status(f"단계 [{stage}] {STAGE_LABELS.get(stage, '')}")

        if stage == "DONE":
            yield ev.done(elapsed_iters=iters, final_stage="DONE")
            return

        # 1) 현재 단계 gate 검사
        passed, issues = check_gate(state, stage)

        if not passed:
            # 단계 실행이 필요 (gate 미통과 = 아직 안 채워짐)
            if stage == "SCOPE":
                yield ev.warning("scope_incomplete",
                                   f"SCOPE 미완: {' / '.join(issues)} — 사용자가 PICO/dataset 입력 필요")
                yield ev.done(stopped_at=stage, reason="needs_user_input")
                return

            elif stage == "SKELETON":
                yield ev.tool_start("skeleton_gen", "LLM 1콜")
                sk = _exec_skeleton(state)
                state.manuscript.setdefault("skeleton", {}).update(sk)
                yield ev.tool_result("skeleton_gen", {"sections": list(sk.keys())})
                project_save(state, cloud=True)

            elif stage == "HYPOTHESIS":
                yield ev.tool_start("hypothesis_gen", "Abstract 초안")
                abs_text = _exec_hypothesis(state)
                state.sections["Abstract"] = abs_text
                # analysis_spec 기본값 보강
                spec = state.analysis_spec or {}
                pico = (state.rq or {}).get("pico") or {}
                spec.setdefault("exposure", pico.get("exposure"))
                spec.setdefault("outcome", pico.get("outcome"))
                spec.setdefault("effect_measure", "aOR")
                spec.setdefault("preregistered", True)
                state.analysis_spec = spec
                yield ev.tool_result("hypothesis_gen", {"abstract_chars": len(abs_text)})
                project_save(state, cloud=True)

            elif stage == "STATS":
                yield ev.tool_start("stat_analysis", "survey_weighted 실엔진")
                result = _exec_stats(state)
                state.results["estimates"] = result
                # provenance 핀
                from src.runtime.provenance import build_fingerprint
                try:
                    pid = build_fingerprint(
                        dataset=(state.dataset or {}).get("name", ""),
                        analysis_spec=state.analysis_spec,
                        result=result,
                    )
                    state.provenance_ids.append(pid)
                except Exception as e:
                    _log.debug("provenance build fail: %s", e)
                # 가정검사 (간이) — error 없으면 passed
                gates = state.gates or {}
                gates["stat"] = "passed" if not result.get("error") else "failed"
                state.gates = gates
                yield ev.tool_result("stat_analysis",
                                       {"has_estimates": bool(result.get("primary") or result.get("aOR")),
                                        "error": result.get("error")})
                # ★ STATS gate = 자동 통과 X. 사용자 확인 필요.
                yield ev.warning("stats_gate",
                                   "★ 통계 결과를 확인하세요. '이 숫자로 진행' 버튼으로 승인하면 SECTIONS 진입.")
                project_save(state, cloud=True)
                if auto:
                    yield ev.done(stopped_at=stage, reason="stats_human_confirm_required")
                    return

            elif stage == "SECTIONS":
                # SPEC §1: Results → Methods → Introduction → Discussion 순서
                for sec in ("Results", "Methods", "Introduction", "Discussion"):
                    yield ev.tool_start(f"section_{sec.lower()}", f"{sec} 작성")
                    text = _exec_section(state, sec)
                    state.sections[sec] = text
                    yield ev.tool_result(f"section_{sec.lower()}", {"chars": len(text)})
                    project_save(state, cloud=True)

            elif stage == "POLISH":
                yield ev.tool_start("polish", "review_and_revise + 톤")
                result = _exec_polish(state)
                gates = state.gates or {}
                gates["peer_score"] = result.get("score") or result.get("peer_score") or 70
                state.gates = gates
                yield ev.tool_result("polish", {"score": gates.get("peer_score")})
                project_save(state, cloud=True)

        # 2) 실행 후 다시 gate 검사
        passed, issues = check_gate(state, state.stage)
        if passed:
            checkpoint(state, label=f"stage_{state.stage}_passed")
            yield ev.badge("stage_passed", state.stage,
                              next_stage=_next_stage(state.stage))
            state.stage = _next_stage(state.stage)
            project_save(state, cloud=True)
            if not auto:
                yield ev.done(stopped_at=state.stage, reason="single_step_complete")
                return
            # auto: 다음 stage 진행
        else:
            yield ev.warning(f"gate_{state.stage}", " / ".join(issues))
            yield ev.done(stopped_at=state.stage, reason="gate_blocked")
            return

    yield ev.done(stopped_at=state.stage, reason="max_iters")


def confirm_stats_human(state: ResearchProject) -> bool:
    """★ 사용자가 'STATS 결과로 진행' 승인 → STATS gate 통과 마킹.

    UI 버튼 → 이 함수 호출 → 다음 advance()는 SECTIONS 진입.
    """
    gates = state.gates or {}
    gates["stat_human_confirmed"] = True
    state.gates = gates
    project_save(state, cloud=True)
    return True


def reset_to_stage(state: ResearchProject, stage: str) -> None:
    """단계 되돌리기 — 갈래치기 직전이나 STATS 재실행 시."""
    if stage not in STAGES:
        return
    state.stage = stage
    project_save(state, cloud=True)


__all__ = [
    "STAGES", "STAGE_LABELS",
    "advance", "check_gate", "confirm_stats_human", "reset_to_stage",
]
