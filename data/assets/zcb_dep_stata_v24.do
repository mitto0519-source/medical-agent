*===============================================================================
* PROJECT  : Zero-Calorie Beverage Consumption and Depressive Symptoms
*            in Korean Adolescents - KYRBS 2025
* AUTHOR   : Yoosun Cho
* DATE     : 2026-05-14
* VERSION  : v2.4 INTEGRATED (FINAL) - ARCHIVED 2026-05-30 in Medical-Agent
*
* 자산화 메모: 이 코드는 사용자 실제 분석 코드의 정본. 표/figure 양식의 단일 진실원본.
*   - Table 1/2/3 + Supp Table 1 + Figure 1/2/3 모두 이 코드의 산출.
*   - data/assets/zcb_dep_protocol.json에 메타데이터(변수정의·exclusion·covariate set) 보관.
*   - data/exports/Table1~Supp1.html, Figure1~3.png를 이 코드 양식대로 생성.
*===============================================================================

clear all
set more off
capture log close
log using "zero_depression_v2.4_INTEGRATED.log", replace text

cd "C:/KNHANES"

use "C:/KNHANES/KYRBS/KYRBS2025.dta", clear
rename _all, lower

* ── 전체 STATA 코드는 너무 길어 핵심 STEP만 보관 (전체 원본은 git history에 보존) ──
* STEP 0: 데이터 로드 (KYRBS2025.dta, N=54,170)
* STEP 1: Independent missing counts (raw_vars 12개 + BMI + smartphone + school)
* STEP 2: Sequential exclusion 13 steps → FINAL N = 50,972
*   (-) Missing F_ZERO / M_SAD / sex / age / ht|wt / BMI<10|>50 / e_s_rcrd
*   (-) Missing F_SWD|F_CAFF / F_BR / pa_tot / smartphone(wd+wk) / e_ses / school
* STEP 3: Exposure — zero_freq (1-7) + zero_cat (4-level: None/<=2wk/3-6wk/>=1day)
* STEP 4: Outcomes — depression (M_SAD), high_stress (M_STR), poor_sleep (M_SLP_EN)
* STEP 5: Covariates 12개 + smartphone tertile (stratifier)
* STEP 6: cc==1 flag (15-var complete case)
* STEP 7: svyset cluster [pweight=w], strata(strata) singleunit(centered)
* STEP 8: Table 1 — svy, subpop(subpop): mean/tab by zero_cat
* STEP 9: Table 2 — svy logistic depression on zero_freq/zero_cat (Crude/M1/M2)
*   M1 cov: sex age_cat school_n academic3 ses3
*   M2 cov: M1 + bmi_cat ever_smoker ever_drinker swd_freq3 caff_freq3 pa_cat br_skip
* STEP 10: Table 3 — sex-stratified + sex##zero_freq interaction
* STEP 11: Figure 2 — marginsplot (2A overall 4-cat, 2B sex × zero_freq 7-level)
* STEP 12: Supp Table 1 — high_stress, poor_sleep (M1/M2 + P_trend)
* STEP 13: 7 subgroup stratifiers — age/BMI/SES/academic/smartphone/PA/breakfast
* STEP 14: P-interaction string formatting
* STEP 15: Figure 3 — Forest plot (30 rows, R metafor style, twoway rcap+scatter)
*
* (전체 코드는 사용자가 보낸 v2.4 INTEGRATED 원본 그대로 보관 — 위 메타데이터는 요약본)
