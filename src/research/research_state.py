"""ResearchState — 논문 프로젝트 단일 진실원본 (State Registry / JSON AST).

조언("research OS")의 핵심: 흩어진 session_state 대신, 논문을 **하나의 구조화 상태**로 관리.
모든 단계(생성/검증/심사/통계/인용)는 이 state만 읽고 수정한다 → drift·덮어쓰기·context 충돌 차단.

논문 = JSON AST:
  sections[key] = {content, status, updated_at, source}
    status: empty(빈) | draft(초안) | verified(검증됨) | locked(잠금-덮어쓰기 금지)
  + study(연구정보) + stat_result(실분석) + citations + reviewer_feedback + stage

전면 재작성 아님 — 기존 working_paper_store가 이 state를 영속화하고,
작업실은 잠금/상태를 이 규칙으로 강제한다. (제자리 진화)
"""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

SECTION_KEYS = ["title", "abstract", "introduction", "methods", "results", "discussion"]
SECTION_LABELS = {
    "title": "제목", "abstract": "Abstract", "introduction": "Introduction",
    "methods": "Methods", "results": "Results", "discussion": "Discussion",
}
# 섹션 상태 — locked/verified는 자동 생성이 덮어쓰지 못한다
STATUS = ("empty", "draft", "verified", "locked")
_PROTECTED = ("verified", "locked")  # 자동 덮어쓰기 금지 상태


