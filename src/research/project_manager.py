"""Project Manager — 연구 주제별 파이프라인 진행 상태 영속적 추적.

각 연구 프로젝트를 data/projects/{project_id}.json에 저장하고
전체 인덱스를 data/projects/index.json으로 관리한다.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_PROJ_DIR = Path("data/projects")
_PROJ_INDEX = _PROJ_DIR / "index.json"

_STATUS_ORDER = [
    "created",
    "novelty_checked",
    "feasibility_validated",
    "stat_done",
    "draft_written",
    "reviewed",
    "revised",
    "completed",
]


class ProjectManager:
    """연구 파이프라인 프로젝트 상태 영속적 관리.

    Usage:
        pm = get_project_manager()
        pid = pm.create_project(topic, dataset="KYRBS")
        pm.set_novelty_result(pid, novelty_dict)
        pm.set_stat_result(pid, stat_result_dict)
        pm.set_review_result(pid, review_dict)
        pm.set_paths(pid, draft_path="...", docx_path="...")
        projects = pm.list_projects()
    """

    def __init__(self):
        _PROJ_DIR.mkdir(parents=True, exist_ok=True)
        self._index: Dict = self._load_index()

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def create_project(self, topic: Dict, dataset: str = "KYRBS") -> str:
        """새 프로젝트 생성. project_id 반환."""
        title = topic.get("title", "untitled")
        pid = hashlib.md5(f"{title}{datetime.now().isoformat()}".encode()).hexdigest()[:12]
        ts = datetime.now().isoformat()

        project = {
            "id": pid,
            "title": title,
            "topic": topic,
            "dataset": dataset,
            "status": "created",
            "created_at": ts,
            "updated_at": ts,
            "novelty_result": None,
            "feasibility_result": None,
            "stat_result_summary": None,
            "review_result_summary": None,
            "draft_path": None,
            "docx_path": None,
            "stata_path": None,
            "cover_letter_path": None,
            "forest_plot_path": None,
            "history": [{"status": "created", "ts": ts}],
        }
        self._save_project(pid, project)
        self._index[pid] = {
            "title": title,
            "dataset": dataset,
            "status": "created",
            "created_at": ts,
        }
        self._save_index()
        _log.info("프로젝트 생성: %s (%s)", pid, title[:50])
        return pid

    def update_status(self, pid: str, status: str, meta: Optional[Dict] = None):
        """프로젝트 상태 업데이트 + meta dict 병합."""
        project = self.get_project(pid)
        if project is None:
            _log.warning("프로젝트 없음: %s", pid)
            return
        project["status"] = status
        project["updated_at"] = datetime.now().isoformat()
        project["history"].append({
            "status": status,
            "ts": datetime.now().isoformat(),
            "meta": meta or {},
        })
        if meta:
            for k, v in meta.items():
                project[k] = v
        self._save_project(pid, project)
        if pid in self._index:
            self._index[pid]["status"] = status
            self._save_index()

    def set_novelty_result(self, pid: str, result: Dict):
        """신규성 확인 결과 저장."""
        self.update_status(pid, "novelty_checked", {
            "novelty_result": {
                "score": result.get("novelty_score", 0),
                "verdict": str(result.get("verdict", ""))[:200],
            }
        })

    def set_feasibility_result(self, pid: str, result: Dict):
        """타당성 검증 결과 저장."""
        self.update_status(pid, "feasibility_validated", {
            "feasibility_result": {
                "is_feasible": result.get("is_feasible"),
                "confidence": result.get("confidence", ""),
                "verdict": str(result.get("verdict", ""))[:200],
            }
        })

    def set_stat_result(self, pid: str, stat_result: Dict):
        """통계 분석 결과 요약 저장."""
        self.update_status(pid, "stat_done", {
            "stat_result_summary": {
                "n_total": stat_result.get("n_total", 0),
                "n_outcome": stat_result.get("n_outcome", 0),
                "outcome_rate": stat_result.get("outcome_rate", 0),
                "n_significant": len([
                    v for v in stat_result.get("model_vars", [])
                    if v.get("significant")
                ]),
                "analysis_type": stat_result.get("analysis_type", "logistic"),
            }
        })

    def set_review_result(self, pid: str, review: Dict):
        """동료 심사 결과 저장."""
        self.update_status(pid, "reviewed", {
            "review_result_summary": {
                "score": review.get("total_score", 0),
                "grade": review.get("grade", "?"),
                "recommendation": review.get("accept_recommendation", "?"),
            }
        })

    def set_paths(self, pid: str, **paths):
        """파일 경로들 저장 (draft_path, docx_path, stata_path 등)."""
        project = self.get_project(pid)
        if project is None:
            return
        project.update(paths)
        project["updated_at"] = datetime.now().isoformat()
        self._save_project(pid, project)

    def mark_completed(self, pid: str):
        """프로젝트 완료 처리."""
        self.update_status(pid, "completed")

    def get_project(self, pid: str) -> Optional[Dict]:
        """프로젝트 전체 데이터 반환."""
        path = _PROJ_DIR / f"{pid}.json"
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            _log.warning("프로젝트 로드 실패 %s: %s", pid, e)
            return None

    def list_projects(self, status_filter: Optional[str] = None) -> List[Dict]:
        """프로젝트 목록 반환 (최신순). status_filter로 상태별 필터링 가능."""
        items = list(self._index.values())
        if status_filter:
            items = [p for p in items if p.get("status") == status_filter]
        return sorted(items, key=lambda x: x.get("created_at", ""), reverse=True)

    def delete_project(self, pid: str):
        """프로젝트 삭제."""
        path = _PROJ_DIR / f"{pid}.json"
        if path.exists():
            path.unlink()
        self._index.pop(pid, None)
        self._save_index()
        _log.info("프로젝트 삭제: %s", pid)

    def get_summary(self) -> str:
        """전체 프로젝트 상태 요약 문자열."""
        total = len(self._index)
        by_status: Dict[str, int] = {}
        for p in self._index.values():
            s = p.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        lines = [f"총 프로젝트: {total}개"]
        for status in _STATUS_ORDER:
            if status in by_status:
                lines.append(f"  {status}: {by_status[status]}개")
        return "\n".join(lines)

    # ── 내부 ─────────────────────────────────────────────────────────────────

    def _load_index(self) -> Dict:
        if _PROJ_INDEX.exists():
            try:
                return json.loads(_PROJ_INDEX.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_index(self):
        _PROJ_INDEX.write_text(
            json.dumps(self._index, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _save_project(self, pid: str, project: Dict):
        (_PROJ_DIR / f"{pid}.json").write_text(
            json.dumps(project, ensure_ascii=False, indent=2), encoding="utf-8"
        )


# ── 전역 인스턴스 ──────────────────────────────────────────────────────────────

_pm_instance: Optional[ProjectManager] = None


def get_project_manager() -> ProjectManager:
    """전역 ProjectManager 싱글톤 반환."""
    global _pm_instance
    if _pm_instance is None:
        _pm_instance = ProjectManager()
    return _pm_instance
