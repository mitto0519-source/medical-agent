# DESIGN_GOVERNANCE_SPEC — DESIGN.md 강제 레이어 (lint·리뷰게이트·학습루프)

> 목표: 이미 좋은 `DESIGN.md`(토큰 단일 진리원)에 **강제(enforcement)**를 더한다 — omd 워크플로의 진짜 가치이자, **"AI가 자꾸 이상한 UI 만든다"의 구조적 해법**.
> ★ omd(oh-my-design, MIT)를 *의존성으로 도입하지 않는다*. 패턴만 기존 인프라에 꽂는다(peer_reviewer 게이트·SELF_EVOLUTION·prompt_loader).
> 연계: `DESIGN.md`(기준) · `UX_CHAT_DESIGN`/`FRONTEND_NEXTJS`(적용) · `SELF_EVOLUTION`(게이트·학습) · `RESEARCH_PIPELINE`(체크포인트 패턴).

---

## 0. 호출 / 원칙
```
@DESIGN_GOVERNANCE_SPEC.md — DESIGN.md를 *강제*하는 lint+리뷰게이트+학습루프를 기존 인프라에 배선.
새 리뷰어/학습루프 만들지 마라 — peer_reviewer 게이트·SELF_EVOLUTION 패턴 재사용.
리뷰는 "좋아보여요" 금지: 모든 BLOCK/WARN에 DESIGN.md 토큰 + 라인참조 근거. 수정 2라운드 하드캡.
```
핵심: DESIGN.md는 *기준*(있음). 빠진 건 **그 기준을 검사·강제·학습하는 루프**. 그게 vibe 리뷰를 *대조 작업*으로 바꿔 "이상한 UI"를 구조적으로 막는다.

---

## 1. 현황 — 있는 것 vs 빠진 것

| | 상태 |
|---|---|
| DESIGN.md 토큰 frontmatter (colors/typo/spacing/radius/components/do-dont/a11y/citation) | ✅ 있음(좋음) |
| sapphire_glass 테마 | ✅ 있음 |
| `design_lint.py` | ❌ **Section 6 "예정"** — 미구현 |
| 디자인 리뷰 게이트(라인참조/severity) | ❌ 없음 |
| preference 학습 루프(교정→DESIGN.md) | ❌ Section 7 수동 절차만 |
| 멀티에이전트 frontmatter 주입 | ❌ Section 8 "skill 구현 예정" |
| Next.js 토큰(Tailwind) 생성 | ❌ applies_to가 Streamlit만 |

→ 토큰은 다 있고 **강제·학습·전파가 빈다.** 이 4개를 채운다.

---

## 2. design_lint.py (Section 6 "예정" → 구현)

DESIGN.md frontmatter 대비 UI 산출물(HTML/JSX/CSS/streamlit) 결정론 검사:
| 검사 | 규칙 | severity |
|---|---|---|
| **color budget** | 팔레트(colors.*) 밖 색 리터럴 사용 | **BLOCK** + 라인참조 (예 "L42: #2563EB — 팔레트 밖") |
| **contrast** | text/bg 페어 < 4.5:1 (a11y) | BLOCK |
| **radius/spacing scale** | scale 밖 값(예 radius 7px) | WARN |
| **component state** | hover/focus/disabled 누락 | WARN |
| **broken-ref** | 존재 않는 `{section.key}` 참조 | BLOCK |
| **orphan token** | 정의됐는데 미사용 | FYI |
| **data_viz 색 변경** | male/female 색 변경(재현성) | BLOCK |
- 출력: `{severity, file, line, rule, msg, design_ref}` JSON + 사람용 리포트. **모든 지적에 라인참조 + DESIGN.md 토큰**.
- CI/pre-commit + 채팅 `/design-lint`로 호출.

---

## 3. 디자인 리뷰 게이트 (omd:designer-review 패턴 — peer_reviewer 재사용)

UI 산출물을 DESIGN.md와 대조. **새 리뷰어 X — `peer_reviewer` 루브릭 구조 재사용**(점수→디자인 항목):
- 항목: 타이포 위계 · color budget · radius scale · 컴포넌트 상태 · 모바일 반응형 · 간격 일관 · voice(microcopy).
- 결과: **BLOCK / WARN / FYI**, 전부 라인참조.
- **"좋아보여요" 금지**: PASS/FAIL마다 근거(토큰·라인) 필수. (= 의료의 "근거 없는 주장 금지"와 같은 규율)
- **수정 2라운드 하드캡**: 2라운드 안에 통과 못 하면 *구조 문제*로 보고 → 설계 회귀(무한 핑퐁 차단). cost_optimizer와 동일 정신(변경된 것만 재검).

## 3b. final-qa 게이트 (출고 직전)
8항목 루브릭(브랜드 일관·a11y·상태완결·카피정합·반응형·color budget·broken-ref·data_viz 무결성) 강제. 통과해야 ship. RESEARCH_PIPELINE의 POLISH 게이트와 동형.

