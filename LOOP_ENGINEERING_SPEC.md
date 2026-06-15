# LOOP_ENGINEERING_SPEC — Medical-Agent 적용 (중복 없이 표면화·연결만)

> 출처: Addy Osmani, *Loop Engineering*; Peter Steinberger; Boris Cherny.
> 짝 문서: `CLAUDE.md`(규칙) · `ARCHITECTURE.md`(자산) · `SELF_EVOLUTION_SPEC.md`(게이트·골드셋) · `RESEARCH_STATE_SPEC.md`(상태 단일 정본).
> 원칙: ① **루프 = 발견→분류→수정→검증** ② **만드는 AI ↔ 검사하는 AI 분리(self-bias 가드)** ③ **상태 파일이 기억** ④ **인지적 항복 방지**(사용자 검토 필수).
> 중복 0: 새 자동화·상태저장·서브에이전트 인프라 만들지 마라 — **Medical-Agent에 이미 6 부품 다 있다**.

---

## 0. 호출 / 원칙

```
@LOOP_ENGINEERING_SPEC.md — §1 자산 매핑을 먼저 읽고, 부족한 4 점만 보강한다.
새 heartbeat/event store/sub-agent runner 생성 금지(규칙 10 위반=중복).
순서: ①정체성(LoopDefinition) → ②triage 우선순위 → ③self-bias 가드 → ④사용자 검토 알림.
```

---

## 1. ★ 자산 매핑 — Medical-Agent에 이미 있다

| Loop 부품 | Addy 기준 | Medical-Agent 기존 자산 | 상태 |
|---|---|---|---|
| ① **Automation** (시작) | cron/hooks/`/loop` | `src/runtime/heartbeat.py` (7 jobs) + `scripts/auto_sync.py` + `mcp_server.py`(BG 학습 스레드) + `src/runtime/backlog.py`(6 handlers) | ✅ 강함 |
| ② **Worktree** (격리) | `git worktree`·서브에이전트 isolation | `data/research_states/{rs_id}.json` + `working_paper_store` + Supabase `ma_research_state` (RESEARCH_STATE_SPEC §3 checkpoint/branch) | ✅ 동등(파일 단위) |
| ③ **Skill** (인수인계) | `SKILL.md` | `prompts/*.md` (medical_core/safety_constraints/yoosun_style/style_polish/chat_style — frontmatter 표준) + `CLAUDE.md` 12 규칙 + `ARCHITECTURE_SHORT.md` 23 sections | ✅ 표준 |
| ④ **Plugin/Connector** | MCP 서버·플러그인 | `mcp_server.py` (48+ tools) + `app/agentic_loop.py` `TOOL_SCHEMAS` (18 tools) + `src/llm/factory.py` 3중 폴백 | ✅ 동등 |
| ⑤ **Sub-agent** (검사 AI 분리) | `.claude/agents/` | `src/research/peer_reviewer.py` (writer↔critic 분리, `revise_with_critique`) + `src/agent/agent_pool.py` + `src/evolution/gate.py` (baseline vs candidate) | ⚠ self-bias 가드 미흡 |
| **상태 파일** (기억) | `progress.md` / Linear | `data/change_log/history.json` + `data/runtime/events.db` (append-only) + `CURRENT_STATE.json` + `ResearchProject`(RESEARCH_STATE_SPEC §1) | ⚠ 통합 view 없음 |

**중복 0 결론**: 6/6 부품 모두 동등 이상. 새 인프라 0개. **표면화·연결·가드만** 추가.

---

## 2. 4가지 강화 (부족한 부분만 — 새 모듈 최소)

### 2.1 LoopDefinition — 흩어진 루프를 한 카탈로그로 표면화
**문제**: heartbeat의 7 jobs · backlog의 6 handlers · peer_reviewer의 critique loop · evolution.gate가 각자 따로 살아있어 "이게 루프다"라는 정체성이 없음.
**처리**: 신규 `src/loops/__init__.py` + `src/loops/registry.py` — 기존 모듈을 LoopDefinition으로 wrap만:
```python
@dataclass
class LoopDefinition:
    name: str
    trigger: Callable                  # automation (heartbeat/backlog/manual)
    skill: str                         # prompts/*.md key (e.g. "medical_core")
    connectors: list[str]              # tool names from TOOL_SCHEMAS
    reviewers: list[str]               # sub-agents (writer, critic, ...)
    state_paths: list[str]             # change_log/events.db/ResearchProject id
    completion: Callable               # success condition (goal-style)
```
기존 7 jobs · 6 handlers · critique · gate 모두 LoopDefinition 객체로 표면화. **로직 변경 0 — wrapping만**.

