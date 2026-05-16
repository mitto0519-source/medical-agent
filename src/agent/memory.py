"""Persistent agent memory — survives restarts via JSON on disk.

Every interaction (Q&A, summary, ingest) is logged here so the agent
can recall what it has seen, what it concluded, and what needs follow-up.
The memory grows incrementally; nothing is ever overwritten.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_TIMESTAMP = lambda: datetime.now().isoformat(timespec="seconds")


class AgentMemory:
    """Simple append-only JSON memory store.

    Structure (per file)
    --------------------
    {
        "ingested_papers": [...],   # papers the agent has read
        "qa_log": [...],            # questions asked and answers given
        "summaries": {...},         # filename → summary text
        "insights": [...],          # Claude-generated cross-paper insights
        "follow_ups": [...]         # open questions for future investigation
    }
    """

    def __init__(self, memory_path: str = "data/agent_memory.json"):
        self._path = Path(memory_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._state = self._load()

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def _load(self) -> Dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except json.JSONDecodeError:
                pass
        return {
            "ingested_papers": [],
            "qa_log": [],
            "summaries": {},
            "insights": [],
            "follow_ups": [],
        }

    def save(self):
        """Flush current state to disk."""
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._state, f, ensure_ascii=False, indent=2)

    # ------------------------------------------------------------------
    # Paper ingestion log
    # ------------------------------------------------------------------

    def log_ingest(self, ingest_result: Dict):
        """Record a newly ingested paper."""
        filename = ingest_result.get("filename", "")
        already = any(p["filename"] == filename for p in self._state["ingested_papers"])
        if not already:
            self._state["ingested_papers"].append(
                {**ingest_result, "ingested_at": _TIMESTAMP()}
            )
            self.save()

    def get_ingested_papers(self) -> List[Dict]:
        return self._state["ingested_papers"]

    # ------------------------------------------------------------------
    # Q&A log
    # ------------------------------------------------------------------

    def log_qa(self, question: str, answer: str, sources: List[Dict]):
        """Record a question-answer pair."""
        self._state["qa_log"].append(
            {
                "timestamp": _TIMESTAMP(),
                "question": question,
                "answer": answer,
                "source_files": list({s["metadata"].get("filename", "") for s in sources}),
            }
        )
        self.save()

    def get_qa_log(self) -> List[Dict]:
        return self._state["qa_log"]

    # ------------------------------------------------------------------
    # Summaries
    # ------------------------------------------------------------------

    def save_summary(self, filename: str, summary: str):
        self._state["summaries"][filename] = {
            "summary": summary,
            "summarised_at": _TIMESTAMP(),
        }
        self.save()

    def get_summary(self, filename: str) -> Optional[str]:
        entry = self._state["summaries"].get(filename)
        return entry["summary"] if entry else None

    # ------------------------------------------------------------------
    # Cross-paper insights
    # ------------------------------------------------------------------

    def add_insight(self, insight: str, related_papers: List[str]):
        self._state["insights"].append(
            {
                "timestamp": _TIMESTAMP(),
                "insight": insight,
                "papers": related_papers,
            }
        )
        self.save()

    def get_insights(self) -> List[Dict]:
        return self._state["insights"]

    # ------------------------------------------------------------------
    # Follow-up questions
    # ------------------------------------------------------------------

    def add_follow_up(self, question: str, reason: str = ""):
        self._state["follow_ups"].append(
            {
                "timestamp": _TIMESTAMP(),
                "question": question,
                "reason": reason,
                "resolved": False,
            }
        )
        self.save()

    def resolve_follow_up(self, index: int):
        if 0 <= index < len(self._state["follow_ups"]):
            self._state["follow_ups"][index]["resolved"] = True
            self.save()

    def get_open_follow_ups(self) -> List[Dict]:
        return [f for f in self._state["follow_ups"] if not f["resolved"]]
