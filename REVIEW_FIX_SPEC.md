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

---

# 깊이 보강 FIX-6~8 — "초고급 논문 에이전트" 체감을 만드는 3층

> 전제: 골격(멀티롤 DAG planner/researcher/writer/stylist/critic/statistician/citation_auditor)은 이미 있음.
> 약점은 구조가 아니라 **검색·기억·비평의 깊이**. 무료 LLM 제품이 똑똑해 보이는 비결 = 컨텍스트 엔지니어링.
> **셋 다 "신규 생성"이 아니라 "기존 부품 확장"이다. 새 모듈을 만들면 그 자체가 규칙10 위반(중복).**

## ⚠ 중복·충돌 방지 매트릭스 (착수 전 필독)

| 신규 FIX | 건드리는 파일 | 이미 있는 부품(중복 주의) | 다른 FIX와 충돌/순서 |
|---|---|---|---|
| FIX-6 검색깊이 | `src/rag/pipeline.py`, `src/config/models.py`, `src/vectordb/store.py` | `semantic_search.py`=키워드 overlap(메모리용, **RAG와 별개**, 병합 금지) | **임베딩 교체는 FIX-3보다 먼저.** 안 그러면 12.6k를 MiniLM으로 넣고 또 재임베딩=2회 인제스트 |
| FIX-7 기억증류 | `src/memory/conversation_memory.py` | `summarize_session()`(주제나열만, **업그레이드 대상**), `record()[:200/:400]` | **같은 파일을 FIX-1(owner_email)·FIX-5(영속)도 수정** → 한 사람이 순서대로, 동시 금지 |
| FIX-8 비평루프 | `app/agentic_loop.py`, `src/research/peer_reviewer.py` | `peer_reviewer`=100점 루브릭+`revised_abstract` **이미 존재**(새 리뷰어 금지, 루프로 감싸기) | writing 파이프라인·`ResearchPipeline` continuity 로깅(self_model 권고)과 겹침 |

---

## FIX-6 — 검색 깊이 (rerank + query rewrite + 도메인 임베딩) ★1순위

**문제**: `src/rag/pipeline.py`에 rerank·query rewrite·hybrid·MMR **전무**(grep 0건). 단순 벡터 top-k + 임베딩 `all-MiniLM-L6-v2`(384d, 범용). self_model 약점 avg_dist=0.515의 직접 원인. 연구 에이전트에서 검색품질=지능.

**변경 (4개, 기존 경로 위에 얹기 — 새 검색기 만들지 말 것)**:
1. **Query rewrite/HyDE**: `pipeline.py` 검색 진입에서 질의→가상답변문 생성(get_llm_client, task="qa") 후 그 텍스트로 임베딩 검색. 옵션 플래그로 on/off.
2. **Cross-encoder rerank**: top-30 회수→재정렬→top-5. 신규 의존 1개(sentence-transformers cross-encoder). `pipeline.py` 검색 결과 후처리 단계로만 삽입(저장 경로 무변경).
3. **MMR + 메타데이터 필터**: ChromaDB `where`로 연도/디자인 필터, 결과 다양화. `vectordb/store.py:add_chunks` 메타에 그 필드가 있는지 먼저 확인(없으면 FIX-3 인제스트 때 메타 추가).
4. **임베딩 교체**: `src/config/models.py:get_embedding_model()`(중앙) 한 곳만 바꾸면 `store.py:45`·`supabase_store.py:24` 동시 반영. 의학 임베더(예: PubMedBERT/MedCPT 계열 또는 bge-large)로.

**다운스트림 연계 (★여기가 사고 지점)**:
- **임베딩을 바꾸면 차원이 바뀐다(384→768 등)** → `get_embedding_dim()` 갱신 + **기존 27,671 청크 전부 무효 → 전 재임베딩 필수** → **반드시 FIX-3(대량 인제스트)보다 먼저 임베딩을 확정**한다. 순서 어기면 12.6k를 두 번 인제스트.
- Supabase 사용 시 pgvector 컬럼 차원도 동일 변경 → **FIX-5 마이그레이션과 묶기**.
- rerank/rewrite는 **질의시점**이라 인제스트와 독립 → 임베딩 교체 없이 먼저 넣어도 안전(저위험 우선).

