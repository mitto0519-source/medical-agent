"""HF Datasets bootstrap — container start 시 누락된 data/ 자동 download.

Online-first 원칙 (RULE-9): 외부 URL/Cloud Run/HF Spaces에서 컨테이너가 처음
부팅될 때 data/ 폴더가 비어 있다. 이 모듈이 HF dataset에서 필요한 자산만 가져온다.

사용:
    from src.runtime.hf_bootstrap import ensure_bootstrap
    ensure_bootstrap()   # streamlit_app.py 진입 시 1회 호출

환경변수:
    HF_TOKEN              — read 권한 (private dataset 접근에 필수)
    HF_DATASET_ID         — 기본값 cave87/medical-agent-runtime
    MEDICAL_AGENT_BOOTSTRAP_PROFILE — minimal / standard / full (default: standard)

profile:
    minimal  : seed + author_profiles + prompts + templates + agent_self
               (앱 진입은 가능. 통계/RAG 불가)
    standard : minimal + library + knowledge_graph + chromadb + runtime
               (RAG/Graph 작동. 단 KYRBS sav 없으면 통계 불가)
    full     : standard + raw (KYRBS 21웨이브) + oa_papers (12,625편 raw)
               (모든 기능 사용 가능. 4GB 다운로드)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

from src.config.logging_config import get_logger

_log = get_logger(__name__)

DEFAULT_DATASET_ID = "cave87/medical-agent-runtime"

PROFILE_FOLDERS = {
    "minimal":  ["data/medical_knowledge_seed", "data/author_profiles",
                 "data/agent_self", "data/templates", "prompts"],
    "standard": ["data/medical_knowledge_seed", "data/author_profiles",
                 "data/agent_self", "data/templates", "prompts",
                 "data/wiki", "data/library", "data/knowledge_graph",
                 "data/chromadb", "data/runtime"],
    "full":     ["data/medical_knowledge_seed", "data/author_profiles",
                 "data/agent_self", "data/templates", "prompts",
                 "data/wiki", "data/library", "data/knowledge_graph",
                 "data/chromadb", "data/runtime",
                 "data/raw", "data/oa_papers"],
}


def _folder_has_content(p: Path, min_files: int = 1) -> bool:
    """폴더가 비어있지 않은지 (이미 데이터 있는지) 확인."""
    if not p.exists():
        return False
    return sum(1 for _ in p.rglob("*") if _.is_file()) >= min_files


def _missing_folders(folders: Iterable[str]) -> list[str]:
    return [f for f in folders if not _folder_has_content(Path(f))]


def _download(folder: str, *, repo_id: str, token: str | None) -> bool:
    """단일 폴더 download via huggingface_hub.snapshot_download (allow_patterns)."""
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        _log.error("huggingface_hub not installed — pip install huggingface_hub")
        return False
    try:
        _log.info("[bootstrap] downloading %s from %s", folder, repo_id)
        snapshot_download(
            repo_id=repo_id, repo_type="dataset",
            allow_patterns=[f"{folder}/*", f"{folder}/**"],
            local_dir=".",
            token=token,
        )
        _log.info("[bootstrap] %s OK", folder)
        return True
    except Exception as e:
        _log.error("[bootstrap] %s FAIL: %s", folder, e)
        return False


def ensure_bootstrap(
    *,
    profile: str | None = None,
    repo_id: str | None = None,
    token: str | None = None,
    force: bool = False,
) -> dict:
    """Streamlit 진입 시 1회 호출. 누락 폴더만 download.

    Returns: {"downloaded": [...], "skipped": [...], "failed": [...]}
    """
    profile = profile or os.environ.get("MEDICAL_AGENT_BOOTSTRAP_PROFILE", "standard")
    repo_id = repo_id or os.environ.get("HF_DATASET_ID", DEFAULT_DATASET_ID)
    token = token or os.environ.get("HF_TOKEN")

    folders = PROFILE_FOLDERS.get(profile, PROFILE_FOLDERS["standard"])
    targets = list(folders) if force else _missing_folders(folders)

    if not targets:
        _log.info("[bootstrap] all profile=%s folders present, nothing to download", profile)
        return {"downloaded": [], "skipped": list(folders), "failed": []}

    _log.info("[bootstrap] profile=%s repo=%s missing=%d", profile, repo_id, len(targets))
    downloaded, failed = [], []
    for f in targets:
        if _download(f, repo_id=repo_id, token=token):
            downloaded.append(f)
        else:
            failed.append(f)

    result = {
        "downloaded": downloaded,
        "skipped": [f for f in folders if f not in targets],
        "failed": failed,
    }
    _log.info("[bootstrap] done: %s", result)
    return result


# ── push-back (write 영속) ──────────────────────────────────────────
# RULE-9 (online-first) 완성: 컨테이너 디스크가 휘발성이라도 사용자 상태가
# HF Datasets로 주기 push되어 재배포 후 복구된다.

_PUSH_TARGETS = [
    "data/runtime",
    "data/agent_self",
    "data/change_log",
    "data/working_papers",
    "data/profiles",      # per-user StyleProfile
    "data/chromadb",      # conversation_memory (대용량이라 ENABLE_HF_PUSH_CHROMA=1일 때만)
]


def push_runtime_to_hf(repo_id: str | None = None, token: str | None = None,
                          folders: Iterable[str] | None = None,
                          include_chroma: bool | None = None) -> dict:
    """data/runtime + agent_self + working_papers + profiles 를 HF Datasets로 push.

    환경변수:
        ENABLE_HF_PUSHBACK=0     → 전면 비활성 (default: 1)
        ENABLE_HF_PUSH_CHROMA=1  → chromadb 포함 (default: 0, 용량 큼)

    Returns: {pushed: [...], skipped: [...], failed: [...]}
    """
    if os.environ.get("ENABLE_HF_PUSHBACK", "1") == "0":
        return {"pushed": [], "skipped": ["disabled by ENABLE_HF_PUSHBACK=0"], "failed": []}

    try:
        from huggingface_hub import HfApi
    except ImportError:
        return {"pushed": [], "skipped": [], "failed": ["huggingface_hub not installed"]}

    rid = repo_id or os.environ.get("HF_DATASET_ID", DEFAULT_DATASET_ID)
    tok = token or os.environ.get("HF_TOKEN", "")
    if not tok:
        return {"pushed": [], "skipped": [], "failed": ["HF_TOKEN missing"]}

    if include_chroma is None:
        include_chroma = os.environ.get("ENABLE_HF_PUSH_CHROMA", "0") == "1"

    targets = list(folders) if folders else _PUSH_TARGETS
    if not include_chroma:
        targets = [t for t in targets if "chromadb" not in t]

    api = HfApi(token=tok)
    pushed, skipped, failed = [], [], []
    import time as _time
    for local in targets:
        lp = Path(local)
        if not lp.exists() or not any(lp.iterdir()):
            skipped.append(local)
            continue
        try:
            t0 = _time.time()
            api.upload_folder(
                repo_id=rid,
                repo_type="dataset",
                folder_path=str(lp),
                path_in_repo=lp.name,
                commit_message=f"runtime push {lp.name} ({_time.strftime('%Y-%m-%d %H:%M:%S')})",
                ignore_patterns=["*.pyc", "__pycache__/*", "*.tmp", "*-wal", "*-shm",
                                  ".DS_Store"],
            )
            _log.info("[push] %s → %s (%.1fs)", local, rid, _time.time() - t0)
            pushed.append(local)
        except Exception as e:
            _log.warning("[push] %s FAIL: %s", local, str(e)[:200])
            failed.append(f"{local}: {str(e)[:120]}")
    return {"pushed": pushed, "skipped": skipped, "failed": failed}


def cli():
    """python -m src.runtime.hf_bootstrap [--profile standard] [--force]"""
    import argparse
    p = argparse.ArgumentParser(description="HF Datasets bootstrap")
    p.add_argument("--profile", default=os.environ.get("MEDICAL_AGENT_BOOTSTRAP_PROFILE", "standard"),
                   choices=list(PROFILE_FOLDERS.keys()))
    p.add_argument("--repo", default=DEFAULT_DATASET_ID)
    p.add_argument("--force", action="store_true")
    a = p.parse_args()
    result = ensure_bootstrap(profile=a.profile, repo_id=a.repo, force=a.force)
    print(result)
    sys.exit(0 if not result["failed"] else 1)


if __name__ == "__main__":
    cli()
