"""Provenance / Reproducibility fingerprint — 한 실행의 "지문"을 한 곳에 캡처.

배경:
    동일 입력 → 동일 결과를 보장하거나, 최소한 결과 차이의 원인을 사후 추적
    가능하려면 매 LLM/통계/RAG 호출에서 "지금 환경이 무엇이었는가"를 기록해야 한다.
    git_sha · 모델 버전 · 프롬프트 해시 · 데이터셋 MD5 · random seed · env signature.

설계:
    - 작은 헬퍼들의 묶음. 무겁지 않게(외부 IO 최소).
    - 결과는 events.db에 `provenance` 타입으로 append (append-only 감사 무결성).
    - 실패해도 호출자 망가지지 않게 graceful — 감사용 부수효과.

API:
    fp = build_fingerprint(scope="paper_write", prompt=..., dataset=...)
    fp_id = record(fp, task_id=...)
    items = recent(scope=..., n=10)
    lookup(fp_id)
    diff(fp_id_a, fp_id_b) -> {changed_keys, same_keys}
    seed_for(scope, key) -> int  # 결정론적 seed (같은 입력 → 같은 seed)

호출 위치:
    - ClaudeClient.generate() — 자동 (auto_record_llm_call) 헬퍼로
    - StatBridge.analyze() — auto_record_stats
    - AutonomousResearchLoop iter 시작 시
    - paper_writer 섹션 출력 후
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger
from src.runtime import events as _events

_log = get_logger(__name__)


# ── git SHA (lazy + cached) ──────────────────────────────────────────────────

_GIT_SHA: str | None = None


def git_sha(short: bool = True) -> str:
    """현재 HEAD git sha (캐시). 실패 시 빈 문자열."""
    global _GIT_SHA
    if _GIT_SHA is not None:
        return _GIT_SHA[:7] if short else _GIT_SHA
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, timeout=5,
            cwd=Path(__file__).resolve().parent.parent.parent,
        )
        if out.returncode == 0:
            _GIT_SHA = out.stdout.decode("utf-8").strip()
        else:
            _GIT_SHA = ""
    except Exception:
        _GIT_SHA = ""
    return _GIT_SHA[:7] if short else _GIT_SHA


# ── env signature (python, OS, key model libs) ──────────────────────────────

_ENV_SIG: dict | None = None


def env_signature() -> dict:
    """환경 지문 (캐시). python·platform·핵심 패키지 버전."""
    global _ENV_SIG
    if _ENV_SIG is not None:
        return _ENV_SIG
    sig = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    for pkg in ("anthropic", "openai", "google.generativeai",
                "statsmodels", "pyreadstat", "chromadb"):
        try:
            mod = __import__(pkg)
            sig[pkg] = getattr(mod, "__version__", "?")
        except Exception:
            sig[pkg] = "missing"
    _ENV_SIG = sig
    return sig


# ── hashing helpers ─────────────────────────────────────────────────────────

def text_hash(text: str | bytes | None) -> str:
    """SHA-256 hex (앞 16자만). None → 빈 문자열."""
    if text is None:
        return ""
    if isinstance(text, str):
        text = text.encode("utf-8", errors="replace")
    return hashlib.sha256(text).hexdigest()[:16]


def file_md5(path: str | Path, *, max_bytes: int = 50 * 1024 * 1024) -> str:
    """파일 MD5 (최대 50MB 까지만 — 더 크면 head만 해시).

    50MB 초과 시 처음 50MB만 해시 + 파일 크기 포함 → 정확한 MD5 아닌 'fingerprint'.
    데이터셋 무결성 추적용으로 충분.
    """
    p = Path(path)
    if not p.exists() or not p.is_file():
        return ""
    try:
        h = hashlib.md5()
        with p.open("rb") as f:
            data = f.read(max_bytes)
            h.update(data)
        size = p.stat().st_size
        if size > max_bytes:
            h.update(str(size).encode())
            return f"{h.hexdigest()[:16]}~head{max_bytes}of{size}"
        return h.hexdigest()
    except Exception:
        return ""


# ── deterministic seed ───────────────────────────────────────────────────────

def seed_for(scope: str, key: str = "") -> int:
    """결정론적 32-bit seed — 같은 (scope, key) → 같은 seed.

    LLM·통계·랜덤 샘플링이 같은 입력에 같은 결과를 내도록 한다.
    """
    raw = f"{scope}|{key}|{git_sha(short=False) or 'no-git'}".encode("utf-8")
    h = hashlib.sha256(raw).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF  # 31-bit positive


# ── fingerprint builder ──────────────────────────────────────────────────────

def build_fingerprint(
    scope: str,
    *,
    prompt: str | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    provider: str | None = None,
    dataset_path: str | Path | None = None,
    dataset_label: str | None = None,
    seed: int | None = None,
    extra: dict | None = None,
) -> dict:
    """한 호출의 fingerprint를 만든다.

    scope 예: "llm_call", "stat_analysis", "rag_search", "paper_section".
    seed 가 None이면 (scope, prompt_hash)로 결정론적 seed 자동 부여.
    """
    p_hash = text_hash(prompt) if prompt is not None else ""
    s_hash = text_hash(system_prompt) if system_prompt is not None else ""
    ds_md5 = file_md5(dataset_path) if dataset_path else ""
    auto_seed = seed if seed is not None else seed_for(scope, p_hash or dataset_label or "")
    fp = {
        "scope": scope,
        "ts": time.time(),
        "git_sha": git_sha(short=True),
        "env": env_signature(),
        "model": model or "",
        "provider": provider or "",
        "prompt_sha": p_hash,
        "system_prompt_sha": s_hash,
        "dataset_md5": ds_md5,
        "dataset_label": dataset_label or "",
        "seed": int(auto_seed),
    }
    if extra:
        # 외부 key 충돌 방지 (extra. prefix 없이 그대로)
        for k, v in extra.items():
            if k not in fp:
                fp[k] = v
    return fp


# ── record / lookup ──────────────────────────────────────────────────────────

def record(fp: dict, *, task_id: str | None = None, actor: str | None = None) -> int:
    """fingerprint를 events.db에 append. event_id 반환 (실패시 -1)."""
    try:
        return _events.append(
            type="provenance",
            payload=fp,
            task_id=task_id,
            actor=actor or fp.get("scope", "unknown"),
        )
    except Exception as e:
        _log.debug("provenance.record 실패 (무시): %s", e)
        return -1


def recent(scope: str | None = None, n: int = 20) -> list[dict]:
    """최근 provenance 레코드 N개. scope 지정 시 필터."""
    items = _events.find(type="provenance", limit=n * 4)
    if scope:
        items = [e for e in items if (e.get("payload") or {}).get("scope") == scope]
    return items[:n]


def lookup(event_id: int) -> dict | None:
    """event_id로 단일 fingerprint 조회."""
    try:
        import sqlite3
        c = _events._conn()
        row = c.execute("SELECT payload_json FROM events WHERE id=? AND type='provenance'",
                        (event_id,)).fetchone()
        if row:
            return json.loads(row[0])
    except Exception:
        pass
    return None


def diff(fp_a: dict, fp_b: dict) -> dict:
    """두 fingerprint 비교 — 결과 차이의 원인 추적용."""
    keys = set(fp_a.keys()) | set(fp_b.keys())
    changed, same, missing = {}, [], []
    for k in sorted(keys):
        va, vb = fp_a.get(k), fp_b.get(k)
        if va is None or vb is None:
            missing.append(k)
        elif va == vb:
            same.append(k)
        else:
            changed[k] = {"a": va, "b": vb}
    return {"changed": changed, "same": same, "missing": missing}


# ── 자동 helpers (호출 위치에서 한 줄로 끝) ──────────────────────────────────

def auto_record_llm_call(
    provider: str, model: str, prompt: str, system_prompt: str = "",
    *, response_sha: str = "", tokens_in: int = 0, tokens_out: int = 0,
    latency_ms: int = 0, task_id: str | None = None,
) -> int:
    """LLM 호출 직후 한 줄로 fingerprint 기록."""
    fp = build_fingerprint(
        scope="llm_call",
        prompt=prompt, system_prompt=system_prompt,
        model=model, provider=provider,
        extra={
            "response_sha": response_sha,
            "tokens_in": tokens_in, "tokens_out": tokens_out,
            "latency_ms": latency_ms,
        },
    )
    return record(fp, task_id=task_id, actor=f"{provider}:{model}")


def auto_record_stats(
    spec: dict, dataset_path: str | Path | None = None,
    *, task_id: str | None = None,
) -> int:
    """통계 분석 fingerprint — outcome/exposure/confounders + dataset_md5 잠금."""
    label = f"{spec.get('design','?')}|{spec.get('outcome','?')}|{spec.get('exposure','?')}"
    spec_hash = text_hash(json.dumps(spec, sort_keys=True, default=str))
    fp = build_fingerprint(
        scope="stat_analysis",
        dataset_path=dataset_path, dataset_label=label,
        extra={"spec_hash": spec_hash, "spec_keys": sorted(spec.keys())},
    )
    return record(fp, task_id=task_id, actor="StatBridge")


__all__ = [
    "git_sha", "env_signature", "text_hash", "file_md5", "seed_for",
    "build_fingerprint", "record", "recent", "lookup", "diff",
    "auto_record_llm_call", "auto_record_stats",
]
