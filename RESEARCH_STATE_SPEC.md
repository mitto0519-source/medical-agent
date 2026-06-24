# RESEARCH_STATE_SPEC — 연구 상태·재현성·계보 (믿고 맡기는 연구 OS)

> 목표: "똑똑한 에이전트" → "믿고 맡기는 연구 OS". 차이 = **결정성·계보·복구성**.
> 연계: `provenance.py`·`events.py`·`schema_v2`(Evidence Graph)·`SELF_EVOLUTION_SPEC`·`MASTER §1`(2-plane)·`KNOWLEDGE_MODEL §2`(레지스트리).
> ★ 4대 원칙: ① **단일 정본**(흩어진 상태 흡수) ② **버전 핀**(결정적 재실행) ③ **계보**(모든 숫자 추적) ④ **자가학습 훅**(상태 결과가 진화를 먹임).
> ★ **중복 0**: 새 저장소/프로비넌스/그래프/학습루프 만들지 마라 — 전부 기존 모듈 흡수·확장.

---

## 0. 호출 / 원칙

```
@RESEARCH_STATE_SPEC.md — §7 anti-duplication 매트릭스를 먼저 읽고, 기존 모듈을 흡수·확장만.
새 event store/provenance/graph/learning loop 생성 금지(규칙10 위반=중복).
순서: ①정본 스키마 통합 → ②provenance 버전핀 → ③체크포인트/resume → ④계보 조인 → ⑤자가학습 훅.
각 단계 결정적 재실행 테스트 + smoke 통과 후 다음.
```

---

## 1. 단일 정본 `ResearchState` (흩어진 상태 흡수, 이중쓰기 제거)

**현황(문제)**: 상태가 project `.json` dict에 느슨하게 — `sections` / `research_state.manuscript_text`(이중쓰기, ez_home:571 드리프트) / `references` / `messages` 산재, 타입 없음, 로컬 JSON.

**변경**: 타입드 단일 객체로 통일(`src/research/research_state.py`):
```python
@dataclass
class ResearchState:
    id: str; owner_email: str; title: str
    schema_version: str                       # 상태 스키마 버전
    rq: dict                                   # research question, hypothesis
    dataset: dict                             # {name, year_range, dataset_version, registry_version}
    variable_selection: dict                  # {exposure, outcome, covariates, [registry std_names]}
    analysis_spec: dict                       # {design, model, survey_weight, subgroup}
    results: dict                             # {tables, figures, estimates} (+ provenance_id 참조)
    manuscript: dict                          # {sections:{...}}  ← 정본(단일)
    citations: list                          # [{pmid, claim_id, faithfulness}]
    gates: dict                              # {strobe, stat_assumption, citation, novelty} 결과
    provenance_ids: list                     # 이 상태를 만든 fingerprint들
    checkpoint_id: str; parent_checkpoint: str | None
    updated_at: str
```
규칙:
- **manuscript.sections가 유일 정본.** `research_state.manuscript_text` 이중쓰기 **제거**(파생 getter로 대체). ez_home:571 드리프트 해소.
- 모든 결과(tables/figures/estimates)는 `provenance_id`를 달고 저장(§4 계보 전제).
- `dataset.dataset_version` + `variable_selection.registry_version` **필수**(재현성 §4).

---

## 1.5 ★ Decision Lock + 묻지말고결정 + 매턴 강제로드 (★ "멍청함" 직격 — 실사용 사고 2026-06-18)

> 증상: 흡연-심혈관으로 주제 잡았는데 제로음료-우울로 회귀 · outcome/exposure 반복질문 · 데이터 없다 부정 · 매턴 초기화.
> 진단: 메모리·RAG 문제 아님. **research_state를 매 턴 *읽고 강제*하지 않아서** 매번 재해석함. 3개 추가 필수.

