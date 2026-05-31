# ARCHITECTURE — Short (LLM injection용)

> 매 입력 직전 hook으로 prepend. 긴 ARCHITECTURE.md는 참고용.
> 새 모듈 만들기 전 — 이 파일에서 grep해서 중복 확인 의무.

## 단일 진입점 (이걸로만 호출)
- LLM: `src.llm.get_llm_client(task=...)` — 3-way failover + persona + intent + provenance + tracing auto-wired
- System prompt 합성: `src.llm.claude_client.build_base_system(base, task)` — persona + prompts + seed + insight + reviewer + design + intent 자동 합성
- Harness facade: `src.agent.harness.get_harness(owner, task)` — events + budget + safety + memory + persona + llm + pool 단일 객체
- Memory write: `src.memory.router.write(kind, content, meta)` — gate + scorer + lifecycle 통과 후 저장
- Events log: `src.runtime.events.append(type, payload)` — append-only 감사

## 모듈 맵 (15 sections)
1. 데이터 로딩 — `src/data/kyrbs_raw_loader.py` (KYRBSLoader, KNHANESLoader)
2. 통계 분석 — `src/data/stat_bridge.py` (논문용 OR/CI), `src/statistics/medical_stats.py` (UI 빠른)
3. 논문 파이프라인 — `src/research/research_pipeline.py` (run_full), `paper_writer.py` (섹션별)
4. LLM — `src/llm/factory.py` (get_llm_client), `claude_client.py` (build_base_system)
5. 메모리 — `src/memory/change_log.py`, `self_model.py`, `agent_insight.py`, `conversation_memory.py`, `router.py`
6. RAG — `src/rag/pipeline.py` (RAGPipeline, search_multistage), `src/vectordb/store.py`
7. 클라우드 — `src/cloud/db.py` (cloud_available, get_engine), `src/auth/users.py`
8. UI — `app/streamlit_app.py`, `app/pages/ez_home.py`, `project_workspace.py`, `app/styles/sapphire_glass.py`
9. 내보내기 — `src/export/word_exporter.py`, `journal_docx_exporter.py`, `reference_library.py`, `figure_builder.py`, `table_builder.py`
10. 검증 — `scripts/audit_wiring.py` (필수), `e2e_diagnose.py`, `test_rag_smoke.py`, `ui_eval.py`
11. 운영 런타임 — `src/runtime/events.py`, `tasks.py`, `idempotency.py`, `heartbeat.py`, `backlog.py`, `provenance.py`, `tracing.py`
12. Safety — `src/safety/citation_grounding.py`, `truth_hierarchy.py`, `physician_review.py`, `consistency_checker.py`, `figure_validator.py`, `style_polish.py`, `anti_ai_filter.py` (신규), `unified.py`
13. Orchestrator — `src/knowledge/orchestrator.py`, `src/agent/writing_orchestrator.py`, `agent_pool.py` (team_review), `planner.py`, `roles.py`, `procedural.py`
14. Harness — `src/agent/harness.py` (AgentHarness facade)
15. 자산화 3단계 (2026-06-01) — `src/knowledge/paper_typology.py` (12,145편 → 400 패턴), `humanize_extractor.py` (12,301편 → 560 문장), `src/research/yoosun_finalize.py`, paper_writer FIX 10-15

## 데이터 위치 (자주 까먹는 것)
- `data/oa_papers/` 689 MB — **12,301편 PMC 본문 + manifest.sqlite** (절대 "없다"고 단정 X)
- `data/chromadb/` 262 MB — papers collection 20,894 chunks
- `data/medical_knowledge_seed/` 6 MB — typology_catalog.json + humanize_catalog.json + vocabulary
- `data/knowledge_graph/` 13 MB — 10,005 nodes NetworkX
- `data/raw/` 2,853 MB — KYRBS .sav 21개 차수
- `data/runtime/` 14 MB — events.db + tasks.db + idempotency.db + budget.json

## 절대 금지
- `ClaudeClient()` 직접 생성 — get_llm_client 우회 = 죽은 경로
- 새 모듈 add 후 `audit_wiring.py` 안 돌림 = dead code
- max_tokens 미지정 LLM 호출 = 출력 잘림
- "X 없다" 단정 — grep 먼저
