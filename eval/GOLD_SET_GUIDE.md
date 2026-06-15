# GOLD_SET_GUIDE — 골드셋을 어떻게 채우나 (mitto 작업)

> 골드셋 = 자가발전·레벨측정·재현성의 *외부 기준*. 시스템이 self-label하면 안 됨(held-out). **임상의(너)만 라벨.**
> 핵심 전략: **작성하지 말고 수확하라.** 네가 이미 신뢰하는 작업(발표논문·Stata 출력·참고문헌)에서 정답을 옮긴다.

---

## 0. 최소 시작 규모 (크게 안 해도 됨)

처음부터 완벽 금지. **축별 10~15개면 측정 시작 가능**:
```
survey_design   : 10  (가장 중요 — 통계 정확성)
claim_evidence  : 15  (인용 충실성)
retrieval       : 10  (RAG 관련성)
structure/style :  5  (가벼움, 반자동)
─────────────────────
합계 ≈ 40개  → 첫 quality_harness 숫자 나옴
```
나중에 **실제 분석할 때마다 1개씩 추가** → 골드셋이 사용과 함께 자란다.

---

## 1. survey_design (★1순위 — 네 예전 결과를 옮기기만)

**수확처**: 네가 이미 Stata/SPSS/R로 돌려서 *맞다고 아는* KYRBS/KNHANES 분석. 발표논문 Table이면 최고.
**방법**: 분석 스펙 + **이미 아는 정답(aOR, CI)**을 적는다. 시스템이 재실행 → 그 숫자가 나오면 통계엔진 정답.
```json
{
  "survey_design": [
    {
      "id": "sd_001",
      "dataset": "KNHANES", "year": 2021,
      "analysis": "logistic",
      "outcome": "depression_phq9_ge10",
      "exposure": "upf_quintile",
      "covariates": ["age","sex","income_q","bmi"],
      "must_use_survey_weight": true,
      "expected": {"aOR": 1.34, "ci": [1.08, 1.66], "p": 0.008},
      "tolerance": {"aOR": 0.03, "ci": 0.05},
      "source": "내 2024 논문 Table 2 / 또는 Stata do-file 출력"
    }
  ]
}
```
> `expected` 값은 **네 신뢰 출력에서 그대로** 옮긴다(예시 숫자는 자리표시 — 진짜 값으로 교체). `tolerance`는 반올림 차 허용폭.
> 10개 중 **2~3개는 survey weight 미적용 시 *틀린* 케이스**로(naive vs weighted 차이를 잡게).

---

## 2. claim_evidence (인용 충실성 — 참고문헌에서 수확)

**수확처**: 네 논문/리뷰의 **참고문헌 목록**. "이 주장 → 이 PMID가 지지한다"를 네가 이미 안다.
**방법**: claim + PMID + 라벨. **음성(틀린 짝)도 반드시 섞어라** — 안 그러면 충실성 검사가 잡을 게 없다.
```json
{
  "claim_evidence": [
    {"id":"ce_001","claim":"High UPF intake is associated with depressive symptoms",
     "pmid":"35000000","label":"supports","source":"내 intro 인용"},
    {"id":"ce_002","claim":"UPF intake lowers depression risk",
     "pmid":"35000000","label":"refutes","note":"방향 반대 — 일부러 틀린 짝(음성)"},
    {"id":"ce_003","claim":"MASLD prevalence in Korea exceeds 30%",
     "pmid":"36000000","label":"neutral","note":"관련은 있으나 직접 지지 아님"}
  ]
}
```
권장 비율: supports 60% / refutes 25% / neutral 15%. **refutes·neutral이 검사의 진짜 시험대.**

---

## 3. retrieval (RAG 관련성 — 네가 아는 핵심 논문)

**수확처**: 네가 실제 칠 질의 + "이건 *반드시* 나와야 한다"는 핵심 PMID들.
```json
{
  "retrieval": [
    {"id":"rt_001","query":"KNHANES ultra-processed food depression Korea",
     "relevant_pmids":["35000000","35111111","35222222"], "k":5}
  ]
}
```
완벽 불필요 — 핵심 3~5개만. nDCG/recall@k가 그걸로 측정된다.

---

## 4. structure / style (가벼움 — 반자동)

- **structure**: 룰 체크라 라벨 거의 없음. "이 입력엔 이 섹션들이 있어야" 정도.
```json
{"structure":[{"id":"st_001","input":"full IMRAD draft","must_have_sections":["Abstract","Introduction","Methods","Results","Discussion"]}]}
```
- **style**: StyleProfiler가 네 업로드 논문에서 지표를 *자동 추출*하므로, 네 논문 1~2편만 지정하면 target_metrics는 반자동.
```json
{"style":[{"id":"sty_001","owner":"mitto0519@gmail.com","reference_papers":["내논문1.pdf"]}]}
```

---

## 5. ★ held-out 규칙 (이거 어기면 측정이 거짓이 됨)

- **골드셋은 프롬프트/학습에 절대 주입 금지.** 평가 전용. 시스템이 골드 답을 외우면 점수가 가짜.
- **에이전트가 *후보 초안*을 만들어주는 건 OK, *라벨 확정*은 너.** 예: "내 참고문헌에서 claim-PMID 짝 20개 뽑아줘" → 에이전트가 초안 → **네가 supports/refutes 검수·수정 후 확정**. 노동은 줄되 정답은 네 손.
- 시스템이 스스로 라벨하고 그걸로 자기 채점 = **금지**(self-bias 회귀).

---

## 6. 채우는 절차 (반나절 코스)

```
1. eval/gold_set.json 열기 (v0.2.0 슬롯 있음)
2. survey_design 10: 네 예전 Stata/논문 Table에서 aOR·CI 옮기기 (2~3개는 weight-틀린 케이스)
3. claim_evidence 15: 네 참고문헌에서 claim-PMID, refutes/neutral 섞기
4. retrieval 10: 자주 칠 질의 + 핵심 PMID
5. structure 5 + style: 네 논문 1~2편 지정
6. 저장 → 측정:
   python -c "from src.diagnostics.quality_harness import run; print(run())"
   → 6축 점수 첫 숫자. reconcile_state에 박혀 매 세션 추세.
```

---

## 7. 성장 (한 번에 다 안 해도 됨)

매 실제 연구를 **끝낼 때마다** 그 분석을 골드 1건으로 추가(체크포인트 시 자동 후보 → 네가 확정). → 쓸수록 골드셋이 커지고 측정이 촘촘해진다. 이게 RESEARCH_STATE 자가학습 훅과 연결되는 지점.

> 요약: **수확(작성 X) · 작게 시작(40개) · 음성 케이스 필수 · 라벨은 네 손 · 쓰면서 성장.**
> 이 40개가 들어오는 순간 "느낌상 올라옴"이 "6축 숫자"가 되고, 자가발전 루프가 비로소 *돈다*.
