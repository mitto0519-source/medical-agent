# KNOWLEDGE_ACQUISITION_SPEC — on-demand 외부지식 획득 + 내재화 (백엔드)

> 목표: 필요할 때 PubMed/Semantic Scholar/Europe PMC/OpenLibrary 등에서 **RAG → 라이브 API → headless 크롤 → 다운로드+인제스트** 4티어로 가져와, *내재화*하고, novelty/유사성/트렌드 질의에 **결합**하는 백엔드 레이어.
> ★ 중복 0: 4티어 부품 대부분 이미 있음 — **통합 라우터 + headless 티어 + 내재화 writeback + 질의결합**만 신규.
> 연계: `RESEARCH_PIPELINE`(SCOPE/novelty 단계) · `SELF_EVOLUTION`(코퍼스 성장) · `KNOWLEDGE_MODEL`(인제스트·그래프) · `provenance`.

---

## 0. 호출 / 원칙
```
@KNOWLEDGE_ACQUISITION_SPEC.md — 기존 티어(evidence_reader/web_reader/oa_bulk_fetcher/novelty_checker/RAG)를
통합 라우터로 오케스트레이션. 새 검색기 만들지 마라(중복). headless 티어 + 내재화 writeback + 라우터만 신규.
법적: robots.txt/ToS 준수, OA만 다운로드, rate limit 준수(NCBI 키). 모든 획득물에 provenance.
```
원칙:
- **싼 것부터(decide-then-fetch)**: 로컬 RAG로 충분하면 외부 안 감. 필요할 때만 단계적으로 비싼 티어.
- **내재화(internalize)**: 라이브로 가져온 건 인제스트 → 다음엔 로컬. 코퍼스가 사용과 함께 성장.
- **결합(compose)**: 로컬 + 라이브를 dedup·랭크·합성. 질의처리에 native tool-use로 끼움.
- **provenance·법적 가드** 필수.

---

## 1. 4-티어 획득 (싼→비싼) + 기존 모듈 매핑

| 티어 | 무엇 | 속도 | 기존 모듈(재사용) | 신규? |
|---|---|---|---|---|
| **T0 RAG 로컬** | 누적 코퍼스 검색 | 즉시 | `service.rag.search_with_rerank`(PubMedBERT+rerank+HyDE) | — |
| **T1 라이브 API** | PubMed/SemScholar/EuropePMC/Crossref/OpenLibrary | 초 | `evidence_reader`(eutils/SS/EPMC/crossref 라이브)·`novelty_checker` | OpenLibrary 추가 |
| **T2 정적 크롤** | API 없는 단순 HTML | 초 | `web_reader`(requests+BS4) | — |
| **T3 headless 크롤** | JS 렌더·API 없는 사이트 | 느림 | (없음) Playwright 설치만 됨 | **★신규** |
| **T4 다운로드+인제스트** | 전문 확보→내재화 | 느림 | `oa_bulk_fetcher`→chunk→embed→graph | — |

> T3만 진짜 신규(Playwright를 *콘텐츠 크롤러*로 — 지금은 ui_eval 테스트용만). 나머지는 통합·확장.

---

## 2. 획득 라우터 (★신규 핵심 — 언제 무엇으로)

`src/acquisition/router.py`:
```python
def acquire(query: str, *, intent: str, recency_days=None, need_fulltext=False,
            owner_email="") -> AcquisitionResult:
    # 1) T0 로컬 먼저
    local = rag.search(query)
    if sufficient(local, intent, recency_days):      # 커버리지·신선도 충족?
        return combine([local])
    # 2) 신선도/커버리지 부족 → T1 라이브 API
    live = evidence_reader.multi_search(query, sources=pick_sources(intent))
    results = combine(local, live)                    # dedup(PMID/DOI)·rank
    # 3) 특정 소스 API 없음/JS → T2/T3 크롤 (필요시만)
    if need_crawl(query): results += crawl(url, headless=needs_js(url))
    # 4) 전문 필요 → T4 다운로드+인제스트
    if need_fulltext: download_and_ingest(top_dois, owner_email)
    internalize(live)                                  # §3 writeback
    return results
```
- `sufficient()`: 로컬 결과 수·평균 관련성·**최신 연도**(trend/novelty는 recency 필수) 판단.
- `pick_sources(intent)`: novelty→PubMed+SemScholar, trend→PubMed by-year, book→OpenLibrary, fact→EuropePMC.
- 단계마다 **provenance**(source, query, fetched_at) 기록.

---

## 3. 내재화 writeback (가져온 걸 다음엔 로컬로 — 코퍼스 성장)

