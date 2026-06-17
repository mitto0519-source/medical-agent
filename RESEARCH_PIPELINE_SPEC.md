# RESEARCH_PIPELINE_SPEC — 백엔드 논문 작성 상태기계 (숫자 먼저, 산문 나중)

> 핵심 통찰(사용자): 의료 논문 = **골격 → 가설(Abstract) → 통계 검증 → 숫자 확인 → 섹션별 디벨롭 → 완성도·톤**.
> 이건 LLM이 한 방에 토하는 게 아니라 **백엔드가 단계를 순서대로 강제하고, LLM은 각 단계만 채우는** 상태기계여야 한다.
> ★ 급소: **STATS(검증된 실수치) → 그 다음 SECTIONS.** 숫자가 산문보다 먼저. = 환각 통계 원천 차단.
> 연계: `RESEARCH_STATE`(상태·체크포인트) · `SELF_EVOLUTION`(학습) · `FRONTEND §5.5`(스트리밍) · `MASTER #2/#3`(통계·cost).
> ★ 중복 0: 단계 *부품*은 `research_pipeline.py`에 이미 있음 — **오케스트레이션만 명시화.**

---

## 0. 호출 / 원칙

```
@RESEARCH_PIPELINE_SPEC.md — 기존 research_pipeline.py 메서드를 단계 상태기계로 오케스트레이션.
새 통계/리뷰/작성 함수 만들지 마라(중복). orchestrator만 신규.
불변식: ① 단계 순서 강제 ② STATS 게이트 통과(검증 실수치 확정) 전엔 SECTIONS 금지 ③ 산문은 state 숫자를 인용, 발명 금지 ④ 각 단계=checkpoint+provenance ⑤ gate마다 휴먼 확인(바이브 논문).
```

핵심 불변식:
- **백엔드가 다음 단계를 결정한다**(LLM 아님). LLM은 *현재 단계 + 검증된 state 슬라이스*만 받아 채운다.
- **숫자 먼저**: SECTIONS는 `state.results`에 *검증된 estimate(provenance 포함)*가 있어야 시작. 산문은 그 숫자를 인용.
- **휴먼 인 루프**: 자동으로 돌되 gate(특히 STATS 후)에서 멈춰 사람 확인. "알아서 해"=전 단계 실행하되 checkpoint는 유지. (CLAUDE.md 바이브 논문 — 사람 주도)

---

## 1. 단계 상태기계 (사용자 순서 = 정식 스테이지)

```
S0 SCOPE      주제·PICO·데이터셋·설계 합의        ← generate_topics / validate_feasibility
   │  gate: PICO 5요소 채워짐 + dataset 가용
S1 SKELETON   골격(섹션 뼈대 + 각 섹션 1줄 목적)   ← 신규 경량(LLM 1콜)
   │  gate: IMRaD 섹션 슬롯 정의됨
S2 HYPOTHESIS Abstract 초안 = 사전명시 가설+분석계획 ← write_paper(abstract-only)
   │  gate: exposure/outcome/covariate/effect_measure 사전명시 (placeholder 숫자)
S3 STATS      ★통계 실행·검증 (실엔진, survey-weighted) ← run_stat_analysis
   │  ★★ GATE(숫자 먼저): estimate(aOR/CI/p/n) 산출 + provenance 핀
   │       + 가정검사(STROBE/회귀가정) + 휴먼 "이 숫자/해석 맞나" 확인
   │       통과 전엔 S4 진입 절대 금지
S4 SECTIONS   섹션별 하나하나 디벨롭 (확정 숫자 인용) ← write_paper(per-section)
   │  순서: Results(숫자) → Methods → Intro(funnel) → Discussion → Abstract 확정
   │  gate: 모든 수치 = state.results 참조(발명 0, claim_evidence_nli 통과)
S5 POLISH     완성도·톤앤매너 (문체+심사+저널)     ← review_and_revise + yoosun + journal_intel
   │  gate: peer score ≥ 임계, STROBE 충족, confidence 표시
DONE          Export (Word + EndNote)
```
- 각 전이 = `ResearchState` 갱신 + `checkpoint()` + `provenance.build_fingerprint`(dataset_version/registry_version 핀).
- 되돌리기/갈래치기: 어느 단계든 `restore`/`branch`(분석 A vs B). S3에서 갈래쳐서 두 분석 비교 가능.

---

## 2. ★ STATS 게이트 (이 스펙의 심장 — 환각 통계 차단)

