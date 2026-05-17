"""Persistent agent memory — filelock 기반 안전한 JSON 저장소.

두 사용자가 동시에 접근해도 파일이 손상되지 않는다.
  - cross-process: filelock (FileLock)
  - in-process: threading.Lock

모든 save()는 원자적 write (임시파일 → rename)로 부분 기록을 방지한다.
"""
from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_TIMESTAMP = lambda: datetime.now().isoformat(timespec="seconds")


def _atomic_write(path: Path, data: dict) -> None:
    """임시파일에 쓰고 rename → 부분 기록 방지."""
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".tmp_memory_", suffix=".json"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


class AgentMemory:
    """안전한 append-only JSON 메모리 저장소.

    Structure
    ---------
    {
        "ingested_papers": [...],
        "qa_log": [...],
        "summaries": {...},
        "insights": [...],
        "follow_ups": [...]
    }
    """

    def __init__(self, memory_path: str = "data/agent_memory.json"):
        self._path = Path(memory_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._thread_lock = threading.Lock()
        self._file_lock = self._make_file_lock()
        self._state = self._load()

    # ── 파일 잠금 ─────────────────────────────────────────────────────────────

    def _make_file_lock(self):
        lock_path = str(self._path) + ".lock"
        try:
            from filelock import FileLock
            return FileLock(lock_path, timeout=10)
        except ImportError:
            _log.warning(
                "filelock 패키지가 없습니다. cross-process 잠금 없이 동작합니다.\n"
                "  pip install filelock"
            )
            return None

    def _acquire(self):
        if self._file_lock is not None:
            self._file_lock.acquire()

    def _release(self):
        if self._file_lock is not None:
            try:
                self._file_lock.release()
            except Exception:
                pass

    # ── 영속성 ────────────────────────────────────────────────────────────────

    def _load(self) -> Dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError) as e:
                _log.warning(f"memory.json 로드 실패, 빈 메모리로 시작: {e}")
        return {
            "ingested_papers": [],
            "qa_log": [],
            "summaries": {},
            "insights": [],
            "follow_ups": [],
        }

    def save(self) -> None:
        """현재 상태를 디스크에 원자적으로 저장 (thread-safe + process-safe)."""
        with self._thread_lock:
            self._acquire()
            try:
                _atomic_write(self._path, self._state)
            finally:
                self._release()

    def _reload_if_changed(self) -> None:
        """파일이 외부에서 변경됐으면 메모리를 다시 로드 (멀티유저 동기화)."""
        if not self._path.exists():
            return
        try:
            disk_mtime = self._path.stat().st_mtime
            if not hasattr(self, "_last_mtime") or disk_mtime > self._last_mtime:
                with open(self._path, "r", encoding="utf-8") as f:
                    self._state = json.load(f)
                self._last_mtime = disk_mtime
        except Exception:
            pass

    # ── Paper ingestion log ───────────────────────────────────────────────────

    def log_ingest(self, ingest_result: Dict) -> None:
        filename = ingest_result.get("filename", "")
        with self._thread_lock:
            self._acquire()
            try:
                self._reload_if_changed()
                if not any(p["filename"] == filename for p in self._state["ingested_papers"]):
                    self._state["ingested_papers"].append(
                        {**ingest_result, "ingested_at": _TIMESTAMP()}
                    )
                    _atomic_write(self._path, self._state)
            finally:
                self._release()

    def get_ingested_papers(self) -> List[Dict]:
        self._reload_if_changed()
        return list(self._state["ingested_papers"])

    # ── Q&A log ───────────────────────────────────────────────────────────────

    def log_qa(self, question: str, answer: str, sources: List[Dict]) -> None:
        entry = {
            "timestamp": _TIMESTAMP(),
            "question": question,
            "answer": answer,
            "source_files": list({s["metadata"].get("filename", "") for s in sources}),
        }
        with self._thread_lock:
            self._acquire()
            try:
                self._reload_if_changed()
                self._state["qa_log"].append(entry)
                _atomic_write(self._path, self._state)
            finally:
                self._release()

    def get_qa_log(self) -> List[Dict]:
        self._reload_if_changed()
        return list(self._state["qa_log"])

    # ── Summaries ─────────────────────────────────────────────────────────────

    def save_summary(self, filename: str, summary: str) -> None:
        with self._thread_lock:
            self._acquire()
            try:
                self._reload_if_changed()
                self._state["summaries"][filename] = {
                    "summary": summary,
                    "summarised_at": _TIMESTAMP(),
                }
                _atomic_write(self._path, self._state)
            finally:
                self._release()

    def get_summary(self, filename: str) -> Optional[str]:
        self._reload_if_changed()
        entry = self._state["summaries"].get(filename)
        return entry["summary"] if entry else None

    # ── Cross-paper insights ──────────────────────────────────────────────────

    def add_insight(self, insight: str, related_papers: List[str]) -> None:
        entry = {
            "timestamp": _TIMESTAMP(),
            "insight": insight,
            "papers": related_papers,
        }
        with self._thread_lock:
            self._acquire()
            try:
                self._reload_if_changed()
                self._state["insights"].append(entry)
                _atomic_write(self._path, self._state)
            finally:
                self._release()

    def get_insights(self) -> List[Dict]:
        self._reload_if_changed()
        return list(self._state["insights"])

    # ── Follow-up questions ───────────────────────────────────────────────────

    def add_follow_up(self, question: str, reason: str = "") -> None:
        entry = {
            "timestamp": _TIMESTAMP(),
            "question": question,
            "reason": reason,
            "resolved": False,
        }
        with self._thread_lock:
            self._acquire()
            try:
                self._reload_if_changed()
                self._state["follow_ups"].append(entry)
                _atomic_write(self._path, self._state)
            finally:
                self._release()

    def resolve_follow_up(self, index: int) -> None:
        with self._thread_lock:
            self._acquire()
            try:
                self._reload_if_changed()
                if 0 <= index < len(self._state["follow_ups"]):
                    self._state["follow_ups"][index]["resolved"] = True
                    _atomic_write(self._path, self._state)
            finally:
                self._release()

    def get_open_follow_ups(self) -> List[Dict]:
        self._reload_if_changed()
        return [f for f in self._state["follow_ups"] if not f["resolved"]]
