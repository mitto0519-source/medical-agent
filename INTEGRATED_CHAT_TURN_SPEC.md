# INTEGRATED_CHAT_TURN_SPEC — 빠르고·정확하고·의료급인 한 턴 (전 스펙 통합)

> 목적: 흩어진 스펙(§5.5 스트리밍 · RESEARCH_PIPELINE · KNOWLEDGE_ACQUISITION · RELIABILITY · RESEARCH_STATE · AGENT_OUTPUT_UX)을
> **한 채팅 턴의 생애주기**로 통합. 단순히 빠른 게 아니라 **빠르면서 정확하고 의료급**.
> ★ 대원칙: **기본은 빠르게(스트리밍), 의료 안전이 요구하는 곳에만 멈춘다(hard gate).** 속도와 정확이 충돌하면 *의료에선 정확이 이긴다*.
> ★ 이 문서는 새 부품이 아니라 *연결 지도* — 모든 기존 모듈이 한 턴에서 어떻게 협력하는지.

---

## 0. 세 종류 시간 (속도↔정확의 해법)

| 종류 | 무엇 | 예 |
|---|---|---|
| **즉시(HOT, <300ms)** | 인지·계획·라우팅. 항상 빠름 | "이해함", plan 칩, 의도분류 |
| **흐름(STREAM)** | 초안·검색결과·status. 빠르고 흐름 | 산문 토큰, "PubMed 검색 중", RAG 카드 |
| **★경성 게이트(BLOCKING)** | 의료 안전상 *멈춰야* 하는 것 | 통계 실수치, 인용 실재, 과대주장 |
| **배경(BACKGROUND)** | 논블로킹 검증 → 사후 배지 | confidence, provenance, deep-verify |

→ 빠름은 HOT/STREAM이 책임지고, 정확은 경성 게이트가 책임진다. **둘을 레인으로 분리**해서 둘 다 얻는다.

---

## 1. 한 턴 생애주기 (단계별 — 레인·모듈·게이트·의료요소)

사용자: *"KYRBS 2023 카페인과 우울 분석해서 Results 써줘"*

| # | 단계 | 레인 | 모듈(기존) | 게이트 | 의료 요소 |
|---|---|---|---|---|---|
| 1 | URL/세션 보존, user msg 영속 | HOT | RESEARCH_STATE, _save_project | — | — |
| 2 | **의도 분류 + 라우팅** | HOT(<300ms) | intent_sensor, trigger_analyzer | — | casual/draft/stat/novelty/full 분기 |
| 3 | `status("이해함")` emit | HOT | §5.5 ChatEvent | — | 빈 화면 0 |
| 4 | 시스템 합성(슬림) | HOT | build_base_system **캐시분만** | — | persona+chat_style+DESIGN |
| 5 | **컨텍스트 획득** | STREAM | KNOWLEDGE_ACQUISITION router(T0→T1) | — | 로컬 RAG 충분? 아니면 라이브 PubMed |
| 6 | (필요시) **Deep Research 루프** | STREAM/BG | acquisition §11 | 비용·iter 한도 | 공백→라이브→내재화→재검색 |
| 7 | **★STATS 게이트** | **BLOCKING** | RESEARCH_PIPELINE S3, survey_weighted | ★숫자 먼저 | survey-weighted 실엔진, aOR/CI/n, 가정검사 |
| 8 | 숫자 확정 + provenance 핀 | (게이트 내) | provenance(dataset/registry ver) | ★재현성 | "이 숫자로?" 휴먼 확인(고위험) |
| 9 | **섹션 작성(스트리밍)** | STREAM | RESEARCH_PIPELINE S4, paper service | ★수치=state 인용 | Results→… 토큰 write, 발명 0 |
| 10 | 인용 삽입 | STREAM | references, acquisition | **★인용 실재 게이트** | PMID 실재 + claim_evidence_nli |
| 11 | 우측 아티팩트 write | STREAM | AGENT_OUTPUT_UX, TipTap | — | 실시간 작성, 버전드 |
| 12 | **검증(논블로킹)** | BACKGROUND | confidence, peer_reviewer, cost_optimizer | — | confidence 4축, STROBE, 변경분만 재검 |
| 13 | 배지 부착 | BACKGROUND | §5.5 badge | — | confidence 0.87, provenance, 경고 |
| 14 | 체크포인트 + 학습신호 | BACKGROUND | RESEARCH_STATE, SELF_EVOLUTION | — | 결과→Failure KB/골드/ranking |