---

## 4. preference 학습 루프 (omd:remember→learn — SELF_EVOLUTION 재사용)

교정을 흘려보내지 않음:
- **capture**: 사용자 교정("CTA에 대문자 금지") → `.design/preferences.md`에 pending 티켓(SELF_EVOLUTION ledger 패턴).
- **gate→fold**: 주기 검토 → DESIGN.md 해당 섹션에 fold. 단 **SELF_EVOLUTION 게이트 통과**(후보→검증→승격, 무단 덮어쓰기 X). 고위험(색·data_viz)은 사람 승인.
- 결과: DESIGN.md가 *정적 문서*가 아니라 **취향이 누적되는 학습 시스템**. (RESEARCH_STATE 자가학습 훅과 동일 원리 — 중복 금지, 통합.)

---

## 5. 멀티에이전트 주입 (Section 8 "예정" → 구현)

DESIGN.md를 모든 에이전트·UI task가 읽게:
- **prompt_loader**: UI/design task 진입 시 `DESIGN.md` frontmatter를 system에 주입(이미 prompt 합성 인프라 있음 — 거기 추가).
- **shim**: `CLAUDE.md`(있음)·`AGENTS.md`(있음)·`.cursor/rules/*`가 DESIGN.md 참조하도록 한 줄씩. → Claude Code/Codex/Cursor 전원 같은 기준.
- DESIGN.md 수정→커밋하면 전 채널 동시 반영. "내 에이전트는 알고 네 건 모르는" 제거.

---

## 6. Next.js 토큰 생성 (마이그레이션 연계)

- `applies_to`에 `web/` 추가.
- **DESIGN.md frontmatter → `tailwind.config.ts` theme 자동 생성**(단일 소스 → Tailwind 토큰). sapphire_glass §9 → Tailwind theme(색·radius·spacing·motion).
- 즉 토큰을 두 번 정의하지 않음 — DESIGN.md가 Streamlit CSS와 Next Tailwind 둘 다의 소스.
- design_lint를 `.tsx`/Tailwind class에도 적용(color budget = Tailwind 임의 색 `[#xxxxxx]` 금지).

---

## 7. Anti-duplication 매핑
| 필요 | 기존 | 처리 |
|---|---|---|
| 기준(토큰) | `DESIGN.md` | 그대로(강화만) |
| 리뷰 게이트 | `peer_reviewer` 루브릭 | 디자인 항목으로 재사용 |
| 2라운드 캡/선택재검 | `cost_optimizer` | 동일 정신 |
| 학습 fold | `SELF_EVOLUTION`(ledger/gate) | preference 티켓에 적용 |
| 주입 | `prompt_loader`/`build_base_system` | DESIGN.md frontmatter 추가 |
| **design_lint / tailwind-gen** | (없음) | **신규(유일)** |

---

## 8. 검증 / 수용
```bash
python scripts/design_lint.py app/ web/      # BLOCK 0건이어야 ship
# 리뷰 게이트: 팔레트 밖 색 심은 더미 → BLOCK + 라인참조 잡히나
# 학습 루프: 교정 1건 → preferences pending → 게이트 후 DESIGN.md fold
# 주입: UI task system prompt에 DESIGN.md 토큰 들어가나
# Next: tailwind.config가 DESIGN.md 토큰과 일치(생성)
```
**수용**: ① color budget 밖 색 = BLOCK(라인참조) ② 리뷰 PASS/FAIL에 근거 100%("좋아보여요" 0) ③ 2라운드 캡 작동 ④ 교정이 DESIGN.md로 fold(게이트 경유) ⑤ 전 에이전트가 DESIGN.md 주입받음 ⑥ Tailwind 토큰=DESIGN.md 단일소스.

---

## 6.5 ★ platform-mapping (Nothing Design Skill 차용 — 단일소스 → 다중타겟)

> 위험: Streamlit CSS와 Next Tailwind가 *토큰을 따로* 정의 → 드리프트. Nothing의 platform-mapping 패턴으로 봉쇄.
> 디자인 스킬 구조로 재구성(내용 그대로, 모듈화): `skills/medical_agent_design/SKILL.md` + `references/{tokens,components,platform-mapping}.md`.

`references/platform-mapping.md` = **DESIGN.md 토큰 1개 → 각 타겟 출력 매핑**:
| DESIGN.md 토큰 | Streamlit (CSS var) | Next.js (Tailwind) | (artifact) |
|---|---|---|---|
| `accent.sapphire` | `--sg-accent: #3B82F6` | `theme.colors.accent` / `bg-accent` | inline |
| `radius.card` | `--sg-radius-card: 18px` | `rounded-[18px]` | |
| `spacing.card_gap` | `gap: 16px` | `gap-4` | |
| `data_viz.male` | (figure_style) | (figure_style) | navy 고정 |
- 한 곳(DESIGN.md)만 바꾸면 Streamlit·Next·figure 전부 따라온다. design_lint가 *양 타겟 모두* color budget 검사(임의 색 = BLOCK).
- `references/components.md` = 버튼/카드/표/오버레이를 **상태(hover/focus/disabled/loading/empty/error)와 함께** 카탈로그 → 에이전트가 매번 추측 안 함.
- 효과: DESIGN.md(토큰) + DESIGN-LANGUAGE(craft) + 이 거버넌스를 **모듈형 design SKILL로 통폐합** + 마이그레이션 단일소스 보장.

