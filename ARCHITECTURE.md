# Medical-Agent 아키텍처 레지스트리

> **이 파일의 목적**: 세션이 새로 열릴 때마다 "이 기능은 어디에 있는가", "이미 만든 것인가 아닌가",
> "같은 것인가 다른 것인가"를 즉시 판단할 수 있도록 한다.
>
> **규칙**: 새 모듈을 만들기 전에 반드시 이 파일을 확인한다.
> 모듈을 추가/변경/삭제할 때마다 이 파일을 업데이트한다.
>
> Last updated: 2026-05-19 (status check + zombie cleanup)

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
| **논문용 OR/CI 회귀분석** | `src/data/stat_bridge.py` → `StatBridge` | ✅ active | 로지스틱/GEE/Cox/선형. 논문 파이프라인 전용 |
| **UI 대화형 통계** | `src/statistics/medical_stats.py` → `MedicalStatistics` | ✅ active | 기술통계/t검정/카이제곱/ANOVA. Streamlit UI 전용 |

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

> **research_pipeline vs research_workflow 구분**:
> - `research_pipeline` = 완전 자동화 백엔드 파이프라인 (코드로 직접 실행)
> - `research_workflow` = Streamlit pages/workflow.py의 단계별 UI 상태 관리
> 둘은 다른 용도이므로 공존 정당함.

### 4. LLM 클라이언트

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| Claude API 호출 | `src/llm/claude_client.py` → `ClaudeClient` | ✅ active | 페르소나 주입 포함 |
| OpenAI API 호출 | `src/llm/openai_client.py` → `OpenAIClient` | ✅ active | fallback용 |
| LLM 팩토리 (자동선택) | `src/llm/factory.py` → `get_llm_client()` | ✅ active | 항상 이걸 통해서 호출 |

### 5. 메모리 / 장기기억

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 작업 이력 로그 | `src/memory/change_log.py` | ✅ active | 모든 유의미한 작업 후 기록 |
| 자가 진단/점수 | `src/memory/self_model.py` | ✅ active | smoke test + git 상태 기반 |
| 자가 학습 인사이트 | `src/memory/agent_insight.py` | ✅ active | |
| 자가 반성/기록 | `src/memory/auto_learn.py` | ✅ active | 각 파이프라인 단계 후 자동 호출 |
| 세션 간 대화 맥락 | `src/memory/conversation_memory.py` | ✅ active | |
| 연속성 관리 | `src/memory/continuity.py` | ✅ active | |
| 페르소나 | `src/agent/persona.py` + `data/agent_self/persona.json` | ✅ active | 절대 비활성화 금지 |

### 6. RAG / 지식 베이스

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 벡터 검색 (RAG) | `src/rag/pipeline.py` → `RAGPipeline` | ✅ active | ChromaDB 기반 |
| 벡터 스토어 (로컬) | `src/vectordb/store.py` → `VectorStore` | ✅ active | ChromaDB wrapper |
| 벡터 스토어 (클라우드) | `src/vectordb/supabase_store.py` → `SupabaseVectorStore` | ✅ active | Supabase pgvector |
| PubMed 수집 + 그래프 | `src/knowledge/trend_learner.py` | ✅ active | periodic_learn.py가 호출 |
| 지식 그래프 | `src/knowledge/medical_graph.py` | ✅ active | 10,005 노드 |
| 의학 온톨로지 | `src/knowledge/medical_ontology.py` | ✅ active | |
| 문서 청킹/인제스트 | `src/ingestion/document_reader.py`, `chunker.py` | ✅ active | |
| PubMed 검색 | `src/ingestion/evidence_reader.py` | ✅ active | novelty_checker가 호출 |

### 7. 클라우드 / 인프라

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| Supabase 연결 | `src/cloud/db.py` → `cloud_available()`, `get_engine()` | ✅ active | |
| 사용자 인증 | `src/auth/users.py` | ✅ active | |
| 스토리지 매니저 | `src/storage/manager.py` | ✅ active | |

### 8. UI

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| 메인 Streamlit 앱 | `app/streamlit_app.py` | ✅ active | 진입점 |
| AI 패널 | `app/ai_panel.py` | ✅ active | |
| 워크플로우 페이지 | `app/pages/workflow.py` | ✅ active | ResearchWorkflow 사용 |
| 시각화 | `src/visualization/medical_plots.py` → `MedicalVisualizer` | ✅ active | |
| 활동 로그 (UI용) | `src/activity/logger.py` | ✅ active | |

### 9. 내보내기

| 기능 | 정규 모듈 | 상태 | 비고 |
|------|----------|------|------|
| DOCX 생성 | `src/export/word_exporter.py` | ✅ active | paper_writer가 호출 |
| 그림 생성 | `src/export/figure_builder.py` | ✅ active | |
| 표 생성 | `src/export/table_builder.py` | ✅ active | |

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
