"""HF Datasets에 누락된 7개 폴더를 한 번에 backup 업로드.

실행 순서:
  1. 작은 폴더 4개 먼저 (agent_self, knowledge_graph, medical_knowledge_seed, runtime) — 빠른 부팅 자료
  2. 큰 폴더 3개 (library, chromadb, oa_papers) — 백그라운드 길게
  3. root에 잘못 풀린 PMC*.txt 9,997개는 server-side move (별도 함수)

병행 실행: python -X utf8 scripts/hf_sync_missing.py 2>&1 | tee data/logs/hf_sync.log
"""
from __future__ import annotations
import os, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.config.env import bootstrap
bootstrap()
from huggingface_hub import HfApi

REPO = "cave87/medical-agent-runtime"

UPLOAD_PLAN = [
    # (local path, path_in_repo, priority)
    ("data/agent_self",              "agent_self",              "P0"),
    ("data/knowledge_graph",         "knowledge_graph",         "P0"),
    ("data/medical_knowledge_seed",  "medical_knowledge_seed",  "P0"),
    ("data/runtime",                 "runtime",                 "P0"),
    ("data/library",                 "library",                 "P1"),
    ("data/chromadb",                "chromadb",                "P1"),
    ("data/oa_papers",               "oa_papers",               "P2"),
]


def upload_one(api: HfApi, local: str, in_repo: str):
    """upload_folder는 path_in_repo 지원. upload_large_folder는 미지원이라 안 씀.

    큰 폴더(>1GB)도 upload_folder가 정상 처리 — 단 commit이 커서 timeout 가능.
    그럴 땐 hf-cli 또는 chunked upload로 전환 필요.
    """
    if not Path(local).exists():
        print(f"  [SKIP] {local} not exists", flush=True)
        return
    n = sum(1 for _ in Path(local).rglob("*") if _.is_file())
    print(f"  [UPLOAD] {local} → {in_repo}  ({n} files)", flush=True)
    t0 = time.time()
    try:
        api.upload_folder(
            repo_id=REPO,
            repo_type="dataset",
            folder_path=local,
            path_in_repo=in_repo,
            commit_message=f"Sync {in_repo}: {n} files",
            ignore_patterns=["*.pyc", "__pycache__/*", "*.tmp", ".DS_Store"],
        )
        print(f"  [DONE]   {in_repo}  ({time.time()-t0:.1f}s)", flush=True)
    except Exception as e:
        print(f"  [FAIL]   {in_repo}: {str(e)[:200]}", flush=True)


def main():
    api = HfApi(token=os.environ["HF_TOKEN"])
    print(f"target repo: {REPO}")
    print(f"plan: {len(UPLOAD_PLAN)} folders")
    for local, in_repo, prio in UPLOAD_PLAN:
        print(f"\n--- {prio}: {local} ---", flush=True)
        upload_one(api, local, in_repo)
    print("\nALL DONE")


if __name__ == "__main__":
    main()
