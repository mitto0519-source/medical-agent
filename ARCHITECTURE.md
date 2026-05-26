# Medical-Agent 아키텍처 레지스트리

> **이 파일의 목적**: 세션이 새로 열릴 때마다 "이 기능은 어디에 있는가", "이미 만든 것인가 아닌가",
> "같은 것인가 다른 것인가"를 즉시 판단할 수 있도록 한다.
>
> **규칙**: 새 모듈을 만들기 전에 반드시 이 파일을 확인한다.
> 모듈을 추가/변경/삭제할 때마다 이 파일을 업데이트한다.
>
> Last updated: 2026-05-21 (FeedbackStore + PMCDownloader + PaperIngester + 개선 모드 UI)

---

## 모듈 맵 (기능 → 정규 위치)

### 1. 데이터 수집/로딩

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| KYRBS .sav 실제 로더 | `src/data/kyrbs_raw_loader.py` → `KYRBSLoader` | ✅ active | 2005~2025 21개 차수 지원 |
| KNHANES .sav 실제 로더 | `src/data/kyrbs_raw_loader.py` → `KNHANESLoader` | ✅ active | 같은 파일에 동거 |
| KYRBS 다운로드 자동화 | `scripts/download_kyrbs.py` | ✅ active | KDCA 21개 차수 + 코드북 |

### 2. 통계 분석

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| **논문용 OR/CI 회귀분석** | `src/data/stat_bridge.py` → `StatBridge` | ✅ active | 로지스틱/GEE/Cox/PSM/다수준/선형/민감도. 논문 파이프라인 전용 |
| **컬럼명 자동 매핑** | `src/data/col_name_resolver.py` → `ColNameResolver` | ✅ active | 18개 표준변수 패턴매칭 + LLM 폴백 → spec 자동 remapping |
| **UI 대화형 통계** | `src/statistics/medical_stats.py` → `MedicalStatistics` | ✅ active | 기술통계/t검정/카이제곱/ANOVA. Streamlit UI 전용 |
| **연구 설계 패턴 자산** | `src/library/design_template.py` → `DesignTemplate` | ✅ active | 논문 설계 패턴(모델링 전략/공변량 분류/Table·Figure 구조) 자산화. 조유선 KYRBS 단면연구 시드. build_context로 논문 작성 시 '구조 라인' 주입 |

> **stat_bridge vs medical_stats 구분**:
> - `stat_bridge` = 논문 파이프라인 (run_full → 실 데이터 → OR/CI → 논문 본문 자동 주입)
> - `medical_stats` = Streamlit UI의 "데이터 탐색" 탭 (사용자가 직접 컬럼 선택 → 빠른 통계)
> 둘은 다른 용도이므로 공존 정당함.

### 3. 논문 생산 파이프라인

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| **원스톱 논문 파이프라인** | `src/research/research_pipeline.py` → `ResearchPipeline` | ✅ active | run_full() = 주제→신규성→통계→논문→심사 |
| 논문 작성 (섹션별) | `src/research/paper_writer.py` → `PaperWriter` | ✅ active | pipeline이 내부적으로 호출 |
| 단계별 UI 워크플로우 | `src/research/research_workflow.py` → `ResearchWorkflow` | ✅ active | app/pages/workflow.py 전용 상태머신 |
| 신규성 확인 (PubMed) | `src/research/novelty_checker.py` → `NoveltyChecker` | ✅ active | pipeline이 내부적으로 호출 |
| 동료 심사 | `src/research/peer_reviewer.py` → `PeerReviewer` | ✅ active | pipeline이 내부적으로 호출 |
| 연구 프로젝트 관리 | `src/research/project_manager.py` → `ProjectManager` | ✅ active | data/projects/ 영속 추적, 단계별 상태+파일 경로 관리 |
| **자율 연구 루프 (Phase A)** | `src/research/autonomous_research_loop.py` → `AutonomousResearchLoop` | ✅ active | Google Deep Research 수준. 반복 PubMed탐색+가설수정. **write_paper_with_stats(deep_research=True)로 연결** — 주제 유지(통계 일관성) + 근거만 reference_context에 보강 |

