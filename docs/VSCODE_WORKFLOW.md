# VS Code 창 분리 학습/개발 워크플로우

## 🪟 창 배치 전략

### 추천 레이아웃: 좌측(학습) vs 우측(개발)

```
┌────────────────────────────────────────────────────────────────┐
│                    VS Code Editor                             │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐
│  │   📚 LEFT PANEL      │  │   💻 RIGHT PANEL                 │
│  │   (학습 & Reference) │  │   (개발 & 실습)                 │
│  │                      │  │                                  │
│  │ /src/statistics/     │  │ /learning/notebooks/             │
│  │  └ medical_stats.py  │  │  └ 05_my_analysis.ipynb          │
│  │                      │  │                                  │
│  │ /examples/           │  │ Terminal (아래)                  │
│  │  └ 01_statistics     │  │  python my_script.py             │
│  │    _example.py       │  │                                  │
│  │                      │  │                                  │
│  │ /docs/               │  │                                  │
│  │  └ LEARNING_GUIDE.md │  │                                  │
│  │                      │  │                                  │
│  └──────────────────────┘  └──────────────────────────────────┘
│                                                                │
├────────────────────────────────────────────────────────────────┤
│  🔧 TERMINAL AREA (전체 너비)                                  │
│  python examples/01_statistics_example.py                    │
│  jupyter lab --notebook-dir=learning/notebooks               │
└────────────────────────────────────────────────────────────────┘
```

---

## 🚀 실제 설정 방법

### 1단계: VS Code에서 폴더 열기

```bash
# 터미널에서
code c:\Users\mitto\OneDrive\Desktop\Medical-Agent

# 또는 VS Code > File > Open Folder
```

### 2단계: 창 분리 (좌측 & 우측)

```
단축키:
- Windows/Linux: Ctrl+\  (백슬래시)
- macOS: Cmd+\ 

또는:
- View > Editor Layout > Two Columns
```

### 3단계: 파일 배치

**좌측 창 (학습 & Reference)**
```
1. Ctrl+P로 명령 팔레트 열기
2. /src/statistics/medical_stats.py 입력
3. 우측 화살표 누르고 좌측 창에서 열기
```

**우측 창 (개발 & 실습)**
```
1. Ctrl+P로 명령 팔레트 열기
2. learning/notebooks/02_statistical_analysis.ipynb 입력
3. 우측 화살표 누르고 우측 창에서 열기
```

---

## 📋 추천 학습 창 배치

### 🎯 Setup 1: Reference Library 학습

```
좌측:  /src/statistics/medical_stats.py
우측:  /learning/notebooks/02_statistical_analysis.ipynb
하단:  Terminal
```

**워크플로우:**
1. 좌측에서 `MedicalStatistics.t_test()` 찾기
2. 우측 노트북에서 실제 사용 예제 보기
3. 하단 Terminal에서 직접 실행
4. 결과 확인

### 🎯 Setup 2: 예제 코드 학습

```
좌측:  /examples/01_statistics_example.py
우측:  /learning/notebooks/05_my_analysis.ipynb (새로 만든 파일)
하단:  Terminal
```

**워크플로우:**
1. 좌측 예제 코드 분석
2. 우측에서 자신의 데이터로 수정
3. 하단에서 실행
4. 결과 확인

### 🎯 Setup 3: Documentation 참고

```
좌측:  /docs/LEARNING_GUIDE.md
우측:  /learning/notebooks/03_visualization.ipynb
하단:  Terminal
```

**워크플로우:**
1. 좌측에서 어떤 걸 할 수 있는지 확인
2. 우측에서 실제로 구현
3. 하단에서 검증

---

## 💡 단축키로 빠르게 전환

```
VS Code 단축키:

Ctrl+1           → 좌측 그룹 포커스
Ctrl+2           → 우측 그룹 포커스
Ctrl+3           → 우측 우측 그룹 포커스 (3분할일 때)

Ctrl+\           → 현재 에디터를 분할
Ctrl+K, Ctrl+←  → 그룹 크기 줄이기
Ctrl+K, Ctrl+→  → 그룹 크기 늘리기

Ctrl+`           → Terminal 토글
```

---

## 🎓 실전 예제: Reference Library 학습

### 시나리오: "t-test를 배우고 싶어요"

#### 단계 1: Reference Library 확인 (좌측 창)

파일: `/src/statistics/medical_stats.py`

```python
@staticmethod
def t_test(group1: pd.Series, group2: pd.Series, paired: bool = False) -> Dict[str, Any]:
    """Perform t-test with effect sizes
    
    Args:
        group1: First group data
        group2: Second group data
        paired: Whether samples are paired
        
    Returns:
        Dictionary with comprehensive test results
    """
    # ... 구현 코드 ...
    
    return {
        't_statistic': t_stat,
        'p_value': p_val,
        'cohens_d': cohens_d,
        'mean_diff': mean_diff,
        'ci_lower': ci_lower,
        'ci_upper': ci_upper,
        'significant': p_val < 0.05,
        # ...
    }
```

**배울 점:**
- 입력: `group1`, `group2` (pd.Series)
- 선택: `paired=True/False`
- 출력: 딕셔너리 (p_value, cohens_d, 신뢰구간 포함)

#### 단계 2: 예제 코드 보기 (우측 창)

파일: `/learning/notebooks/02_statistical_analysis.ipynb`

```python
from src.statistics import MedicalStatistics

# 데이터 준비
control = df[df['treatment'] == 'Control']['followup_score']
treatment_a = df[df['treatment'] == 'Treatment A']['followup_score']

# t-test 실행
med_stats = MedicalStatistics()
t_test_results = med_stats.t_test(control, treatment_a, paired=False)

