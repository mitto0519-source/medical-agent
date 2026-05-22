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

### 2. smoke test — 13/13 PASS가 절대 기준
```
python scripts/headless_ai_test.py
```
- **백그라운드로 실행**(약 12~15분, LLM 호출 다수). `run_in_background: true`.
- 13/13 PASS 미달이면 즉시 원인 복구 후 재실행. 낮아진 채로 다음 작업 금지.

### 3. Phase A/B/C 실경로 검증 (smoke가 안 타는 deep_research/parallel 경로)
```
python scripts/verify_phase_abc.py
```
3/3 PASS 확인. (Phase A 자율탐색은 PubMed 3라운드라 2~4분)

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

## 크레딧 소진 시 (중요)
Claude API 크레딧이 0이면 smoke test의 LLM 항목(주제생성·신규성·논문작성·동료심사·Q&A)이
`credit balance too low`로 실패한다. 이때:
- LLM 무관 부분만 단위 검증(import·규칙기반·구조 테스트)으로 대체
- **반드시 "LLM 경로 full smoke test는 불가, 구조/규칙기반만 검증함"을 보고에 명시** (규칙 11)
- 거짓으로 "13/13 통과"라고 보고하지 않는다