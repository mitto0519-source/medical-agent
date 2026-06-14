# SELF_EVOLUTION_SPEC — 제대로 된 자가발전 닫힌 루프

> 짝 문서: `MASTER_UPGRADE_ROADMAP`(신뢰성#5/#6) · `E2E_PILOT_TEST_PLAN`(여정 점수) · `KNOWLEDGE_MODEL_SPEC`.
> 문제: 현재는 "자가발전 부품은 다 있는데 **자기가 채점하고 절대 안 되돌리는**" 상태 = 진화가 아니라 누적/드리프트.
> 목표: **외부 골드셋 앵커 + 변경 게이트(유지/롤백)** 둘을 채워 닫힌 루프로. ★ 새 구축 최소 — 기존 모듈 배선.

---

## 0. 호출 / 원칙

```
@SELF_EVOLUTION_SPEC.md — §8 매핑대로 기존 모듈(capability_bench/quality_tracker/prompt_ab/
improvement_engine/persona/agent_insight)을 닫힌 루프로 배선. 새 점수기/메모리 만들지 마라(중복).
불변식: ① 점수의 기준은 외부 골드셋(자기판단 금지) ② 모든 진화는 후보버전→게이트 통과해야 승격, 아니면 롤백.
골드셋은 held-out — 시스템이 직접 학습/라벨 금지(사용자만 라벨). 게이밍 방지(§9).
```

핵심 불변식 2개(이게 "제대로"의 정의):
- **외부 앵커**: 측정 기준 = 사용자 라벨 골드셋. self_auditor 자기점수는 *보조*지 기준 아님.
- **게이트된 변경**: persona/prompt/retrieval 변경은 골드셋에서 baseline 이겨야 유지. 지면 자동 롤백.

---

## 1. 닫힌 루프 (현재 결함 → 목표)

```
현재(열린 루프):  측정(자기채점) → 변경(append-only) → ⨯ 재측정·롤백 없음 → 드리프트

목표(닫힌 루프):
   골드셋(외부 진실) ──measure──▶ score(축별)
        ▲                              │
        │                       detect 약점/회귀
   re-measure(GATE)                    │
        │                              ▼
   promote(↑) / rollback(↓) ◀─candidate── improvement_engine
   (persona/prompt/retrieval = 버전드 아티팩트, prompt_ab로 A/B)
                                   └ 고위험만 사람 승인(approval queue, 유지)
```

---

## 2. 컴포넌트 A — 골드셋(외부 앵커) ★1순위, 없으면 전체 무의미

**현존**: `eval/gold_set.json v0.2.0`(claim_evidence_pairs / survey_design_test_cases 슬롯, mitto 라벨 필요), `quality_harness`(현재 0.0).

**스키마 확정** `eval/gold_set.json`:
```json
{
  "version": "0.3.0",
  "retrieval": [{"query":"...", "relevant_pmids":["..."], "k":5}],
  "claim_evidence": [{"claim":"...", "pmid":"...", "label":"supports|refutes|neutral"}],
  "survey_design": [{"dataset":"KYRBS","year":2023,"analysis":"logistic",
                    "outcome":"depression","exposure":"zcb","expected":{"aOR":1.04,"ci":[1.02,1.06]},
                    "must_use_survey_weight":true}],
  "style": [{"owner":"mitto","text_sample":"...", "target_metrics":{...}}],
  "structure": [{"input":"...", "must_have_sections":["Intro","Methods",...]}]
}
```
**축별 점수**(quality_harness 채움):
| 축 | 측정 | 산식 |
|---|---|---|
| retrieval | nDCG@k / recall@k vs relevant_pmids | 0~1 |
| citation_faithfulness | NLI(claim_evidence_nli) 일치율 | %, 목표 ≥95 |
| stat_correctness | survey_weighted 산출 vs expected(허용오차) + must_use_weight 준수 | pass율 |
| style_match | StyleProfiler 지표 거리 | 0~1 |
| structure | 필수 섹션 충족 | % |
| functional | E2E 여정 J1~J11 green율 | n/11 |
→ `quality_harness.run() -> {축별, overall, version}`. **이 overall이 모든 게이트의 기준값.**

> ★ held-out: 골드셋은 학습/프롬프트에 *주입 금지*. 평가 전용. 시스템이 골드 답을 외우면 측정이 거짓이 됨(§9).

---

## 3. 컴포넌트 B — 버전드 변경 아티팩트 (append-only 폐기)

**현존 문제**: `persona.accumulated_perspectives` append-only·리셋없음 → 해로운 변경 영구 잔존.

**변경**: 진화 대상(persona 관점 / 버전드 프롬프트 / retrieval 설정[rerank 가중·top_k·임베딩])을 **후보 버전**으로 표기:
```
data/agent_self/persona.json         → 각 perspective에 {id, added_at, status: candidate|active|retired, contribution_score}
prompts/*.md                         → 이미 version 프론트매터 有 → candidate 버전 병행
data/runtime/evolution_ledger.db     → 후보→게이트결과→승격/롤백 이력 (events.db append)
```
원칙: **활성(active)은 게이트 통과분만.** candidate는 A/B에서만 노출.

---

## 4. 컴포넌트 C — 게이트 (promote/rollback) ★2순위

**현존**: `prompt_ab.py`(A/B), `capability_bench.py`(점수), `improvement_engine`(변경 생성+승인큐).

**배선**: 변경 1건 = 다음 파이프라인:
```
improvement_engine가 candidate 생성
   → prompt_ab: baseline(active) vs candidate를 골드셋 부분집합에 실행
   → quality_harness.overall(candidate) vs (baseline)
   → Δ ≥ +ε(유의)면 promote(active 교체) / Δ ≤ 0면 rollback(candidate retire)
   → evolution_ledger 기록 (provenance fingerprint 포함 — 재현)
   → 고위험(persona 핵심·safety)만 get_approval_queue로 사람 확인 후 promote
```
- ε·표본수는 노이즈 방지(소표본 우연 상승 거름). 동률은 보수적으로 baseline 유지(의료).
- **자동 승격은 저위험만**(retrieval 설정 등). persona/safety는 사람 게이트.

---

## 5. 컴포넌트 D — 회귀 가드

**현존**: `quality_tracker.get_trend()` → improving/degrading/stable(감지만, 행동 없음).

**배선**: 매 골드셋 실행 후:
- `overall`이 직전 active 대비 하락 → **릴리스 차단 + 알림(notifier) + 직전 버전으로 자동 롤백 옵션**.
- `degrading` 추세 N회 연속 → 자가발전 일시중지(safe mode) + 사람 호출.
- `reconcile_state.py`에 `quality.overall`·축별·추세 박음(진실원본에 노출, 매 세션 hook 주입).

---

## 6. 컴포넌트 E — 기억/관점을 측정 기여로 가중 (누적 → 선택)

**현존**: `scorer.py`(memory router 게이트), persona confidence%(측정 미연동).

**변경**: 관점·insight·기억의 `contribution_score`를 **실측에서 벌어오게**:
- 어떤 관점이 active일 때 골드셋 점수 기여(ablation: 빼고 측정한 Δ) → 음수 기여 관점은 retire.
- 사용빈도·여정 성공·인용통과·검증통과로 memory_quality_score(Reliability #5와 동일물 — 중복 금지, 통합).
- persona는 상위 기여 관점만 주입(토큰 예산 + 품질).

---

## 7. 컴포넌트 F — 사람 승인 게이트 (의료 안전, 유지)

**현존**: `improvement_engine.get_approval_queue/approve_item/reject_item`.
- 고위험 변경(safety 프롬프트·persona 핵심·통계 기본설정)은 자동 승격 금지 → 큐에서 사람 확인.
- 저위험(retrieval 가중·문체 미세)은 게이트(C) 통과 시 자동.
- 의료라 **기본은 보수적**: 불확실하면 사람.

---

## 8. 기존 모듈 → 변경 매핑 (배선, 신규 최소)

| 닫힌루프 요소 | 현존 모듈 | 변경 |
|---|---|---|
| 측정 기준 | `eval/gold_set.json`+`quality_harness` | 스키마 확정 + 축별 점수 구현(§2) |
| 점수기 | `capability_bench` | 골드셋 대조로 전환(자기채점→앵커채점) |
| A/B | `prompt_ab` | baseline vs candidate 게이트로 사용(§4) |
| 변경 생성 | `improvement_engine` | 출력을 candidate+ledger로, 자동승격 저위험 한정 |
| 추세/회귀 | `quality_tracker` | degrading→차단/롤백/safe-mode 연결(§5) |
| 진화 대상 | `persona`/prompts/retrieval cfg | 버전드+status+contribution(§3,§6) |
| 승인 | approval queue | 고위험 라우팅(§7) |
| 재현 | `runtime/provenance` | 모든 게이트 결정에 fingerprint |
| 진실원본 | `reconcile_state` | quality 점수·추세 카운트 추가 |

> 신규 파일은 `evolution_ledger`(events.db 위) + quality_harness 채점 로직 정도. 나머지는 전부 배선.

---

## 9. 게이밍/드리프트 방지 (★ "제대로"의 안전장치)

- **골드셋 held-out**: 평가셋을 프롬프트/학습에 절대 주입 안 함. 별도 보관, 평가 전용. (자기 답 외우기 차단)
- **사용자만 라벨**: 시스템이 골드 정답을 self-label 금지(자기채점 회귀). claim_evidence·survey expected는 임상의가 라벨.
- **앵커 다양성**: 단일 지표 최적화 금지 — retrieval·citation·stat·style 동시 게이트(한 축 게이밍이 다른 축 깨면 reject).
- **회귀 우선**: 어떤 축이라도 명백 하락이면 overall 올라도 보류(의료 안전).
- **provenance 필수**: 모든 승격/롤백에 git_sha·model·gold_version 기록 → 사후 원인추적.

---

## 10. 검증 + 합격 기준
```bash
# 골드셋 채점 동작
python -c "from src.diagnostics.quality_harness import run; print(run())"   # overall>0, 축별 표시
# 게이트: 일부러 나쁜 candidate → rollback 되나
python scripts/test_evolution_gate.py   # 신규: bad candidate가 promote 안 되고 ledger에 rollback 기록
# 회귀 가드: degrading 주입 → safe-mode/알림
# reconcile에 quality 노출
python scripts/reconcile_state.py && grep -A3 quality CURRENT_STATE.json
```
**합격(제대로 된 자가발전)**:
1. overall이 골드셋(외부)에서 산출됨(자기채점 아님).
2. 나쁜 변경이 **자동 롤백**되고 ledger에 남음(append-only 아님).
3. degrading 추세가 릴리스를 **차단**함.
4. 모든 게이트 결정에 provenance fingerprint.
5. 골드셋이 held-out(프롬프트에 안 들어감).

---

## 11. 결정지점 (사용자)
1. 골드셋 규모/라벨 우선순위: claim_evidence vs survey_design 중 먼저? (권장: survey_design — 정확성 직결)
2. 자동 승격 허용 범위: retrieval만 vs 문체까지? (의료라 보수 권장)
3. Δ 유의 임계 ε + 최소 표본수.
4. degrading 몇 회 연속에 safe-mode?

> 요약: 부품은 다 있다. **골드셋(외부 기준) + 게이트(유지/롤백)** 둘만 배선하면 "누적"이 "진화"가 된다.
> 그 전엔 아무리 학습해도 나아진다는 보장이 없다. 이게 자가발전의 진짜 전제다.
