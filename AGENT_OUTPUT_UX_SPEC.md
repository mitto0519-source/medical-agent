# AGENT_OUTPUT_UX_SPEC — 사고 트레이스 + 아티팩트 패널 + 인터랙티브 고도화

> 목표: Claude처럼 ① **사고 과정(추론 트레이스)** 출력 ② **오른쪽 아티팩트 패널**(논문이 팝업처럼 떠서 실시간 작성) ③ **가운데에서 옵션·그림·이미지를 주고받으며** 오른쪽 논문을 고도화 — 엣지 있는 디자인과 병행.
> 연계(중복 0): `UX_CHAT_DESIGN`(컴포저·구조화출력) · `FRONTEND_NEXTJS §6`(3-pane·TipTap) · `§5.5`(ChatEvent) · `RESEARCH_PIPELINE`(단계) · `RESEARCH_STATE`(아티팩트 버전).
> ★ 신규 = 이 3요소의 *상호작용 모델*. 셸·이벤트·컴포넌트 기반은 기존 스펙 재사용.

---

## 0. 호출 / 원칙
```
@AGENT_OUTPUT_UX_SPEC.md — §5.5 ChatEvent를 (a)사고트레이스 (b)아티팩트 (c)인터랙티브요소로 렌더.
사고트레이스는 *실제* 계획/툴/provenance 이벤트를 표면화(추론 연기·theater 금지).
아티팩트는 RESEARCH_STATE 버전과 동기. 가운데 인터랙션이 오른쪽 아티팩트를 mutate.
```
원칙:
- **가운데 = 사고·대화·선택(과정)**, **오른쪽 = 산출물(논문 아티팩트)**. 과정과 결과 분리.
- 사고 트레이스는 **진짜**여야 한다 — 실제 plan/tool/stats-gate/provenance를 보여주지, 그럴듯한 가짜 추론을 연기하지 않는다(의료 신뢰).
- 가운데 인터랙션(옵션·그림·이미지)이 **오른쪽 아티팩트를 직접 고도화**. 양방향.

---

## 1. 인터랙션 모델 (3-zone 의미)

```
좌: 프로젝트          가운데: 과정(대화+사고+선택)              오른쪽: 산출물(아티팩트)
                    ┌──────────────────────────┐         ┌──────────────────────┐
                    │ ▸ 사고 과정 (collapsible) │         │ 📄 논문 아티팩트       │
                    │   - 계획/단계/툴 호출       │ ──개선──▶│   TipTap 실시간 write  │
                    │   - 왜 이 결정인지(provenance)│        │   섹션별·버전드        │
                    │ 응답 텍스트(chat_style)     │ ◀─참조──│   diff/accept          │
                    │ [옵션 칩] [미니 다이어그램]  │         │ ─ Stat표·Figure 아티팩트│
                    │ [이미지 주고받기]            │         └──────────────────────┘
                    └──────────────────────────┘
```
- 가운데 인터랙션 → 이벤트 → 오른쪽 아티팩트 mutate(+사고트레이스가 "왜"를 기록).
- 오른쪽 아티팩트의 특정 부분 클릭 → 가운데로 "이 문장 고쳐줘" 컨텍스트 전달(역방향).

---

## 2. 사고 과정 (추론 트레이스) — Claude식, 단 *진짜*

**무엇**: 응답 전/중에 **접히는 "사고 과정" 블록**. 안에 *실제* 진행:
```
▸ 사고 과정  (기본 접힘, 클릭 펼침)
   · 의도 파악: novelty 체크 요청 (intent=novelty)
   · 계획: 로컬 RAG → 부족 시 PubMed 라이브 → 유사도/gap
   · 🔍 rag_search "KNHANES UPF depression" → 12 hits
   · 🌐 pubmed_search (라이브) → 8 papers (2023–2025)
   · ⚖ stats-gate: survey-weighted 필요 판단
   · 결론 근거: gap 점수 0.71, 선행 3편 (PMID…)
```
**매핑(§5.5 이벤트 → 트레이스 줄)**: `status`/`plan`/`tool_start`/`tool_result`/`warning` → 사고 블록의 타임라인 줄. 즉 **사고 트레이스 = 활동 이벤트의 사람이 읽는 형태**.
**진짜 원칙**: 여기 들어가는 건 *실제로 실행된* 단계 + provenance(model/dataset/registry/seed). **LLM이 "음 생각해보면…" 같은 가짜 추론을 쓰는 게 아니다.** 의료라 추론 theater = 위험. 트레이스는 감사 가능한 실제 결정 로그.
**디자인**: 작은 모노/뮤트 톤, 좌측 컬러바, 단계 아이콘. 펼침 시 부드러운 height 트랜지션. 기본 접힘(노이즈 X).

---

## 3. 오른쪽 아티팩트 패널 (Claude artifacts 패턴)

**무엇**: 산출물이 *대화 흐름과 분리된* 1급 객체로 오른쪽에 뜸. 타입:
| 아티팩트 | 렌더 | 상호작용 |
|---|---|---|
| 📄 Manuscript | TipTap, 섹션별 SSE write/erase | 인라인 편집·diff·accept/reject·"전체보기" |
| 📊 Stat table | 표 카드 | "프리뷰에 삽입"·재실행 |
| 📈 Figure | 이미지 + 캡션 | 삽입·재생성·다운로드 |
| 📚 References | 인용 리스트 | 추가/제거→인용번호 재계산 |
**버전드**: 각 아티팩트 = RESEARCH_STATE 체크포인트와 동기. **버전 토글**(v1↔v2)·롤백·브랜치(분석 A/B 나란히). Claude artifacts의 버전 슬라이더처럼.
**실시간 write**: `token{section}` 이벤트 → 해당 TipTap 노드 append, 수정 시 erase+rewrite(diff 하이라이트). "쓰다 지웠다 고도화" 체감.
**팝업 동작**: 데스크톱=우측 고정 패널, 모바일=풀스크린 시트(아티팩트 탭).

