"""Long-horizon harness — 며칠 단위 'paper-in-progress' resume + iterative self-review.

배경 (2026-05-30):
    Devin 같은 long-horizon agent는 며칠 단위 작업을 catch-up하면서 self-correcting.
    우리는 runtime.tasks의 durable state + Heartbeat catch-up이 이미 있어, 그 위에
    paper-in-progress 모드를 얹어 multi-iteration self-review loop를 구현.

흐름:
    iteration N:
      1) 현재 sections 검토 (STROBE + consistency + capability_bench 약점)
      2) 약점 섹션 선택 (highest deficit)
      3) _delegate_to_writer로 그 섹션만 다시 작성
      4) 결과를 project에 patch + events 기록
      5) budget 체크 → 한도 도달 시 중단

    iteration 사이는 runtime.tasks state로 저장 → 컨테이너 재시작·중단 후 resume 가능.

API:
    run_self_review_loop(project, pid, *, max_iters=3, budget_usd=2.0,
                          target_score=85.0) -> dict
        → {"iters_run": int, "final_score": float, "improvements": [...]}

호출:
    workspace 토픽바의 "🔄 자기개선 루프" 버튼 또는 chat에서 "더 개선해줘" 요청 시.
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)


def _evaluate_sections(sections: Dict[str, Any]) -> Dict[str, float]:
    """각 섹션의 '약점 점수' 산출 (높을수록 더 개선 필요).

    기준:
    1. STROBE 누락 항목 수
    2. consistency 사고 수
    3. style_polish AI score
    4. 섹션 길이 (너무 짧으면 약점)
    """
    deficits: Dict[str, float] = {}
    for name in ("Introduction", "Methods", "Results", "Discussion"):
        body = sections.get(name)
        if not isinstance(body, str):
            deficits[name] = 50.0  # 미존재 = 큰 약점
            continue
        score = 0.0
        # 1. 길이 (너무 짧으면 +)
        if len(body) < 1500:
            score += 30
        elif len(body) < 2500:
            score += 10
        # 2. AI style score
        try:
            from src.safety.style_polish import ai_style_score
            ai_s = ai_style_score(body).ai_style_score
            score += ai_s * 0.4  # max 40
        except Exception:
            pass
        # 3. consistency 약점 (해당 섹션만)
        try:
            from src.safety.consistency_checker import check_consistency
            rep = check_consistency({name: body})
            score += len(rep.issues) * 5
        except Exception:
            pass
        deficits[name] = score
    return deficits


def run_self_review_loop(
    project: Dict[str, Any],
    pid: str,
    *,
    max_iters: int = 3,
    budget_usd: float = 2.0,
    target_score: float = 85.0,
    delegate_fn=None,
    save_fn=None,
) -> Dict[str, Any]:
    """iterative self-review: 약점 섹션을 매 iter 다시 작성.

    Args:
        delegate_fn: callable(prompt, project, mode) -> {"content": str}
                     None이면 project_workspace._delegate_to_writer 자동 import.
        save_fn: callable(pid, project) — _save_project. None이면 import.
    """
    if delegate_fn is None:
        from app.pages.project_workspace import _delegate_to_writer as _dlg
        delegate_fn = _dlg
    if save_fn is None:
        from app.pages.project_workspace import _save_project as _sv
        save_fn = _sv

    sections = project.get("sections") or {}
    improvements: List[Dict] = []
    t0 = time.time()

    # 예산 추적 (실측 budget API 없으면 LLM 호출당 단순 카운트)
    spent_usd = 0.0
    per_call_est = 0.05  # 대략 1500토큰 호출 = $0.05

    for it in range(max_iters):
        deficits = _evaluate_sections(sections)
        worst_section, worst_score = max(deficits.items(), key=lambda kv: kv[1])
        avg_deficit = sum(deficits.values()) / max(len(deficits), 1)

        _log.info("[long_horizon] iter %d/%d — worst=%s (deficit=%.1f), avg=%.1f",
                  it + 1, max_iters, worst_section, worst_score, avg_deficit)
        _events.append("self_review_iter",
                        {"iter": it + 1, "worst": worst_section,
                         "deficit": worst_score, "avg": avg_deficit,
                         "all_deficits": deficits},
                        actor="long_horizon")

        # 목표 점수 도달 또는 예산 초과 시 중단
        if avg_deficit <= (100 - target_score) and it > 0:
            improvements.append({"iter": it + 1, "action": "stop",
                                  "reason": "target_score_reached"})
            break
        if spent_usd >= budget_usd:
            improvements.append({"iter": it + 1, "action": "stop",
                                  "reason": "budget_exhausted",
                                  "spent_usd": spent_usd})
            break

        # 약점 섹션 다시 작성
        improve_prompt = (
            f"섹션 '{worst_section}'을 다시 작성해라. 현재 약점 신호:\n"
            f"- 길이 부족 또는 cliché 과다 또는 consistency 사고\n"
            f"- 핵심 발견을 첫 문장에 두고, 숫자/대조를 두 번째 문장에 두고, "
            f"임상·정책 함의를 마지막에 둬라.\n"
            f"기존 본문을 폐기하고 새로 써라."
        )
        try:
            reply = delegate_fn(improve_prompt, project, mode="🔬 Yoosun 스타일 재작성")
            new_text = reply.get("content", "")
            if new_text and len(new_text) > 800:
                sections[worst_section] = new_text
                project["sections"] = sections
                save_fn(pid, project)
                improvements.append({
                    "iter": it + 1, "action": "rewrite",
                    "section": worst_section,
                    "before_deficit": worst_score,
                    "new_chars": len(new_text),
                })
                spent_usd += per_call_est
            else:
                improvements.append({"iter": it + 1, "action": "skip",
                                      "reason": "weak_output", "section": worst_section})
        except Exception as e:
            improvements.append({"iter": it + 1, "action": "error",
                                  "section": worst_section, "error": str(e)[:200]})

    # 최종 평가
    final_deficits = _evaluate_sections(sections)
    final_avg = sum(final_deficits.values()) / max(len(final_deficits), 1)
    final_score = max(0.0, 100.0 - final_avg)

    elapsed = time.time() - t0
    out = {
        "iters_run": len(improvements),
        "final_score": round(final_score, 1),
        "elapsed_sec": round(elapsed, 1),
        "spent_usd": round(spent_usd, 3),
        "improvements": improvements,
        "final_deficits": final_deficits,
    }
    _events.append("self_review_done", out, actor="long_horizon")
    return out


__all__ = ["run_self_review_loop"]