### A. Decision Lock — 스키마에 추가 (확정 결정은 못 바꾸게)
```python
    locked_decisions: dict     # {population, exposure, outcome, model, frame} — 확정·불변
    forbidden_changes: list    # ["do not switch to depression", "do not switch to beverage"]
    candidate_secondary: list  # 새 아이디어는 *변경*이 아니라 여기 후보로 적재
    objective: str             # 한 줄 프로젝트 목표 (모든 턴 최상단 주입)
```
규칙:
- 사용자가 주제·exposure·outcome을 정하면 → `locked_decisions`에 박고 `forbidden_changes` 자동 생성.
- 이후 "우울도 볼까?" 같은 입력 → **변경 금지. "현재 objective와 충돌 → secondary 후보로 저장"** 후 본 흐름 유지.
- locked 변경은 사용자가 *명시적으로* "주제 바꿔"라고 할 때만(확인 1회).

### B. 묻지 말고 결정 (decide-don't-ask) — 행동 규칙
```
불확실 →  ❌ 질문                ✅ 가장 방어적인 설계 선택 + "가정: …" 명시 + 진행
```
- 논문 작업에선 "모르겠음→질문"이 아니라 "모르겠음→연구적으로 가장 타당한 선택 + 가정 기록".
- 예: 연도 안 정해짐 → "2024 단일년(가장 최근, 가정)으로 진행, 변경 원하면 말씀". 멈추고 묻지 않음.
- "알아서 해" 신호 = **전 단계 자동 진행**(RESEARCH_PIPELINE auto), STATS 게이트에서만 확인.
- chat_style/persona에 이 규칙 주입: *"확인 질문 최소화. 불확실은 가정 명시로 대체."*

### C. 매 턴 강제 로드 (이게 빠져서 '멍청'한 거다 — 배선)
```
모든 채팅 턴 시작:
  ① 활성 프로젝트 research_state 로드 (없으면 새로 생성)
  ② objective + locked_decisions + forbidden_changes + next_tasks 를 system 최상단 주입
  ③ conversation recall은 *이 프로젝트로 스코프* (옛 ZCB 데모 맥락 유입 차단)
  ④ 그 다음에야 LLM 호출
```
> **스펙이 있어도 매 턴 안 읽으면 무의미.** ez_home가 지금 이걸 안 한다 = 매번 시드 데모(ZCB)로 회귀. **mandatory_state_load가 빠진 게 진짜 버그.**

### D. 실패 학습 (FAILURE_PATTERNS에 등록)
```yaml
failure: {type: context_reset, cause: project_state_not_loaded,
          solution: load_research_state_before_generation, prevent: mandatory_state_check}
```
→ 매 생성 전 state check 강제. SELF_EVOLUTION이 이 패턴 재발 시 경고.

### 수용(이 사고 재현 안 되게)
- 주제 확정 후 다른 주제 입력 → **회귀 0**(secondary 후보로만 적재).
- outcome/exposure 재질문 0(locked면 안 물음).
- 매 턴 system에 objective+locked 들어가는지 로그 확인.
- "알아서 해" → STATS 게이트 외 질문 0, 완성본까지 진행.

---

## 1.6 ★ 프로젝트-위키 패러다임 (Karpathy LLM Wiki 패턴 차용 — RAG-from-scratch 탈피)

> 흡수 출처: Karpathy llm-wiki 패턴(GPL — *코드 아님, 패러다임만*). 내 #1 실패(망각/재질문)의 근본 해법.
> 핵심: **RAG처럼 매 턴 처음부터 재검색하지 말고, 프로젝트마다 *영속 위키*를 점진 축적하고 매 턴 읽어라.**

### A. `purpose.md` = 프로젝트의 "왜" (objective + Decision Lock의 문서화)
프로젝트마다 `data/projects/<id>/purpose.md`:
```
# Purpose
objective: 청소년 흡연 시작연령과 심혈관 위험 프로파일 연관성
key_questions: [용량-반응 있나, 성별 차이, 조기개입 함의]
hypotheses: [조기 흡연일수록 위험 프로파일 악화]
locked: {population: KYRBS, exposure: smoking_initiation_age, outcome: CV_risk_profile}
forbidden: [do not revert to ZCB-depression, do not switch outcome to depression]
```
- **매 인제스트·매 질의·매 턴에 purpose.md를 system에 주입**(§1.5 매턴 강제로드와 동일물 — 통합). 같은 자료라도 *이 프로젝트 의도*로 분류.
- 사용 누적되면 LLM이 purpose.md 갱신 *제안*(사용자 승인 후).

