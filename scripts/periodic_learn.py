"""주기적 학습 실행 스크립트 — 단독 실행 또는 스케줄러에서 호출.

사용법:
  python scripts/periodic_learn.py              # 기본 (60일, 쿼리당 30편)
  python scripts/periodic_learn.py --days 30    # 최근 30일
  python scripts/periodic_learn.py --dry-run    # 수집 수 확인만 (인제스트 없음)
  python scripts/periodic_learn.py --status     # 마지막 실행 정보만 출력

Windows Task Scheduler 설정 예시 (매일 오전 3시):
  트리거: 매일 03:00
  동작: python "C:\\path\\to\\scripts\\periodic_learn.py"
  시작 위치: C:\\path\\to\\Medical-Agent

Railway Cron (railway.toml 추가 예시):
  [[cronjobs]]
  schedule = "0 3 * * *"
  command = "python scripts/periodic_learn.py"
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def main():
    parser = argparse.ArgumentParser(description="Medical-Agent 주기적 학습 실행")
    parser.add_argument("--days", type=int, default=60,
                        help="PubMed 최근 N일 논문 수집 (기본 60)")
    parser.add_argument("--max-per-query", type=int, default=30,
                        help="쿼리당 최대 논문 수 (기본 30)")
    parser.add_argument("--dry-run", action="store_true",
                        help="수집 수 확인만 (DB 변경 없음)")
    parser.add_argument("--status", action="store_true",
                        help="마지막 실행 정보 출력 후 종료")
    args = parser.parse_args()

    from src.config.env import bootstrap
    bootstrap()

    if args.status:
        from src.knowledge.trend_learner import get_last_run_info
        info = get_last_run_info()
        print("=== 주기적 학습 상태 ===")
        print(f"마지막 실행: {info['last_run']}")
        print(f"총 실행 횟수: {info['run_count']}회")
        print(f"누적 수집 논문: {info['ingested_count']}편")
        return

    if args.dry_run:
        print("=== Dry-run 모드 — 수집 수만 확인 ===")
        from src.knowledge.medical_ontology import get_ontology
        from src.knowledge.trend_learner import _search_pmids
        from datetime import datetime, timedelta
        ontology = get_ontology()
        queries = ontology.pubmed_queries_for_dataset("KYRBS")[:3]
        total = 0
        for q in queries:
            pmids = _search_pmids(q, days=args.days, max_results=args.max_per_query)
            print(f"  [{len(pmids):3d}편] {q[:70]}")
            total += len(pmids)
        print(f"총 예상 수집: ~{total}편 (중복 포함)")
        return

    print("=== Medical-Agent 주기적 학습 시작 ===")
    from src.knowledge.trend_learner import run_trend_learn
    summary = run_trend_learn(days=args.days, max_per_query=args.max_per_query)

    print()
    print("=== 실행 완료 ===")
    print(f"신규 논문 수집:  {summary['new_papers']}편")
    print(f"중복 스킵:       {summary['skipped_papers']}편")
    print(f"개념 추출:       {summary['concepts_extracted']}건")
    print(f"그래프 노드:     {summary['graph_nodes_before']} → {summary['graph_nodes_after']}")
    print(f"RAG 인제스트:    {summary.get('rag_ingested', 0)}편")
    if summary.get("errors"):
        print(f"오류: {summary['errors']}")


if __name__ == "__main__":
    main()