`src/acquisition/internalize.py`:
- 라이브/크롤/다운로드 결과 → **dedup(PMID/DOI 기준, 이미 있으면 skip)** → `hierarchical_chunker` → PubMedBERT 임베딩 → chromadb 768d + 지식그래프 노드(Claim/EXPOSURE_TO_OUTCOME) → **provenance(source/fetched_at/query)**.
- 비동기(BACKGROUND lane, FRONTEND §5.5) — 질의 응답을 막지 않음.
- 결과: 자주 묻는 영역이 점점 로컬화 → 외부 호출↓, 속도↑. (KNOWLEDGE_MODEL §2 "지속 확대" + SELF_EVOLUTION 코퍼스 성장과 동일물 — 중복 금지, 통합.)

---

## 4. 질의처리 결합 — novelty / 유사성 / 트렌드 (native tool-use)

agentic_loop 툴로 노출(이미 pubmed_search/consensus_search/longitudinal_trend 있음 → 라우터 경유로 통일):
| 의도 | 호출 | 결합 로직 |
|---|---|---|
| **novelty** | `acquire(intent="novelty", recency_days=…)` | 로컬+라이브 PubMed/SemScholar 합집합 → 임베딩 유사도 → 지식그래프 `RESEARCH_GAP` → **novelty score + 실제 선행논문 리스트(PMID·provenance, 인용가능)** |
| **유사성** | `acquire(intent="similar")` | 결합 코퍼스 임베딩 top-k + cross-encoder rerank |
| **트렌드** | `acquire(intent="trend", by_year)` | PubMed 연도 윈도우 카운트 → 궤적/증가율 |
- **핵심**: 단정 금지 — novelty 결과는 *실제 검색된 선행논문*에 근거(앞선 "텍스트 연기" 사고 방지). 못 찾으면 "확인 필요 + 검증쿼리" 제시.
- RESEARCH_PIPELINE **SCOPE/novelty 단계**에서 라우터 호출 → state.gates.novelty 기록.

---

## 5. 소스 레지스트리 (API vs 크롤, rate limit, 법적)
| 소스 | 방식 | 한계/법적 |
|---|---|---|
| PubMed (NCBI eutils) | T1 API | rate ~3/s(키 없이)·10/s(NCBI_API_KEY). 메타/초록만 |
| Semantic Scholar | T1 API | 키 권장, rate limit |
| Europe PMC | T1 API + T4 OA 전문 | OA만 다운로드 |
| Crossref | T1 API | 메타·DOI |
| OpenLibrary | T1 API | 서지/도서 |
| 기타 (지침·사이트) | T2/T3 크롤 | **robots.txt/ToS 준수**, OA/허용분만 |
> 가드: rate limiter + 캐시(중복 호출 방지) + OA-only 다운로드(KNHANES 교훈 — 라이선스 위반 금지) + provenance.

---

## 6. 캐싱 / 신선도
- 질의-결과 캐시(TTL): 같은 질의 재호출 시 API 안 감(rate 절약). trend/novelty는 짧은 TTL(신선도).
- 내재화된 건 영구(로컬 RAG). 라이브 메타는 TTL 캐시.

---

## 7. Anti-duplication 매트릭스
| 필요 | 기존 | 처리 |
|---|---|---|
| 라이브 PubMed/SS/EPMC/Crossref | `evidence_reader` | 라우터가 호출(그대로) |
| novelty | `novelty_checker` | 라우터 intent=novelty로 통합 |
| 정적 크롤 | `web_reader` | T2 그대로 |
| 다운로드+인제스트 | `oa_bulk_fetcher`+chunker+graph | T4 그대로 |
| 로컬 검색 | `service.rag` | T0 그대로 |
| 코퍼스 성장 | KNOWLEDGE_MODEL 인제스트 | internalize가 재사용 |
| **라우터/headless/writeback** | (없음) | **신규(유일)**: `src/acquisition/{router,crawler_headless,internalize}.py` |

---

## 8. 검증 / 수용
```bash
python scripts/test_acquisition.py   # 신규: 로컬 충분→외부 안 감 / 신선도 부족→라이브 / dedup / provenance
# novelty 라이브: 실제 PubMed 호출되고 선행논문 PMID 반환(텍스트 연기 아님)
python -c "from src.acquisition.router import acquire; r=acquire('KNHANES UPF depression', intent='novelty', recency_days=365); print([p['pmid'] for p in r.similar])"
# 내재화: 라이브 결과가 chromadb에 추가됐는지(dedup) + provenance 존재
```
**수용**: ① 로컬 충분 시 외부 0(불필요 호출 X) ② novelty/trend가 *실제 라이브 결과* 근거(provenance) ③ 가져온 것 내재화(다음엔 로컬) ④ rate/robots/OA 가드 ⑤ 못 찾으면 단정 X + 검증쿼리.

