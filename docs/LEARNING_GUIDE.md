# 📚 통계 학습 & 자가 고도화 가이드

## 🎯 전체 구조 한눈에 보기

```
┌─────────────────────────────────────────────────────────────────┐
│           🚀 프로덕션 앱 (웹 서버)                              │
│         /app/main.py → http://localhost:5000                   │
│  - REST API로 통계 분석 요청                                    │
│  - 자동화 분석 파이프라인                                       │
│  - 비프로그래머도 사용 가능                                     │
└─────────────────────────────────────────────────────────────────┘
                            ↑ 활용
┌─────────────────────────────────────────────────────────────────┐
│        📦 핵심 Reference Library (재사용 가능한 코드)           │
│              /src/statistics/*                                  │
│  ✓ MedicalStatistics - 기본 통계 분석                          │
│  ✓ SurvivalAnalysis - 생존분석                                 │
│  ✓ CategoricalAnalysis - 범주형 분석                           │
│  ✓ MultipleComparison - 다중 비교 보정                         │
└─────────────────────────────────────────────────────────────────┘
                      ↑ 학습하고 응용
┌─────────────────────────────────────────────────────────────────┐
│     💡 학습 & 개발 영역 (당신의 작업 공간)                      │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ /learning/notebooks/ ← 🎓 JUPYTER에서 대화형 학습       │  │
│  │ ├── 01_data_exploration.ipynb                           │  │
│  │ ├── 02_statistical_analysis.ipynb                       │  │
│  │ ├── 03_visualization.ipynb                              │  │
│  │ └── 04_manuscript_generation.ipynb                      │  │
│  │                                                          │  │
│  │ /examples/ ← 💡 작동하는 예제 코드                      │  │
│  │ ├── 01_statistics_example.py                            │  │
│  │ ├── 02_data_management_example.py                       │  │
│  │ └── 03_novelty_detection_example.py                     │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🎓 학습 경로 (3단계)

### 1️⃣ **기초 학습** (완전 초보자)
📍 위치: `/learning/notebooks/01_data_exploration.ipynb`

**하는 일:**
- 데이터 로드하기
- 기본 통계값 계산 (평균, 중앙값, 표준편차)
- 데이터 분포 시각화
- Null값 확인

**학습 방법:**
```bash
# 1. Jupyter Lab 시작
jupyter lab --notebook-dir=learning/notebooks

# 2. 01_data_exploration.ipynb 열기
# 3. 셀 하나씩 실행하면서 이해하기
# 4. 자신의 데이터로 변경해서 실행해보기
```

**예제:**
```python
import pandas as pd
from src.statistics import MedicalStatistics

# 데이터 로드
df = pd.read_csv('your_data.csv')

# 기본 통계
stats = MedicalStatistics()
result = stats.descriptive_stats(df['blood_pressure'])
print(result)
```

---

### 2️⃣ **중급 학습** (통계 개념 이해)
📍 위치: `/learning/notebooks/02_statistical_analysis.ipynb`

**하는 일:**
- t-test, ANOVA, 카이제곱 검정
- 상관분석
- 비모수 검정 (Mann-Whitney U, Kruskal-Wallis)
- 정규성 검정

**학습 방법:**
```bash
# 1. 02_statistical_analysis.ipynb 실행
# 2. 각 통계 검정 이해하기
# 3. 언제 어떤 검정을 쓸지 파악하기
# 4. 실제 데이터에 적용해보기
```

**예제:**
```python
# 두 그룹 비교
control = df[df['treatment'] == 'Control']['outcome']
treatment = df[df['treatment'] == 'Treatment']['outcome']

result = stats.t_test(control, treatment)
print(f"p-value: {result['p_value']}")
print(f"Cohen's d: {result['cohens_d']}")

# 상관분석
corr = stats.correlation(df['age'], df['cholesterol'], method='pearson')
print(corr)
```

---

### 3️⃣ **고급 학습** (맞춤형 분석)
📍 위치: `/examples/` + `/learning/notebooks/`

**하는 일:**
- 생존분석 (Kaplan-Meier)
- 회귀분석 (선형, 로지스틱)
- Cox 비례위험 모델
- 다중 비교 보정
- 자신의 분석 파이프라인 구축

**학습 방법:**
```bash
# 1. /examples/ 의 예제들 실행
python examples/01_statistics_example.py

