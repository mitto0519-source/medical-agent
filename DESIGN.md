---
name: Medical-Agent Design System
version: 2.0.0
last_updated: 2026-05-27
theme: sapphire_glass        # Lovable-inspired glassmorphism (2026-05-27 도입)
source_of_truth: this file
applies_to:
  - app/streamlit_app.py    # 메인 UI
  - data/exports/Figure*.{png,pdf}  # 논문 figure
  - data/exports/ZCB_*.docx        # 논문 Word 본문

colors:
  # Clinical / epidemiology publication palette.
  primary:
    navy:    "#1f4e79"   # 메인 강조 (Male in figures, primary buttons)
    maroon:  "#7d2e2e"   # 보조 강조 (Female in figures, danger)
  neutral:
    text:        "#222222"
    text_subtle: "#555555"
    text_muted:  "#888888"
    border:      "#dddddd"
    surface:     "#ffffff"
    surface_alt: "#f7f7f9"
    panel_bg:    "#eef3f8"  # admin/info 패널
  semantic:
    success: "#1f6e3a"   # ✓ 표시·완료
    warning: "#a26b00"   # ⚠ stash 누적·쿼터 80%
    danger:  "#a02828"   # ✗ 실패·환각 차단
    info:    "#1f4e79"
  data_viz:
    # 논문 figure 전용 (matplotlib/seaborn). 변경 금지 (figure 재현성).
    male:     "#1f4e79"
    female:   "#7d2e2e"
    male_ci:  "#1f4e7922"   # 22 alpha
    female_ci: "#7d2e2e22"
    overall_diamond: "#000000"
    ref_line: "#000000"

typography:
  # 한글 + 영어 의학 표기 혼합 → Sans-serif 우선, 수식·통계엔 monospace
  sans:
    family:    ["Pretendard", "Apple SD Gothic Neo", "Malgun Gothic", "Nanum Gothic", "Noto Sans CJK KR", "system-ui"]
    fallback:  "sans-serif"
  serif:
    family:    ["Source Serif Pro", "Noto Serif KR", "Times New Roman"]
    fallback:  "serif"
    usage:     "논문 Word 본문(submission docx)에서만"
  mono:
    family:    ["JetBrains Mono", "Consolas", "Courier New"]
    fallback:  "monospace"
    usage:     "통계 결과 출력·코드·OR/CI 정렬"

  sizes:
    h1: "1.6rem"   # 페이지 타이틀
    h2: "1.2rem"   # 섹션 헤더 (논문 작업실 등)
    h3: "1.0rem"
    body: "0.95rem"
    caption: "0.85rem"
    metric: "1.5rem"  # 숫자 강조 (n=50,972)

  figure:
    # Figure 1/2/3 정확 매칭 (build_paper_figures.py와 동기)
    title_size: 12.0
    title_weight: "bold"
    axis_label_size: 11.0
    tick_size: 10.0
    value_annotation_size: 10.0

spacing:
  scale: [0, 4, 8, 12, 16, 20, 24, 32, 48, 64]   # px
  panel_gap: 16
  section_gap: 32
  paragraph_gap: 12
  dialog_padding: 24

radius:
  control: 4    # button/input
  card: 8       # panel/dialog
  badge: 12

components:
  button:
    primary:
      bg: "{colors.primary.navy}"
      fg: "white"
      hover_bg: "#163a5a"
    secondary:
      bg: "{colors.neutral.surface_alt}"
      fg: "{colors.neutral.text}"
      border: "{colors.neutral.border}"
    danger:
      bg: "{colors.semantic.danger}"
      fg: "white"

  panel:
    surface: "{colors.neutral.surface}"
    border: "1px solid {colors.neutral.border}"
    radius: "{radius.card}"
    padding: "{spacing.dialog_padding}"

  dialog:
    # @st.dialog 결과/그래프 팝업 표준
    width: "rem(56)"   # 약 900px
    padding: "{spacing.dialog_padding}"
    title_size: "{typography.sizes.h2}"
    actions_gap: "{spacing.panel_gap}"

  data_table:
    header_bg: "{colors.neutral.panel_bg}"
    row_alt_bg: "{colors.neutral.surface_alt}"
    border: "{colors.neutral.border}"

