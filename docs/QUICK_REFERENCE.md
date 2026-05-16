# 📍 빠른 참조 카드 - Reference Library 한눈에 보기

## 🎯 언제 어디서 뭘 하는가?

### 상황 1️⃣: "t-test를 배우고 싶어요"

```
Step 1: Reference 찾기
┌──────────────────────────────────────────┐
│ /src/statistics/medical_stats.py          │
│ → Ctrl+F "t_test" 검색                    │
│ → 메서드 정의와 설명 읽기                 │
│ → 반환 값의 의미 이해                     │
└──────────────────────────────────────────┘

Step 2: 예제 보기
┌──────────────────────────────────────────┐
│ /examples/01_statistics_example.py        │
│ → "example_t_test()" 함수 찾기            │
│ → 실제 사용법 코드 분석                   │
└──────────────────────────────────────────┘

Step 3: 직접 실습
┌──────────────────────────────────────────┐
│ /learning/notebooks/02_statistical_*.ipynb│
│ → t-test 예제 셀 실행                     │
│ → 자신의 데이터로 수정                    │
└──────────────────────────────────────────┘

Step 4: 자신의 분석
┌──────────────────────────────────────────┐
│ /learning/notebooks/05_my_analysis.ipynb  │
│ → 새 노트북에서 직접 작성                 │
│ → 프로덕션 배포 준비                      │
└──────────────────────────────────────────┘
```

---

### 상황 2️⃣: "어떤 통계 분석을 할 수 있어?"

**빠른 검색 맵:**

```
목적                    메서드명                  파일위치
─────────────────────────────────────────────────────────
기본 통계              descriptive_stats()       
정규분포 확인           detect_normality()        MedicalStatistics
두 그룹 비교            t_test()                  클래스
세 개 이상 그룹         anova()                   /src/statistics/
비모수 검정             mann_whitney_u()          medical_stats.py
                       kruskal_wallis()
범주형 데이터          chi_square()              CategoricalAnalysis
                       proportion_test()         클래스
생존분석               kaplan_meier()            SurvivalAnalysis
                       cox_regression()          클래스
상관분석               correlation()             
회귀분석               regression_analysis()     MedicalStatistics
                       logistic_regression()     클래스
다중 비교 보정          bonferroni_correction()   MultipleComparison
                       fdr_correction()          클래스
결측치 처리             handle_missing_values()   MedicalStatistics
```

---

### 상황 3️⃣: "이 메서드 사용법을 모르겠어"

```
찾기 순서:

1순위: /src/statistics/medical_stats.py
   └─ 메서드 정의와 docstring
   
2순위: /examples/01_statistics_example.py
      /examples/02_data_management_example.py
      /examples/03_novelty_detection_example.py
   └─ 실제 사용 예제
   
3순위: /learning/notebooks/
   └─ Jupyter에서 상세 설명과 실행
   
4순위: /docs/LEARNING_GUIDE.md
   └─ 학습 경로와 가이드
```

---

## 📂 각 영역별 역할 정리

```
┌─────────────────────────────────────┐
│ /src/statistics/medical_stats.py    │  ⭐ 메서드 정의 (Ctrl+F로 찾기)
│ - MedicalStatistics                 │  ⭐ Docstring 읽기
│ - SurvivalAnalysis                  │  ⭐ 파라미터와 반환값 이해
│ - CategoricalAnalysis               │
│ - MultipleComparison                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ /examples/*_example.py              │  ⭐ 실행 가능한 완전한 예제
│ - 01_statistics_example.py          │  ⭐ 데이터 생성부터 결과까지
│ - 02_data_management_example.py     │  ⭐ 여러 메서드 조합 사용법
│ - 03_novelty_detection_example.py   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ /learning/notebooks/                │  ⭐ 대화형 학습
│ - 01_data_exploration.ipynb         │  ⭐ 마크다운 설명 + 코드
│ - 02_statistical_analysis.ipynb     │  ⭐ 결과 시각화
│ - 03_visualization.ipynb            │  ⭐ 단계별 실행
│ - 04_manuscript_generation.ipynb    │
│ - 05_my_analysis.ipynb (새로 만들) │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ /docs/                              │  ⭐ 학습 경로
│ - LEARNING_GUIDE.md                 │  ⭐ 프로젝트 구조
│ - ARCHITECTURE.md                   │  ⭐ 설계 원칙
│ - VSCODE_WORKFLOW.md                │  ⭐ 실무 팁
│ - PROJECT_STRUCTURE.md              │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│ /app/main.py                        │  ⭐ 프로덕션 API
│ - REST 엔드포인트                    │  ⭐ 자동화 분석
│ - 웹 서버                           │  ⭐ 배포 준비
└─────────────────────────────────────┘
```

---