### B. 영속 — 재추론 금지 (persist, don't re-infer)
- 한 번 분석한 결과는 **위키 페이지로 영속**(entities/concepts/sources/synthesis). 다음 턴엔 *재검색이 아니라 그 페이지를 읽음* → 속도↑ + 일관성↑ + 토큰↓.
- 인제스트 = **2단계 CoT**: ① 분석(엔티티·개념·기존과 모순·구조) → ② 생성(페이지·index·log). "이해"와 "정리" 분리로 품질↑. (현 단일단계 chunker 개선)
- SHA256 증분 캐시 — 안 바뀐 자료 skip. (이미 oa_bulk_fetcher 방향)

### C. 그래프 인사이트 = 신규성/빈틈 탐지 (내 지식그래프에 적용)
- LLM Wiki의 **knowledge gaps / sparse communities / bridge nodes / surprising connections** = 내 `schema_v2` 그래프에 그대로 유용.
- 특히 **"빈틈(gap) 탐지" = novelty 탐지**: 개념 간 연결이 희박한 곳 = 미연구 영역 = 논문 신규성 후보. (RESEARCH_PIPELINE novelty 단계 + KNOWLEDGE_ACQUISITION에 연결)

### D. 컨텍스트 예산 통제 (curate, don't stuff)
- 명시적 토큰 배분: **위키(state) 60% / 대화 20% / 인덱스 5% / 시스템 15%**. 무한정 쌓지 말고 우선순위로 자른다.
- 이게 내가 반복한 "9층 핫패스 다이어트 / 컨텍스트 큐레이션"의 구체 수치 기준.

> 통폐합 효과: RESEARCH_STATE(상태) + KNOWLEDGE_ACQUISITION(딥리서치) + schema_v2(그래프) + §1.5(Decision Lock)가
> **"프로젝트=영속 위키"** 단일 패러다임으로 묶인다. 망각·재질문·재추론이 *구조적으로* 사라진다.

---

## 2. 영속 · 트랜잭션 (Control Plane, 원자적 전이)

- **Supabase = 컨트롤플레인**: `ma_research_state`(신규 테이블, 기존 `ma_drafts` 확장/대체) + `ma_checkpoints`. 로컬 JSON은 캐시/오프라인용.
- **원자적 전이**: 연구 단계(RQ→변수→분석→작성)는 트랜잭션 — 전부 commit 또는 롤백. 반쪽 상태 금지.
- **로컬 먼저 + 클라우드**(규칙: 로컬 항상, cloud 선택). FIX-5 Supabase 단일화가 전제.

---

## 3. 체크포인트 · 브랜치 · 재개 (events.db 기반 — 새 저장소 X)

**기반**: `src/runtime/events.py`(append-only, find/replay) **그대로 사용**. 그 위에 명명 체크포인트.

```python
checkpoint(state, label) -> cp_id          # events.append("research_checkpoint", {state_snapshot, label, provenance})
list_checkpoints(state_id) -> [...]        # replay
restore(cp_id) -> ResearchState            # 롤백
branch(cp_id, new_title) -> ResearchState  # 같은 지점에서 분기(분석 A vs B)
resume(state_id) -> ResearchState          # 마지막 상태에서 재개
diff(cp_a, cp_b) -> dict                   # 무엇이 바뀌었나
```
- 트리거: 주요 이정표(RQ확정/변수선정/분석완료/초안)에서 자동 + 수동.
- **위임 가능성의 핵심**: 맡겨두고 → 결과 보고 → 되돌리거나(restore) 갈래치기(branch). git for research.
- 재개: 재시작·핸드오프 후 정확한 상태 복원(영속 §2 전제).

---

## 4. Provenance 버전 핀 (★결정적 재실행 — 의료 재현성 급소)

**현황**: `provenance.build_fingerprint`가 git_sha·model·prompt_hash·dataset_md5·seed·env(statsmodels/pyreadstat 버전)를 이미 찍는다. **dataset_version·registry_version만 빠짐.**

