"""
auto_sync.py — Medical-Agent Git 자동 동기화 데몬 (v3, 2026-05-27)
================================================
★ commit-first 패턴 (stash 0 의존, worktree 불필요)

동작:
  변경 감지 → 60초 디바운스 → git add -A → git commit → pull --rebase → push
                                                ↑ 트리가 이미 clean이라 stash 불필요

v2(stash) → v3 차이:
  - stash push/pop 완전 제거 (누적·pop 실패·작업 손실 위험 0)
  - "commit-first": 항상 local WIP를 먼저 commit한 뒤 pull. 트리가 clean이라 rebase 안전
  - rebase conflict 발생 시 abort + 다음 cycle 재시도 (현재 commit 보존)
  - push 실패 시 한 번 더 pull--rebase + push (commit 이미 있어 trivial)
  - lockfile / 자기 살아있는 PID 확인 / catchup pull은 그대로

쓸 만한가:
  - stash 안 쓰니 worktree 같은 우회 메커니즘도 불필요
  - 사용자가 편집 중인 파일은 60초 idle 후 commit → 부분 저장 위험 낮음
  - rebase는 항상 clean 트리에서 일어남 → stash pop 실패 같은 상황 원천 차단
"""
from __future__ import annotations
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.resolve()
LOG_FILE = BASE_DIR / "scripts" / "sync.log"
LOCK_FILE = BASE_DIR / ".auto_sync.lock"
DEBOUNCE_SECONDS = 60
POLL_SECONDS = 10


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
    r = subprocess.run(["git"] + args, capture_output=True, text=True,
                       cwd=BASE_DIR, encoding="utf-8")
    return r.stdout.strip(), r.stderr.strip(), r.returncode


# ── lockfile (multi-instance 차단) ────────────────────────────────────────────

def acquire_lock() -> bool:
    if LOCK_FILE.exists():
        try:
            pid = int((LOCK_FILE.read_text(encoding="utf-8").strip() or "0"))
        except Exception:
            pid = 0
        alive = False
        if pid > 0:
            try:
                if os.name == "nt":
                    import ctypes
                    h = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
                    if h:
                        ctypes.windll.kernel32.CloseHandle(h)
                        alive = True
                else:
                    os.kill(pid, 0); alive = True
            except Exception:
                alive = False
        if alive:
            log(f"이미 실행 중 (PID={pid}) — 새 인스턴스 종료")
            return False
        log(f"stale lock 정리 (PID={pid})")
        try: LOCK_FILE.unlink()
        except Exception: pass
    LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    return True


def release_lock():
    try:
        if LOCK_FILE.exists() and LOCK_FILE.read_text(encoding="utf-8").strip() == str(os.getpid()):
            LOCK_FILE.unlink()
    except Exception:
        pass


# ── 상태 헬퍼 ────────────────────────────────────────────────────────────────

def has_changes() -> bool:
    out, _, _ = git(["status", "--porcelain"])
    return bool(out.strip())


def get_changed_files() -> list:
    out, _, _ = git(["status", "--porcelain"])
    return [l[3:].strip() for l in out.splitlines() if l.strip()]


def ahead_behind() -> tuple:
    """origin/master 대비 (ahead, behind) — fetch 후 사용."""
    out, _, code = git(["rev-list", "--left-right", "--count", "HEAD...origin/master"])
    if code != 0:
        return (0, 0)
    parts = out.split()
    return (int(parts[0]), int(parts[1])) if len(parts) >= 2 else (0, 0)


# ── 핵심: commit-first 동기화 ────────────────────────────────────────────────

