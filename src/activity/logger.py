"""Per-user activity logger — persistent JSON + session state."""
from __future__ import annotations
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

LOG_DIR = Path("data/activity")


def _safe_email(email: str) -> str:
    return email.replace("@", "_at_").replace(".", "_")


def log_activity(
    user_email: str,
    page: str,
    action: str,
    input_data: dict,
    output_summary: str,
    output_data: Optional[dict] = None,
) -> dict:
    entry = {
        "id": datetime.now().strftime("%Y%m%d_%H%M%S_%f"),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "page": page,
        "action": action,
        "input": input_data,
        "output_summary": output_summary,
        "output": output_data or {},
    }
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{_safe_email(user_email)}.json"
    try:
        existing = json.loads(log_file.read_text(encoding="utf-8")) if log_file.exists() else []
        existing.insert(0, entry)
        log_file.write_text(json.dumps(existing[:200], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass
    return entry


def get_user_log(user_email: str, page: Optional[str] = None, limit: int = 20) -> list:
    log_file = LOG_DIR / f"{_safe_email(user_email)}.json"
    if not log_file.exists():
        return []
    try:
        entries = json.loads(log_file.read_text(encoding="utf-8"))
        if page:
            entries = [e for e in entries if e.get("page") == page]
        return entries[:limit]
    except Exception:
        return []
