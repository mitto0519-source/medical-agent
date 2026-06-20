"""Memory Facade — 13 모듈 통합 회상 단일 진입점.

★ 사용자 정직 진단 (2026-06-20): "장기 기억 메모리를 모든 agent에 연계 통합 시킨게
있는데 왜 통합 연동 안 됨?". 정답: 모듈은 다 있는데 build_full_system에 회상 호출 0건.

5층 메모리 통합 (CLAUDE.md 규칙 12 단일 코어 정신):
  ① conversation_memory (대화 ChromaDB cross-session)
  ② change_log (작업 이력)
  ③ memory.router items (typed working/episodic/semantic/procedural/goal)
  ④ persona (페르소나 시드)
  ⑤ research_state checkpoints (현 프로젝트 진척)

API:
    from src.memory.facade import recall_all_layers
    block = recall_all_layers(query, project, owner_email, max_chars=2000)
    # → system prompt에 inject 가능한 텍스트 블록 (5층 통합)
"""
from __future__ import annotations

from typing import Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def recall_all_layers(query: str, project: Optional[dict] = None,
                         owner_email: str = "", max_chars: int = 2000) -> str:
    """5층 메모리 통합 회상 → system prompt inject용 텍스트.

    Args:
        query: 현재 user message (recall 키워드).
        project: 현재 active project dict (research_state 키 참조).
        owner_email: 사용자 식별 (per-user scope).
        max_chars: 총 출력 길이 상한 (system prompt 비대화 방지).

    Returns:
        멀티라인 텍스트. 빈 문자열이면 inject 생략.
    """
    parts = []
    project = project or {}
    project_id = project.get("id")

    # ① conversation_memory (cross-session 대화)
    try:
        from src.memory.conversation_memory import recall_relevant
        hits = recall_relevant(query, n=3, owner_email=owner_email or None) or []
        if hits:
            parts.append("[L1 대화기억] 이전 세션 관련 대화:")
            for h in hits[:3]:
                if isinstance(h, dict):
                    txt = (h.get("agent_summary") or h.get("user_input_summary")
                           or h.get("text") or "")
                else:
                    txt = str(h)
                if txt and len(txt) > 20:
                    parts.append(f"  · {txt[:200]}")
    except Exception as e:
        _log.debug("L1 conversation_memory.recall fail: %s", e)

    # ② change_log (최근 작업 이력)
    try:
        from src.memory.change_log import get_recent
        recent = get_recent(5) or []
        if recent:
            parts.append("[L2 작업이력] 최근 변경:")
            for r in recent[:5]:
                title = r.get("title") or r.get("description", "")
                if title:
                    parts.append(f"  · {title[:120]}")
    except Exception as e:
        _log.debug("L2 change_log fail: %s", e)

    # ③ memory.router items (typed)
    try:
        from src.memory.lifecycle import active_items
        items = active_items(limit=5) or []
        if items:
            parts.append("[L3 typed memory] 활성 항목:")
            for it in items[:5]:
                t = it.get("type", "?")
                txt = it.get("text", "")[:120]
                if txt:
                    parts.append(f"  · [{t}] {txt}")
    except Exception as e:
        _log.debug("L3 lifecycle.active_items fail: %s", e)

    # ④ persona (요약만 — 전체는 별도 inject)
    try:
        from pathlib import Path as _P
        import json as _json
        pp = _P("data/agent_self/persona.json")
        if pp.exists():
            p = _json.loads(pp.read_text(encoding="utf-8"))
            ne = p.get("notable_exchanges", [])
            if ne:
                parts.append(f"[L4 persona] notable_exchanges {len(ne)}건 누적 (직접 inject는 _build_system이 처리)")
    except Exception as e:
        _log.debug("L4 persona fail: %s", e)

    # ⑤ research_state checkpoints (현 프로젝트 진척)
    if project_id:
        try:
            from src.research.research_state import list_checkpoints
            cps = list_checkpoints(project_id, limit=3) or []
            if cps:
                parts.append(f"[L5 research_state] 프로젝트 {project_id} 체크포인트 {len(cps)}건:")
                for cp in cps[:3]:
                    label = cp.get("label", "?")
                    parts.append(f"  · {label}")
        except Exception as e:
            _log.debug("L5 research_state.list_checkpoints fail: %s", e)

    if not parts:
        return ""

    block = "\n".join(parts)
    if len(block) > max_chars:
        block = block[:max_chars] + "\n  ... (truncated)"

    return ("--- ★ LONG-TERM MEMORY (5층 통합 회상, CLAUDE.md 규칙 12) ---\n"
            + block
            + "\n--- END MEMORY ---")


__all__ = ["recall_all_layers"]
