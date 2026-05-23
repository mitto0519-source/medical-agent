"""LLM Provider 건강도 추적 — 자동 검색 최적화 폴백.

사용자가 어떤 provider를 쓸지 고를 필요 없이, 시스템이 각 provider의
성공/실패를 학습해 '실제로 작동하는' provider를 자동 우선한다.

- 최근 실패한 provider는 쿨다운 동안 후순위로 (죽은 Claude를 매번 먼저 때리는 낭비 제거)
- 최근 성공한 provider를 우선
- 단, 전부 쿨다운이면 그래도 시도 (영구 차단 없음)

저장: data/diagnostics/llm_health.json (세션 간 유지)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PATH = Path("data/diagnostics/llm_health.json")
_COOLDOWN_SEC = 600  # 실패 후 10분간 후순위 (크레딧 소진/레이트리밋 회피)

# 품질 우선순위 (낮을수록 우선). seed/스타일/근거는 모든 LLM에 동일 주입되지만,
# 그 기준을 재현하는 문체·정밀도는 모델 급차가 있어 작동하는 것 중 고품질을 우선.
_QUALITY_RANK = {"anthropic": 0, "openai": 1, "google": 2}


def _load() -> Dict[str, dict]:
    if not _PATH.exists():
        return {}
    try:
        return json.loads(_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: Dict[str, dict]) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        _log.debug("llm_health 저장 실패: %s", e)


def record_success(provider: str) -> None:
    """provider 호출 성공 기록 — 우선순위 상승, 실패 카운트 리셋."""
    if not provider:
        return
    data = _load()
    e = data.get(provider, {})
    e["last_success"] = time.time()
    e["fail_count"] = 0
    e.pop("last_fail", None)
    e.pop("reason", None)
    data[provider] = e
    _save(data)


def record_failure(provider: str, reason: str = "") -> None:
    """provider 호출 실패 기록 — 쿨다운 진입."""
    if not provider:
        return
    data = _load()
    e = data.get(provider, {})
    e["last_fail"] = time.time()
    e["fail_count"] = e.get("fail_count", 0) + 1
    e["reason"] = (reason or "")[:120]
    data[provider] = e
    _save(data)


def order_by_health(providers: List[str]) -> List[str]:
    """가용 provider 목록을 건강도 기준으로 정렬해 반환.

    우선순위: 쿨다운 아닌 것 > 쿨다운인 것. 같은 그룹 내에선 최근 성공 우선.
    전부 쿨다운이면 원래(키) 순서 유지 — 그래도 전부 시도하게.
    """
    if not providers:
        return providers
    data = _load()
    now = time.time()

    def sort_key(p: str):
        e = data.get(p, {})
        last_fail = e.get("last_fail", 0)
        last_success = e.get("last_success", 0)
        fail_count = e.get("fail_count", 0)
        in_cooldown = (now - last_fail) < _COOLDOWN_SEC if last_fail else False
        # 1차: 쿨다운 여부(작동하는 것 먼저). 2차: 실패횟수.
        # 3차: 품질 우선순위(작동하는 것 중 고품질 모델 우선). 4차: 최근 성공.
        return (1 if in_cooldown else 0, fail_count, _QUALITY_RANK.get(p, 9), -last_success)

    ordered = sorted(providers, key=sort_key)
    if ordered != providers:
        _log.info("LLM 자동 최적화: provider 우선순위 %s → %s", providers, ordered)
    return ordered


def get_health_summary() -> Dict[str, dict]:
    """현재 건강도 상태 (UI/디버깅용)."""
    data = _load()
    now = time.time()
    summary = {}
    for p, e in data.items():
        last_fail = e.get("last_fail", 0)
        summary[p] = {
            "healthy": not ((now - last_fail) < _COOLDOWN_SEC if last_fail else False),
            "fail_count": e.get("fail_count", 0),
            "last_reason": e.get("reason", ""),
        }
    return summary