patterns:
  do:
    - "통계 결과는 항상 95% CI와 함께 보고 (Stata svy 표기: OR (95% CI lo–hi))"
    - "한국 의학 표기 + 영문 용어 병기: 청소년 우울 (Adolescent depression)"
    - "Figure 색상은 data_viz 팔레트만 — male=navy, female=maroon 고정"
    - "환각 차단 표기: '— pending Stata STEP 13 log' 또는 'memory_gate quarantine'"
    - "버튼 라벨에 동사부터: '계산하기'·'다운로드'·'저장'"

  dont:
    - "Figure에서 빨강(#ff0000) / 형광색 사용 금지 — 색맹 접근성 + 학술적 톤"
    - "통계 값을 텍스트로만 보고 (CI 누락) 금지"
    - "한자만 / 영문만 단독 사용 금지 — 모호한 의학 용어는 병기"
    - "데이터가 없으면 '— pending'으로 명시; 환각으로 채우지 말 것 (규칙 11)"

  citation:
    in_text: "Vancouver numbered: [1], [5-7], [10, 29]"
    list_format: "[index]. Authors. Title. Journal. Year;Vol(Issue):Pages."
    word_field: "EN.CITE (travelling library 임베드) — scripts/build_endnote_docx.py"

i18n:
  primary_locale: "ko-KR"
  document_locale: "en-US (논문 submission docx)"
  date_format: "YYYY-MM-DD"
  number_format:
    thousands: ","
    decimal: "."
    or_precision: 2          # "1.04 (1.02-1.06)"
    p_value: ["P < 0.001", "P = 0.001", "P = 0.026"]

accessibility:
  contrast_min: 4.5      # AA for normal text
  contrast_large: 3.0    # AA for large text (18pt+ or bold 14pt+)
  focus_outline: "2px solid {colors.primary.navy}"
  color_blind_safe: true # navy/maroon pair 검증

assets:
  figures_dir: "data/exports/"
  paper_template: "data/exports/ZCB_paper_v2.4_FINAL.md"
  stata_canonical: "data/exports/ZCB_v2.4_canonical.do"
  figure_data: "data/exports/figure_data.json"
---

# Medical-Agent Design System

이 문서는 Streamlit UI + 논문 산출물(figure, Word, EndNote) 일관성의 **단일 진리원**입니다.
YAML frontmatter는 기계 파싱용(`scripts/build_paper_figures.py`, `app/streamlit_app.py`가 참조),
본문은 인간/AI 판단 근거.

## 왜 필요한가

이전엔 Streamlit UI 색·논문 figure 색·Word 강조 색이 각자 따로 정해졌다. AI 코딩 에이전트가
새 화면·새 figure를 만들 때마다 '이 색을 써도 되나?'를 매번 추측했다. 그 결과:
- 같은 데이터를 다른 figure에서 다른 색으로 표현
- 버튼/라벨 명명 규칙 산발
- 통계 값 보고 시 CI 누락 사례 발생

→ DESIGN.md를 source of truth로 두면 AI가 매번 같은 기준으로 작업.

## 적용 원칙

1. **figure 재현성**: `data_viz.male`/`female` 색은 절대 변경 금지. 변경 시 모든 과거
   submission docx와 시각적 불일치 발생 → 동일 페이퍼 재제출에 혼란.
2. **데이터 무결성**: 통계는 항상 점추정 + 95% CI. p값은 < 0.001 / = 0.001 형식.
3. **환각 차단 표기**: 데이터 없으면 '— pending' 또는 '미확정'. 추정 값으로 채우는 것 금지.
   `feedback_full_layer_standard.md` 메모리 + 규칙 11 참조.
4. **이중 표기**: 한국 청소년 우울 (Korean adolescent depression) 같이 한·영 병기.
5. **접근성**: navy/maroon 페어는 색맹(red-green)에서도 구별 가능. 형광·순적색 금지.

## Section 1. Colors

(YAML 참조). 주요 사용 예:
- Streamlit 사이드바 강조 = `colors.primary.navy`
- 위험 경고 (LLM 쿼터 100%·환각 차단) = `colors.semantic.danger`
- 표 헤더 = `colors.neutral.panel_bg`
- Figure 1·2·3 = `colors.data_viz.*` (이외 사용 금지)

