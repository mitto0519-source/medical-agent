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

---

## EstreGenesis / agent-skills 통합 패턴 (2026-05-28 추가)

### 다중 도구 thin bridge (드리프트 방지)

| 도구 | 파일 | 본 SSoT 흡수 |
|------|------|-------------|
| Claude Code | `CLAUDE.md` (11 규칙) | 본 AGENTS.md + ARCHITECTURE.md |
| GitHub Copilot | `.github/copilot-instructions.md` | (필요 시) — 본 파일 가리킴 |
| Cursor | `.cursor/rules/main.mdc` | (필요 시) |
| Gemini CLI | `GEMINI.md` | `build_base_system` 공유 — 동일 prompts/persona/memory |
| 기타 (Cline/Windsurf/Continue) | 각자 룰 파일 | 본 AGENTS.md 참조 |

→ 도구별 룰 변경 금지. 변경은 본 파일 + CLAUDE.md + `prompts/*.md` 에서만.

### Agent-time vs Human-time 추정 (EstreGenesis v1.6.0)

`src/agent/planner.py::Planner.plan(..., pace_mode=)`:

| Mode | agent×human 배수 | 용도 |
|------|-----------------|------|
| `cautious` | 2–4× | 모든 검증 단계 강제 |
| `proactive` | 5–6× | **기본값** |
| `burst` | 6–8× | 빠른 prototype |
| `sprint` | 9–10× | 데모/실험 (최소 검증) |

각 `TaskNode`: `agent_time_sec + human_review_time_sec + wall_clock_sec` 분리 보고.

### 의학 논문 도메인 슬래시 커맨드 (agent-skills 패턴)

`src/agent/slash_commands.py`:

| 슬래시 | 동작 | 내부 호출 |
|--------|------|----------|
| `/research-question` | 가설 + novelty | pubmed_search + cross_modal_query |
| `/study-design` | KYRBS/KNHANES + STROBE | strobe_check + design template |
| `/run-analysis` | StatBridge 회귀 + figure | kyrbs_stat + build_figure |
| `/draft-section` | content + style 2-layer | find_components + apply_author_style + patch_preview |
| `/strobe-review` | 22항목 + consistency + causal | strobe_check + consistency_check + causal_check |
| `/submit-journal` | docx + figure + EndNote XML | WordExporter + reference_library |

### 합리화 방지 (agent-skills "rationalization defense")

흔한 변명 + 우리 반박 메모리:
- ❌ "나중에 추가할게요" → [[feedback_wiring_not_creation]]
- ❌ "아마 동작할 거예요" → [[feedback_no_lies]]
- ❌ "OneDrive 때문이에요" → [[feedback_no_lies]] (외부 탓 금지)
- ❌ "사용자가 묻기 전에 알 수 없어요" → [[feedback_proactive_to_be]]
- ❌ "각 layer는 따로 동작합니다" → [[feedback_organism_flow]]

증거 요건 (협상 불가):
- 코드 변경 → `python scripts/audit_wiring.py` PASS
- LLM 동작 → 실 generate 결과 (PONG 아님)
- 데이터 변경 → events.db append 확인 (`python scripts/replay_task.py`)

### `_lessons/` = `memory/feedback_*.md`

50건 ceiling → 패턴화 → `docs/troubleshooting/` 정착 (EstreGenesis 패턴).
현재 11건 → 안전.
