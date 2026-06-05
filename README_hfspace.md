---
title: Medical-Agent
emoji: 🔬
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 8501
pinned: false
license: mit
short_description: Vibe paper copilot for clinical/translational medicine
---

# Medical-Agent

Lovable-style chat-only paper copilot for clinical/translational medicine.

Built on KYRBS/KNHANES/NHIS/HIRA/KCCR data with HF Datasets bootstrap + Supabase live state.

## Architecture
- Static data (12K+ PMC OA papers, 21 KYRBS waves, ChromaDB, knowledge graph) → HF Datasets `cave87/medical-agent-runtime`
- Live user state (12 ma_* tables) → Supabase
- LLM 3-way failover: Claude → OpenAI → Gemini

## Required Secrets (Settings → Repository secrets)
- `HF_TOKEN` — to download data from cave87/medical-agent-runtime
- `SUPABASE_DB_URL` — live user state
- `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY` — at least one
- `NCBI_EMAIL` — PubMed API
