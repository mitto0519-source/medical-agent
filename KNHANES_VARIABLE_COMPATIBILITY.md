# KNHANES Variable Compatibility Matrix (2007-2024)

> 짝 문서: `KYRBS_VARIABLE_COMPATIBILITY.md` (청소년건강행태조사).
> 진실원본: `data/registry/knhanes/variables.yaml` — 코드(`src/data/knhanes_raw_loader.py`)는 yaml만 읽음.

## 1. 데이터 파일 위치 (KDCA 신청·승인 후 사용자 수동 다운로드)

```
data/raw/knhanes/통합파일(SPSS기준만들기)/HN<YY>_all.sav     # 12 wave (HN13~HN24, ★primary)
data/raw/knhanes/통합본(STATA)/KNHANES_2013_2024.dta        # 639MB STATA 통합본 (인코딩 손상)
data/raw/knhanes/지침서/*.pdf                                # KDCA 공식 이용지침 25개 PDF
data/raw/knhanes/HN<YY>_24RC(SPSS).zip                      # 24h dietary recall (별도)
data/raw/knhanes/HN<YY>_OE(SPSS).zip                        # Oral exam (HN14/15/19, optional)
data/raw/knhanes/HN<YY>_EYE.zip                             # Eye exam (HN17~21, optional)
data/raw/knhanes/HN<YY>_PAM.zip                             # Physical activity monitor (HN14~17)
data/raw/knhanes/HN<YY>_FFQ.sav                             # Food Frequency Questionnaire (HN14/15)
```

로더 (`src.data.knhanes_raw_loader`)는 한글 폴더 + 대소문자 혼합 (HN13_all vs HN24_ALL) 모두 case-insensitive scan.

## 2. Survey Design Variables (★복합표본설계 필수)

| std_name | KNHANES 변수 | 의미 | 적용 기간 |
|---|---|---|---|
| `strata` | `kstrata` | 분산추정 층 | 2007-2024 |
| `cluster` | `psu` | 조사구번호 (PSU) | 2007-2024 |
| `wt_itvex` | `wt_itvex` | 건강설문·검진조사 가중치 | 2007-2024 |
| `wt_ntr` | `wt_ntr` | 영양조사 가중치 | 2014-2024 (이전: `wt_ntex`) |
| `wt_total` | `wt_tot` | 건강설문+검진+영양 통합 가중치 | 2014-2024 (신규) |
| `wt_pft` | `wt_pft` | 폐기능검사 가중치 | optional |
| `wt_pfnt` | `wt_pfnt` | 폐기능+영양 가중치 | optional |

★ 분석 시 항상 `svydesign(ids=~psu, strata=~kstrata, weights=~wt_itvex)` 패턴. naive logistic 절대 금지.
→ `src/analysis/survey_weighted.py` (statsmodels.SurveyDesign → rpy2 R survey → naive 경고 3-tier).

## 3. Demographics

| std_name | KNHANES 변수 | 코딩 | 비고 |
|---|---|---|---|
| `age` | `age` | year (만 나이) | 0~80+ (top-coded) |
| `sex` | `sex` | 1=남 / 2=여 | |
| `education` | `edu` | 1=초졸이하 / 2=중졸 / 3=고졸 / 4=대졸이상 | 19+ |
| `income_q` | `incm` | 1~4 quartile | 가구 단위 |
| `region` | `region` | 17개 시도 | optional |
| `marriage` | `marri_1` | 1=기혼·동거 / 2=별거/이혼/사별 / 3=미혼 | 19+ |

## 4. Health Examination (검진)

| std_name | KNHANES 변수 | 단위 | 기간/주의 |
|---|---|---|---|
| `bmi` | `HE_BMI` | kg/m² | 2007- |
| `wc` | `HE_wc` | cm | 2007-, Korean cutoff 남90/여85 |
| `sbp` | `HE_sbp` | mmHg | 2007- (3회 측정 평균) |
| `dbp` | `HE_dbp` | mmHg | 2007- |
| `glucose` | `HE_glu` | mg/dL | 2007- (8h 공복) |
| `hba1c` | `HE_HbA1c` | % | 2007- |
| `hdl` | `HE_HDLc` (2007-2018), `HE_HDL_st2` (2019-) | mg/dL | ★ 컬럼명 변경 |
| `ldl` | `HE_LDLc` (2007-2018), `HE_LDL_drct` (2019-) | mg/dL | ★ 직접측정으로 변경 |
| `tg` | `HE_TG` | mg/dL | 2007- |
| `tchol` | `HE_chol` | mg/dL | 2007- |
| `ggt` | `HE_GGT` | U/L | 2007- (FLI 계산 필수) |
| `ast` | `HE_AST` | U/L | 2007- |
| `alt` | `HE_ALT` | U/L | 2007- (HSI 계산 필수) |
| `cr` | `HE_crea` | mg/dL | 2007- |
| `hgb` | `HE_HB` | g/dL | 2007- |
| `uric_acid` | `HE_Uric` | mg/dL | optional |
| `vit_d` | `HE_VitD` | ng/mL | optional |