**검증**:
```bash
# rerank 전후 동일 쿼리 관련성 비교(있으면 scripts/diagnose_novelty.py 류로 avg_dist)
python -c "from src.rag.pipeline import <검색함수>; print([h['distance'] for h in <검색함수>('zero-calorie beverage depression adolescent', k=5)])"
python scripts/test_rag_smoke.py   # 12/12
```
**판정**: rerank 적용 후 top-5 평균 distance가 의미 있게 하락하면 PASS.
**롤백**: `pipeline.py`/`models.py` `git checkout`. 임베딩 되돌리면 재임베딩 필요 → `data/chromadb.bak` 복원.

---

## FIX-7 — 기억 증류 (절단→reflection + rolling summary) ★2순위

**문제**: `conversation_memory.record()`가 `user_summary[:200]`/`agent_summary[:400]`로 **문자열 절단**(86-87행). `summarize_session()`(182행)은 **주제 나열만**(진짜 요약 아님). 흐름·연속성·깊이가 여기서 끊긴다.

**변경 (기존 함수 업그레이드 — 새 모듈 금지)**:
1. `record()`에 **reflection 필드** 추가: 교환 후 LLM(get_llm_client, task="standard")이 "확정 사실 / 열린 질문 / 사용자 선호"를 구조화 추출해 entry에 저장. 절단 문자열은 보조로만.
2. `summarize_session()`을 **rolling summary**로 교체: 누적 요약을 LLM으로 갱신·저장하고, 매 턴 system에 재주입.
3. `recall_relevant`은 그대로 두되(벡터), reflection 구조화 사실을 우선 노출.

**다운스트림 연계**:
- **같은 파일을 FIX-1(owner_email 인자)·FIX-5(클라우드 영속)도 수정** → **한 번에 한 FIX만**, 순서 FIX-1 → FIX-7 → FIX-5 권장(시그니처 충돌 방지).
- rolling summary 주입 지점 = `app/agentic_loop.py:build_system_with_preview` (이미 recall 주입함, 거기에 summary 슬롯 추가). FIX-측 컨텍스트 토큰 예산(아래 백로그 4번)과 함께.
- 추가 LLM 호출 비용↑ → reflection은 turn마다 말고 N턴/세션종료에 배치 가능.

**검증**:
```bash
python -c "from src.memory import conversation_memory as cm; cm.record('우울 지표 KYRBS로 보자','aOR 1.04...', owner_email='mitto0519@gmail.com'); print(cm.summarize_session())"
# summary가 주제나열이 아니라 사실/스레드 문장이면 PASS
python scripts/test_rag_smoke.py
```
**롤백**: `conversation_memory.py` `git checkout`. 데이터 손실 없음(append 구조).

---

## FIX-8 — 비평 루프 반복화 (원샷 채점→generate·critique·revise ×N) ★3순위

**문제**: `peer_reviewer.py`에 100점 루브릭·section_scores·major_concerns·`revised_abstract`가 **이미 있다**(채점기 존재). 빠진 건 **반복**: 한 번 채점하고 끝. 약한 모델에서 깊이를 만드는 최대 배율이 이 루프다.

**변경 (peer_reviewer 재사용 — 새 리뷰어 만들지 말 것)**:
1. `agentic_loop`의 `critic` 롤/writing 경로에 루프: **생성 → `peer_reviewer` 채점 → 점수<임계 또는 major_concern 있으면 → 수정 재생성 → 재채점**, 최대 2~3회.
2. 루브릭에 논문 특화 게이트 추가: STROBE 항목(`_h_strobe` 재사용)·통계 가정 위반·**인용 실재성**·과대주장. (백로그 "검증 게이트 4종"과 동일물 → **여기로 통합, 중복 생성 금지**.)
3. 종료조건·최대횟수·비용상한 명시(무한루프/크레딧 폭주 방지).

**다운스트림 연계**:
- `peer_reviewer`는 LLM 필요 → `get_llm_client(task="paper_review")` 경유(직접 client 금지, 규칙5). `_TASK_TIER`에 `paper_review` 없으면 `src/config/models.py`에 추가.
- 루프가 도는 writing 경로 = `src/research/research_pipeline.py`/`agentic_loop._h_run_plan` → **self_model이 지적한 "ResearchPipeline.write_paper continuity 로깅 미연결"을 이때 함께 연결**(중복 작업 방지).
- 백로그의 "검증 게이트 4종"은 **FIX-8에 흡수** → 백로그에서 제거.