---

## 9. 결정지점
1. headless(T3) 범위: 어떤 소스까지? (대부분 API 있어 T3 최소화 권장)
2. 자동 내재화 vs 사용자 승인: 라이브 결과를 자동 코퍼스化 vs 확인 후. (권장: 자동 + 저품질 필터)
3. 캐시 TTL: novelty/trend 신선도 vs API 절약 균형.
4. NCBI/SemScholar API 키 발급(rate↑).

---

## 10. 의존 / 선후
```
ez_home 네이티브 tool-use(선행) ─▶ acquire 툴 노출
service.rag(T0)+evidence_reader(T1)+web_reader(T2)+oa_bulk_fetcher(T4) ─▶ router(신규)
                                                          ├─▶ internalize(writeback) ─▶ chromadb+graph+provenance
                                                          └─▶ RESEARCH_PIPELINE novelty 단계 결합
                                                          (FRONTEND §5.5 BACKGROUND lane으로 비동기)
```
---

## 11. Deep Research 루프 (실시간 RAG 강화 — khoj deep-research 원리 차용, 코드 아님)

> 딥리서치 = 한 방 검색이 아니라 **반복으로 RAG를 실시간 강화**: 검색→공백탐지→라이브획득→내재화→재검색→합성.

```python
def deep_research(query, *, max_iters=4, cost_cap, coverage_target=0.8) -> Result:
    for i in range(max_iters):                  # ★한도(통제)
        hits = router.acquire(query, intent="evidence")      # T0→T1→…
        if coverage(hits) >= coverage_target: break
        gaps = detect_gaps(hits, query)         # 개념·연도·반대근거 공백
        router.acquire(gaps, need_fulltext=True)# 공백만 라이브 보강 + 내재화(§3)
        if spent >= cost_cap: break              # ★비용 상한(통제)
    return synthesize(hits, provenance=True)
```
- **실시간 RAG 강화 = 내재화 루프(§3) 결합**: 가져온 즉시 인제스트 → 다음 iter엔 로컬이 더 강해짐.
- **통제**: max_iters·cost_cap·coverage_target·킬스위치 + iter별 provenance.
- 연계: RESEARCH_PIPELINE SCOPE/novelty에서 호출, FRONTEND §5.5 BACKGROUND(응답 안 막음).

## 12. 논문 최신화/트렌드 Study 루프 (도메인판 "자동화" — 뉴스레터 아님)

> 범용 자동화·뉴스레터 X. **네 활성 주제의 최신 논문·트렌드·노벨티 변화를 주기적으로 study**.

```python
def currency_study(owner, *, topics=active_topics(owner), cost_cap, opt_in=True):
    for t in topics:
        latest = router.acquire(t, intent="trend", recency_days=180)  # 연도윈도
        internalize(latest)                       # 코퍼스 최신화
        update_state(t, novelty=novelty_shift(t, latest))  # RESEARCH_STATE.gates
        surface(owner, t, "신규 N편 / 트렌드↑ / novelty 재평가")  # 알림 아닌 study 카드
```
- 트리거: heartbeat(기존 인프라) 주기 + 채팅 on-demand("이 주제 최신 봐줘"). **opt-in·주제별**.
- 통제: cost_cap·주제 화이트리스트·빈도 한도·끄기. 결과=푸시알림 아닌 *study 카드*.
- 연계: heartbeat job 1개 추가(인프라 중복 X) + §3 내재화 + novelty 도구.

---

## 13. ★ 통제 가능성 규율 (비개발자용 — 모든 루프 공통, 누락 0)

루프는 강력한 만큼 위험(무한·비용폭주·조용한 오염). **모든 루프에 5개 강제**:
1. **한도** max_iters/cost_cap/time_cap — 무한 금지.
2. **킬스위치** ENV 또는 1버튼 즉시 정지.
3. **관측** events.db+provenance — "조용히" 도는 것 금지.
4. **휴먼 게이트** 고위험(대량 코퍼스 변경·큰 비용)은 승인 후.
5. **고아 0** `audit_wiring.py`로 호출부·출력처 연결 확인(규칙10).
> 이 5개가 "누락없이+연계완벽+통제가능"의 실체. 비개발자가 안심하고 맡기는 전제.

---

> 요약: 4티어 + **딥리서치 루프(실시간 RAG 강화)** + **최신화 study 루프(도메인 자동화)**, 전부 §13 통제 규율 위에서.
> khoj는 *원리 참고*만(AGPL 코드 복제 금지). 보강은 네 스펙·인프라에 재구현.
