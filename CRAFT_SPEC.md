# CRAFT_SPEC — Design Engineering Spec (Lovable급 완성도 조견표)

> 색상표가 아니라 **토큰 *아래* 단계의 craft 규칙.** Lovable/Linear/Vercel/Raycast가 세련돼 보이는 *실제* 이유.
> ★ 완성도 = 이 문서 50% + **레퍼런스(Lovable) 옆에 띄우고 픽셀 단위 반복 보정 50%**(§12). 문서만으론 안 나온다.
> 구현: **shadcn/ui** 베이스(Lovable 스택) + 아래 값. 미감: **딥네이비**(의료=신뢰), Lovable 핑크/오렌지 아님.

---

## 1. Layer Architecture (5층 — 화면을 층으로 쌓는다)
| 층 | 역할 | 값(딥네이비) |
|---|---|---|
| **L0 Background** | 순수 바닥 | `#09090B` / `#0B0B0F` |
| **L1 Atmosphere** | ★분위기(메시 그라데이션) | §2 |
| **L2 Content Surface** | 본문 면 | `rgba(255,255,255,.03)` |
| **L3 Floating Surface** | 떠있는 패널 | `rgba(255,255,255,.05)` |
| **L4 Interactive** | 입력·버튼 | `rgba(18,20,28,.92)` |
> 깊이 = 색이 아니라 *투명도 레이어* 쌓기. 한 화면에 이 5층이 다 있어야 깊이감.

## 2. ★ Atmosphere Layer = 메시 그라데이션 (싸구려↔Lovable 차이의 핵심)
직선 2색 금지. **여러 radial-gradient blob + 큰 blur**:
```css
.atmosphere {
  background:
    radial-gradient(900px 700px at 20% 15%,  #2F5EFFcc, transparent 60%),   /* royal blue */
    radial-gradient(1100px 850px at 80% 30%, #122B5Ecc, transparent 62%),   /* deep navy  */
    radial-gradient(1000px 800px at 50% 90%, #22D3EE55, transparent 60%),   /* cyan       */
    radial-gradient(800px 700px at 70% 80%,  #7C5CFF44, transparent 60%),   /* soft violet*/
    #0B1020;                                                                /* base       */
  filter: blur(120px);            /* ★색보다 blur가 중요 — 색 경계가 안 보여야 함 */
}
```
| Blob | 색 | 크기 |
|---|---|---|
| 1 | royal blue `#2F5EFF` | 900~1200 |
| 2 | deep navy `#122B5E` | 1000~1300 |
| 3 | cyan `#22D3EE` | 800~1000 |
| 4 | soft violet `#7C5CFF` | 800~1000 |
> 규칙: **색 경계가 보이면 실패.** blur 120px+, blob 4개+, 저채도 base 위. (의료=네이비/시안, 신뢰감)

## 3. Surface Architecture (카드 3종)
| Surface | 용도 | 값 |
|---|---|---|
| A Background card | 본문 카드 | `rgba(255,255,255,.03)` |
| B Panel | 패널 | `rgba(255,255,255,.05)` |
| C Floating | 입력창·모달 | `rgba(18,20,28,.92)` + backdrop-blur |
> 입력창 = Surface C(거의 불투명 다크) — atmosphere 위에 *떠있는 오브젝트*처럼.

## 4. Border System (초보가 망하는 곳)
| 나쁨 | Lovable |
|---|---|
| `1px solid #444` (보임) | `1px solid rgba(255,255,255,.08)` |
> **있는데 안 보여야 한다.** 진한 선 = 촌스러움. 전부 `rgba(255,255,255,.06~.10)`.

## 5. Radius Scale (매우 큼)
| 요소 | radius |
|---|---|
| Badge/pill | 999px |
| Button | 12px |
| Card | 24px |
| Input | 28px |
| Hero panel | 32px |

## 6. Spacing Rhythm (여유 = 세련됨)
```
12 · 20 · 32 · 48 · 64 · 96      (8/16/24 보다 한 단계 넓게)
```
> Lovable이 여유로워 보이는 이유. 빽빽하면 싸구려.

