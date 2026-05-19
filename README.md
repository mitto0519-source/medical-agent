# 의료 연구 논문 자동화 분석 환경

## 📁 프로젝트 구조

```
Medical-Agent/
│
├── 📚 learning/              # 🎓 학습 및 탐색 영역
│   ├── notebooks/
│   │   ├── 01_data_exploration.ipynb
│   │   ├── 02_statistical_analysis.ipynb
│   │   ├── 03_visualization.ipynb
│   │   └── 04_manuscript_generation.ipynb
│   └── tutorials/            # 튜토리얼 및 가이드
│
├── 🚀 app/                   # 💼 프로덕션 애플리케이션 영역
│   ├── streamlit_app.py      # Streamlit 메인 애플리케이션 (현재 진입점)
│   ├── ai_panel.py           # AI 패널 모듈
│   ├── api/                  # REST API 엔드포인트
│   ├── config/               # 설정 파일
│   │   └── settings.py
│   ├── pages/                # Streamlit 페이지
│   ├── templates/            # HTML 템플릿
│   └── ⚠️ main.py            # [DEPRECATED] Flask 레거시 코드 (미사용, 삭제 예정)
│
├── 📖 examples/             # 💡 작동 예제
│   ├── 01_statistics_example.py
│   ├── 02_data_management_example.py
│   └── 03_novelty_detection_example.py
│
├── 📚 docs/                 # 문서
│   ├── PROJECT_STRUCTURE.md
│   └── ARCHITECTURE.md
│
├── 📂 data/                 # 연구 데이터 및 데이터셋
│
├── 📦 src/                  # 핵심 라이브러리 코드
│   ├── statistics/          # 의료 통계 분석
│   ├── visualization/       # 그래프 및 시각화
│   ├── database/            # 데이터 관리
│   ├── nlp/                 # NLP 및 참신성 감지
│   └── papergen/            # 논문 생성 도구
│
├── requirements.txt         # Python 의존성
└── README.md               # 프로젝트 문서
```

## 🎯 두 가지 사용 영역

### 🎓 학습 영역 (`/learning`)

**목적**: 대화형 탐색, 실험, 학습

**포함 내용**:
- Jupyter 노트북 (`/notebooks/`)
- 데이터 탐색 및 시각화
- 통계 분석 시연
- 새로운 분석 파이프라인 개발

**사용 방법**:
```bash
jupyter lab --notebook-dir=learning/notebooks
```

**장점**:
- ✅ 대화형 코드 실행
- ✅ 즉시 시각화
- ✅ 점진적 실험
- ✅ 마크다운 문서화
- ✅ 결과 재현 가능

---

### 💼 프로덕션 영역 (`/app`)

**목적**: 안정적이고 즉시 배포 가능한 애플리케이션

**포함 내용**:
- Flask 웹 애플리케이션
- REST API 엔드포인트
- 환경별 설정
- HTML UI 템플릿

**사용 방법**:
```bash
cd app
python main.py
```

**API 엔드포인트**:
- `POST /api/statistics` - 통계 계산
- `POST /api/analysis/novelty` - 연구 참신성 분석
- `POST /api/manuscript/generate` - 논문 섹션 생성
- `GET /health` - 상태 확인

**장점**:
- ✅ 웹 인터페이스 제공
- ✅ REST API로 통합 가능
- ✅ 자동화 및 배치 처리 지원
- ✅ 안정적이고 테스트된 코드

---

## 💡 작동 예제 (`/examples`)

**목적**: 각 모듈의 실제 사용 예제

**예제들**:
1. `01_statistics_example.py` - 의료 통계 사용법
2. `02_data_management_example.py` - 데이터 정제 및 데이터베이스
3. `03_novelty_detection_example.py` - 연구 참신성 분석

**사용 방법**:
```bash
# 예제 실행
python examples/01_statistics_example.py
```

---

## 🔄 워크플로우

### 학습 및 실험 시:
```
1. 학습 영역 열기
2. Jupyter Lab 시작
3. 노트북에서 대화형 작업
4. 새로운 아이디어 테스트
5. 결과 시각화
```

### 프로덕션 사용 시:
```
1. 앱 영역 열기
2. Flask 서버 실행
3. 웹 인터페이스 또는 API 사용
4. 자동화 및 배치 처리
```

### 예제 학습 시:
```
1. 예제 폴더 열기
2. 해당 예제 실행
3. 코드 패턴 학습
4. 자신의 코드에 적용
```

---

## 📚 핵심 라이브러리 모듈

모두 `/src/` 디렉토리에 있으며, 학습 영역과 프로덕션 영역 모두에서 사용 가능합니다.

### 통계 분석 (`statistics/`)
```python
from src.statistics import MedicalStatistics

stats = MedicalStatistics()
# t-검정, ANOVA, 카이제곱, 만-휘트니 등
result = stats.t_test(group1, group2)
```