**검증**:
```bash
python -c "from src.research.peer_reviewer import <리뷰함수>; r=<리뷰함수>('<초안텍스트>'); print(r.pct, len(r.major_concerns))"
# 루프 1회 후 점수 상승 + major_concern 감소 확인(실측 표)
python scripts/test_rag_smoke.py
```
**판정**: revise 1회 후 total_score가 오르면 루프 작동 PASS. 안 오르면 critique→revise 프롬프트 미반영.
**롤백**: `agentic_loop.py` `git checkout`. peer_reviewer는 원래 동작 보존(루프만 외부 추가).

---

---

# 진행 현황 업데이트 (2026-06-14) — VS Code 실행 + 독립검증 반영

| FIX | 상태 | 검증 메모 |
|---|---|---|
| FIX-0 reconcile | ✅ 완료 | `reconcile_state.py` measure_truth 재사용, 컴파일 OK |
| FIX-1 문체 배선 | ✅ 완료 | load_prompt(owner_email) 5곳 관통, StyleProfiler.load/to_prompt_block 실존 |
| FIX-2 온톨로지 | ✅ 27→114 | `_load_seed_extensions`. (내 마운트 stale로 27 보였음 — 로컬 114 확인 권장) |
| FIX-3 인제스트 | ⚠ **50편만** | 전체 12,625는 ★아래 차단조건 충족 후 |
| FIX-4 더미제거 | ✅ | pmid=12345 제거, 단 **graph.json 로컬 파싱 유효성 직접 확인 필요**(내 마운트 2회 torn read) |
| FIX-5 영속 | ✅ HF push-back | 15분 손실창 존재, Supabase 단일화는 별도 |
| FIX-6 검색깊이 | ✅ rerank+HyDE / ⚠ 임베딩 | **PubMedBERT 768d 활성** — 단 ★레거시 컬렉션 고아(아래) |
| FIX-7 기억증류 | ✅ | _distill + rolling summary |
| FIX-8 비평루프 | ✅ | revise_with_critique (max2, target80%) |
| FIX-9 ground-truth 주입 | ✅ 완료 | `_ground_truth_block()` build_base_system:174, 985자 블록 주입 확인 |
| FIX-10 schema 실배선 | ❌ **미착수** | schema_v2는 정의만, chunker/orchestrator 미통합 → ★전체 인제스트 차단 |

## ★★ 차단조건 2개 — 전체 12,625 인제스트 전에 반드시 해소

**차단 A — 레거시 27,618청크가 고아다.** PubMedBERT 활성 시 에이전트는 `papers_pubmedbert_768d`만 질의(store.py:31-38이 EMBEDDING_MODEL로 컬렉션명 결정). 옛 `papers_minilm_384d`(27,618)는 **다른 컬렉션이라 질의 안 됨**. 지금 검색 가능 코퍼스 = 50편(~782청크)뿐. **전체 재인제스트 끝나기 전까지 RAG는 이전보다 나쁨 → 데모/배포 금지.**

**차단 B — schema_v2 미배선 상태로 전체 인제스트하면 3.5시간 2회 낭비.** 아래 FIX-10이 선행돼야 새 메타/엣지로 한 번에 박힌다.

→ **전체 인제스트 순서: §9 확정 → FIX-10 → (그때) 전체 12,625 인제스트 1회.**

---

## FIX-9 — ground-truth 런타임 주입 [✅ 완료, 참고용]

**한 일**: `src/llm/claude_client.py:_ground_truth_block()`(21)이 `CURRENT_STATE.json:verified_counts` + CLAUDE.md 압축 규칙을 build_base_system(174)에서 매 호출 주입. PowerShell 훅 의존 제거 → 웹=로컬 동등.
**잔여 검증**: 웹 진입(streamlit/agentic_loop)에서도 이 블록이 실제 system 최상단에 들어가는지 1회 확인(로컬 hook과 중복주입 없는지도).

---

## FIX-10 — schema_v2 파이프라인 실배선 (★전체 인제스트 차단 선행조건)

