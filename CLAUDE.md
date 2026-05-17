# Medical-Agent — Claude 작업 표준 규칙

> 매 세션 시작 시 자동 로드. 이 규칙들은 모든 작업에 예외 없이 적용된다.

## 세션 시작 루틴 (매번 실행)

```python
# 1. 장기기억 읽기
from src.memory.change_log import build_context_summary
from src.memory.agent_insight import build_self_context, get_next_actions
from src.memory.self_model import get_model, surface_next_action

# 2. 프로젝트 현재 상태 파악
model = get_model()           # 건강도 점수, 약점, 우선순위
next = surface_next_action()  # 가장 먼저 할 일

# 3. 필요시 자가 진단 갱신
from src.memory.self_model import refresh
model = refresh()             # git 상태 + 모듈 체크 + 점수 재계산
```

**세션 시작 즉시 확인해야 할 파일:**
- `data/agent_self/self_model.json` — 현재 건강도 + 우선 작업
- `data/agent_self/insights.json` — 축적된 자체 학습 내용
- `data/change_log/history.json` — 최근 작업 이력

---

## 프로젝트 목적

조유선 스타일 의학 논문 자동 생산 파이프라인.
KYRBS/KNHANES 데이터 기반 공중보건 연구 → 주제 생성 → 신규성 확인 → 논문 작성.
사용자: mitto0519@gmail.com (super_admin), misslonghorn46@gmail.com

---

## 핵심 아키텍처

```
src/config/     — 중앙 설정 (models.py, env.py, logging_config.py)
src/llm/        — LLM 클라이언트 (Claude/OpenAI, 모델 자동 선택)
src/memory/     — 장기기억 (change_log.py, continuity.py)
src/agent/      — MedicalAgent (RAG + 기억)
src/research/   — 논문 파이프라인 (pipeline, workflow, writer)
src/rag/        — ChromaDB RAG
src/vectordb/   — 벡터 스토어 (local/Supabase)
src/auth/       — 사용자 인증
src/cloud/      — Supabase 연결
app/            — Streamlit UI + AI 패널
mcp_server.py   — Claude Desktop MCP 서버
```

---

## 8가지 작업 표준 규칙

### 규칙 1 — 먼저 탐색하고, 그 다음 코딩한다

작업 시작 전에 반드시 관련 코드를 먼저 파악한다.
바로 편집기부터 열지 않는다.

```
# 새 기능 추가 전
→ Grep/Read로 관련 파일 확인
→ Explore 에이전트로 패턴 파악
→ 그 다음 계획 수립, 그 다음 코딩
```

적용 범위: 낯선 파일, 연쇄 영향이 예상되는 변경, 처음 건드리는 모듈

---

### 규칙 2 — "무엇"이 아니라 "왜"를 git으로 확인한다

코드가 이상해 보여도 바로 고치지 말고, 먼저 의도를 확인한다.

```bash
git log --oneline -20          # 최근 변경 흐름
git show <commit>              # 특정 커밋 전체 내용
git log -p -- <파일경로>        # 파일별 변경 이력
```

특히: conflict 해결, 코드 삭제, 패턴 변경 전에 반드시 확인.
이유 없이 존재하는 코드는 없다 — 이유를 먼저 찾아라.

---

### 규칙 3 — CLAUDE.md가 컨텍스트다, 매 세션 읽고 시작한다

이 파일이 자동으로 로드된다. 추가로 `data/change_log/history.json`과
메모리 파일도 세션 시작 시 확인한다.

```
C:\Users\mitto\.claude\projects\...\memory\MEMORY.md  — 인덱스
data/change_log/history.json                          — 작업 이력
```

세션 간 컨텍스트 손실은 이 두 곳을 읽으면 복구된다.
중요 결정을 내릴 때마다 memory 파일을 업데이트한다.

---

### 규칙 4 — 계획 먼저, 실행은 승인 후

비자명하거나 연쇄 영향이 있는 작업은 반드시 먼저 계획을 제시한다.

계획 필요 상황:
- 새 모듈 추가 또는 기존 모듈 구조 변경
- 여러 파일에 걸친 변경 (3개 이상)
- 데이터베이스 스키마 변경
- 기존 API 시그니처 변경

계획 형식: 변경 파일 목록 + 이유 + 영향 받는 downstream + 롤백 방법