## Section 2. Typography

- 한글 우선 (Pretendard) — 의학 용어가 한·영 혼합이라 가독성 핵심
- 통계 값(OR/CI/p)은 monospace로 정렬 → Figure 3 forest plot의 텍스트 컬럼이 깨지지 않도록
- 논문 submission Word 본문은 serif (Source Serif Pro / Noto Serif KR) — 별도 export pipeline

## Section 3. Spacing & Layout

- 8px 그리드 베이스 (4의 배수)
- 패널 간격 16px / 섹션 간격 32px
- @st.dialog 팝업 너비 약 900px (모니터 한 화면에 결과+차트 동시 보이도록)

## Section 4. Components

### 4.1 통계 결과 팝업 (@st.dialog)

```python
@st.dialog("ANOVA 결과", width="large")
def show_anova_result(result):
    # 메트릭
    c1, c2, c3 = st.columns(3)
    c1.metric("F-statistic", f"{result.f:.3f}")
    c2.metric("p-value", f"{result.p:.4f}")
    c3.metric("N", f"{result.n:,}")
    # 그래프
    st.plotly_chart(result.boxplot_fig, use_container_width=True)
    # 다운로드
    st.download_button("결과 CSV", result.csv, "anova_result.csv", "text/csv")
    st.download_button("그래프 PNG", result.png, "anova_boxplot.png", "image/png")
```

### 4.2 다운로드 패턴

- CSV / DOCX / PDF / PNG / EndNote XML 5가지 표준
- 파일명 규칙: `{topic}_{view}.{ext}` (예: `ZCB_Figure3_forest.pdf`)

### 4.3 Figure 생성 컴포넌트

- 입력: `figure_data.json` (실데이터)
- 출력: PNG (300 dpi) + PDF (vector)
- 색·폰트·축 라벨 크기는 모두 YAML frontmatter 참조

## Section 5. Patterns — do / don't

(YAML 참조). 추가:

### do
- 사용자가 모르는 의학 용어는 첫 등장 시 풀어 쓰기 (BMI = body mass index)
- 진행 중인 작업은 spinner + 예상 시간 ("Claude로 첨삭 중… ~30초")
- 실패 시 친절 메시지 + 원문 오류 동시 표시

### don't
- "데이터가 없습니다"만 표시하지 말 것 — 왜 없는지 + 해결법 같이
- LLM 출력을 검증 없이 화면에 띄우지 말 것 — memory_gate 통과 후

## Section 6. 메타 / Lint 규칙

`scripts/design_lint.py` (예정):
- broken-ref: figure가 존재하지 않는 컴포넌트 토큰 참조
- contrast: data_viz 페어가 4.5:1 미만이면 경고
- orphan: 사용 안 되는 토큰
- section-order: components > patterns > i18n 순서 유지

## Section 7. 변경 절차

새 색·새 컴포넌트 추가:
1. 이 파일 frontmatter에 추가
2. 사용처(streamlit_app.py / build_paper_figures.py) 갱신
3. change_log 기록
4. (있다면) `scripts/design_lint.py` 재실행

색 **변경**은 figure 재현성 영향이라 신중. 변경 전:
- 기존 figure 영향 검토 (data/exports/Figure*.png 모두)
- ARCHITECTURE.md에 영향 모듈 표기
- 사용자 승인

## Section 8. AI 코딩 에이전트 사용법

Claude Code · Cursor · Streamlit chat이 새 화면·figure 만들 때:

1. **이 파일 frontmatter를 system prompt에 자동 주입** (구현 예정: skill로)
2. 토큰 참조 시 항상 `{section.key}` 표기
3. 새 색·새 폰트가 필요해 보이면 **먼저 frontmatter 검토** — 이미 있을 가능성 큼
4. frontmatter에 없는 패턴 새로 만들면 → 사용자에게 명시 후 추가

관련: [ARCHITECTURE.md](ARCHITECTURE.md) (모듈 레지스트리), `memory/feedback_full_layer_standard.md` (품질 표준).

---

## Section 9. Sapphire Glass theme (v2.0.0 — 2026-05-27)

> Lovable.dev 스타일에서 영감받은 **글래스모피즘 다크 테마**. 사용자 요청:
> "옛스럽지 않게, 사파이어 글라스 액션 카드 기준으로 깨끗하고 심플하게."
> 본 섹션은 streamlit UI 전용 (논문 figure/docx 양식과 무관).