> **research_pipeline vs research_workflow 구분**:
> - `research_pipeline` = 완전 자동화 백엔드 파이프라인 (코드로 직접 실행)
> - `research_workflow` = Streamlit pages/workflow.py의 단계별 UI 상태 관리
> 둘은 다른 용도이므로 공존 정당함.

### 4. LLM 클라이언트

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| Claude API 호출 | `src/llm/claude_client.py` → `ClaudeClient` | ✅ active | 페르소나 주입. `build_base_system()` 공유함수(전 LLM 일관 주입) |
| OpenAI API 호출 | `src/llm/openai_client.py` → `OpenAIClient` | ✅ active | fallback용 |
| Gemini API 호출 | `src/llm/gemini_client.py` → `GeminiClient` | ✅ active | 무료티어 폴백. ClaudeClient와 동일 generate() 시그니처 |
| LLM 팩토리 (자동선택) | `src/llm/factory.py` → `get_llm_client()` | ✅ active | 항상 이걸 통해서 호출. 3중 연쇄폴백(Claude→OpenAI→Gemini) + 건강도 자동 우선순위 |
| LLM 건강도 추적 | `src/llm/health.py` → `order_by_health()` | ✅ active | 작동하는 provider 자동 우선 + 품질순위. data/diagnostics/llm_health.json |

### 5. 메모리 / 장기기억

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 작업 이력 로그 | `src/memory/change_log.py` | ✅ active | 모든 유의미한 작업 후 기록 |
| 자가 진단/점수 | `src/memory/self_model.py` | ✅ active | smoke test + git 상태 기반 |
| 자가 학습 인사이트 | `src/memory/agent_insight.py` | ✅ active | |
| 자가 반성/기록 | `src/memory/auto_learn.py` | ✅ active | 각 파이프라인 단계 후 자동 호출 |
| 세션 간 대화 맥락 | `src/memory/conversation_memory.py` | ✅ active | |
| 연속성 관리 | `src/memory/continuity.py` | ✅ active | |
| 의미론적 기억 검색 | `src/memory/semantic_search.py` | ✅ active | insights.json + 이력 키워드 유사도 검색 → LLM 프롬프트 주입 |
| **역량 자기평가 벤치마크 (Phase C)** | `src/diagnostics/capability_bench.py` → `CapabilityBench` | ✅ active | 논문 완성 후 7개 차원 자동 평가. 약점 → capability_insights.json 누적. **루프 닫힘**: `get_improvement_context()` → `_build_system()` 주입으로 다음 작성에 자동 반영 |
| **실 리뷰어 피드백 저장소** | `src/memory/user_feedback_store.py` → `FeedbackStore` | ✅ active | 실제 저널 리뷰어 코멘트 누적. 키워드 오버랩 검색 → `build_context()`/`get_reviewer_patterns()`. `_build_system()` + paper_writer에 자동 주입. data/feedback/feedback_store.json |
| 페르소나 | `src/agent/persona.py` + `data/agent_self/persona.json` | ✅ active | 절대 비활성화 금지 |

