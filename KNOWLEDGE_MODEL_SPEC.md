# KNOWLEDGE_MODEL_SPEC — 청킹·온톨로지·그래프 정의 (다학제·고세분화)

> 짝 문서: `REVIEW_FIX_SPEC.md`(배관 수리). 이 문서는 **지식 모델 자체의 정의**.
> 원칙: 의미를 **임의 발명하지 않는다**. 모든 축을 기성 표준(MeSH/UMLS CUI/SNOMED-CT/ICD/LOINC/RxNorm·ATC/HPO/MedDRA)과
> 보고 프레임워크(PICO/PECO·STROBE·CONSORT·PRISMA·GRADE·Oxford CEBM)에 **앵커**한다. 그래야 정당하고 상호운용된다.
> ★ 타이밍: 이 스키마는 **FIX-3 대량 인제스트·그래프 빌드 전에** 확정. 이후 변경 = 12,625편 전량 재처리.

---

## 0. VS Code 호출

```
@KNOWLEDGE_MODEL_SPEC.md 를 §8 매핑대로 구현해라.
순서: ①어휘 로더(표준 코드 앵커) → ②청크 메타 스키마 → ③그래프 노드/엣지 카탈로그 → ④개념배정 파이프라인.
기존 ONTOLOGY dict(src/knowledge/medical_ontology.py)·hierarchical_chunker·medical_graph 인터페이스는 유지(규칙10).
표준 어휘 파일이 없으면 "MISS"로 보고하고 다운로드 스텁만 만들어(규칙11). 임의 개념 발명 금지.
§9 결정지점은 구현 전에 사용자에게 확인.
```

---

## 1. 설계 원칙

1. **표준 앵커 우선** — 모든 개념은 가능한 한 코드(MeSH UID / UMLS CUI / SNOMED SCTID / ICD-10/11 / LOINC / RxNorm·ATC / HPO / MedDRA)를 갖는다. `code=None`은 "미앵커"로 표시하고 큐에 쌓아 후속 매핑.
2. **다축(multi-axial)** — 한 논문/청크는 여러 축에 동시 태깅(인구 × 질환 × 노출 × 결과 × 방법 × 분과). 단일 버킷 금지.
3. **고세분화 + 계층** — 각 축은 domain → subdomain → concept → (synonym/child)의 3~4층. 입도는 "검색·추론에 쓸모"가 기준.
4. **다학제 교차축** — `D_discipline`(분과)와 `D_mechanism`(기전)을 별도 축으로 둬서 *서로 다른 전공의 논문이 같은 기전/모집단으로 연결*되게 한다(=translational/cross-disciplinary 추론의 핵심).
5. **증거-정량 보존** — 관계(엣지)는 라벨만이 아니라 effect measure·방향·CI·n을 속성으로 싣는다. "연관 있다"가 아니라 "aOR 1.04 (1.02–1.06), cross-sectional, n=51k".
6. **버전·거버넌스** — 어휘/스키마는 `schema_version`을 갖고, 변경은 마이그레이션 기록. 개념 추가는 append-only.

---

## 2. 채택 표준 어휘 (축 → 표준 → 코드체계)

| 축 | 1차 표준 | 코드 | 비고 |
|---|---|---|---|
| 질환/증상 | MeSH, SNOMED-CT, ICD-10/11 | D-UID / SCTID / ICD | 임상 진단축 |
| 표현형 | HPO | HP: | 희귀질환·유전 |
| 노출/위험요인 | MeSH(+ExposureOntology) | D-UID | 행동·환경·직업·식이 |
| 중재 | SNOMED 'procedure', ATC | SCTID/ATC | 약물·수술·행동·기기·정책 |
| 약물 | RxNorm, ATC | RxCUI/ATC | 성분·제형·계열 |
| 검사/바이오마커 | LOINC | LOINC# | 랩·정량지표 |
| 유해사례 | MedDRA | PT/SOC | pharmacovigilance |
| 유전 | HGNC, Sequence Ontology, GO | HGNC/SO/GO | gene·variant·pathway |
| 방법/설계 | STROBE·CONSORT·PRISMA + 자체 method 어휘 | 내부 | 통계·인과 |
| 증거수준 | Oxford CEBM, GRADE | 내부 enum | level·certainty |
| 통합 ID | **UMLS CUI** | CUI | 위 모든 코드의 cross-walk 허브 |

