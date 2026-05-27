"""Audit wiring — 새로 추가된 def/class 심볼이 production 경로에서 실제 호출되는지 검증.

자체검증 의무 (CLAUDE.md 규칙 10 / [[feedback_wiring_not_creation]]):
  작업 완료 = 파일 작성 + import 통과 + **호출부 wiring 검증**.

사용:
    python scripts/audit_wiring.py                     # git HEAD~1...HEAD 범위
    python scripts/audit_wiring.py --range=HEAD~5..HEAD
    python scripts/audit_wiring.py --files src/foo.py  # 명시 파일

검증 원칙:
  · 추가된 모든 `^def `/`^class ` 심볼을 추출 (private `_` 시작 제외)
  · 각 심볼명을 src/ app/ scripts/에서 grep — 작성 파일 외에 1+ 호출이 있어야 OK
  · 0 callers = dead code → FAIL 로 보고
"""
from __future__ import annotations

import argparse
import io
import re
import subprocess
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


def _git_diff_files(rev_range: str) -> list[str]:
    cmd = ["git", "diff", "--name-only", rev_range]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return [f for f in out.stdout.splitlines()
            if f.endswith(".py") and (f.startswith("src/") or f.startswith("scripts/") or f.startswith("app/"))]


def _git_added_lines(file_path: str, rev_range: str) -> list[str]:
    cmd = ["git", "diff", rev_range, "--", file_path]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return [ln[1:] for ln in out.stdout.splitlines()
            if ln.startswith("+") and not ln.startswith("+++")]


def _extract_symbols(file_path: str, lines: list[str]) -> list[tuple[str, str]]:
    """추가된 줄에서 def/class 심볼 추출. private(_) 제외."""
    syms: list[tuple[str, str]] = []
    for ln in lines:
        m = re.match(r"^\s*(def|class)\s+([A-Za-z][A-Za-z0-9_]*)\s*[\(:]", ln)
        if m and not m.group(2).startswith("_"):
            syms.append((m.group(2), m.group(1)))
    return syms


def _count_callers(symbol: str, exclude_file: str) -> int:
    """src/ app/ scripts/에서 symbol을 참조하는 줄 수 (정의 자체 제외)."""
    n = 0
    for root in ("src", "app", "scripts"):
        if not Path(root).exists():
            continue
        cmd = ["git", "grep", "-n", r"\b" + symbol + r"\b", "--", root]
        out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
        for ln in out.stdout.splitlines():
            # 경로:line:내용
            if not ln:
                continue
            path = ln.split(":", 1)[0]
            if Path(path).resolve() == Path(exclude_file).resolve():
                # 자기 파일 내 호출(__init__ 자가호출 등)도 카운트는 함 — but skip definition line
                if re.search(rf"^\s*(def|class)\s+{re.escape(symbol)}\b", ln.split(":", 2)[-1]):
                    continue
            n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--range", default="HEAD~1..HEAD",
                     help="git rev range (default: HEAD~1..HEAD)")
    ap.add_argument("--files", nargs="*", help="명시 파일 (range 무시)")
    ap.add_argument("--min-callers", type=int, default=1,
                     help="이 수 미만이면 FAIL (default: 1)")
    args = ap.parse_args()

    if args.files:
        files = args.files
        added_lines = {f: Path(f).read_text(encoding="utf-8").splitlines() for f in files
                        if Path(f).exists()}
    else:
        files = _git_diff_files(args.range)
        added_lines = {f: _git_added_lines(f, args.range) for f in files}

    if not files:
        print("✓ 검사 대상 파일 없음 (변경 .py 없음)")
        return 0

    print(f"audit_wiring — range={args.range}, files={len(files)}")
    print("=" * 96)

    total_syms = 0
    failures: list[tuple[str, str, str]] = []
    for f, lines in added_lines.items():
        syms = _extract_symbols(f, lines)
        if not syms:
            continue
        for name, kind in syms:
            callers = _count_callers(name, f)
            total_syms += 1
            mark = "✓" if callers >= args.min_callers else "✗"
            print(f"  {mark} {kind:5s} {name:40s} callers={callers:3d}  ({f})")
            if callers < args.min_callers:
                failures.append((name, kind, f))

    print("-" * 96)
    if failures:
        print(f"✗ FAIL: {len(failures)}/{total_syms} 심볼이 wiring 안 됨 (dead code 위험)")
        for name, kind, f in failures:
            print(f"    {kind} {name}  in {f}")
        return 1
    print(f"✓ PASS: {total_syms} 심볼 모두 호출부 1+ 존재")
    return 0


if __name__ == "__main__":
    sys.exit(main())