### 6. RAG / 지식 베이스

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 벡터 검색 (RAG) | `src/rag/pipeline.py` → `RAGPipeline` | ✅ active | ChromaDB 기반 |
| 벡터 스토어 (로컬) | `src/vectordb/store.py` → `VectorStore` | ✅ active | ChromaDB wrapper |
| 벡터 스토어 (클라우드) | `src/vectordb/supabase_store.py` → `SupabaseVectorStore` | ✅ active | Supabase pgvector |
| PubMed 수집 + 그래프 | `src/knowledge/trend_learner.py` | ✅ active | periodic_learn.py가 호출 |
| 지식 그래프 (의학) | `src/knowledge/medical_graph.py` | ✅ active | 10,005 노드. NetworkX. PubMed 자동수집 자가발전 |
| 지식 그래프 (코드) | `src/knowledge/code_graph.py` → `CodeGraph` | ✅ active | 코드 구조 자산화(ast, NetworkX). 981노드. 고아/끊긴import/ARCHITECTURE대조 자가진단 → e2e_diagnose 연계. 규칙10 자동화 |
| 의학 온톨로지 | `src/knowledge/medical_ontology.py` | ✅ active | |
| 문서 청킹/인제스트 | `src/ingestion/document_reader.py`, `chunker.py` | ✅ active | |
| **멀티에이전트 병렬 풀 (Phase B)** | `src/agent/agent_pool.py` → `AgentPool` | ✅ active | StatAgent/LitAgent/WritingAgent/ReviewAgent. ThreadPoolExecutor 기반. **write_paper_with_stats(parallel=True)로 연결** — _parallel_pre_collect()가 PMC다운로드(I/O)+신규성(LLM) 동시 실행 |
| PubMed 검색 | `src/ingestion/evidence_reader.py` | ✅ active | novelty_checker가 호출 |
| **PMC 오픈액세스 전문 다운로더** | `src/ingestion/pmc_downloader.py` → `PMCDownloader` | ✅ active | PMC 오픈액세스 논문 전문 XML 다운로드 → data/pmc_papers/ 캐시 → RAGPipeline.ingest_file() 자동 인덱싱. write_paper_with_stats() 호출 전 자동 실행. |
| **기존 논문 파서 (개선 모드)** | `src/ingestion/paper_ingester.py` → `PaperIngester` | ✅ active | DOCX/PDF/TXT 파싱 → IMRAD 섹션 분리 → IngestedPaper. Streamlit "기존 논문 개선" 페이지에서 사용. data/drafts/uploaded/ 캐시. |

### 7. 클라우드 / 인프라

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| Supabase 연결 | `src/cloud/db.py` → `cloud_available()`, `get_engine()` | ✅ active | |
| 사용자 인증 | `src/auth/users.py` | ✅ active | `is_admin()` super_admin 2명+admin role = full access |
| 스토리지 매니저(참고문헌 RAG) | `src/storage/manager.py` | ✅ active | NotebookLM/RAG 적재 |
| **작성 논문 영속 저장** | `src/storage/working_paper_store.py` | ✅ active | 작업실 6섹션을 계정 귀속 저장/불러오기(data/working_papers, 로컬+클라우드 best-effort). manager.py와 별개 |
| **State Registry (논문 JSON AST)** | `src/research/research_state.py` → `ResearchState` | ✅ active | 논문 단일 진실원본: 섹션별 content+status(empty/draft/verified/locked) + study + stat + citations. 잠긴 섹션은 자동생성이 덮어쓰기 금지(drift 차단). 작업실 🔒 토글, 저장 시 meta._status 영속 |
| **데이터 단일 해결** | `app/streamlit_app.py` → `_ensure_raw_df()`, `_raw_data_available()` | ✅ active | 전 페이지 공유: 세션→data/raw 자동로드(_find_real_data). 업로드 강요 제거 |
| **대화 영속 메모리(MemPalace식)** | `src/memory/conversation_memory.py` → `record()`, `recall_relevant()` | ✅ active | verbatim 저장 + ChromaDB 의미검색 회수(계정격리). 요약/최근만이 아니라 '관련 과거'를 회수 |
| **메모리 위생 게이트** | `src/memory/memory_gate.py` → `assess()` | ✅ active | self-pollution 차단: 너무짧음/중복/환각마커=quarantine(저장거부), tier(verified/auto) 부여. agent_insight·persona가 commit 전 호출. LLM무관 |
| **계층 RAG 청킹** | `src/ingestion/hierarchical_chunker.py` → `chunk_paper()` | ✅ active | 섹션 인식 청킹 + 메타(section/rhetorical_role/citation_density/statistical_method/evidence_level). trend_learner 인제스트가 사용. 일반 token chunk 대체 |
| **누적 지식 위키(OpenKB식)** | `src/knowledge/research_wiki.py` → `ResearchWiki` | ✅ active | 개념 페이지 누적(생성/추가)+[[링크]]+lint. add_source/build_context/query. 작업실 글쓰기에 주입+저장시 백그라운드 흡수. data/wiki/{owner}/ |
| 컨테이너화 | `Dockerfile`, `docker-compose.yml`, `.dockerignore` | ✅ active | code-in-image + data/ 볼륨. OneDrive 환경함정 근본차단. `docker compose up -d --build` |

