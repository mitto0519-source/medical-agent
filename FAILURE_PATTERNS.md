# Failure Patterns — 자주 반복되는 실수와 예방책

> 이 파일은 매 사용자 입력 직전 hook으로 prepend됨. 짧게 유지.

## P-1 부재 단정 (most common, 2026-06-01 격노 트리거)
**증상**: "X가 없다 / 구현 안 됐다 / 자산이 빈약하다" 단정 보고
**원인**: 단일 경로만 확인 (예: `data/pmc_papers`만 보고 `data/oa_papers` 못 찾음)
**예방**: 의심스러운 부재 진단 직전 — `Get-ChildItem data/` + `MEMORY.md` grep + `ARCHITECTURE.md` grep 의무

## P-2 텍스트 비전 (사용자 절대 금지)
**증상**: "그러면 ~할 수 있을 것 같습니다" / 카탈로그 / 계획 작성하고 끝
**원인**: 실코드 적용/반영 검증 안 함
**예방**: 모든 답변은 실 파일 수정 + 실 실행 + 차분 측정(before/after)로 끝나야 함

## P-3 거짓 완료 보고
**증상**: "100% 일치" "완벽 검증" "PASS" 같은 절대 표현
**원인**: 실제 측정 안 함 / 부분 측정으로 전체 단정
**예방**: 측정 수치 표 + 통과/실패 비율 + tolerance 명시. 한 항목이라도 fail이면 fail.

## P-4 dead code 생성
**증상**: 새 모듈 작성 후 호출처 0건
**원인**: `audit_wiring.py` 안 돌림
**예방**: 새 함수/클래스 add 후 의무 실행. callers=0이면 wire-up이 부족한 것.

## P-5 메모리 망각
**증상**: 이전 대화에서 명시된 사실을 그 세션 내에서도 잊어버림
**원인**: Claude stateless + giant context 자동 압축이 중요도 판단 실패
**예방**:
- pre-prompt hook (`.claude/hooks/preprompt_memory_inject.ps1`)로 매 입력 직전 핵심만 prepend
- CORE_MEMORY.md / CURRENT_STATE.json 짧고 구조화된 파일로 통합
- 긴 README는 참고용, 실 주입은 SHORT만

## P-6 시드 자산 회로 단절
**증상**: 12,301편 본문 + 20,894 chunks가 인덱싱돼 있는데 paper_writer가 retrieve 0
**원인**: `rag_pipeline=None` 기본값으로 호출자가 안 넘기면 회로 안 살아남
**예방**: `__init__`에서 자동 attach (FIX 10 적용 완료). 새 자산 만들 때도 자동 attach 패턴 따를 것.

## P-7 max_tokens 미지정
**증상**: Methods 862자 같은 비정상 짧은 출력
**원인**: `client.generate(prompt)` 호출 시 max_tokens 안 줌 → 기본 2048 토큰에서 잘림
**예방**: 모든 LLM 호출에 max_tokens 명시. 섹션별 차등 (Abstract 1800 / Methods 5500 등)

## P-8 OneDrive 환경 함정
**증상**: 갑자기 `.venv`/소스 증발 / "전부 에러"
**원인**: OneDrive sync가 unloaded files 처리
**예방**: 시작 시 import smoke check + 근본 해결은 Docker (`docker compose up -d`)

## P-9 PowerShell + Korean output
**증상**: 한국어 출력 mojibake (cp949 ↔ UTF-8 round-trip)
**원인**: PowerShell stdout 기본 인코딩
**예방**:
```powershell
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
```
ASCII 영문 hook이 가장 안전.

## P-10 anti-meta 룰 vs 본문 보존 충돌
**증상**: `_strip_llm_meta`가 본문 첫 단락을 통째로 삭제
**원인**: 키워드 매칭이 본문 중간 정상 표현까지 잡음
**예방**: 키워드는 "단락 시작 prefix 30자"로만 좁히기. 반복 횟수 5→2로 축소.
