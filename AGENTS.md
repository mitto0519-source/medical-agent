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

---

## 🔁 Loop Engineering Catalog (2026-06-15 — LOOP_ENGINEERING_SPEC §1)

> Addy Osmani · Boris Cherny — "프롬프트 짜기"에서 "루프 짜기"로. Medical-Agent는 6 부품 모두 동등 이상 보유.

### 등록 루프 12개 (`src/loops/registry.py:list_loops()`)

| 이름 | trigger | purpose |
|---|---|---|
| `heartbeat:periodic_learn` | hourly | PubMed 24h trend 자동 수집 |
| `heartbeat:backlog_drain` | 5min | 파일 인제스트 큐 처리 |
| `heartbeat:reconcile_state` | daily | CURRENT_STATE.json 갱신 |
| `backlog:ingest_paper` / `register_dataset` / `rag_reindex` / `style_profile` / `checkpoint` / `quality_eval` | manual | 6 handlers (백로그 처리) |
| `critique:revise_with_critique` | manual | writer↔critic 분리 (★self_bias_guard 자동) |
| `evolution:gate` | manual | candidate→골드셋→promote/rollback |
| `research:autonomous` | manual | autopilot run_full IMRAD |

### Slash 명령

`/loop [name]` · `/goal <목표>` · `/triage` · `/state` · `/checkpoint <label>` · `/branch <cp_id> <제목>` · `/help`

### Sub-agent diversity (self-bias guard)

writer ≠ critic 강제. 같은 family면 cross-family critic 추천. 라우팅:
- `paper_section` (writer) → Sonnet (standard tier)
- `critic_review` (검사) → Opus (premium tier) — cross-tier로 self-bias 차단
- `physician_review`, `stat_review` → premium (의료 보수)

### State view (오늘 어디까지)

`src/loops/state_view.today_view(owner_email)` → ResearchProject 진행도 + 인제스트 % + 골드셋 라벨 진척 + self_model 다음 한 수.
사이드바 expander로 노출.

### 인지적 항복 방지

- 5턴+ 연속 자동 응답 → 사이드바 노란 배지 "직접 본문 점검 권장"
- 골드셋 0건 + 10턴 → "라벨링 1순위" 알림
- self-bias warning 발생 → critic 모델 교체 권장
- confidence < 0.6 → "검토 필수" 빨간 배지

상세: `LOOP_ENGINEERING_SPEC.md`.