## 5. Disease History (의사진단)

| std_name | KNHANES 변수 | 코딩 |
|---|---|---|
| `dm_dx` | `DE1_dg` | 1=yes 0=no |
| `dm_tx` | `DE1_pr` | 1=치료중 |
| `ht_dx` | `DI1_dg` | 1=yes |
| `ht_tx` | `DI1_pr` | 1=항고혈압제 |
| `dyslip_dx` | `DI2_dg` | 1=yes |
| `dyslip_tx` | `DI2_pr` | 1=lipid-lowering |
| `mi_dx` | `DI3_dg` | 심근경색 |
| `angina_dx` | `DI4_dg` | 협심증 |
| `stroke_dx` | `DI5_dg` | 뇌졸중 |
| `cancer_dx` | `DC1_dg` | 1=any cancer |
| `ckd_dx` | `DK4_dg` | optional |
| `hep_b` | `LQ_5HepB` | 1=B형간염 |
| `hep_c` | `LQ_5HepC` | 1=C형간염 |

## 6. Behavior / Lifestyle

| std_name | KNHANES 변수 | 비고 |
|---|---|---|
| `smoking_current` | `BS3_1` | 1=daily 2=occasional 3=former 8=never |
| `smoking_pyrs` | `BS_pck_yr` | pack-years (계산변수) |
| `alcohol_freq` | `BD1_11` | 음주 빈도/월 |
| `alcohol_amt_drink` | `BD2_1` | 1회 음주량 (잔) |
| `alcohol_g_week` | derived | = freq×amount×g/standard_drink (★ MetALD cutoff) |
| `pa_vig` | `BE3_71` | 격렬 신체활동 일/주 |
| `pa_mod` | `BE3_75` | 중강도 신체활동 일/주 |
| `sleep_hours` | derived (BP16_11~14, 2018+) / `BP16_1` (2007-2017) | ★ 코딩 변경 |
| `stress` | `BP1` | 1=많이 4=거의 없음 |
| `depression_2wk` | `BP5` | M_SAD equivalent |

## 7. Nutrition (24h Recall)

| std_name | KNHANES 변수 | 단위 |
|---|---|---|
| `energy_kcal` | `N_EN` | kcal/day |
| `protein_g` | `N_PROT` | g/day |
| `fat_g` | `N_FAT` | g/day |
| `cho_g` | `N_CHO` | g/day |
| `sodium_mg` | `N_NA` | mg/day |
| `calcium_mg` | `N_CA` | mg/day |
| `fiber_g` | `N_FIBER` | g/day |
| `sugar_g` | `N_SUG` | g/day |
| `npd_score` | derived | NOVA classification ★ UPF 분석용 |

## 8. ★ 도메인 패턴 (이 매핑이 분석 코드를 만든다)

### 8.1 MASLD (2023 정의, AASLD/EASL) — Korean adaptation
**필요 변수**: BMI/wc/glucose/hba1c/sbp/dbp/HDL/TG + DE1_dg/DI1_dg/DI2_dg

**판별식 (`src/data/knhanes_patterns.py`)**:
```
hepatic_steatosis = FLI(BMI, wc, TG, GGT) ≥ 60
   OR HSI(ALT, AST, BMI, sex, DM) ≥ 36
cardiometabolic_risk ≥ 1 (총 5축):
  - BMI ≥ 23 OR wc > 90남/85여
  - glucose ≥ 100 OR hba1c ≥ 5.7% OR DM_dx/tx
  - sbp ≥ 130 OR dbp ≥ 85 OR HT_dx/tx
  - TG ≥ 150 OR lipid-lowering
  - HDL ≤ 40남/50여
MASLD = steatosis AND cardiometabolic_risk
```

### 8.2 MetALD (2023 신설) — moderate alcohol overlap
**필요 변수**: 위 + BD1_11 + BD2_1 (알코올 g/주 계산)
```
moderate_alcohol_M = 140 ≤ g/week ≤ 350
moderate_alcohol_F = 70 ≤ g/week ≤ 210
MetALD = steatosis AND cardiometabolic ≥ 1 AND moderate_alcohol
ALD_predominant = steatosis AND g/week > 350M / 210F
```

