"""Self-bias Guard — writer↔critic 모델 다양성 강제.

LOOP_ENGINEERING_SPEC §2.2: 같은 글을 자기가 채점하면 후하게 매김
(Addy Osmani 사례: 동일 모델 self-eval 9.04 vs 독립 eval 7.43, 1.6점 격차).

Policy:
  - 정확히 같은 model      → 강한 warning + critic 모델 추천
  - 같은 family(Claude만)  → moderate warning + cross-family critic 추천
  - cross-family/provider   → OK

배선 위치: peer_reviewer.revise_with_critique 진입 + evolution.gate.run_gate.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


_FAMILY_MAP = {
    "anthropic": ("claude",),
    "openai": ("gpt", "openai"),
    "google": ("gemini", "google", "bison", "palm"),
    "openrouter": ("openrouter",),
}


def _detect_family(model: str) -> str:
    m = (model or "").lower()
    for fam, kws in _FAMILY_MAP.items():
        if any(k in m for k in kws):
            return fam
    return "unknown"


@dataclass
class BiasReport:
    severity: str            # "ok" | "moderate" | "strong"
    msg: str
    recommended_critic_provider: Optional[str] = None
    recommended_critic_task: Optional[str] = None
    allow_proceed: bool = True


def warn_if_self_review(writer_model: str, critic_model: str,
                          *, strict_mode: bool = False) -> BiasReport:
    """writer ↔ critic 다양성 평가.

    strict_mode=True (의료 권장): 동일 model이면 차단 (allow_proceed=False).
    """
    if not writer_model or not critic_model:
        return BiasReport("ok", "model info missing — skipped")
    wm = (writer_model or "").lower()
    cm = (critic_model or "").lower()
    wf = _detect_family(wm)
    cf = _detect_family(cm)

    if wm == cm:
        return BiasReport(
            severity="strong",
            msg=(f"writer == critic ({writer_model}) — self-bias 위험 매우 큼. "
                  f"Addy 사례 9.04 vs 7.43 (1.6점 격차). cross-family critic 권장."),
            recommended_critic_provider=("openai" if wf == "anthropic" else "anthropic"),
            recommended_critic_task="critic_review",
            allow_proceed=not strict_mode,
        )
    if wf == cf and wf != "unknown":
        return BiasReport(
            severity="moderate",
            msg=(f"writer/critic 모두 {wf} family — 같은 학습 분포로 self-bias 잔재. "
                  f"다른 provider critic 권장."),
            recommended_critic_provider=("openai" if wf == "anthropic" else "anthropic"),
            recommended_critic_task="critic_review",
            allow_proceed=True,
        )
    return BiasReport(
        severity="ok",
        msg=f"cross-family critic ({wf} writer / {cf} critic) — bias 차단 OK",
        allow_proceed=True,
    )


def select_critic_for(writer_model: str, *, prefer_premium: bool = True) -> dict:
    """writer 모델 받아 critic용 추천 (provider/task tier) 반환."""
    wf = _detect_family(writer_model)
    # cross-family default
    if wf == "anthropic":
        return {"provider": "openai", "task": "critic_review", "reason": "cross-family"}
    if wf == "openai":
        return {"provider": "anthropic", "task": "critic_review", "reason": "cross-family"}
    if wf == "google":
        return {"provider": "anthropic", "task": "critic_review", "reason": "cross-family"}
    return {"provider": "anthropic", "task": "critic_review", "reason": "default"}


__all__ = ["BiasReport", "warn_if_self_review", "select_critic_for"]
