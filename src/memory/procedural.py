"""Procedural memory — 행동 전략 기억 ('이 reviewer는 sample weighting을 본다').

외부 진단 (2026-05-28): "procedural learning이 가장 부족" 해결.

기존 router의 procedural type은 단순 rules.json append. 본 모듈은:
  · ProceduralRule schema (trigger/action/domain/confidence/n_applied/n_success)
  · SQLite 저장 (data/runtime/procedural.db)
  · 매칭 helper: find_applicable(context) → List[ProceduralRule]
  · 적용 결과 피드백: report_outcome(rule_id, success: bool)
  · capability_bench이 실패 → 자동으로 새 procedural rule 추출 (별도 작업)

사용:
    from src.memory.procedural import add_rule, find_applicable, report_outcome
    add_rule(trigger="reviewer mentions sample weighting",
             action="add detailed pweight/strata description in Methods",
             domain="journal_review")
    rules = find_applicable("This reviewer asks about sample weighting", domain="journal_review")
    report_outcome(rules[0]["id"], success=True)
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional

from src.config.logging_config import get_logger

_log = get_logger(__name__)
_DB = Path("data/runtime/procedural.db")


def _conn() -> sqlite3.Connection:
    _DB.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(_DB))
    c.execute("PRAGMA journal_mode=WAL")
    c.execute("""CREATE TABLE IF NOT EXISTS rules(
        id TEXT PRIMARY KEY,
        trigger TEXT NOT NULL,
        action TEXT NOT NULL,
        domain TEXT NOT NULL,
        confidence REAL DEFAULT 0.5,
        n_applied INTEGER DEFAULT 0,
        n_success INTEGER DEFAULT 0,
        last_applied REAL DEFAULT 0,
        source_episodes_json TEXT,
        created_at REAL,
        schema_version TEXT DEFAULT '1.0.0'
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_domain ON rules(domain)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_conf ON rules(confidence)")
    c.commit()
    return c


def _hash(trigger: str, action: str) -> str:
    return hashlib.sha1(f"{trigger[:80]}|{action[:80]}".lower().encode("utf-8")).hexdigest()[:16]


def add_rule(*, trigger: str, action: str, domain: str = "general",
              confidence: float = 0.5, source_episodes: Optional[List[str]] = None) -> str:
    """행동 전략 rule 추가. trigger+action 동일이면 skip → 기존 id 반환."""
    from src.memory.schemas import validate_procedural, ProceduralRule
    rid = _hash(trigger, action)
    rec = {
        "id": rid, "trigger": trigger.strip(), "action": action.strip(),
        "domain": domain, "confidence": float(confidence),
        "n_applied": 0, "n_success": 0, "last_applied": 0.0,
        "source_episodes": source_episodes or [],
        "created_at": time.time(),
    }
    v = validate_procedural(rec)
    if "_schema_invalid" in v:
        _log.warning("procedural schema invalid: %s", v["_schema_invalid"])
        return rid
    c = _conn()
    c.execute(
        "INSERT OR IGNORE INTO rules"
        "(id, trigger, action, domain, confidence, n_applied, n_success, "
        " last_applied, source_episodes_json, created_at, schema_version)"
        " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (rid, rec["trigger"], rec["action"], rec["domain"],
         rec["confidence"], 0, 0, 0.0,
         json.dumps(rec["source_episodes"]), rec["created_at"], "1.0.0"),
    )
    c.commit()
    try:
        from src.runtime import events as _events
        _events.append("procedural_rule_added",
                        {"id": rid, "domain": domain, "trigger": trigger[:120]},
                        actor="procedural_memory")
    except Exception:
        pass
    return rid


def find_applicable(context: str, *, domain: Optional[str] = None,
                     min_confidence: float = 0.3, limit: int = 5) -> List[Dict]:
    """context 텍스트와 trigger 키워드 매칭. domain 필터 옵션."""
    if not context:
        return []
    ctx_lo = context.lower()
    c = _conn()
    sql = ("SELECT id, trigger, action, domain, confidence, n_applied, n_success, last_applied"
            " FROM rules WHERE confidence >= ?")
    params: list = [min_confidence]
    if domain:
        sql += " AND domain=?"
        params.append(domain)
    sql += " ORDER BY confidence DESC, n_success DESC LIMIT ?"
    params.append(limit * 5)   # 임시 풀; trigger 매칭 후 필터
    rows = c.execute(sql, tuple(params)).fetchall()
    out: List[Dict] = []
    for r in rows:
        rid, trig, act, dom, conf, na, ns, la = r
        # 단순 키워드 매칭 (trigger 본문의 핵심 토큰 일부가 context에 포함)
        toks = [t for t in trig.lower().split() if len(t) > 3]
        if not toks:
            continue
        match = sum(1 for t in toks if t in ctx_lo) / max(1, len(toks))
        if match >= 0.30:
            out.append({"id": rid, "trigger": trig, "action": act, "domain": dom,
                         "confidence": conf, "n_applied": na, "n_success": ns,
                         "match_score": round(match, 3)})
    out.sort(key=lambda x: (x["match_score"], x["confidence"]), reverse=True)
    return out[:limit]


def report_outcome(rule_id: str, *, success: bool):
    """rule 적용 후 성공/실패 피드백 → confidence 조정 (지수 가중)."""
    c = _conn()
    row = c.execute(
        "SELECT confidence, n_applied, n_success FROM rules WHERE id=?",
        (rule_id,)).fetchone()
    if not row:
        return
    conf, na, ns = row
    na_new = na + 1
    ns_new = ns + (1 if success else 0)
    # 지수 weighted: 새 결과 영향 0.2
    new_conf = 0.8 * conf + 0.2 * (1.0 if success else 0.0)
    c.execute(
        "UPDATE rules SET confidence=?, n_applied=?, n_success=?, last_applied=? WHERE id=?",
        (round(new_conf, 4), na_new, ns_new, time.time(), rule_id))
    c.commit()
    try:
        from src.runtime import events as _events
        _events.append("procedural_outcome",
                        {"id": rule_id, "success": success,
                         "new_confidence": round(new_conf, 3)},
                        actor="procedural_memory")
    except Exception:
        pass


def stats() -> Dict:
    """전체 procedural rule 현황."""
    c = _conn()
    total = c.execute("SELECT COUNT(*) FROM rules").fetchone()[0]
    by_dom = dict(c.execute(
        "SELECT domain, COUNT(*) FROM rules GROUP BY domain ORDER BY 2 DESC"
    ).fetchall())
    top = c.execute(
        "SELECT id, domain, trigger, action, confidence, n_applied, n_success"
        " FROM rules WHERE n_applied > 0"
        " ORDER BY confidence DESC, n_applied DESC LIMIT 8"
    ).fetchall()
    return {
        "total": total,
        "by_domain": by_dom,
        "top": [{"id": r[0], "domain": r[1], "trigger": r[2][:80],
                  "action": r[3][:120], "confidence": r[4],
                  "n_applied": r[5], "n_success": r[6]} for r in top],
    }
