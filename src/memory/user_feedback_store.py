"""User Feedback Store — 실제 저널 리뷰어 피드백 누적 DB.

저장 형식: data/feedback/feedback_store.json
  - 사용자가 직접 붙여넣기한 리뷰어 코멘트를 저장
  - 키워드 오버랩으로 관련 피드백 검색
  - _build_system()에 패턴 주입 → LLM 자동 반영
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_STORE_PATH = Path("data/feedback/feedback_store.json")


def _load() -> List[Dict]:
    if not _STORE_PATH.exists():
        return []
    try:
        return json.loads(_STORE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _save(records: List[Dict]) -> None:
    _STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _STORE_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _keywords(text: str) -> set[str]:
    """소문자 단어 토큰 집합 (불용어 제거)."""
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been",
        "this", "that", "and", "or", "but", "in", "on", "at", "to",
        "for", "of", "with", "by", "as", "it", "its", "we", "our",
        "you", "your", "they", "their", "please", "should", "would",
        "could", "may", "might", "must", "also", "however", "while",
        "although", "since", "which", "that", "who", "what", "how",
        "do", "does", "did", "not", "no", "more", "less", "than",
        "i", "me", "my", "he", "she", "his", "her", "한", "이", "가",
    }
    tokens = re.findall(r"[a-zA-Z가-힣]{2,}", text.lower())
    return {t for t in tokens if t not in stopwords}


class FeedbackStore:
    """저널 리뷰어 피드백 누적 저장소."""

    def add(
        self,
        feedback_text: str,
        journal: str = "",
        topic_keywords: str = "",
        source: str = "reviewer",
        paper_title: str = "",
        decision: str = "",        # "major_revision" | "minor_revision" | "reject" | "accept"
    ) -> str:
        """피드백 추가. 반환값: 생성된 record ID."""
        if not feedback_text or not feedback_text.strip():
            raise ValueError("feedback_text가 비어 있습니다.")

        records = _load()
        record = {
            "id": str(uuid.uuid4())[:8],
            "created_at": datetime.now().isoformat(),
            "journal": journal.strip(),
            "paper_title": paper_title.strip(),
            "topic_keywords": topic_keywords.strip(),
            "source": source,            # "reviewer" | "editor" | "user"
            "decision": decision,
            "feedback_text": feedback_text.strip(),
            "keywords": sorted(_keywords(feedback_text + " " + topic_keywords)),
        }
        records.append(record)
        _save(records)
        _log.info("피드백 저장 완료 (id=%s, journal=%s)", record["id"], journal)
        return record["id"]

    def get_relevant(
        self,
        query: str,
        journal: str = "",
        top_k: int = 5,
    ) -> List[Dict]:
        """쿼리와 관련성 높은 피드백 top_k 반환 (키워드 오버랩 스코어링)."""
        records = _load()
        if not records:
            return []

        q_kw = _keywords(query)
        scored = []
        for r in records:
            r_kw = set(r.get("keywords", []))
            overlap = len(q_kw & r_kw)
            # 동일 저널이면 보너스 점수
            journal_bonus = 2 if journal and journal.lower() == r.get("journal", "").lower() else 0
            score = overlap + journal_bonus
            if score > 0:
                scored.append((score, r))

        scored.sort(key=lambda x: -x[0])
        return [r for _, r in scored[:top_k]]

    def build_context(self, query: str, journal: str = "") -> str:
        """논문 작성 프롬프트 주입용 컨텍스트 문자열 반환."""
        hits = self.get_relevant(query, journal=journal, top_k=3)
        if not hits:
            return ""
        lines = ["PAST REVIEWER FEEDBACK (apply these lessons to this paper):"]
        for i, r in enumerate(hits, 1):
            j = f"[{r['journal']}] " if r["journal"] else ""
            dec = f" ({r['decision']})" if r["decision"] else ""
            lines.append(f"\n--- Feedback #{i} {j}{dec} ---")
            lines.append(r["feedback_text"][:600])
        return "\n".join(lines)

    def get_reviewer_patterns(self, top_n: int = 5) -> str:
        """_build_system() 주입용 — 자주 지적되는 패턴 요약.

        실 리뷰어 피드백(source != 'ai_reviewer')을 우선하고, 남는 자리를 AI 동료심사로 채운다.
        AI 심사가 대량 누적돼도 실제 저널 피드백이 밀려나지 않도록 보장.
        """
        records = _load()
        if not records:
            return ""

        human = [r for r in records if r.get("source") != "ai_reviewer"]
        ai = [r for r in records if r.get("source") == "ai_reviewer"]

        # 실 리뷰어 우선 → 부족분을 최근 AI 심사로 채움
        selected = human[-top_n:]
        if len(selected) < top_n:
            selected = selected + ai[-(top_n - len(selected)):]

        snippets = []
        for r in selected:
            j = f"[{r['journal']}]" if r["journal"] else "[unknown journal]"
            src = "AI심사" if r.get("source") == "ai_reviewer" else "리뷰어"
            dec = f" ({r['decision']})" if r["decision"] else ""
            snippet = r["feedback_text"][:300].replace("\n", " ").strip()
            snippets.append(f"• [{src}]{j}{dec}: {snippet}")

        return (
            "REVIEWER PATTERN MEMORY (lessons from past submissions — apply proactively):\n"
            + "\n".join(snippets)
        )

    def list_all(self) -> List[Dict]:
        """전체 피드백 목록 반환."""
        return _load()

    def delete(self, record_id: str) -> bool:
        """ID로 피드백 삭제. 반환: 성공 여부."""
        records = _load()
        filtered = [r for r in records if r.get("id") != record_id]
        if len(filtered) == len(records):
            return False
        _save(filtered)
        _log.info("피드백 삭제 완료 (id=%s)", record_id)
        return True

    def count(self) -> int:
        return len(_load())


# 편의 함수 (모듈 레벨)

def add_feedback(
    feedback_text: str,
    journal: str = "",
    topic_keywords: str = "",
    source: str = "reviewer",
    paper_title: str = "",
    decision: str = "",
) -> str:
    return FeedbackStore().add(
        feedback_text=feedback_text,
        journal=journal,
        topic_keywords=topic_keywords,
        source=source,
        paper_title=paper_title,
        decision=decision,
    )


def get_feedback_context(query: str, journal: str = "") -> str:
    return FeedbackStore().build_context(query, journal=journal)


def get_reviewer_patterns(top_n: int = 5) -> str:
    return FeedbackStore().get_reviewer_patterns(top_n=top_n)
