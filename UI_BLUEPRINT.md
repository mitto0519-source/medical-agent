# UI_BLUEPRINT — Medical Agent 디자인 단일 원본 (Source of Truth)

> 흩어진 레퍼런스/스펙/데모를 *결정 잠금*으로 통폐합. VS Code(C:\dev)가 이 문서 1개만 읽고 빌드한다.
> 토큰 세부 = `CRAFT_SPEC.md` / 화면구조·IA = `FRONTEND_NEXTJS_SPEC.md` / 시각 증거 = 아래 데모 4개.
> ★ 완성도 = 이 문서 50% + 레퍼런스 옆에 놓고 픽셀 보정 50%(§5).

---

## 1. 레퍼런스 → 확정 결정 → 증거 데모 → Next.js 타깃
| # | 레퍼런스(네가 준 것) | 확정 결정 | 증명 데모 | Next.js 컴포넌트 |
|---|---|---|---|---|
| R1 | Lovable 대시보드 | 진입 hero: 메시 그라데이션 + 떠있는 글래스 입력 + 템플릿 카드 | `craft_landing_demo.html` | `app/(entry)/page.tsx` + `<Hero>` `<Composer>` `<TemplateGrid>` |
| R2 | World Forge 로그인 | 로그인=어두운 atmosphere + 가운데 글래스 카드 + 그라데이션 입장 | `craft_login_demo.html` | `app/login/page.tsx` + `<AuthCard>` |
| R3 | Lovable 채팅 로그 | 작업 요약 카드(Details/Preview+북마크)·메시지 액션행·Add reference 바·Build pill 컴포저 | `craft_workspace_demo.html` (좌) | `<ChatLog>` `<WorkCard>` `<MsgActions>` `<RefBar>` `<Composer>` |
| R4 | ChatGPT 인라인 이미지 | 채팅 중간 figure: "생성 중" 플레이스홀더 → 완성 figure 인라인 | `craft_inline_figure_demo.html` | `<InlineFigure>` (loading→rendered) |
| R5 | Lovable 프리뷰 토글 | 우측 패널 모드 분리: Preview·Edit·Tables·Figures·Sources | `craft_preview_modes_demo.html` | `<PreviewPane>` + `<ModeToggle>` |
| R6 | FigureLabs | 작업화면=밝은 톤 옵션, Before/After 비교, 산출물 퀄리티 | (workspace 우측 light paper) | `<ComparePane>` 라이트 테마 |
| R7 | ChatGPT 3-컬럼 | 좌 Nav · 중 Conversation · 우 Context/Preview | workspace 데모 구조 | `<AppShell>` 3-pane 그리드 |

## 2. 톤 분리 (확정)
- **진입(login/hero) = 다크 atmosphere**(딥네이비 메시, 신뢰감). R1·R2.
- **작업화면 = 다크 chat(좌) + 라이트 paper(우)**. R3·R6. (Edit/Preview는 라이트 paper, 채팅은 다크)
- 의료 클리셰(청진기·DNA·심전도) 금지. 배경 = 추상 데이터/지식그래프 텍스처만.

## 3. 잠긴 토큰 (CRAFT_SPEC 발췌 — 변경 금지)
```
Layer        L0 #09090B · L1 메시(radial×4 + blur120) · L2 .03 · L3 .05 · L4 (18,20,28,.92)
Border       rgba(255,255,255,.08)  (hover .16)  — 진한 선 금지
Radius       pill 999 · button 12 · card 14~24 · input 28 · hero 32
Spacing      12 · 20 · 32 · 48 · 64 · 96
Type         primary #E8EAF0 · secondary #9AA0B0 · muted #646A7A  (헤드라인만 흰/그라데)
Accent       gradient #2F5EFF → #4F7BFF (버튼·send), #22D3EE(포인트)
Shadow       거의 없음. 0 0 0 1px rgba(255,255,255,.04)
Motion       hover 180 · modal 220 · page 300 · 500+ 금지
Paper(light) bg #FbFbFd · text #1a1c22 · accent #2F5EFF · serif 본문 / sans 라벨
Figure       navy #1f4e79 · teal #3d7068 · maroon #7d2e2e · despine · vector
```

## 4. 컴포넌트 빌드 매니페스트 (shadcn 베이스, 우선순위 순)
1. `<AppShell>` — 3-pane 그리드(Nav 248 / Chat 44% / Preview) · IA 사이드바(R7)
2. `<Composer>` — textarea + ＋/Research▾/mic/원형 send (R1·R3 공통, 재사용)
3. `<ChatLog>` + `<WorkCard>`(Details/Preview seg+북마크) + `<MsgActions>` + `<RefBar>` (R3)
4. `<InlineFigure>` — loading(점격자 shimmer)→engine-rendered SVG + 액션(삽입/SVG/PNG/재생성) (R4)
5. `<PreviewPane>` + `<ModeToggle>` — Preview/Edit/Tables/Figures/Sources, Edit=contenteditable 동기화 (R5)
6. `<Hero>`/`<TemplateGrid>` (R1) · `<AuthCard>` (R2)

## 5. 디자인 QA 게이트 (DESIGN_GOVERNANCE 연동 — 머지 조건)
빌드 후 각 컴포넌트를 대응 데모/레퍼런스와 **나란히 놓고** 체크:
```
□ 메시 그라데이션 색 경계 안 보임(blur 120+)   □ border 보일듯말듯(.08)
□ 입력창 패딩/radius28/떠있는 오브젝트감         □ 카드 hover lift + 라디우스 일관
□ spacing 리듬(12·20·32·48)                     □ 회색 타이포 위계
□ figure=engine 렌더(diffusion 아님)·벡터        □ 모드 토글 active 그라데
□ motion ≤300ms                                  □ "Lovable/FigureLabs 옆에 놔도 안 어색"
```
PASS 아니면 머지 금지. 루브릭 = 레퍼런스 매칭.

---

## 6. 정직한 경계 (지금/다음)
- 데모 4개 = **시각 원본(목업)**. 실제 동작(Edit↔채팅 양방향 동기화, 인라인 figure 실호출, auth)은 *Next.js+상태관리에서 배선*해야 함.
- 빌드는 **C:\dev(VS Code)** 에서 일어남 — 이 OneDrive 폴더에선 문서·목업만 둠. VS Code가 이 BLUEPRINT + 데모 4개 + CRAFT_SPEC을 입력으로 컴포넌트화.
- 다음 한 수: VS Code에서 `<AppShell>`+`<Composer>`부터(§4 순서) shadcn으로 구현 → §5 게이트로 데모 옆 비교 → 통과분만 머지.