---

## 4. 가운데 인터랙티브 요소 (옵션·그림·이미지) — 아티팩트를 고도화

대화가 텍스트만이 아니라 **선택·시각 교환**으로 오른쪽을 움직임:

**4.1 옵션 칩 (선택지)**
에이전트가 갈림길에서 칩 제시 → 클릭 → 아티팩트 갱신:
```
"MASLD로 갈까요?"  [MASLD] [MetALD 분리] [NAFLD 유지]
"성별 상호작용 넣을까요?"  [넣기] [빼기]
```
→ 클릭 = 이벤트 → 파이프라인 단계 진행 + 사고트레이스 기록 + 오른쪽 manuscript/analysis_spec 갱신. (타이핑 없이 고도화)

**4.2 미니 다이어그램 (시각적 사고)**
study design·DAG(교란/매개)·PRISMA flow·forest를 *대화 안에 작게* 렌더(Mermaid/SVG). "이 인과구조 맞나요?" → 노드 클릭으로 조정 → analysis_spec 반영.

**4.3 이미지 주고받기 (Vision)**
- 사용자→: 차트/표 사진 업로드 → Vision 분석 → "이 표를 Results에 넣을까요?" → 아티팩트 삽입.
- 에이전트→: 생성한 figure를 카드로 → 클릭 삽입.
→ KNOWLEDGE_ACQUISITION의 이미지 인제스트 + Vision 블록 재사용.

**4.4 인라인 액션**
응답 문장 옆 hover 액션: "프리뷰에 반영" "근거 보기(provenance)" "다시" "더 깊게".

---

## 5. 고도화 루프 (가운데 ↔ 오른쪽 양방향)

```
사용자 메시지/옵션선택/이미지
   → 사고 과정(실제 plan/tool/provenance 스트림)        [가운데, 접힘 가능]
   → 응답 텍스트(chat_style: 결론먼저·짧게)              [가운데]
   → 오른쪽 아티팩트 mutate (token write/diff)           [오른쪽]
   → confidence/citation 배지 사후 부착(BACKGROUND)      [오른쪽]
오른쪽 문장 클릭 → "이 부분 이렇게" → 다시 가운데로(역방향 컨텍스트)
```
- RESEARCH_PIPELINE 단계와 결합: 각 단계가 사고트레이스 1블록 + 아티팩트 1갱신.
- 매 mutate = 체크포인트(되돌리기/브랜치 가능).

---

## 6. 엣지 디자인 (UX_CHAT_DESIGN 토큰 + 이 레이어)
- 사고 블록: 뮤트 모노, 좌 컬러바, 단계 아이콘, 부드러운 펼침. "기계가 생각 중" 느낌(Lovable 빌드로그).
- 아티팩트: 카드 그림자·라운드·버전 슬라이더·diff 하이라이트(추가=emerald, 삭제=취소선).
- 옵션 칩: pill, sapphire 1색 강조, hover lift. 다이어그램: 라인 클린. 전이: 토큰 write 커서·height 트랜지션.
- 1 강조색·일관 타입스케일·여백 — "디자이너가 설계한" 절제.

---

## 7. 컴포넌트 (FRONTEND_NEXTJS §7에 추가)
```
<ChatPane>
  <ReasoningTrace events=…/>        // §2 접이식, status/tool/provenance
  <Message body=… components=[Callout,OptionChips,MiniDiagram,ImageExchange,CitationChip]/>
  <Composer/>
<ArtifactPane>
  <ArtifactTabs: Manuscript|Stats|Figures|Refs/>
  <ManuscriptArtifact tiptap versionSlider diff/>   // RESEARCH_STATE 버전
  <ConfidenceBadge/><ProvenancePopover/>
```
이벤트 reducer: status/plan/tool→ReasoningTrace, token→ManuscriptArtifact, option→파이프라인 advance, badge→배지.

---

## 8. 검증 / 수용
- 사고 과정 = *실제* 이벤트(가짜 추론 0): 트레이스 각 줄이 events.db/provenance에 대응.
- 오른쪽 아티팩트가 token으로 실시간 write + 버전 토글/롤백.
- 옵션 칩 클릭 → 타이핑 없이 아티팩트 갱신 + 사고트레이스 기록.
- 이미지 업로드 → Vision 분석 → 아티팩트 삽입.
- 의료: 아티팩트 의학 주장에 confidence·citation 배지, 트레이스에 stats-gate 결정.

---

## 9. 결정지점
1. 사고 과정 기본 노출: 접힘(권장) vs 펼침.
2. 트레이스 상세도: 단계만 vs 툴 입출력까지(개발자 토글).
3. 아티팩트 편집 깊이: 풀 인라인(TipTap) vs 제안+채팅편집.
4. 옵션 칩 자동 제시 빈도(너무 잦으면 피로).

> 요약: **과정은 가운데(진짜 사고트레이스+옵션·그림·이미지), 산출은 오른쪽(버전드 아티팩트, 실시간 write).**
> 가운데 인터랙션이 오른쪽 논문을 고도화하는 양방향 루프 — Claude의 thinking+artifacts를 의료 논문에 맞춘 형태.
> 기반(이벤트·셸·컴포넌트)은 기존 스펙 재사용, 이 *상호작용 모델*만 신규.
