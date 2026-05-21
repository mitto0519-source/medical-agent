"""Phase A/B/C 실경로 통합 검증 스크립트.

smoke test로는 안 타는 deep_research=True / parallel=True 경로를 직접 호출해
실제로 동작하는지 검증한다. (LLM + NCBI API 사용 — smoke test와 동시 실행 금지)
"""
import io
import os
import pathlib
import sys

# Windows 콘솔(cp949)에서 유니코드 출력 보장
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

_root = pathlib.Path(__file__).resolve().parent.parent
os.chdir(_root)
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.research.research_pipeline import ResearchPipeline  # noqa: E402

TOPIC = {
    "title": "Adolescent smartphone overuse and sleep deprivation",
    "exposure": "smartphone overuse",
    "outcome": "sleep deprivation",
    "population": "Korean adolescents",
}
QUERY = "smartphone overuse sleep deprivation Korean adolescents"


def main():
    rp = ResearchPipeline()
    results = []

    # ── Phase B: 병렬 사전수집 (PMC 다운로드 + 신규성 동시) ──────────────────
    print("=" * 60)
    print("[Phase B] _parallel_pre_collect — AgentPool 병렬 실행")
    print("=" * 60)
    try:
        rp._parallel_pre_collect(QUERY, TOPIC)
        novelty_papers = getattr(rp, "_novelty_papers", [])
        ok_b = True  # 예외 없이 완료되면 통과 (내부 로그로 PMC/novelty 확인)
        print(f"  [PASS] Phase B 완료 — novelty 누적 논문 {len(novelty_papers)}편")
        results.append(("Phase B parallel", ok_b))
    except Exception as e:
        print(f"  [FAIL] Phase B: {e}")
        results.append(("Phase B parallel", False))

    # ── Phase A: 자율 연구 루프 (근거 컨텍스트 생성) ─────────────────────────
    print("=" * 60)
    print("[Phase A] _run_deep_research — AutonomousResearchLoop")
    print("=" * 60)
    try:
        ctx = rp._run_deep_research(TOPIC)
        ok_a = bool(ctx) and "AUTONOMOUS RESEARCH EVIDENCE" in ctx
        print(f"  [{'PASS' if ok_a else 'WARN'}] Phase A 근거 컨텍스트 {len(ctx)}자")
        if ctx:
            print("  ─ 미리보기:", ctx[:200].replace("\n", " "))
        results.append(("Phase A deep_research", ok_a))
    except Exception as e:
        print(f"  [FAIL] Phase A: {e}")
        results.append(("Phase A deep_research", False))

    # ── Phase C: 자기개선 컨텍스트 (루프 닫힘 확인) ───────────────────────────
    print("=" * 60)
    print("[Phase C] get_improvement_context — 자기개선 루프")
    print("=" * 60)
    try:
        from src.diagnostics.capability_bench import get_improvement_context
        ctx_c = get_improvement_context()
        # 누적된 약점이 있으면 내용 반환, 없으면 빈 문자열 (둘 다 정상)
        ok_c = isinstance(ctx_c, str)
        print(f"  [PASS] Phase C 함수 동작 — 현재 컨텍스트 {len(ctx_c)}자")
        if ctx_c:
            print("  ─ 미리보기:", ctx_c[:200].replace("\n", " "))
        results.append(("Phase C improvement_loop", ok_c))
    except Exception as e:
        print(f"  [FAIL] Phase C: {e}")
        results.append(("Phase C improvement_loop", False))

    # ── 결과 요약 ─────────────────────────────────────────────────────────────
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    for name, ok in results:
        print(f"  {'[PASS]' if ok else '[FAIL]'} {name}")
    print(f"  결과: {passed}/{len(results)} PASS")
    print("=" * 60)
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
