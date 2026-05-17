# Medical-Agent — Run & Verification

Quick steps to run locally and verify core functionality.

Prerequisites
- Python 3.10+ installed
- `pip install -r requirements.txt` (or at least `pytest`, `flask`, `streamlit` for UI)
- Create `.env` from `.env.example` and set `ANTHROPIC_API_KEY` for real LLM runs

Run Streamlit UI (local)
```bash
streamlit run app/streamlit_app.py --server.port 8501
```

Run Flask API (local)
```bash
python app/main.py
```

Run functional smoke (no external services)
```bash
python scripts/e2e_functional_smoke.py
```

Run import smoke
```bash
python scripts/e2e_smoke_imports.py
```

Run tests
```bash
pytest -q
```

Verification checklist
- [ ] Health endpoint returns 200: `GET /health`
- [ ] In-memory RAG smoke returns mock answer (see `scripts/e2e_functional_smoke.py`)
- [ ] `tests/test_app_health.py` and `tests/test_functional_smoke.py` pass
- [ ] `.env` contains `ANTHROPIC_API_KEY` for real LLM runs

Notes
- CI workflow runs `pytest` and the functional smoke script on push/PR.
- For full integration tests using real LLMs or Supabase, set `OPENAI_API_KEY`, `GOOGLE_API_KEY`, and/or `SUPABASE_DB_URL` in the environment or CI secrets.
