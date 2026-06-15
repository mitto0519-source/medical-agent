"""Supabase PostgreSQL engine — single shared connection pool.

Usage:
    from src.cloud.db import cloud_available, get_engine

When SUPABASE_DB_URL is not set, cloud_available() returns False and
get_engine() returns None. Every caller must check cloud_available() first.
"""
from __future__ import annotations

import os
from functools import lru_cache

from src.config.logging_config import get_logger

_log = get_logger(__name__)


@lru_cache(maxsize=1)
def get_engine():
    """Return SQLAlchemy engine (cached) or None when cloud is not configured."""
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        return None
    try:
        import sqlalchemy as sa
        engine = sa.create_engine(
            url,
            pool_pre_ping=True,   # detects stale connections on Railway
            pool_size=5,
            max_overflow=10,
        )
        _init_tables(engine)
        return engine
    except Exception as e:
        _log.warning("Cloud DB init failed: %s", e)
        return None


def cloud_available() -> bool:
    return get_engine() is not None


def _init_tables(engine) -> None:
    """Create all Medical-Agent tables if they don't exist."""
    from sqlalchemy import text
    ddl_statements = [
        """
        CREATE TABLE IF NOT EXISTS ma_users (
            email        TEXT PRIMARY KEY,
            name         TEXT        NOT NULL DEFAULT '',
            role         TEXT        NOT NULL DEFAULT 'viewer',
            api_key      TEXT        NOT NULL UNIQUE,
            created_at   TEXT        NOT NULL DEFAULT CURRENT_DATE::TEXT,
            active       BOOLEAN     NOT NULL DEFAULT TRUE,
            llm_provider TEXT,
            llm_api_key  TEXT
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_users_key_idx ON ma_users (api_key)",
        """
        CREATE TABLE IF NOT EXISTS ma_activity (
            id             TEXT        PRIMARY KEY,
            user_email     TEXT        NOT NULL,
            page           TEXT        NOT NULL DEFAULT '',
            action         TEXT        NOT NULL DEFAULT '',
            input_data     JSONB       NOT NULL DEFAULT '{}',
            output_summary TEXT        NOT NULL DEFAULT '',
            output_data    JSONB       NOT NULL DEFAULT '{}',
            timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_activity_user_idx ON ma_activity (user_email, timestamp DESC)",
        """
        CREATE TABLE IF NOT EXISTS ma_author_profiles (
            slug            TEXT PRIMARY KEY,
            author_name     TEXT        NOT NULL,
            writing_style   JSONB       NOT NULL DEFAULT '{}',
            methodology     JSONB       NOT NULL DEFAULT '{}',
            paper_structure JSONB       NOT NULL DEFAULT '{}',
            vocabulary      JSONB       NOT NULL DEFAULT '[]',
            citation_style  JSONB       NOT NULL DEFAULT '{}',
            study_focus     JSONB       NOT NULL DEFAULT '[]',
            raw_examples    JSONB       NOT NULL DEFAULT '[]',
            papers_analysed JSONB       NOT NULL DEFAULT '[]',
            system_prompt   TEXT        NOT NULL DEFAULT '',
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ma_datasets (
            name                TEXT PRIMARY KEY,
            full_name           TEXT  NOT NULL DEFAULT '',
            description         TEXT  NOT NULL DEFAULT '',
            variables           JSONB NOT NULL DEFAULT '{}',
            analysis_notes      JSONB NOT NULL DEFAULT '[]',
            common_confounders  JSONB NOT NULL DEFAULT '[]',
            papers_using_this   JSONB NOT NULL DEFAULT '[]',
            updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS ma_drafts (
            id           SERIAL PRIMARY KEY,
            safe_title   TEXT        NOT NULL,
            topic_title  TEXT        NOT NULL DEFAULT '',
            author_email TEXT,
            content      TEXT        NOT NULL,
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_drafts_author_idx ON ma_drafts (author_email, created_at DESC)",
        # ★ RESEARCH_STATE_SPEC §2 — ma_research_state (단일 정본)
        """
        CREATE TABLE IF NOT EXISTS ma_research_state (
            id              TEXT        PRIMARY KEY,
            owner_email     TEXT        NOT NULL DEFAULT '',
            title           TEXT        NOT NULL DEFAULT '새 연구',
            schema_version  TEXT        NOT NULL DEFAULT '1.0.0',
            data_json       JSONB       NOT NULL DEFAULT '{}',
            updated_at      BIGINT      NOT NULL DEFAULT 0
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_research_state_owner_idx ON ma_research_state (owner_email, updated_at DESC)",
        # ma_working_papers (ez_home project dict 호환 — F5 안전 mirror)
        """
        CREATE TABLE IF NOT EXISTS ma_working_papers (
            id           TEXT        PRIMARY KEY,
            owner_email  TEXT        NOT NULL DEFAULT '',
            title        TEXT        NOT NULL DEFAULT '새 작업',
            data_json    JSONB       NOT NULL DEFAULT '{}',
            updated_at   BIGINT      NOT NULL DEFAULT 0
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_working_papers_owner_idx ON ma_working_papers (owner_email, updated_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS ma_workflows (
            workflow_id  TEXT        PRIMARY KEY,
            user_email   TEXT,
            dataset      TEXT        NOT NULL DEFAULT 'KYRBS',
            current_stage TEXT       NOT NULL DEFAULT 'topic_proposal',
            state        JSONB       NOT NULL DEFAULT '{}',
            created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_workflows_user_idx ON ma_workflows (user_email, updated_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS ma_change_log (
            id           TEXT        PRIMARY KEY,
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_email   TEXT        NOT NULL DEFAULT '',
            session_id   TEXT        NOT NULL DEFAULT '',
            action_type  TEXT        NOT NULL DEFAULT 'general',
            title        TEXT        NOT NULL,
            description  TEXT        NOT NULL DEFAULT '',
            what_changed JSONB       NOT NULL DEFAULT '{}',
            why_better   TEXT        NOT NULL DEFAULT '',
            inputs       JSONB       NOT NULL DEFAULT '{}',
            outputs      JSONB       NOT NULL DEFAULT '{}',
            impact       JSONB       NOT NULL DEFAULT '{}'
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_change_log_user_idx ON ma_change_log (user_email, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS ma_change_log_type_idx ON ma_change_log (action_type, timestamp DESC)",
        """
        CREATE TABLE IF NOT EXISTS ma_agent_insights (
            id           TEXT        PRIMARY KEY,
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            category     TEXT        NOT NULL DEFAULT 'pattern',
            title        TEXT        NOT NULL,
            insight      TEXT        NOT NULL DEFAULT '',
            why_matters  TEXT        NOT NULL DEFAULT '',
            how_to_apply TEXT        NOT NULL DEFAULT '',
            confidence   FLOAT       NOT NULL DEFAULT 0.8,
            tags         JSONB       NOT NULL DEFAULT '[]',
            source       TEXT        NOT NULL DEFAULT 'observation',
            status       TEXT        NOT NULL DEFAULT 'active'
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_insights_cat_idx ON ma_agent_insights (category, timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS ma_insights_status_idx ON ma_agent_insights (status, timestamp DESC)",
        """
        CREATE TABLE IF NOT EXISTS ma_topics (
            id          TEXT        PRIMARY KEY,
            timestamp   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_email  TEXT        NOT NULL DEFAULT '',
            dataset     TEXT        NOT NULL DEFAULT '',
            focus       TEXT        NOT NULL DEFAULT '',
            n_topics    INT         NOT NULL DEFAULT 0,
            topics      JSONB       NOT NULL DEFAULT '[]'
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_topics_user_idx ON ma_topics (user_email, timestamp DESC)",
        """
        CREATE TABLE IF NOT EXISTS ma_novelty_results (
            id           TEXT        PRIMARY KEY,
            timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            user_email   TEXT        NOT NULL DEFAULT '',
            topic_title  TEXT        NOT NULL DEFAULT '',
            exposure     TEXT        NOT NULL DEFAULT '',
            outcome      TEXT        NOT NULL DEFAULT '',
            population   TEXT        NOT NULL DEFAULT '',
            result       JSONB       NOT NULL DEFAULT '{}'
        )
        """,
        "CREATE INDEX IF NOT EXISTS ma_novelty_user_idx ON ma_novelty_results (user_email, timestamp DESC)",
    ]
    with engine.begin() as conn:
        for stmt in ddl_statements:
            conn.execute(text(stmt.strip()))