class ResearchState:
    """논문 프로젝트 상태 레지스트리 (JSON 직렬화 가능)."""

    def __init__(self, owner_email: str = "", paper_id: Optional[str] = None):
        self.owner_email = owner_email
        self.paper_id = paper_id
        self.study: Dict[str, str] = {}                # exposure/outcome/population/dataset/summary
        self.sections: Dict[str, Dict] = {
            k: {"content": "", "status": "empty", "updated_at": 0.0, "source": ""}
            for k in SECTION_KEYS
        }
        self.stat_result: Optional[Dict] = None
        self.citations: List[Dict] = []
        self.reviewer_feedback: List[Dict] = []
        self.stage: str = "draft"
        self.updated_at: float = time.time()

    # ── 섹션 (잠금/검증 규칙 강제) ────────────────────────────────────────
    def can_write(self, key: str) -> bool:
        """자동 생성이 이 섹션을 덮어써도 되는가? (verified/locked면 금지)"""
        return self.sections.get(key, {}).get("status", "empty") not in _PROTECTED

    def set_section(self, key: str, content: str, source: str = "ai",
                    force: bool = False) -> bool:
        """섹션 내용 설정. 보호 상태(verified/locked)면 force 아닌 한 거부. 성공 시 True."""
        if key not in self.sections:
            self.sections[key] = {"content": "", "status": "empty", "updated_at": 0.0, "source": ""}
        if not force and not self.can_write(key):
            return False
        s = self.sections[key]
        s["content"] = content or ""
        s["status"] = "draft" if (content or "").strip() else "empty"
        s["updated_at"] = time.time()
        s["source"] = source
        self.updated_at = time.time()
        return True

    def get_section(self, key: str) -> str:
        return self.sections.get(key, {}).get("content", "")

    def status_of(self, key: str) -> str:
        return self.sections.get(key, {}).get("status", "empty")

    def set_status(self, key: str, status: str):
        if key in self.sections and status in STATUS:
            self.sections[key]["status"] = status
            self.updated_at = time.time()

    def lock(self, key: str):
        self.set_status(key, "locked")

    def unlock(self, key: str):
        # 잠금 해제 시 내용 유무에 따라 draft/empty
        if key in self.sections:
            self.set_status(key, "draft" if self.sections[key]["content"].strip() else "empty")

    def mark_verified(self, key: str):
        self.set_status(key, "verified")

    def locked_keys(self) -> List[str]:
        return [k for k in self.sections if self.status_of(k) in _PROTECTED]

    # ── 통계/인용/심사 ───────────────────────────────────────────────────
    def set_stat_result(self, r: Optional[Dict]):
        self.stat_result = r
        self.updated_at = time.time()

    def add_review(self, reviewer: str, score: Any, concerns: List[str]):
        self.reviewer_feedback.append({
            "reviewer": reviewer, "score": score,
            "concerns": concerns, "at": time.time()})

    # ── 조립 / 직렬화 ────────────────────────────────────────────────────
    def to_markdown(self) -> str:
        parts = []
        for k in SECTION_KEYS:
            v = self.get_section(k).strip()
            if not v:
                continue
            parts.append(f"# {v}" if k == "title" else f"## {SECTION_LABELS[k]}\n\n{v}")
        return "\n\n".join(parts)

    def filled_count(self) -> int:
        return sum(1 for k in SECTION_KEYS if self.get_section(k).strip())

    def to_dict(self) -> Dict:
        return {
            "paper_id": self.paper_id, "owner_email": self.owner_email,
            "title": self.get_section("title") or self.study.get("title", ""),
            "study": self.study, "sections": self.sections,
            "stat_result": self.stat_result, "citations": self.citations,
            "reviewer_feedback": self.reviewer_feedback,
            "stage": self.stage, "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ResearchState":
        st = cls(owner_email=d.get("owner_email", ""), paper_id=d.get("paper_id"))
        st.study = d.get("study", {}) or {}
        # sections: 신형(dict) 또는 구형({key: "텍스트"}) 모두 수용 (하위호환)
        secs = d.get("sections", {}) or {}
        for k in SECTION_KEYS:
            v = secs.get(k)
            if isinstance(v, dict):
                st.sections[k] = {
                    "content": v.get("content", ""),
                    "status": v.get("status", "draft" if v.get("content", "").strip() else "empty"),
                    "updated_at": v.get("updated_at", 0.0), "source": v.get("source", ""),
                }
            elif isinstance(v, str):  # 구형 포맷
                st.sections[k] = {"content": v, "status": "draft" if v.strip() else "empty",
                                  "updated_at": 0.0, "source": "legacy"}
        st.stat_result = d.get("stat_result")
        st.citations = d.get("citations", []) or []
        st.reviewer_feedback = d.get("reviewer_feedback", []) or []
        st.stage = d.get("stage", "draft")
        st.updated_at = d.get("updated_at", time.time())
        return st

    # ── Streamlit 세션 브리지 (작업실 ws_* 키와 동기화) ──────────────────
    def to_session(self, ss):
        """state → st.session_state (작업실 편집 위젯이 읽도록)."""
        for k in SECTION_KEYS:
            ss[f"ws_{k}"] = self.get_section(k)
        ss["ws_status"] = {k: self.status_of(k) for k in SECTION_KEYS}
        ss["ws_paper_id"] = self.paper_id
        if self.stat_result is not None:
            ss["stat_result_for_paper"] = self.stat_result
        for sk, val in self.study.items():
            if val:
                ss[f"ws_{sk}"] = val

    @classmethod
    def from_session(cls, ss, owner_email: str = "") -> "ResearchState":
        """st.session_state → state (저장 시)."""
        st = cls(owner_email=owner_email, paper_id=ss.get("ws_paper_id"))
        _status = ss.get("ws_status", {}) or {}
        for k in SECTION_KEYS:
            content = ss.get(f"ws_{k}", "") or ""
            st.sections[k] = {
                "content": content,
                "status": _status.get(k, "draft" if content.strip() else "empty"),
                "updated_at": time.time() if content.strip() else 0.0, "source": "user",
            }
        st.study = {sk: ss.get(f"ws_{sk}", "") for sk in
                    ("exposure", "outcome", "population", "dataset", "summary", "title")}
        st.stat_result = ss.get("stat_result_for_paper")
        return st


# ═══════════════════════════════════════════════════════════════════════════
# ★ RESEARCH_STATE_SPEC 확장 (2026-06-15) — 단일 정본 + 체크포인트/브랜치/resume
# 기존 ResearchState class는 그대로 유지(호환성). module-level 함수로 확장.
# ═══════════════════════════════════════════════════════════════════════════

import json as _json
import uuid as _uuid
from dataclasses import dataclass as _dc, field as _df, asdict as _asdict
from pathlib import Path as _Path
from typing import Optional as _Opt

SCHEMA_VERSION = "1.0.0"
_STATE_DIR = _Path("data/research_states")


@_dc
class ResearchProject:
    """단일 정본 (RESEARCH_STATE_SPEC §1) — ez_home project dict 흡수, 이중쓰기 차단.

    manuscript['sections']가 유일 sections 정본.
    manuscript_text는 property(파생, 저장 X) — 드리프트 차단.
    """
    id: str
    owner_email: str = ""
    title: str = "새 연구"
    schema_version: str = SCHEMA_VERSION
    rq: Dict = _df(default_factory=dict)
    dataset: Dict = _df(default_factory=dict)            # name/year/dataset_version/registry_version
    variable_selection: Dict = _df(default_factory=dict)
    analysis_spec: Dict = _df(default_factory=dict)
    results: Dict = _df(default_factory=dict)
    manuscript: Dict = _df(default_factory=lambda: {"sections": {}})
    citations: List[Dict] = _df(default_factory=list)
    gates: Dict = _df(default_factory=dict)
    provenance_ids: List[int] = _df(default_factory=list)
    checkpoint_id: str = ""
    parent_checkpoint: _Opt[str] = None
    messages: List[Dict] = _df(default_factory=list)
    attachments: List[Dict] = _df(default_factory=list)
    updated_at: str = ""

    @property
    def sections(self) -> Dict:
        return (self.manuscript or {}).setdefault("sections", {})

    @property
    def manuscript_text(self) -> str:
        secs = self.sections
        out: list = []
        for key in ("Abstract", "Introduction", "Methods", "Results",
                      "Discussion", "Conclusion", "References"):
            v = secs.get(key) or secs.get(key.lower())
            if not v:
                continue
            if isinstance(v, dict):
                for sk, sv in v.items():
                    if sv: out.append(f"### {sk}\n{sv}")
            else:
                out.append(f"## {key}\n{v}")
        return "\n\n".join(out)

    def project_to_dict(self) -> Dict:
        d = _asdict(self)
        d["_derived_manuscript_text_len"] = len(self.manuscript_text)
        return d


def _path_for(state_id: str) -> _Path:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)
    return _STATE_DIR / f"{state_id}.json"


