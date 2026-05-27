"""Prompt A/B + bandit selector — versioned prompt 변종을 평가/선택.

`prompts/*.md`에 같은 name으로 v1.0.0 / v1.0.1 같이 두 변종이 있을 때 어느 쪽이
eval 점수가 높은지 자동 추적. epsilon-greedy bandit (단순)으로 산출.

저장: `data/diagnostics/prompt_ab.json`
  {"variant_id": {"trials": int, "wins": int, "score_sum": float}}

호출:
    from src.diagnostics.prompt_ab import pick_variant, report_outcome
    variant = pick_variant("yoosun_style", candidates=["v1.0.0", "v1.0.1"])
    # ... LLM 호출 + eval
    report_outcome("yoosun_style", variant, eval_score=0.92)
"""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_STATE = Path("data/diagnostics/prompt_ab.json")


def _load() -> dict:
    if _STATE.exists():
        try:
            return json.loads(_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(state: dict):
    _STATE.parent.mkdir(parents=True, exist_ok=True)
    _STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def pick_variant(prompt_name: str, candidates: List[str],
                  epsilon: float = 0.2) -> str:
    """epsilon-greedy 선택 — 확률 epsilon로 random 탐색, 아니면 최고 평균점 선택."""
    if not candidates:
        return ""
    state = _load().get(prompt_name, {})
    if random.random() < epsilon or not state:
        chosen = random.choice(candidates)
        _log.debug("prompt_ab explore %s → %s", prompt_name, chosen)
        return chosen
    # 평균 점수 최대인 후보
    best, best_avg = candidates[0], -1.0
    for c in candidates:
        s = state.get(c, {})
        trials = s.get("trials", 0)
        if trials == 0:
            return c   # 한 번도 시도 안한 후보 우선 (warm-up)
        avg = s.get("score_sum", 0.0) / trials
        if avg > best_avg:
            best, best_avg = c, avg
    return best


def report_outcome(prompt_name: str, variant: str, eval_score: float,
                    win: Optional[bool] = None):
    """variant 사용 후 결과 기록."""
    state = _load()
    bucket = state.setdefault(prompt_name, {}).setdefault(variant,
                {"trials": 0, "wins": 0, "score_sum": 0.0})
    bucket["trials"] = bucket.get("trials", 0) + 1
    bucket["score_sum"] = bucket.get("score_sum", 0.0) + float(eval_score)
    if win:
        bucket["wins"] = bucket.get("wins", 0) + 1
    _save(state)


def stats(prompt_name: Optional[str] = None) -> dict:
    """현재까지의 trial/win/avg 요약."""
    state = _load()
    if prompt_name:
        state = {prompt_name: state.get(prompt_name, {})}
    out: dict = {}
    for name, variants in state.items():
        out[name] = {}
        for v, b in variants.items():
            trials = b.get("trials", 0)
            out[name][v] = {"trials": trials,
                             "wins": b.get("wins", 0),
                             "avg_score": (b.get("score_sum", 0.0) / trials) if trials else 0.0}
    return out
