"""Projects service — 프로젝트 영속화 단일 진입 (Phase 1 추출).

★ 2026-06-21 Phase 1: ez_home._project_path / _load_or_init_project 순수 추출.
  · Streamlit 의존 0 (st.session_state X)
  · 호출부는 ez_home에서 delegate 1줄 → service.projects.X 양식
  · FastAPI도 동일 함수 호출 가능 (api/main.py에서 그대로)

기존 working_paper_store (Supabase) 와는 별도 — 이건 로컬 JSON 단순 양식.
사용자 working_paper_store 양식이 필요한 경우 별도 모듈 사용.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_PROJECTS_DIR = Path("data/runtime/projects")


def path_for(pid: str) -> Path:
    """Project JSON 파일 경로. 디렉토리 자동 생성."""
    _PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    return _PROJECTS_DIR / f"{pid}.json"


def load_or_init(pid: str, initial_title: str = "새 작업") -> dict:
    """기존 project 로드 또는 새 양식 초기화.

    파일 없거나 JSON parse 실패 시 빈 양식 반환 (id/title/messages/sections/updated).
    """
    p = path_for(pid)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            _log.warning("project %s parse fail: %s", pid, e)
    return {
        "id": pid,
        "title": (initial_title or "새 작업")[:60],
        "messages": [],
        "sections": {},
        "updated": datetime.now().isoformat(),
    }


def save(project: dict) -> None:
    """Project 디스크 저장. updated timestamp 자동 갱신."""
    if not project.get("id"):
        _log.warning("save called without project.id — skip")
        return
    project["updated"] = datetime.now().isoformat()
    p = path_for(project["id"])
    try:
        p.write_text(json.dumps(project, ensure_ascii=False, indent=2),
                       encoding="utf-8")
    except Exception as e:
        _log.warning("project %s save fail: %s", project["id"], e)


__all__ = ["path_for", "load_or_init", "save"]
