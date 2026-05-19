"""자율 학습 사이클 — Task Scheduler에서 주 1회 자동 실행.

순서:
  1. PubMed 신규 논문 수집 (periodic_learn)
  2. 3개 신호 학습 + 가중치 통합 (MetaLearner)
  3. self_model 갱신
  4. 결과 기록
"""
from __future__ import annotations

import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from src.config.env import bootstrap
bootstrap()

from src.config.logging_config import get_logger
_log = get_logger("learning_cycle")


def main():
    print("=" * 60)
    print("Medical-Agent 자율 학습 사이클 시작")
    print("=" * 60)

    # Step 1: PubMed 수집
    print("\n[1/3] PubMed 논문 수집...")
    try:
        from src.knowledge.trend_learner import run_trend_learn
        summary = run_trend_learn(days=30, max_per_query=20)
        print(f"  신규 {summary.get('new_papers', 0)}편 수집, "
              f"RAG {summary.get('rag_ingested', 0)}편 인제스트")
    except Exception as e:
        print(f"  수집 실패 (계속 진행): {e}")

    # Step 2: MetaLearner 통합 사이클
    print("\n[2/3] 3-Signal MetaLearner 통합...")
    try:
        from src.learning.meta_learner import MetaLearner
        ml = MetaLearner()
        result = ml.run_cycle()
        weights = result.get("cycle_weights", {})
        print(f"  통합 완료: {len(result.get('top_insights', []))}개 인사이트")
        print(f"  가중치 — "
              f"OutcomeTracker: {weights.get('outcome_tracker', 0):.0%} | "
              f"KnowledgeDistiller: {weights.get('knowledge_distiller', 0):.0%} | "
              f"FineTuner: {weights.get('finetune_manager', 0):.0%}")
        # 주요 인사이트 출력
        for item in result.get("top_insights", [])[:3]:
            print(f"  [{item['source'][:10]}] {item['text'][:80]}")
    except Exception as e:
        print(f"  MetaLearner 실패: {e}")
        _log.exception("[cycle] MetaLearner 오류")

    # Step 3: self_model 갱신
    print("\n[3/3] Self-model 갱신...")
    try:
        from src.memory.self_model import refresh
        model = refresh()
        print(f"  건강도: {model.overall_score}/100")
    except Exception as e:
        print(f"  갱신 실패: {e}")

    print("\n" + "=" * 60)
    print("사이클 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
