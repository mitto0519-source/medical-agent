# FRONTEND_MIGRATION_SPEC — Streamlit → Next.js (논문 특화 Lovable형 제품)

> 짝 문서: `REVIEW_FIX_SPEC.md`(백엔드 배관), `KNOWLEDGE_MODEL_SPEC.md`(지식모델).
> 목표 제품: **LLM과 대화하면 오른쪽 프리뷰에서 논문이 실시간으로 써지고, 통계·그림·레퍼런스가 자유롭게 붙고 빠지며,
> Word 다운로드 시 EndNote(.enl)도 함께 나오는** 사용자친화·고속 제품. UX 모태=Lovable, 기능=논문 작성 특화.
> ★ 원칙: **기능 누락 0.** 과거~최신 Streamlit에 흩어진 기능을 §2 카탈로그로 전수 보존하고 화면에 재배치한다.
> ★ 원칙: **두뇌는 재사용, 얼굴만 교체.** `src/`(메모리·RAG·지식모델·통계·export)는 그대로. `app/`(Streamlit)만 대체.

---

## 0. VS Code 호출

```
@FRONTEND_MIGRATION_SPEC.md 를 Phase 1부터 실행.
Phase 1(서비스 추출)이 끝나기 전에는 Next.js 코드를 시작하지 마라(중복 방지).
각 추출 함수는 st.*/session_state 의존을 제거하고 src/service/ 로 옮기되, 기존 Streamlit이 그 서비스를 호출하도록 바꿔
동작 동일성을 smoke+수동 1회로 확인(strangler — Streamlit 살려둠).
§2 카탈로그의 모든 행이 Next.js 또는 admin으로 매핑되기 전에는 Streamlit 은퇴 금지(누락 방지).
```

---

## 1. 목표 아키텍처 (3계층 분리)

```
src/service/*  ── 순수 로직(프레임워크 무관): chat_turn, rag, stats, figures, references, export, style, novelty
      │  └─ 기존 src/ (memory/rag/research/export/knowledge/statistics) 그대로 호출
      ├──────────────► FastAPI  (SSE 스트리밍 + REST)        ── api/
      │                     └─► Next.js (제품 얼굴)           ── web/
      └──────────────► Streamlit (개발/관리자 전용, 점진 은퇴) ── app/
```
- 스트리밍: **SSE**(서버→클라 단방향 토큰. `_stream_reply`가 이미 generator라 그대로 감쌈). WebSocket은 과함.
- 인증: Streamlit 세션 → **JWT**(src/auth/users.py 재사용, API 미들웨어로).
- 영속: **Supabase 단일화**(REVIEW FIX-5 승격) — 제품엔 HF push-back 15분 손실창 불가.

---

## 2. ★ 기능 전수 카탈로그 (누락 0 — 모든 행이 어딘가로 가야 함)

> 분류: **P**=제품(소비자 화면) · **A**=admin/개발자 전용 · **S**=서비스로만(백그라운드).
> "백킹"=실제 로직 모듈(이미 존재, 재사용).

### 2.1 채팅·작성 코어 (ez_home.py + agentic_loop)
| 기능 | 현 위치 | 백킹 | 분류 | Next.js 배치 |
|---|---|---|---|---|
| 대화→스트리밍 응답 | ez_home `_stream_reply`(788) | get_llm_client generate_streamed | P | 좌측 채팅(토큰 스트림) |
| 시스템 합성(+프리뷰/기억) | ez_home `_build_full_system`(749), agentic_loop `build_system_with_preview` | persona/recall/changelog/preview | S | (API 내부) |
| 실시간 우측 프리뷰 패치 | agentic_loop `patch_preview`(28) | docx preview snapshot | P | 우측 프리뷰 라이브 |
| IMRaD 후처리/보강 | ez_home `_post_process_imrad`(420),`_enrich_imrad`(496) | research/writer | S | (API 내부) |
| 전체 논문 트리거 | ez_home `_full_paper_prompt`(584),`_is_full_paper_trigger` | paper_writer | P | 채팅 명령/버튼 |
| Go deep / Go wide / Autopilot | ez_home `_go_deep_prompt`/`_go_wide_prompt`/`_is_autopilot_trigger` | planner | P | 채팅 모드 토글 |
| 내 논문 업로드(문체) | ez_home `_render_my_papers_uploader`(866) | StyleProfiler | P | 설정/문체 패널 |