## 7. Typography Hierarchy (헤드라인 빼면 거의 회색)
| 등급 | 값 |
|---|---|
| Primary | `#FFFFFF` (헤드라인만) |
| Secondary | `#B4B4B8` |
| Muted | `#8A8A93` (라벨·캡션·placeholder) |
- Hero `Medical Research Agent` 40~56px/700. Sub `Transform Questions into Evidence, Analysis and Publications` muted.

## 8. Sidebar Spec
| 요소 | 값 |
|---|---|
| Workspace switcher | h40 · radius12 · pad 12×8 |
| Nav item | h36 · radius10 |
| Hover | `rgba(255,255,255,.06)` |
| Active | `rgba(255,255,255,.10)` |
> 절대 진한 색 active 금지. 옅은 흰색 오버레이만.

## 9. Input Box Engineering (Lovable 핵심 — 툴바 아닌 *오브젝트*)
| 속성 | 값 |
|---|---|
| Height | 96~112 |
| Width | 560~720 (중앙) |
| Radius | 28 |
| Surface | C (`rgba(18,20,28,.92)`)+blur |
| Border | `rgba(255,255,255,.08)` |
| 내부 | placeholder(muted) · `auto▾` pill · mic · send(원형) 한 줄 |
> "툴바"가 아니라 *떠있는 오브젝트*로 보여야 함.

## 10. Shadow Rule (거의 안 씀)
```
박스섀도 ❌  0 8px 40px rgba()   (초보)
✅  0 0 0 1px rgba(255,255,255,.06)  + 아주 약한 0 1px 0 rgba(0,0,0,.2)
```
> 그림자가 또렷이 보이면 실패. 깔끔함 = 그림자 *없음*에 가깝게.

## 11. Motion Spec
| 동작 | duration | easing |
|---|---|---|
| Hover | 180ms | cubic-bezier(.4,0,.2,1) |
| Modal | 220ms | |
| Page transition | 300ms | |
| 금지 | **500ms+** | (느려서 싸구려) |

## 12. ★ Reference-Matching QA Workflow (완성도의 나머지 50%)
문서대로 짜도 첫 draft는 어색하다. **반드시 반복 보정:**
```
1) shadcn + §1~11 값으로 빌드
2) lovable.dev/dashboard(또는 FigureLabs)를 *옆 화면에 띄움*
3) 나란히 비교하며 보정: atmosphere blur 정도 · border 가시성 · 입력창 패딩/radius ·
   사이드바 hover · spacing 리듬 · pill 배지 · 그림자 강도
4) "Lovable 옆에 놓고 어색하지 않은가" PASS까지 반복(보통 3~5회)
```
- DESIGN_GOVERNANCE 리뷰게이트 **루브릭 = 레퍼런스 매칭**(이 12개 항목 라인참조 체크).
- 이걸 *디자인 QA 프로세스*로 고정 — 완성도는 이 반복에서 나온다.

---

## 13. Medical Agent 적응 (Lovable 복제 X)
- 팔레트: Lovable 핑크/오렌지 → **딥네이비/로열블루/시안/소프트바이올렛**(신뢰감).
- Hero: `Medical Research Agent` / `Transform Questions into Evidence, Analysis and Publications` / `Ask a research question…`
- Template grid(아래): KNHANES · Meta-analysis · Systematic Review · Cohort Study · Publication Draft · Statistical Analysis (클릭=흐름 시작).
- 워크스페이스(작업 중)는 **밝은 톤**(FigureLabs, §6.4) — 진입=다크 atmosphere / 작업=라이트 의도 분리.

> 요약: 세련됨 = **Layer(5) + 메시 atmosphere(blur 120) + Surface(3) + 안 보이는 border + 큰 radius + 여유 spacing + 회색 위계 + 미세 motion**, 그리고 **레퍼런스 옆에 놓고 맞을 때까지 반복**.
> 이게 토큰표 아래의 *진짜 craft*고, shadcn으로 짓고 §12로 다듬으면 "색만 같은 싸구려"가 "Lovable급"이 된다.
