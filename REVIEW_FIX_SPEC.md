# REVIEW_FIX_SPEC — Medical-Agent 정밀 수정·보강 스펙

> 작성: 외부 진단(Cowork, read-only). 실수정은 VS Code(Claude Code)에서 실행.
> 목적: 추측 없이 위→아래로 처리하면 **에러 없이** 수정+보강이 끝나도록, 각 항목에
> `파일:라인 → 근본원인 → 변경 → 다운스트림 연계 → 검증 → 롤백`을 모두 박아둔 단일 문서.
> 모든 수치는 2026-06-13 실측(샌드박스에서 실파일/실DB 조회).

---

## 0. VS Code에서 호출하는 법 (이 문단을 그대로 붙여넣어 시작)

```
@REVIEW_FIX_SPEC.md 를 읽고, FIX-0부터 순서대로 실행한다.
규칙:
- 각 FIX는 "변경 → 다운스트림 연계 전수수정 → 검증 → change_log.log()" 까지 한 묶음으로 끝낸다(규칙10).
- 한 FIX의 검증(Verify)이 PASS하기 전에는 다음 FIX로 넘어가지 않는다.
- 코드 직접 client 생성/모델 하드코딩 금지(규칙5). LLM은 get_llm_client(task=...) 경유.
- 구현 못 한 부분은 "안 됨 + 이유"로 보고(규칙11). "아마 될 것" 금지.
- 시작 전 FIX마다 git diff 가능하도록 작은 커밋 단위 유지.
먼저 FIX-0(reconcile)만 실행하고 결과 표를 보여줘. 내가 확인 후 다음으로 간다.
```

> 권장: **한 번에 하나의 FIX만** 시키고 검증을 본 뒤 다음으로. 한꺼번에 시키면 다운스트림이 꼬인다.

---

## 1. 검증된 현재 상태 (Ground Truth) — 문서가 거짓말하는 지점

| 항목 | 문서(CURRENT_STATE.json) | **실측(2026-06-13)** | 갭 |
|---|---|---|---|
| 논문 전문 | "12,301 full-text" | 전문(.txt) **12,625**, 메타stub **25,251**, 사이드카json 12,625 (총 50,504 파일) | 전문은 ~12.6k뿐, "5만"의 75%는 본문 미확보 |
| RAG 청크 | "20,894 chunks" | ChromaDB embeddings **27,671**, 큐 대기 **893**, embedding_metadata 314,673 | 전문 12.6k 기준 편당 2.2청크 = **인제스트 ~7~8%만 완료** |
| 지식그래프 파일 | `medical_graph.json` | 실파일은 `data/knowledge_graph/graph.json` | **파일명부터 불일치** |
| 그래프 구성 | "10,005 nodes" | nodes **10,134** (paper 10,105 / **concept 27** / dataset 2), edges 54,131 (HAS_CONCEPT 51,652 / USES_DATASET 1,991 / concept간 RELATED_TO **108**) | 개념층이 27개뿐 = 평면 태깅 |
| 온톨로지 | (언급 없음) | `medical_ontology.py` 하드코딩 dict **27개 개념** | 그래프 천장 = 이 27개 |
| 조유선 | "yoosun seed" | `yoosun_cho.json` 11편 분석, raw_examples 10, system_prompt 6,234자 | 작동 OK, 단 단일저자 하드코딩 |

> **결론**: 권위 메모리(CURRENT_STATE.json)가 실데이터와 어긋나 있고, 이를 자동 일치시키는 코드가 **없다**(`grep CURRENT_STATE` → 코드 writer 0건, sync.log만 언급). 그래서 매 세션 에이전트가 틀린 숫자로 추론한다. **이게 "VS Code에서 자꾸 꼬인다"의 1차 원인.**

---

## FIX-0 — 진실원본 자동 동기화 (최우선, 의존성 없음)