### 2.2 채팅 툴 (agentic_loop 18종 — 대화 중 호출되는 기능)
| 툴 | 백킹 | 분류 | 비고 |
|---|---|---|---|
| `kyrbs_stat`(51) | statistics/medical_stats | P | 통계 실행→표/그림 |
| `pubmed_search`(77) | external evidence | P | 실시간 레퍼런스 찾기 |
| `rag_search`(101) | rag/pipeline(rerank+HyDE) | P | 사내 코퍼스 검색 |
| `strobe_check`(90) / `consistency_check`(96) | peer_reviewer/diagnostics | P | 검증 게이트 |
| `find_components`(113)/`cross_modal_query`(135) | library/knowledge | P | 컴포넌트·지식 |
| `apply_author_style`(151) | StyleProfiler/yoosun | P | 문체 입히기 |
| `run_plan`(166)/`dispatch_role`(184) | planner DAG/roles | P | 멀티스텝 자동 |
| `causal_check`(226)/`consensus_search`(212)/`external_evidence`(240)/`longitudinal_trend`(253) | knowledge/research | P | 근거·추론 |
| `procedural_recall`(198) | memory/procedural | S | |
| `sandbox_run`(266)/`slash_run`(279) | runtime/sandbox, slash_commands | A | 개발자 |

### 2.3 출력·내보내기 (src/export — ★EndNote 포함)
| 기능 | 백킹 | 분류 | Next.js |
|---|---|---|---|
| Word(docx) 내보내기 | `journal_docx_exporter.py` | P | Export 버튼 |
| **EndNote(.enl) 동반 출력** | `reference_library.py` | P | Word와 함께 묶음 다운로드 |
| 레퍼런스 라이브러리(추가/삭제) | `reference_library.py`,`citation_workflow.py` | P | 우측 References 패널(자유 삽입/제거) |
| 그림 생성 | `publication_figure_generator.py`,`image_gen.py` | P | 우측 Figures 패널 |
| 표 빌더 | `table_builder.py` | P | 우측 Tables |
| 저널 타겟팅/커버레터 | `journal_targeting.py`,`cover_letter_writer.py` | P | 제출 패널 |

### 2.4 클래식 모드 20화면 (streamlit_app.py — 파이프라인 단계, 대부분 채팅으로 흡수)
| 화면 | 라인 | 분류 | 처리 |
|---|---|---|---|
| 홈 | 851 | P | Next.js 랜딩/새 작업 |
| 논문 작업실(바이브 채팅) | 1085 | P | **메인 = 좌채팅+우프리뷰** |
| 글쓰기 스타일 | 1940 | P | 문체 패널(업로드+선택) |
| 작업 타임라인 | 3856 | P | 히스토리 패널 |
| 원스톱 자동 파이프라인 | 2036 | P | 채팅 "autopilot" |
| 연구 주제 생성 | 2139 | P | 채팅 핸들러 |
| 신규성 확인 | 2209 | P | 채팅 툴(causal/consensus) |
| 논문 설계 & 타당성 | 2379 | P | 채팅 핸들러 |
| 원시자료 업로드 | 2425 | P | 데이터 패널 |
| 데이터 분석 | 2625 | P | 통계 패널(kyrbs_stat) |
| 논문 작성 | 2890 | P | 프리뷰 작성 |
| 기존 논문 개선 | 3425 | P | 업로드→개선 채팅 |
| 논문 업로드 & 인제스트 | 3700 | P | 데이터/문체 패널 |
| Agent Q&A | 3614 | P | 채팅 기본 |
| 워크플로우 | 2018 | A→P | 단계 가이드(옵션 패널) |
| Notebook 에디터 | 3637 | A | 개발자 |
| 자동 학습 루프 | 3809 | A | 백그라운드/admin |
| 자가 진단 | 3936 | A | admin |
| 지식베이스 관리 | 3765 | A | admin |
| 지식 위키(누적) | 4129 | P/A | 읽기=P, 관리=A |

### 2.5 아카이브 레거시 (app/pages/_archive — 누락 점검 대상)
| 화면 | 백킹 | 분류 |
|---|---|---|
| backlog(작업큐/이벤트) | runtime/tasks,events | A |
| dashboard(메모리5층/추세/알림) | memory layers, notifier | A |
| memory_explorer | memory | A |
| workflow(단계형 주제→) | research_workflow | A→P(가이드) |

> **누락 방지 규칙**: 위 모든 행이 §3 화면 또는 admin으로 매핑되기 전엔 Streamlit 은퇴 금지. 매핑 매트릭스(§7)로 추적.

---

## 3. Next.js 제품 화면 (Lovable형 — 단일 워크스페이스)

소비자 제품은 페이지 20개가 아니라 **하나의 작업실**이다:

