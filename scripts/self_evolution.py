"""자가 진단 + 자동 개선 CLI 실행기.

사용법:
    python scripts/self_evolution.py            # 전체 진단 (LLM 평가 포함)
    python scripts/self_evolution.py --quick    # 빠른 진단 (LLM 평가 제외)
    python scripts/self_evolution.py --report   # 마지막 진단 결과 출력
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Windows cp949 환경에서 한국어/이모지 출력 보장
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf-8-sig"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.config.env import bootstrap
bootstrap()

from src.config.logging_config import get_logger
_log = get_logger("self_evolution")


def run_audit(quick: bool = False) -> None:
    from src.diagnostics.self_auditor import SelfAuditor
    from src.diagnostics.improvement_engine import ImprovementEngine

    print("=" * 60)
    print("  Medical-Agent 자가 진단 + 자동 개선")
    print(f"  모드: {'빠른 진단' if quick else '전체 진단 (LLM 평가 포함)'}")
    print("=" * 60)

    auditor = SelfAuditor()
    print("\n[1/2] 자가 진단 실행 중...")
    result = auditor.run_quick_audit() if quick else auditor.run_full_audit()

    print(f"\n  종합 점수: {result.overall_score}/100")
    print(f"  소요 시간: {result.duration_sec:.1f}초")

    if result.code_issues:
        high = [i for i in result.code_issues if i["severity"] == "high"]
        med = [i for i in result.code_issues if i["severity"] == "medium"]
        print(f"\n  코드 이슈: high={len(high)}, medium={len(med)}")
        for issue in high[:5]:
            print(f"    ⚠ [{issue['type']}] {issue['file']} L{issue['line']}")

    rag = result.rag_health
    print(f"\n  RAG 상태: {rag.get('status')} (docs={rag.get('doc_count')}, avg_dist={rag.get('avg_score')})")

    llm = result.llm_health
    print(f"  LLM 상태: {llm.get('status')} ({llm.get('response_ms')}ms)")

    if result.llm_gaps:
        print(f"\n  아키텍처 갭 ({len(result.llm_gaps)}개 발견):")
        for gap in result.llm_gaps[:3]:
            auto_label = "AUTO" if gap.get("auto") else "MANUAL"
            print(f"    [{auto_label}] P{gap.get('priority',0)}: {gap.get('gap','')[:70]}")

    print("\n[2/2] 자동 개선 실행 중...")
    engine = ImprovementEngine()
    improvements = engine.run(result.to_dict())
    auto_applied = improvements.get("auto_applied", [])
    queued = improvements.get("queued_count", 0)

    print(f"\n  자동 적용: {len(auto_applied)}건")
    for label in auto_applied:
        print(f"    ✅ {label}")
    if queued:
        print(f"  승인 대기: {queued}건 — UI에서 확인 가능")

    print("\n✅ 자가 진단 + 개선 완료")
    print(f"   결과 저장: data/diagnostics/audit_log.json")


def show_report() -> None:
    from src.diagnostics.self_auditor import get_last_audit, get_audit_history

    last = get_last_audit()
    if not last:
        print("진단 이력 없음 — 먼저 자가 진단을 실행하세요.")
        return

    history = get_audit_history(5)
    scores = [h["overall_score"] for h in history]

    print("=" * 60)
    print("  마지막 자가 진단 결과")
    print("=" * 60)
    print(f"  시간: {last['timestamp']}")
    print(f"  점수: {last['overall_score']}/100")
    if len(scores) > 1:
        trend = "↑" if scores[0] > scores[-1] else "↓" if scores[0] < scores[-1] else "→"
        print(f"  추세: {scores[0]} {trend} (이전 {scores[-1]})")

    rag = last.get("rag_health", {})
    print(f"\n  RAG: {rag.get('status')} | docs={rag.get('doc_count')} | avg_dist={rag.get('avg_score')}")

    issues = last.get("code_issues", [])
    high = [i for i in issues if i.get("severity") == "high"]
    print(f"  코드이슈: {len(issues)}건 (high={len(high)})")

    gaps = last.get("llm_gaps", [])
    print(f"  아키텍처 갭: {len(gaps)}건")
    for g in gaps[:3]:
        print(f"    P{g.get('priority',0)}: {g.get('gap','')[:60]}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Medical-Agent 자가 진단 + 자동 개선")
    parser.add_argument("--quick", action="store_true", help="빠른 진단 (LLM 평가 제외)")
    parser.add_argument("--report", action="store_true", help="마지막 진단 결과만 출력")
    args = parser.parse_args()

    if args.report:
        show_report()
    else:
        run_audit(quick=args.quick)
