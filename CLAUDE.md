# Medical-Agent — Claude 작업 표준 규칙

> 매 세션 시작 시 자동 로드. 이 규칙들은 모든 작업에 예외 없이 적용된다.

## 세션 시작 루틴 (매번 실행)

### 0. 환경 무결성 체크 (★최우선 — 코드보다 환경부터)
> 이 프로젝트는 **OneDrive 안**에 있어 `.venv` 패키지가 증발/소스가 되돌려진다.
> "전부 에러"의 단일 루트원인이 환경인 경우가 많다. 코드 의심 전에 환경부터 확인한다.

```bash
python -c "import sys;print(sys.executable)"   # .venv 경로
python -c "
for m in ['anthropic','openai','google.generativeai','pyreadstat','streamlit','statsmodels','chromadb','docx']:
    try: __import__(m); print('OK  ',m)
    except Exception: print('MISS',m)
"
# MISS 있으면 즉시: python -m pip install <누락>   (추측 금지, 실제 import로 확인 — 규칙7)
```
근본해결은 Docker(`docker compose up -d --build`). 자세히: 메모리 `feedback-onedrive-env-trap`, `project-docker-setup`.

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

# 4. 페르소나 로드 (항상 활성화)
from src.agent.persona import get_persona, get_system_prompt
persona = get_persona()       # 누적된 연구자 캐릭터 + 관점 로드
```

**세션 시작 즉시 확인해야 할 파일:**
- `ARCHITECTURE.md` — **모듈 정의 레지스트리 (새 모듈 만들기 전 반드시 확인)**
- `data/agent_self/self_model.json` — 현재 건강도 + 우선 작업
- `data/agent_self/insights.json` — 축적된 자체 학습 내용
- `data/change_log/history.json` — 최근 작업 이력

---

## 프로젝트 목적 — "바이브 논문" 코파일럿 (★최상위 원칙)

> **이 시스템은 AI가 알아서 논문을 찍어내는 도구가 아니다.**
> 바이브 코딩처럼, **사람이 의학 논문을 써내려가는 흐름을 AI가 실시간으로 거드는 "바이브 논문" 도구**다.
> 사람이 주도하고, AI는 옆에서 매끄럽게 보조하며, 사람은 결과를 보며 다듬는다.

핵심 원칙 (모든 기능 설계·UX 판단의 기준):
1. **주인공은 사람.** AI 자동 생성(run_full, deep_research 등)은 메인이 아니라 "초안 시드" 보조다.
2. **최적화 기준 = 자동화 수준이 아니라, 사람이 얼마나 편하고 간단하게 더 좋은 논문을 쓰는가.**
3. **메인 = 논문 작업실** (사람이 직접 쓰고 AI가 섹션/문장 단위로 거든다 + 우측 실시간 프리뷰).
   자동 파이프라인 / 통계 / 신규성 / 동료심사 / 그림 = "필요할 때 편하게 지원하는 옵션".
4. 새 기능을 만들 때 자문: "이게 사람이 직접 쓰는 흐름을 더 매끄럽게 하는가? 아니면 AI가 대신하게 하는가?"
   → 후자라면 메인이 아니라 옵션으로 둔다.

데이터 기반: KYRBS/KNHANES 공중보건 연구 (주제 탐색 → 신규성 확인 → 통계 → 작성 보조).
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

### 규칙 5 — 모든 변경 후 다층 검증한다 (CLI 통과 ≠ 앱에서 동작)

```bash
python scripts/test_rag_smoke.py        # ① 임포트+RAG 스모크 (절대기준)
python scripts/e2e_diagnose.py          # ② 코드 무결성 (LLM무관)
python scripts/prove_stata_e2e.py       # ③ 통계엔진 회귀 (실 KYRBS→표/그림)
docker compose up -d && python scripts/ui_eval.py   # ④ 실브라우저 UI 회귀(45 assertions)
```

**smoke 절대기준은 깨지면 즉시 복구. UI/LLM 변경은 반드시 ④로 실앱 검증.**

> ★교훈(2026-05-24): LLM/외부의존 기능은 **CLI 테스트만으로 "된다" 보고 금지**.
> Gemini가 CLI(PONG)는 통과하나 Streamlit 스레드(닫힌 stderr)에서 init 실패해 채팅이 죽었던 사례.
> `scripts/ui_eval.py`(Playwright)로 실앱에서 outcome(채팅→섹션 반영, 저장→복원)까지 확인 후 보고.

추가 검증:
- 새 모듈: `python -c "from src.xxx import Xxx; print('OK')"`
- Supabase: cloud_available() 확인
- 환경 의심 시: [[feedback-onedrive-env-trap]] import 체크 먼저

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

### 규칙 9 — 페르소나는 항상 활성 상태다 (절대 비활성화 금지)

이 시스템은 단순 논문 도구가 아니다.
**의학박사 수준의 연구자 캐릭터**가 모든 LLM 호출에 항상 주입된다.

```
# 페르소나 파일들 (절대 삭제 금지)
data/agent_self/persona.json          — 살아있는 캐릭터 문서 (매 연구마다 진화)
data/agent_self/conversation_memory.json — 세션 간 대화 맥락

