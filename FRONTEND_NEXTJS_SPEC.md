# FRONTEND_NEXTJS_SPEC — Next.js/React 풀 설계 (SEO + GEO 레이어링)

> 목적: Streamlit → Next.js 변환의 *코드 레벨 풀 설계*. `FRONTEND_MIGRATION_SPEC`(전략·서비스추출)·`UX_CHAT_DESIGN`(컴포저·출력)·`§5.5 스트리밍`을 구현 가능한 구조로.
> ★ 핵심 통찰: 이 앱은 **두 종류 표면**이다 — ① *공개 콘텐츠*(SEO/GEO 대상, 검색·AI엔진이 봐야 함) ② *인증 워크스페이스*(비공개, 색인 금지). **렌더링 전략을 이 둘로 가른다.**
> ★ GEO 시너지: 우리가 만든 provenance·인용·지식그래프(MeSH/UMLS)·E-E-A-T가 *정확히 GEO가 보상하는 것*. 신뢰성 레이어가 곧 GEO 자산.

---

## 0. 호출 / 원칙

```
@FRONTEND_NEXTJS_SPEC.md — web/ 를 Next.js App Router로 구축.
순서: ①디렉터리·라우팅 골격 → ②공개 레이어(SSG/ISR + SEO/GEO) → ③앱 셸(3-pane + SSE) → ④API 연결 → ⑤마이그레이션 매핑대로 기능 이식.
선행: FRONTEND_MIGRATION Phase1(서비스 추출) + Phase2(FastAPI SSE) 완료. React는 그 위에 올림.
워크스페이스는 색인 금지(noindex). SEO/GEO는 공개 콘텐츠 레이어에만.
```

원칙:
- **공개 = 서버 렌더(RSC/SSG/ISR)**, **앱 = 클라이언트(CSR + SSE)**. App Router로 한 코드베이스에서 분리.
- 의료 = **YMYL** → E-E-A-T(저자·인용·정확성·날짜) 필수. provenance/citation이 이걸 충족.
- 콘텐츠는 **인용 가능하게**(추출 친화: 결론 먼저·정의·표·PMID/DOI). GEO 목표 = "랭크"가 아니라 "인용됨".

---

## 1. 스택

| 영역 | 선택 | 이유 |
|---|---|---|
| 프레임워크 | **Next.js 15 App Router + TypeScript** | RSC로 공개/앱 렌더 분리, 메타데이터 API, ISR |
| 스타일 | **Tailwind** (sapphire 토큰 이식) | UX_CHAT_DESIGN 디자인 시스템 연속성 |
| 서버상태 | **TanStack Query** | API 캐시·재검증 (Streamlit session_state 대체) |
| 프리뷰 에디터 | **TipTap** (ProseMirror) | 토큰 스트리밍 write/erase + 인라인 편집 |
| 스트리밍 | **EventSource (SSE)** | §5.5 ChatEvent 소비 |
| 구조화데이터 | **schema-dts** (JSON-LD 타입드) | GEO 스키마 |
| 인증 | **JWT (httpOnly cookie)** | 공개/앱 경계 |

---

## 2. 라우트 레이어링 (★ SEO/GEO 아키텍처의 핵심)

```
web/app/
├─ (public)/                      ← SEO/GEO 레이어: SSG/ISR, 색인 O, 서버렌더
│   ├─ page.tsx                   /            랜딩 (제품 소개)
│   ├─ research/[slug]/page.tsx   /research/*  주제 해설·발표논문 (★GEO 핵심 콘텐츠)
│   ├─ concept/[cui]/page.tsx     /concept/*   지식그래프 엔티티 페이지 (MeSH/UMLS) ★GEO
│   ├─ methods/[slug]/page.tsx    /methods/*   방법론 설명 (survey-weighted 등)
│   ├─ about, pricing, blog/*
│   └─ layout.tsx                 공개 셸 (헤더/푸터, JSON-LD)
├─ (app)/                         ← 워크스페이스: CSR + SSE, noindex, 인증 필요
│   ├─ layout.tsx                 3-pane 셸 (좌 projects / 중 chat / 우 preview)
│   ├─ page.tsx                   /app         새 대화
│   └─ project/[id]/page.tsx      /app/project/* 프로젝트 워크스페이스
├─ api/                           ← BFF (필요시; 주 백엔드는 FastAPI 별도)
│   ├─ chat/route.ts              SSE 프록시 → FastAPI /chat
│   └─ auth/[...]/route.ts
├─ sitemap.ts  robots.ts          SEO
├─ llms.txt (public/)  llms-full.txt   ★GEO
└─ globals.css
```
- **(public)** 그룹: 정적/ISR, 메타데이터+JSON-LD. 검색·AI엔진 타깃.
- **(app)** 그룹: `export const dynamic = 'force-dynamic'`, `<meta robots="noindex">`, 인증 게이트. SSE 스트리밍.
- 두 그룹이 **다른 layout** → 공개는 마케팅 셸, 앱은 3-pane 셸.