**문제**: `CURRENT_STATE.json`을 갱신하는 코드가 없다. 수기 유지 → 영구 드리프트.
`assess_maturity.py`는 print만 하고 파일을 안 쓴다. `src/memory/self_model.py:102 refresh()`는 `self_model.json`만 갱신(별도 파일).

**변경**: 새 스크립트 `scripts/reconcile_state.py` 생성. 실데이터를 스캔해 `CURRENT_STATE.json`의 수치 필드를 덮어쓴다.

측정해야 할 실값(이미 검증된 조회 방법):
```python
# 논문
oa = Path("data/oa_papers")
n_meta = len(list(oa.glob("*.meta.json")))            # 25,251
n_full = len(list(oa.glob("*.txt")))                  # 12,625
n_full_real = sum(1 for f in oa.glob("*.txt") if f.stat().st_size > 5*1024)  # 12,338
# ChromaDB
import sqlite3, glob
db = glob.glob("data/chromadb/*.sqlite3")[0]
c = sqlite3.connect(db)
n_chunks = c.execute("SELECT count(*) FROM embeddings").fetchone()[0]       # 27,671
n_queue  = c.execute("SELECT count(*) FROM embeddings_queue").fetchone()[0] # 893
# 그래프
import json
g = json.load(open("data/knowledge_graph/graph.json"))
n_nodes = len(g["nodes"]); 
from collections import Counter
ntypes = Counter(n.get("type") for n in g["nodes"])   # paper/concept/dataset
# 온톨로지
from src.knowledge.medical_ontology import MedicalOntology
n_concepts = len(MedicalOntology().all_concepts())     # 27
```
→ 이 값들로 `CURRENT_STATE.json:key_assets_by_size` + 신규 `verified_counts` 블록을 갱신하고, `ARCHITECTURE.md`의 그래프 파일명을 `graph.json`으로 정정.

**다운스트림 연계 (전수)**:
- `CURRENT_STATE.json` → 매 prompt hook(`.claude/hooks/preprompt_memory_inject.ps1`)이 prepend → 갱신 즉시 에이전트 추론에 반영.
- `ARCHITECTURE.md` / `ARCHITECTURE_SHORT.md` → `medical_graph.json` 언급 전부 `graph.json`으로 grep 치환.
- `assess_maturity.py` → reconcile 호출 또는 동일 카운터 재사용(중복 카운터 만들지 말 것, 규칙10).

**검증**:
```bash
python scripts/reconcile_state.py && python -c "import json;d=json.load(open('CURRENT_STATE.json'));print(d.get('verified_counts'))"
grep -rn "medical_graph.json" ARCHITECTURE.md ARCHITECTURE_SHORT.md CURRENT_STATE.json  # 0건이어야 함
```
**롤백**: `git checkout CURRENT_STATE.json ARCHITECTURE.md`. 스크립트는 신규 파일이라 삭제만.

---

## FIX-1 — 본인 문체 엔진 배선 (★ "AI같지 않게"의 핵심, 고아 코드 활성화)

**문제 (전형적 꼬임)**: 사용자별·정량 문체 엔진 `src/ingestion/style_profiler.py`가 **이미 완성**돼 있다 — `StyleProfiler`(96), `_owner_hash(owner_email)`(110), `_profile_path`(115, `data/.../{hash}/style_profile.json`), `extract_from_text()`(152), 백분위 기반 stylometry(174). 클래스 docstring도 "AI같지 않게=사용자 본인 문체의 진짜 엔진"이라 명시.
**그러나 호출되지 않는다.** 라이브 경로 `src/agent/prompt_loader.py`는 조유선 하드코딩:
- `prompt_loader.py:33-35` → `TASK_PROMPTS["paper_write"] = [..., "yoosun_style", ...]`
- `prompt_loader.py:119-125` → `yoosun_cho.json` raw_examples를 강제 첨부.

