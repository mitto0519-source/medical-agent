"""Audit script — data/ 전체에서 lone UTF-16 surrogate 스캔 + 자동 클린.

용도:
    Claude API가 `400 no low surrogate` 로 영구 차단되는 사고(2026-05-30)의
    재발 방지. 이미 디스크에 자리잡은 깨진 텍스트를 찾아내 클린하거나 신고한다.

사용:
    # 스캔만 (안전)
    python scripts/audit_text_safety.py
    # 발견된 파일 자동 sanitize (json/jsonl만, 백업 .bak 생성)
    python scripts/audit_text_safety.py --fix

스캔 대상:
    data/**/*.json, data/**/*.jsonl, data/**/*.md, data/**/*.txt
    (SQLite/binary는 제외 — 별도 처리 필요)

종료 코드:
    0 = 깨진 텍스트 없음
    1 = 발견됨 (CI gate 활용 가능)
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys
from pathlib import Path

# Windows cp949 콘솔에서도 em-dash(—) 같은 비-ASCII 출력이 깨지지 않도록 강제 UTF-8.
os.environ["PYTHONIOENCODING"] = "utf-8"
if sys.stdout and hasattr(sys.stdout, "buffer"):
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass
if sys.stderr and hasattr(sys.stderr, "buffer"):
    try:
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True)
    except Exception:
        pass

# 프로젝트 루트 sys.path 보장 (스크립트 단독 실행)
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from src.utils.text_sanitize import (
    scan_lone_surrogates, strip_lone_surrogates, safe_json_dumps,
)

EXTS = {".json", ".jsonl", ".md", ".txt"}
SKIP_DIRS = {"__pycache__", ".git", "_archive", "uploads"}  # uploads는 사용자 원본


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if p.suffix.lower() not in EXTS:
            continue
        yield p


def _scan(p: Path) -> int:
    try:
        text = p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        # utf-8이 아님 — 잠재 위험, 카운트 1로 표시
        return -1
    except Exception:
        return 0
    return len(scan_lone_surrogates(text))


def _fix_json(p: Path) -> bool:
    """json/jsonl 파일을 sanitize 후 같은 경로에 다시 쓴다. 백업 .bak 생성."""
    try:
        text = p.read_text(encoding="utf-8")
    except Exception:
        return False
    cleaned = strip_lone_surrogates(text)
    if cleaned == text:
        return False
    p.with_suffix(p.suffix + ".bak").write_text(text, encoding="utf-8")
    if p.suffix.lower() == ".json":
        try:
            obj = json.loads(cleaned)
            p.write_text(safe_json_dumps(obj, indent=2), encoding="utf-8")
            return True
        except Exception:
            # JSON 자체가 깨졌으면 raw 텍스트로 클린만 적용
            pass
    p.write_text(cleaned, encoding="utf-8")
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true",
                    help="발견된 파일을 자동 sanitize (백업 .bak 생성)")
    ap.add_argument("--root", default="data",
                    help="스캔 루트 (기본: data/)")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        print(f"[skip] {root} 없음")
        return 0

    found, fixed, undecodable = [], [], []
    for p in _iter_files(root):
        n = _scan(p)
        if n < 0:
            undecodable.append(p)
        elif n > 0:
            found.append((p, n))

    print(f"=== audit_text_safety — root={root} ===")
    print(f"  scanned exts: {sorted(EXTS)}")
    print(f"  skipped dirs: {sorted(SKIP_DIRS)}")
    print()

    if undecodable:
        print(f"[WARN] UTF-8 디코딩 실패 {len(undecodable)}개:")
        for p in undecodable[:10]:
            print(f"  - {p.relative_to(root.parent if root.parent.exists() else root)}")
        print()

    if not found:
        print("[OK] lone surrogate 발견 0건")
        return 0

    print(f"[FOUND] lone surrogate 포함 파일 {len(found)}개:")
    for p, n in found[:30]:
        try:
            rel = p.relative_to(root.parent if root.parent.exists() else root)
        except Exception:
            rel = p
        print(f"  - {rel}  ({n}개 lone)")

    if args.fix:
        print()
        print("--fix 모드: sanitize 적용 중…")
        for p, _ in found:
            if _fix_json(p):
                fixed.append(p)
                print(f"  [fixed] {p}  (백업 {p.with_suffix(p.suffix+'.bak').name})")
        print(f"\n총 {len(fixed)}개 파일 sanitize 완료.")
    else:
        print("\n(--fix 없으면 진단만, 변경 안 함)")

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