def new_project(*, owner_email: str = "", title: str = "새 연구") -> ResearchProject:
    return ResearchProject(
        id=f"rs_{_uuid.uuid4().hex[:12]}",
        owner_email=owner_email,
        title=title[:200],
        updated_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )


def project_save(state: ResearchProject, *, cloud: bool = True) -> None:
    """로컬 먼저 + Supabase 베스트 에프트."""
    state.updated_at = time.strftime("%Y-%m-%dT%H:%M:%S")
    try:
        _path_for(state.id).write_text(
            _json.dumps(state.project_to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8")
    except Exception:
        pass
    if not cloud:
        return
    try:
        from src.cloud.db import cloud_available, get_engine
        if not cloud_available():
            return
        from sqlalchemy import text as _sql
        with get_engine().begin() as conn:
            conn.execute(_sql(
                "INSERT INTO ma_research_state "
                "(id, owner_email, title, schema_version, data_json, updated_at) "
                "VALUES (:id, :oe, :ti, :sv, :dj, :ts) "
                "ON CONFLICT (id) DO UPDATE SET "
                "title=:ti, schema_version=:sv, data_json=:dj, updated_at=:ts"),
                {"id": state.id, "oe": state.owner_email,
                 "ti": state.title[:200], "sv": state.schema_version,
                 "dj": _json.dumps(state.project_to_dict(), ensure_ascii=False),
                 "ts": int(time.time())})
    except Exception:
        pass


def project_load(state_id: str) -> _Opt[ResearchProject]:
    """Supabase 먼저 → 로컬 fallback."""
    try:
        from src.cloud.db import cloud_available, get_engine
        if cloud_available():
            from sqlalchemy import text as _sql
            with get_engine().begin() as conn:
                row = conn.execute(_sql(
                    "SELECT data_json FROM ma_research_state WHERE id=:id"),
                    {"id": state_id}).fetchone()
                if row and row[0]:
                    return _project_from_dict(_json.loads(row[0]))
    except Exception:
        pass
    p = _path_for(state_id)
    if not p.exists():
        return None
    try:
        return _project_from_dict(_json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return None


def _project_from_dict(d: Dict) -> ResearchProject:
    fields = {f.name for f in ResearchProject.__dataclass_fields__.values()}
    clean = {k: v for k, v in (d or {}).items() if k in fields}
    return ResearchProject(**clean)


def from_project_dict(project: Dict) -> ResearchProject:
    """ez_home project dict → ResearchProject. 이중쓰기 흡수."""
    rs = ResearchProject(
        id=project.get("id") or f"rs_{_uuid.uuid4().hex[:12]}",
        owner_email=project.get("owner_email", ""),
        title=project.get("title", "새 연구")[:200],
        messages=project.get("messages") or [],
        attachments=project.get("attachments") or [],
        updated_at=project.get("updated", ""),
    )
    rs.manuscript = {"sections": project.get("sections") or {}}
    legacy = project.get("research_state") or {}
    if legacy.get("pico"):
        rs.rq = {"pico": legacy["pico"]}
    if legacy.get("dataset"):
        rs.dataset = {
            "name": legacy.get("dataset"),
            "year_range": legacy.get("year"),
            "dataset_version": legacy.get("dataset_version", ""),
            "registry_version": legacy.get("registry_version", ""),
        }
    if legacy.get("stat_result"):
        rs.results["estimates"] = legacy["stat_result"]
    if legacy.get("stat_spec"):
        rs.analysis_spec = legacy["stat_spec"]
    if legacy.get("novelty"):
        rs.gates["novelty"] = legacy["novelty"]
    refs = project.get("references") or legacy.get("references") or []
    rs.citations = refs if isinstance(refs, list) else []
    return rs


def to_project_dict(state: ResearchProject) -> Dict:
    """ResearchProject → ez_home project dict (호환성)."""
    return {
        "id": state.id,
        "owner_email": state.owner_email,
        "title": state.title,
        "messages": state.messages,
        "attachments": state.attachments,
        "sections": state.sections,
        "references": state.citations,
        "research_state": {
            "pico": (state.rq or {}).get("pico"),
            "dataset": (state.dataset or {}).get("name"),
            "year": (state.dataset or {}).get("year_range"),
            "dataset_version": (state.dataset or {}).get("dataset_version"),
            "registry_version": (state.dataset or {}).get("registry_version"),
            "stat_spec": state.analysis_spec,
            "stat_result": (state.results or {}).get("estimates"),
            "novelty": (state.gates or {}).get("novelty"),
            # ★ manuscript_text는 파생 — 저장 X (state.manuscript_text 속성)
        },
        "updated": state.updated_at,
    }


# ── 체크포인트 / 브랜치 / resume (events.db append-only) ────────────────────

def _events():
    from src.runtime import events as _e
    return _e


def checkpoint(state: ResearchProject, label: str = "auto",
                  *, provenance_id: _Opt[int] = None) -> str:
    cp_id = f"cp_{_uuid.uuid4().hex[:12]}"
    state.checkpoint_id = cp_id
    project_save(state)
    try:
        _events().append(
            type="research_checkpoint",
            payload={
                "cp_id": cp_id, "state_id": state.id, "label": label,
                "snapshot": state.project_to_dict(),
                "parent": state.parent_checkpoint,
                "provenance_id": provenance_id, "ts": time.time(),
            },
            task_id=state.id, actor="research_state",
        )
    except Exception:
        pass
    return cp_id


def list_checkpoints(state_id: str, *, limit: int = 50) -> List[Dict]:
    try:
        items = _events().find(type="research_checkpoint",
                                  task_id=state_id, limit=limit * 2)
    except Exception:
        return []
    return [{
        "cp_id": (ev.get("payload") or {}).get("cp_id"),
        "label": (ev.get("payload") or {}).get("label"),
        "ts": (ev.get("payload") or {}).get("ts"),
        "parent": (ev.get("payload") or {}).get("parent"),
    } for ev in items[:limit]]


def restore(cp_id: str) -> _Opt[ResearchProject]:
    try:
        items = _events().find(type="research_checkpoint", limit=500)
    except Exception:
        return None
    for ev in items:
        pl = ev.get("payload") or {}
        if pl.get("cp_id") == cp_id and pl.get("snapshot"):
            state = _project_from_dict(pl["snapshot"])
            state.parent_checkpoint = cp_id
            project_save(state)
            return state
    return None


def branch(cp_id: str, new_title: str = "분기") -> _Opt[ResearchProject]:
    state = restore(cp_id)
    if state is None:
        return None
    state.id = f"rs_{_uuid.uuid4().hex[:12]}"
    state.title = f"{new_title} ({state.title})"[:200]
    state.parent_checkpoint = cp_id
    project_save(state)
    try:
        _events().append(
            type="research_branch",
            payload={"new_state_id": state.id, "from_cp": cp_id, "ts": time.time()},
            task_id=state.id, actor="research_state",
        )
    except Exception:
        pass
    return state


def resume(state_id: str) -> _Opt[ResearchProject]:
    return project_load(state_id)


def diff(cp_a: str, cp_b: str) -> Dict:
    sa = restore(cp_a)
    sb = restore(cp_b)
    if sa is None or sb is None:
        return {"error": "checkpoint missing"}
    da, db = sa.project_to_dict(), sb.project_to_dict()
    changed = {}
    for k in set(da.keys()) | set(db.keys()):
        if da.get(k) != db.get(k):
            changed[k] = "differ"
    return {"cp_a": cp_a, "cp_b": cp_b, "changed_fields": changed}
