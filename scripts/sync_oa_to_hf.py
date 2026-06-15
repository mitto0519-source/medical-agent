"""Data plane sync — data/oa_papers/ → HF private Datasets (영구 차단).

★ FIX-11 ④-bis (2026-06-15): 두 번째 데이터 사고 (filter-repo로 워킹트리 .txt 영구 삭제)
방지. 인제스트 후 항상 HF Datasets에 push-back → git이 데이터를 건드릴 수 없게.

실행:
  python scripts/sync_oa_to_hf.py            # 전체 sync
  python scripts/sync_oa_to_hf.py --dry-run  # 진단만

heartbeat에서 매일 1회 자동 호출 권장 (idempotent).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def main() -> int:
    from src.config.env import bootstrap
    bootstrap()
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-id", default="cave87/medical-agent-runtime")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("HF_TOKEN", "")
    if not token:
        print("ERROR: HF_TOKEN missing")
        return 1
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("ERROR: huggingface_hub not installed")
        return 1

    oa = Path("data/oa_papers")
    if not oa.exists():
        print(f"⚠ {oa} 없음 — sync 중단")
        return 1

    txt_files = list(oa.glob("PMC*.txt"))
    meta_files = list(oa.glob("PMC*.meta.json"))
    print(f"로컬: .txt {len(txt_files):,} / .meta.json {len(meta_files):,}")

    if args.dry_run:
        print("\n--dry-run: 실제 업로드 안 함. 위 파일을 HF push할 수 있음.")
        return 0

    api = HfApi(token=token)
    print(f"\n→ HF push: {args.repo_id} (private, dataset)")
    try:
        api.upload_folder(
            folder_path=str(oa),
            repo_id=args.repo_id,
            repo_type="dataset",
            allow_patterns=["PMC*.txt", "PMC*.meta.json"],
            commit_message=f"oa_papers sync — {len(txt_files):,} txt + {len(meta_files):,} meta",
        )
        print(f"✓ sync 완료: {len(txt_files):,}편 → {args.repo_id}")
        return 0
    except Exception as e:
        print(f"❌ sync 실패: {e}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
