"""Longitudinal eval — 시계열 self-improvement 측정.

외부 진단 (2026-05-28): "지난달보다 실제로 agent가 좋아졌는가? 수치화 필요."

기존 `scripts/eval_benchmark.py`는 5축 단일 시점 측정. 본 모듈은:
  · 매 eval run 결과를 SQLite에 축적 (data/runtime/longitudinal.db)
  · trend 분석: metric별 7일/30일 이동평균, regression 검출
  · improvement_signal: 새 commit 후 점수가 떨어지면 events에 경고
  · capability_bench.get_improvement_context에 흡수되어 LLM이 trend 인지

호출:
    from src.diagnostics.longitudinal_eval import record_eval, trend, regression_alert
    record_eval(report_dict)        # eval_benchmark.py 끝에서 호출
    t = trend(metric="stat_zcb_aOR_within_0.05", days=30)
    alerts = regression_alert()     # 회귀 발생 metric 리스트
"""
from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DB = Path("data/runtime/longitudinal.db")


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS eval_runs(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        timestamp TEXT,
        pass_rate REAL,
        n_pass INTEGER,
        n_total INTEGER,
        git_sha TEXT,
        report_json TEXT
    )""")
    c.execute("""CREATE TABLE IF NOT EXISTS metric_points(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ts REAL NOT NULL,
        run_id INTEGER,
        metric TEXT NOT NULL,
        score REAL,
        threshold REAL,
        passed INTEGER,
        detail TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_metric_ts ON metric_points(metric, ts)")
    c.commit()
    return c


def _git_sha() -> str:
    try:
        import subprocess
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                            capture_output=True, text=True, timeout=3)
        return (r.stdout or "").strip()[:12]
    except Exception:
        return ""


def record_eval(report: Dict) -> int:
    """eval_benchmark JSON report → DB. run_id 반환.
    report = {"timestamp":..., "n_pass":..., "n_scored":..., "metrics": [...]}"""
    c = _conn()
    ts = time.time()
    pass_rate = float(report.get("pass_rate") or 0.0)
    cur = c.execute(
        "INSERT INTO eval_runs(ts, timestamp, pass_rate, n_pass, n_total, git_sha, report_json)"
        " VALUES (?,?,?,?,?,?,?)",
        (ts, report.get("timestamp", ""), pass_rate,
         int(report.get("n_pass") or 0), int(report.get("n_total") or 0),
         _git_sha(), json.dumps(report, ensure_ascii=False, default=str)[:50000]),
    )
    run_id = int(cur.lastrowid or 0)
    for m in report.get("metrics", []):
        c.execute(
            "INSERT INTO metric_points(ts, run_id, metric, score, threshold, passed, detail)"
            " VALUES (?,?,?,?,?,?,?)",
            (ts, run_id, m.get("name", ""),
             float(m.get("score") or 0.0) if m.get("score") is not None else None,
             float(m.get("threshold") or 0.0),
             1 if m.get("pass") is True else (0 if m.get("pass") is False else None),
             (m.get("detail") or "")[:500]),
        )
    c.commit()
    try:
        from src.runtime import events as _events
        _events.append("longitudinal_eval_recorded",
                        {"run_id": run_id, "pass_rate": pass_rate,
                         "n_metrics": len(report.get("metrics", []))},
                        actor="longitudinal_eval")
    except Exception:
        pass
    return run_id