# 결과 해석
print(f"t-statistic: {t_test_results['t_statistic']:.4f}")
print(f"p-value: {t_test_results['p_value']:.4f}")
print(f"Cohen's d: {t_test_results['cohens_d']:.4f}")
```

#### 단계 3: 직접 실습 (우측 창 - 새 노트북)

파일: `/learning/notebooks/05_my_t_test.ipynb`

```python
# 자신의 데이터로 시도
import pandas as pd
from src.statistics import MedicalStatistics

# 자신의 데이터 로드
df = pd.read_csv('../data/my_data.csv')

# 두 그룹 추출
group_a = df[df['category'] == 'A']['value']
group_b = df[df['category'] == 'B']['value']

# t-test 실행
stats = MedicalStatistics()
result = stats.t_test(group_a, group_b)

# 결과 확인
print(f"p-value: {result['p_value']:.4f}")
if result['significant']:
    print("유의미한 차이가 있습니다!")
else:
    print("유의미한 차이가 없습니다.")
```

---

## 📊 4가지 창 레이아웃 조합

### Layout A: 이론 학습 (초보자용)
```
┌──────────────────┬──────────────────┐
│ Documentation    │ Jupyter Notebook │
│ LEARNING_GUIDE   │ 01_exploration   │
└──────────────────┴──────────────────┘
         Terminal (하단)
```

### Layout B: Reference 학습 (중급자용)
```
┌──────────────────┬──────────────────┐
│ Reference Code   │ Example Code     │
│ medical_stats.py │ 01_example.py    │
└──────────────────┴──────────────────┘
         Terminal (하단)
```

### Layout C: 실습 & 개발 (고급자용)
```
┌──────────────────┬──────────────────┐
│ Example File     │ My Notebook      │
│ 01_example.py    │ 05_my_analysis   │
└──────────────────┴──────────────────┘
         Terminal (하단)
```

### Layout D: 풀 스택 분석
```
┌──────────────────┬──────────────────┐
│ Documentation    │ Jupyter Notebook │
│ + Reference Code │ + Terminal       │
└──────────────────┴──────────────────┘
```

---

## 🎯 일일 워크플로우 예제

### 오전: 새로운 통계 방법 학습

1. **9시 - Reference 읽기** (좌측)
   ```
   /src/statistics/medical_stats.py
   → correlation_matrix() 메서드 분석
   ```

2. **9시 30분 - 예제 실행** (우측)
   ```
   /examples/01_statistics_example.py
   → correlation 부분 실행
   ```

3. **10시 - 직접 실습** (우측, 새 노트북)
   ```
   /learning/notebooks/my_correlation.ipynb
   → 자신의 데이터로 실행
   ```

### 오후: 고도화 & 최적화

4. **2시 - 기존 코드 개선** (좌측 + 우측)
   ```
   좌측: /src/statistics/medical_stats.py (참고)
   우측: /learning/notebooks/05_my_analysis.ipynb (수정)
   ```

5. **3시 - API로 배포** (좌측 + 하단)
   ```
   좌측: /app/main.py (REST endpoint 추가)
   하단: Terminal (테스트)
   ```

---

## 🚀 효율적인 학습 팁

### Tip 1: 좌측 = 참고, 우측 = 실행
- 절대 좌측을 수정하지 말 것
- 좌측은 읽기 전용으로 Reference 용도
- 우측에서만 자신의 코드 작성

### Tip 2: Jupyter Notebook 미리보기
```
Ctrl+Shift+V (마크다운) → Jupyter 파일은 자동으로 렌더링
```

### Tip 3: Terminal로 빠른 테스트
```bash
# Terminal에서 직접 Python 실행
python
>>> import pandas as pd
>>> from src.statistics import MedicalStatistics
>>> stats = MedicalStatistics()
>>> # 테스트...
```

### Tip 4: File Explorer에서 끌어다 놓기
```
좌측 File Explorer에서 파일 우클릭
→ "Open to the Side" 클릭
→ 자동으로 분할된 창에서 열림
```

---

## 📌 VS Code 설정 팁

### settings.json에 추가 권장 설정

```json
{
  // Python 포매팅
  "python.formatting.provider": "black",
  "[python]": {
    "editor.formatOnSave": true,
    "editor.defaultFormatter": "ms-python.python"
  },

  // Jupyter 설정
  "jupyter.notebookFileRoot": "${workspaceFolder}",
  "jupyter.interactiveWindow.textEditor.executeSelection": true,

  // 글꼴 크기 (읽기 쉬운 크기)
  "editor.fontSize": 14,
  "editor.lineHeight": 1.6,

  // Minimap (우측 작은 지도)
  "editor.minimap.enabled": true,

  // 탭 크기
  "editor.tabSize": 4,
  "editor.insertSpaces": true
}
```

### 추천 확장 프로그램

```
- Python (Microsoft)
- Pylance (Python 언어 지원)
- Jupyter (Notebook 지원)
- Pandas (DataFrame 시각화)
- Thunder Client (API 테스트)
```

---

## 🎓 학습 진도 체크리스트

```
□ VS Code에서 두 창 분할 완료
□ 좌측에 /src/statistics/medical_stats.py 열기
□ 우측에 /learning/notebooks/02_statistical_analysis.ipynb 열기
□ 하단에 Terminal 열기 (Ctrl+`)
□ Reference Library 메서드 리스트 이해
□ 예제 코드 한 번 이상 실행
□ 자신의 데이터로 수정해서 실행
□ 새로운 노트북 생성해서 작성
□ 결과를 이해하고 해석할 수 있음
□ 프로덕션(API)에 배포 준비 완료
```

