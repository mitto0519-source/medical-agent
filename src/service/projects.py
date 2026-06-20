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


def list_projects(owner_email: str = "") -> list[dict]:
    """Supabase ma_working_papers + 로컬 working_papers/*.json 통합.

    ★ 2026-06-21 Phase 1: ez_home._load_projects 순수 추출 (Streamlit 의존 0).
    · gradient 양식 UI 양식은 caller (ez_home)에서 추가 — service는 raw data만.
    · FastAPI /projects도 동일 함수 호출 가능.

    Args:
        owner_email: 사용자 이메일 (Supabase ma_working_papers.owner_email 필터).
                     빈 문자열이면 전 사용자 LIMIT 20 양식.

    Returns:
        [{"id": ..., "title": ..., "edited": ..., "status": ..., "mtime": ...}, ...]
        mtime 내림차순 정렬, 빈 title 양식 제거, 상위 30개.
    """
    out: list[dict] = []
    seen_ids: set = set()

    # 1) Supabase (있으면 우선)
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text as _sql
            with get_engine().connect() as conn:
                if owner_email:
                    rows = conn.execute(_sql(
                        "SELECT id, title, updated_at, data_json FROM ma_working_papers "
                        "WHERE owner_email=:oe ORDER BY updated_at DESC LIMIT 50"),
                        {"oe": owner_email}).mappings().all()
                else:
                    rows = conn.execute(_sql(
                        "SELECT id, title, updated_at, data_json FROM ma_working_papers "
                        "ORDER BY updated_at DESC LIMIT 20")).mappings().all()
            for r in rows:
                pid = r["id"]
                if pid in seen_ids:
                    continue
                raw_title = (r["title"] or "").strip()
                ts = r["updated_at"] or 0
                # title fallback (chat_xxx, '새 작업' 등 placeholder는 첫 user msg로)
                meaningful_title = (raw_title and raw_title != pid
                                       and not raw_title.startswith("chat_")
                                       and raw_title not in ("새 작업","새 대화","제목 없음","Untitled"))
                fallback_used = False
                if not meaningful_title:
                    try:
                        dj = r.get("data_json") or {}
                        if isinstance(dj, str):
                            dj = json.loads(dj)
                        msgs = (dj or {}).get("messages") or []
                        for m in msgs:
                            if m.get("role") == "user" and m.get("content"):
                                raw_title = m["content"][:60].strip()
                                fallback_used = True
                                break
                        if not fallback_used:
                            secs = (dj or {}).get("sections") or {}
                            for k in ("Abstract","abstract","Introduction","introduction","full"):
                                v = secs.get(k)
                                if isinstance(v, str) and v.strip():
                                    raw_title = v.strip()[:60]
                                    fallback_used = True
                                    break
                    except Exception:
                        pass
                if not raw_title or raw_title == pid or raw_title.startswith("chat_"):
                    continue
                seen_ids.add(pid)
                title = raw_title[:60]
                edited = (datetime.fromtimestamp(ts).strftime("Edited %Y-%m-%d")
                            if ts else "Edited (cloud)")
                out.append({"id": pid, "title": title, "edited": edited,
                              "status": "☁ Cloud",
                              "mtime": float(ts) if ts else 0.0})
    except Exception as e:
        _log.debug("Supabase list_projects fail: %s", e)

    # 2) 로컬 working_papers/*.json (보조)
    if _PROJECTS_DIR.exists():
        all_jsons = list(_PROJECTS_DIR.glob("*.json")) + list(_PROJECTS_DIR.glob("*/*.json"))
        for jp in sorted(all_jsons, key=lambda p: p.stat().st_mtime, reverse=True):
            pid = jp.stem
            if pid in seen_ids:
                continue
            try:
                data = json.loads(jp.read_text(encoding="utf-8"))
                raw_title = (data.get("title") or
                              (data.get("topic") or {}).get("title") or "").strip()
                n_msgs = len(data.get("messages") or [])
                has_sections = bool(data.get("sections"))
                meaningful = (n_msgs > 0 or has_sections or
                                (raw_title and raw_title not in
                                  ("새 작업", "새 대화", "제목 없음", "Untitled")))
                if not meaningful:
                    continue
                if not raw_title or raw_title == pid or raw_title.startswith("chat_"):
                    for m in (data.get("messages") or []):
                        if m.get("role") == "user" and m.get("content"):
                            raw_title = m["content"][:60].strip()
                            break
                title = (raw_title or "(제목 없음)")[:60]
                mtime = jp.stat().st_mtime
                edited = datetime.fromtimestamp(mtime).strftime("Edited %Y-%m-%d")
                status = "Published" if data.get("status") == "published" else ""
                seen_ids.add(pid)
                out.append({"id": pid, "title": title, "edited": edited,
                              "status": status, "n_msgs": n_msgs, "mtime": mtime})
            except Exception:
                continue

    # mtime 내림차순 + 빈 title 제거 + 상위 30개
    out.sort(key=lambda p: p.get("mtime") or 0, reverse=True)
    out = [p for p in out
              if p.get("title") and p["title"].strip() not in
              ("새 작업", "새 대화", "제목 없음", "Untitled", "(제목 없음)")]
    return out[:30]


__all__ = ["path_for", "load_or_init", "save", "list_projects"]
