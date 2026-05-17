-- Medical-Agent Cloud Tables
-- Run once in Supabase SQL Editor before first deployment.

CREATE TABLE IF NOT EXISTS ma_users (
    email        TEXT PRIMARY KEY,
    name         TEXT        NOT NULL DEFAULT '',
    role         TEXT        NOT NULL DEFAULT 'viewer',
    api_key      TEXT        NOT NULL UNIQUE,
    created_at   TEXT        NOT NULL DEFAULT CURRENT_DATE::TEXT,
    active       BOOLEAN     NOT NULL DEFAULT TRUE,
    llm_provider TEXT,
    llm_api_key  TEXT
);
CREATE INDEX IF NOT EXISTS ma_users_key_idx ON ma_users (api_key);

CREATE TABLE IF NOT EXISTS ma_activity (
    id             TEXT        PRIMARY KEY,
    user_email     TEXT        NOT NULL,
    page           TEXT        NOT NULL DEFAULT '',
    action         TEXT        NOT NULL DEFAULT '',
    input_data     JSONB       NOT NULL DEFAULT '{}',
    output_summary TEXT        NOT NULL DEFAULT '',
    output_data    JSONB       NOT NULL DEFAULT '{}',
    timestamp      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ma_activity_user_idx ON ma_activity (user_email, timestamp DESC);

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
);

CREATE TABLE IF NOT EXISTS ma_datasets (
    name                TEXT PRIMARY KEY,
    full_name           TEXT  NOT NULL DEFAULT '',
    description         TEXT  NOT NULL DEFAULT '',
    variables           JSONB NOT NULL DEFAULT '{}',
    analysis_notes      JSONB NOT NULL DEFAULT '[]',
    common_confounders  JSONB NOT NULL DEFAULT '[]',
    papers_using_this   JSONB NOT NULL DEFAULT '[]',
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS ma_drafts (
    id           SERIAL PRIMARY KEY,
    safe_title   TEXT        NOT NULL,
    topic_title  TEXT        NOT NULL DEFAULT '',
    author_email TEXT,
    content      TEXT        NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS ma_drafts_author_idx ON ma_drafts (author_email, created_at DESC);