### 8.3 IDF Metabolic Syndrome (Asian)
**필요 변수**: 위 + wc 우선
```
wc > 90남/85여  (Korean cutoff)
+ TG ≥ 150 (또는 lipid-lowering)
+ HDL ≤ 40남/50여
+ SBP ≥ 130 / DBP ≥ 85 (또는 HT_tx)
+ glucose ≥ 100 (또는 DM_dx/tx)
≥ 3개 중심성비만 + 2개 추가 = MetSx
```

### 8.4 CKD stage (eGFR CKD-EPI 2021)
필요 변수: HE_crea + age + sex → eGFR → G1~G5 stage.

### 8.5 NOVA UPF Classification (KNHANES 24h recall 기반)
영양조사 식품군 매칭 → NOVA 4분류 (1=unprocessed, 4=ultra-processed). 식품군 매핑 yaml 필요 (별도).

## 9. 데이터 세분화 (subgroup) helpers

`src/data/knhanes_subgroup.py`:
- `bmi_category(bmi)`: WHO Asian cutoff (`<18.5 / 18.5-22.9 / 23-24.9 / 25-29.9 / 30+`)
- `age_group(age, scheme="decade"|"who"|"adolescent")`: 10대 단위 또는 WHO 표준
- `income_quartile_label(incm)`: Q1 lowest ~ Q4 highest
- `education_group(edu)`: 4분류 통일
- `urban_rural(region)`: 7대도시 vs 도/광역
- `pool_years(df_list, balance_weights=True)`: 다연도 pool (가중치 보정 후 합)
- `study_phase_label(year)`: Phase IV (07-09) / V (10-12) / VI (13-15) / VII (16-18) / VIII (19-21) / IX (22-24)

## 10. wave별 호환성 요약 (★상관·결손)

| 변수 그룹 | HN13 | HN14 | HN15 | HN16 | HN17 | HN18 | HN19 | HN20 | HN21 | HN22 | HN23 | HN24 |
|---|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|:-:|
| Survey design (strata/psu/wt) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| wt_ntr (영양) | ✗ wt_ntex | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| HDL_st2 (표준화) | ✗ HDLc | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| LDL_drct (직접측정) | ✗ LDLc | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| sleep_hours (BP16_1 단일) | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| sleep (BP16_11~14 분리, derived) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Eye exam | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✗ | ✗ | ✗ |
| FFQ (별도파일) | ✗ | ✓ | ✓ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ |
| 24RC | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

## 11. 다연도 pool 권장 조합

| 분석 목적 | 권장 pool | 이유 |
|---|---|---|
| MASLD/MetALD 신정의 | HN19-HN24 (6년) | HDL_st2 / LDL_drct 일관성 |
| 만성질환 trend | HN13-HN24 (12년) | 충분한 power, design-effect 보정 |
| NOVA UPF×outcome | HN16-HN24 (9년) | FFQ는 결손, 24RC 통일 |
| Adolescent 분석 (12-18세) | HN13-HN24 (12년) | 표본 작음, 가급적 풀 pool |

## 12. 한계 (정직)

- **Liver imaging 없음** — MASLD는 FLI/HSI surrogate (sens ~70-80%, spec ~80%). biopsy/MRI-PDFF/FibroScan 결과 없음.
- **HE_GGT 일부 wave 결손** — FLI 계산 시 확인 필요 (대부분 있음).
- **혈청검사 표준화 변경** — 2019년 전후 HDL/LDL 값 직접 비교 주의 (호환 표 §10 참고).
- **24RC 단일 day** — usual intake 추정엔 NCI method 같은 추가 보정 필요.
- **자가보고 진단/치료** — DI1_dg 등은 의사진단 self-report. 측정값으로 보강 권장.

## 13. 참고 문서

- KDCA 「국민건강영양조사 자료 이용지침」 4기(2007-09) ~ 9기(2022-24): `data/raw/knhanes/지침서/*.pdf` (25개)
- 식품·식이코드 자료집: `data/raw/knhanes/지침서/HN<YY>_24RC(식품_영양코드).xlsx`
- Rinella ME et al. *Hepatology* 2023; 78:1966–1986 (MASLD/MetALD 정의)
- Bedogni G et al. *BMC Gastroenterol* 2006; 6:33 (FLI)
- Lee JH et al. *Dig Liver Dis* 2010; 42:503–508 (HSI)
