# web/ — Next.js Frontend (Phase 3 골격)

> 선행: FRONTEND_MIGRATION_SPEC Phase 1 (서비스 추출, 완료) + Phase 2 (FastAPI SSE, 완료).
> 본 디렉토리는 Phase 3의 **골격**입니다. 패리티 매트릭스 (§7) 채우기는 다음 사이클.

## 구조 (FRONTEND_NEXTJS_SPEC §2)

```
web/
├─ app/
│   ├─ layout.tsx                  Root (Pretendard + sapphire_glass base)
│   ├─ globals.css                 Tailwind + DESIGN-LANGUAGE craft 규칙
│   ├─ (public)/                   ← SEO/GEO, SSG/ISR, 색인 O
│   │   └─ page.tsx                  랜딩 (JSON-LD ScholarlyArticle/WebSite)
│   ├─ (app)/                      ← Workspace, CSR + SSE, noindex
│   │   ├─ layout.tsx                3-pane 셸 (좌 RECENT / 중 Chat 하단고정 / 우 TipTap)
│   │   └─ page.tsx                  채팅 + 사고 트레이스 + 컴포저
│   ├─ robots.ts                   AI 크롤러 명시 허용 (GEO 전제)
│   └─ sitemap.ts                  공개 라우트만
├─ components/                     chat/preview/composer (Phase 3 다음 사이클)
├─ lib/
│   ├─ api.ts                      FastAPI 18 routes 호출 wrapper
│   └─ sse.ts                      streamChat — ChatEvent generator 소비
├─ public/
│   └─ llms.txt                    ★ GEO 표준 — AI 엔진에 사이트 안내
├─ next.config.ts                  standalone (Docker/HF Space sdk:docker)
├─ tailwind.config.ts              sapphire_glass 토큰 + DESIGN-LANGUAGE 라운드 스케일
├─ tsconfig.json                   strict + @/* path alias
└─ package.json                    Next 15 + React 19 + TanStack Query + TipTap
```

## 실행

```bash
cd web
npm install            # 의존성
# FastAPI 백엔드 별도 실행
uvicorn api.main:app --reload --port 8000
# Next dev
npm run dev            # http://localhost:3000
```

`NEXT_PUBLIC_API_BASE` 환경변수로 FastAPI 위치 지정 (기본 http://localhost:8000).

## 디자인 강제

빌드 전 `python -m src.design.design_lint web/` 실행 — 팔레트 밖 색·라운드 비표준·broken-ref 차단.

## 다음 사이클 작업

- [ ] `/research/[slug]`, `/concept/[cui]` 동적 페이지 + ISR + JSON-LD
- [ ] components/preview/TipTapManuscript.tsx (섹션별 SSE token append)
- [ ] components/composer/Composer.tsx (첨부칩·모델·@ref·슬래시메뉴)
- [ ] 인증 미들웨어 (/app/** JWT 게이트)
- [ ] Dockerfile + HF Space sdk:docker 배포
- [ ] Lighthouse + Google Rich Results Test 검증