### 2.2 Self-bias Guard — writer↔critic 모델 다양성 강제
**문제**: 현재 `peer_reviewer.revise_with_critique`가 writer와 critic이 같은 모델·같은 family면 자기점수 후하게 매김(블로그 글의 9.04 vs 7.43 사례와 동일 위험).
**처리**: 신규 `src/safety/self_bias_guard.py` — 가드 함수:
```python
warn_if_self_review(writer_model, critic_model) -> dict
  - 같은 family(둘 다 Claude / 둘 다 GPT 등) → warning + 교차 family 추천
  - 같은 정확한 model → 강한 warning + 강제 차단(opt-out 가능)
  - cross-family OK → 정상
```
배선 위치: `peer_reviewer.revise_with_critique` 진입부 + `evolution.gate.run_gate`.

### 2.3 Triage Inbox — backlog 우선순위·분류 view
**문제**: `src/runtime/backlog.py` 6 handlers는 enqueue·drain만 — **우선순위 정렬·분류된 view 없음**. 사용자가 "지금 봐야 할 것"을 모름.
**처리**: 신규 `src/loops/triage.py` — backlog + events.db + change_log를 합성:
```python
inbox(owner_email=None) -> {urgent[], today[], soon[], background[]}
  - urgent: physician_review 대기 / 실패 retry 필요
  - today: 사용자 응답 필요 / 골드셋 라벨 신규 후보
  - soon: 자가발전 promote/rollback 대기
  - background: 인제스트 진행 / cron 실행 중
```
ez_home 사이드바에 위젯 — Lovable의 "할 일" 카드처럼.

### 2.4 State View — "오늘 어디까지 왔나" 통합 표시
**문제**: change_log · events · ResearchProject · CURRENT_STATE 4곳에 흩어진 상태 → 사용자가 "내 작업 어디까지 진행됐나" 모름.
**처리**: 신규 `src/loops/state_view.py` — 한 줄짜리 함수:
```python
today_view(owner_email) -> {
    last_session, active_projects, pending_reviews,
    last_checkpoint, next_action(from_self_model),
    ingest_progress, gold_set_labelled_count
}
```
ez_home 상단 토픽바 또는 사이드바에 표시.

---

## 3. 인지적 항복 방지 (사용자 검토 강제)

**원칙(Addy)**: "The loop doesn't know the difference. You do." — 루프가 매끄러울수록 사람은 검토를 건너뛰고 싶어진다. 이를 차단:

| 시점 | 알림 |
|---|---|
| autopilot 5턴 연속 사용자 검토 없음 | ez_home에 노란 배지 "5턴 째 검토 없음 — 한 번 직접 본문 점검 권장" |
| confidence overall < 0.6 | 빨간 배지 + 자동 promote 차단 |
| sub-agent self-bias 감지 (같은 모델 review) | warning + 다른 family 추천 |
| 골드셋 라벨 0개 + 10턴 경과 | "라벨링 1순위" 알림 (SELF_EVOLUTION §2 외부 앵커) |

배선 위치: `ez_home._render_chat_page` 사이드바 또는 토픽바에 알림 row.

---

## 4. 슬래시 명령 (선택 — composer 부산물)

| 명령 | 동작 | 매핑 |
|---|---|---|
| `/loop <name>` | 루프 1회 수동 실행 | `src/loops/registry.run_loop(name)` |
| `/goal <목표>` | goal-loop 작성 (완료 조건 만족까지 반복) | `src/loops/goal.py` (신규, heartbeat 위) |
| `/triage` | inbox 4분류 chat에 표시 | `src/loops/triage.inbox()` |
| `/state` | today_view 표시 | `src/loops/state_view.today_view()` |
| `/checkpoint <label>` | ResearchProject 체크포인트 (RESEARCH_STATE §3) | `research_state.checkpoint(state, label)` |
| `/branch <cp_id> <title>` | 같은 지점에서 갈래치기 | `research_state.branch(cp_id, title)` |

배선: ez_home 컴포저에 `/` 입력 감지 → `src/loops/commands.dispatch_slash(cmd, args)`.

---

## 5. 모델 다양성 정책 (writer ≠ critic)

`src/config/models.py:_TASK_TIER` 강화:
```
paper_section (writer)    → standard (Sonnet)
critic_review (검사 AI)   → ★ premium (Opus) 또는 cross-provider (GPT-4o/Gemini)
                             ← writer와 동일 family면 self_bias_guard가 warning
verify_bg (백그라운드)    → fast (Haiku)
chat_orchestrate (대화)    → fast (Haiku)
```
실패 시 (예: Opus 크레딧 0) failover로 GPT-4o critic — **family 다양성이 self-bias 차단**.

---

## 6. 자가학습 훅 (SELF_EVOLUTION 연결)

루프 산출이 SELF_EVOLUTION의 학습 신호로 자동 흘러감 (RESEARCH_STATE §6 후속):
- 루프 실패(`completion` False) → `failure_kb.record_failure(failure_type, vars, resolution)`
- 루프 통과 + 검토 통과 → 골드셋 후보로 큐 (사용자 라벨 대기)
- self-bias warning → `evolution.ledger`에 candidate로 기록 (cross-family 강제 정책 후보)

신규 모듈 0 — 모두 기존 모듈 호출만.

---

## 7. ★ Anti-duplication 매트릭스 (착수 전 필독)

