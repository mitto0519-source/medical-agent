---
name: verify-medical
description: Medical-Agent 코드 변경 후 표준 검증 루틴. import check → smoke test 13/13 → Phase A/B/C 검증 → ARCHITECTURE/메모리 갱신 → 커밋. 코드를 수정하고 "검증해줘"/"커밋 전 확인" 류 요청 시 사용.
---

# Medical-Agent 변경 후 검증 루틴

CLAUDE.md 규칙 5(smoke test)·10(전후방 연결 완전성)을 실행 절차로 구현한 것.
이번 세션들에서 매 변경마다 실제 반복한 패턴을 추출했다.

## 절차

### 1. 변경 모듈 import check (LLM 무관, 항상 먼저)
```
python -c "from src.<changed_module> import <Symbol>; print('OK')"
```
새 함수/클래스를 추가했으면 그 심볼까지 명시적으로 import.

### 2. 다층 검증 (통폐합된 정규 스크립트 — 2026-05-24 정리)
> 중복 UI 검증 스크립트(verify_all_pages/verify_ui/e2e_streamlit_playwright/e2e_full_test/
> check_streamlit_http)는 ui_eval.py로 통폐합·삭제됨. 아래가 정규 검증 레이어다.

```bash
python scripts/test_rag_smoke.py     # ① import+RAG 스모크 (비UI, 절대기준)
python scripts/e2e_diagnose.py       # ② 코드 무결성 (LLM무관: import/심볼/code_graph)
python scripts/prove_stata_e2e.py    # ③ 실 통계 회귀 (실 KYRBS→표/그림, ZCB aOR)
docker compose restart medical-agent # ★ 코드 바꿨으면 필수 (Windows 마운트 inotify 미전파)
python scripts/ui_eval.py            # ④ 실 브라우저 UI 회귀 49 assertions (가장 빡셈)
```
- ui_eval = **canonical UI 회귀**(graded: 페이지 렌더 + 채팅→섹션 outcome + 저장→복원). 거짓양성 없음.
- ④ 전에 **반드시 `docker compose restart`** — 안 하면 옛 스크립트가 돌아 헛검증(메모리 feedback-docker-windows-reload).

### 3. (선택) 비브라우저 LLM 전기능 / Phase 배선
```
python scripts/headless_ai_test.py    # 비브라우저 전기능 LLM 회귀 (12~15분)
python scripts/verify_phase_abc.py    # Phase A/B/C 고아배선 3/3
```

### 4. 완전성 점검 (규칙 10)
- 새 모듈이면 `ARCHITECTURE.md` 모듈 맵에 등록했는가
- 신규 함수가 실제로 호출되는가 (고아 코드 금지 — grep으로 역참조)
- 중복 구현 없는가

### 5. 장기기억 갱신
- `change_log.log()` 기록
- 중요 결정이면 `~/.claude/projects/.../memory/`에 메모리 파일 + MEMORY.md 인덱스 한 줄

### 6. 커밋
- 변경 파일만 명시적으로 `git add` (런타임 부산물 self_model/chromadb/audit_log 제외)
- 커밋 메시지 끝에 `Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>`

## 크레딧/쿼터 소진 시
이제 **무료 Gemini 자동 폴백 + 모델 순환**이 있어 Claude 크레딧 0이어도 LLM 경로가 대부분 동작한다
(Claude→OpenAI→Gemini, Gemini 무료 모델 4종 순환). 단:
- 세 provider 무료분까지 전부 429면 ui_eval의 chat_write가 실패할 수 있다 → 잠시 후(분당한도 리셋) 재시도.
- LLM-무관 레이어(① test_rag_smoke ② e2e_diagnose ③ prove_stata_e2e)는 쿼터와 무관하게 항상 검증 가능.
- 거짓으로 "통과"라고 보고하지 않는다(규칙 11). 실제 실행 결과만 보고.