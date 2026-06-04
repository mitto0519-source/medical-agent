"""User edit feedback loop — RULE-8 #5: 사용자가 AI draft를 수정하면 diff를
'physician correction example'로 캡쳐해 다음 생성에 few-shot으로 자동 주입.

워크플로우:
    1. AI가 섹션 작성 (write_full_paper)
    2. 사용자가 workspace에서 그 섹션 수동 편집 (st.text_area, save)
    3. _save_project가 변경 감지 → record_edit() 호출
    4. paper_writer 다음 호출 시 같은 섹션의 최근 N개 edit를 few-shot으로 user_prompt 박음

저장 위치: data/runtime/user_edits.sqlite
"""
from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)

_DB = Path("data/runtime/user_edits.sqlite")


def _init():
    _DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB))
    conn.execute("""CREATE TABLE IF NOT EXISTS edits (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_email TEXT,
        project_id TEXT,
        section TEXT,
        ai_draft TEXT,
        user_final TEXT,
        diff_summary TEXT,
        ts REAL
    )""")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_section ON edits(section, ts DESC)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_owner ON edits(owner_email, ts DESC)")
    conn.commit()
    return conn


def record_edit(*, owner_email: str, project_id: str, section: str,
                 ai_draft: str, user_final: str) -> bool:
    """AI draft vs user 최종 저장본 diff 캡쳐."""
    if not ai_draft or not user_final or ai_draft == user_final:
        return False
    # 짧은 변경은 무시 (오타 수준)
    if abs(len(ai_draft) - len(user_final)) < 30 and \
            sum(a != b for a, b in zip(ai_draft, user_final)) < 30:
        return False
    try:
        import difflib
        diff = list(difflib.unified_diff(
            ai_draft.splitlines(keepends=False),
            user_final.splitlines(keepends=False),
            lineterm="", n=1
        ))
        diff_text = "\n".join(diff[:80])  # 양식 길이 제한
        conn = _init()
        conn.execute(
            "INSERT INTO edits (owner_email, project_id, section, ai_draft, "
            "user_final, diff_summary, ts) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (owner_email or "", project_id, section, ai_draft[:8000],
             user_final[:8000], diff_text, time.time()))
        conn.commit()
        conn.close()
        _log.info("[user_edits] recorded %s/%s (%d→%d chars)",
                   project_id, section, len(ai_draft), len(user_final))
        return True
    except Exception as e:
        _log.warning("[user_edits] record fail: %s", e)
        return False


def get_recent_examples(section: str, *, owner_email: Optional[str] = None,
                         limit: int = 3) -> List[Dict]:
    """같은 섹션의 최근 N개 user-correction example. paper_writer가 few-shot로 사용."""
    if not _DB.exists():
        return []
    try:
        conn = sqlite3.connect(str(_DB))
        conn.row_factory = sqlite3.Row
        q = "SELECT ai_draft, user_final, diff_summary, ts FROM edits WHERE section=?"
        args = [section]
        if owner_email:
            q += " AND owner_email=?"
            args.append(owner_email)
        q += " ORDER BY ts DESC LIMIT ?"
        args.append(limit)
        rows = conn.execute(q, args).fetchall()
        conn.close()
        return [{"ai_draft": r["ai_draft"], "user_final": r["user_final"],
                  "diff": r["diff_summary"], "ts": r["ts"]} for r in rows]
    except Exception as e:
        _log.warning("[user_edits] get fail: %s", e)
        return []


def build_few_shot_block(section: str, *, owner_email: Optional[str] = None,
                          n: int = 2, max_chars: int = 800) -> str:
    """user_prompt에 박을 텍스트 블록."""
    ex = get_recent_examples(section, owner_email=owner_email, limit=n)
    if not ex:
        return ""
    lines = [f"## USER PHYSICIAN CORRECTIONS — past {section} edits (mimic the user's voice and corrections)\n"]
    for i, e in enumerate(ex, 1):
        lines.append(f"### Past edit {i}\nAI draft (rejected): "
                      f"{(e['ai_draft'] or '')[:max_chars]}\n\n"
                      f"User final (preferred): "
                      f"{(e['user_final'] or '')[:max_chars]}\n")
    lines.append("Apply the same kind of corrections this time.\n")
    return "\n".join(lines)


__all__ = ["record_edit", "get_recent_examples", "build_few_shot_block"]
