#!/usr/bin/env python3
"""E2E Import Smoke Script

Attempts to import key modules to surface syntax/import-time errors and
reports required environment variable presence.
"""
import importlib
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

MODULES = [
    # Skip top-level Streamlit app imports which execute on import
    "app.ai_panel",
    "src.ingestion.pdf_reader",
    "src.ingestion.document_reader",
    "src.ingestion.chunker",
    "src.vectordb.store",
    "src.vectordb.supabase_store",
    "src.llm.claude_client",
    "src.papergen.manuscript_gen",
    "src.research.research_pipeline",
    "src.agent.medical_agent",
]

errors = []
print("Running import smoke checks...\n")
for mod in MODULES:
    try:
        importlib.import_module(mod)
        print(f"[OK] Imported {mod}")
    except Exception as e:
        print(f"[ERR] Import failed: {mod} -> {e.__class__.__name__}: {e}")
        tb = traceback.format_exc()
        errors.append((mod, tb))

print("\nEnvironment variables check:")
required = ["ANTHROPIC_API_KEY"]
optional = ["OPENAI_API_KEY", "SUPABASE_DB_URL", "GOOGLE_API_KEY"]
missing_required = []
for var in required:
    if not os.environ.get(var):
        missing_required.append(var)
        print(f"  - MISSING required: {var}")
    else:
        print(f"  - OK: {var}")
for var in optional:
    print(f"  - {'SET' if os.environ.get(var) else 'not set'}: {var}")

print("\nSummary:")
if errors:
    print(f"  - {len(errors)} import errors detected. See details below.")
    for mod, tb in errors:
        print(f"\n--- {mod} trace ---\n")
        print(tb)
else:
    print("  - No import errors detected.")

if missing_required:
    print("\nCritical environment variables missing. E2E cannot proceed until these are set.")
    sys.exit(2)

print("\nImport smoke finished. If no critical envs missing, next step is functional smoke (ingest→vector→query→papergen).")
sys.exit(0)