# 2. 코드 분석하고 이해하기
# 3. 자신의 문제에 맞춰 수정하기
# 4. 새로운 노트북 만들어서 고도화하기
```

**예제:**
```python
# 회귀분석
result = stats.regression_analysis(
    df=df,
    y_col='outcome',
    x_cols=['age', 'blood_pressure', 'cholesterol']
)
print(result)

# 로지스틱 회귀
logistic_result = stats.logistic_regression(
    df=df,
    y_col='disease',
    x_cols=['age', 'risk_factor']
)
print(f"AUC: {logistic_result['auc']}")
```

---

## 📖 Reference Library 상세 가이드

### `MedicalStatistics` 클래스
📍 위치: `/src/statistics/medical_stats.py`

**기술할 수 있는 모든 메서드:**

```python
from src.statistics import MedicalStatistics

stats = MedicalStatistics()

# 1️⃣ 기술통계
stats.descriptive_stats(series)              # 기본 통계
stats.grouped_descriptive(df, 'value', 'group')  # 그룹별 통계

# 2️⃣ 비교검정
stats.t_test(group1, group2, paired=False)  # t-검정
stats.mann_whitney_u(group1, group2)        # Mann-Whitney U
stats.chi_square(contingency_table)         # 카이제곱
stats.anova(*groups)                        # ANOVA
stats.kruskal_wallis(*groups)               # Kruskal-Wallis

# 3️⃣ 상관 및 연관성
stats.correlation(x, y, method='pearson')   # 상관분석
stats.correlation_matrix(df)                # 상관행렬

# 4️⃣ 회귀분석
stats.regression_analysis(df, 'y', ['x1', 'x2'])      # 선형회귀
stats.logistic_regression(df, 'y', ['x1', 'x2'])      # 로지스틱

# 5️⃣ 가정 검정
stats.detect_normality(series, test='shapiro')        # 정규성

# 6️⃣ 결측치 처리
stats.handle_missing_values(df, strategy='mean')      # 결측치 처리
```

### `SurvivalAnalysis` 클래스
📍 위치: `/src/statistics/medical_stats.py`

```python
from src.statistics import SurvivalAnalysis

survival = SurvivalAnalysis()

# 생존분석
km_result = survival.kaplan_meier(durations, events)

# Cox 회귀
cox_result = survival.cox_regression(
    df=df,
    duration_col='time',
    event_col='event',
    x_cols=['age', 'treatment']
)

# Log-rank 검정
lr_result = survival.log_rank_test(
    durations1, events1,
    durations2, events2
)
```

### `CategoricalAnalysis` 클래스
```python
from src.statistics import CategoricalAnalysis

cat = CategoricalAnalysis()

# 분할표 작성
table = cat.contingency_table(df, 'var1', 'var2')

# 비율 검정
prop_test = cat.proportion_test(successes=50, totals=100)

# McNemar 검정
mcnemar = cat.mcnemar_test(df, 'var1', 'var2')
```

### `MultipleComparison` 클래스
```python
from src.statistics import MultipleComparison

comp = MultipleComparison()

# Bonferroni 보정
bonf = comp.bonferroni_correction(p_values=[0.001, 0.05, 0.1])

# FDR 보정
fdr = comp.fdr_correction(p_values=[0.001, 0.05, 0.1])

# Tukey HSD
tukey = comp.tukey_hsd([group1, group2, group3])
```

---

## 🔄 자가 고도화 워크플로우

### 📋 단계별 진행 방식

```
┌─────────────────────────────────────────┐
│  Step 1: Reference Library 탐색         │
│  /src/statistics/medical_stats.py       │
│  └─ 어떤 메서드가 있는지 파악           │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Step 2: 예제 코드로 배우기              │
│  /examples/01_statistics_example.py     │
│  └─ 실제 사용법 확인                     │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Step 3: Jupyter에서 직접 실습          │
│  /learning/notebooks/                   │
│  └─ 자신의 데이터로 실행해보기          │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Step 4: 새로운 노트북 생성              │
│  05_my_custom_analysis.ipynb            │
│  └─ 자신의 분석 파이프라인 구축         │
└─────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────┐
│  Step 5: 프로덕션에 배포                │
│  /app/main.py에서 사용                  │
│  └─ REST API로 자동화                   │
└─────────────────────────────────────────┘
```

---

## 💻 실제 사용 시나리오

### 시나리오 1: 새로운 통계 분석 학습

```python
# learning/notebooks/05_my_analysis.ipynb 에서