| 필요 | 기존 모듈 | 처리 | 새로 만들면 |
|---|---|---|---|
| 시작 트리거 | `runtime/heartbeat.py` + `backlog.py` | **그대로** + LoopDefinition wrap | ✗ 새 cron 금지 |
| 격리·체크포인트 | `runtime/events.py` + `research_state.checkpoint/branch` | **그대로 사용** | ✗ 새 git-worktree 금지 |
| Skill 형식 | `prompts/*.md` + `CLAUDE.md` | **그대로**(SKILL.md 동등) | ✗ 형식 통일 강요 X |
| Connector | `mcp_server` + `agentic_loop.TOOL_SCHEMAS` | **그대로** | ✗ 새 MCP 서버 금지 |
| Sub-agent 분리 | `peer_reviewer` + `agent_pool` + `evolution.gate` | self-bias 가드만 추가 | ✗ 새 reviewer runner 금지 |
| 상태 단일정본 | `ResearchProject`(RESEARCH_STATE) + events.db | **그대로** + state_view 합성 | ✗ 새 state store 금지 |
| 자가학습 | SELF_EVOLUTION 모듈 (ledger/anchor/gate) | **그대로** + 신호 emit | ✗ 새 학습루프 금지 |

**신규 파일**: `src/loops/__init__.py`, `src/loops/registry.py`, `src/loops/triage.py`, `src/loops/state_view.py`, `src/loops/commands.py`, `src/safety/self_bias_guard.py`. 다른 6 부품은 모두 기존.

---

## 8. 배선 맵

| 요소 | 파일 | 변경 |
|---|---|---|
| LoopDefinition | `src/loops/registry.py`(신규) | 기존 7 jobs/6 handlers를 객체로 wrap |
| Triage | `src/loops/triage.py`(신규) | backlog+events+change_log 합성 view |
| State view | `src/loops/state_view.py`(신규) | ResearchProject+CURRENT_STATE+self_model 합성 |
| Slash 명령 | `src/loops/commands.py`(신규) + `app/pages/ez_home.py` 컴포저 | `/loop /goal /triage /state /checkpoint /branch` |
| Self-bias 가드 | `src/safety/self_bias_guard.py`(신규) | `peer_reviewer.revise_with_critique` 진입 + `evolution.gate.run_gate` |
| 모델 라우팅 | `src/config/models.py:_TASK_TIER` | `critic_review` 추가 (premium 또는 cross-provider) |
| 사용자 검토 알림 | `app/pages/ez_home.py` 사이드바 | 5턴/confidence/self-bias/골드셋 4 알림 |
| AGENTS.md | 신규 또는 `CLAUDE.md` 확장 | 루프 카탈로그 + 호출 방법 |

---

## 9. 검증 / 수용 기준

```bash
# LoopDefinition smoke — 모든 기존 자동화가 객체로 wrap
python -c "from src.loops.registry import list_loops; print(list_loops())"
# Triage smoke
python -c "from src.loops.triage import inbox; print(inbox('mitto@gmail.com'))"
# Self-bias 가드
python -c "from src.safety.self_bias_guard import warn_if_self_review; \
print(warn_if_self_review('claude-sonnet-4-6','claude-sonnet-4-6'))"
# State view
python -c "from src.loops.state_view import today_view; print(today_view('mitto@gmail.com'))"
```
**수용**:
- ① 6 부품 모두 카탈로그에 등재 ② self-bias 동일 모델 warning emit ③ triage 4분류 동작 ④ today_view에 ResearchProject + ingest 진행 포함 ⑤ ez_home 사이드바 인지적 항복 알림 노출 ⑥ `/loop /goal` 슬래시 실행 ⑦ 신규 자동화 인프라 0개 (anti-duplication 매트릭스 위반 없음)

---

## 10. 결정지점

1. self-bias 정책: warning만 vs 동일 model 강제 차단? (의료라 **차단** 권장)
2. critic_review tier: premium(Opus) vs cross-provider(GPT-4o/Gemini)? (cross-provider = 다양성, 비용 ↑)
3. triage 우선순위 알고리즘: 단순 시간순 vs confidence+sla 가중 (권장: 후자)
4. 사용자 검토 알림 threshold: 5턴 vs 3턴 (의료 보수 = 3)

---

## 11. 의존 / 선후

```
RESEARCH_STATE §1(단일 정본) ──▶ §2.4 state_view (의존)
SELF_EVOLUTION §2(골드셋) ──▶ §3 인지적 항복 골드셋 라벨 알림
MASTER §3 #5(Failure KB) ──▶ §6 자가학습 훅
이 외에는 전부 기존 모듈 그대로 — 신규 인프라 0.
```

> 요약: Medical-Agent는 **Loop Engineering 6 부품 모두 동등 이상** 보유.
> 새로 짓는 건 0. **표면화(LoopDefinition) + 가드(self-bias) + 통합 view(triage·state) + 사용자 검토 알림** 4가지만 추가하면, "프롬프트 짜는 사람"에서 "루프 짜는 사람"으로의 인지 전환이 코드에도 동일하게 반영된다.
