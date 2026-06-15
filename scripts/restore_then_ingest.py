"""복구 + 즉시 인제스트 체인 — 사다리 #4 + #5 자동 연결.

순서:
  1. HF Datasets에서 oa_papers 다운로드 (9,796편)
  2. data/ root에 떨어진 PMC*.{txt,meta.json} → data/oa_papers/로 이동
  3. ingest_fulltext_corpus.py --skip-existing 자동 시작 (이미 인덱싱된 3,697편 skip)
  4. 추가 차집합 2,829편 (12,625 - 9,796) — oa_bulk_fetcher로 별도 fetch (옵션)

실행:
  python scripts/restore_then_ingest.py
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    print("=" * 60)
    print("Restore + Ingest 체인 시작")
    print("=" * 60)

    # 1. HF 다운로드
    print("\n[Phase 1] HF Datasets → data/oa_papers/")
    r = subprocess.run(
        [sys.executable, "scripts/restore_oa_papers_from_hf.py"],
        check=False
    )
    if r.returncode != 0:
        print(f"❌ 복구 실패 (exit {r.returncode}). 인제스트 중단.")
        return r.returncode

    # 2. 인벤토리 확인
    oa = Path("data/oa_papers")
    txt = list(oa.glob("PMC*.txt"))
    print(f"\n✓ 복구 완료: {len(txt):,}편 .txt")
    if not txt:
        print("⚠ 복구된 .txt 0편 — 인제스트 무의미. 중단.")
        return 1

    # 3. 인제스트 시작 (skip-existing 활성)
    print(f"\n[Phase 2] ingest_fulltext_corpus.py --skip-existing")
    print(f"   ChromaDB에 이미 있는 PMID는 자동 skip (3,697편)")
    print(f"   예상 신규: {max(0, len(txt) - 3697):,}편")
    print(f"   예상 시간: {max(0, len(txt) - 3697) * 10 / 3600:.1f}h (0.1편/초)")
    r2 = subprocess.run(
        [sys.executable, "scripts/ingest_fulltext_corpus.py", "--skip-existing"],
        check=False
    )
    print(f"\n인제스트 종료 (exit {r2.returncode})")
    return r2.returncode


if __name__ == "__main__":
    raise SystemExit(main())
