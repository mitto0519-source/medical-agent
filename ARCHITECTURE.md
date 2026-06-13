# ARCHITECTURE.md — Auto-generated

> Last regenerated: 2026-06-13 17:20:52
> Source: `scripts/regenerate_architecture.py`
> 수동 편집 금지 — 인벤토리·파일명·count는 실 파일 시스템에서 매번 다시 채움.
> 디자인·아키텍처 결정 같은 prose는 별도 ARCHITECTURE_SHORT.md 에 작성.

## src/ — Python modules (auto-enumerated)

| Module | py files | content |
|---|---|---|
| `activity/` | 1 | logger |
| `agent/` | 14 | agent_pool, cognitive_activation, harness, intent_sensor, medical_agent … |
| `auth/` | 1 | users |
| `citation/` | 1 | manager |
| `cloud/` | 2 | db, migrate |
| `collaboration/` | 1 | access |
| `config/` | 3 | env, logging_config, models |
| `data/` | 4 | col_name_resolver, kyrbs_raw_loader, stat_bridge, survey_loader |
| `diagnostics/` | 7 | capability_bench, improvement_engine, longitudinal_eval, prompt_ab, quality_tracker … |
| `export/` | 13 | citation_workflow, cover_letter_writer, figure_builder, image_gen, journal_docx_exporter … |
| `ingestion/` | 9 | chunker, document_reader, evidence_reader, hierarchical_chunker, oa_bulk_fetcher … |
| `knowledge/` | 11 | citation_graph, code_graph, humanize_extractor, medical_graph, medical_ontology … |
| `library/` | 5 | component_extractor, components, dataset_library, design_template, methods_library |
| `llm/` | 10 | budget, claude_client, factory, gemini_client, health … |
| `memory/` | 15 | agent_insight, auto_learn, change_log, continuity, conversation_memory … |
| `notebooklm/` | 2 | client, paper_sync |
| `profile/` | 1 | author_profile |
| `rag/` | 1 | pipeline |
| `research/` | 14 | analysis_preregistration, autonomous_research_loop, emphasis_profile, long_horizon, novelty_checker … |
| `runtime/` | 10 | backlog, events, heartbeat, hf_bootstrap, idempotency … |
| `safety/` | 10 | anti_ai_filter, audit_trail, causal_checker, citation_grounding, consistency_checker … |
| `statistics/` | 1 | medical_stats |
| `storage/` | 2 | manager, working_paper_store |
| `tools/` | 0 |  |
| `utils/` | 1 | text_sanitize |
| `vectordb/` | 2 | store, supabase_store |
| `visualization/` | 1 | medical_plots |

## data/ — Storage layout (auto-enumerated)

| Folder | file count | extensions (top 4) |
|---|---|---|
| `data/_ux_shots/` | 39 | .png:39 |
| `data/activity/` | 1 | .json:1 |
| `data/agent_self/` | 7 | .json:6, .2026-06-04:1 |
| `data/assets/` | 3 | .json:2, .do:1 |
| `data/author_profiles/` | 2 | .json:2 |
| `data/change_log/` | 1 | .json:1 |
| `data/chromadb/` | 14 | .bin:12, .sqlite3:1, .pickle:1 |
| `data/chromadb_test/` | 9 | .bin:8, .sqlite3:1 |
| `data/diagnostics/` | 7 | .json:6, .txt:1 |
| `data/drafts/` | 43 | .png:16, .svg:15, .txt:7, .docx:3 |
| `data/exports/` | 56 | .docx:13, .png:12, .md:9, .html:6 |
| `data/journals/` | 5 | .json:5 |
| `data/knowledge_graph/` | 5 | .json:5 |
| `data/libraries/` | 3 | .json:3 |
| `data/library/` | 1 | .db:1 |
| `data/logs/` | 5 | .log:4, .1:1 |
| `data/medical_knowledge_seed/` | 28 | .json:28 |
| `data/oa_papers/` | 50504 | .metadata:25251, .json:12625, .txt:12625, .sqlite:1 |
| `data/papers/` | 8 | .docx:6, .pptx:2 |
| `data/pmc_papers/` | 6 | .txt:6 |
| `data/projects/` | 1 | .json:1 |
| `data/raw/` | 45 | .zip:22, .sav:21, .md:1, .json:1 |
| `data/runtime/` | 15 | .db:8, .db-shm:2, .db-wal:2, .json:2 |
| `data/templates/` | 1 | .json:1 |
| `data/wiki/` | 12 | .md:12 |
| `data/workflows/` | 1 | .json:1 |
| `data/working_papers/` | 24 | .json:24 |

## data/runtime/ — Single-core memory backend (full inventory)

| File | Bytes | Purpose hint |
|---|---|---|
| `alerts.log` | 64 | Runtime alerts |
| `events.db` | 10,280,960 | Append-only audit log (CLAUDE.md 규칙 12) |
| `events.db-shm` | 32,768 | Append-only audit log (CLAUDE.md 규칙 12) |
| `events.db-wal` | 716,912 | Append-only audit log (CLAUDE.md 규칙 12) |
| `heartbeat_state.json` | 274 | Heartbeat 7 jobs catch-up state |
| `idempotency.db` | 4,096 | Tool call cache (재현성) |
| `idempotency.db-shm` | 32,768 | Tool call cache (재현성) |
| `idempotency.db-wal` | 45,352 | Tool call cache (재현성) |
| `lifecycle.db` | 28,672 | Memory TTL + decay scheduler |
| `longitudinal.db` | 20,480 | Time-series trends |
| `memory.db` | 0 | Typed memory (scorer/lifecycle/gate) |
| `notifications.json` | 270 | Pending user notifications |
| `physician_review.db` | 32,768 | Review queue + decisions |
| `procedural.db` | 20,480 | Procedural memory (5층 중 4번째) |
| `tasks.db` | 176,128 | TaskRun state machine |

## data/knowledge_graph/ — Graphs (actual filenames)

| File | Bytes | Type |
|---|---|---|
| `citation_graph.json` | 222,181 | Citation network (paper ↔ paper) |
| `code_graph.json` | 467,524 | Code asset graph (e2e_diagnose 자가진단) |
| `graph.json` | 13,426,465 | Main medical knowledge graph (NetworkX) |
| `meta.json` | 108 | Graph metadata + last_updated |
| `trend_state.json` | 34,082 | PubMed 24h trend cache |

## data/oa_papers/ — OA paper collection (정직 통계)

- Total metadata sweep: **0** papers
- Full text collected (.txt): **12,625** (0.0%)
- Metadata-only (no body): **-12,625** ← backfill 대상
- Sidecar JSON: 12,625
- Other (sqlite/.gitignore): 1


## prompts/ — Versioned system prompts (each auto-injected via prompt_loader)

| File | Bytes | Role |
|---|---|---|
| `curated_seed.md` | 8,178 | Curated 2,100 paper seed exemplars |
| `medical_core.md` | 1,972 | Core medical persona |
| `safety_constraints.md` | 2,686 | Hard safety bounds |
| `style_polish.md` | 5,092 | Polish patterns (NEJM/Lancet) |
| `yoosun_style.md` | 2,369 | 조유선 writing style |

## text_sanitize canonical path (정정)

실 위치 (1 file): `src\utils\text_sanitize.py`

이전 문서가 `src/safety/text_sanitize.py` 도 있다고 표기한 건 환각. canonical 위치는 위 한 곳뿐.

