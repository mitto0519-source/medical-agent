"""Integrated audit for the 5 production-readiness layers.

  P1 Reproducibility   — provenance fingerprints 적재 비율 + 최근 LLM 호출에서 prompt_sha 누락 여부
  P2 Safety            — safety.check_all 호출 events vs LLM 출력 events (호출률)
  P3 Observability     — span_start/end 비율 + latency 분포
  P4 Stats determinism — analysis_plan_registered vs analysis_plan_violation 비율
  P5 Memory lifecycle  — items DB 건수 + tick 최근 결과 + memory_write events 대비 lifecycle register 비율

수동 실행:
    python scripts/audit_5_layers.py           # 사람 친화 표
    python scripts/audit_5_layers.py --json    # JSON 출력 (CI 양식)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
from pathlib import Path

os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.config.env import bootstrap
bootstrap()


def _safe_count(fn, *args, **kwargs) -> int:
    try:
        return len(fn(*args, **kwargs) or [])
    except Exception:
        return 0


def audit_p1_reproducibility(since_hours: int = 24) -> dict:
    from src.runtime import events as _ev
    from src.runtime import provenance as _prov  # noqa
    since = time.time() - since_hours * 3600
    prov = _ev.find(type="provenance", since_ts=since, limit=500)
    llm = [e for e in _ev.find(type="span_end", since_ts=since, limit=500)
           if (e.get("payload") or {}).get("name", "").startswith("llm.")]
    # prompt_sha 누락된 provenance
    missing = [e for e in prov
               if not (e.get("payload") or {}).get("prompt_sha")
               and (e.get("payload") or {}).get("scope") == "llm_call"]
    out = {
        "since_hours": since_hours,
        "provenance_events": len(prov),
        "llm_span_events": len(llm),
        "coverage_ratio": round(len(prov) / max(len(llm), 1), 3),
        "missing_prompt_sha": len(missing),
        "status": "ok" if len(prov) >= len(llm) * 0.5 else "warn",
    }
    return out


def audit_p2_safety(since_hours: int = 24) -> dict:
    from src.runtime import events as _ev
    since = time.time() - since_hours * 3600
    safety_events = _ev.find(type="safety.check_all.warn", since_ts=since, limit=200) + \
                    _ev.find(type="safety.check_all.fail", since_ts=since, limit=200)
    # gate별 fail/warn
    by_gate: dict[str, int] = {}
    for gate_name in ("citation_grounding", "consistency", "causal_claims",
                       "physician_review", "figure_validator"):
        for sev in ("warn", "fail"):
            n = _safe_count(_ev.find, type=f"safety.{gate_name}.{sev}", since_ts=since)
            if n:
                by_gate[f"{gate_name}.{sev}"] = n
    # LLM 출력 events 대비 safety 호출률 (정확 측정은 어렵고 근사)
    llm_spans = [e for e in _ev.find(type="span_end", since_ts=since, limit=500)
                 if (e.get("payload") or {}).get("name", "") in
                 ("llm.anthropic.generate", "llm.openai.generate", "llm.google.generate")]
    coverage = round(len(safety_events) / max(len(llm_spans), 1), 3) if llm_spans else None
    out = {
        "since_hours": since_hours,
        "safety_total_events": len(safety_events),
        "by_gate": by_gate,
        "llm_outputs_seen": len(llm_spans),
        "approx_call_ratio": coverage,
        "status": "ok" if llm_spans and len(safety_events) >= len(llm_spans) * 0.2 else "warn",
    }
    return out


def audit_p3_observability(since_hours: int = 24) -> dict:
    from src.runtime import events as _ev
    since = time.time() - since_hours * 3600
    starts = _ev.find(type="span_start", since_ts=since, limit=1000)
    ends = _ev.find(type="span_end", since_ts=since, limit=1000)
    # latency 분포 (ms)
    lats = sorted(int((e.get("payload") or {}).get("latency_ms", 0) or 0) for e in ends)
    if lats:
        p50 = lats[len(lats) // 2]
        p95 = lats[min(int(len(lats) * 0.95), len(lats) - 1)]
        p99 = lats[min(int(len(lats) * 0.99), len(lats) - 1)]
    else:
        p50 = p95 = p99 = 0
    # error spans
    errs = sum(1 for e in ends if (e.get("payload") or {}).get("status") == "error")
    out = {
        "since_hours": since_hours,
        "span_start": len(starts), "span_end": len(ends),
        "orphaned_starts": max(0, len(starts) - len(ends)),
        "latency_ms_p50": p50, "latency_ms_p95": p95, "latency_ms_p99": p99,
        "error_spans": errs,
        "status": "ok" if abs(len(starts) - len(ends)) < max(2, len(starts) // 20) else "warn",
    }
    return out


def audit_p4_stats_determinism(since_hours: int = 24 * 30) -> dict:
    from src.runtime import events as _ev
    since = time.time() - since_hours * 3600
    reg = _ev.find(type="analysis_plan_registered", since_ts=since, limit=200)
    vio = _ev.find(type="analysis_plan_violation", since_ts=since, limit=200)
    res = _ev.find(type="analysis_plan_result", since_ts=since, limit=200)
    out = {
        "since_hours": since_hours,
        "registered": len(reg),
        "violations": len(vio),
        "results_linked": len(res),
        "violation_rate": round(len(vio) / max(len(reg), 1), 3),
        "status": "ok" if len(vio) == 0 else ("warn" if len(vio) <= 2 else "fail"),
    }
    return out


def audit_p5_memory_lifecycle(since_hours: int = 24) -> dict:
    from src.runtime import events as _ev
    since = time.time() - since_hours * 3600
    try:
        from src.memory.lifecycle import stats as lc_stats
        lc = lc_stats()
    except Exception as e:
        lc = {"error": str(e)[:120]}
    writes = _ev.find(type="memory_write", since_ts=since, limit=500)
    quarantined = _ev.find(type="memory_quarantined", since_ts=since, limit=500)
    rejected = _ev.find(type="memory_rejected", since_ts=since, limit=500)
    ticks = _ev.find(type="lifecycle_tick", since_ts=since * 0 + (time.time() - 7 * 86400), limit=10)
    # 가장 최근 tick 결과
    last_tick = (ticks[0] if ticks else {}).get("payload") if ticks else None
    out = {
        "since_hours": since_hours,
        "lifecycle_db": lc,
        "memory_writes": len(writes),
        "quarantined": len(quarantined),
        "rejected": len(rejected),
        "last_tick_within_7d": last_tick,
        "status": (
            "warn" if lc.get("items", 0) == 0 and len(writes) > 0
            else "ok"
        ),
    }
    return out


def _print_table(report: dict) -> None:
    print("=" * 72)
    print(f"  5-LAYER AUDIT  ({report['ts']})")
    print("=" * 72)
    for layer in ("P1_reproducibility", "P2_safety", "P3_observability",
                  "P4_stats_determinism", "P5_memory_lifecycle"):
        d = report[layer]
        status = d.get("status", "?")
        flag = {"ok": "✓", "warn": "△", "fail": "✗"}.get(status, "?")
        print(f"\n[{flag}] {layer.replace('_', ' ').upper()}  ({status})")
        for k, v in d.items():
            if k == "status":
                continue
            if isinstance(v, dict):
                print(f"    {k}:")
                for kk, vv in v.items():
                    print(f"        {kk}: {vv}")
            else:
                print(f"    {k}: {v}")
    print()
    print("=" * 72)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    args = ap.parse_args()
    report = {
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "since_hours": args.hours,
        "P1_reproducibility": audit_p1_reproducibility(args.hours),
        "P2_safety": audit_p2_safety(args.hours),
        "P3_observability": audit_p3_observability(args.hours),
        "P4_stats_determinism": audit_p4_stats_determinism(),
        "P5_memory_lifecycle": audit_p5_memory_lifecycle(args.hours),
    }
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
    else:
        _print_table(report)
    # 종료 코드 — 한 layer라도 fail이면 1
    if any(r.get("status") == "fail" for k, r in report.items() if isinstance(r, dict)):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
