# DESIGN-LANGUAGE — craft 규칙 (디자이너처럼 생각하는 법)

> styleseed 방법을 흡수하되 **Toss 핀테크 미감이 아니라 임상 연구 도구 + sapphire_glass + 3-pane**에 맞춘 craft 규칙.
> 역할 분담: `DESIGN.md`=브랜드 토큰(무엇) · **이 문서=craft 규칙(어떻게)** · `DESIGN_GOVERNANCE`=강제(검사).
> ★ 목적: "제너릭 AI 출력"을 "엣지 있는 프로 UI"로. 규칙은 구체적일수록 AI가 잘 따른다.
> ★ Next.js 빌드 전에 확정 — design_lint가 이 규칙을 검사. 토큰은 `DESIGN.md` 참조(중복 정의 금지).

---

## 1. 색 절제 (Color Discipline)

- **강조색은 *오직 하나* — sapphire(`accent.sapphire #3B82F6`).** 나머지는 전부 그레이스케일/뉴트럴. 강조색은 *active/selected/primary action*에만. 무지개 금지.
- **순흑(#000)·순백(#FFF) 금지(텍스트).** 가장 어두운 텍스트 = `text.on_dark #F5F5FA`(다크) / 라이트면 #2A2A2A. 5단계 그레이만.
- **의미색은 의미일 때만**: success=mint, warning=amber, danger=rose. 장식으로 쓰지 마라.
- **★figure 색은 예외이자 불변**: `data_viz.male/female`(navy/maroon)는 *논문 재현성*이라 절대 변경·확장 금지(DESIGN.md). UI 강조색과 섞지 마라.
- 한 화면 색 예산: 강조 1 + 뉴트럴 5 + 의미색(필요시 1~2). 그 외 리터럴 색 = design_lint **BLOCK**.

## 2. 숫자·통계 표시 (의료 도구의 핵심)

- **숫자는 크게, 단위·라벨은 작게 — 2:1.** 예: `aOR 1.34`의 1.34는 크게(metric 1.5rem), "aOR"·"(95% CI 1.08–1.66)"는 작게(caption). 같은 크기 금지.
- **통계는 항상 점추정 + 95% CI 동반.** CI 없는 단독 숫자 = 금지(DESIGN.md 규율 + 환각 차단).
- OR/CI/p는 **monospace 정렬**(forest plot·표 컬럼 안 깨지게).
- p값 표기 고정: `P < 0.001` / `P = 0.001` / `P = 0.026`.
- 큰 수 천단위 콤마(`n = 50,972`). 소수 OR 2자리.

## 3. 카드 = 유일한 콘텐츠 그릇

- **모든 콘텐츠는 카드 안에. 페이지 배경에 직접 얹지 마라.** 카드(surface)와 배경(bg)의 대비 *그 자체가* 시각 구분선이다.
- sapphire_glass: 카드 = `glass.bg(흰 6%)` + `blur 24px` + `border 흰 12%` + `radius 18px`. 배경은 radial gradient.
- **그림자는 거의 안 보이게(opacity 4~8% / shadow_soft).** 그림자가 또렷이 보이면 *너무 강한 것*. hover시에만 `shadow_glow`(sapphire 25%) 살짝.
- 카드 안 여백 호흡: `card_padding 20px`, 카드 간 `card_gap 16px`. 빽빽 금지.

## 4. 컴포넌트 상태 완결 (4-피드백 — styleseed 흡수)

모든 데이터 컴포넌트는 **4가지 상태를 전부** 가진다(하나라도 빠지면 design_lint WARN):
1. **skeleton** — 로딩(스피너 대신 형태 유지). "Claude로 첨삭 중… ~30초" 식 예상시간.
2. **empty** — 빈 상태. "데이터 없음"만 X → *왜 없는지 + 해결법*(예: "KYRBS .sav 업로드 또는 — pending Stata STEP 13").
3. **error** — 친절 메시지 + 원문 오류 동시. 복구 액션.
4. **success** — 완료 토스트/체크.
- 인터랙티브 요소는 hover/focus/disabled 3상태 필수(focus = 2px sapphire outline, a11y).

## 5. 선택 UI 규칙 (카드 안 드롭다운 금지)

- **2~4개 옵션 = pill 토글**(radius_chip 999px). 드롭다운 X.
- **5개+ = 별도 패널/페이지.** 카드 안에 긴 셀렉트 박지 마라.
- 예: "MASLD/MetALD/NAFLD"(3개) = pill. "저널 선택"(다수) = 패널.
- (AGENT_OUTPUT_UX의 옵션 칩과 동일물 — 통합.)

## 6. 타이포 위계 (3단계로 충분)

- 채팅/UI: body(0.92rem) 기본, h2(1.1rem/600) 섹션, **거대 헤더(h1 큰 사이즈) 금지**(chat_style.md — 채팅에선 더더욱).
- 위계는 *크기보다 weight·여백*으로. 같은 화면에 폰트 사이즈 4종 이상 = 난잡.
- 한·영 의학용어 병기: "청소년 우울 (adolescent depression)". 한자/영문 단독 모호어 금지.

## 7. 레이아웃 — 정보 피라미드 (information pyramid)

- 위에서 아래로 **중요도 순**: 결론/핵심 수치 → 근거 → 보조. (chat_style "결론 먼저"와 동형.)
- 3-pane: 좌(프로젝트)·중(과정)·우(산출물) 역할 고정. 섞지 마라.
- 섹션 4종만: hero/요약 · 핵심지표 · 상세 · 보조. 무한 컬럼 금지.
- 간격: 8px 그리드(4의 배수). 섹션 32 / 패널 16 / 단락 12.

## 8. 모션 (절제)

- transition 150~250ms `cubic-bezier(0.4,0,0.2,1)`. hover lift `translateY(-2px)`.
- 토큰 스트리밍 write 커서 + 부드러운 height 트랜지션(사고블록/아티팩트).
- **모든 것에 hover 효과 금지**(styleseed 금지패턴) — 클릭 가능한 것만.

## 9. 금지 패턴 (forbidden — 어기면 BLOCK/WARN)

- 순흑/순백 텍스트, 강조색 2개+, 무지개 의미색.
- 또렷한 그림자(8%+), 카드 밖 콘텐츠, 카드 안 드롭다운(5개+).
- CI 없는 통계 단독 표기, figure에 빨강/형광/data_viz 외 색.
- 거대 채팅 헤더, 폰트 사이즈 4종+, 모든 요소 hover.
- 빈 상태에 "데이터 없음"만, 로딩에 맨 스피너(skeleton 없이).
- 숫자=단위 동일 크기, 임의 spacing(scale 밖 값).

## 10. 적용 / 강제

- **토큰**: `DESIGN.md` 참조(여기서 색·간격 재정의 금지).
- **검사**: `DESIGN_GOVERNANCE`의 design_lint + 리뷰게이트가 이 문서 규칙을 라인참조로 검사.
- **컴포넌트**: Next.js `web/`에서 styleseed shadcn 구조(Radix+CVA) 차용 → sapphire로 리스타일, 이 규칙 준수.
- **주입**: prompt_loader가 UI task에 `DESIGN.md` 토큰 + 이 craft 규칙을 system에 주입.

---

## 흡수 체크리스트 (styleseed → 내 것)
- [x] craft 규칙(이 문서) — Toss 미감 제외, 임상+sapphire로 적응
- [ ] 컴포넌트 토대: styleseed shadcn primitive/pattern 구조 차용 → web/ 리스타일
- [ ] UX 스킬: /ux-flow·/ux-audit(Nielsen)·/ux-copy·/ux-feedback → DESIGN_GOVERNANCE/skills에 흡수
- [ ] (안 함) Toss seed 통째 복사 — 정체성 충돌

> 요약: styleseed의 *방법*(구체 craft 규칙 + 컴포넌트 구조 + UX-law)을 흡수하되, *Toss 비주얼*은 버리고 **임상+sapphire 정체성**으로 적응. 이 문서가 DESIGN.md(토큰)과 DESIGN_GOVERNANCE(강제) 사이의 빠진 "craft 층"이다.
