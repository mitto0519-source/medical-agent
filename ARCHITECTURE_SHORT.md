# ARCHITECTURE — Short (LLM injection용)

> 매 입력 직전 hook으로 prepend. 긴 ARCHITECTURE.md는 참고용.
> 새 모듈 만들기 전 — 이 파일에서 grep해서 중복 확인 의무.

## 단일 진입점 (이걸로만 호출)
- LLM: `src.llm.get_llm_client(task=...)` — 3-way failover + persona + intent + provenance + tracing auto-wired
- System prompt 합성: `src.llm.claude_client.build_base_system(base, task)` — persona + prompts + seed + insight + reviewer + design + intent 자동 합성
- Harness facade: `src.agent.harness.get_harness(owner, task)` — events + budget + safety + memory + persona + llm + pool 단일 객체
- Memory write: `src.memory.router.write(kind, content, meta)` — gate + scorer + lifecycle 통과 후 저장
- Events log: `src.runtime.events.append(type, payload)` — append-only 감사

## 모듈 맵 (19 sections — 2026-06-14 갱신)
1. 데이터 로딩 — `src/data/kyrbs_raw_loader.py` (21차수) + `knhanes_raw_loader.py` (HN13~HN24, 한글 하위폴더 case-insensitive scan, STATA dta + 지침서 PDF 인지)
2. 통계 분석 — `src/data/stat_bridge.py` (논문용 OR/CI), `src/statistics/medical_stats.py` (UI 빠른), `src/analysis/survey_weighted.py` (★KYRBS/KNHANES strata/cluster/weight 정확 SE — 3-tier: statsmodels.SurveyDesign → rpy2 R survey → naive APPROXIMATE 경고)
3. 논문 파이프라인 — `src/research/research_pipeline.py` (run_full), `paper_writer.py` (섹션별)
4. LLM — `src/llm/factory.py` (get_llm_client), `claude_client.py` (build_base_system). 4 provider 모두 provenance.auto_record_llm_call 배선됨
5. 메모리 — `src/memory/change_log.py`, `self_model.py`, `agent_insight.py`, `conversation_memory.py`, `router.py`
6. RAG — `src/rag/pipeline.py` (RAGPipeline, search_multistage, search_with_rerank, search_hyde), `src/vectordb/store.py` (dynamic collection_name per embedding dim)
7. 클라우드 — `src/cloud/db.py` (cloud_available, get_engine), `src/auth/users.py`
8. UI — `app/streamlit_app.py`, `app/pages/ez_home.py` (10 helper 함수 모두 `src.service.*` 위임), `project_workspace.py`, `app/styles/sapphire_glass.py`
9. 내보내기 — `src/export/word_exporter.py`, `journal_docx_exporter.py`, `reference_library.py`, `figure_builder.py`, `table_builder.py`
10. 검증 — `scripts/audit_wiring.py` (필수), `e2e_diagnose.py`, `test_rag_smoke.py`, `ui_eval.py`, `scripts/register_dataset.py` (★dataset-agnostic dry-run)
11. 운영 런타임 — `src/runtime/events.py`, `tasks.py`, `idempotency.py`, `heartbeat.py`, `backlog.py`, `provenance.py`, `tracing.py`
12. Safety — `src/safety/citation_grounding.py`, `truth_hierarchy.py`, `physician_review.py`, `consistency_checker.py`, `figure_validator.py`, `style_polish.py`, `anti_ai_filter.py`, `unified.py`, `claim_evidence_nli.py` (★3-tier deberta-v3-mnli/LLM-judge/lexical NLI for "real PMID but wrong claim" 차단)
13. Orchestrator — `src/knowledge/orchestrator.py`, `src/agent/writing_orchestrator.py`, `agent_pool.py` (team_review), `planner.py`, `roles.py`, `procedural.py`
14. Harness — `src/agent/harness.py` (AgentHarness facade)
15. 자산화 3단계 (2026-06-01) — `src/knowledge/paper_typology.py`, `humanize_extractor.py`, `src/research/yoosun_finalize.py`, paper_writer FIX 10-15
16. **Service Layer (FRONTEND_MIGRATION Phase1)** — `src/service/` 9 modules: rag/paper/chat/references/figures/data/stats/tables/export. 모두 streamlit 의존성 없음 — Streamlit과 FastAPI 양쪽 공유 계약. ez_home 위임 PASS, audit_wiring 16/16
17. **Reliability Layer (MASTER_UPGRADE §3)** — `src/reliability/` 6 modules: cost_optimizer (★net-new, critical-path reviewer routing), evidence_graph (Claim node on schema_v2), confidence (4축 weighted geomean), snapshot (events.db named checkpoint + rollback), failure_kb (procedural memory + as_avoid_block), journal_intel (compliance_report on journal_targeting word_limit/ref_style)
18. **Dataset Registry (MASTER_UPGRADE §2)** — `data/registry/{kyrbs,knhanes}/variables.yaml` (single source of truth) + `scripts/register_dataset.py` (dry-run diff). KNHANES variables.yaml MISSING=0 검증 완료
19. **Evolution Layer (SELF_EVOLUTION_SPEC)** — `src/evolution/` ledger (candidate→gate result→promote/rollback append-only on events.db) + anchor (★held-out gold_set 6축 채점기 — overall = weighted geomean over non-None axes). ★골드셋 mitto 라벨링 1순위
20. **KNHANES Domain (KYRBS 동격, 2026-06-15)** — `src/data/knhanes_patterns.py` (FLI/HSI/MASLD/MetALD/ALD/IDF MetSx/eGFR CKD-EPI 2021/alcohol_g_week) + `knhanes_subgroup.py` (Asian BMI cat/age_group 4 스킴/income quartile/study_phase IV-IX/pool_years) + `data/registry/knhanes/variables.yaml` (KDCA 매핑) + `KNHANES_VARIABLE_COMPATIBILITY.md` (12 wave 매트릭스). service.data.load_knhanes(year, add_derived=True) 자동 derived 8개 추가, load_knhanes_pooled(years|phase), service.stats.analyze_knhanes (kstrata/psu/wt_itvex 자동 preset)
21. **Universal File Loader (2026-06-15)** — `src/ingestion/universal_loader.py` markitdown 1차 + 전용 fallback. 텍스트 18종/문서 11종/데이터 7종/이미지 7종/미디어 9종/notebook. 이미지는 base64 data URI for Vision LLM. service.data.load_attachment(path) 진입
22. **ChatEvent + Streaming Architecture (FRONTEND_MIGRATION §5.5)** — `src/service/events.py` ChatEvent dataclass + SSE 직렬화. `src/service/chat.py:stream_turn` 3-Lane (HOT status<300ms / STREAM tool_start/tool_result/token / BACKGROUND badge). `app/pages/ez_home.py` reducer + 📌 pin row 9 sections + 컴포저(첨부+모델 picker) + auto-scroll + F5 safe URL pid
23. **Research State Single Source (RESEARCH_STATE_SPEC §1)** — `src/research/research_state.py` 끝부분에 `ResearchProject` dataclass 추가(기존 ResearchState 보존). manuscript.sections 유일 정본, manuscript_text는 파생 property. checkpoint/restore/branch/resume/diff (events.db 위), Supabase ma_research_state DDL. provenance.build_fingerprint에 dataset_version + registry_version 인자 추가 → 결정적 재실행