즉 새 엔진(style_profiler) ↔ 옛 경로(yoosun 하드코딩)가 **공존하며 옛 것만 작동**.

**변경 (배선 + 폴백 강등)**:
1. `prompt_loader.load_prompt(task, *, owner_email=None)`에 owner 인자 추가.
2. paper_write 계열일 때: `StyleProfiler`로 `owner_email`의 `style_profile.json`을 조회.
   - 있으면 → 그 프로파일(정량 지표 + 추출 규칙)을 system에 주입, yoosun_style은 **미주입**.
   - 없으면 → 기존 `yoosun_style` + raw_examples를 **폴백**으로 주입(하위호환 유지).
3. `yoosun_style.md`는 삭제하지 말고 "기본 폴백 시드"로 격하(헤더 주석 1줄).

**다운스트림 연계 (전수 — 여기서 안 하면 에러/무반영)**:
- `prompt_loader.load_prompt` 시그니처 변경 → **모든 호출부 수정**:
  ```bash
  grep -rn "load_prompt(" src app --include=*.py    # 호출부 전수 확인 후 owner_email 전달
  grep -rn "load_yoosun_with_exemplars" src app     # 이 헬퍼도 owner 분기로 통합
  ```
- `src/llm/claude_client.py build_base_system(base, task)` → prompt_loader를 부르는 합성 지점. owner_email을 task 컨텍스트로 전달받도록 한 단계 위(`get_llm_client(task=...)`)에서 owner를 넘길 경로 확인. owner 없으면 폴백이므로 **시그니처는 keyword-default로** 하위호환.
- `app/agentic_loop.py:build_system_with_preview(...)` → 이미 `owner`를 알고 있음(=프로젝트 owner). 여기서 prompt 합성 시 owner_email을 prompt_loader까지 관통시킴.
- 신규: **본인 논문 업로드 → StyleProfiler.extract_from_text → style_profile.json 저장** UI/핸들러. 업로드 경로가 없으면 이 FIX의 절반(소비)만 되고 생산이 빔 → `app/pages/project_workspace.py` 또는 ez_home 채팅 핸들러에 "내 논문 올리기" 추가(규칙8: 메뉴보다 채팅 핸들러 우선).
- `src/ingestion/style_profiler.py`가 docx/pdf를 읽음 → `python-docx`, `pypdf` 의존성 확인(`requirements.txt`).

**검증**:
```bash
python -c "from src.ingestion.style_profiler import StyleProfiler as S; p=S().extract_from_text(open('data/oa_papers/'+[f for f in __import__('os').listdir('data/oa_papers') if f.endswith('.txt')][0]).read(), owner_email='mitto0519@gmail.com'); print(p)"
# owner 프로파일 있을 때 yoosun 미주입 확인:
python -c "from src.agent.prompt_loader import load_prompt; s=load_prompt('paper_write', owner_email='mitto0519@gmail.com'); print('yoosun' in s, len(s))"
python scripts/test_rag_smoke.py     # 12/12 유지
```
**판정 기준**: owner 프로파일 존재 시 출력 system에 yoosun 시드가 빠지고 본인 지표가 들어가면 PASS. 빠지지 않으면 분기 미배선.
**롤백**: prompt_loader/claude_client/agentic_loop 3파일 `git checkout`. style_profiler는 원래 미사용이라 영향 없음.

---

## FIX-2 — 온톨로지 27→수백 확장 (그래프 "패턴화"의 천장 제거)

**문제**: 그래프 배선은 정상이다 — `orchestrator.ingest()`(orchestrator.py:96)가 `ontology.extract_concepts(text)`(122) → `_add_to_graph`(229) → `medical_graph.add_paper/add_concept/link_paper_concept`(graph.py:93/104/123)를 제대로 호출. **막힌 건 데이터**: `medical_ontology.py:22~`의 하드코딩 dict가 `D_population/D_behavior/...` 27개 개념뿐. 모든 논문이 27버킷에만 꽂힘 → "유형화 패턴화" 불가, concept간 엣지 108개뿐.

