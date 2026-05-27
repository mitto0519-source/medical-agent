"""Prompt Loader — prompts/ 디렉토리에서 system prompt 합성·캐싱·버저닝.

VS Code / Streamlit / MCP 가 모두 같은 prompt source를 쓰도록 단일 진입점.

API:
  load_prompt(task) -> str               # task별 합성 prompt
  load_yoosun_with_exemplars() -> str    # paper_write 전용 (medical_core + yoosun + raw_examples)
  list_prompts() -> list[dict]           # 등록된 prompt + 메타
  get_version(name) -> str               # YAML frontmatter version

YAML frontmatter:
  name / version / applies_to(list) / extends / last_updated / required_for
"""
from __future__ import annotations

import json
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DIR = Path(os.environ.get("PROMPTS_DIR", "prompts"))
_LOCK = threading.Lock()

# task → prompts to compose (medical_core + safety_constraints 항상 포함)
_TASK_COMPOSITION = {
    "paper_write":  ["medical_core", "safety_constraints", "yoosun_style"],
    "paper_writing":["medical_core", "safety_constraints", "yoosun_style"],
    "chat":         ["medical_core", "safety_constraints"],
    "qa":           ["medical_core", "safety_constraints"],
    "fast":         ["medical_core", "safety_constraints"],
    "summary":      ["medical_core", "safety_constraints"],
    "standard":     ["medical_core", "safety_constraints"],
}


# ── frontmatter 파싱 ─────────────────────────────────────────────────────────

_FM_RE = re.compile(r"^---\s*\n(.+?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_md(path: Path) -> tuple:
    """{frontmatter dict, body str} 반환. frontmatter 없으면 ({}, full text)."""
    text = path.read_text(encoding="utf-8")
    m = _FM_RE.match(text)
    if not m:
        return ({}, text)
    fm_raw, body = m.group(1), m.group(2)
    fm: dict = {}
    for line in fm_raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        v = v.strip()
        # list 처리 [a, b, c]
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("'\"") for x in v[1:-1].split(",") if x.strip()]
        fm[k.strip()] = v
    return (fm, body.strip())


@lru_cache(maxsize=32)
def _load_single(name: str) -> tuple:
    """이름으로 단일 prompt md 로드 → (frontmatter, body)."""
    path = _DIR / f"{name}.md"
    if not path.exists():
        _log.warning("prompt 파일 없음: %s", path)
        return ({}, "")
    return _parse_md(path)


def reload_all():
    """캐시 초기화 (파일 수정 후 호출)."""
    _load_single.cache_clear()


# ── 공개 API ──────────────────────────────────────────────────────────────────

def get_version(name: str) -> str:
    fm, _ = _load_single(name)
    return fm.get("version", "0.0.0")


def list_prompts() -> list:
    """prompts/*.md 전수 메타."""
    out = []
    if not _DIR.exists():
        return out
    for p in sorted(_DIR.glob("*.md")):
        fm, _ = _parse_md(p)
        out.append({"file": p.name, "name": fm.get("name", p.stem),
                    "version": fm.get("version", "?"),
                    "applies_to": fm.get("applies_to", []),
                    "required_for": fm.get("required_for", "")})
    return out


def load_prompt(task: str = "standard", *, include_yoosun_exemplars: bool = False) -> str:
    """task에 맞는 system prompt 합성. 항상 medical_core + safety_constraints 포함."""
    names = _TASK_COMPOSITION.get(task, _TASK_COMPOSITION["standard"])
    parts = []
    versions = []
    for n in names:
        fm, body = _load_single(n)
        if body:
            parts.append(f"# === {fm.get('name', n)} v{fm.get('version', '?')} ===\n\n{body}")
            versions.append(f"{n}@{fm.get('version', '?')}")

    # paper_write 시 yoosun_cho.json의 raw_examples 첨부
    if include_yoosun_exemplars or "yoosun_style" in names:
        try:
            prof_path = Path(os.environ.get("AGENT_SELF_DIR", "data/author_profiles")) / ".."
            prof_path = (prof_path / "author_profiles" / "yoosun_cho.json").resolve()
            if not prof_path.exists():
                prof_path = Path("data/author_profiles/yoosun_cho.json")
            if prof_path.exists():
                prof = json.loads(prof_path.read_text(encoding="utf-8"))
                exemplars = prof.get("raw_examples", [])[:3]
                if exemplars:
                    parts.append("# === Author's actual writing (few-shot exemplars) ===\n\n"
                                 + "\n\n---\n\n".join(e[:1200] for e in exemplars))
        except Exception as e:
            _log.debug("yoosun raw_examples 첨부 실패: %s", e)

    composed = "\n\n".join(parts)
    if composed:
        composed = f"<!-- prompts: {', '.join(versions)} -->\n\n" + composed
    return composed


def load_yoosun_with_exemplars() -> str:
    """paper_write 단축 — 항상 exemplars 포함."""
    return load_prompt("paper_write", include_yoosun_exemplars=True)


# NOTE: 과거에 있었던 compose_runtime_system_prompt()는 제거됨 (2026-05-27).
# 같은 합성(versioned prompt + persona + memory)을 `src.llm.claude_client.build_base_system()`이
# 이미 수행한다. 두 경로 공존은 dead code 및 buildup-drift 위험이므로 build_base_system 단일화.
# 외부에서 직접 versioned prompt만 받고 싶을 때는 `load_prompt(task)`를 그대로 호출.