> **UMLS CUI를 마스터 키**로: 각 개념은 `cui` 1개 + 출처별 코드 N개. 이것이 다학제 cross-walk를 가능케 함.

---

## 3. 온톨로지 축(Domain) 카탈로그 — 고세분화

> 각 개념 record 스키마(현 `ONTOLOGY` dict 확장):
> ```json
> "C_xxx": {"label":"", "cui":"C0000000", "mesh":"D000000", "snomed":"", "icd":"",
>           "axis":"disease", "parents":["C_yyy"], "synonyms":[...,"한글"],
>           "keywords":[...], "embed_centroid":null, "discipline":["cardiology","epi"]}
> ```

### A. D_population (인구·생애·특수집단)
life_stage(신생아/영아/소아/청소년/성인/노인) · sex/gender · race_ethnicity · 특수(임산부·면역저하·투석·중환자·장애·요양) · 사회경제(소득·교육·고용·지역·이주) · 직업군. 앵커: MeSH "Age Groups", SNOMED person/finding.

### B. D_disease (질환 — 신체계통별 세분)
순환기 · 내분비/대사(비만·당뇨·이상지질·MASLD) · 호흡기 · 소화기 · 신장/비뇨 · 신경 · 정신(우울·불안·수면·중독) · 근골격 · 혈액/종양 · 감염 · 면역/류마티스 · 피부 · 안과/이비인후 · 산과/부인과 · 주산기/선천. 앵커: ICD-10/11 chapter ↔ SNOMED ↔ MeSH.

### C. D_exposure (노출·위험요인)
행동(흡연·음주·신체활동·수면·스크린) · 식이/영양(가당음료·인공감미료·나트륨·식이패턴) · 환경(대기/수질/중금속·소음·온도) · 직업(교대·유해물질) · 약물성 · 유전성 · 심리사회(스트레스·고립·ACEs) · 의료(방사선·수혈). 앵커: MeSH, ExO.

### D. D_intervention (중재)
약물 · 수술/시술 · 행동/생활습관 · 기기 · 재활 · 정책/보험/규제 · 검진/스크리닝 · 영양. 앵커: SNOMED procedure, ATC.

### E. D_outcome (결과)
사망(전/원인별) · 이환(발생/재발) · 환자보고(PRO·삶의질·기능) · 바이오마커변화 · 의료이용(입원·재입원·응급) · 비용/경제 · 안전(AE·SAE) · 진단정확(민감도·특이도). 앵커: MeSH outcome, MedDRA(AE).

### F. D_biomarker_lab (검사·정량지표) — LOINC
혈당/HbA1c · 지질패널 · 간효소 · 신기능(eGFR) · 염증(CRP) · 호르몬 · 혈압/BMI/체성분 · 영상지표(유방밀도 등) · 유전/오믹스.

### G. D_drug (약물) — RxNorm/ATC
성분 · 계열(ATC L1~L5) · 제형 · 적응증 · 상호작용 · AE프로파일.

### H. D_genetics (유전·분자)
gene(HGNC) · variant(SO) · pathway(GO/KEGG) · expression · GWAS-trait. (MR/유전역학 지원)

### I. D_methodology (방법·통계·인과)
기술통계 · 회귀(선형/로지스틱/포아송/Cox/혼합) · 생존분석 · 성향점수/IPTW · 도구변수/MR · DID/ITS/RDD · 매개/조절분석 · 베이지안 · 메타분석 · 결측처리 · 민감도분석. 앵커: 자체 `methodology_terms`(현존) + STROBE 항목.

### J. D_study_design (설계 — STROBE/보고기준)
cross-sectional · case-control · cohort(전/후향) · nested CC · case-crossover · RCT(+2차분석) · trial-emulation/target-trial · SCCS · ITS · diagnostic-accuracy(STARD) · prediction/prognosis(TRIPOD) · MR · qualitative · systematic-review/MA(PRISMA).

