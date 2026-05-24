"""자동학습 스케줄러 데몬 — 컨테이너에 상주하며 매일 1회 최신논문 학습 + 캐치업.

anacron 방식(중요): 정해진 시각이 아니라 '마지막 학습 후 경과시간'으로 판단한다.
  - 컨테이너 시작 시 즉시 체크 → 마지막 학습 후 24h 지났으면(또는 미실행) 바로 실행(캐치업).
  - 이후 1시간마다 재확인 → 24h 경과 시 실행.
  - PC가 꺼져 배치를 놓쳐도, PC 켜서 컨테이너가 뜨면 시작 즉시 캐치업된다.

docker-compose의 'learner' 서비스로 `restart: unless-stopped` 실행 → 앱 접속과 무관하게 자율 학습.
LLM-무관(PubMed 크롤링+임베딩+그래프)이라 쿼터 소진과 무관하게 작동.
"""
from __future__ import annotations

import io
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

INTERVAL_H = float(os.environ.get("LEARN_INTERVAL_H", "24"))   # 학습 주기(시간)
CHECK_EVERY_S = int(os.environ.get("LEARN_CHECK_EVERY_S", "3600"))  # 경과 재확인 간격(초)


def _hours_since_last() -> float:
    """마지막 학습 후 경과 시간(시간). 미실행이면 매우 큰 값(=즉시 실행)."""
    try:
        from src.knowledge.trend_learner import get_last_run_info
        lr = str(get_last_run_info().get("last_run", "")).strip()
    except Exception:
        return 1e9
    if not lr or lr in ("미실행", "오류"):
        return 1e9
    for parse in (
        lambda s: datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S"),
        lambda s: datetime.fromisoformat(s),
    ):
        try:
            return (datetime.now() - parse(lr)).total_seconds() / 3600.0
        except Exception:
            continue
    return 1e9


def main() -> int:
    from src.config.env import bootstrap
    bootstrap()
    from src.config.logging_config import get_logger
    log = get_logger("learn_scheduler")
    log.info("자동학습 스케줄러 시작 — 주기 %.0fh, 캐치업 ON, 확인주기 %ds", INTERVAL_H, CHECK_EVERY_S)

    from src.knowledge.trend_learner import run_trend_learn

    while True:
        try:
            h = _hours_since_last()
            if h >= INTERVAL_H:
                catchup = " (캐치업: 미실행/장기미실행)" if h > 1e8 else " (캐치업)"
                log.info("마지막 학습 %.1fh 전 → 최신논문 학습 실행%s",
                         h if h < 1e8 else -1, catchup if h >= INTERVAL_H else "")
                try:
                    s = run_trend_learn(days=60, max_per_query=30)
                    log.info("학습 완료: 신규 %s편, 그래프 %s→%s",
                             s.get("new_papers"), s.get("graph_nodes_before"), s.get("graph_nodes_after"))
                except Exception as e:
                    log.warning("학습 실행 실패(다음 주기 재시도): %s", str(e)[:200])
            else:
                log.info("다음 학습까지 %.1fh 남음 (마지막 %.1fh 전)", INTERVAL_H - h, h)
        except Exception as e:
            log.warning("스케줄러 사이클 오류(계속): %s", str(e)[:200])
        time.sleep(CHECK_EVERY_S)


if __name__ == "__main__":
    raise SystemExit(main())