```
┌───────────────────────────── Workspace ─────────────────────────────┐
│ Sidebar: 프로젝트 목록 · 새 작업 · 사용자                              │
├──────────────────────────┬──────────────────────────────────────────┤
│  좌: 채팅 (스트리밍)       │  우: 라이브 논문 프리뷰 (실시간 작성)       │
│  - 자연어로 지시           │  - IMRaD 섹션이 토큰으로 채워짐             │
│  - 모드: deep/wide/auto    │  - 인라인 편집/수락·거절(diff)             │
│  - 명령: 통계/그림/레퍼     │  도킹 패널(탭): Stats · Figures · Tables · │
│                          │   References(삽입/제거) · Style · Export   │
├──────────────────────────┴──────────────────────────────────────────┤
│ 하단/우상단: Export(Word+EndNote) · 검증 게이트(STROBE/통계/인용) 배지  │
└──────────────────────────────────────────────────────────────────────┘
```
- **References 패널**: pubmed/rag 검색 결과를 카드로, **드래그 또는 +/−로 본문에 삽입/제거**(실시간 인용 갱신).
- **Stats/Figures 패널**: 채팅이 생성한 산출을 누적, 클릭하면 프리뷰 본문에 삽입.
- **Export**: 한 번에 `paper.docx` + `references.enl`(EndNote) 묶음 다운로드.
- 검증 게이트는 **막는 벽이 아니라 인라인 배지/제안**(올바른 마찰).

---

## 4. Phase 1 — 서비스 추출 (★진짜 첫 수, Next.js 아님)

`ez_home.py`/`agentic_loop.py`의 로직을 `st.*` 제거해 `src/service/`로. **함수 단위 체크리스트**(누락=중복구현 위험):

| 추출 대상(현 위치) | → 신규 서비스(순수함수) | 입력→출력 |
|---|---|---|
| `_stream_reply`(ez 788) | `src/service/chat.py: stream_turn(project, msg, owner) -> Iterator[str]` | st 제거, generator 유지 |
| `_build_full_system`(749) | `chat.build_system(project,msg,owner) -> str` | |
| `_rag_retrieve`(706) | `src/service/rag.py: retrieve(query,top_k) -> list[Hit]` | rerank/HyDE 경유 |
| `_post_process_imrad`/`_enrich_imrad` | `src/service/paper.py: postprocess/enrich(draft,ctx) -> (md,meta)` | |
| `_full_paper_prompt`/`_go_*`/`autopilot` | `src/service/paper.py: prompts...` | |
| `_generate_figure`(341) | `src/service/figures.py: generate(project,type) -> (bytes,caption)` | |
| `_hits_to_references`(396) | `src/service/references.py: from_hits / add / remove / to_endnote` | .enl 출력 |
| `_post_turn_hooks`(821) | `src/service/chat.py: post_turn(...)` | 기억/change_log |
| agentic_loop `_h_*`(18종) | `src/service/tools.py: 각 핸들러 순수화` | st 무관 |
| 데이터 로딩(.sav) | streamlit `_ensure_raw_df`(504), agentic_loop `_load_kyrbs_cached`(434) | `src/service/data.py: load_dataset(kind,years) -> DataFrame` | pyreadstat, 캐시. **통계의 입력 — 이거 없으면 stats 불가** |
| 통계 산출 | (이미 src/statistics/medical_stats) | `service/stats.py: run(df, spec) -> {results, tables, figs}` | descriptive/t/chi2/anova/회귀/로지스틱 등 전 함수 노출 |
| 피겨 | (이미 src/export/publication_figure_generator) | `service/figures.py: generate(spec) -> [(bytes,svg,caption)]` | forest/prevalence_bar/subgroup_forest/coefficient |
| 테이블 | (이미 src/export/table_builder) | `service/tables.py: build(kind, data) -> docx_table/json` | baseline/regression/cross/raw, three-line |
| export 묶음 | (이미 src/export/journal_docx_exporter+reference_library) | `service/export.py: to_docx_bundle(project) -> {docx, enl}` | 표·그림·인용 합쳐 Word+EndNote |

> **★ 계산 불변식(CLAUDE.md 규칙)**: `service/stats.py`·`figures`·`tables`는 **실엔진(statsmodels/matplotlib/python-docx)이 계산·렌더**한다. LLM은 *무엇을 돌릴지 결정 + 결과 해석*만. `/stats/run` API는 LLM이 아니라 엔진을 호출해야 함(숫자 환각 금지). 이 불변식을 Phase 1 추출·Phase 2 API에 그대로 유지.

검증: 추출 후 **Streamlit이 새 서비스를 호출**하도록 교체 → 화면 동작 동일(수동 1회 + smoke). 동일하면 Phase 2.

---

## 5. Phase 2 — FastAPI (서비스 래핑)