# 페르소나가 자동 주입되는 곳
src/llm/claude_client.py _build_system() — 모든 LLM 호출
app/ai_panel.py                          — Streamlit AI 패널
src/research/research_pipeline.py        — 주제 생성 후 자동 진화

# 주입 내용
- 연구자적 특성 (학구적 호기심, 비판적 고찰, 공중보건 시각)
- 언어 스타일 (연구실 동료와의 자연스러운 학문적 대화체)
- 누적된 연구 관점 (매 파이프라인 실행 후 자동 갱신)
- 세션 간 대화 맥락 (연속성 유지)
```

페르소나 진화 원칙:
- 연구 파이프라인 실행 시 `persona.evolve_from_research()` 자동 호출
- 사용자 피드백이 긍정적일 때 `evolve_from_conversation()` 자동 호출
- `data/agent_self/persona.json`의 `accumulated_perspectives`는 누적만 되고 리셋 없음
- 세션 시작 시 반드시 `get_persona()`로 현재 페르소나 상태 확인

---

### 규칙 10 — 모든 작업은 전후방 연결 완전성을 보장한다 (절대 규칙)

> **새 모듈 생성 전 의무**: `ARCHITECTURE.md`를 먼저 읽고 같은 기능이 이미 있는지 확인한다.
> 없으면 만들되 ARCHITECTURE.md에 즉시 기재한다.
> 기존 모듈을 대체하면 기존 것을 삭제하고 ARCHITECTURE.md 삭제 기록표에 남긴다.

작업 단위가 아무리 작아도, **항상 다음 체크리스트를 수행한다.**
"요청한 것만 하고 끝" 은 절대 허용되지 않는다.

#### 10-1. 작업 시작 전 — 연결 지도 그리기
```
① 이 작업의 INPUT은 무엇인가? (누가 이것을 호출/생성하는가)
② 이 작업의 OUTPUT은 무엇인가? (이것이 어디에 주입/사용되는가)
③ 동일 기능이 다른 곳에 이미 구현되어 있지 않은가? (중복 탐지)
④ 이 변경으로 영향받는 downstream 모듈은 무엇인가?
```

#### 10-2. 작업 중 — 연관된 것을 전부 같이 개발한다
```
- 새 함수/클래스 → 호출부, import, 타입 힌트, 로깅까지 같이
- 새 모듈 → __init__.py export, 설정 파일 반영, smoke test 항목 추가까지
- 데이터 변경 → 읽는 쪽, 쓰는 쪽, 마이그레이션까지
- API 변경 → 호출부 전수 수정, 하위 호환 제거까지
- Config 변경 → 영향받는 모든 모듈 확인 및 반영
```

#### 10-3. 작업 후 — 완전성 검증
```
① smoke test 12/12 PASS 확인 (필수)
② 새로 만든 것이 실제로 호출되는지 end-to-end 추적
③ 기존 코드와 중복 구현이 생겼다면 → 즉시 통합 또는 기존 것 제거
④ 사용되지 않는 dead code가 생겼다면 → 즉시 삭제
⑤ change_log.log() 기록
```

#### 10-4. 스크리닝 체크리스트 (작업 완료 전 반드시)
| 확인 항목 | 방법 |
|-----------|------|
| 중복 구현 없는가 | `Grep`으로 동일 기능 키워드 검색 |
| import 깨진 것 없는가 | `python -c "from src.xxx import ..."` |
| 호출부 누락 없는가 | 신규 함수명으로 역참조 검색 |
| 테스트 커버 됐는가 | smoke test 또는 단위 테스트 실행 |
| 연결 안 된 고아 코드 없는가 | `git diff`로 추가된 코드 전체 검토 |

> **이 규칙은 요청의 크기와 무관하다.**
> 한 줄 수정도, 새 모듈 추가도, 모두 동일하게 적용한다.
> "일단 되는지 보자"는 없다. 만들면 완성이다.

---

### 규칙 11 — 거짓말하지 않는다 (절대 규칙, 예외 없음)

#### 금지 행위
- **한 척**: 구현 안 했으면서 "완료됐습니다" 보고
- **껍데기 구현**: `pass`, 하드코딩 더미값, `return None` 으로 채워놓고 "동작합니다" 주장
- **환각**: 존재하지 않는 함수·파일·변수를 있다고 언급
- **과장**: 부분 구현을 전체 구현인 것처럼 표현
- **회피**: 안 되는 이유를 숨기고 얼버무리기

#### 의무 행위
```
완전 구현 불가능한 경우:
  → 왜 안 되는지 정확히 설명 (기술적 한계 / 외부 의존성 / 시간·비용)
  → 지금 가능한 것과 불가능한 것을 명확히 구분
  → 가능한 해결책 또는 대안 제시