---

### 규칙 5 — 모든 변경 후 smoke test로 검증한다

```bash
python scripts/test_rag_smoke.py
```

**12/12 PASS는 절대 기준이다. 낮아지면 즉시 복구 후 다음 작업.**

추가 검증:
- 새 모듈: `python -c "from src.xxx import Xxx; print('OK')"`
- Supabase: cloud_available() 확인
- Streamlit: 실제 UI에서 동작 확인 (가능할 때)

---

### 규칙 6 — 장기기억을 직접 읽고 업데이트한다

모든 에이전트는 과거 작업을 기억해야 한다. 기억 못하는 것은 없다.

```python
# 작업 기록 (모든 유의미한 작업 후 필수)
from src.memory import change_log
change_log.log(
    title="무엇을 했는가",
    action_type="config_change|qa|paper_write|...",
    description="상세 내용",
    why_better="왜 더 좋아졌는가",
    impact={"affected_modules": ["모듈명"]},
)

# Claude Code 메모리 업데이트 (중요 결정 후)
# → C:\Users\mitto\.claude\projects\...\memory\ 에 저장
```

이전에 결정한 사항을 번복하지 않는다.
항상 이전 작업 위에 더 개선하는 방향으로만 진행한다.

---

### 규칙 7 — 추측하지 말고 실제 데이터를 직접 확인한다

```bash
# 실제 상태 확인 명령어들
git status                               # 현재 변경사항
git log --oneline -10                    # 최근 이력
python scripts/test_rag_smoke.py         # 전체 모듈 상태
python -c "from src.cloud.db import cloud_available; print(cloud_available())"
cat data/change_log/history.json | python -m json.tool | head -50
```

오류 발생 시: 로그를 먼저 읽고, 추측으로 고치지 말고, 근거를 찾아 고친다.
`data/logs/app.log` — 표준 로그 파일.

---

### 규칙 8 — 독립적 작업은 병렬로 실행한다

서로 의존성 없는 작업은 동시에 처리한다.

```
# 병렬 처리 적합한 경우
- 여러 파일 읽기 (Read × N)
- 탐색 + 다른 탐색 (Explore × N)
- 테스트 실행 + 문서 업데이트

# 순차 처리 필수인 경우
- 파일 읽기 → 편집 (Read 후 Edit)
- 계획 수립 → 구현 → 테스트
```

---

## 코드 작성 표준

### 모델 선택 — 절대 하드코딩 금지

```python
# 금지
model = "claude-opus-4-7"

# 정석
from src.config.models import get_model
provider, model_id = get_model(task="paper_writing")
```

### 로깅 — 표준 로거만 사용

```python
# 금지
import logging; logging.getLogger(__name__)

# 정석
from src.config.logging_config import get_logger
_log = get_logger(__name__)
```

### 환경변수 — 단일 로드

```python
# 금지 (각 파일에서 load_dotenv())

# 정석 (entry point에서만)
from src.config.env import bootstrap
bootstrap()
```

### 클라우드 쓰기 — 반드시 로컬 먼저

```python
# 정석: 로컬 항상 + 클라우드 선택
_write_local(data)
if cloud_available():
    try: _write_cloud(data)
    except: _log.warning(...)
```

---

## 영향도 체크리스트

변경 전 반드시 확인:

| 변경 대상 | 영향 받는 곳 확인 |
|----------|----------------|
| `src/config/models.py` | 모든 LLM 호출부 |
| `src/cloud/db.py` | `_init_tables()` DDL, 모든 cloud write |
| `src/memory/change_log.py` | 모든 `_log()`, `record()` 호출부 |
| `src/llm/*.py` | `src/rag/pipeline.py`, `MedicalAgent` |
| `src/auth/users.py` | Streamlit 로그인, MCP auth |
| `app/streamlit_app.py` | 모든 페이지, AI 패널 |

---

## 절대 하면 안 되는 것

- smoke test 12/12 PASS 깨뜨리기
- git conflict marker 해결 없이 커밋
- 이전에 결정한 사항 이유 없이 번복
- cloud 저장 없이 local만 저장 (반대는 괜찮음)
- `except: pass` — 최소 `_log.warning()` 추가
- 테스트 없이 "아마 될 것"이라고 보고