**문제 (고아 정의)**: `src/knowledge/schema_v2.py`는 정의·검증기만 있고 파이프라인과 **완전 분리**(orchestrator·chunker에 `schema_v2/validate_chunk_meta/effect_measure/axis/cui` grep 0건). 결과:
- `hierarchical_chunker.chunk_paper`(112-116)는 아직 **5개 키만**(section/rhetorical_role/citation_density/statistical_method/evidence_level) 출력. §5의 population/exposure/outcome/effect_measure/sample_size/discipline/mechanism/cui **없음**.
- `orchestrator._index_chunks`(169-215)의 ChromaDB metadata도 옛 필드(pmid/doi/title/year/journal/concepts/section/chunk_id)뿐.
- `_add_to_graph`(229)는 `add_concept`/`link_concepts`에 cui/axis/rel을 안 넘김 → 그래프가 여전히 HAS_CONCEPT 평면 태깅.

즉 **50편 인제스트는 옛 스키마로 박혔다.** 전체 인제스트 전에 이걸 실배선해야 한다.

**변경 (기존 심볼 확장 — 새 모듈 금지)**:
1. **chunker**: `hierarchical_chunker.chunk_paper`가 `schema_v2.CHUNK_META_FIELDS` 전체를 채우도록 확장. 정량 추출(effect_measure/estimate/CI/sample_size)·축 태깅(population/exposure/outcome/discipline/mechanism)을 §4 하이브리드(키워드→UMLS링킹→임베딩+LLM)로. 채운 뒤 `schema_v2.validate_chunk_meta(meta)`로 검증(에러 로깅). 못 채운 필드는 `None`(거짓 채움 금지, 규칙11).
2. **orchestrator._index_chunks**: chunk meta 전체를 ChromaDB metadata로 전달(현재는 일부만). ChromaDB 메타는 스칼라만 허용 → list는 콤마 join, dict는 평탄화.
3. **orchestrator._add_to_graph**: `extract_concepts` 결과를 `medical_graph.add_concept(concept_id, label, domain, cui=, axis=)`(104, 확장됨)로, 관계는 `link_concepts(c1, c2, weight, rel=<schema_v2.EDGE_TYPES>)`(147, 확장됨)로. 엣지 weight = `schema_v2.edge_confidence(sample_size, evidence_level)`(220). 미지 엣지/축은 `is_known_edge/is_known_axis`로 게이트.

**다운스트림 연계 (전수 — 누락 시 에러/무효)**:
- ChromaDB metadata 스키마 변경 → **검색 필터(FIX-6 메타 필터)가 새 필드를 참조**하므로 함께 반영. `where={"study_design":...}` 등.
- `reconcile_state.py`에 엣지 타입 분포·`with_cui` 비율·메타 충전율 카운트 추가(진실원본에 스키마 상태 노출).
- **컬렉션 일원화**: 전체 인제스트는 `papers_pubmedbert_768d`로. 끝난 뒤 레거시 `papers_minilm_384d` 컬렉션은 **dead → drop**(규칙10, 고아 제거). drop 전 검색이 768d만 보는지 확인.
- `validate_chunk_meta`의 통제값(RHETORICAL_ROLES/SECTION_LABELS/EFFECT_MEASURES)과 chunker 출력 enum 일치 확인(불일치 시 전수 검증 실패).
- §9 USER_DEFAULTS(이미 schema_v2에 conservative 기본값)가 이 배선에 주입되므로 **§9 확정을 FIX-10 착수 전에**.

**검증 (50편 재인제스트로 양식 먼저)**:
```bash
# 새 메타가 실제로 ChromaDB에 박히나
python -c "import chromadb;c=chromadb.PersistentClient('data/chromadb');col=[x for x in c.list_collections() if '768' in x.name][0];import json;print(col.get(limit=1,include=['metadatas'])['metadatas'])"
# 메타에 effect_measure/discipline/axis/cui 키가 보이고 값이 채워졌는지
python -c "from src.knowledge.medical_ontology import MedicalOntology as O;c=O().all_concepts();print('with_cui',sum(1 for x in c if x.get('cui')),'/',len(c))"
python -c "import json,collections;g=json.load(open('data/knowledge_graph/graph.json'));print(collections.Counter(e.get('relation') for e in g['links']).most_common())"  # HAS_CONCEPT 외 타입 ≥5종
python scripts/test_rag_smoke.py
```
**판정**: 새 컬렉션 메타에 §5 정량/축 필드가 채워지고, 그래프 엣지 타입이 ≥5종으로 다양화되면 PASS. 그제서야 **전체 12,625 인제스트 1회** 진행.
**롤백**: chunker/orchestrator `git checkout`. 50편 재인제스트분만 영향(컬렉션 비우고 재실행). medical_graph는 kwarg default라 하위호환 유지.

