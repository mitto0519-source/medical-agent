"""E2E 자가 진단 — LLM 크레딧 무관 전수 점검 (루틴화).

크레딧이 0이어도 시스템 무결성을 확인하는 결정적 진단:
  1. src.* 전 모듈 import 전수 (깨진 연결/고아 import 탐지)
  2. self_auditor 빠른 진단
  3. self_model 건강도 갱신
  4. 핵심 신규 모듈 심볼 존재 확인 (이번 세션들 산출물)

사용: python scripts/e2e_diagnose.py
결과: 콘솔 + data/diagnostics/e2e_diag_report.txt
"""
import io
import os
import pathlib
import sys

_root = pathlib.Path(__file__).resolve().parent.parent
os.chdir(_root)
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

report = []


def line(s=""):
    report.append(str(s))
    print(s)


def main():
    line("=" * 60)
    line("  E2E 자가 진단 (LLM 무관)")
    line("=" * 60)

    # ── 1. import 전수 ──────────────────────────────────────────────
    line("\n[1] src.* 전 모듈 import 전수")
    import importlib
    import pkgutil
    import src
    broken = []
    total = 0
    for m in pkgutil.walk_packages(src.__path__, "src."):
        total += 1
        try:
            importlib.import_module(m.name)
        except Exception as e:
            broken.append(f"{m.name}: {type(e).__name__} {str(e)[:90]}")
    if broken:
        line(f"  [FAIL] {len(broken)}/{total} 모듈 import 실패:")
        for b in broken:
            line(f"    - {b}")
    else:
        line(f"  [PASS] {total}개 모듈 전부 import OK")

    # ── 2. 핵심 신규 모듈 심볼 존재 (이번 세션들 산출물) ────────────
    line("\n[2] 핵심 연결고리 심볼 확인")
    checks = [
        ("src.memory.user_feedback_store", ["FeedbackStore", "get_reviewer_patterns"]),
        ("src.ingestion.pmc_downloader", ["PMCDownloader", "download_pmc_for_topic"]),
        ("src.ingestion.paper_ingester", ["PaperIngester"]),
        ("src.diagnostics.capability_bench", ["get_improvement_context", "CapabilityBench"]),
        ("src.diagnostics.stat_consistency", ["verify_stat_consistency"]),
        ("src.research.paper_writer", ["PaperWriter"]),
    ]
    sym_fail = []
    for mod_name, syms in checks:
        try:
            mod = importlib.import_module(mod_name)
            for s in syms:
                if not hasattr(mod, s):
                    sym_fail.append(f"{mod_name}.{s} 없음")
        except Exception as e:
            sym_fail.append(f"{mod_name} import 실패: {str(e)[:60]}")
    # PaperWriter.refine_section (인스턴스 메서드)
    try:
        from src.research.paper_writer import PaperWriter
        if not hasattr(PaperWriter, "refine_section"):
            sym_fail.append("PaperWriter.refine_section 없음")
    except Exception:
        pass
    if sym_fail:
        line(f"  [FAIL] {len(sym_fail)}개 심볼 누락:")
        for s in sym_fail:
            line(f"    - {s}")
    else:
        line("  [PASS] 핵심 심볼 전부 존재")

    # ── 3. self_auditor 빠른 진단 ───────────────────────────────────
    line("\n[3] self_auditor 빠른 진단")
    try:
        from src.diagnostics.self_auditor import SelfAuditor
        res = SelfAuditor().run_quick_audit()  # AuditResult 객체 (dict 아님)
        line(f"  [PASS] overall_score={getattr(res, 'overall_score', '?')}, "
             f"code_issues={len(getattr(res, 'code_issues', []))}")
    except Exception as e:
        line(f"  [WARN] self_auditor 실패(비치명): {type(e).__name__} {str(e)[:80]}")

    # ── 4. self_model 건강도 ────────────────────────────────────────
    line("\n[4] self_model 건강도")
    try:
        from src.memory.self_model import get_model
        m = get_model()  # ProjectHealthModel 객체 (dict 아님)
        line(f"  [PASS] health={getattr(m, 'overall_score', '?')}, smoke={getattr(m, 'smoke_test_status', '?')}")
    except Exception as e:
        line(f"  [WARN] self_model 실패(비치명): {type(e).__name__} {str(e)[:80]}")

    # ── 요약 ────────────────────────────────────────────────────────
    line("\n" + "=" * 60)
    ok = not broken and not sym_fail
    line(f"  결과: {'무결성 OK — 연결고리 정상' if ok else '⚠️ 문제 발견 — 위 항목 확인'}")
    line("=" * 60)

    out = pathlib.Path("data/diagnostics/e2e_diag_report.txt")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(report), encoding="utf-8")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