**변경 (택1, 권장은 B)**:
- A) `medical_ontology.py`의 dict를 손으로 수백 개로 확장(빠르지만 유지부담).
- B) **MeSH/UMLS 로더 추가** — `data/medical_knowledge_seed`(6MB, typology/vocabulary catalog 존재)나 MeSH descriptor를 파싱해 `MedicalOntology`를 파일 기반으로 로드. `extract_concepts`/`all_concepts` 인터페이스는 유지(규칙10: 호출부 무변경).
- 두 경우 모두 **개념 도메인을 임상축으로 확장**: mechanism / exposure / outcome / biomarker / drug / design 노드 타입을 추가해 concept↔concept 엣지(`link_concepts`, graph.py:133)를 실제로 생성(현재 108→수천 목표).

**다운스트림 연계**:
- 온톨로지 확장만으론 **기존 그래프가 자동 재태깅되지 않음** → 코퍼스 재인제스트 필요(= FIX-3과 연결). 순서: FIX-2(온톨로지) → FIX-3(재인제스트)가 함께 돌아야 그래프 개념층이 채워짐.
- `orchestrator.query()`(269)의 `top_concepts` 집계 → 개념 수 증가에 자동 반영, 별도 수정 불필요(인터페이스 유지 시).
- `concept_gap_pairs`(graph.py:170) / 신규성 탐지가 개념 다양성에 의존 → 확장 후 신규성 품질 향상 기대.

**검증**:
```bash
python -c "from src.knowledge.medical_ontology import MedicalOntology; print('concepts=',len(MedicalOntology().all_concepts()))"   # >>27
python -c "import json,collections;g=json.load(open('data/knowledge_graph/graph.json'));print(collections.Counter(n['type'] for n in g['nodes']))"  # concept 수 증가(FIX-3 후)
```
**롤백**: `git checkout src/knowledge/medical_ontology.py` + graph.json 백업 복원(아래 FIX-3 백업 참조).

---

## FIX-3 — 인제스트 완주 + 큐 드레인 (RAG 가용분 7%→목표 80%+)

**문제**: 전문 12,625편 대비 청크 27,671개(편당 2.2) = 대부분 미인제스트. 원인은 **두 인제스트 경로 불일치**:
- `scripts/ingest_graph_papers.py:34 build_chunk(node)` → **graph.json paper 노드의 abstract**만 청킹(line 88 `paper_nodes`). 본문 미사용 → 편당 1~2청크.
- `src/knowledge/orchestrator.py:96 ingest(full_text=...)` → 본문 청킹+개념추출+그래프까지 하는 **정식 경로**. 그러나 12.6k .txt를 이 경로로 흘리는 배치 드라이버가 안 돌았음.
- `chunker.py:13` chunk_size=500/overlap=100 → 15KB 본문이면 ~30청크. 12,625×30 ≈ 370k 기대 → 현재 27,671은 ~7.5%.

**변경**:
1. 배치 드라이버 작성/수정: `data/oa_papers/*.txt` 전수 → `orchestrator.ingest(pmid, title, abstract, full_text=...)` 호출. `ingest_graph_papers.py`를 본문 경로로 교체하거나 신규 `scripts/ingest_fulltext_corpus.py`로 일원화(둘 다 두면 또 꼬임 → **하나로 통합하고 옛 것은 제거**, 규칙10).
2. 멱등성: 이미 인제스트된 pmid skip(`embeddings_queue`/메타로 중복 차단). `src/runtime/idempotency.py` 활용.
3. 큐 드레인: `embeddings_queue` 893건 처리(ChromaDB 비동기 큐가 안 비워졌을 수 있음 → flush/persist 확인).
4. 메타stub 25,251의 본문 fetch 정책 결정: `src/ingestion/oa_bulk_fetcher.py`/`pmc_downloader.py`로 본문 받을지, 아니면 stub는 RAG 제외할지 **명시적 결정 후 문서화**.