### K. D_data_source (데이터 출처)
national-survey(KYRBS/KNHANES/KOSIS) · claims(NHIS/HIRA) · registry(KCCR…) · EMR · cohort(KoGES…) · trial · lab/omics · 문헌. (현 graph의 dataset 노드 확장)

### L. D_setting (의료 세팅)
1차/2차/3차 · ICU/응급/외래/입원 · 지역사회 · 학교/직장 · 원격.

### M. D_discipline (분과 — ★다학제 교차축)
cardiology · endocrinology · nephrology · neurology · psychiatry · oncology · infectious-disease · pulmonology · gastroenterology · pediatrics · ob-gyn · surgery · rheumatology/immunology · pharmacology · genomics · **epidemiology · biostatistics · health-policy · health-economics · public-health · preventive-medicine · nutrition · environmental/occupational-health · medical-informatics**. → 같은 기전/모집단을 공유하는 *다른 분과 논문*을 연결하는 데 쓴다.

### N. D_evidence (증거수준·비뱌어스)
oxford_level(1a~5) · grade_certainty(high/mod/low/verylow) · risk_of_bias(RoB2/ROBINS-I 도메인) · conflict_of_interest · funding_source.

### O. D_temporal (시간)
acute/subacute/chronic · time_horizon · follow_up_duration · exposure_window · induction/latency.

### P. D_mechanism (기전 — ★다학제 교차축)
pathophysiologic pathway(염증·인슐린저항·산화스트레스·내피기능·HPA축·신경전달·미생물군) · molecular(수용체·효소·유전자발현). → exposure→outcome을 *왜*로 잇는 매개층. translational 추론의 허브.

---

## 4. 개념 배정 파이프라인 (키워드 → 하이브리드)

현재: 키워드 문자열 매칭(crude). 업그레이드 3단:
1. **Dictionary match** (현존 keywords) — 빠른 1차.
2. **UMLS/MeSH 엔티티 링킹** — scispaCy `en_core_sci_*` + `EntityLinker(umls)` 또는 MetaMap Lite → 텍스트 멘션을 CUI로. (앵커 자동 부여)
3. **임베딩 centroid + LLM 검증** — 개념별 `embed_centroid`와 청크 임베딩 유사도 top-k, 경계사례만 LLM(get_llm_client, task="qa")이 확정. (의미 기반, 동의어/문맥 처리)
→ 출력: 청크/논문에 `concepts:[{cui, axis, score, method}]`. 점수·출처 보존(감사 가능).

---

## 5. 청크 메타 스키마 (전 필드 카탈로그)

`hierarchical_chunker.chunk_paper`가 청크마다 부여(현 section/role 확장):

| 필드 | 통제값/표준 | 예 |
|---|---|---|
| `section` | IMRaD+ (background/methods/results/discussion/limitation/funding/ethics) | "methods" |
| `subsection` | 자유+표준화 | "statistical analysis" |
| `rhetorical_role` | AZ/CoreSC enum (background/hypothesis/method/result/finding/interpretation/limitation/implication/comparison) | "finding" |
| `study_design` | §3-J enum | "cross-sectional" |
| `population` | §3-A concept CUI[] | ["C_adolescent"] |
| `exposure` / `outcome` / `intervention` | §3-C/E/D CUI[] | exposure=["C_zcb"] |
| `biomarker` / `drug` / `gene` | LOINC/RxNorm/HGNC | — |
| `statistical_method` | §3-I enum | "logistic regression" |
| `effect_measure` | OR/aOR/RR/HR/MD/SMD/β | "aOR" |
| `effect_estimate` | {value, ci_low, ci_high, p} | {1.04,1.02,1.06,0.001} |
| `sample_size` / `events` / `follow_up` | int/dur | 51000 |
| `covariates` | concept[] | [age,sex,BMI…] |
| `evidence_level` | §3-N | grade=moderate |
| `risk_of_bias` | RoB2/ROBINS-I 도메인 | — |
| `citation_density` | float(현존) | 0.08 |
| `discipline` | §3-M[] | [psychiatry,nutrition,epi] |
| `mechanism` | §3-P CUI[] | [inflammation] |
| `provenance` | pmid/doi/journal/year/section_char_span | — |

