"""oa_papers 25,251편 (50,504 files) chunked upload to HF Datasets.

이전 시도: 한 commit으로 50K files → 504 Gateway Timeout.
이번: 1000 files씩 batch commit (~50 commits) → 각 commit 작아서 timeout 회피.

병행 가능: 이 스크립트가 도는 동안 다른 작업 진행 OK.
실행: python -X utf8 scripts/hf_oa_papers_chunked.py > data/logs/oa_chunked.log 2>&1
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.env import bootstrap
bootstrap()

from huggingface_hub import HfApi, CommitOperationAdd

REPO = "cave87/medical-agent-runtime"
LOCAL_DIR = Path("data/oa_papers")
BATCH_SIZE = 800  # 한 commit당 파일 수


def main():
    api = HfApi(token=os.environ["HF_TOKEN"])
    if not LOCAL_DIR.exists():
        print(f"missing {LOCAL_DIR}")
        return

    # 이미 업로드된 파일 (skip)
    print("Fetching existing files in repo...", flush=True)
    existing = set(api.list_repo_files(REPO, repo_type="dataset"))
    existing_oa = {f for f in existing if f.startswith("oa_papers/")}
    print(f"  already in oa_papers/: {len(existing_oa)}", flush=True)

    # 로컬 파일 수집
    local_files = []
    for fp in LOCAL_DIR.rglob("*"):
        if not fp.is_file():
            continue
        if fp.suffix.lower() in {".pyc", ".tmp"}:
            continue
        rel = fp.relative_to(LOCAL_DIR).as_posix()
        in_repo = f"oa_papers/{rel}"
        if in_repo in existing_oa:
            continue
        local_files.append((fp, in_repo))
    print(f"to upload: {len(local_files)} files", flush=True)

    if not local_files:
        print("nothing to upload — all in sync")
        return

    total_batches = (len(local_files) + BATCH_SIZE - 1) // BATCH_SIZE
    t_start = time.time()
    for i in range(0, len(local_files), BATCH_SIZE):
        batch = local_files[i:i + BATCH_SIZE]
        batch_n = i // BATCH_SIZE + 1
        print(f"\n[batch {batch_n}/{total_batches}] uploading {len(batch)} files", flush=True)
        ops = [CommitOperationAdd(path_in_repo=in_repo, path_or_fileobj=str(fp))
                for fp, in_repo in batch]
        try:
            t0 = time.time()
            api.create_commit(
                repo_id=REPO,
                repo_type="dataset",
                operations=ops,
                commit_message=f"oa_papers batch {batch_n}/{total_batches}",
            )
            print(f"  done in {time.time()-t0:.1f}s  (total elapsed {time.time()-t_start:.1f}s)",
                  flush=True)
        except Exception as e:
            print(f"  FAIL batch {batch_n}: {str(e)[:200]}", flush=True)
            time.sleep(10)  # 504 등 일시 장애 회피 후 다음 batch 계속

    print(f"\nALL DONE in {time.time()-t_start:.1f}s")


if __name__ == "__main__":
    main()
