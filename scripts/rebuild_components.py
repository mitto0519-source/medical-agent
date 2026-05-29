"""기존 OA 풀텍스트 12,258편을 정규식 확장된 extractor로 일괄 재추출.

이미 받은 자산을 더 깊이 활용 (사용자 요구 2026-05-29):
  · 추가 다운로드 없이 component_extractor.py v2 정규식으로 재추출
  · 기존 components.db는 보존, 새 components만 add (sha1 id로 중복 자동 skip)
  · max_per_kind 30 → 80 (더 많이 추출)

호출:
    python scripts/rebuild_components.py            # 전체
    python scripts/rebuild_components.py --limit 100 # 첫 100편만 테스트
"""
from __future__ import annotations

import argparse
import io
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _ensure_utf8():
    if hasattr(sys.stdout, "buffer"):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8",
                                        errors="replace", line_buffering=True)


def main():
    _ensure_utf8()
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="0이면 전체")
    args = ap.parse_args()

    from src.library.component_extractor import extract_and_store
    from src.library.components import get_library
    import json as _j

    oa_dir = Path("data/oa_papers")
    txts = sorted(oa_dir.glob("PMC*.txt"))
    if args.limit:
        txts = txts[: args.limit]

    print(f"=== Rebuild Components · {len(txts):,} paper 재추출 시작 ===", flush=True)
    cs0 = get_library().stats()
    print(f"Before: {cs0['total']:,} components", flush=True)
    print(f"  by_kind: {cs0['by_kind']}", flush=True)

    t0 = time.time()
    total_added = 0
    for i, p in enumerate(txts, 1):
        try:
            body = p.read_text(encoding="utf-8", errors="replace")
            meta_p = p.with_suffix(".meta.json")
            pmcid = p.stem
            pmid = ""
            if meta_p.exists():
                try:
                    meta = _j.loads(meta_p.read_text(encoding="utf-8"))
                    pmid = meta.get("pmid", "") or ""
                except Exception:
                    pass
            n = extract_and_store(body, source_pmid=pmid or pmcid, author_style="")
            total_added += n
        except Exception as e:
            print(f"  [{i}] {p.name} fail: {e}", flush=True)
            continue
        if i % 200 == 0:
            elapsed = time.time() - t0
            rate = i / max(elapsed, 0.1)
            eta = (len(txts) - i) / max(rate, 0.1)
            cs = get_library().stats()
            print(f"[{i:,}/{len(txts):,}] components total={cs['total']:,} "
                   f"(+{cs['total']-cs0['total']:,}) · rate={rate:.1f}p/s · ETA={eta:.0f}s",
                   flush=True)

    cs1 = get_library().stats()
    print(f"\n=== DONE · elapsed={(time.time()-t0)/60:.1f}min ===", flush=True)
    print(f"Before:  {cs0['total']:,} components", flush=True)
    print(f"After:   {cs1['total']:,} components (+{cs1['total']-cs0['total']:,})", flush=True)
    print(f"\nNew by_kind:", flush=True)
    for k in cs1["by_kind"]:
        b0 = cs0["by_kind"].get(k, 0)
        b1 = cs1["by_kind"][k]
        print(f"  {k:30s} {b0:>7,} → {b1:>7,} (+{b1-b0:,})", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