## 🚀 5분 빠른 시작

```bash
# 1️⃣ Jupyter Lab 시작 (3초)
jupyter lab --notebook-dir=learning/notebooks

# 2️⃣ 브라우저에서 열기 (2초)
# http://localhost:8888

# 3️⃣ 노트북 선택
# 01_data_exploration.ipynb

# 4️⃣ 첫 셀 실행
# Shift+Enter

# ✅ 끝! 이제 학습 시작 가능
```

---

## 🎯 메서드별 Quick Reference

### 📊 기술통계 (Descriptive Statistics)

```python
from src.statistics import MedicalStatistics

stats = MedicalStatistics()

# 단일 시리즈
result = stats.descriptive_stats(series)
# 반환: DataFrame (mean, median, std, min, max, quantiles...)

# 그룹별 통계
result = stats.grouped_descriptive(df, 'value_col', 'group_col')
# 반환: DataFrame (각 그룹별 통계)
```

**언제 사용:**
- ✅ 데이터의 기본 특성 파악
- ✅ 보고서 작성 시 기술통계 제시

---

### 📈 비교검정 (Comparison Tests)

```python
# 👥 두 그룹 비교
result = stats.t_test(group1, group2, paired=False)
result = stats.mann_whitney_u(group1, group2)
# 반환: Dict (t_statistic, p_value, effect_size...)

# 👥👥👥 세 개 이상 그룹 비교
result = stats.anova(group1, group2, group3)
result = stats.kruskal_wallis(group1, group2, group3)
# 반환: Dict (f_statistic/h_statistic, p_value...)

# 📋 범주형 비교
result = stats.chi_square(contingency_table)
# 반환: Dict (chi2_statistic, p_value, cramers_v...)
```

**언제 사용:**
- ✅ 처리군과 대조군 비교
- ✅ 여러 치료법 효과 비교
- ✅ 범주형 변수 관계 분석

---

### 🔗 상관분석 (Correlation)

```python
# 두 변수 상관성
result = stats.correlation(x, y, method='pearson')
# 반환: Dict (correlation, p_value, ci_lower, ci_upper...)

# 전체 상관행렬
result = stats.correlation_matrix(df, method='pearson', p_values=True)
# 반환: DataFrame (각 쌍의 상관계수와 p값)
```

**언제 사용:**
- ✅ 변수 간 선형 관계 확인
- ✅ 다중공선성 체크
- ✅ 변수 선택 (회귀분석 전)

---

### 📉 회귀분석 (Regression)

```python
# 선형 회귀
result = stats.regression_analysis(df, y_col='outcome', 
                                   x_cols=['age', 'bmi'])
# 반환: Dict (coefficients, r_squared, p_values...)

# 로지스틱 회귀 (이진 분류)
result = stats.logistic_regression(df, y_col='disease',
                                   x_cols=['age', 'risk_factor'])
# 반환: Dict (odds_ratios, auc, sensitivity, specificity...)
```

**언제 사용:**
- ✅ 예측 모델 구축
- ✅ 위험 인자 분석
- ✅ 질병 진단 확률 계산

---

### ⏳ 생존분석 (Survival Analysis)

```python
from src.statistics import SurvivalAnalysis

survival = SurvivalAnalysis()

# Kaplan-Meier 곡선
result = survival.kaplan_meier(durations, events, group=None)
# 반환: Dict (kmf객체, survival_func, median_survival...)

# Cox 비례위험 모델
result = survival.cox_regression(df, 'time', 'event', 
                                x_cols=['treatment', 'age'])
# 반환: Dict (hazard_ratios, concordance_index...)

# Log-rank 검정
result = survival.log_rank_test(dur1, events1, dur2, events2)
# 반환: Dict (test_statistic, p_value...)
```

**언제 사용:**
- ✅ 임상시험 생존율 비교
- ✅ 예후 인자 분석
- ✅ 추적 관찰 연구

---

### 📊 범주형 분석 (Categorical Analysis)

```python
from src.statistics import CategoricalAnalysis

cat = CategoricalAnalysis()

# 분할표
table = cat.contingency_table(df, 'row_var', 'col_var')

# 비율 검정
result = cat.proportion_test(successes=50, totals=100)
# 또는 여러 그룹: proportion_test([50, 60], [100, 100])

# McNemar 검정 (쌍을 이룬 이진 변수)
result = cat.mcnemar_test(df, 'before', 'after')
```

**언제 사용:**
- ✅ 카테고리 변수 관계 분석
- ✅ 반응률/완치율 비교
- ✅ 사전-사후 검사

---

### 🔬 가정 검정 (Assumption Tests)

```python
# 정규성 검정
result = stats.detect_normality(series, test='shapiro')
# 또는: 'anderson', 'kstest'

# 반환: Dict (statistic, p_value, is_normal...)
```

