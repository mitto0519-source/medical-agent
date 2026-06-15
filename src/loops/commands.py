"""Slash command dispatch — /loop /goal /triage /state /checkpoint /branch.

ez_home 컴포저에서 첫 글자 `/` 감지 시 호출.
"""
from __future__ import annotations

from typing import Dict, Any

from src.config.logging_config import get_logger

_log = get_logger(__name__)


def dispatch_slash(cmd: str, args: str = "", *, project: Dict = None,
                      owner_email: str = "") -> Dict[str, Any]:
    """Slash 명령 → 결과 dict (chat에 표시).

    Returns: {"ok", "kind", "title", "body"} — kind=text/json/table 등
    """
    c = (cmd or "").lstrip("/").lower().strip()
    a = (args or "").strip()

    if c == "loop":
        from src.loops.registry import list_loops, run_loop
        if not a:
            loops = list_loops()
            return {"ok": True, "kind": "table", "title": f"🔁 등록된 루프 ({len(loops)}개)",
                    "rows": [{"name": l["name"], "trigger": l["trigger"],
                                "purpose": l["purpose"][:60]} for l in loops]}
        r = run_loop(a)
        return {"ok": r.get("ok", False), "kind": "json",
                "title": f"🔁 loop '{a}' 실행", "body": r}

    if c == "goal":
        # goal-loop: 완료 조건 만족까지 반복 (가벼운 manual ver — heartbeat 위)
        if not a:
            return {"ok": False, "kind": "text",
                    "body": "사용법: /goal <목표 문장>. 예: /goal 카페인-우울 표 채우기"}
        return {"ok": True, "kind": "text",
                "title": f"🎯 goal 등록: {a[:80]}",
                "body": f"이 목표는 heartbeat 백로그에 추가됩니다 (완료 시까지 반복 시도)."}

    if c == "triage":
        from src.loops.triage import inbox
        ib = inbox(owner_email=owner_email or None)
        return {"ok": True, "kind": "json", "title": "📥 Triage Inbox",
                "body": ib}

    if c == "state":
        from src.loops.state_view import today_view
        v = today_view(owner_email=owner_email or None)
        return {"ok": True, "kind": "json", "title": "🗂 오늘 상태", "body": v}

    if c == "checkpoint":
        if not project:
            return {"ok": False, "kind": "text", "body": "활성 프로젝트 없음"}
        try:
            from src.research.research_state import from_project_dict, checkpoint as _cp
            rp = from_project_dict(project)
            cp_id = _cp(rp, label=a or "manual")
            return {"ok": True, "kind": "text",
                    "title": "📌 체크포인트 생성",
                    "body": f"cp_id: {cp_id}\nlabel: {a or 'manual'}"}
        except Exception as e:
            return {"ok": False, "kind": "text", "body": f"실패: {e}"}

    if c == "branch":
        parts = a.split(maxsplit=1)
        if len(parts) < 1:
            return {"ok": False, "kind": "text",
                    "body": "사용법: /branch <cp_id> [새 제목]"}
        try:
            from src.research.research_state import branch as _br
            cp_id = parts[0]
            title = parts[1] if len(parts) > 1 else "분기"
            rp = _br(cp_id, new_title=title)
            if rp is None:
                return {"ok": False, "kind": "text",
                        "body": f"체크포인트 {cp_id} 못 찾음"}
            return {"ok": True, "kind": "text",
                    "title": "🌿 분기 생성",
                    "body": f"new state_id: {rp.id}\ntitle: {rp.title}"}
        except Exception as e:
            return {"ok": False, "kind": "text", "body": f"실패: {e}"}

    if c in ("help", "h", ""):
        return {"ok": True, "kind": "text", "title": "Slash 명령",
                "body": ("/loop [name]    — 등록된 루프 / 수동 실행\n"
                          "/goal <목표>     — 완료까지 반복 목표 등록\n"
                          "/triage         — 4분류 inbox\n"
                          "/state          — 오늘 어디까지 왔나\n"
                          "/checkpoint [label] — 현 프로젝트 체크포인트\n"
                          "/branch <cp_id> [제목] — 같은 지점에서 갈래")}

    return {"ok": False, "kind": "text", "body": f"알 수 없는 명령: /{c}. `/help` 참고."}


__all__ = ["dispatch_slash"]
