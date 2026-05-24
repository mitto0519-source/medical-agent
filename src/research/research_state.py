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