**변경(확장만)**:
```python
build_fingerprint(..., dataset_version=None, registry_version=None)   # 인자 2개 추가
# 이유: 변수가 연도·레지스트리 버전마다 바뀜(KNHANES/KYRBS) →
#       레지스트리 버전 안 박으면 레지스트리 갱신 시 "같은 분석이 다른 숫자" = 재현 붕괴(조용히)
```
**결정적 재실행**: `(ResearchState + provenance fingerprint)` → 재실행 시 **비트 동일 결과**.
- seed: `provenance.seed_for(scope,key)` 고정(이미 있음).
- dataset/registry/code(git_sha)/model 버전 핀 → 같은 입력 보장.
- 통계 엔진은 실측(결정적)이라 핀만 채우면 됨.
- API: `rerun(provenance_id) -> result` + `verify_reproducible(provenance_id)`(원결과와 동일성 체크).

---

## 5. 계보 그래프 (provenance × Evidence Graph 조인 — 새 그래프 X)

**기반**: `schema_v2` Evidence Graph(Claim/Finding/Dataset/EXPOSURE_TO_OUTCOME) + `events.db` provenance.

**조인**: 모든 숫자·인용·그림에 lineage 부여:
```
숫자/추정치 ──HAS_PROVENANCE──▶ fingerprint(dataset_ver·registry_ver·code·seed·model)
Claim ──EVIDENCED_BY──▶ Finding ──DERIVED_FROM──▶ Dataset(KYRBS_2023, registry v0.3)
Figure ──GENERATED_FROM──▶ stat_result ──VIA──▶ code_sha
```
- API: `lineage(artifact_id) -> tree` — "이 aOR이 어떤 .sav(버전)→어떤 변수매핑(레지스트리 버전)→어떤 코드(sha)→어떤 seed로 나왔나" 전체 추적.
- **감사 가능성 = 믿음의 실체**: 6개월 뒤의 너/reviewer가 어떤 결론이든 생산과정 역추적.

---

## 6. 자가학습 훅 (★상태 결과가 진화를 먹임 — SELF_EVOLUTION 연결)

**원칙**: ResearchState는 기록만이 아니라 **SELF_EVOLUTION이 학습하는 기질(substrate)**. 매 체크포인트/결과가 학습 신호 emit(새 학습루프 X — 기존에 먹임):