> 비어있는 필드는 `null`(거짓 채움 금지). 추출 신뢰도 `*_conf` 동반 가능.

---

## 6. 그래프 스키마 — 노드·엣지 카탈로그 (관계 온톨로지)

### 6.1 노드 타입 (현 paper/concept/dataset → 확장)
`Paper · Author · Journal · Dataset · Study · Concept(축별 subtype: Population/Disease/Exposure/Outcome/Intervention/Biomarker/Drug/Gene/Mechanism) · Finding · Hypothesis · Method · Guideline · Discipline`.
각 노드: `id, type, subtype(axis), cui, label, attrs`.

### 6.2 엣지 타입 카탈로그 (★ 평면태깅→패턴그래프의 핵심)
속성 공통: `weight, evidence_level, n_studies, provenance[]`. 정량관계는 `effect_measure/estimate/ci/p/direction` 추가.

| 범주 | 엣지 | from→to | 추가속성 |
|---|---|---|---|
| 서지/측정 | `REPORTS` | Paper→Finding | |
| | `USES_DESIGN` | Paper→Study_design | |
| | `USES_DATASET` | Paper→Dataset | |
| | `USES_METHOD` | Paper→Method | |
| | `MEASURES` | Study→Biomarker/Outcome | LOINC |
| 연관/인과 | `EXPOSURE_TO_OUTCOME` | Exposure→Outcome | effect_measure/estimate/ci/direction |
| | `RISK_FACTOR_FOR` / `PROTECTS_AGAINST` | Exposure→Disease | |
| | `MECHANISM_OF` | Mechanism→(Exp→Out) | |
| | `MEDIATES` / `MODERATES` / `CONFOUNDS` | Concept→edge | |
| | `DOSE_RESPONSE` | Exposure→Outcome | p_for_trend |
| 임상 | `TREATS` | Intervention/Drug→Disease | |
| | `CAUSES_AE` | Drug→AdverseEvent | MedDRA, freq |
| | `CONTRAINDICATED_WITH` / `INTERACTS_WITH` | Drug→Drug/Condition | |
| | `DIAGNOSES` / `PROGNOSTIC_FOR` | Biomarker→Disease | sens/spec/AUC |
| | `BIOMARKER_OF` | Biomarker→Mechanism | |
| 담론(과학적) | `SUPPORTS` / `CONTRADICTS` | Finding→Finding | |
| | `REPLICATES` / `EXTENDS` | Paper→Paper | |
| | `CITES` | Paper→Paper | |
| | `RESEARCH_GAP` | Concept↔Concept | (신규성 탐지 입력) |
| 다학제 교차 | `SHARED_MECHANISM` | Disease↔Disease | via Mechanism |
| | `SHARED_POPULATION` | Study↔Study | |
| | `TRANSLATES_TO` | Gene/Mechanism→Clinical_outcome | bench→bedside |
| | `SPANS_DISCIPLINE` | Paper→Discipline[] | |

### 6.3 다학제 추론이 가능해지는 예 (질의→그래프 traversal)
- "가당음료–우울, 다른 분과에서 같은 기전(염증) 쓰는 연구?" → `Exposure(ZCB)-EXPOSURE_TO_OUTCOME->Outcome(depression)`, `Mechanism(inflammation)-MECHANISM_OF->edge`, `SHARED_MECHANISM`로 cardiology/metabolic 논문 도달.
- "이 노출의 결과들에 dose-response 일관성?" → `DOSE_RESPONSE` 엣지 p_for_trend 집계.
- "신규성": 두 개념이 문헌에 `RESEARCH_GAP`(동시 출현 적음) → 후보 가설.
- "약물 안전신호": `Drug-CAUSES_AE->MedDRA` 빈도 + `EXPOSURE_TO_OUTCOME` RWE 교차.

---

