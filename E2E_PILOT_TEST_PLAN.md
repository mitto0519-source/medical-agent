# E2E_PILOT_TEST_PLAN — 실브라우저 사용자 여정 검증 + 픽스 루프

> 목적: "임포트 PASS"가 아니라 **실제 UX에서 뇌가 작동하는가**를 검증. 파일럿 가능 레벨 도달 판정.
> 도구: 기존 `scripts/ui_eval.py`(Playwright) 확장 + `e2e_functions.py`(서비스 CLI) + `prove_stata_e2e.py`(통계) + provenance/events.db(무엇이 실제 실행됐나).
> ★ 나(외부)는 라이브 실행 불가 — **전부 사용자 머신에서**. 이 문서는 그 실행 대본.

---

## 0. ★ E2E 전에 차단블로커 3개부터 (안 그러면 빈 뇌를 테스트함)

| 블로커 | 확인 | 안 됐으면 |
|---|---|---|
| RAG 코퍼스 빔 | `ingest_full.log` 완료 + 768d 컬렉션 count ≫ 782 | 전체 인제스트 끝까지(검색이 비면 모든 작성 여정이 가짜) |
| 채팅 경로 이중 | ez_home 10 미연결 심볼 정리(service 단일 위임) | 함수단위 추출 마저(여정이 옛/새 경로 섞여 비결정적) |
| 데이터 매핑 | `register_dataset.py kyrbs/knhanes --dry-run` PASS | 통계 여정이 변수 못 찾음 |

→ 셋 green 전엔 §2 여정 결과가 무의미. 먼저 닫아라.

---

## 1. 픽스 루프 — 층별 이분(이 시스템은 층이 많아 무작정 고치면 시간 폭발)

여정 실패 시 **위→아래로 한 층씩** 책임 소재 격리:
```
① UI 층      ui_eval 스크린샷 + stException 카운트 → 화면이 깨졌나, 로직이 안 왔나
② 서비스 층  python -c "from src.service.X import f; f(...)"  (st 없이 직접 호출) → 입출력 맞나
③ LLM/툴 층  provenance/events.db 조회 → 어떤 model/prompt/dataset로 실제 실행됐나
④ 데이터 층  data/logs/app.log + register dry-run → .sav/청크/변수 실재하나
```
원칙: **②에서 재현되면 UI 문제 아님**(서비스 버그). ②는 되는데 ①이 깨지면 위임/렌더 문제. 항상 가장 아래 재현 지점부터 고친다(규칙7).

---

## 2. 파일럿 사용자 여정 매트릭스 (= 파일럿의 정의)

각 여정 = ui_eval task. 각: **단계 → 기대 산출 → assertion → 흔한 실패 → 픽스 위치**. 전부 green = 뇌 임베드 + 파일럿 가능.

| # | 여정 | 핵심 assertion | 흔한 실패 | 픽스 위치 |
|---|---|---|---|---|
| J1 | 로그인→새 프로젝트→대화 시작 | stException=0, 응답 토큰 스트림 옴 | 키 없음/페르소나 미주입 | get_llm_client, build_base_system |
| J2 | "X 주제 탐색" | RAG 근거 인용 + 주제 카드 | 검색 빔(코퍼스), rerank 우회 | service/rag.retrieve, 인제스트 |
| J3 | "Intro 써줘" | **우측 프리뷰**에 섹션 채워짐 | preview 패치 안 옴 | patch_preview, build_system_with_preview |
| J4 | "KYRBS 2023 우울~ZCB 로지스틱" | **표** 생성 + survey-weighted 경고/적용 | 변수 못 찾음 / naive SE | service/data.load_dataset, survey_weighted |
| J5 | "forest plot 그려줘" | 피겨 PNG 첨부, 캡션 | 그림 빈/폰트깨짐 | service/figures, publication_figure_generator |
| J6 | "레퍼런스 찾아 넣어/빼" | refs 삽입→인용번호 재계산, 제거 반영 | 인용 안 박힘 | service/references, citation_workflow |
| J7 | 내 논문 업로드→문체 적용 | 이후 문장이 본인 문체 | StyleProfiler 미로딩 | prompt_loader owner_email, style_profiler |
| J8 | "전체 IMRaD 작성" | 섹션 전부 + 표/그림/refs 연결 | 일부 섹션 빔/타임아웃 | paper_writer, cost_optimizer |
| J9 | **Export** | `paper.docx`+`references.enl` 다운, Word서 열림 | enl 누락/서식깨짐 | service/export.to_docx_bundle, journal_docx |
| J10 | 새 세션 재진입 | 대화+프로젝트 복원 | 영속 손실 | conversation_memory, FIX-5 persist |
| J11 | 신뢰성 표면 | provenance 기록 + confidence 표시 + 가짜 인용 차단 | 배선 안 됨 | provenance.auto_record, claim_evidence_nli |

> J1~J10 = 기능 파일럿. J11 = 신뢰 파일럿(의료라 필수). **J4·J9·J11이 가장 잘 깨지고 가장 중요**(통계 정확성·산출물·환각).

---

## 3. 실행 방법

```bash
# 1) 앱 띄우고 실브라우저 회귀 (기존 하네스 확장)
docker compose up -d && python scripts/ui_eval.py        # J1~J10 assertion PASS/FAIL 리포트 + 스크린샷
# 2) 서비스 직접(② 층) — UI 빼고 로직만
python scripts/e2e_functions.py                          # service.* 직접 호출 검증
# 3) 통계 진짜 도나(J4)
python scripts/prove_stata_e2e.py                        # 실 KYRBS→표/그림
# 4) 무엇이 실제 실행됐나(③ 층)
python -c "from src.runtime.events import find; [print(e) for e in find(type='provenance', limit=5)]"
# 5) 산출물 수동 확인(자동화 어려움)
#    paper.docx Word서 열기, 표 three-line/그림 300dpi/refs EndNote import 되는지 눈으로
```
> ui_eval에 J4~J11 task를 추가하는 게 이번 작업의 핵심(현재 J1~J3 수준만 커버). 각 task에 graders(assertion) 명시.

---

## 4. 파일럿 합격 기준 (exit criteria)

```
[기능]  J1~J10 ui_eval PASS + 산출물 수동확인(docx/enl/figure) OK
[정확]  J4 survey-weighted 적용 또는 명시 경고 + prove_stata_e2e PASS
[신뢰]  J11: provenance 100% 기록 · confidence 표시 · 가짜 PMID 차단 1건 이상 실증
[영속]  J10 재세션 복원 (로컬+클라우드 양쪽)
[안정]  전 여정 stException=0, P95 응답<지정초, 비용/토큰 cost_optimizer로 상한
```
이 5개 green = **"내가 잘 활용할 뇌가 임베드된, 파일럿 가능 레벨"**. 하나라도 red면 §1 루프로 그 층만 고친다.

---

## 5. 지금 당장 할 일 순서
```
① 블로커 3개(§0) 닫기  ──→  ② ui_eval에 J4~J11 task 추가  ──→  ③ 전 여정 실행·리포트
   └ 실패는 §1 층별 이분으로 그 층만 픽스 → 재실행. green 될 때까지 반복.
```
> 한 번에 다 고치려 하지 마라. **여정 하나씩 green** 만들고 다음. J1→J11 순.