---

## FIX-11 — 데이터 git 추방 + auto-sync 가드 (push 차단 해소 + 재발 방지 + 정책 준수)

**문제**: auto-sync commit `81fc357`이 KNHANES raw ZIP 80+개(각 100MB+, ≈2.5GB)를 git에 통째 커밋 → GitHub 100MB 단일파일 한계 + push 페이로드 초과 → `remote end hung up`. 코드패치 4개(dbaba2b/a913c48/85ae017)가 같은 미푸시 페이로드에 묶여 **동반 reject**. 부차: **KDCA 재배포 정책상 KNHANES raw .sav를 public GitHub에 두면 안 됨**.

**근본원인**: `scripts/auto_sync.py`가 **`git add -A`**(7행 docstring / ~120행)로 데이터/바이너리까지 무차별 stage·commit. → history 고쳐도 1분 뒤 재오염.

**※ LFS 기각**: LFS도 GitHub에 업로드 → 정책 위반 그대로. 데이터는 git이 아니라 데이터플레인(비공개)으로.

**변경 (순서 중요 — ①출혈차단 → ②퍼지 → ③push → ④데이터 이전)**:

① **출혈 차단 (먼저, 안 하면 퍼지 후 재오염)**
```bash
# .gitignore 추가
printf '\ndata/raw/\ndata/oa_papers/\ndata/chromadb/\n*.sav\n*.dta\n*.zip\n' >> .gitignore
git rm -r --cached data/raw data/oa_papers data/chromadb   # 디스크 유지, 추적만 해제
```
+ `scripts/auto_sync.py`: **`git add -A` → 화이트리스트/사이즈 가드로 교체**:
```python
# add -A 금지. 코드만 + 50MB 초과·data/raw·*.sav·*.zip는 절대 stage 금지.
git(["add", "--", "*.py", "*.md", "*.json", "*.yaml", "*.toml", "prompts", "src", "app", "scripts"])
# 가드: staged 중 50MB↑ 있으면 abort+경고(재발 즉시 차단)
big = [f for f in staged_files() if size(f) > 50*1024*1024]
if big: log(f"ABORT: 거대파일 staged {big}"); git(["reset"]); return
```

② **history 퍼지 (push 미완료라 안전 — 로컬 재작성)**
```bash
git branch backup-before-purge                       # ★ 백업 필수
pip install git-filter-repo
git filter-repo --path data/raw --path data/oa_papers --path data/chromadb --invert-paths --force
# → 데이터 blob 전 history 제거, 코드 4패치 보존
```
> 단일 커밋 확인: `git log --oneline --stat | grep -iE "knhanes|\.zip|\.sav" | head`. 여러 커밋에 퍼졌으면(매분 auto-sync) filter-repo가 정답.

③ **push**
```bash
git remote add origin <url>    # filter-repo가 origin 제거 → 재설정
git push origin master         # 페이로드 작아져 통과
```

④ **데이터 → 데이터플레인 (정책·용량 영구 해결, MASTER §1)**
KNHANES/KYRBS raw를 **비공개 HF Dataset(private) 또는 S3/R2/Supabase Storage**에 업로드. 기존 `src/runtime/hf_bootstrap.py`가 컨테이너 시작 시 download(이미 있음). git엔 코드만.

**다운스트림 연계**:
- `hf_bootstrap` repo_id를 **private**로 + 토큰. raw 폴더 download 대상 유지.
- MASTER_ROADMAP §1(2-plane): 이 작업이 데이터플레인 분리의 첫 실행분.
- 모든 auto-sync 후속 커밋이 가드 적용받음(재발 0).

**검증**:
```bash
git push origin master && echo PUSH_OK
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectsize) %(rest)' | awk '$2>104857600' | head   # 100MB↑ 0건이어야
# auto-sync 가드: data/raw에 더미 .sav 두고 1 cycle → commit 안 됨 확인
python scripts/test_rag_smoke.py
```
**판정**: push 성공 + history에 100MB↑ blob 0 + auto-sync가 .sav를 skip하면 PASS.
**롤백**: `backup-before-purge` 브랜치로 복원. filter-repo 전 클론 백업 권장.