## 7. 경우의 수 — 설계가 커버하는 연구 시나리오 (체크)
관찰연구(단면/코호트/환자대조) · RCT 2차분석 · target-trial emulation · 진단정확도 · 예측모형 · MR · 약물역학/안전신호 · 자연실험(정책) · 매개/조절 · 아형 이질성/정밀의학 · 메타분석 · 질적연구 · 다학제(translational: omics→clinical, 환경→대사, 정신↔대사 공유기전). → §3 축 + §6 엣지가 각 시나리오의 핵심 관계를 표현하는지 매핑표를 구현 시 첨부(규칙10).

---

## 8. 기존 코드 매핑 + 마이그레이션 (안 깨지게)

| 정의 | 현 코드 | 변경 |
|---|---|---|
| 어휘 | `medical_ontology.ONTOLOGY` dict + `_load_seed_extensions()` | record에 `cui/snomed/icd/axis/discipline` 필드 추가, 표준 로더(scispaCy/UMLS) 추가. `all_concepts()/extract_concepts()` 시그니처 유지 |
| 청크 메타 | `hierarchical_chunker.chunk_paper` meta | §5 필드 확장(없으면 null). `orchestrator._index_chunks`가 그대로 ChromaDB metadata로 전달 |
| 그래프 | `medical_graph.add_concept/link_paper_concept/link_concepts` | 노드 subtype·엣지 타입 enum 추가, `link_concepts(rel=...)` 인자화. 기존 HAS_CONCEPT/USES_DATASET 보존 |
| 배정 | `extract_concepts`(키워드) | §4 3단 하이브리드로 내부 교체(인터페이스 동일) |

마이그레이션: 스키마 확정 → **그 다음** FIX-3 인제스트(전문) + 그래프 재빌드. 순서 어기면 재처리. `schema_version` 박고 `reconcile_state.py`에 어휘/노드/엣지 카운트 추가.

---

## 9. 사용자(임상의) 결정지점 — 내가 정하면 안 되는 것

1. **표준 채택 범위**: SNOMED-CT(라이선스·방대) 풀 채택 vs MeSH+UMLS만(가볍게). 권장: **UMLS CUI 허브 + MeSH/LOINC/RxNorm/MedDRA**, SNOMED는 단계적.
2. **개념 입도**: 어디까지 쪼갤지(예 "우울" 한 개 vs PHQ 기반 중증도 분층). 검색 체감 vs 유지비 트레이드오프.
3. **분과(D_discipline) 목록 확정**: §3-M가 네 연구 스코프를 다 덮는지.
4. **엣지 신뢰 임계**: `EXPOSURE_TO_OUTCOME`를 단일 논문에도 그릴지, n≥k에서만 그릴지.
5. **자동추출 vs 사람검수**: 개념·관계 자동배정의 사람 승인 게이트 둘지.

---

## 10. 빌드 순서 + 검증

```
①§2 어휘 로더(표준 앵커) → ②§5 청크 메타 → ③§6 그래프 스키마 → ④§4 배정 파이프라인
→ (스키마 freeze) → FIX-6 임베딩 확정 → FIX-3 전문 인제스트 → 그래프 재빌드 → reconcile_state
```
검증:
```bash
python -c "from src.knowledge.medical_ontology import MedicalOntology as O; c=O().all_concepts(); print('concepts',len(c),'with_cui',sum(1 for x in c if x.get('cui')))"
# 청크 메타: 샘플 인제스트 후 ChromaDB 메타에 effect_measure/section/discipline 존재 확인
# 그래프: 엣지 타입 분포가 HAS_CONCEPT 외 EXPOSURE_TO_OUTCOME/MECHANISM_OF 등으로 다양화됐는지
python scripts/test_rag_smoke.py
```
판정: 개념의 `with_cui` 비율↑, 그래프 엣지 타입 ≥10종 출현, 청크 메타에 정량필드 채워지면 "정의가 실제로 작동".

> 이 문서의 축·관계는 표준에 앵커된 **출발 정의**다. §9를 네가 확정하면 그때 freeze하고 구현·인제스트로 간다.
