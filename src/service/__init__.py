"""Service layer — pure-logic entry points consumed by Streamlit (now) and FastAPI (later).

Per FRONTEND_MIGRATION_SPEC.md Phase 1:
- Each function takes plain data in, returns plain data out
- No `streamlit` imports, no `session_state` reads
- ez_home.py imports these and adapts to Streamlit
- FastAPI will import these directly (no rewrites)
"""
__all__ = ["rag", "paper", "chat", "references", "figures", "data", "stats", "tables", "export"]