### 시각화 (`visualization/`)
```python
from src.visualization import MedicalVisualizer

visualizer = MedicalVisualizer()
fig = visualizer.box_plot(data, x="treatment", y="outcome")
```

### 데이터 관리 (`database/`)
```python
from src.database import MedicalDatabase, DataCleaner

db = MedicalDatabase("research.db")
cleaner = DataCleaner()
clean_data = cleaner.handle_missing_values(df)
```

### NLP 및 참신성 감지 (`nlp/`)
```python
from src.nlp import NoveltyDetector

detector = NoveltyDetector()
gap = detector.detect_research_gaps(existing, new_research)
```

### 논문 생성 (`papergen/`)
```python
from src.papergen import ManuscriptGenerator

gen = ManuscriptGenerator(title, authors, institution)
abstract = gen.generate_abstract(...)
```

---

## 🎯 어떤 영역을 선택할까?

### 학습 영역 사용:
- 🔬 새로운 데이터셋 탐색
- 📊 새로운 통계 방법 테스트
- 📈 시각화 및 그래프 생성
- 🧪 새로운 분석 파이프라인 프로토타이핑
- 🎓 통계 방법 학습 및 이해

### 프로덕션 영역 사용:
- 🌐 웹 인터페이스 필요
- 🔌 REST API 통합
- 🤖 자동화 및 배치 처리
- 📦 다른 애플리케이션과 연동
- 🚀 배포 및 프로덕션 실행

---

## 🚀 빠른 시작

### 설치
```bash
pip install -r requirements.txt
```

### 학습 시작 (노트북)
```bash
jupyter lab --notebook-dir=learning/notebooks
```

### 애플리케이션 시작 (프로덕션)
```bash
cd app
python main.py
```

### 예제 실행
```bash
python examples/01_statistics_example.py
```

---

## � 상세 문서 & 가이드

### 🎯 시작하기 (선택)