**다운스트림 연계**:
- `src/vectordb/store.py:70 add_chunks` → ChromaDB 로컬. **온라인 영속은 FIX-5 전제**(안 하면 재배포 때 인제스트 결과 소실 → 헛수고). **FIX-5를 먼저 하거나 동시에.**
- self_model 약점 "RAG avg_dist=0.515" → 인제스트 완주 후 재측정. 여전히 나쁘면 임베딩 모델/청킹 전략(hierarchical_chunker 사용) 조정.
- `HF_TOKEN 미설정`(self_model next_action) → 임베딩 모델 다운로드 실패로 인제스트가 조용히 멈출 수 있음 → 배치 시작 전 토큰 확인.
- FIX-2 온톨로지 확장과 **같은 배치에서** 재태깅되어야 그래프 개념층도 채워짐.

**검증**:
```bash
python scripts/ingest_fulltext_corpus.py --limit 50    # 소량 먼저
python -c "import sqlite3,glob;c=sqlite3.connect(glob.glob('data/chromadb/*.sqlite3')[0]);print('chunks=',c.execute('SELECT count(*) FROM embeddings').fetchone()[0])"  # 증가 확인
python scripts/test_rag_smoke.py
# 관련성 회귀: 동일 쿼리로 avg_dist 측정(있으면 scripts/diagnose_novelty.py 등)
```
**판정**: 50편 인제스트에 청크가 ~1,000+ 증가(편당 ~20)하면 본문 경로 정상. 50~100만 증가하면 여전히 abstract 경로.
**롤백**: 인제스트 전 `cp -r data/chromadb data/chromadb.bak` + `cp data/knowledge_graph/graph.json graph.json.bak`. 실패 시 복원.

---

## FIX-4 — 그래프 테스트더미 제거 + 무결성

**문제**: graph.json에 `"Test: Adolescent obesity..." pmid 12345` 더미 노드가 운영 데이터에 섞여 있음(샘플 노드에서 확인). 코드 시더는 아니고(grep 12345 → 전부 docstring 예시), 과거 수동/테스트 ingest가 영속화된 잔여물.

**변경**: 정리 스크립트 `scripts/prune_graph.py` — pmid가 실 PMC/PMID 형식이 아니거나 title이 `Test:`로 시작하는 노드 + 그 엣지 제거. 백업 후 실행.

**다운스트림 연계**: graph.json을 읽는 모든 곳(`orchestrator`, `research_pipeline` 신규성, `app` 표시)이 자동 정상화. node/edge 카운트 변동 → **FIX-0 reconcile 재실행**으로 CURRENT_STATE 갱신.

**검증**:
```bash
python -c "import json;g=json.load(open('data/knowledge_graph/graph.json'));print([n for n in g['nodes'] if str(n.get('title','')).startswith('Test') or n.get('pmid')=='12345'])"  # [] 이어야 함
```
**롤백**: `graph.json.bak` 복원.

---

## FIX-5 — 온라인 영속 (write-back) — "온라인=로컬"의 전제

**문제**: `src/runtime/hf_bootstrap.py`는 콜드스타트 시 `snapshot_download`(다운로드)만. 코드 전역에 `upload_file/push_to_hub/HfApi` **0건**. → HF Spaces 등 휘발 FS에서 세션 중 쓴 `data/runtime/*.db`(events/tasks/lifecycle/procedural/idempotency), `data/chromadb`, 대화기억이 **재시작·슬립·재배포 때 소실**. 핵심 메모리 쓰기 경로 `src/memory/router.py`→`src/runtime/events.py:73 append`도 로컬 only.
부분 예외: `change_log/agent_insight/self_model`만 Supabase 미러(`src/cloud/db.py` ma_* 테이블).

