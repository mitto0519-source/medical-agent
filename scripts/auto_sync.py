"""
auto_sync.py — Medical-Agent Git 자동 동기화 데몬 (v2, 2026-05-26 hardening)
================================================
시작 시: lockfile 확인 → git pull
변경 감지 시: git add -A → commit → push (디바운스)
충돌 방지: pull --rebase + stash, stash pop 실패 시 작업 보존(silent 무시 금지)

★ v2 변경 (이전 stash 누적 버그·중복 실행 사고 대응):
  - lockfile(.auto_sync.lock): PID 기반 중복 실행 차단(stale lock 자동 정리)
  - stash 누적 모니터: 5개 이상이면 동기화 중단(사용자에게 알림 후 수동 정리 요구)
  - stash pop 실패 시 명시적 로그 + stash 보존(작업 손실 방지)
  - 자기-생성 stash에 'auto_sync_' 라벨 → 식별 가능
  - 디바운스 60초(편집 활발 중 push 안 함)
"""

import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
LOG_FILE = BASE_DIR / "scripts" / "sync.log"
LOCK_FILE = BASE_DIR / ".auto_sync.lock"
DEBOUNCE_SECONDS = 60   # 마지막 변경 후 60초간 가만히면 동기화
POLL_SECONDS = 10
MAX_STASH = 5           # 자기-생성 stash 누적 한도


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def git(args: list) -> tuple:
    result = subprocess.run(
        ["git"] + args,
        capture_output=True, text=True, cwd=BASE_DIR, encoding="utf-8"
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


# ── Lock 처리 ────────────────────────────────────────────────────────────────

def acquire_lock() -> bool:
    """다중 실행 방지. stale lock(죽은 PID)은 자동 정리. False면 종료."""
    if LOCK_FILE.exists():
        try:
            pid = int((LOCK_FILE.read_text(encoding="utf-8").strip() or "0"))
        except Exception:
            pid = 0
        if pid > 0:
            # 살아있는지 확인 — Windows/POSIX 모두 동작
            alive = False
            try:
                if os.name == "nt":
                    import ctypes
                    PROCESS_QUERY_LIMITED = 0x1000
                    h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED, False, pid)
                    if h:
                        ctypes.windll.kernel32.CloseHandle(h)
                        alive = True
                else:
                    os.kill(pid, 0); alive = True
            except Exception:
                alive = False
            if alive:
                log(f"이미 실행 중 (PID={pid}). 새 인스턴스 종료.")
                return False
        log(f"stale lock 정리 (PID={pid})")
        try: LOCK_FILE.unlink()
        except Exception: pass
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock():
    try:
        if LOCK_FILE.exists() and (LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid())):
            LOCK_FILE.unlink()
    except Exception:
        pass


# ── git 상태 헬퍼 ─────────────────────────────────────────────────────────────

def has_changes() -> bool:
    stdout, _, _ = git(["status", "--porcelain"])
    return bool(stdout.strip())


def stash_count() -> int:
    out, _, _ = git(["stash", "list"])
    return len([l for l in out.splitlines() if l.strip()])


def get_changed_files() -> list:
    stdout, _, _ = git(["status", "--porcelain"])
    return [l[3:].strip() for l in stdout.splitlines() if l.strip()]


# ── 동기화 ────────────────────────────────────────────────────────────────────

def pull() -> bool:
    """변경사항 stash 후 pull --rebase. pop 실패 시 stash 보존(작업 손실 방지)."""
    # 누적 stash 안전장치
    sc = stash_count()
    if sc >= MAX_STASH:
        log(f"  ⚠ stash 누적 {sc}개 (한도 {MAX_STASH}) — pull 중단. `git stash list` 확인 후 수동 정리 필요.")
        return False

    label = f"auto_sync_{datetime.now().strftime('%m%d_%H%M%S')}"
    stashed = False
    if has_changes():
        _, err, code = git(["stash", "push", "-u", "-m", label])
        if code == 0 and "No local changes" not in err:
            stashed = True

    out, err, code = git(["pull", "--rebase", "origin", "master"])
    if code != 0:
        log(f"  ✗ PULL 실패: {err}")
        if stashed:
            _, perr, pcode = git(["stash", "pop"])
            if pcode != 0:
                log(f"  ⚠ pull 실패 후 stash pop도 실패 — stash 보존: {perr}")
        return False

    log(f"  ✓ PULL: {out or '최신'}")
    if stashed:
        _, perr, pcode = git(["stash", "pop"])
        if pcode != 0:
            log(f"  ⚠ stash pop 실패 — 작업 보존(stash list에 남음): {perr}")
            log(f"     수동 복원: git stash pop  (또는 git stash apply --index)")
            return False
    return True


def push(changed_files: list) -> bool:
    summary = ", ".join(changed_files[:5])
    if len(changed_files) > 5:
        summary += f" 외 {len(changed_files)-5}개"
    ts = datetime.now().strftime("%m/%d %H:%M")
    commit_msg = f"Auto-sync [{ts}]: {summary}"

    git(["add", "-A"])
    _, err, code = git(["commit", "-m", commit_msg])
    if code != 0:
        log(f"  커밋 스킵 (변경 없음): {err}")
        return True

    log(f"  ✓ 커밋: {commit_msg}")
    _, err, code = git(["push", "origin", "master"])
    if code == 0:
        log("  ✓ PUSH 완료")
        return True

    log(f"  ✗ PUSH 실패: {err} — pull --rebase 후 1회 재시도")
    if not pull():
        return False
    _, err2, code2 = git(["push", "origin", "master"])
    if code2 == 0:
        log("  ✓ PUSH 재시도 성공")
        return True
    log(f"  ✗ PUSH 재시도도 실패: {err2}")
    return False


# ── 메인 루프 ─────────────────────────────────────────────────────────────────

def main():
    log("=" * 50)
    log("Medical-Agent 자동 동기화 시작 (v2)")
    log(f"  base: {BASE_DIR}")
    log(f"  디바운스: {DEBOUNCE_SECONDS}초 | 폴링: {POLL_SECONDS}초 | stash 한도: {MAX_STASH}")
    log("=" * 50)

    if not acquire_lock():
        sys.exit(0)

    log(f"현재 stash {stash_count()}개 (한도 {MAX_STASH})")
    pull()

    last_change_time = None
    last_known_status = ""

    try:
        while True:
            time.sleep(POLL_SECONDS)
            try:
                stdout, _, _ = git(["status", "--porcelain"])
                current = stdout.strip()

                if current != last_known_status:
                    if current:
                        log(f"  변경 감지 ({len(current.splitlines())}개) — {DEBOUNCE_SECONDS}초 후 동기화")
                        last_change_time = time.time()
                    last_known_status = current

                if last_change_time and (time.time() - last_change_time >= DEBOUNCE_SECONDS):
                    if has_changes():
                        changed = get_changed_files()
                        if pull():
                            push(changed)
                        last_known_status = ""
                    last_change_time = None
            except Exception as e:
                log(f"  loop 오류: {e}")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
