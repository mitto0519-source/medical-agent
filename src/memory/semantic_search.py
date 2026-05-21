"""Semantic Memory Search — insights.json + 작업 이력을 현재 주제와 키워드 유사도로 검색.

벡터 인프라 없이 작동하는 가벼운 검색 모듈.
현재 주제 키워드와 겹치는 과거 인사이트/이력을 빠르게 추출해
LLM 프롬프트에 컨텍스트로 주입한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_INSIGHTS_PATH = Path("data/agent_self/insights.json")
_HISTORY_PATH = Path("data/change_log/history.json")


class SemanticMemorySearch:
    """인사이트/작업 이력에서 현재 주제와 관련된 항목을 검색.

    Usage:
        sms = SemanticMemorySearch()
        results = sms.search("스마트폰 수면", top_k=3)
        ctx = sms.build_context("스마트폰 수면")
    """

    def __init__(self):
        self._insights: List[Dict] = self._load_insights()
        self._history: List[Dict] = self._load_history()

    # ── 공개 API ─────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """쿼리와 가장 관련성 높은 인사이트/이력 반환.

        Returns:
            [{"source": "insights"|"history", "text": str, "score": float, "tags": list}]
        """
        query_words = set(re.findall(r"\b\w{3,}\b", query.lower()))
        candidates: List[Dict] = []

        # 인사이트 검색
        for item in self._insights:
            text = str(item.get("insight", "")) + " " + str(item.get("context", ""))
            score = self._overlap_score(query_words, text)
            if score > 0:
                candidates.append({
                    "source": "insights",
                    "text": str(item.get("insight", ""))[:300],
                    "score": score,
                    "tags": item.get("tags", []),
                    "action": item.get("action", ""),
                })

        # 작업 이력 검색 (유의미한 것만)
        for item in self._history:
            text = str(item.get("title", "")) + " " + str(item.get("description", ""))
            score = self._overlap_score(query_words, text)
            if score >= 0.3:
                candidates.append({
                    "source": "history",
                    "text": (
                        f"[{item.get('action_type', '')}] "
                        f"{item.get('title', '')}: "
                        f"{str(item.get('description', ''))[:200]}"
                    ),
                    "score": score,
                    "tags": [item.get("action_type", "")],
                    "action": item.get("title", ""),
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]

    def build_context(self, query: str, top_k: int = 3) -> str:
        """검색 결과를 LLM 프롬프트 주입용 문자열로 변환.

        Returns: 관련 과거 인사이트/이력 요약 (없으면 빈 문자열)
        """
        results = self.search(query, top_k=top_k)
        if not results:
            return ""
        lines = ["## Past Research Insights (Topic-Relevant)"]
        for r in results:
            src = r["source"]
            lines.append(f"- [{src}] {r['text']}")
        return "\n".join(lines)

    def reload(self):
        """인사이트/이력 파일 다시 로드 (파일 갱신 후 호출)."""
        self._insights = self._load_insights()
        self._history = self._load_history()

    # ── 내부 ─────────────────────────────────────────────────────────────────

    @staticmethod
    def _overlap_score(query_words: set, text: str) -> float:
        """단어 집합과 텍스트의 키워드 겹침 점수 (0~1)."""
        if not query_words or not text:
            return 0.0
        text_words = set(re.findall(r"\b\w{3,}\b", text.lower()))
        if not text_words:
            return 0.0
        return len(query_words & text_words) / max(len(query_words), 1)

    @staticmethod
    def _load_insights() -> List[Dict]:
        if not _INSIGHTS_PATH.exists():
            return []
        try:
            data = json.loads(_INSIGHTS_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            return data.get("insights", []) if isinstance(data, dict) else []
        except Exception as e:
            _log.debug("insights.json 로드 실패: %s", e)
            return []

    @staticmethod
    def _load_history() -> List[Dict]:
        if not _HISTORY_PATH.exists():
            return []
        try:
            data = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data[-50:]  # 최근 50개만
            return []
        except Exception as e:
            _log.debug("history.json 로드 실패: %s", e)
            return []