import pandas as pd
from src.statistics import MedicalStatistics

# 1. 데이터 로드
df = pd.read_csv('../data/my_research_data.csv')

# 2. Reference Library 참고하며 분석
stats = MedicalStatistics()

# 기본 통계 확인
desc = stats.descriptive_stats(df['blood_pressure'])
print(desc)

# 정규성 검정
normality = stats.detect_normality(df['blood_pressure'])
print(normality)

# 그룹 비교 (검정 선택)
if normality['is_normal']:
    # 정규분포 → t-test
    result = stats.t_test(df[df['group']=='A']['value'],
                         df[df['group']=='B']['value'])
else:
    # 비정규분포 → Mann-Whitney U
    result = stats.mann_whitney_u(df[df['group']=='A']['value'],
                                 df[df['group']=='B']['value'])

print(result)
```

### 시나리오 2: 새로운 방법론 개발

```python
# learning/notebooks/06_new_methodology.ipynb 에서

import pandas as pd
import numpy as np
from src.statistics import MedicalStatistics, MultipleComparison

# 복수의 통계 검정 수행
p_values = [0.001, 0.05, 0.1, 0.15]

# Reference Library 활용
comp = MultipleComparison()
bonf = comp.bonferroni_correction(p_values)
fdr = comp.fdr_correction(p_values)

# 비교 시각화
comparison_df = pd.DataFrame({
    'original_p': p_values,
    'bonferroni': bonf['p_adjusted'],
    'fdr': fdr['p_adjusted']
})
print(comparison_df)
```

### 시나리오 3: 프로덕션 배포

```python
# app/main.py에 새로운 API 엔드포인트 추가

from src.statistics import MedicalStatistics, SurvivalAnalysis

@app.route('/api/analysis/survival', methods=['POST'])
def analyze_survival():
    data = request.json
    survival = SurvivalAnalysis()
    
    result = survival.kaplan_meier(
        durations=data['durations'],
        event_observed=data['events']
    )
    
    return jsonify({
        'median_survival': float(result['median_survival']),
        'event_count': int(result['event_count'])
    })
```

---

## 📚 학습 자료 위치 정리

| 목적 | 위치 | 파일 | 설명 |
|------|------|------|------|
| **기본 개념** | `/learning/` | `notebooks/01_*.ipynb` | 데이터 탐색, 시각화 |
| **통계 방법** | `/learning/` | `notebooks/02_*.ipynb` | 각종 통계 검정 |
| **시각화** | `/learning/` | `notebooks/03_*.ipynb` | 그래프, 차트 생성 |
| **논문 작성** | `/learning/` | `notebooks/04_*.ipynb` | 원고 자동화 |
| **실행 예제** | `/examples/` | `*_example.py` | 완전히 작동하는 코드 |
| **Reference** | `/src/statistics/` | `medical_stats.py` | 모든 메서드의 소스 |
| **API 사용** | `/app/` | `main.py` | 웹 서버 활용 |
| **설정** | `/app/config/` | `settings.py` | 환경 설정 |

---

## 🚀 빠른 시작 (5분)

```bash
# 1. Jupyter 시작
jupyter lab --notebook-dir=learning/notebooks

# 2. 브라우저에서 01_data_exploration.ipynb 열기

# 3. 첫 번째 셀 실행:
import pandas as pd
from src.statistics import MedicalStatistics

# 4. 자신의 데이터로 변경하고 실행

# 5. 결과 확인하고 다음 노트북으로 진행
```

---

## 💡 팁: 효율적인 학습 방법

1. **Reference Library 먼저 읽기**
   - `/src/statistics/medical_stats.py` 의 메서드 이름들 스캔
   - 각 메서드의 docstring 읽기

2. **예제 코드 실행**
   - `/examples/` 의 파일들 그대로 실행
   - 결과 이해하기

3. **Jupyter에서 실습**
   - `/learning/notebooks/` 에서 직접 실행
   - 변수 수정해서 다시 실행

4. **자신의 노트북 생성**
   - 새로운 `.ipynb` 파일 생성
   - Reference Library 활용해서 작성

5. **프로덕션 배포**
   - 검증된 분석을 `/app/` 에서 API로 제공