---

## 3. 렌더링 전략 (레이어별)

| 라우트 | 전략 | 재검증 |
|---|---|---|
| `/` 랜딩 | SSG | 빌드 시 |
| `/research/[slug]` | **ISR** | 매 변경/3개월(GEO freshness) |
| `/concept/[cui]` | ISR (지식그래프에서 생성) | 그래프 갱신 시 |
| `/methods/*` | SSG/ISR | |
| `/app/**` | **CSR + SSE** (force-dynamic) | 실시간 |
- ISR(`revalidate`)로 공개 콘텐츠 신선도 유지(GEO 권장: 3개월↓). 그래프/논문 갱신 시 on-demand revalidate.

---

## 4. SEO 설계 (공개 레이어)

- **Metadata API**: 각 page `generateMetadata()` → title/description/canonical/OG/Twitter. 동적(논문 제목·초록).
- **`sitemap.ts`**: 모든 공개 라우트 + research/concept 동적 수집. **`robots.ts`**: 앱 noindex, 공개 allow, **AI 크롤러(GPTBot/ClaudeBot/PerplexityBot/Google-Extended) 허용**(GEO 전제).
- **시맨틱 HTML**: `<article> <h1..h3> <section> <time> <cite>`. heading 위계 정확.
- **Core Web Vitals**: RSC로 JS 최소, 이미지 `next/image`, 폰트 `next/font`. LCP/INP/CLS 통과.
- **다국어**(선택): ko/en `hreflang` (의학 영어 + 한국 사용자).

---

## 5. ★ GEO 설계 (AI 엔진 인용 최적화 — 우리 강점이 직결)

> 목표: ChatGPT/Perplexity/Google AI Overview/Claude가 우리 콘텐츠를 **인용·근거**로 쓰게.

**5.1 llms.txt (사이트 루트, GEO 표준)**
```
# /public/llms.txt
# Medical-Agent — clinical/translational research copilot
## Key content
- /research/[topics] : evidence-grounded medical research explainers (cited, PMID/DOI)
- /concept/[mesh]    : medical concept pages (MeSH/UMLS anchored)
- /methods/*         : survey-weighted analysis, STROBE, novelty methodology
## Crawling
Allow: GPTBot, ClaudeBot, PerplexityBot, Google-Extended
Sitemap: https://.../sitemap.xml
```
+ `llms-full.txt`: 핵심 페이지 풀텍스트(추출 친화). + 봇 요청 시 **마크다운 콘텐츠 협상**(`.md` 버전 제공).