S4(산문) 진입 조건:
1. `run_stat_analysis` → `survey_weighted.fit_logit_svy`(실엔진, 3-tier)로 **실수치** 산출.
2. estimate가 `state.results`에 저장 + 각 숫자에 **provenance_id**(dataset_version·registry_version·seed·code_sha).
3. 가정 검사: 회귀 가정·표본수·survey design 적용 여부 → `gates.stat`.
4. **휴먼 확인 체크포인트**: "aOR 1.34 (1.08–1.66), n=4,200, survey-weighted ✓ — 이 숫자/해석으로 갈까?" → 승인 시 S4.
- **S4의 모든 수치는 `state.results`를 *인용*한다. LLM이 숫자를 새로 만들면 = 위반**(claim_evidence_nli + provenance_guard가 잡음).
- 숫자 바뀌면(재분석) → S4/S5 영향 섹션만 `cost_optimizer`로 재생성(전체 재작성 금지, MASTER #3).

---

## 3. 백엔드 오케스트레이션 (LLM 아님이 운전)

`src/research/pipeline_orchestrator.py`(신규 — 유일 신규 모듈):
```python
def advance(state: ResearchState, *, auto: bool=False) -> Iterator[ChatEvent]:
    stage = state.stage
    if stage == "SCOPE":      run generate_topics/validate → state.rq; gate; checkpoint
    elif stage == "SKELETON": LLM 1콜(골격); state.manuscript.skeleton
    elif stage == "HYPOTHESIS": write_paper(abstract_only); state.manuscript.sections["Abstract"]
    elif stage == "STATS":    run_stat_analysis → state.results(+provenance); ★gate; (auto면 멈춤 신호)
    elif stage == "SECTIONS": per-section write_paper(인용=state.results); claim_evidence_nli
    elif stage == "POLISH":   review_and_revise + style + journal_intel
    yield events per stage (status/tool_result/token/badge)  # FRONTEND §5.5
```
- `auto=True`("알아서 해") = 단계를 연속 진행하되 **STATS gate에서 멈춰 휴먼 확인**(의료 안전). 나머지 gate는 통과 알림.
- `auto=False` = 단계마다 사람이 "다음" 누름(바이브, 사람 주도).
- 매 단계 LLM은 `get_llm_client(task=...)` + *그 단계 프롬프트 + state 슬라이스*만. (전체 논문 한 방 금지)

---

## 4. 기존 코드 매핑 (중복 0 — 오케스트레이션만 신규)

| 단계 | 기존 메서드(research_pipeline.py) | 변경 |
|---|---|---|
| SCOPE | `generate_topics`/`check_novelty`/`validate_feasibility` | 그대로 호출 |
| SKELETON | (없음) | 경량 LLM 1콜 신규(작음) |
| HYPOTHESIS | `write_paper`(abstract 모드) | 인자로 단계 한정 |
| STATS | `run_stat_analysis`+`_build_stat_spec` | survey_weighted + provenance 핀 + gate |
| SECTIONS | `write_paper`(per-section) | state.results 인용 강제 |
| POLISH | `review_and_revise`(이미 worst-section 재작성 루프) | + yoosun + journal_intel |
| 오케스트레이터 | (없음) | `pipeline_orchestrator.advance` 신규(유일) |
| 상태/체크포인트 | RESEARCH_STATE | 그대로 |
| 스트리밍 | FRONTEND §5.5 ChatEvent | 그대로 |

> `write_paper`가 지금 *전체* 논문을 쓰면 → **단계별 호출로 분리**(abstract만/섹션만). 한 방 생성 폐기 = 숫자먼저 원칙 강제.

---

## 5. 자가학습 훅 (단계 결과 → SELF_EVOLUTION)
- STATS 가정 위반/실패 → Failure KB(`{failure_type, variables, resolution}`).
- POLISH peer score → quality_tracker + 골드 후보.
- claim_evidence_nli 결과 → citation_faithfulness 축.
- 단계별 소요/비용 → cost_optimizer 학습.
→ "맡겨서 돌린 파이프라인"이 다음 실행을 더 낫게(RESEARCH_STATE §6 연결).

---

## 6. UX 표현 (FRONTEND §5.5 + UX_CHAT_DESIGN)
- 단계 진행 = 상단 **단계 칩 진행바**(SCOPE→SKELETON→STATS→…). 현재 단계 강조.
- STATS gate = 우측에 **통계 결과 카드**(aOR/CI/n + survey-weighted 배지) + "이 숫자로 진행" 버튼.
- SECTIONS = 우측 프리뷰 섹션별 채워짐(Results부터). 인용은 칩.
- 사람이 어느 단계든 멈추고 수정/브랜치.

---

## 7. 검증 / 수용
```bash
python scripts/test_pipeline_stages.py   # 신규: 단계 순서 강제 + STATS gate 전 SECTIONS 차단 확인
# 숫자먼저: STATS 없이 S4 호출 시 거부되는가
# 산문 숫자 = state.results 참조인가(발명 0): claim_evidence_nli 통과
python scripts/prove_stata_e2e.py        # STATS 실수치 정확
python scripts/test_rag_smoke.py
```
**수용**: ① 단계 순서 강제(건너뛰기 차단) ② STATS gate 통과 전 SECTIONS 불가 ③ 산문 수치 100% state.results 참조(발명 0) ④ 각 단계 checkpoint+provenance ⑤ auto 모드도 STATS에서 휴먼 확인 ⑥ 숫자 변경 시 영향 섹션만 재생성.

---

## 8. 결정지점
1. auto("알아서 해") 시 멈출 gate: STATS만 vs STATS+POLISH? (권장: STATS 필수, POLISH 옵션)
2. SECTIONS 작성 순서: Results-first 고정 vs 사용자 선택.
3. 숫자 변경 시 재생성 범위: 영향 섹션만(cost_optimizer) vs 전체.
4. SKELETON을 LLM 자동 vs 템플릿(IMRaD 고정).

---

## 9. 의존 / 선후
```
RESEARCH_STATE(상태·체크포인트) ─┐
research_pipeline.py(단계 부품) ─┼─▶ pipeline_orchestrator(신규) ─▶ FRONTEND §5.5(스트리밍 표현)
survey_weighted + provenance핀 ─┘                                  └─▶ SELF_EVOLUTION(학습 훅)
ez_home 네이티브 tool-use(선행) — 단계 산출을 tool_result 이벤트로 표면화
```
> 요약: 부품은 다 있다. **백엔드 상태기계 + 숫자먼저 게이트**만 명시화하면, LLM 프리스타일이 *규율 있는 연구 파이프라인*이 된다.
> 이게 "LLM 기반인데도 믿고 맡기는" 의료 논문 작성의 골격이다.