def trend(metric: str, *, days: int = 30) -> Dict:
    """단일 metric의 시계열 + 이동평균 + slope."""
    c = _conn()
    cutoff = time.time() - days * 86400
    rows = c.execute(
        "SELECT ts, score FROM metric_points WHERE metric=? AND ts >= ? "
        "AND score IS NOT NULL ORDER BY ts ASC",
        (metric, cutoff)).fetchall()
    if not rows:
        return {"metric": metric, "n": 0, "trend": "no_data"}
    scores = [r[1] for r in rows]
    n = len(scores)
    # 단순 linear slope (x = index)
    if n >= 2:
        xs = list(range(n))
        x_mean = sum(xs) / n
        y_mean = sum(scores) / n
        num = sum((xs[i] - x_mean) * (scores[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den else 0.0
    else:
        slope = 0.0
    moving_7 = sum(scores[-7:]) / min(7, n)
    return {
        "metric": metric, "n": n, "days": days,
        "first": scores[0], "last": scores[-1],
        "moving_avg_7": round(moving_7, 4),
        "slope": round(slope, 6),
        "direction": "up" if slope > 0.001 else ("down" if slope < -0.001 else "flat"),
        "points": [{"ts": r[0], "score": r[1]} for r in rows[-20:]],
    }


def regression_alert(*, lookback: int = 5,
                      drop_threshold: float = 0.05) -> List[Dict]:
    """최근 N runs에서 score가 이전 평균보다 drop_threshold 이상 떨어진 metric."""
    c = _conn()
    metrics = c.execute(
        "SELECT DISTINCT metric FROM metric_points").fetchall()
    alerts: List[Dict] = []
    for (m,) in metrics:
        rows = c.execute(
            "SELECT score FROM metric_points WHERE metric=? AND score IS NOT NULL "
            "ORDER BY ts DESC LIMIT ?",
            (m, lookback)).fetchall()
        if len(rows) < 3:
            continue
        latest = rows[0][0]
        prev_avg = sum(r[0] for r in rows[1:]) / max(1, len(rows) - 1)
        drop = prev_avg - latest
        if drop >= drop_threshold:
            alerts.append({
                "metric": m, "latest": latest, "prev_avg": round(prev_avg, 4),
                "drop": round(drop, 4),
            })
            try:
                from src.runtime import events as _events
                _events.append("longitudinal_regression",
                                {"metric": m, "latest": latest,
                                 "prev_avg": prev_avg, "drop": drop},
                                actor="longitudinal_eval")
            except Exception:
                pass
    return alerts


def summary(*, days: int = 30) -> Dict:
    """전체 metric의 trend + alert 요약 — `/backlog` 페이지나 mcp에서."""
    c = _conn()
    cutoff = time.time() - days * 86400
    runs = c.execute(
        "SELECT COUNT(*), AVG(pass_rate) FROM eval_runs WHERE ts >= ?",
        (cutoff,)).fetchone()
    n_runs = int(runs[0] or 0)
    avg_pass = round(float(runs[1] or 0.0), 4)
    metrics = c.execute(
        "SELECT DISTINCT metric FROM metric_points WHERE ts >= ?",
        (cutoff,)).fetchall()
    trends = {m: trend(m, days=days) for (m,) in metrics}
    return {
        "days": days, "n_runs": n_runs, "avg_pass_rate": avg_pass,
        "n_metrics": len(metrics),
        "trends": trends,
        "alerts": regression_alert(),
    }


def improvement_context_block() -> str:
    """capability_bench.get_improvement_context에서 흡수할 텍스트."""
    s = summary(days=30)
    if not s["trends"]:
        return ""
    parts = ["# LONGITUDINAL EVAL (last 30d)"]
    parts.append(f"runs={s['n_runs']} · avg_pass_rate={s['avg_pass_rate']}")
    for name, t in list(s["trends"].items())[:8]:
        arrow = {"up": "↑", "down": "↓", "flat": "→"}.get(t.get("direction"), "?")
        parts.append(f"- {name}: {t.get('first','?'):.3f} → {t.get('last','?'):.3f} "
                      f"{arrow} (avg7={t.get('moving_avg_7')}) n={t.get('n')}")
    if s["alerts"]:
        parts.append("⚠️ REGRESSION ALERTS:")
        for a in s["alerts"]:
            parts.append(f"  - {a['metric']}: dropped {a['drop']:.3f} below prev avg")
    return "\n".join(parts)