**5.2 JSON-LD 구조화 데이터** (`schema-dts`, page별 주입)
| 페이지 | 스키마 |
|---|---|
| /research/[slug] | **`ScholarlyArticle` + `MedicalWebPage`** (author, citation[], datePublished, dateModified, about=MedicalCondition) |
| /concept/[cui] | **`MedicalCondition`/`MedicalEntity`** (code=MeSH, sameAs=UMLS) |
| /methods/* | `Article` + `HowTo` (분석 절차) |
| FAQ 블록 | `FAQPage` |
| 전역 | `Organization` + `WebSite`(SearchAction) |
> 의료 스키마(MedicalWebPage 등)는 E-E-A-T·정확성 신호. **citation에 실제 PMID/DOI** → provenance 레이어가 그대로 공급.

**5.3 추출 친화 콘텐츠 구조** (GEO 핵심)
- **결론·정의 먼저**(answer-first), 명확한 heading, 짧은 단락, 비교 표, FAQ 블록.
- **fact density**: 모든 주장에 통계·인용·고유 인사이트(빈 일반론 X). → 우리 Evidence Graph/RAG가 공급.
- "LLM이 그대로 따올 수 있는 문장" 형태로.

**5.4 E-E-A-T (YMYL 의료 — 필수)**
- **저자 표기**(임상의/연구자) + bio + ORCID. **모든 의학 주장에 인용**(provenance → 표면화).
- `dateModified` 표기 + 정기 갱신(freshness). 의학 정확성 면책·검토 표기.
- **엔티티 명료성**: MeSH/UMLS 코드로 개념 고정(/concept/[cui]) → AI엔진이 엔티티 인식.

**5.5 GEO 콘텐츠 엔진 (우리만의 각도)**
지식그래프 + 발표/공개 논문 → **자동으로 공개 콘텐츠 생성**:
- 지식그래프 concept 노드 → `/concept/[cui]` 페이지(정의·관련 노출-결과·근거 논문·인용).
- 파이프라인 산출 중 *공개 허용*한 것 → `/research/[slug]`(요약·방법·결과·인용, JSON-LD).
- provenance가 모든 숫자·인용에 출처 → **인용 가능·검증 가능 = GEO/E-E-A-T 만점 콘텐츠**.
→ 즉 신뢰성 레이어가 곧 GEO 콘텐츠 파이프라인. (단, 사용자 비공개 연구는 절대 공개 X — opt-in 발행만)

---

## 6. 앱 셸 (3-pane + 컴포저 + SSE) — UX_CHAT_DESIGN 구현

```
(app)/layout.tsx:
┌ Sidebar(좌) ─┬─ Chat(중, flex-col-reverse 하단고정) ─┬─ Preview(우, TipTap) ┐
│ RECENT       │ 메시지 로그(최신 아래)                  │ 섹션별 실시간 write  │
│ projects만   │ 활동 타임라인(status/tool 이벤트)        │ (SSE token→erase/diff)│
│ + 새 채팅    │ ───────────────────────────────────    │ Stats/Figures/Refs 탭 │
│              │ Composer: [첨부칩][모델▾][@ref] 입력 [↑] │ Export(docx+enl)      │
└──────────────┴────────────────────────────────────────┴───────────────────────┘
```
- **좌 = 프로젝트만**(가운데 X — 사용자 요구 명시). **중 = 채팅 하단고정**(`flex-direction:column-reverse`). **컴포저 = 단일 박스**(첨부칩·모델·@ref 내장, UX §4). **우 = TipTap 실시간 write/erase**(§5.5 token 이벤트).
- 첨부 = **프롬프트에 안 넣고** object store + RAG 인제스트 → 검색(컨텍스트/용량 한계 해소).

---

## 7. 컴포넌트 트리 (앱)
```
<WorkspaceLayout>
  <Sidebar><NewChat/><RecentProjects/></Sidebar>
  <ChatPane>
    <ActivityTimeline/>            // status/tool_start/tool_result
    <MessageLog reverse/>          // 하단고정
    <Composer>                     // UX §4
      <AttachmentChips/><ModelPicker/><RefInsert/><SlashMenu/><Input/>
    </Composer>
  </ChatPane>
  <PreviewPane>
    <StageProgress/>               // SCOPE→STATS→… (RESEARCH_PIPELINE)
    <TipTapManuscript/>            // 섹션별 SSE write
    <DockPanels: Stats|Figures|Tables|References|Export/>
  </PreviewPane>
</WorkspaceLayout>
```
구조화 출력 컴포넌트(UX §3): `<Callout> <ComparisonTable> <CitationChip> <StatCard> <FigureCard> <Collapsible>` = remark/MDX 플러그인.

---

## 8. 데이터·API 연결
- **백엔드 = FastAPI**(FRONTEND §5, 서비스 래핑). Next는 그걸 소비.
- 읽기/공개: RSC에서 직접 fetch(서버) → 캐시/ISR.
- 앱 상호작용: 클라이언트 `EventSource('/api/chat')` → Next route가 FastAPI SSE 프록시(인증 쿠키 부착).
- 상태: TanStack Query(프로젝트·refs·stats) + 로컬(컴포저 임시).
- **로직 0 in Next** — 전부 service/FastAPI. (규칙10)

---

## 9. 인증 / 공개·비공개 경계
- JWT httpOnly 쿠키. `(app)` 미들웨어로 게이트, 미인증 → `/login`.
- `(public)`은 무인증. 발행 콘텐츠만 공개, **사용자 연구 데이터는 절대 공개 라우트로 안 샘**(opt-in 발행 플래그).

---

## 10. 디렉터리 (web/)
```
web/
├─ app/ (위 §2)
├─ components/ {chat,preview,composer,public,ui}
├─ lib/ {api(fastapi client), sse, schema(json-ld), auth}
├─ public/ {llms.txt, llms-full.txt, og images}
├─ next.config.ts (output:'standalone' for Docker)
├─ tailwind.config.ts (sapphire 토큰)
└─ Dockerfile (HF Space sdk:docker)
```

---

## 11. 마이그레이션 매핑 (Streamlit → Next, 누락 0)
FRONTEND_MIGRATION §2 카탈로그를 라우트/컴포넌트로:
| Streamlit | Next |
|---|---|
| ez_home 채팅 | `(app)` ChatPane + SSE |
| 우측 프리뷰 | PreviewPane + TipTap |
| 첨부/모델/refs | Composer 컴포넌트 |
| 클래식 20화면 P분류 | 앱 패널·채팅 핸들러로 흡수 |
| A분류(자가진단/학습루프/지식관리) | **Streamlit admin 잔류**(공개 X) |
| export(docx+enl) | Export 패널 → FastAPI /export |
| (신규) 발행 콘텐츠 | `(public)/research`·`/concept` (GEO) |

---

## 12. 호스팅 / 캐싱
- **HF Space `sdk: docker`** + Next `output:'standalone'` 컨테이너 (HF 유지). 또는 공개 레이어는 Vercel(ISR 네이티브)·앱은 HF.
- ISR revalidate + on-demand(`revalidatePath`) — 그래프/논문 갱신 시.
- CDN 캐시: 공개 정적, 앱 no-store.

---

## 13. 빌드 순서 (strangler) + 검증
```
0. (선행) FRONTEND_MIGRATION Phase1 서비스추출 + Phase2 FastAPI SSE
1. web/ 골격 + (app) 셸 + SSE 채팅 → 1개 화면 패리티
2. Preview(TipTap)+Composer+패널 → 핵심 워크스페이스 패리티
3. (public) 레이어 + SEO/GEO(llms.txt/JSON-LD/sitemap)
4. GEO 콘텐츠 엔진(concept/research 자동생성)
5. 패리티 매트릭스(§11) 전행 ✓ → Streamlit 은퇴(admin만 잔류)
```
검증:
- **Lighthouse** (SEO/Perf/CWV ≥ 90), **Google Rich Results Test**(JSON-LD 유효), **llms.txt** 접근, robots에 AI봇 allow.
- 앱: SSE 토큰 스트림, 3-pane 동작, J3~J6 여정 green.
- 공개: `/concept/[cui]`·`/research/[slug]` 구조화데이터·인용 렌더, noindex가 앱에만.

---

## 14. 결정지점
1. 공개 콘텐츠 발행 범위: 지식그래프 concept 전부 vs 큐레이션? 사용자 연구는 opt-in만(고정).
2. 호스팅: 전부 HF Docker vs 공개=Vercel/앱=HF 분리(ISR은 Vercel이 유리).
3. 다국어(ko/en) 범위.
4. TipTap 편집 깊이: 풀 인라인 편집 vs 읽기+채팅편집.
5. admin(자가진단 등)을 Next로 옮길지 Streamlit 잔류(권장: 잔류).

> 요약: **한 코드베이스, 두 렌더 전략** — 공개(SSG/ISR+SEO/GEO, 우리 provenance/그래프가 인용가능 콘텐츠로 직결)와 앱(CSR+SSE 3-pane). 신뢰성 레이어가 곧 GEO 자산이라는 게 이 설계의 고유 강점이다.
> 선행은 FRONTEND_MIGRATION Phase1/2. 그 위에 이 web/를 올린다.