구현이 부분적인 경우:
  → "X는 됩니다, Y는 아직 안 됩니다" 명시
  → 미완성 부분의 TODO를 코드에 남기고 사용자에게 고지

테스트 안 한 경우:
  → "테스트하지 않았습니다" 명시, "아마 될 것"이라고 하지 않음
  → 반드시 실제 실행으로 확인 후 보고
```

#### 판단 기준
> "이 코드가 사용자가 의도한 기능을 실제로 수행하는가?"
> Yes → 완료. No 또는 불확실 → 미완료로 보고, 이유 설명.

껍데기 로직을 그럴듯하게 포장하는 것은 실제 버그보다 더 나쁘다.
발견하기 어려운 거짓이기 때문이다.

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

### LLM 호출 — 반드시 get_llm_client(with_failover) 경유

```python
# 금지 (직접 client 생성 → 크레딧0이면 그냥 죽음, 무료 폴백 안 됨, 페르소나 누락)
from src.llm.claude_client import ClaudeClient; ClaudeClient(...).generate(...)

# 정석 (Claude→OpenAI→무료 Gemini 자동 연쇄폴백 + 페르소나/seed 일관 주입)
from src.llm import get_llm_client
client = get_llm_client(task="qa")            # provider 미지정 = 무료우선 자동선택
answer = client.generate(prompt, system_prompt=sys, max_tokens=2048)
```
> 새 LLM 경로를 만들면 **반드시 이 경로로** 통합한다(규칙10 전수적용). 직접 client 생성·
> 특정 모델 직접호출(예: gemini-1.5-pro)은 폴백/페르소나를 우회하는 죽은 경로다.
> **"폴백 된다/된다"는 실제 generate 호출(라이브)로 확인한 뒤에만 보고**한다(규칙11).

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
