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

## P-11 양식/placeholder 단어 반복 출력 (2026-06-14)
**증상**: 한국어 답변에 "양식" 같은 placeholder 단어가 반복 등장
**원인**: LLM 출력 미검열 → 사용자 격노 트리거 ("양식양식 안고칠꺼냐")
**예방**: 한국어 답변 작성 후 send 전 "양식" 문자열 출현 0회 자기검열. 영어 우선 전환.

## P-12 ARCHITECTURE.md 동기화 누락 (2026-06-14 CLAUDE.md 규칙10 위반)
**증상**: 새 패키지 5개(service/reliability/evolution/analysis/data·knhanes_raw_loader) 만들고 ARCHITECTURE.md/SHORT 미갱신 → 사용자 지적 "절대규칙에 항시 동기화"
**원인**: 작업량 많아질수록 동기화 의무 잊음. 규칙10 위반.
**예방**: 새 src/ 패키지 생성 시 즉시 (1) `scripts/regenerate_architecture.py` 실행 (2) ARCHITECTURE_SHORT.md에 prose 한 줄. 작업 종료 직전 의무 체크.

## P-13 외부 라이센스 데이터 자동 다운로드 단정 (2026-06-14)
**증상**: KNHANES "신청서·본인인증 우회 가능" 단정
**원인**: KDCA 정책(승인+본인인증) 사전 확인 안 함
**예방**: 외부 데이터 자동 다운로드 시도 전 약관·인증 정책 확인. 안 되면 정직히 "수동 다운로드 + 폴더 드롭 자동 인식" 패턴으로 안내.

## P-14 STATA .dta 한국어 STRL 인코딩 가정 (2026-06-14)
**증상**: `pd.read_stata` / `pyreadstat.read_dta` 모두 UTF-8/cp949 모두 fail
**원인**: 한국 STATA 파일은 STRL 인코딩 손상이 흔함
**예방**: STATA 통합본은 메인 path로 가정 금지. 개별 .sav를 primary로 두고 .dta는 옵션.

## P-15 HF Space CONFIG_ERROR 침묵 (2026-06-15)
**증상**: GitHub push는 성공 + git push hf 성공인데도 HF Space lastModified가 4일 전 그대로, 새 코드 안 반영
**원인**: README.md에 HF Space frontmatter (title/sdk/app_port 등) 누락 → 빌드 시 CONFIG_ERROR → 옛 빌드 유지
**예방**: HF Space에 push할 때 README.md 첫줄 frontmatter 의무. HF API runtime.stage 항상 확인 (RUNNING/APP_STARTING/CONFIG_ERROR/RUNTIME_ERROR).

## P-16 HF Space default branch mismatch (2026-06-15)
**증상**: `git push hf master` 성공 표시되지만 빌드 안 됨
**원인**: HF Space default branch는 `main`. push가 master refs로 가면 활성화 안 됨.
**예방**: `git push hf master:main --force` 사용. origin은 master:master 유지.

## P-17 auto-sync git add -A 거대 데이터 오염 (2026-06-14 FIX-11)
**증상**: KNHANES raw 2.5GB가 git history에 박혀 push 영원히 reject
**원인**: scripts/auto_sync.py가 `git add -A`로 .gitignore 미존재 path까지 통째로 commit
**예방**: FIX-11 가드 — banned path/ext skip + 50MB 사이즈 가드 + whitelist add. filter-repo로 history 영구 제거 + force push.
