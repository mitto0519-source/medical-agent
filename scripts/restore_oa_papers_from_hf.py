"""HF Datasets에서 oa_papers 사본 복구 — 사다리 #4 (FIX-11 사고 후 복구).

source: cave87/medical-agent-runtime (private, lastModified 2026-06-11 — 사고 이전)
target: data/oa_papers/
  PMC*.txt + PMC*.meta.json  (약 9,796편)
  + agent_self/* (옵션 — 메모리 복구)
  + chromadb/*  (옵션 — 벡터 백업)

snapshot_download 한 줄로 통째로. 이미 있는 파일 skip.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from src.config.env import bootstrap
    bootstrap()
    token = os.environ.get("HF_TOKEN", "")
    if not token:
        print("ERROR: HF_TOKEN missing in .env")
        return 1
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("ERROR: huggingface_hub not installed. pip install huggingface_hub")
        return 1

    target = Path("data")
    target.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("OA papers 복구: cave87/medical-agent-runtime → data/")
    print("=" * 60)
    print("주의: 대용량(추정 1-3GB). 진행률 표시됨.")
    t0 = time.time()
    try:
        local_path = snapshot_download(
            repo_id="cave87/medical-agent-runtime",
            repo_type="dataset",
            local_dir=str(target),
            local_dir_use_symlinks=False,
            token=token,
            # PMC*.txt + meta.json + agent_self + chromadb 모두
            allow_patterns=["PMC*.txt", "PMC*.meta.json",
                              "agent_self/*", "chromadb/*",
                              "manifest.sqlite", "README.md", ".gitattributes"],
        )
        dt = time.time() - t0
        print(f"\n✓ 다운로드 완료: {local_path} ({dt:.0f}s)")
    except Exception as e:
        print(f"\nFAIL: {type(e).__name__}: {e}")
        return 2

    # PMC*.txt를 data/oa_papers/로 이동 (snapshot_download가 root에 둠)
    oa_dir = Path("data/oa_papers")
    oa_dir.mkdir(parents=True, exist_ok=True)
    moved = 0
    for p in target.glob("PMC*.txt"):
        target_p = oa_dir / p.name
        if not target_p.exists():
            p.rename(target_p)
            moved += 1
    for p in target.glob("PMC*.meta.json"):
        target_p = oa_dir / p.name
        if not target_p.exists():
            p.rename(target_p)
            moved += 1
    print(f"\nPMC 파일 → data/oa_papers/로 이동: {moved:,}개")

    # 인벤토리 확인
    txt = list(oa_dir.glob("PMC*.txt"))
    meta = list(oa_dir.glob("PMC*.meta.json"))
    print(f"최종 data/oa_papers: .txt {len(txt):,} / .meta.json {len(meta):,}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
