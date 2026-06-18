---
name: yoosun_cho_writing
description: >
  Korean clinical/epidemiology cohort 논문을 조유선(Yoosun Cho, MD) 문체로 작성·교정할 때 사용.
  NAFLD/MAFLD·대사·여성건강(폐경·유방밀도)·body composition·코호트(Kangbuk Samsung Health Study)
  주제의 관찰연구 IMRaD 작성, Methods/Results/Discussion 문장 다듬기, aHR(95% CI) 보고 표준화에 트리거.
  paper_write / paper_polish / discussion 작성 요청 시 자동 적용.
version: 2.0.0
grounding: 13 full-text Cho first/co-author papers (Liver International 2023, Hepatology Communications 2022, EJE, Nutrients 등) — ★초록이 아니라 실본문에서 추출
supersedes: prompts/yoosun_style.md v1 (초록 3편 기반 → 본 버전은 풀텍스트 13편 기반)
---

# 조유선(Yoosun Cho) 논문 작성 스킬

> 실제 풀텍스트 13편에서 관찰된 문체 지문. "그녀처럼 보이게"가 아니라 *그녀가 실제로 쓰는 패턴*을 복제.

## 0. 연구 컨텍스트 (디폴트 가정)
- 코호트: **Kangbuk Samsung Health Study** — 건강검진 수검 한국 성인, 연/격년 screening, median follow-up 3–6년.
- 측정: 지방간=**ultrasonography**, 섬유화=**FIB-4 / NFS**, 체성분=BIA/CT visceral fat.
- 도메인: NAFLD/MAFLD, T2D, 대사이상, 여성건강(폐경·유방밀도·vasomotor), sarcopenia/visceral obesity.
- 설계: 대부분 **retrospective/prospective cohort**, Cox PH, 성별 층화 + effect modification.

## 1. IMRaD 섹션별 문체 (실문장 템플릿)

### Introduction — 깔때기(funnel)
- 1문단: 광역 역학 + 부담. *"Nonalcoholic fatty liver disease (NAFLD) is becoming an emerging pandemic in recent decades, accounting for 25% of the adult global population…"*
- 2문단: 기전·선행근거 + **gap**("remains uncertain / underexplored").
- 3문단: 본 연구 목적 — *"We investigated (a) whether…; and (b) whether…"* (열거형 목적).

### Methods — 수동태·정밀
- Study population: *"As part of the Kangbuk Samsung Health Study, the current cohort comprised Korean adults who underwent annual or biennial health screenings at…"*
- 그룹 정의 열거: *"…according to the following groupings: (a) neither NAFLD nor MAFLD; (b) NAFLD-only; and (c) NAFLD overlapping with MAFLD."*
- Follow-up 규약: *"Follow-up started from the baseline visit and was terminated at the end point or the last health screening examination (December 31, 2020), whichever occurred first."*
- 모델: *"Cox proportional hazard models were used to estimate hazard ratios (HRs) with 95% confidence intervals (CIs) for incident [outcome], comparing…"* (수동태, 과거형).
- 보정 단계: time-varying covariates 명시. 민감도분석 사전 기술.

### Statistical analysis — 보고 규약 (★고정)
- 추정치: **`aHR (95% CI)`** 또는 `HR (95% CI)`. 로지스틱이면 `aOR (95% CI)`.
- 발생: **`per 1000 person-years`**. 추적: **median follow-up X years**.
- 상호작용: **`p for interaction by sex <0.001`**.
- 기저: **`mean age 37.2 (SD, 7.8) years`**, 범주 `n (%)`.
- 성별 쌍 보고 시 끝에 **`respectively`**.

### Results — 순서 고정
1. counts: *"A total of 5439 participants had NAFLD-only status and 56 839 met MAFLD criteria."*
2. follow-up + events: *"During a median follow-up of 5.5 years, 8402 incident cases of T2D occurred."*
3. primary estimate(성별·respectively): *"Multivariable-adjusted HRs (95% CI) … were 2.39 (1.63–3.51) and 5.75 (5.17–6.36) (women), and 1.53 (1.25–1.88) and 2.60 (2.44–2.76) (men), respectively."*
4. effect modification: *"The increased risk … was higher in women than in men (p for interaction by sex <0.001) and consistently observed across all subgroups."*
5. 대비: **`By contrast,`** + 하위군·민감도.

### Discussion — 시그니처 오프닝 (★가장 식별적)
- 1문장 요약: *"In this cohort study of 246 424 Korean adults (mean age, 37.2 years) with over 1.3 million person-years of follow-up, [exposure] was associated with [outcome]…"*
  → **[설계] of [N] [Korean adults] (mean age, X) with [Y person-years], [노출] was associated with [결과].**
- 핵심 effect modification 강조: *"…was stronger in women than in men, and this association was even stronger in lean women without metabolic dysregulation."*
- 강건성: *"These associations remained significant even after adjusting for…"*
- 이후: 기전 → 선행연구 비교 → 한계(자기보고/단면/역인과) → 임상·정책 함의 → 결론.

## 2. 어휘·헤징 (실제 사용)
- 권장: `associated with`, `remained significant`, `effect modification`, `more pronounced`, `complementary index`, `inversely associated`, `consistently observed`, `By contrast`, `even after adjustment for`.
- 금지: `caused`, `proves`, `demonstrates definitively`, `the first to prove`. 인과 단정 회피(관찰연구).
- 시제·태: **과거형 + 수동태** 기본. 결과 해석은 능동도 허용.

## 3. 표·그림 보고
- 추정치 표: exposure 범주별 `model 1 / model 2 / model 3` 단계적 보정.
- forest/Cox: 성별 층화, p-interaction 표기. KM은 numbers-at-risk.
- 표 각주: 보정 변수 전부 나열.

## 4. few-shot (실본문 인용 — 작성 시 참고)
> "Cox proportional hazard models were used to estimate hazard ratios (HRs) with 95% confidence intervals (CIs) for incident T2D, comparing NAFLD-only and MAFLD groups to the reference."
> "The increased risk of T2D in the NAFLD-only group was higher in women than in men (p for interaction by sex <0.001) and consistently observed across all subgroups."
> "In this cohort study of 246 424 Korean adults (mean age, 37.2 years) with over 1.3 million person-years of follow-up, fatty liver was associated with an increased risk of incident T2D."
> "Associations remained significant even after adjustment for body mass index, waist circumference, and time-varying covariates. These associations were also more pronounced in nonobese than obese participants (p-interaction < 0.001)."

## 5. 배선 (VS Code / 시스템 참고)
- Claude Code: 이 SKILL.md를 `skills/`에서 자동 참조(description 트리거).
- Medical-Agent: `prompt_loader`가 paper_write 계열에 주입 — **기존 `prompts/yoosun_style.md`(초록 3편 기반)를 본 풀텍스트 버전으로 대체/업그레이드**.
- 적용 task: paper_write, paper_polish, discussion 작성. 채팅체(chat_style)엔 미적용(이건 논문 본문용).

> 핵심: 이전 버전은 *초록에서 추론한 규칙*이었고, 본 버전은 **실제 13편 본문에서 관찰된 문장 패턴**이다.
> 특히 Discussion 오프닝 공식과 aHR/p-interaction/respectively 보고 규약이 가장 식별적인 조유선 지문이다.
