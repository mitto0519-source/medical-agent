# MASTER_UPGRADE_ROADMAP — 데이터 레이어 + 신뢰성 계층 + 전체 통합

> 통합 대상: `REVIEW_FIX_SPEC`(백엔드 배관) · `KNOWLEDGE_MODEL_SPEC`(지식모델) · `FRONTEND_MIGRATION_SPEC`(제품화)
> + 본 문서(데이터 레이어 확장성 + 신뢰성 8계층). 자가발전 + 논문 확장성 지속 가능 구조가 목표.
> ★ 대원칙: **새로 만들지 말고 배선·확장하라.** 아래 매핑대로 절반 이상이 이미 존재한다(규칙10).

---

## 0. 호출

```
@MASTER_UPGRADE_ROADMAP.md — §1 두-plane 아키텍처를 목표로, §4 통합 순서대로 실행.
모든 신뢰성 계층은 "현存 파일"을 먼저 확인하고 확장한다(새 모듈 금지). §3 표의 "현존" 열이 출발점.
데이터셋은 dataset-agnostic 레지스트리로(§2) — KYRBS 전용 코드를 새 DB마다 복붙 금지.
```

---

## 1. 두-Plane 아키텍처 (SSR·대용량 DB·Supabase 분리 — "지금 그 구조냐"에 대한 답)

**부분적으로만.** 현재: Supabase에 `ma_*`(메타/users/drafts/change_log) + 대용량은 로컬 2.8GB + HF download. 깔끔한 분리는 아직 아님.

목표(=네가 말한 구조):
```
Control Plane  (Supabase Postgres)  ── 가볍고 항상 접속
  · users / auth / projects / drafts / research_state / provenance / change_log
  · variable_registry / dataset_catalog / confidence / failure_kb / journal_rules
Data Plane     (대용량 객체 스토어)   ── 무겁고 온디맨드
  · raw .sav (KYRBS/KNHANES/신규 DB) · oa_papers · chromadb(벡터) · figures
  · 후보: HF Datasets(버전드) / S3·R2 / Supabase Storage
Compute        (서버사이드 API)        ── 통계·RAG·작성은 여기서
  · .sav를 데이터 plane에서 온디맨드 로드 → stats 엔진 실행 → 결과만 클라로
Front          (Next.js, SSR)          ── 데이터 안 들고, API만 호출 → "언제 어디서나"
```
원칙: **프론트는 데이터를 안 가진다.** 대용량은 데이터 plane, 연산은 서버. 그래서 폰에서도 동일. (FRONTEND_MIGRATION의 서버사이드 stats와 동일선상.)
선행: REVIEW **FIX-5**를 HF push-back → **Supabase 컨트롤플레인 + 버전드 데이터플레인**으로 승격.

---

## 2. 데이터 레이어 — 다중 DB 확장성 (KYRBS/KNHANES/임의 DB 동일 구조)

**현존**: `kyrbs_raw_loader._VAR_MAP`(연도별 변수 후보 매핑) + F_BR 코딩 자동감지 + `KYRBS_VARIABLE_COMPATIBILITY.md`. **KYRBS만** 잘 됨. KNHANES는 스텁(.sav 부재, 전용 매핑 없음).

목표 — **dataset-agnostic 레지스트리**(컨트롤플레인 테이블 + 파일):
```
data/registry/<dataset>/variables.yaml   # 버전드, 단일 진실원본
  변수별: std_name · axis(KNOWLEDGE_MODEL 온톨로지축) · {year_range: raw_name} ·
          coding(연도별 코드체계) · derivation · unit · value_labels · status(O/-/△/?)
```
구성요소:
1. **레지스트리 단일화** — `_VAR_MAP`·코딩규칙·호환매트릭스·코드북을 위 YAML 하나에서 *생성*. 로더는 읽기만. (드리프트 제거)
2. **register_dataset 파이프라인**(신규, dataset-agnostic) — `scripts/register_dataset.py <file>`: 컬럼·값레이블 스캔 → 레지스트리 diff → 신규/개명/누락/코딩변경 플래그 → 사람 확인 → 버전업 + 매트릭스 재생성 + smoke. **새 wave·새 DB가 같은 한 명령으로 흡수**.
3. **dataset_catalog**(컨트롤플레인) — 어떤 DB·연도·변수셋이 가용한지 항상 질의 가능. "항시 공급" = 이 카탈로그 + 데이터플레인 동기화.
4. **KNHANES 패리티 + 임의 DB** — 같은 레지스트리/로더 인터페이스. claims/registry/EMR/cohort도 동일 구조로 plug-in(CURRENT_STATE의 scope_extensibility와 일치).
→ 변수 축(axis)이 KNOWLEDGE_MODEL 온톨로지와 같은 통제어휘 → 데이터 변수 ↔ 문헌 개념이 한 그래프에서 연결(다학제·근거연결의 토대).

---

## 3. 신뢰성 8계층 — 현존 매핑 + 확장 (★대부분 이미 있음)