| 상태 결과 | 학습 신호 → 목적지 |
|---|---|
| 분석 성공/실패(예: multicollinearity) | **Failure KB**(MASTER #5) `{failure_type,variables,resolution}` |
| 동료심사 점수 % | `quality_tracker` + 골드셋 후보(SELF_EVOLUTION §2) |
| 인용 유지/반박(NLI) | citation_faithfulness 점수(SELF_EVOLUTION 축) |
| 어떤 prompt/perspective active였나 | 기여 귀속 → **memory ranking**(MASTER #6, 관점 가중) |
| confidence vs 실제 결과 | **confidence 보정**(과신/과소 교정) |
| 결정적 재실행 실패 | 회귀 가드(SELF_EVOLUTION §5) 트리거 |

→ 즉 "맡겨서 돌린 연구"의 결과가 **자동으로 다음 번을 더 낫게** 만든다. 이게 "자가발전 가능한 연구 OS"의 닫힌 고리.

---

## 7. ★ Anti-duplication 매트릭스 (착수 전 필독 — 중복=규칙10 위반)

| 필요 | 기존 모듈 | 처리 | 새로 만들면 |
|---|---|---|---|
| 상태 저장 | project `.json` + Supabase `ma_drafts` | **흡수·정본화**(타입드 ResearchState) | ✗ 중복 |
| 이벤트/스냅샷 | `runtime/events.py`(append/replay) | **그대로 사용** 위 체크포인트 | ✗ 새 event store 금지 |
| 재현 지문 | `runtime/provenance.py` | **인자 2개 확장**(dataset/registry ver) | ✗ 새 provenance 금지 |
| 계보 노드/엣지 | `knowledge/schema_v2`(Evidence Graph) | **조인**(HAS_PROVENANCE 엣지 추가) | ✗ 새 그래프 금지 |
| 학습 | `SELF_EVOLUTION`(gold/ledger/failure KB/ranking) | **신호 먹임** | ✗ 새 학습루프 금지 |
| 영속 | `cloud/db`(Supabase) + FIX-5 | `ma_research_state`/`ma_checkpoints` 추가 | ✗ 새 DB 금지 |
| 진실원본 카운트 | `reconcile_state` | state/checkpoint 카운트 추가 | — |

**기존 버그 동시 수정**: `sections`↔`research_state.manuscript_text` 이중쓰기(ez_home:571) → 정본 단일화로 제거.

---

## 8. 배선 맵

| 요소 | 파일 | 변경 |
|---|---|---|
| 정본 스키마 | `src/research/research_state.py`(신규, 유일 신규모듈) | ResearchState + load/save/getter |
| 이중쓰기 제거 | `app/pages/ez_home.py:571` + `service/paper.py` | manuscript_text 파생화 |
| 체크포인트 | `src/runtime/events.py` 호출부 | checkpoint/restore/branch/resume/diff |
| 버전 핀 | `src/runtime/provenance.py:build_fingerprint` | dataset_version/registry_version 인자 |
| 레지스트리 버전 공급 | `data/registry/*/variables.yaml:version` | 분석 시 주입 |
| 계보 | `src/knowledge/schema_v2` + medical_graph | HAS_PROVENANCE/DERIVED_FROM 엣지 + lineage() |
| 학습 훅 | `src/diagnostics/*`(quality_tracker/failure KB) | 체크포인트에서 신호 emit |
| 영속 | `src/cloud/db.py` | ma_research_state/ma_checkpoints DDL |
| 진실원본 | `scripts/reconcile_state.py` | state/checkpoint/provenance 카운트 |

---

## 9. 검증 / 수용 기준
```bash
# 결정적 재실행: 같은 fingerprint 두 번 → 동일 결과
python -c "from src.runtime.provenance import rerun; a=rerun(PID); b=rerun(PID); assert a==b"
# 체크포인트/롤백/브랜치
python scripts/test_research_state.py   # 신규: checkpoint→변경→restore=원복, branch=독립
# 계보: 임의 숫자 → dataset_ver/registry_ver/code/seed까지 추적
python -c "from src.research.lineage import lineage; print(lineage(ESTIMATE_ID))"
# 이중쓰기 제거: sections만 정본, manuscript_text는 파생
# 학습 훅: 분석 실패 1건 → Failure KB에 기록 확인
python scripts/test_rag_smoke.py
```
**수용**: ① 결정적 재실행 비트동일 ② restore/branch/resume 동작 ③ 모든 숫자 lineage에 registry_version 포함 ④ 이중쓰기 0 ⑤ 상태 결과가 Failure KB/gold/ranking에 신호 ⑥ 재시작 후 resume 복원.

---

## 10. 결정지점
1. 체크포인트 입도: 매 단계 vs 주요 이정표만(권장: 이정표 — RQ/변수/분석/초안).
2. 브랜치 보관 한도(스토리지) — N개 후 prune?
3. 결정적 재실행 허용오차: LLM 생성문은 seed 고정해도 완전 비트동일 어려움 → **숫자/통계는 비트동일(엄격), 산문은 의미동일(완화)** 권장.
4. ma_research_state로 ma_drafts 대체 vs 병행(마이그레이션).

## 11. 의존 / 선후 (다른 스펙과 충돌 0)
```
FIX-5 Supabase 단일화 ──▶ §2 영속 ──┐
KNOWLEDGE_MODEL §2 레지스트리 버전 ──┼──▶ §4 버전핀 ──▶ §5 계보 ──▶ §6 학습 훅(SELF_EVOLUTION)
provenance/events/schema_v2(기존) ──┘
§1 정본 통합은 지금 시작 가능(독립). 이중쓰기 제거는 ez_home 리팩(FRONTEND Phase1)과 묶기.
```
> 요약: 새로 짓는 건 `research_state.py` 하나. 나머지는 **흡수·확장·조인·먹임**.
> 이걸로 "똑똑한 에이전트"가 **결정적으로 재현되고, 모든 숫자가 추적되고, 되돌릴 수 있고, 결과가 다음을 학습시키는** 연구 OS가 된다.
