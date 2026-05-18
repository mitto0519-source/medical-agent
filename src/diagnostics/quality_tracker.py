"""Quality Tracker — 파이프라인 실행 품질 시계열 추적.

파이프라인 실행 후 자동으로 호출되어 RAG 점수, 주제 품질,
논문 품질 지표를 시계열로 저장하고 추세를 분석한다.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_FILE = Path("data/diagnostics/quality_history.json")
_MAX = 300


def record_run(pipeline_type: str, metrics: Dict) -> None:
    """파이프라인 실행 결과 기록.

    Args:
        pipeline_type: "rag_search" | "topic_gen" | "novelty" | "paper_write"
        metrics: 측정값 dict — score, word_count, novelty_score 등
    """
    entries = _load()
    entries.insert(0, {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "pipeline_type": pipeline_type,
        **{k: v for k, v in metrics.items() if isinstance(v, (int, float, str, bool))},
    })
    _save(entries)


def get_trend(pipeline_type: str, metric: str, days: int = 30) -> Dict:
    """특정 메트릭의 시간 추세 분석."""
    cutoff = datetime.now() - timedelta(days=days)
    entries = [
        e for e in _load()
        if e.get("pipeline_type") == pipeline_type
        and e.get(metric) is not None
        and _parse_ts(e.get("timestamp", "")) > cutoff
    ]
    if not entries:
        return {"trend": "no_data", "values": [], "n_samples": 0}
    values = [float(e[metric]) for e in entries if e.get(metric) is not None]
    if len(values) < 2:
        return {"trend": "insufficient", "values": values, "n_samples": len(values)}

    mid = max(1, len(values) // 2)
    recent_avg = sum(values[:mid]) / mid
    older_avg = sum(values[mid:]) / max(1, len(values) - mid)

    if recent_avg > older_avg * 1.05:
        trend = "improving"
    elif recent_avg < older_avg * 0.95:
        trend = "degrading"
    else:
        trend = "stable"

    return {
        "trend": trend,
        "recent_avg": round(recent_avg, 4),
        "older_avg": round(older_avg, 4),
        "values": values[:10],
        "n_samples": len(values),
    }


def get_summary(days: int = 7) -> Dict:
    """최근 N일 품질 요약."""
    cutoff = datetime.now() - timedelta(days=days)
    recent = [e for e in _load() if _parse_ts(e.get("timestamp", "")) > cutoff]
    by_type: Dict[str, List] = {}
    for e in recent:
        t = e.get("pipeline_type", "unknown")
        by_type.setdefault(t, []).append(e)
    return {
        "period_days": days,
        "total_runs": len(recent),
        "by_type": {t: len(v) for t, v in by_type.items()},
    }


def _parse_ts(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.min


def _load() -> List[Dict]:
    if not _FILE.exists():
        return []
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(entries: List[Dict]) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(
        json.dumps(entries[:_MAX], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