---

## 8.5 ★ Figure Output Quality (FigureLabs급 산출물 — 데이터 vs 스키매틱 분리)

> 능력은 있음(`publication_figure_generator`·`figure_builder.kaplan_meier`·`medical_plots`). 목표 = *출판급 품질*.
> ★ 불변식: **LLM은 figure *명세*만, 렌더는 deterministic 엔진(matplotlib/Graphviz/SVG).** diffusion으로 의학 스키매틱 생성 금지(해부·기전 환각 = 의료 위험).

### A. 데이터/통계 figure (forest·KM·bar — 폴리시로 출판급)
| 레버 | 규칙 |
|---|---|
| 벡터 우선 | **SVG/PDF 주산출물** + 폰트 임베드. PNG는 미리보기 |
| 저널 규격 | 컬럼폭(mm)·최소폰트(pt)·DPI·포맷 = `journal_intel`에 저널별 테이블 |
| 색 | data_viz 팔레트만(navy/maroon 불변), 색맹+흑백 시뮬 통과 |
| 다패널 | A/B/C 축·스타일·폰트 일치 |
| 주석 완결 | n · p · CI · 유의표시 · 단위 · 범례 |
| 타입별 | forest=pooled diamond+ref line+weight · KM=numbers-at-risk+censoring tick |

### B. 개념 스키매틱 figure (study flow·기전·graphical abstract = FigureLabs 영역)
- **재건축 X**(전용 학습모델). 현실 경로:
  - **Graphviz / D2 / Mermaid → 깨끗한 벡터** (STROBE/CONSORT flow, 노출→경로→결과 박스-화살표). deterministic, 환각 0.
  - **큐레이션 의학 SVG 컴포넌트 라이브러리** 조합(장기·세포·화살표).
  - **FigureLabs/BioRender 외부 도구 통합**(일러스트는 그들이 낫다).
- diffusion 금지(의학 figure 환각 위험).

### C. Figure QA 게이트 (peer_reviewer 루브릭 재사용 — UI 게이트와 동형)
figure 산출 시 자동 검사, BLOCK/WARN + 근거:
- 벡터인가 · 폰트 임베드 · 저널 규격(폭/DPI/포맷) 준수 · data_viz 색 준수 · 색맹/흑백 안전 · 주석 완결(n/p/CI/단위) · 통계 일치(state.results 참조, numbers-before-prose).
- 통과 못 하면 "완료" 금지. ("좋아보여요" 금지 = figure에도 적용)

### D. 배선 (중복 0)
| 요소 | 기존 | 변경 |
|---|---|---|
| 통계 figure | `publication_figure_generator`·`figure_builder` | 벡터/저널규격/주석 강화 |
| 저널 규격 | `journal_intel` | figure spec 테이블 추가 |
| 스키매틱 | (없음/약함) | Graphviz/D2 엔진 + SVG 컴포넌트 lib (신규) 또는 외부 통합 |
| QA 게이트 | `peer_reviewer`·`cost_optimizer` | figure 항목 재사용 |
| 색·규격 토큰 | `DESIGN.md` data_viz/figure | 그대로(단일소스) |

> 요약: **통계 figure = 폴리시(벡터·저널규격·QA게이트)로 출판급 달성. 스키매틱 = Graphviz/SVG 또는 외부통합(재건축 X). LLM 명세→엔진 렌더 불변식.**

---

## 9. 펀치라인 (왜 이게 "이상한 UI" 해법인가)
지금까지 UI 리뷰가 "느낌이 좀…"이라 매번 다른 게 나왔다. **DESIGN.md(기준) + lint/리뷰게이트(강제) = 리뷰가 의견싸움이 아니라 *대조 작업*이 된다.** Component 락 이후 색·radius가 안 바뀐다 = "페이지마다 다른 서비스"의 구조적 해결. **Next.js 빌드 전에 이걸 깔면, VS Code가 만드는 UI가 DESIGN.md를 못 벗어난다** — 이상한 게 *구조적으로* 안 나온다.

> 요약: DESIGN.md는 이미 좋다. **lint + 리뷰게이트 + 학습 fold + 멀티에이전트 주입 + Tailwind 생성** 5개를 기존 인프라에 꽂으면, 기준이 *강제*되고 *학습*되며 *전파*된다. omd는 참고만, 도입은 네 인프라로.