def sync_cycle():
    """변경이 있으면 add+commit. 그 다음 fetch → behind면 pull --rebase → push."""
    changed = get_changed_files() if has_changes() else []

    # 1) local WIP가 있으면 먼저 commit
    if changed:
        # ★ REVIEW_FIX-11 (2026-06-14): git add -A 폐기.
        # 81fc357 사고 (KNHANES raw 2.5GB git 오염) 후 가드 박음.
        # (a) .gitignore 존중: git status로 보이는 것만 stage 후보
        # (b) 50MB 사이즈 가드: 단일 파일이 50MB 넘으면 skip + log
        # (c) 데이터 path 명시 차단 (data/raw/, data/oa_papers/, *.sav, *.dta, *.zip)
        BANNED_PATHS = ("data/raw/", "data/oa_papers/", "data/chromadb/",
                          "data/runtime/", "data/.hf_cache/",
                          "data/research_states/", "data/library/")
        BANNED_EXTS = (".sav", ".dta", ".sas7bdat", ".zip",
                         ".db", ".db-shm", ".db-wal")
        # ★ FIX-11 ④-bis 보강 (2026-06-16): 임시 위치(data/ root)에 떨어지는 PMC 패턴
        # restore_oa_papers_from_hf.py가 data/ root에 임시 다운로드 후 oa_papers/로 이동
        # 그 사이 auto-sync가 가로채는 사고 영구 차단.
        BANNED_NAME_PREFIXES = ("PMC",)
        BANNED_NAME_SUFFIXES = (".txt", ".meta.json")
        SIZE_CAP = 50 * 1024 * 1024  # 50MB
        safe_files: list[str] = []
        skipped: list[str] = []
        for f in changed:
            # banned path/ext
            if any(f.startswith(b) or f.replace("\\", "/").startswith(b)
                   for b in BANNED_PATHS):
                skipped.append(f"path:{f}")
                continue
            if any(f.lower().endswith(e) for e in BANNED_EXTS):
                skipped.append(f"ext:{f}")
                continue
            # ★ PMC*.txt / PMC*.meta.json 임시 위치 가드 (어디 있든 차단)
            fname = f.replace("\\", "/").split("/")[-1]
            if (any(fname.startswith(p) for p in BANNED_NAME_PREFIXES) and
                any(fname.endswith(s) for s in BANNED_NAME_SUFFIXES)):
                skipped.append(f"pmc:{f}")
                continue
            # size guard
            try:
                fp = BASE_DIR / f
                if fp.exists() and fp.is_file() and fp.stat().st_size > SIZE_CAP:
                    skipped.append(f"size:{f} ({fp.stat().st_size//1024//1024}MB)")
                    continue
            except Exception:
                pass
            safe_files.append(f)
        if skipped:
            log(f"  ⚠ banned/oversized skip ({len(skipped)}): {skipped[:3]} ...")
        if not safe_files:
            log("  • no safe files to stage (all skipped) — cycle 끝")
            return
        summary = ", ".join(safe_files[:5])
        if len(safe_files) > 5:
            summary += f" 외 {len(safe_files)-5}개"
        ts = datetime.now().strftime("%m/%d %H:%M")
        msg = f"Auto-sync [{ts}]: {summary}"
        # whitelist add (not -A)
        for f in safe_files:
            git(["add", "--", f])
        out, err, code = git(["commit", "-m", msg])
        if code != 0:
            log(f"  커밋 스킵 (no diff/hook): {err or out}")
        else:
            log(f"  ✓ 커밋: {msg[:90]}")

    # 2) fetch — 원격 변경 여부 확인 (commit 후 트리는 clean)
    _, ferr, fcode = git(["fetch", "origin", "master"])
    if fcode != 0:
        log(f"  ✗ FETCH 실패 (네트워크?): {ferr[:80]}")
        return

    ahead, behind = ahead_behind()

    # 3) 원격이 앞서면 rebase (clean 트리이므로 stash 불필요)
    if behind > 0:
        log(f"  원격 {behind}개 앞섬 → pull --rebase")
        out, err, code = git(["pull", "--rebase", "origin", "master"])
        if code != 0:
            # rebase conflict — abort 후 다음 cycle 재시도 (현재 commit은 보존됨)
            git(["rebase", "--abort"])
            log(f"  ✗ REBASE conflict → abort, 다음 cycle 재시도: {err[:80]}")
            return
        log(f"  ✓ PULL --rebase: {out[:80] or 'ok'}")
        ahead, behind = ahead_behind()

    # 4) push (ahead가 있을 때만)
    if ahead > 0:
        out, err, code = git(["push", "origin", "master"])
        if code == 0:
            log(f"  ✓ PUSH ({ahead}개 commit)")
            return
        # push 실패: 원격이 사이에 또 앞서갔을 수 있음 — 한 번 더 시도
        log(f"  ✗ PUSH 1차 실패 (race?) → fetch+rebase+retry: {err[:80]}")
        git(["fetch", "origin", "master"])
        _, err2, code2 = git(["pull", "--rebase", "origin", "master"])
        if code2 != 0:
            git(["rebase", "--abort"])
            log(f"  ✗ 2차 rebase 실패 → 다음 cycle: {err2[:80]}")
            return
        _, err3, code3 = git(["push", "origin", "master"])
        log(f"  {'✓ PUSH 재시도 성공' if code3 == 0 else f'✗ PUSH 재시도 실패: {err3[:80]}'}")


def main():
    log("=" * 50)
    log("Medical-Agent 자동 동기화 시작 (v3 commit-first)")
    log(f"  base: {BASE_DIR}")
    log(f"  디바운스: {DEBOUNCE_SECONDS}초 | 폴링: {POLL_SECONDS}초 | stash 0 의존")
    log("=" * 50)

    if not acquire_lock():
        sys.exit(0)

    # 부팅 catchup
    sync_cycle()

    last_change_time = None
    last_known_status = ""
    try:
        while True:
            time.sleep(POLL_SECONDS)
            try:
                out, _, _ = git(["status", "--porcelain"])
                current = out.strip()
                if current != last_known_status:
                    if current:
                        log(f"  변경 감지 ({len(current.splitlines())}개) — {DEBOUNCE_SECONDS}초 후 동기화")
                        last_change_time = time.time()
                    last_known_status = current
                if last_change_time and (time.time() - last_change_time >= DEBOUNCE_SECONDS):
                    sync_cycle()
                    last_change_time = None
                    last_known_status = ""
            except Exception as e:
                log(f"  loop 오류: {e}")
    finally:
        release_lock()


if __name__ == "__main__":
    main()
