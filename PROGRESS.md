# PROGRESS.md — Medical-Agent State Layer

> Harness Engineering State Layer, Medical-Agent 도메인 특화.
> 의학 연구 파이프라인은 PICO → Design → Data → Analysis → Manuscript → Review의
> 6단계 ResearchState AST를 갖는다. 이 파일은 **현재 어느 stage에 있는지** + **clinical
> reasoning 의사결정 흔적**을 사람·에이전트 모두 읽도록 요약한다.

## 현재 활성 작업 (2026-06-11)

**Stage**: 인프라 안정화 (PRE-RESEARCH)
**활성 ResearchState**: 없음 (사용자가 새 vibe paper 세션 시작 대기)

### LLM 인프라 (P0 차단)
| Provider | 상태 | 근거 |
|---|---|---|
| Anthropic | 🚫 죽음 | `"Your credit balance is too low"` — paper_writer/physician_review 양식 사용 불가 |
| OpenAI | 🚫 죽음 | `"You exceeded your current quota"` |
| Google | 🟡 한계 | 무료 5 RPM tier, 24-110초 latency, 의학 깊이 부족 |
| OpenRouter | 🟢 준비 완료 | 코드 추가됨 (`src/llm/openrouter_client.py`) — `.env`에 `OPENROUTER_API_KEY=...` 추가 시 즉시 활성화 |

→ **clinical reasoning은 paid Claude/OpenAI 권장. 보조·요약·tool routing은 OpenRouter free로 충분.**

### 단일 코어 wiring 검증 결과 (2026-06-11)
| 코어 | 양식 | 검증 |
|---|---|---|
| `persona.get_system_prompt("paper_writing")` | "한국 공중보건 연구 AI, 의학박사 수준, 학구적 호기심·비판적 고찰" | ✅ 주입 확인 |
| `conversation_memory.recall_relevant` | cross-session 5층 메모리 (working/episodic/semantic/procedural/goal) | ✅ 629자 회수 |
| `build_system_with_preview` | persona + medical_seed + RAG + preview + recall + change_log | ✅ 5101자 합성 |
| `medical_graph` | 10,120 노드 / 54,026 엣지 (last_updated 2026-06-09) | ✅ 로드 |
| `events.append` / `memory.router.write` / `change_log.log` | 매 채팅 턴 자동 누적 | ✅ wiring 확인 |

### Vibe Paper UX (2026-06-11)
- ✅ chat(좌) + preview(우) 고정 2-split 단일 페이지
- ✅ 600px 고정 높이 스크롤 컨테이너 (무한 확장 X)
- ✅ `generate_streamed` 토큰 스트리밍
- ✅ Preview empty state 로고 + tagline
- ⏳ Go wide / Go deep parallel exploration 트리거 (Figma 패턴 적용 예정)
- ⏳ figurelabs 양식 PublicationFigureGenerator 채팅 hookup

## ResearchState AST (도메인 모델)

모든 진행 중 연구는 `data/working_papers/{pid}.json` + (예정) `data/research_state/{pid}/` 에 다음 양식으로 저장:

```
ResearchState
├── pico: {population, intervention/exposure, comparison, outcome}
├── design: {strobe_type, dataset, year_range, sample_size, eligibility}
├── methods: {stat_models, covariates, sensitivity_plans, software}
├── results: {tables, figures, effect_sizes, ci, p_values}
├── manuscript: {abstract, intro, methods, results, discussion, conclusion}
├── citations: [{pmid, doi, used_in_section, claim}]
└── audit: {decisions_log, review_notes, conflicts_resolved}
```

이 AST의 일부만 채워져 있어도 `paper_writer`/`physician_review`/`stat_bridge`는 빈 칸을 묻거나 채운다. 끝나지 않은 작업은 `audit.decisions_log`에 양식·이유 기록 → 다음 세션이 이어받는다.

## 다음 (우선순위)

### P0 — 사용자 액션
- LLM 키 fix (OpenRouter 무료 추천 / Anthropic 충전 / OpenAI 충전 중 택1)

### P1 — Medical-Agent 특화 Harness 적용
1. **Go wide (PICO parallel exploration)**: 사용자 주제 → AgentPool로 3-5개 PICO 변형 동시 생성. 카드 양식으로 chat에 양식.
2. **Go deep (refinement loop)**: 선택된 PICO → epidemiologist/biostatistician/clinician 내부화 토론 (Latent Agents 패턴) → 단일 LLM 호출에서 3관점 비교
3. **physician_review verifier 강화**: paper_writer가 생성한 draft를 STROBE 체크리스트 항목별로 검증, 실패 시 paper_writer에 stderr 양식 재시도 (Plan-Watch-Recover 패턴)
4. **citation_grounding**: medical_graph + RAG에서 인용 가능한 PMID만 허용, fabrication 시 reject

### P2 — 양식 확장
5. **PublicationFigureGenerator 채팅 hookup**: "Forest plot KM curve Sankey 그려" 자연어 → 7종 PNG+SVG preview에 표시
6. **structured extraction batch**: 12,500편 PMC OA papers에 PICO/GRADE/limitation/conflict 6필드 추출 → paper_writer few-shot
7. **HF Space build** (외부 URL 접속) + Datasets oa_papers 업로드 완료 확인

### P3 — 자가 발전 회로
8. **MOSS-style source-level evolution**: capability_bench가 systematic failure 패턴 감지 시 (예: effect size 해석 반복 실수) → `paper_writer.py` 일부를 자동 rewrite + ephemeral trial worker 재생 검증 + 양식 양식 양식 rollback
9. **Hooks "stop signal" 자동 학습**: 사용자 "하지마"/"왜 자꾸"/"그거 말고" 입력 시 events.append + memory.router.write가 자동으로 `.harness/norms.md` 업데이트 제안

## 차단·기술 부채

- 🚫 LLM paid keys (위 P0)
- 🟡 `MedicalGraph.number_of_nodes()` attribute 없음 → `_graph.number_of_nodes()` 또는 facade 추가
- 🟡 `_llm_reply` 비활성 (스트리밍으로 대체) — 정리 필요
- 🟡 HF Datasets `oa_papers` 백그라운드 업로드 retry 상태 확인 필요 (704MB / 25,251 files)

## 세션 핸드오프

다음 세션 시작 시 양식 순서:
1. **PROGRESS.md** (이 파일) — 현재 stage + ResearchState + 차단
2. **AGENTS.md** — 생성/검증 분리 + 책임 맵
3. **CLAUDE.md** — 12개 작업 표준 규칙 (특히 RULE-7/8/9/11/12)
4. **ARCHITECTURE.md** — 모듈 정의 (새 모듈 만들기 전 의무)
5. **feature_list.json** — 기능 + done/in_progress/blocked
6. `data/agent_self/self_model.json` — 건강도
7. `git log --oneline -10`

세션 종료 = 이 PROGRESS.md 갱신 + `change_log.log()`.
