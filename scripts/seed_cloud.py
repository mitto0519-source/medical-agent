"""One-time seed: local JSON files → Supabase PostgreSQL.

Run ONCE after running migrations/001_init_tables.sql in Supabase SQL Editor.

Usage:
    python scripts/seed_cloud.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Fix Windows console encoding
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=True)

from src.cloud.db import cloud_available, get_engine
from sqlalchemy import text

if not cloud_available():
    print("ERROR: SUPABASE_DB_URL not set. Add it to .env first.")
    sys.exit(1)

engine = get_engine()
print("Connected to Supabase.\n")


# ── 1. Users ─────────────────────────────────────────────────────────────
users_file = ROOT / "data" / "users.json"
if users_file.exists():
    users = json.loads(users_file.read_text(encoding="utf-8"))
    with engine.begin() as conn:
        for email, info in users.items():
            conn.execute(text("""
                INSERT INTO ma_users
                    (email, name, role, api_key, created_at, active, llm_provider, llm_api_key)
                VALUES
                    (:email, :name, :role, :api_key, :created_at, :active, :llm_provider, :llm_api_key)
                ON CONFLICT (email) DO UPDATE SET
                    name         = EXCLUDED.name,
                    role         = EXCLUDED.role,
                    api_key      = EXCLUDED.api_key,
                    active       = EXCLUDED.active,
                    llm_provider = EXCLUDED.llm_provider,
                    llm_api_key  = EXCLUDED.llm_api_key
            """), {
                "email": email,
                "name": info.get("name", ""),
                "role": info.get("role", "viewer"),
                "api_key": info.get("api_key", ""),
                "created_at": info.get("created_at", "2024-01-01"),
                "active": info.get("active", True),
                "llm_provider": info.get("llm_provider") or "Claude (Anthropic)",
                "llm_api_key": info.get("llm_api_key") or "",
            })
    print(f"[users] Seeded {len(users)} users.")
else:
    print("[users] data/users.json not found — skipped.")

# ── 2. Author Profiles ───────────────────────────────────────────────────
profiles_dir = ROOT / "data" / "author_profiles"
seeded = 0
if profiles_dir.exists():
    for f in profiles_dir.glob("*.json"):
        try:
            profile = json.loads(f.read_text(encoding="utf-8"))
            slug = f.stem
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO ma_author_profiles
                        (slug, author_name, writing_style, methodology, paper_structure,
                         vocabulary, citation_style, study_focus, raw_examples,
                         papers_analysed, system_prompt, updated_at)
                    VALUES
                        (:slug, :author_name,
                         CAST(:writing_style AS jsonb), CAST(:methodology AS jsonb),
                         CAST(:paper_structure AS jsonb), CAST(:vocabulary AS jsonb),
                         CAST(:citation_style AS jsonb), CAST(:study_focus AS jsonb),
                         CAST(:raw_examples AS jsonb), CAST(:papers_analysed AS jsonb),
                         :system_prompt, NOW())
                    ON CONFLICT (slug) DO UPDATE SET
                        author_name     = EXCLUDED.author_name,
                        writing_style   = EXCLUDED.writing_style,
                        methodology     = EXCLUDED.methodology,
                        paper_structure = EXCLUDED.paper_structure,
                        vocabulary      = EXCLUDED.vocabulary,
                        citation_style  = EXCLUDED.citation_style,
                        study_focus     = EXCLUDED.study_focus,
                        raw_examples    = EXCLUDED.raw_examples,
                        papers_analysed = EXCLUDED.papers_analysed,
                        system_prompt   = EXCLUDED.system_prompt,
                        updated_at      = NOW()
                """), {
                    "slug": slug,
                    "author_name": profile.get("author_name", slug),
                    "writing_style": json.dumps(profile.get("writing_style", {}), ensure_ascii=False),
                    "methodology": json.dumps(profile.get("methodology", {}), ensure_ascii=False),
                    "paper_structure": json.dumps(profile.get("paper_structure", {}), ensure_ascii=False),
                    "vocabulary": json.dumps(profile.get("vocabulary", []), ensure_ascii=False),
                    "citation_style": json.dumps(profile.get("citation_style", {}), ensure_ascii=False),
                    "study_focus": json.dumps(profile.get("study_focus", []), ensure_ascii=False),
                    "raw_examples": json.dumps(profile.get("raw_examples", []), ensure_ascii=False),
                    "papers_analysed": json.dumps(profile.get("papers_analysed", []), ensure_ascii=False),
                    "system_prompt": profile.get("system_prompt", ""),
                })
            seeded += 1
        except Exception as e:
            print(f"  ERROR seeding {f.name}: {e}")
print(f"[author_profiles] Seeded {seeded} profiles.")

# ── 3. Dataset Library ───────────────────────────────────────────────────
libs_dir = ROOT / "data" / "libraries"
seeded = 0
if libs_dir.exists():
    for f in libs_dir.glob("dataset_*.json"):
        try:
            ds = json.loads(f.read_text(encoding="utf-8"))
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO ma_datasets
                        (name, full_name, description, variables, analysis_notes,
                         common_confounders, papers_using_this, updated_at)
                    VALUES
                        (:name, :full_name, :description,
                         CAST(:variables AS jsonb), CAST(:analysis_notes AS jsonb),
                         CAST(:common_confounders AS jsonb), CAST(:papers_using_this AS jsonb),
                         NOW())
                    ON CONFLICT (name) DO UPDATE SET
                        full_name          = EXCLUDED.full_name,
                        description        = EXCLUDED.description,
                        variables          = EXCLUDED.variables,
                        analysis_notes     = EXCLUDED.analysis_notes,
                        common_confounders = EXCLUDED.common_confounders,
                        papers_using_this  = EXCLUDED.papers_using_this,
                        updated_at         = NOW()
                """), {
                    "name": ds["name"],
                    "full_name": ds.get("full_name", ""),
                    "description": ds.get("description", ""),
                    "variables": json.dumps(ds.get("variables", {}), ensure_ascii=False),
                    "analysis_notes": json.dumps(ds.get("analysis_notes", []), ensure_ascii=False),
                    "common_confounders": json.dumps(ds.get("common_confounders", []), ensure_ascii=False),
                    "papers_using_this": json.dumps(ds.get("papers_using_this", []), ensure_ascii=False),
                })
            seeded += 1
        except Exception as e:
            print(f"  ERROR seeding {f.name}: {e}")
print(f"[datasets] Seeded {seeded} datasets.")

# ── 4. Drafts ────────────────────────────────────────────────────────────
drafts_dir = ROOT / "data" / "drafts"
seeded = 0
if drafts_dir.exists():
    for f in drafts_dir.glob("*.txt"):
        try:
            content = f.read_text(encoding="utf-8")
            with engine.begin() as conn:
                conn.execute(text("""
                    INSERT INTO ma_drafts (safe_title, topic_title, content)
                    VALUES (:safe_title, :topic_title, :content)
                    ON CONFLICT (safe_title) DO UPDATE SET
                        content = EXCLUDED.content
                """), {
                    "safe_title": f.stem,
                    "topic_title": f.stem.replace("_", " "),
                    "content": content,
                })
            seeded += 1
        except Exception as e:
            print(f"  ERROR seeding draft {f.name}: {e}")
print(f"[drafts] Seeded {seeded} drafts.")

print("\nSeed complete. All local data is now in Supabase.")
