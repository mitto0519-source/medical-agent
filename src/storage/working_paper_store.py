"""Working Paper Store — 사용자가 '작성 중인 논문'을 계정 귀속으로 영속 저장.

논문 작업실의 6개 섹션(title/abstract/introduction/methods/results/discussion)과
연구 메타를 계정별로 저장/불러오기/삭제. 로컬 항상 + 클라우드(가능 시) 동기화.

storage/manager.py(참고문헌 RAG 적재)와 별개 — 이건 '내가 쓰는 논문' 영속성 담당.
세션 종료/컨테이너 재시작에도 data/working_papers/(볼륨 마운트)에 남는다.
"""
from __future__ import annotations

import json
import re
import time
import uuid
from pathlib import Path
from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DIR = Path("data/working_papers")

SECTION_KEYS = ["title", "abstract", "introduction", "methods", "results", "discussion"]


def _safe(email: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", (email or "anon").lower())


def _user_dir(email: str) -> Path:
    d = _DIR / _safe(email)
    d.mkdir(parents=True, exist_ok=True)
    return d


def save_paper(owner_email: str, sections: dict, meta: Optional[dict] = None,
               paper_id: Optional[str] = None) -> str:
    """논문 저장(신규 또는 갱신). paper_id 없으면 신규 생성. 저장된 id 반환."""
    paper_id = paper_id or uuid.uuid4().hex[:12]
    title = (sections.get("title") or "").strip() or (meta or {}).get("title", "") or "제목 없음"
    rec = {
        "id": paper_id, "owner_email": owner_email, "title": title,
        "sections": {k: sections.get(k, "") for k in SECTION_KEYS},
        "meta": meta or {}, "updated_at": time.time(),
    }
    (_user_dir(owner_email) / f"{paper_id}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8")
    _cloud_upsert(rec)  # best-effort
    _log.info("working paper 저장: %s (%s)", paper_id, owner_email)
    return paper_id


def list_papers(owner_email: str, all_papers: bool = False) -> list[dict]:
    """저장 논문 목록(최신순). all_papers=True면 전 계정(admin)."""
    out = []
    dirs = [d for d in _DIR.glob("*") if d.is_dir()] if all_papers else [_user_dir(owner_email)]
    for d in dirs:
        for f in d.glob("*.json"):
            try:
                r = json.loads(f.read_text(encoding="utf-8"))
                out.append({"id": r["id"], "title": r.get("title", ""),
                            "owner_email": r.get("owner_email", ""),
                            "updated_at": r.get("updated_at", 0)})
            except Exception:
                continue
    out.sort(key=lambda r: r.get("updated_at", 0), reverse=True)
    return out


def load_paper(owner_email: str, paper_id: str, all_papers: bool = False) -> Optional[dict]:
    """논문 1건 로드. all_papers=True면 전 계정 탐색(admin)."""
    cands = [_user_dir(owner_email) / f"{paper_id}.json"]
    if all_papers:
        cands += list(_DIR.glob(f"*/{paper_id}.json"))
    for p in cands:
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                return None
    return None


def delete_paper(owner_email: str, paper_id: str, all_papers: bool = False) -> bool:
    cands = [_user_dir(owner_email) / f"{paper_id}.json"]
    if all_papers:
        cands += list(_DIR.glob(f"*/{paper_id}.json"))
    for p in cands:
        if p.exists():
            p.unlink()
            _log.info("working paper 삭제: %s", paper_id)
            return True
    return False


def _cloud_upsert(rec: dict) -> None:
    """클라우드(Supabase) 동기화 — 가능할 때만, 실패해도 로컬은 유지(규칙: 로컬먼저+클라우드)."""
    try:
        from src.cloud.db import cloud_available, get_engine
        if not cloud_available():
            return
        import sqlalchemy as sa
        with get_engine().begin() as conn:
            conn.execute(sa.text(
                "CREATE TABLE IF NOT EXISTS ma_working_papers ("
                "id text PRIMARY KEY, owner_email text, title text, "
                "sections jsonb, meta jsonb, updated_at double precision)"))
            conn.execute(sa.text(
                "INSERT INTO ma_working_papers (id, owner_email, title, sections, meta, updated_at) "
                "VALUES (:id,:oe,:t,:s,:m,:u) "
                "ON CONFLICT (id) DO UPDATE SET title=:t, sections=:s, meta=:m, updated_at=:u"),
                {"id": rec["id"], "oe": rec["owner_email"], "t": rec["title"],
                 "s": json.dumps(rec["sections"], ensure_ascii=False),
                 "m": json.dumps(rec["meta"], ensure_ascii=False), "u": rec["updated_at"]})
    except Exception as e:
        _log.warning("working paper 클라우드 동기화 실패(로컬은 저장됨): %s", str(e)[:120])