---

## FIX-11 ④-bis — 데이터 = 재생성 가능 캐시 (영구 차단, 2026-06-16 추가)

**문제**: FIX-11 filter-repo가 push 차단은 해결했지만 **두 번째 데이터 사고** 유발:
`git filter-repo --path data/oa_papers --invert-paths` 가 history에 추적되던 path를 워킹트리에서도 hard-reset으로 삭제. 이후 `git gc --prune=now` 가 .git/objects도 영구 정리. 결과: **9,000편+ PMC 본문 .txt가 사라짐**. ChromaDB 47,568 chunks(3,697편 분)는 살아남았으나 나머지 8,928편 인덱싱 불가.

복구: HF Datasets 사본(`cave87/medical-agent-runtime`, 사고 4일 전 백업)에 9,796편 살아있어 즉시 복구 가능. 그러나 **재발 차단**이 핵심.

**근본원인**: 데이터(재생성 가능)와 코드를 같은 트리에 둠. git이 어떤 명령(filter-repo, clean, reset --hard, OneDrive sync 충돌)이든 데이터를 건드릴 수 있는 구조.

**영구 해법 (외부 진단 그대로)**:

1. **데이터플레인 분리** — `oa_papers`, `raw`, `chromadb`는 **HF private Datasets / 객체스토어**가 단일 진실원본. 워킹트리는 *언제든 재생성 가능한 캐시*.
2. **재fetch 차집합 스크립트** — `oa_bulk_fetcher.py` 부분 차집합 모드: ChromaDB에 든 PMID는 빼고 Europe PMC에서 누락분만 받음.
3. **컨테이너 부팅 시 자동 복구** — `scripts/restore_oa_papers_from_hf.py` (이미 작성). docker compose up / HF Space 부팅 시 자동 호출 → 워킹트리 비어있어도 즉시 복구.
4. **정기 push-back** — `scripts/sync_oa_to_hf.py` (이미 작성). 인제스트 후 또는 heartbeat 매일 1회 HF push. idempotent.

**구현 산출**:
- `scripts/restore_oa_papers_from_hf.py` — HF → data/oa_papers/ 다운로드 (allow_patterns로 선택)
- `scripts/sync_oa_to_hf.py` — data/oa_papers/ → HF push-back (인제스트 후)
- `scripts/restore_then_ingest.py` — 복구 + 인제스트 체인 한 줄
- `src/runtime/heartbeat.py` 신규 job: `data_plane_sync` (매일, idempotent)

**검증**:
```bash
# 워킹트리 oa_papers 일부러 삭제 → restore가 복원하나
rm -rf data/oa_papers/*.txt
python scripts/restore_oa_papers_from_hf.py
ls data/oa_papers/PMC*.txt | wc -l  # > 0 이어야 PASS
# filter-repo 시뮬 → restore_then_ingest 한 줄로 30분 내 풀 복구
```

**판정**: 워킹트리에서 .txt 일부러 지워도 부팅 자동 복구 + 인제스트 시작 + sync로 cloud truth 갱신 = 데이터 사고 영구 0.

**롤백**: HF Dataset의 commit history (private, 자동 버전 관리) — 옛 상태로 언제든 복원.

---

## FIX-12 — ★ 저장소 OneDrive 탈출 (며칠째 사고의 물리적 근본원인)

**문제**: 저장소가 **OneDrive 폴더 안**(`C:\Users\mitto\OneDrive\Desktop\Medical-Agent`)에 있다. OneDrive는 디스크 절약차 파일을 *오프로드(on-demand stub)* 하고, 큰 파일은 *스트리밍*해서 — 에이전트/마운트가 읽을 때 블로킹·부분읽기·증발이 난다. (sfs/Mirage가 정확히 지적한 문제)
→ 이번 세션 내내의 증상이 전부 이것: 마운트 stale(src/service·loops·specs 안 보임), **oa_papers .txt 소실**, **"working directory empty"**, graph.json torn-read, filter-repo 사고 증폭.