`api/` (현재 빈 `app/api/`를 진짜 API로):
| 엔드포인트 | 메서드 | 서비스 | 비고 |
|---|---|---|---|
| `/auth/login`,`/me` | POST/GET | src/auth | JWT |
| `/projects` CRUD | GET/POST/PATCH/DELETE | service/project | |
| `/chat` | POST (SSE) | chat.stream_turn | text/event-stream 토큰 |
| `/preview/{pid}` | GET/PATCH | preview snapshot | 우측 동기화 |
| `/rag/search` | POST | rag.retrieve | rerank |
| `/references` | GET/POST/DELETE | references | 삽입/제거 |
| `/references/export.enl` | GET | references.to_endnote | EndNote |
| `/stats/run` | POST | stats.run | 표/그림 |
| `/figures` | POST/GET | figures | |
| `/style/upload`,`/style` | POST/GET | StyleProfiler | 본인 논문→문체 |
| `/novelty`,`/strobe`,`/consistency` | POST | tools | 검증 게이트 |
| `/export/docx` | GET | export.to_docx_bundle | docx+enl zip |

원칙: API는 **얇게**. 모든 로직은 service. (규칙10 — 로직 중복 금지)

---

## 6. Phase 3 — Next.js (web/)

- 스택: **Next.js(App Router) + TypeScript + Tailwind** (sapphire_glass의 색·라운드·폰트를 Tailwind theme로 이식 → 디자인 연속성).
- 스트리밍: `EventSource`로 `/chat` SSE 구독 → 좌측 채팅 + 우측 프리뷰 동시 갱신.
- 프리뷰: 마크다운/구조화 docx 모델을 실시간 렌더, 섹션별 토큰 append, 인라인 편집(ProseMirror/TipTap 권장).
- References: 검색 결과 카드 → 삽입/제거 시 `/references` 호출 → 본문 인용 번호 자동 재계산.
- Export: `/export/docx` → `paper.docx`+`references.enl` zip 다운로드.
- 상태: 서버상태(React Query) + 프로젝트 로컬상태. (Streamlit session_state 대체)

---

## 7. Phase 4 — Strangler 은퇴 + 누락 패리티 매트릭스

각 §2 행을 **Next.js 구현 완료**로 체크하기 전엔 Streamlit 유지. 매트릭스 예:
| 기능(§2 행) | Streamlit | Next.js | 패리티? |
|---|---|---|---|
| 채팅 스트리밍 | ✓ | ☐ | |
| 우측 라이브 프리뷰 | ✓ | ☐ | |
| 통계 실행 | ✓ | ☐ | |
| 레퍼런스 삽입/제거 | ✓ | ☐ | |
| Word+EndNote 묶음 | ✓ | ☐ | |
| … (전 행) | | | |

전 행 ✓✓ 되면 streamlit_app.py(4,215)·ez_home·project_workspace **은퇴**. admin 분류는 Streamlit에 남겨 내부도구로 유지(소비자 UI 안 만듦 — 낭비 방지).

---

## 8. 의존·선후 (다른 스펙과 충돌 방지)

- **백엔드 FIX 우선**: REVIEW FIX-10(스키마 실배선)·전체 인제스트가 끝나야 RAG/레퍼런스 품질이 제품급. **Phase 1(추출)은 지금 시작 가능**(병렬), Phase 3(React) 본격화는 RAG 완주 후 체감.
- **영속**: FIX-5 HF push-back → **Supabase 단일화 승격**이 제품 전제. Phase 2와 묶기.
- **per-user**: persona/self_model 전역 → 멀티유저 제품이면 per-user 분리(REVIEW 백로그) 필요.
- **지금 Streamlit UI 더 다듬지 말 것** — Phase 1 추출만. 폴리시는 React로 가면 버려진다.

---

## 9. 결정지점 (착수 전 확인)
1. Next.js 호스팅(Vercel) + API 컨테이너(Cloud Run/Fly) + Supabase — 이 3분할 OK?
2. 프리뷰 에디터: TipTap(리치 인라인 편집) vs 읽기전용 렌더+채팅편집 — 어디까지 직접 편집 허용?
3. admin 화면(자가진단/학습루프/지식관리)은 Streamlit 잔류 vs Next.js admin 탭 — 잔류 권장(낭비 방지).
4. 인증 범위: 단일 사용자(너) vs 멀티테넌시 출시 — per-user 분리 필요여부 결정.

## 10. 검증
- Phase 1: 서비스 추출 후 Streamlit 동작 동일(smoke 12/12 + 수동) → 회귀 0.
- Phase 2: 각 엔드포인트 계약 테스트(SSE 토큰 수신, docx+enl 바이트 유효).
- Phase 3: §7 패리티 매트릭스 전 행 ✓.
- 누락 최종 점검: `grep`로 §2 카탈로그 키워드가 Next.js/web 또는 admin에 모두 존재하는지 대조.

> 이 문서는 §2 카탈로그로 "과거~최신 흩어진 기능"을 고정한다. Phase 1부터 가면 두뇌 손실 0, 기능 누락 0으로 얼굴만 Lovable급으로 교체된다.
