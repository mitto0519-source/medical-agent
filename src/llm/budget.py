"""Reasoning Budget — LLM 호출 비용/토큰 한도 + 자동 다운그레이드.

원본: events에 기록된 llm_call 이벤트를 집계해 일/주 사용량 산출.
한도 도달 시: factory.get_llm_client에 'recommended_provider(task)' 를 통해
   더 저렴한 provider(예: opus → sonnet → gemini-flash)로 자동 라우팅.

비용 모델은 보수적 추정치 (model_costs.py 환경변수로 재정의 가능).

API:
  record(provider, model, tokens_in, tokens_out)   # 또는 자동: events.append('llm_call', ...)로 누적
  usage(window="day"|"week") -> {tokens, cost_usd, by_provider}
  remaining(window="day") -> {tokens_pct, cost_pct}
  recommended_provider(task, requested_provider=None) -> str
  set_caps(day_cost_usd=..., week_cost_usd=...)

저장: data/runtime/budget_state.json (caps 영속, 일/주 슬롯)
"""
from __future__ import annotations

import json
import os
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)
_STATE_PATH = Path(os.environ.get("RUNTIME_DB_DIR", "data/runtime")) / "budget_state.json"
_LOCK = threading.Lock()


# 모델별 1M 토큰당 USD (input, output) — 보수적 추정. 환경변수로 재정의 가능.
_DEFAULT_PRICES: dict[str, tuple[float, float]] = {
    # Anthropic Claude (최신 우선)
    "claude-opus-4-8": (15.0, 75.0),
    "claude-opus-4-7": (15.0, 75.0),
    "claude-opus-4-6": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    # OpenAI (대략)
    "gpt-4o": (2.5, 10.0),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-5": (3.0, 15.0),
    # Google Gemini
    "gemini-flash-latest": (0.0, 0.0),       # 무료 티어 한도 내
    "gemini-2.5-flash": (0.0, 0.0),
    "gemini-2.5-flash-lite": (0.0, 0.0),
    "gemini-flash-lite-latest": (0.0, 0.0),
    "gemini-1.5-pro": (1.25, 5.0),
    # Mock
    "mock": (0.0, 0.0),
}

_DEFAULT_CAPS = {
    "day_cost_usd": float(os.environ.get("LLM_BUDGET_DAY_USD", "10.0")),
    "week_cost_usd": float(os.environ.get("LLM_BUDGET_WEEK_USD", "50.0")),
}


def _load_state() -> dict:
    if _STATE_PATH.exists():
        try: return json.loads(_STATE_PATH.read_text(encoding="utf-8"))
        except Exception: pass
    return {"caps": dict(_DEFAULT_CAPS), "prices": {}}


def _save_state(state: dict) -> None:
    _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _price_for(model: str) -> tuple[float, float]:
    state = _load_state()
    override = state.get("prices", {}).get(model)
    if override:
        return tuple(override)  # type: ignore
    # exact 매치 후 prefix fallback
    if model in _DEFAULT_PRICES:
        return _DEFAULT_PRICES[model]
    for k, v in _DEFAULT_PRICES.items():
        if model.startswith(k.split("-")[0]):  # claude/gpt/gemini family
            return v
    return (1.0, 5.0)  # 알 수 없으면 보수적


def set_caps(day_cost_usd: float | None = None, week_cost_usd: float | None = None) -> dict:
    with _LOCK:
        st = _load_state()
        st.setdefault("caps", dict(_DEFAULT_CAPS))
        if day_cost_usd is not None: st["caps"]["day_cost_usd"] = float(day_cost_usd)
        if week_cost_usd is not None: st["caps"]["week_cost_usd"] = float(week_cost_usd)
        _save_state(st)
        return st["caps"]


def caps() -> dict:
    return _load_state().get("caps", dict(_DEFAULT_CAPS))


def record(provider: str, model: str, tokens_in: int = 0, tokens_out: int = 0,
           task: str | None = None, success: bool = True,
           latency_ms: int | None = None) -> dict:
    """LLM 호출 결과 기록. events에 audit 항목으로 누적 (집계는 events에서).

    latency_ms 도 함께 기록하면 `latency_summary()`에서 p50/p95 산출.
    """
    p_in, p_out = _price_for(model)
    cost = (tokens_in * p_in + tokens_out * p_out) / 1_000_000.0
    payload = {"provider": provider, "model": model, "tokens_in": tokens_in,
               "tokens_out": tokens_out, "cost_usd": round(cost, 6),
               "task": task, "success": success}
    if latency_ms is not None:
        payload["latency_ms"] = int(latency_ms)
    _events.append("llm_usage", payload, actor=f"llm:{provider}")
    return payload