**변경 (택1)**:
- A) **Supabase 일원화(정공법)**: events/conversation/tasks를 SQLite 대신 Supabase로. ChromaDB → `src/vectordb/supabase_store.py`(이미 존재, pgvector) 활성화. 작업량 큼, 동시성/멱등 안전.
- B) **HF Datasets write-back(빠른 봉합)**: `hf_bootstrap`에 대칭 `ensure_persist()` 추가 — 주기/세션종료 시 `upload_folder`로 `data/runtime`·`data/chromadb` 업로드. 단일 인스턴스 전제(동시쓰기 충돌 주의), 큰 청크는 비용/지연.

**다운스트림 연계**:
- FIX-3 인제스트 결과·FIX-2 그래프가 온라인에서 살아남으려면 **이 FIX가 선행/동반**되어야 함. 안 하면 인제스트가 매 배포 헛수고.
- `RUNTIME_DB_DIR` env(events/tasks/lifecycle/idempotency 공통)와 ChromaDB path를 **영속 볼륨 또는 동기화 대상**으로 일관 지정.
- 멀티유저면 conversation_memory는 owner_email로 분리되지만(이미 OK), **persona/self_model/insights/graph는 전역** → 온라인 다중사용자 시 섞임. per-user가 목표면 별도 FIX(아래 백로그).

**검증**: 컨테이너 재시작 시나리오로 "세션에서 쓴 메모리가 재기동 후 recall되는가"를 실제 재시작으로 확인(규칙5: CLI PASS≠앱 동작). `scripts/ui_eval.py` 류로 저장→재기동→복원 outcome 검증.
**롤백**: bootstrap/cloud 설정 `git checkout`. Supabase 스키마 변경 시 마이그레이션 역적용.

---

## 백로그 (별도 사이클 — 지금 건드리지 말 것)

- **persona/self_model/insights/knowledge_graph per-user 분리**: 현재 전역 단일 파일. "그 사람에게 최적화"가 다중사용자로 가면 필요. 단일사용자 운영이면 보류.
- **검증 게이트 4종**(통계가정·인용실재·신규성·과대주장)을 프리뷰 인라인 경고로 — "올바른 마찰". 토대(FIX-0~5) 후.
- **최상위 일회성 스크립트 20개 + scripts 59개 + app/_archive 정리**: `app/main.py` Flask 레거시 제거(self_model이 이미 권고), `delete_main.py/do_commit.py/prepare_commit.py` 등 잔여물 archive 이동.
- **app/streamlit_app.py.tmp.32032.* 7개 삭제**(동시편집 잔여물, gitignore돼 git엔 안 잡힘).
- **규칙위반 정리**: ClaudeClient 직접호출 5곳(roles.py:172, rag/pipeline.py:78, project_workspace.py:1101/1210, mcp_server.py:970), `except: pass`(planner.py 6곳 등), load_dotenv 분산.

---

## 실행 순서 요약 (의존성 그래프)

```
FIX-0 (reconcile, 독립) ──────────────┐
FIX-5 (영속) ──┐                       │
               ├─> FIX-2 (온톨로지) ──> FIX-3 (재인제스트, 본문) ──> FIX-0 재실행(카운트 갱신)
FIX-4 (더미제거, 독립) ────────────────┘
FIX-1 (문체 배선, 독립) ── 언제든
```
- **먼저**: FIX-0 → FIX-1(체감 큼, 독립) → FIX-4(저위험).
- **묶음**: FIX-5 ↔ FIX-2 ↔ FIX-3 은 함께(영속 없이 인제스트=헛수고, 온톨로지 없이 재인제스트=개념층 안 참).
- 각 FIX 후 `change_log.log()` + smoke 12/12 확인.

> 작성 기준 데이터는 2026-06-13 실측. 코드가 그새 바뀌었으면 FIX 착수 전 해당 파일을 다시 읽고 라인 보정할 것(규칙7).