| 문서 | 대상 | 내용 |
|------|------|------|
| **[📖 LEARNING_GUIDE.md](docs/LEARNING_GUIDE.md)** | 모든 사용자 | 3단계 학습 경로, Reference Library 완벽 가이드 |
| **[💻 VSCODE_WORKFLOW.md](docs/VSCODE_WORKFLOW.md)** | 개발자 | 창 분리 워크플로우, 일일 작업 예제 |
| **[🚀 QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** | 빠른 참조 | 메서드별 사용법, 5분 시작 가이드 |

### 📐 기술 문서

| 문서 | 내용 |
|------|------|
| **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** | 시스템 아키텍처, 데이터 플로우, 배포 전략 |
| **[PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** | 폴더 구조, 각 영역 설명, 파일 조직 |

---

## 🚀 5분 빠른 시작

### 1️⃣ Jupyter에서 학습 (권장)
```bash
jupyter lab --notebook-dir=learning/notebooks
```
그 후 브라우저에서 `01_data_exploration.ipynb` 열기

### 2️⃣ 예제 실행
```bash
python examples/01_statistics_example.py
```

### 3️⃣ 웹 서버 시작
```bash
cd app
python main.py
# http://localhost:5000 접속
```

---

## 📚 Reference Library 한눈에

### 🎓 학습 영역 (`/learning`)
**여기서 배웁니다:**
- `/notebooks/01_data_exploration.ipynb` - 기초 (데이터 탐색)
- `/notebooks/02_statistical_analysis.ipynb` - 중급 (통계 검정)
- `/notebooks/03_visualization.ipynb` - 시각화 (그래프)
- `/notebooks/04_manuscript_generation.ipynb` - 논문 작성

**방법:**
```bash
jupyter lab --notebook-dir=learning/notebooks
# 셀을 하나씩 실행하면서 학습
```

### 💡 예제 영역 (`/examples`)
**여기서 참고합니다:**
- `01_statistics_example.py` - 기본 통계 사용법
- `02_data_management_example.py` - 데이터 관리
- `03_novelty_detection_example.py` - 참신성 분석

**방법:**
```bash
python examples/01_statistics_example.py
# 코드를 분석하고 자신의 노트북에서 응용
```

### 📦 Reference Library (`/src/statistics`)
**가져갈 수 있는 것들:**

```python
from src.statistics import (
    MedicalStatistics,      # t-test, ANOVA, 회귀분석 등
    SurvivalAnalysis,       # Kaplan-Meier, Cox 모델
    CategoricalAnalysis,    # 카이제곱, McNemar
    MultipleComparison      # Bonferroni, FDR 보정
)

# 기본 사용법
stats = MedicalStatistics()
result = stats.t_test(group1, group2)
print(f"p-value: {result['p_value']}")
```

**모든 메서드:**
- 기술통계: `descriptive_stats()`, `grouped_descriptive()`
- 비교검정: `t_test()`, `anova()`, `mann_whitney_u()`, `chi_square()`
- 상관분석: `correlation()`, `correlation_matrix()`
- 회귀분석: `regression_analysis()`, `logistic_regression()`
- 생존분석: `kaplan_meier()`, `cox_regression()`, `log_rank_test()`
- 기타: `handle_missing_values()`, `detect_normality()`

### 🚀 프로덕션 영역 (`/app`)
**여기서 배포합니다:**
- `/app/main.py` - Flask 웹 서버
- `/app/api/` - REST API 엔드포인트
- `/app/config/settings.py` - 설정 관리

**시작:**
```bash
cd app && python main.py
```

---

## 🎯 어디서 뭘 할까?

### "t-test 배우고 싶어"
```
1. /docs/QUICK_REFERENCE.md 에서 t_test 찾기
2. /src/statistics/medical_stats.py 에서 정의 읽기
3. /examples/01_statistics_example.py 에서 예제 실행
4. /learning/notebooks/02_*.ipynb 에서 실습
```

### "내 데이터 분석하고 싶어"
```
1. /learning/notebooks/05_my_analysis.ipynb 생성
2. /src/statistics/medical_stats.py 참고하면서 작성
3. Reference Library 메서드 사용
4. 완성 후 /app/main.py 에서 API로 배포
```

### "새로운 분석 방법 개발하고 싶어"
```
1. /docs/LEARNING_GUIDE.md 에서 3단계 학습 따르기
2. /examples/ 에서 유사 예제 찾기
3. 자신의 노트북에서 구현
4. 완성 후 라이브러리에 추가 고려
```

---

## 📍 창 분리 작업 (추천)

**좌측(Reference) vs 우측(실습):**

```bash
# VS Code에서
Ctrl+\ (또는 Cmd+\)  # 창 분리

좌측:  /src/statistics/medical_stats.py
우측:  /learning/notebooks/02_statistical_analysis.ipynb
하단:  Terminal
```

자세한 내용은 [💻 VSCODE_WORKFLOW.md](docs/VSCODE_WORKFLOW.md) 참조

---

## ✅ 다음 단계

- [ ] [📖 LEARNING_GUIDE.md](docs/LEARNING_GUIDE.md) 읽기
- [ ] Jupyter Lab에서 첫 번째 노트북 실행
- [ ] `/examples/` 의 예제 코드 실행
- [ ] 자신의 데이터로 분석 시도
- [ ] REST API를 통한 자동화 구축
- [ ] 프로덕션 배포

---

## 📞 주요 경로 맵

```
🎓 학습 중심          💡 참고 중심           🚀 프로덕션 중심
├─ /learning/         ├─ /examples/          ├─ /app/
├─ notebooks/         ├─ *_example.py        ├─ main.py
├─ Jupyter Lab        ├─ 실행 가능한 코드    └─ REST API
└─ 대화형 학습        └─ 패턴 참고           

📚 문서 가이드
├─ LEARNING_GUIDE.md (상세 학습 경로)
├─ VSCODE_WORKFLOW.md (개발 환경 설정)
├─ QUICK_REFERENCE.md (메서드 빠른 참조)
└─ ARCHITECTURE.md (기술 설계)
```

---

## 📋 체크리스트

### 프로젝트 설정
- [x] 학습/프로덕션 영역 분리
- [x] 핵심 라이브러리 모듈 생성
- [x] Jupyter 노트북 생성
- [x] Flask 애플리케이션 생성
- [x] 예제 코드 작성
- [x] 상세 문서 작성
- [x] Learning Guide 작성
- [ ] 의존성 설치
- [ ] 애플리케이션 테스트

---

## 📚 모든 가이드 목록

1. **[📖 LEARNING_GUIDE.md](docs/LEARNING_GUIDE.md)** - ⭐ 가장 먼저 읽기
   - 3단계 학습 경로 (기초→중급→고급)
   - Reference Library 완벽 가이드
   - 실제 시나리오별 워크플로우

2. **[💻 VSCODE_WORKFLOW.md](docs/VSCODE_WORKFLOW.md)** - ⭐ 개발자 필독
   - VS Code 창 분리 레이아웃
   - 일일 작업 패턴
   - 단축키 및 팁

3. **[🚀 QUICK_REFERENCE.md](docs/QUICK_REFERENCE.md)** - ⭐ 빠른 참조
   - 메서드별 사용법
   - 상황별 검색 맵
   - 5분 시작 가이드

4. **[ARCHITECTURE.md](docs/ARCHITECTURE.md)** - 기술 설계서
   - 시스템 아키텍처
   - 데이터 플로우
   - 배포 전략

5. **[PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md)** - 구조 설명서
   - 폴더별 역할
   - 파일 조직
   - 사용 권장사항
