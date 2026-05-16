"""
auto_sync.py — Medical-Agent Git 자동 동기화 데몬
================================================
시작 시: git pull
변경 감지 시: git add -A → commit → push (디바운스 30초)
충돌 방지: pull --rebase 사용
"""

import subprocess
import sys
import time
import os
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
LOG_FILE = BASE_DIR / "scripts" / "sync.log"
WATCH_DIRS = ["src", "data/libraries", "data/author_profiles", "app", "scripts"]
DEBOUNCE_SECONDS = 30   # 변경 후 30초 대다가 커밋 (연속 저장 묶음 처리)
POLL_SECONDS = 10       # 10초마다 변경 감지


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def git(args: list[str]) -> tuple[str, str, int]:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=BASE_DIR, encoding="utf-8"
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def has_changes() -> bool:
    stdout, _, _ = git(["status", "--porcelain"])
    return bool(stdout.strip())


def pull():
    """변경사항 커밋 후 pull --rebase로 충돌 최소화."""
    log("▼ PULL 시작...")
    # 로컬 변경이 있으면 먼저 stash
    if has_changes():
        git(["stash"])
        stashed = True
    else:
        stashed = False

    out, err, code = git(["pull", "--rebase", "origin", "master"])
    if code == 0:
        log(f"  ✓ PULL 완료: {out or '최신 상태'}")
    else:
        log(f"  ✗ PULL 실패: {err}")

    if stashed:
        out2, err2, _ = git(["stash", "pop"])
        log(f"  stash pop: {out2 or err2}")


def push(changed_files: list[str]):
    """add → commit → push."""
    summary = ", ".join(changed_files[:5])
    if len(changed_files) > 5:
        summary += f" 외 {len(changed_files)-5}개"

    ts = datetime.now().strftime("%m/%d %H:%M")
    commit_msg = f"Auto-sync [{ts}]: {summary}"

    git(["add", "-A"])
    out, err, code = git(["commit", "-m", commit_msg])
    if code != 0:
        log(f"  커밋 스킵 (변경 없음): {err}")
        return

    log(f"  ✓ 커밋: {commit_msg}")

    out, err, code = git(["push", "origin", "master"])
    if code == 0:
        log(f"  ✓ PUSH 완료")
    else:
        log(f"  ✗ PUSH 실패: {err}")
        # push 실패 시 pull --rebase 후 재시도
        pull()
        git(["push", "origin", "master"])


def get_changed_files() -> list[str]:
    stdout, _, _ = git(["status", "--porcelain"])
    files = []
    for line in stdout.splitlines():
        if line.strip():
            files.append(line[3:].strip())
    return files


def main():
    log("=" * 50)
    log("Medical-Agent 자동 동기화 시작")
    log(f"  감시 경로: {BASE_DIR}")
    log(f"  디바운스: {DEBOUNCE_SECONDS}초 | 폴링: {POLL_SECONDS}초")
    log("=" * 50)

    # 시작 시 pull
    pull()

    last_change_time = None
    last_known_status = ""

    while True:
        time.sleep(POLL_SECONDS)

        try:
            stdout, _, _ = git(["status", "--porcelain"])
            current_status = stdout.strip()

            if current_status != last_known_status:
                # 새 변경 감지
                if current_status:
                    log(f"  변경 감지 ({len(current_status.splitlines())}개 파일) — {DEBOUNCE_SECONDS}초 후 동기화")
                    last_change_time = time.time()
                last_known_status = current_status

            # 디바운스 경과 후 push
            if last_change_time and (time.time() - last_change_time >= DEBOUNCE_SECONDS):
                if has_changes():
                    changed = get_changed_files()
                    pull()  # push 전에 최신 pull
                    push(changed)
                    last_known_status = ""
                last_change_time = None

        except Exception as e:
            log(f"  오류: {e}")


if __name__ == "__main__":
    main()
