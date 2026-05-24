# AGENTS.md — 에이전트 책임 맵 + 생성/검증 분리 (책임 경계 계약)

> 조언(research OS) ②·④: "생성"과 "검증"을 **완전히 분리**하고, 각 에이전트는 **단일 책임**만 갖는다.
> 책임 중복 = drift·충돌·오염의 원인. 새 기능 추가 시 이 맵을 먼저 확인하고, 책임이 겹치면 만들지 말고 기존 것에 위임한다.

## 핵심 원칙
1. **생성(Generator)과 검증(Verifier)은 절대 같은 호출에서 동시에 하지 않는다.**
   생성은 hallucination 방향, 검증은 constraint 방향 → 충돌. 별도 단계·별도 모듈.
2. **통계는 LLM이 계산하지 않는다.** LLM은 orchestrator/해석만. 실계산은 StatBridge(statsmodels).
3. **단일 상태원본**: 모든 에이전트는 `ResearchState`(JSON AST)만 읽고 수정. 직접 session_state 난립 금지.
4. **메모리는 검증된 것만 commit**: `memory_gate` 통과해야 self-memory/RAG에 저장(self-pollution 차단).

## 책임 맵 (모듈 = 단일 책임, 중복 금지)

### 생성 (Generation)
| 책임 | 정규 모듈 | 비고 |
|------|----------|------|
| 주제 생성 | `research_pipeline.generate_topics` | 연구질문/노출/결과만 |
| 섹션 작성 | `research/paper_writer`, 작업실 `_ws_agent`(intent=write) | 초안 생성만 — 검증 안 함 |
| 자동 파이프라인 | `research_pipeline.run_full` | 오케스트레이션(생성 단계 호출) |

### 검증 (Verification) — 생성과 분리
| 책임 | 정규 모듈 | 검사 대상 |
|------|----------|----------|
| 동료심사 | `research/peer_reviewer.PeerReviewer` | 방법·신규성·구조 (100점 루브릭) |
| 통계 정합 | `diagnostics/stat_consistency` | 논문 OR/p값 ↔ 실분석 결과 대조(환각 탐지) |
| 메모리 위생 | `memory/memory_gate` | self-memory commit 전 quarantine/verified |
| 신규성 | `research/novelty_checker` | PubMed 대비 독창성 |
| 코드 무결성 | `knowledge/code_graph` | 고아/끊긴 import/ARCHITECTURE 대조 |

### 엔진 (Engines) — 도메인 계층 분리
| 계층 | 정규 모듈 | 역할 |
|------|----------|------|
| Statistical | `data/stat_bridge.StatBridge` (statsmodels) | OR/CI/p-trend 실계산 (LLM 아님) |
| Style | `profile/author_profile` | 문체/구조 (지식과 분리) |
| Knowledge(RAG) | `vectordb/store` + `ingestion/hierarchical_chunker` | 근거 — 섹션/role/citation 메타 청킹 |
| Knowledge(Graph) | `knowledge/medical_graph` | 엔티티-관계 |
| Memory(대화) | `memory/conversation_memory` | verbatim + 의미검색 |
| Memory(누적위키) | `knowledge/research_wiki` | 개념 누적 |
| State | `research/research_state.ResearchState` | 논문 JSON AST 단일원본 |
| LLM | `llm/factory.get_llm_client` | provider 폴백(생성/해석만) |

### 자가발전 (Self-evolution) — 검증 게이트 필수
| 책임 | 정규 모듈 | 게이트 |
|------|----------|--------|
| 최신논문 학습 | `knowledge/trend_learner` + `scripts/learn_scheduler` | tier=auto 표식 |
| 인사이트 누적 | `memory/agent_insight.record` | memory_gate 통과만 |
| 페르소나 진화 | `agent/persona.add_perspective` | memory_gate 통과만 |

## 금지 (책임 침범)
- ❌ writer가 자기 글을 스스로 "검증완료"로 표시 → 검증은 PeerReviewer/stat_consistency만.
- ❌ LLM이 p값/OR 계산 → StatBridge만.
- ❌ 검증 없이 self-memory/persona commit → memory_gate 우회 금지.
- ❌ 새 "그림/메모리/그래프" 모듈 난립 → 기존 엔진에 위임(ARCHITECTURE.md 확인).
