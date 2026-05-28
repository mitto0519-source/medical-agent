"""Sandbox + autonomous debug loop — frontier agent의 execution recovery 격차.

외부 진단 (2026-05-28): "autonomous debugging loop (error→inspect→patch→rerun→regression)"
미구현 → 본 모듈이 그 layer.

설계:
  · Python 코드를 subprocess sandbox에서 실행 (cwd/env/timeout 격리)
  · 실패 시 stderr 자동 분석 → 패턴 매칭으로 원인 분류 → 가능하면 자동 패치 시도
  · max_iter까지 retry. 모든 step events 기록 → replay.

자동 복구 패턴 (휴리스틱 + LLM 옵션):
  - ModuleNotFoundError → `pip install <module>` 시도 또는 import path 수정
  - SyntaxError / IndentationError → 라인 추출 + 컨텍스트 보고
  - FileNotFoundError → 경로 정규화 시도
  - KeyError / AttributeError → 호출자 컨텍스트 보고

호출:
    from src.runtime.sandbox import run_python, autonomous_repair_loop
    r = run_python("print(2+2)")
    # r = {"ok": True, "stdout":"4\\n", "stderr":"", "exit_code":0, "elapsed_sec":...}

    r = autonomous_repair_loop(
        script="from src.foo import bar\\nbar()",
        max_iter=3,
        repair_fn=None,   # None이면 휴리스틱; 또는 LLM repair callable
    )
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── Run isolation ───────────────────────────────────────────────────────────

def run_python(code: str, *, timeout_sec: int = 30,
                cwd: Optional[str] = None,
                env_extra: Optional[Dict[str, str]] = None,
                argv: Optional[List[str]] = None) -> Dict:
    """단일 Python 코드를 subprocess로 실행. 결과 dict 반환.

    Args:
        code: 실행할 source. import sys 등 자유.
        timeout_sec: SIGKILL 시간.
        cwd: 작업 디렉토리 (기본 repo root).
        env_extra: 추가 env vars.
        argv: sys.argv (기본 [tmp.py]).

    Returns:
        {"ok": bool, "stdout": str, "stderr": str, "exit_code": int,
         "elapsed_sec": float, "tmp_path": str}
    """
    txn = uuid.uuid4().hex[:10]
    tmp_dir = Path(tempfile.gettempdir()) / "ma_sandbox"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"sb_{txn}.py"
    tmp_path.write_text(code, encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    if env_extra:
        env.update(env_extra)

    cmd = [sys.executable, "-X", "utf8", str(tmp_path)] + (argv or [])
    t0 = time.time()
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                            timeout=timeout_sec, cwd=cwd or os.getcwd(),
                            env=env, encoding="utf-8", errors="replace")
        elapsed = round(time.time() - t0, 3)
        result = {
            "ok": p.returncode == 0,
            "stdout": (p.stdout or "")[-8000:],
            "stderr": (p.stderr or "")[-8000:],
            "exit_code": p.returncode,
            "elapsed_sec": elapsed,
            "tmp_path": str(tmp_path),
        }
    except subprocess.TimeoutExpired:
        elapsed = round(time.time() - t0, 3)
        result = {"ok": False, "stdout": "", "stderr": f"TIMEOUT after {timeout_sec}s",
                   "exit_code": -1, "elapsed_sec": elapsed, "tmp_path": str(tmp_path)}
    except Exception as e:
        result = {"ok": False, "stdout": "", "stderr": f"SUBPROCESS ERROR: {e}",
                   "exit_code": -1, "elapsed_sec": round(time.time() - t0, 3),
                   "tmp_path": str(tmp_path)}

    try:
        from src.runtime import events as _events
        _events.append("sandbox_run",
                        {"txn": txn, "ok": result["ok"], "exit": result["exit_code"],
                         "elapsed_sec": result["elapsed_sec"],
                         "stderr_head": result["stderr"][:160]},
                        actor="sandbox")
    except Exception:
        pass
    return result


# ── Heuristic root-cause classifier ─────────────────────────────────────────

_ERR_PATTERNS = [
    (re.compile(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]"),
     "missing_module"),
    (re.compile(r"ImportError: cannot import name ['\"]([^'\"]+)['\"] from"),
     "missing_import_symbol"),
    (re.compile(r"FileNotFoundError: \[Errno 2\][^']*'([^']+)'"),
     "missing_file"),
    (re.compile(r"(SyntaxError|IndentationError): ([^\n]+)"),
     "syntax"),
    (re.compile(r"KeyError: ['\"]([^'\"]+)['\"]"),
     "missing_key"),
    (re.compile(r"AttributeError: [^\n]+has no attribute ['\"]([^'\"]+)['\"]"),
     "missing_attr"),
    (re.compile(r"TypeError: [^\n]+"),
     "type_error"),
    (re.compile(r"PermissionError: \[Errno 13\][^\n]+"),
     "permission"),
    (re.compile(r"sqlite3\.OperationalError: ([^\n]+)"),
     "sqlite_op"),
    (re.compile(r"requests\.exceptions\.(?:Timeout|ConnectionError)"),
     "network"),
    (re.compile(r"TIMEOUT after \d+s"),
     "timeout"),
]


def classify_error(stderr: str) -> Dict:
    """stderr → {kind, detail, hint}. unknown이면 첫 줄만 반환."""
    if not stderr:
        return {"kind": "unknown", "detail": "", "hint": ""}
    for pat, kind in _ERR_PATTERNS:
        m = pat.search(stderr)
        if m:
            detail = m.group(1) if m.lastindex else ""
            hint = _HINTS.get(kind, "")
            return {"kind": kind, "detail": detail, "hint": hint}
    first_line = stderr.strip().splitlines()[-1] if stderr.strip() else ""
    return {"kind": "unknown", "detail": first_line[:200], "hint": ""}


_HINTS = {
    "missing_module":      "Install via `pip install {detail}` or check sys.path",
    "missing_import_symbol": "Check src/__init__.py exports or use the correct module path",
    "missing_file":        "Verify path; create parent dirs; check cwd",
    "syntax":              "Open the file at the indicated line and fix the syntax",
    "missing_key":         "dict.get(key, default) or check upstream payload",
    "missing_attr":        "Object lacks attribute; check class definition or instance type",
    "type_error":          "Argument types mismatch — verify call signature",
    "permission":          "File/dir permission denied; check ownership or read-only volume",
    "sqlite_op":           "DB locked/schema mismatch — run migrate or close connections",
    "network":             "External service unreachable; retry with backoff or use cache",
    "timeout":             "Increase timeout or split work into smaller batches",
}


# ── Heuristic auto-repair ───────────────────────────────────────────────────

def heuristic_repair(code: str, error_info: Dict) -> Optional[str]:
    """간단한 자동 패치 시도. 가능하면 새 code 반환, 불가능하면 None.

    현재 지원:
      - missing_module: 'try: import X\\nexcept: pass' wrapper (실 install은 안 함)
      - missing_attr/key: 호출 부분에 .get() 또는 hasattr 가드 (단순 sed)
    """
    kind = error_info.get("kind")
    detail = error_info.get("detail") or ""
    if kind == "missing_module":
        # 단순 install (위험) 대신 try/except 가드만 wrap → 사용자가 직접 install 결정
        return (f"# heuristic repair: missing module '{detail}' guard\n"
                f"try:\n    import {detail}  # noqa: F401\n"
                f"except ImportError:\n    pass\n\n" + code)
    if kind == "missing_key":
        # dict["X"] → dict.get("X") (정밀 X — 보고만)
        return re.sub(
            rf"\[\s*['\"]({re.escape(detail)})['\"]\s*\]",
            r".get('\1')", code, count=2)
    return None


# ── Autonomous repair loop ──────────────────────────────────────────────────

def autonomous_repair_loop(script: str, *, max_iter: int = 3,
                            repair_fn: Optional[Callable[[str, Dict], Optional[str]]] = None,
                            timeout_sec: int = 30) -> Dict:
    """error → classify → repair → rerun → max_iter까지.

    Args:
        script: 실행할 코드.
        repair_fn: (code, error_info) → patched_code | None.
                    None이면 heuristic_repair.
        max_iter: 최대 시도 수 (성공하면 즉시 중단).
    """
    repair_fn = repair_fn or heuristic_repair
    history: List[Dict] = []
    current = script
    last_result: Optional[Dict] = None

    for i in range(max(1, max_iter)):
        r = run_python(current, timeout_sec=timeout_sec)
        last_result = r
        step = {"iter": i + 1, "ok": r["ok"], "exit": r["exit_code"],
                 "stderr_head": r["stderr"][:200]}
        if r["ok"]:
            history.append(step)
            break
        info = classify_error(r["stderr"])
        step["error_info"] = info
        try:
            from src.runtime import events as _events
            _events.append("repair_attempt",
                            {"iter": i + 1, "kind": info["kind"],
                             "detail": info["detail"]},
                            actor="sandbox")
        except Exception:
            pass
        patched = repair_fn(current, info)
        if not patched or patched == current:
            step["repair"] = "no_patch_available"
            history.append(step)
            break
        step["repair"] = "applied"
        history.append(step)
        current = patched

    return {
        "final_ok": last_result["ok"] if last_result else False,
        "iterations": len(history),
        "history": history,
        "final_stdout": (last_result or {}).get("stdout", "")[-2000:],
        "final_stderr": (last_result or {}).get("stderr", "")[-2000:],
        "final_code": current if (last_result and not last_result["ok"]) else "",
    }


# ── Regression check ────────────────────────────────────────────────────────

def regression_compare(before_output: str, after_output: str,
                        *, max_diff_chars: int = 200) -> Dict:
    """before vs after 출력 비교. 단순 diff size + first divergent line."""
    if before_output == after_output:
        return {"regression": False, "identical": True}
    # 첫 줄 diff
    bl = before_output.splitlines()
    al = after_output.splitlines()
    first_diff = None
    for i, (bb, aa) in enumerate(zip(bl, al)):
        if bb != aa:
            first_diff = {"line": i + 1, "before": bb[:200], "after": aa[:200]}
            break
    if first_diff is None and len(bl) != len(al):
        first_diff = {"line": min(len(bl), len(al)) + 1,
                       "before": (bl[-1] if bl else ""),
                       "after": (al[-1] if al else "")}
    return {
        "regression": True,
        "identical": False,
        "before_len": len(before_output),
        "after_len": len(after_output),
        "first_diff": first_diff,
    }