| # | 계층 | 현존(파일) | 상태 | 변경 = 확장 | 연계 |
|---|---|---|---|---|---|
| 1 | **Evidence Graph** (Claim→Evidence→Dataset→Paper→Cite) | `schema_v2` Finding/REPORTS/SUPPORTS/CONTRADICTS/USES_DATASET | 70% | **Claim 노드 신설** + 생성문장↔Claim↔Evidence/Dataset 연결. 인용은 실재 PMID만 | KNOWLEDGE_MODEL 그래프 위에 |
| 2 | **Provenance** (결론→agent/prompt/dataset/model) | `runtime/provenance.py` build_fingerprint(git_sha·model·prompt_hash·dataset_md5·seed·env) | 80% **거의 완성** | **호출부 배선**: 모든 writer/stat/rag 호출에서 record + 문장단위 표면화 | events.db, FRONTEND export 메타 |
| 3 | **Workflow Cost Optimizer** (critical-path 선택 재검수) | 없음 | **0% 신규** | 변경유형 감지 → 해당 reviewer만 재실행(Stat변경→Stat리뷰만). 전체 재실행 금지 | REVIEW **FIX-8** 비평루프에 통합 |
| 4 | **Research State Snapshot** (version·rollback) | `runtime/events.py`(append-only) + provenance + git auto-sync | 50% 소재有 | 명명 체크포인트 `research_state_vN`(RQ/변수선정/회귀 시점) + rollback. events replay 위에 | 컨트롤플레인 저장 |
| 5 | **Failure KB** (왜 실패: multicollinearity→remove BMI) | `FAILURE_PATTERNS.md` + `self_auditor` + `memory/auto_learn` | 40% 문서수준 | 구조화 KB `{failure_type,variables,resolution}` → memory.router(procedural) + 생성시 주입해 회피 | typed memory |
| 6 | **Confidence Engine** (claim/stat/citation/novelty별) | `schema_v2.edge_confidence` + peer_reviewer 루브릭% | 30% 프리미티브 | 컴포넌트 confidence 계산(citation=PMID실재·매칭, stat=가정충족, novelty=graph gap) → overall 집계·표면화 | 검증게이트(FIX-8)·Evidence Graph |
| 7 | **Journal Intelligence** (저널별 룰·트렌드) | `export/journal_targeting.py`(JAMA 등 강조전략) + cover_letter + journal_docx | 60% | word_limit·reference style·acceptance trend 추가. 저널별 템플릿 | FRONTEND export·제출패널 |
| 8 | 추가 Agent | planner DAG roles 다수 | — | **하지 마라**(네 결론 동의). 위 1~7이 ROI 큼 | — |

> **핵심**: 8개 중 net-new는 #3 하나. #2·#7은 거의 완성품 배선, #1·#6은 schema_v2 확장, #4·#5는 소재 위 구조화. "8개 구축"이 아니라 "1개 신규 + 7개 배선/확장".

### 왜 신뢰성이 새 에이전트보다 먼저인가 (네 결론 강화)
의료 논문의 가치는 *더 많은 자동생성*이 아니라 **"왜 이 결론이 나왔는지 추적·재현·신뢰 가능"**에서 나온다. Provenance+Evidence Graph+Confidence = 환각 감소·출처추적·재검증, Cost Optimizer = 운영비·타임아웃 해결. 둘 다 품질과 비용에 직접. 새 에이전트는 그 다음.

---

## 4. 통합 실행 순서 (전 스펙 + 본 문서)

```
[기반·차단해소]
  REVIEW FIX-10 (schema 실배선)  ──┐  ← 전체 인제스트 차단기
  §2 데이터 레지스트리 단일화      │  ← 변수축=온톨로지축 정합
  §1 Supabase 컨트롤플레인 승격     │  (REVIEW FIX-5 확장)
         └─────────────────────────┴─► 전체 12,625 인제스트 1회 (PubMedBERT+새스키마)
                                          │
[신뢰성 — 대부분 배선]                      ▼
  #2 Provenance 배선  →  #1 Evidence Graph(Claim)  →  #6 Confidence 집계
  #4 Snapshot  →  #5 Failure KB  →  #3 Cost Optimizer(FIX-8 통합)
  #7 Journal Intelligence 확장
[제품화 — 병렬 가능]
  FRONTEND Phase1(서비스 추출) → Phase2(API) → Phase3(Next.js) → Phase4(은퇴)
[데이터 확장]
  §2 register_dataset 파이프라인 → KNHANES 패리티 → 임의 DB plug-in
```
원칙:
- **지금 당장**: FIX-10 · §2 레지스트리 단일화 · FRONTEND Phase1 — 셋은 병렬 가능(서로 다른 파일).
- **차단**: 전체 인제스트는 FIX-10+레지스트리 후. 신뢰성 #1·#6은 인제스트 후 그래프가 있어야 의미.
- **비용주의**: #3(Cost Optimizer)을 #2(Provenance)·#6(Confidence) 켜기 *전에* 넣어 검수 폭발 선제 차단.
- 각 단계 `change_log.log()` + smoke 12/12.

---

## 5. 결정지점 (착수 전)
1. 데이터플레인 스토어: HF Datasets(버전드) vs S3/R2 vs Supabase Storage — 2.8GB+증가 감안.
2. Snapshot 입도: 매 단계 vs 주요 이정표만(RQ/변수/분석/작성).
3. Confidence 임계 정책: overall < x면 사용자 경고/차단? (의료라 보수적 권장)
4. register_dataset 사람검수 게이트: 변수 변경 자동승인 vs 항상 확인(권장: 항상).

## 6. 검증
- §2: `register_dataset` 신규 wave 1건 → 레지스트리 diff 리포트 + 매트릭스 재생성 PASS.
- #2: 임의 paper_write 1회 → events.db에 provenance fingerprint(git_sha/model/dataset) 존재.
- #1/#6: 생성 문장에 Claim→Evidence(실 PMID)→Dataset 연결 + confidence 표면화.
- #3: Stat만 변경 시 Stat reviewer만 재실행(나머지 skip 로그) — 토큰/시간 감소 측정.
- 전체: smoke 12/12 + reconcile_state에 registry/provenance/confidence 카운트 추가.

> 요약: 데이터(다중DB·레지스트리·2-plane)와 신뢰성(8계층, 대부분 배선)을 기존 3스펙 위에 얹는다.
> 새로 짓는 건 거의 없다 — **이미 가진 프리미티브를 연결**해 자가발전·재현·신뢰·확장이 항시 성립하는 구조로 만든다.