```yaml
sapphire_glass:
  background:
    # 화면 전체 — 사파이어→마젠타 radial gradient
    primary:   "#0A0A1F"
    radial_from: "#1E1B4B"        # 사파이어 인디고
    radial_via:  "#7C3AED"        # 보라
    radial_to:   "#EC4899"        # 마젠타 핑크
    surface_dark: "#0F0F23"       # sidebar
    overlay_black: "rgba(0, 0, 0, 0.40)"

  glass:
    # 액션 카드/입력바/메뉴 표면
    bg:           "rgba(255, 255, 255, 0.06)"
    bg_hover:     "rgba(255, 255, 255, 0.10)"
    bg_active:    "rgba(255, 255, 255, 0.14)"
    border:       "rgba(255, 255, 255, 0.12)"
    border_focus: "rgba(124, 58, 237, 0.50)"   # 사파이어 글로우
    blur_px:      24
    radius_card:  "18px"
    radius_chip:  "999px"          # pill
    shadow_soft:  "0 8px 32px rgba(15, 15, 35, 0.40)"
    shadow_glow:  "0 0 24px rgba(124, 58, 237, 0.25)"

  text:
    on_dark:        "#F5F5FA"      # 본문 (옅은 화이트)
    on_dark_subtle: "#A3A3B8"      # 보조
    on_dark_muted:  "#6B6B7E"
    on_glass:       "#FFFFFF"

  accent:
    sapphire:  "#3B82F6"    # 액션 버튼 / Link
    cyan:      "#06B6D4"    # 보조 강조
    violet:    "#8B5CF6"    # 글로우
    mint:      "#10B981"    # 성공
    rose:      "#F43F5E"    # 위험

  spacing:
    page_padding: "24px"
    card_padding: "20px"
    card_gap:     "16px"
    sidebar_w:    "232px"

  typography:
    family: ["Inter", "Pretendard", "system-ui", "sans-serif"]
    title:  "1.5rem / 700"
    h2:     "1.1rem / 600"
    body:   "0.92rem / 400"
    caption: "0.80rem / 400"

  motion:
    transition_fast: "150ms cubic-bezier(0.4, 0, 0.2, 1)"
    transition_med:  "250ms cubic-bezier(0.4, 0, 0.2, 1)"
    hover_lift:      "translateY(-2px)"
```

### 컴포넌트 사양 (sapphire_glass)

- **Glass action card** — `background: glass.bg`, `backdrop-filter: blur(24px)`,
  `border: 1px solid glass.border`, `border-radius: 18px`. hover시 `glass.bg_hover`
  + `transform: hover_lift` + `box-shadow: shadow_glow`.
- **Project card (그리드)** — 16:10 비율 썸네일 위, 하단 제목+편집일자.
  hover시 ring(2px sapphire). published 배지(좌하단 chip).
- **Big input bar** (홈 메인) — 폭 720px, padding 16px, glass.bg, border focus시
  sapphire 글로우. 우측 `Build ▾` chip + 마이크/전송 icon.
- **Sidebar** — surface_dark, 232px 폭, item hover시 glass.bg, active=violet bg.
- **Split workspace** — 좌 chat 38% / 우 preview 62%, drag handle (양쪽 폭 조절).
- **Preview tab bar** — Manuscript / Figures / Tables / Supplement (4 chip tabs).
- **Manuscript preview** — Word 양식 1:1 (TNR 11pt, double-space, A4) on white card.

### 모듈

- `app/styles/sapphire_glass.py` — `inject_sapphire_glass()` → `st.markdown(<style>)`
  으로 한 번 주입. 모든 새 page 진입 시 호출.
- `app/pages/_lovable_home.py` — Lovable-style 홈 (사이드바+입력바+카드그리드)
- `app/pages/_project_workspace.py` — split chat + Word preview + figure/table toggle.

### 옛 UI 호환

기존 `app/streamlit_app.py` 본체는 살아있음 — 사이드바에 "New (sapphire)" 토글로
새 양식 진입. 점진 마이그레이션, 갑작스러운 변경으로 사용자 워크플로 깨지지 않게.
