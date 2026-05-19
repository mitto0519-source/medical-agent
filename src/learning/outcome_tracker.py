"""Signal 1: 아웃컴 기반 패턴 학습.

PeerReviewer 점수를 추적해 어떤 토픽/방법론이 높은 점수를 받는지 패턴을 추출.
데이터가 쌓일수록 confidence가 올라가는 구조.
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_HISTORY = Path("data/change_log/history.json")
_CACHE = Path("data/agent_self/outcome_insights.json")


def extract_insights() -> Dict:
    """history.json에서 peer_review + paper_write 기록을 분석해 패턴 추출."""
    if not _HISTORY.exists():
        return _empty()

    try:
        history = json.loads(_HISTORY.read_text(encoding="utf-8"))
    except Exception as e:
        _log.warning("history 로드 실패: %s", e)
        return _empty()

    # peer_review 기록에서 점수 수집
    scores_by_topic: Dict[str, List[float]] = defaultdict(list)
    scores_by_exposure: Dict[str, List[float]] = defaultdict(list)
    scores_by_domain: Dict[str, List[float]] = defaultdict(list)

    for entry in history:
        if entry.get("action_type") == "peer_review":
            outputs = entry.get("outputs", {})
            score = outputs.get("score")
            if score is None:
                continue
            score = float(score)
            topic = entry.get("inputs", {}).get("topic", "")
            # 토픽 키워드 분류
            for kw in ["수면", "sleep", "우울", "depression", "비만", "obesity",
                       "흡연", "smoking", "음주", "alcohol", "신체활동", "exercise",
                       "당뇨", "diabetes", "고혈압", "hypertension"]:
                if kw.lower() in topic.lower():
                    scores_by_domain[kw].append(score)
            scores_by_topic[topic[:40]].append(score)

    # 도메인별 평균 점수 계산
    domain_scores = {
        k: {"mean": sum(v) / len(v), "n": len(v)}
        for k, v in scores_by_domain.items()
        if len(v) > 0
    }
    high_domains = sorted(
        [(k, v["mean"], v["n"]) for k, v in domain_scores.items()],
        key=lambda x: x[1], reverse=True
    )

    # 인사이트 텍스트 생성
    insights = []
    total_papers = len([h for h in history if h.get("action_type") == "peer_review"])

    if high_domains:
        top = high_domains[:3]
        for domain, mean_score, n in top:
            if n >= 1:
                insights.append(
                    f"고성과 도메인 '{domain}': 평균 peer score {mean_score:.0f}/100 "
                    f"(n={n}). 이 주제 우선 추천."
                )
        if len(high_domains) > 3:
            low = high_domains[-2:]
            for domain, mean_score, n in low:
                insights.append(
                    f"저성과 도메인 '{domain}': 평균 {mean_score:.0f}/100 — "
                    f"방법론 보완 필요."
                )

    if total_papers == 0:
        insights.append("아직 peer review 데이터 없음 — 첫 논문 작성 후 패턴 학습 시작.")

    confidence = min(0.9, 0.3 + total_papers * 0.1)  # 논문 1편당 confidence +0.1

    result = {
        "source": "outcome_tracker",
        "insights": insights,
        "confidence": confidence,
        "data_volume": total_papers,
        "domain_scores": domain_scores,
    }
    _CACHE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    _log.info("[outcome] 패턴 추출 완료: %d개 인사이트, confidence=%.2f",
              len(insights), confidence)
    return result


def _empty() -> Dict:
    return {"source": "outcome_tracker", "insights": [], "confidence": 0.1,
            "data_volume": 0, "domain_scores": {}}