## 데이터 위치 (자주 까먹는 것 — 2026-06-14 갱신)
- `data/oa_papers/` 689 MB — **12,625편 PMC 본문 + manifest.sqlite** (절대 "없다"고 단정 X)
- `data/chromadb/` — `papers_biomednlppubmedbertbaseu_768d` 41k+ chunks (PubMedBERT 인제스트 진행 중) + legacy `papers` 27,618 (MiniLM 384d, 풀 인제스트 완료 후 드롭 예정)
- `data/medical_knowledge_seed/` 6 MB — typology_catalog.json + humanize_catalog.json + vocabulary
- `data/knowledge_graph/` 13 MB — 10k+ nodes NetworkX + schema_v2 (Claim/EVIDENCED_BY/DERIVED_FROM/CITES_FOR 추가)
- `data/raw/kyrbs*.sav` 2.5 GB — 2005-2025 21차수
- `data/raw/knhanes/` — **HN13~HN24 12 wave 통합본 (.sav)** + STATA `KNHANES_2013_2024.dta` 639MB + 지침서 25 PDFs. variables.yaml 매핑 MISSING=0
- `data/registry/{kyrbs,knhanes}/variables.yaml` — single source of truth (loader가 읽기만)
- `eval/gold_set.json` v0.3.0 — **HELD-OUT** 골드셋 (프롬프트 주입 금지). 6축 슬롯 (라벨 대기)
- `data/runtime/` 14 MB — events.db + tasks.db + idempotency.db + evolution ledger

## 절대 금지
- `ClaudeClient()` 직접 생성 — get_llm_client 우회 = 죽은 경로
- 새 모듈 add 후 `audit_wiring.py` 안 돌림 = dead code
- max_tokens 미지정 LLM 호출 = 출력 잘림
- "X 없다" 단정 — grep 먼저
- 새 모듈 만들고 ARCHITECTURE.md/ARCHITECTURE_SHORT.md 동기화 안 함 = 규칙10 위반 (2026-06-14 사고)
- `eval/gold_set.json` 라벨을 시스템이 자기 채움 = 게이밍 (SELF_EVOLUTION §9: 사용자만 라벨)
- gold_set 프롬프트에 주입 = held-out 위반 (자기 답 외우기)
- 새 데이터셋 wave 받고 register_dataset.py dry-run 안 함 = 변수 매핑 드리프트

## 스펙 6종 체계 (2026-06-14 정합)
1. `REVIEW_FIX_SPEC` — 배관 (FIX-0~FIX-10)
2. `KNOWLEDGE_MODEL_SPEC` — MeSH/UMLS/SNOMED/STROBE/GRADE 표준 + 16 axes + 24 disciplines
3. `MASTER_UPGRADE_ROADMAP` — 데이터(2-plane) + 신뢰성 8계층 (#3만 net-new, 7은 배선/확장)
4. `FRONTEND_MIGRATION_SPEC` — Phase1(service 추출, ★완료) → Phase2(FastAPI SSE) → Phase3(Next.js)
5. `E2E_PILOT_TEST_PLAN` — J1~J11 user journeys + 층별 이분
6. `SELF_EVOLUTION_SPEC` — 골드셋 anchor + 변경 게이트(promote/rollback) + 회귀 가드

★ 모두 한 점으로 수렴: **eval/gold_set.json 사용자 라벨링이 1순위 외부 자산.** 없으면 5계층(레벨/신뢰/자가발전/회귀/측정)이 다 추정.
