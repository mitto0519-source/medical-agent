# SESSION_HANDOFF — VS Code(C:\dev) Claude 컨텍스트 리셋

> 세션이 흐려졌을 때 이 파일을 통째로 읽혀라. 사실만, 검증된 것만.

## 0. 지금 상태 (한 줄)
Medical-Agent = "바이브 논문" 코파일럿. Streamlit → **Next.js(`web/`) 전환 중**. 디자인 craft 배선 + 로그인까지 동작 단계. 리포는 **C:\dev**(OneDrive 밖 — 되돌림 트랩 때문에 이전함).

## 1. 실행 방법 (★ 단일 서버 아님)
두 개가 같이 떠야 한다:
- 프론트: `cd C:\dev\web && npm run dev` → :3000
- 백엔드: `uvicorn api.main:app --port 8000 --reload` → :8000
- 권장: `docker compose up` 으로 묶어 띄움(“하나만 켜짐” 실수 방지).
- 로그인 실패의 99%는 **백엔드 8000 미기동**. 확인: `http://localhost:8000/health`.

## 2. 로그인 사실 (검증됨)
- 라우트 `POST /auth/login` (api/main.py:83), 쿠키 `ma_token` `secure=False·samesite=lax`(localhost OK).
- 화이트리스트 `data/users.json`: `mitto0519@gmail.com`(super_admin), `misslonghorn46@gmail.com`.
- 프론트 `web/app/login/page.tsx` = 다크 atmosphere 글래스(CRAFT_SPEC §13 / UI_BLUEPRINT R2). 동작 정상.
- ⚠ 그 파일 `submit()` 주석에 깨진 반복 텍스트(`양식 양식 양식 X …`)가 섞여 있음 → **주석만 정리**(기능 코드는 정상: token localStorage 백업 + 150ms 대기 + `location.replace`).

## 3. 디자인 단일 원본 (이것만 따른다)
- `CRAFT_SPEC.md` — 토큰 아래 craft(Layer5/메시 atmosphere blur120/Surface3/border .08/radius/spacing/motion).
- `UI_BLUEPRINT.md` — 레퍼런스→결정→데모→컴포넌트 매핑 + 빌드 매니페스트 + QA 게이트.
- 토큰 실체: `web/app/globals.css`(:root + @layer) + `web/tailwind.config.ts`(sapphire/maroon/ink).
- 시각 레퍼런스(목업, OneDrive 폴더): `craft_landing/login/workspace/inline_figure/preview_modes_demo.html`.

## 4. 방금 배선한 것 (web/, 권위본 확인됨 / C:\dev 빌드 검증은 네가 할 것)
1. `globals.css` — 미정의였던 `.card`·`.stat-number`·`.stat-unit` + `.seg-group/.seg-btn` 추가(로그인·랜딩 깨짐 수정).
2. `app/login/page.tsx` — 라이트 → 다크 atmosphere 글래스.
3. `components/composer/Composer.tsx` — 이모지 구식 → craft(원형 그라데 send·attach/mic/모델 pill·@ref 바).
4. `components/PreviewPane.tsx` — 2모드 → **6모드 세그먼트 토글**(Preview/Compare/Edit/Tables/Figures/Sources). Edit=TipTap 배선, Tables/Figures/Sources=정직한 빈 상태.
5. `components/RecentSidebar.tsx` — 죽은 코드 → SlimRail 재export(중복 제거, 규칙10).

## 5. 트랩 / 금지 (반복 실수)
- **OneDrive 트랩**: OneDrive 폴더에서 작업하면 소스 되돌림/잘림. **반드시 C:\dev에서만.**
- **거짓 "통과" 금지(규칙11)**: 커밋 메시지의 "tsc+build 통과"를 곧이 믿지 말고, 머지 전 `cd web && npx tsc --noEmit && npm run build` 실제로 돌려라.
- **의료 figure = diffusion 금지**: 통계 그림은 실데이터 엔진(lifelines/matplotlib 벡터)만. 환각 차단.
- 컴포넌트가 토큰을 *실제로* 쓰는지 확인(정의만 하고 미적용 = 반복 실패 패턴).

## 6. 다음 (우선순위)
1. C:\dev/web 에서 `tsc --noEmit` + `npm run build` 실측 → 통과 확인 후에만 머지.
2. `PreviewPane` Tables/Figures/Sources에 `research_state` 실데이터 배선(현재 빈 상태 placeholder).
3. Phase 1: 채팅 turn에 research_state 매 턴 주입(주제 망각 버그) + native tool-use(인라인 figure 실호출).
4. 3개 라이브 테스트: ① 주제 기억 ② tool→preview 채움 ③ 모드 토글.