**변경 (ops — 코드 아님)**:
1. 저장소를 **OneDrive 밖 일반 경로로 이전**: 예 `C:\dev\Medical-Agent`. (git remote·.venv 그대로 이동)
2. **데이터플레인 분리**(MASTER §1): raw/oa_papers/chromadb는 OneDrive·git 둘 다 금지 → HF private/S3/Supabase Storage. 워킹카피는 재생성 캐시.
3. OneDrive 백업이 필요하면 *문서/산출물만* 별도 폴더로, *코드·데이터 저장소는 OneDrive 밖*.
4. (대안) sfs류로 `--remote s3://...` 마운트 — 오프로드 없는 동기화.

**다운스트림**: 모든 경로 참조는 상대경로라 이전만으로 동작. hf_bootstrap·docker 마운트 경로 확인. git remote(origin/hf) 유지.
**검증**: 이전 후 `dir`·`git status` 안정, 마운트 stale 없음, 큰 파일 즉시 읽힘.
**롤백**: 경로 복원(데이터 손실 없음 — 복사 이전).
> ★ 이게 #1 즉효다. "왜 자꾸 망가지고 안 보이나"의 답이 *OneDrive*다. 다른 fix 전에 이거부터.

### FIX-12b — agent-time vs human-time 추정 정책 (EstreGenesis 차용, ops)
AI는 작업기간을 인간기준 **5~10× 부풀린다**. 계획 시 모드 고정: Cautious 2~4× / Proactive 5~6× / Burst 6~8× / Sprint 9~10×. 추정을 *에이전트작업+사람검토+실경과*로 분리 보고. (계획 신뢰성↑, 너 없던 정책)

---

## 백로그 (별도 사이클 — 지금 건드리지 말 것)

- **persona/self_model/insights/knowledge_graph per-user 분리**: 현재 전역 단일 파일. "그 사람에게 최적화"가 다중사용자로 가면 필요. 단일사용자 운영이면 보류.
- ~~검증 게이트 4종~~ → **FIX-8에 흡수됨**(중복 생성 금지). 프리뷰 인라인 경고 UI만 별도 작업으로 남김.
- **최상위 일회성 스크립트 20개 + scripts 59개 + app/_archive 정리**: `app/main.py` Flask 레거시 제거(self_model이 이미 권고), `delete_main.py/do_commit.py/prepare_commit.py` 등 잔여물 archive 이동.
- **app/streamlit_app.py.tmp.32032.* 7개 삭제**(동시편집 잔여물, gitignore돼 git엔 안 잡힘).
- **규칙위반 정리**: ClaudeClient 직접호출 5곳(roles.py:172, rag/pipeline.py:78, project_workspace.py:1101/1210, mcp_server.py:970), `except: pass`(planner.py 6곳 등), load_dotenv 분산.

---

## 실행 순서 요약 (의존성 그래프)

```
[완료] FIX-0,1,2,4,5,6(rerank+임베딩),7,8,9
[남은 핵심 경로 — 전체 인제스트로 가는 유일한 정답 순서]

   graph.json/chroma 로컬 유효성 확인
            │
   §9 결정 5개 확정 (USER_DEFAULTS 덮어쓸지)
            │
   FIX-10 (schema_v2 → chunker/orchestrator/graph 실배선)   ←★전체 인제스트 차단기
            │
   50편 재인제스트로 새 메타/엣지 PASS 검증
            │
   전체 12,625 인제스트 1회 (papers_pubmedbert_768d, ~3.5h)
            │
   레거시 papers_minilm_384d 컬렉션 drop  +  reconcile_state 재실행
            │
   quality_harness gold_set 실 PMID 채우기
```
- **지금 하면 안 되는 것**: 전체 12,625 인제스트(차단 A·B 미해소 → 3.5h 2회 낭비 + 검색코퍼스 공백).
- **다음 한 수**: §9 확정 → **FIX-10**. 이게 전체 인제스트의 단일 선행조건.
- **conversation_memory.py 공유(FIX-1·7·5)·임베딩-인제스트 선후**는 이미 반영됨(완료).
- 각 FIX 후 `change_log.log()` + smoke 12/12 확인.

> 작성 기준 데이터는 2026-06-13 실측. 코드가 그새 바뀌었으면 FIX 착수 전 해당 파일을 다시 읽고 라인 보정할 것(규칙7).