→ 1~5는 빠르게 흐르고, **7·10만 멈춘다(의료 안전)**, 12~14는 뒤에서 따라붙는다. 사용자는 거의 항상 *흐름*을 본다.

---

## 2. 의도 라우팅 (2단계 — 빠른 분기)

```
intent_sensor(fast/Haiku) → 분류:
  casual_qa   → 바로 stream 답(게이트 없음). 가장 빠름.
  draft       → S4 섹션작성(단, 수치 있으면 STATS 게이트 선행)
  stat        → S3 STATS 게이트 필수
  novelty     → KNOWLEDGE_ACQUISITION novelty(라이브) + deep research
  full_paper  → RESEARCH_PIPELINE 전체(SCOPE→…→POLISH)
```
- 라우팅·오케스트레이션 = **Haiku**(빠름). 본문 작성 = Sonnet. 최고품질 명시 = Opus. (속도 레버)
- 분기로 **불필요한 게이트를 건너뛴다** — casual 질문에 STATS 게이트 안 검 = 빠름. stat 요청엔 반드시 검 = 정확.

---

## 3. ★ 경성 게이트 3개 (의료급의 핵심 — 빠름보다 우선)

| 게이트 | 언제 | 규칙 | 위반 시 |
|---|---|---|---|
| **숫자 먼저(STATS)** | 통계/수치 포함 응답 | 실엔진(survey-weighted) 산출 + state.results 핀 *전엔* 산문 금지 | 산문 작성 차단, "분석 먼저" |
| **인용 실재** | PMID/근거 인용 | 실재 PMID + claim_evidence_nli 일치 | 가짜/불일치 인용 차단, "확인 필요" |
| **과대주장** | 의학적 결론 | confidence 임계 미달 시 단정 금지 | "—로 보이나 검증 필요" 약화 |

> 이 셋은 *속도를 양보한다*. 의료에서 빠른 거짓 < 느린 진실. 단 게이트가 도는 동안도 `status`로 "통계 검증 중"을 보여줘 *체감*은 유지.

---

## 4. 연계 지도 (어느 스펙이 어디서 — 누락 0)

```
사용자 입력
 → §5.5 ChatEvent(전 구간 스트림 척추)
 → intent_sensor/trigger_analyzer(라우팅)
 → build_base_system + chat_style + DESIGN-LANGUAGE(주입, 슬림)
 → KNOWLEDGE_ACQUISITION(컨텍스트·deep research·novelty)
 → RESEARCH_PIPELINE(단계·STATS 게이트·섹션)
 → survey_weighted + provenance(정확·재현)
 → references + claim_evidence_nli(인용 실재)
 → RELIABILITY(confidence·cost_optimizer·STROBE, 배경)
 → AGENT_OUTPUT_UX(사고트레이스·아티팩트·옵션칩)
 → RESEARCH_STATE(상태·체크포인트) + SELF_EVOLUTION(학습신호)
 → FRONTEND_NEXTJS(3-pane 렌더) / DESIGN_GOVERNANCE(UI 강제)
```
모든 스펙이 한 턴에서 호출된다. **고아 0**: 새 연결은 audit_wiring로 확인.

---

## 5. 통제 가능성 (모든 게이트·루프 공통 — KNOWLEDGE_ACQUISITION §13 재사용)
한도(iter/cost/time) · 킬스위치 · 관측(events+provenance) · 휴먼 게이트(고위험) · 고아 0. 비개발자가 안심하고 맡기는 전제.

---

## 6. 검증 / 수용 (빠름 ∧ 정확 ∧ 의료급)
```
[빠름]   첫 status <300ms · 첫 토큰 <1.5s(casual) · 스트림 끊김 0
[정확]   STATS 게이트 통과 전 산문 차단 · 산문 수치 100% state.results 인용(발명 0)
         · 가짜 PMID 0 · survey-weighted 적용/명시
[의료급] confidence 표시 · provenance 100% · 과대주장 약화 · STROBE 충족
[연계]   한 턴에서 전 스펙 호출 확인(audit_wiring) · 고아 0
[통제]   킬스위치·한도·관측 동작
```

---

## 7. 한 줄
**빠름(HOT/STREAM) + 정확(경성 게이트 3) + 의료급(survey/provenance/confidence/STROBE)** 을 *레인 분리*로 동시 달성.
사용자는 즉시 반응하고 흐르는 채팅을 보지만, 숫자·인용·결론은 의료 안전 게이트를 반드시 통과한다.
이게 "빠르고 정확하고 제대로 의료 지원되는" 통합 턴이고, 흩어진 스펙들이 *여기서* 하나로 협력한다.