def _window_since(window: str) -> float:
    now = datetime.utcnow()
    if window == "day":
        start = datetime(now.year, now.month, now.day)
    elif window == "week":
        start = now - timedelta(days=now.weekday())
        start = datetime(start.year, start.month, start.day)
    else:
        start = now - timedelta(hours=1)
    return start.timestamp()


def usage(window: str = "day") -> dict:
    since = _window_since(window)
    rows = _events.find(type="llm_usage", since_ts=since, limit=10000)
    by_p: dict[str, dict] = {}
    total_cost = 0.0; total_in = 0; total_out = 0
    for r in rows:
        pl = r.get("payload") or {}
        prov = pl.get("provider", "?")
        d = by_p.setdefault(prov, {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0})
        d["calls"] += 1
        d["tokens_in"] += int(pl.get("tokens_in") or 0)
        d["tokens_out"] += int(pl.get("tokens_out") or 0)
        d["cost_usd"] += float(pl.get("cost_usd") or 0.0)
        total_in += int(pl.get("tokens_in") or 0)
        total_out += int(pl.get("tokens_out") or 0)
        total_cost += float(pl.get("cost_usd") or 0.0)
    return {"window": window, "calls": sum(p["calls"] for p in by_p.values()),
            "tokens_in": total_in, "tokens_out": total_out,
            "cost_usd": round(total_cost, 4), "by_provider": by_p}


def remaining(window: str = "day") -> dict:
    u = usage(window); c = caps()
    cap_cost = c.get(f"{window}_cost_usd", _DEFAULT_CAPS[f"{window}_cost_usd"])
    used = u["cost_usd"]; left = max(0.0, cap_cost - used)
    return {"window": window, "cap_cost_usd": cap_cost, "used_cost_usd": used,
            "left_cost_usd": round(left, 4),
            "pct_used": round((used / cap_cost * 100) if cap_cost else 0, 1)}


# task별 선호 provider 순위 (정상 시)
_PREFER: dict[str, list[str]] = {
    "paper_writing": ["anthropic", "openai", "google"],
    "qa":            ["anthropic", "openai", "google"],
    "fast":          ["google", "anthropic", "openai"],
    "summary":       ["anthropic", "openai", "google"],
    "ocr":           ["openai", "google", "anthropic"],
    "standard":      ["anthropic", "openai", "google"],
}


def recommended_provider(task: str = "standard", requested: str | None = None) -> dict:
    """예산 사용률 보고 다운그레이드 의사결정.
    pct_used < 80 → 요청대로(또는 task 기본).
    80~100 → google(무료) 우선.
    100+ → google 강제 + 경고 이벤트.
    """
    r = remaining("day")
    pct = r["pct_used"]
    pref = _PREFER.get(task, _PREFER["standard"])
    chosen = requested or pref[0]
    reason = "default"
    if pct >= 100:
        chosen = "google"; reason = "budget_exhausted"
        _events.append("budget_exhausted", {"task": task, "pct": pct}, actor="budget")
    elif pct >= 80:
        if chosen not in ("google",):
            chosen = "google"; reason = "budget_warning_downgrade"
            _events.append("budget_downgrade", {"task": task, "from": requested or pref[0], "to": "google", "pct": pct}, actor="budget")
    return {"provider": chosen, "reason": reason, "pct_used": pct,
            "left_cost_usd": r["left_cost_usd"]}


def snapshot() -> dict:
    """heartbeat에서 정기 호출용 — 일/주 사용 + remaining 한 번에."""
    return {
        "day": {**usage("day"), **remaining("day")},
        "week": {**usage("week"), **remaining("week")},
        "caps": caps(),
        "latency": latency_summary("day"),
    }


def latency_summary(window: str = "day") -> dict:
    """provider별 p50/p95/max latency (ms) — events.llm_usage의 latency_ms 집계."""
    since = _window_since(window)
    rows = _events.find(type="llm_usage", since_ts=since, limit=10000)
    by_p: dict[str, list[int]] = {}
    for r in rows:
        pl = r.get("payload") or {}
        lat = pl.get("latency_ms")
        if lat is None:
            continue
        by_p.setdefault(pl.get("provider", "?"), []).append(int(lat))
    out: dict[str, dict] = {}
    for prov, lats in by_p.items():
        if not lats:
            continue
        lats_sorted = sorted(lats)
        n = len(lats_sorted)
        def _pct(p: float) -> int:
            idx = max(0, min(n - 1, int(p * n / 100)))
            return lats_sorted[idx]
        out[prov] = {"n": n, "p50_ms": _pct(50), "p95_ms": _pct(95),
                     "max_ms": lats_sorted[-1], "mean_ms": int(sum(lats_sorted) / n)}
    return {"window": window, "by_provider": out}