**언제 사용:**
- ✅ 통계 검정 선택 (모수 vs 비모수)
- ✅ 데이터 변환 필요 여부 판단

---

### ✅ 다중 비교 보정 (Multiple Comparison)

```python
from src.statistics import MultipleComparison

comp = MultipleComparison()

# Bonferroni 보정
result = comp.bonferroni_correction(p_values=[0.01, 0.05, 0.1])
# 반환: Dict (p_original, p_adjusted, significant...)

# FDR 보정 (더 보수적)
result = comp.fdr_correction(p_values=[0.01, 0.05, 0.1])
```

**언제 사용:**
- ✅ 다중 가설검정 시 Type I 오류 보정
- ✅ 유전자 발현 연구 (수천 개 유전자)
- ✅ 임상 다중 검정

---

## 💾 데이터 관리

```python
from src.database import MedicalDatabase, DataCleaner

# 데이터베이스 작업
db = MedicalDatabase('research.db')
db.insert_data('patients', df)
result = db.query("SELECT * FROM patients WHERE age > 50")

# 결측치 처리
cleaner = DataCleaner()
df_clean = cleaner.handle_missing_values(df, strategy='mean')
outliers = cleaner.detect_outliers(df, method='iqr')
df_normalized = cleaner.normalize(df, method='minmax')
```

---

## 📊 시각화

```python
from src.visualization import MedicalVisualizer

viz = MedicalVisualizer()

# 기본 그래프
viz.distribution_plot(data, title="분포도")
viz.box_plot(df, x='group', y='value')
viz.scatter_with_trend(x, y)

# 상호작용 그래프
viz.interactive_scatter(df, x='age', y='cholesterol', color='treatment')
viz.interactive_box(df, x='group', y='outcome')
```

---

## 🔍 NLP & 참신성 감지

```python
from src.nlp import NoveltyDetector, KeywordExtractor, TextAnalyzer

# 연구 참신성
detector = NoveltyDetector()
gap = detector.detect_research_gaps(corpus, new_research)

# 키워드 추출
extractor = KeywordExtractor()
keywords = extractor.extract_keywords(text, top_n=10)

# 텍스트 분석
analyzer = TextAnalyzer()
metrics = analyzer.readability_metrics(text)
```

---

## 📝 논문 생성

```python
from src.papergen import ManuscriptGenerator

gen = ManuscriptGenerator(title, authors, institution)

# 각 섹션 생성
abstract = gen.generate_abstract(bg, obj, methods, results, conc)
introduction = gen.generate_introduction(problem, lit, gap, hyp)
methods = gen.generate_methods(design, pop, collection, analysis)
results = gen.generate_results(stats_dict, findings_list)

# 완전한 논문
manuscript = gen.generate_full_manuscript(sections_dict)
```

---

## 🎓 학습 체크리스트

```
단계 1: 기초 이해
□ LEARNING_GUIDE.md 읽기
□ /src/statistics/ 구조 파악
□ Reference Library에 어떤 메서드가 있는지 숙지

단계 2: 예제 실행
□ /examples/01_statistics_example.py 실행
□ 결과 이해하기
□ 코드 수정해서 재실행

단계 3: Jupyter 실습
□ /learning/notebooks/ 에서 대화형 학습
□ 셀 하나씩 실행하면서 이해
□ 자신의 데이터로 변경

단계 4: 자체 분석
□ 새 노트북 생성 (05_my_analysis.ipynb)
□ Reference Library 사용해서 분석
□ 결과 해석 및 시각화

단계 5: 배포 준비
□ /app/main.py 에서 API 엔드포인트 추가
□ REST API로 테스트
□ 프로덕션 배포
```

---

## 🆘 문제 해결

| 문제 | 해결 |
|------|------|
| 메서드 사용법을 모르겠어 | → /src/statistics/ 에서 docstring 읽기 |
| 예제가 필요해 | → /examples/ 의 해당 파일 실행 |
| 결과를 어떻게 해석할지 | → /learning/notebooks/ 의 설명 읽기 |
| API로 사용하고 싶어 | → /app/main.py 에 엔드포인트 추가 |
| 새로운 분석을 만들고 싶어 | → 새 노트북 생성 후 Reference 참고하며 작성 |

---

## 🚀 다음 단계

```
✅ Reference Library 학습 완료
   ↓
✅ 예제 코드 실행 & 이해
   ↓
✅ 자신의 데이터로 분석
   ↓
✅ Jupyter에서 완성된 분석
   ↓
✅ /app/ 에서 API로 자동화
   ↓
✅ 프로덕션 배포 & 운영
```

**시작하기:** `jupyter lab --notebook-dir=learning/notebooks`

