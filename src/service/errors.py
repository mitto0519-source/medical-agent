"""Errors service — UX-5 친절한 에러 메시지 HTML 생성 (Phase 1 추출).

★ 2026-06-21 Phase 1: ez_home._friendly_error 순수 추출.
  · Streamlit 의존 0
  · HTML 문자열 반환 (Streamlit/Next.js 양쪽에서 사용 가능)
"""
from __future__ import annotations

from typing import List, Optional


def friendly_error(kind: str, raw_msg: str,
                      alternatives: Optional[List[str]] = None) -> str:
    """UX-5: 에러 메시지 친절화 — 원인 + 대안 HTML.

    Args:
        kind: stat / data / llm / network / file
        raw_msg: 원본 에러 메시지
        alternatives: 해결 양식 list (최대 4개 표시)

    Returns:
        msg-asst 클래스 양식 HTML 문자열.
    """
    titles = {
        "stat": "📊 통계 분석 실패",
        "data": "💾 데이터 로드 실패",
        "llm":  "🤖 AI 호출 실패",
        "network": "🌐 외부 연결 실패",
        "file": "📁 파일 처리 실패",
    }
    title = titles.get(kind, "⚠ 작업 실패")
    msg = f"<b>{title}</b><br>"
    msg += (f"<span style='color:#555555;font-size:0.84rem;'>"
              f"원인: {(raw_msg or '')[:200]}</span>")
    if alternatives:
        msg += ("<br><b style='font-size:0.84rem;'>해결책:</b>"
                  "<ul style='margin:4px 0 0 20px;font-size:0.84rem;'>")
        for alt in alternatives[:4]:
            msg += f"<li>{alt}</li>"
        msg += "</ul>"
    return msg


__all__ = ["friendly_error"]