### 8. UI

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 메인 Streamlit 앱 | `app/streamlit_app.py` | ✅ active | 진입점. Before/After 수정 비교 UI + 그림 갤러리 + 리뷰어 피드백 저장 + 기존 논문 개선 모드 포함 |
| AI 패널 | `app/ai_panel.py` | ✅ active | |
| 워크플로우 페이지 | `app/pages/workflow.py` | ✅ active | ResearchWorkflow 사용 |
| 시각화 | `src/visualization/medical_plots.py` → `MedicalVisualizer` | ✅ active | |
| 활동 로그 (UI용) | `src/activity/logger.py` | ✅ active | |

### 9. 내보내기

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| DOCX 생성 | `src/export/word_exporter.py` | ✅ active | paper_writer가 호출 |
| 저널 DOCX 생성 | `src/export/journal_docx_exporter.py` | ✅ active | JournalStyle 적용, EndNote XML+BibTeX 동시 생성 |
| 저널 레지스트리 | `src/export/journal_registry.py` | ✅ active | data/journals/styles/*.json, 미등록 시 LLM 자동 생성 |
| 참고문헌 라이브러리 | `src/export/reference_library.py` | ✅ active | PubMed API, Vancouver/APA 포맷, EndNote XML, BibTeX |
| STATA do-file 생성 | `src/export/stata_exporter.py` | ✅ active | 연구 스펙→STATA 분석 코드(svy:logistic+Table1+subgroup+sensitivity) |
| 그림 생성 + Forest Plot | `src/export/figure_builder.py` | ✅ active | `stat_result_to_forest_plot()` — StatBridge 결과→PNG 자동 저장. Malgun Gothic 한글 폰트 |
| **출판용 전체 그림/표 생성** | `src/export/publication_figure_generator.py` → `PublicationFigureGenerator` | ✅ active | FigureLabs 수준. Forest/ROC/유병률/서브그룹/Table1/Table2/계수플롯 300dpi PNG+SVG |
| 표 생성 | `src/export/table_builder.py` | ✅ active | |
| 커버 레터 생성 | `src/export/cover_letter_writer.py` | ✅ active | 저널+주제+리뷰 결과 기반 영문 커버 레터 LLM 생성 |

### 10. 검증 / 자가진단 (Eval — 다층)

> Anthropic 'evals for AI agents' 방식의 다층 검증. 코드 무결성(LLM무관) + 실통계 회귀 + 실브라우저 회귀.

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 코드 무결성 진단 | `scripts/e2e_diagnose.py` | ✅ active | import전수+심볼+self_model+code_graph (LLM무관) |
| 통계엔진 회귀(실데이터) | `scripts/prove_stata_e2e.py` | ✅ active | 실 KYRBS→StatBridge→표/그림. ZCB aOR 재현 |
| **UI 회귀 eval(브라우저)** | `scripts/ui_eval.py` | ✅ active | Playwright admin 로그인→페이지별 grader+워크플로 outcome(채팅→섹션, 저장→복원). 45 assertions |
| RAG/모듈 스모크 | `scripts/test_rag_smoke.py` | ✅ active | 임포트+ChromaDB 절대기준 |

### 11. 운영 런타임 (Operational Runtime) — 2026-05-25 신규

> 24/7 안정 운영을 위한 인프라 레이어. SQLite + asyncio 기반 — 외부 의존(Redis/Temporal) 없음.

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| **Event Sourcing** (append-only 감사로그) | `src/runtime/events.py` | ✅ active | SQLite WAL, replay/find/span. LLM·메모리쓰기·작업전이 전부 기록. 환각 추적 핵심 |
| **TaskRun State Machine** (durable workflow) | `src/runtime/tasks.py` | ✅ active | CREATED→RUNNING→...→COMPLETED/FAILED, idempotency_key 캐시 24h, stale recover, steps 누적 |
| **Idempotency Cache** | `src/runtime/idempotency.py` | ✅ active | PubMed/CrossRef/LLM 같은 입력 재호출 캐시. `@idempotent(ns, key_fn)` 데코레이터 |
| **Reasoning Budget** | `src/llm/budget.py` | ✅ active | 일/주 비용 ceiling + 80% 도달 시 google 자동 다운그레이드. events 기반 집계 |
| **Memory Router** (typed write) | `src/memory/router.py` | ✅ active | episodic/semantic/procedural/goal 라우팅. memory_gate + scorer 통과 후 저장 |
| **Memory Scorer** | `src/memory/scorer.py` | ✅ active | importance/novelty/recurrence/trust 산출 → gate 결정(store/review/quarantine/skip) |
| **Memory Lifecycle** (TTL/decay/충돌) | `src/memory/lifecycle.py` | ✅ active | 일별 confidence decay, 만료 archive, 천단위콤마/소수/% 충돌 감지+supersede |
| **Heartbeat** (정기 작업 단일 진입) | `src/runtime/heartbeat.py` | ✅ active | 부팅 catch-up + 분단위 polling. task_recover/lifecycle_tick/idempotency_gc/budget_snapshot/trend_learn 흡수 |
| EndNote CWYW docx 빌더 | `scripts/build_endnote_docx.py` | ✅ active | EN.CITE 필드(travelling library 임베드) Word docx 생성 |

> **연결 흐름**: heartbeat가 lifecycle/budget/task를 정기 실행 · 모든 LLM/메모리/도구 호출은 events로 감사 · TaskRun이 작업 중복방지+크래시 복구 · 라우터가 메모리 쓰기 단일 진입.

---

## 삭제된 모듈 (왜 없는지 기록)

| 모듈 | 삭제일 | 삭제 이유 | 대체 모듈 |
|------|--------|----------|----------|
| `src/database/db_manager.py` | 2026-05-19 | cloud/db.py로 대체, 미참조 | `src/cloud/db.py` |
| `src/nlp/novelty_detector.py` | 2026-05-19 | research/novelty_checker.py로 대체, 미참조 | `src/research/novelty_checker.py` |
| `src/papergen/manuscript_gen.py` | 2026-05-19 | research/paper_writer.py로 대체, 미참조 | `src/research/paper_writer.py` |
| `src/learning/meta_learner.py` | 2026-05-19 | memory/auto_learn.py가 실제 사용, learning/ 전체 미참조 | `src/memory/auto_learn.py` |
| `src/learning/finetune_manager.py` | 2026-05-19 | 위와 동일 | `src/memory/auto_learn.py` |
| `src/learning/knowledge_distiller.py` | 2026-05-19 | 위와 동일 | `src/memory/auto_learn.py` |
| `src/learning/outcome_tracker.py` | 2026-05-19 | 위와 동일 | `src/memory/auto_learn.py` |
| `examples/` (전체) | 2026-05-19 | 삭제된 모듈만 참조, 유지 가치 없음 | — |
| `src/statistics/auto_analyzer.py` | 2026-05-19 | 미호출 dead code. stat_bridge가 OR/CI 담당 | `src/data/stat_bridge.py` |
| `src/statistics/results_writer.py` | 2026-05-19 | 미호출 dead code. paper_writer가 직접 처리 | `src/research/paper_writer.py` |
| `SurveyLoader.generate_synthetic()` | 2026-05-19 | 합성 데이터 생성 전면 금지. 실제 원시자료만 허용 | `src/data/kyrbs_raw_loader.py` |
| `StatBridge.quick_demo()` | 2026-05-19 | 합성 데이터 기반 demo 함수. 동일 사유 삭제 | — |

---

## 새 모듈 추가 프로세스

새 기능을 만들기 전에 반드시:
1. 이 파일에서 같은 기능이 이미 있는지 확인
2. 없으면 추가하되 표에 먼저 기재 (status: 🔨 building)
3. 완성 후 status: ✅ active로 변경
4. 기존 모듈을 대체하는 경우: 기존 것 삭제 + "삭제된 모듈" 표에 기록

---

## 현재 ⚠️ 정리 대기 중

| 항목 | 내용 | 계획 |
|------|------|------|
