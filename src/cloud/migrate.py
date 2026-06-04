"""Supabase schema migration — 12 ma_* 테이블 일괄 CREATE + verify.

매 컨테이너 부팅 시 streamlit_app에서 1회 호출되어 누락 테이블 자동 생성.
Idempotent — 이미 존재하면 skip.

사용:
    from src.cloud.migrate import ensure_all_tables
    ensure_all_tables()  # streamlit_app entry에서 hf_bootstrap 직후 호출

ARCHITECTURE 원칙 (RULE-9 ONLINE-FIRST):
    - 정적 데이터 (KYRBS sav, chromadb, graph, OA papers) → HF Datasets (hf_bootstrap)
    - 라이브 사용자 상태 (auth, drafts, intent, activity, ...) → Supabase 12 tables

전체 12 테이블:
    ma_users / ma_activity / ma_author_profiles / ma_datasets / ma_drafts /
    ma_workflows / ma_change_log / ma_agent_insights / ma_topics /
    ma_novelty_results / ma_intent_history / ma_working_papers
"""
from __future__ import annotations

from typing import Dict, List

from src.config.logging_config import get_logger

_log = get_logger(__name__)


# ── 12 테이블 DDL (db.py와 동일) ─────────────────────────────────────────
_DDLS: List[tuple[str, str]] = [
    ("ma_intent_history",
     "CREATE TABLE IF NOT EXISTS ma_intent_history ("
     "id bigserial PRIMARY KEY, owner_email text, "
     "emphasis jsonb, avoidance jsonb, reader jsonb, tone jsonb, "
     "persona jsonb, ts timestamp DEFAULT now())"),
    ("ma_working_papers",
     "CREATE TABLE IF NOT EXISTS ma_working_papers ("
     "id text PRIMARY KEY, owner_email text, title text, "
     "sections jsonb, meta jsonb, updated_at double precision)"),
]


def ensure_all_tables() -> Dict[str, str]:
    """모든 ma_* 테이블 idempotent CREATE. 결과: {table: status}.

    db.py:_init_tables가 이미 10개를 만들고, 본 함수는 추가 2개 (intent, working_papers)
    + 누락된 schema_evolutions 통합 처리.
    """
    from src.cloud.db import cloud_available, get_engine
    if not cloud_available():
        _log.info("[migrate] Supabase unavailable (SUPABASE_DB_URL not set) — skip")
        return {"_": "skipped (no SUPABASE_DB_URL)"}

    engine = get_engine()
    if engine is None:
        _log.warning("[migrate] cloud_available=True but get_engine returned None")
        return {"_": "skipped (engine None)"}

    import sqlalchemy as sa
    result: Dict[str, str] = {}

    # db.py에 위임: ma_users / ma_activity / ma_author_profiles / ma_datasets /
    # ma_drafts / ma_workflows / ma_change_log / ma_agent_insights / ma_topics / ma_novelty_results
    try:
        from src.cloud.db import _init_tables
        with engine.connect() as conn:
            _init_tables(engine)
            conn.commit() if hasattr(conn, "commit") else None
        result["db_init_tables"] = "ok (10 tables)"
    except Exception as e:
        result["db_init_tables"] = f"fail: {e}"
        _log.error("[migrate] db._init_tables FAIL: %s", e)

    # 추가 2개 테이블 (각 모듈이 lazy create 하지만, 부팅 시 한 번 보장)
    for name, ddl in _DDLS:
        try:
            with engine.connect() as conn:
                conn.execute(sa.text(ddl))
                conn.commit() if hasattr(conn, "commit") else None
            result[name] = "ok"
        except Exception as e:
            result[name] = f"fail: {e}"
            _log.error("[migrate] %s FAIL: %s", name, e)

    # 검증: 모든 테이블 SELECT COUNT 가능한지
    test_tables = [
        "ma_users", "ma_activity", "ma_author_profiles", "ma_datasets", "ma_drafts",
        "ma_workflows", "ma_change_log", "ma_agent_insights", "ma_topics",
        "ma_novelty_results", "ma_intent_history", "ma_working_papers",
    ]
    with engine.connect() as conn:
        for t in test_tables:
            try:
                conn.execute(sa.text(f"SELECT COUNT(*) FROM {t} LIMIT 1"))
                result[f"verify_{t}"] = "ok"
            except Exception as e:
                result[f"verify_{t}"] = f"FAIL: {str(e)[:80]}"

    ok = sum(1 for v in result.values() if v == "ok" or v.startswith("ok"))
    fail = sum(1 for v in result.values() if "fail" in v.lower() or "FAIL" in v)
    _log.info("[migrate] complete: ok=%d fail=%d", ok, fail)
    return result


def cli():
    """python -m src.cloud.migrate"""
    r = ensure_all_tables()
    print("=" * 60)
    print("Supabase migration result:")
    for k, v in r.items():
        print(f"  {k:35s} {v}")
    print("=" * 60)


if __name__ == "__main__":
    cli()
