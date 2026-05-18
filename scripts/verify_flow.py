"""단계 플로우 연결 검증: 주제생성 → 신규성 → 타당성 배너 + 다음단계 버튼."""
import sys, asyncio
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

SS = Path("scripts/screenshots")
SS.mkdir(exist_ok=True)

async def main():
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1440, "height": 900})

        # 로그인
        await page.goto("http://localhost:8502", timeout=20000)
        await page.wait_for_load_state("networkidle", timeout=20000)
        await asyncio.sleep(2)
        await page.locator("input[type='text']").first.fill("mitto0519@gmail.com")
        await page.locator("button:has-text('접속하기')").click()
        await page.wait_for_load_state("networkidle", timeout=15000)
        await asyncio.sleep(3)
        print("✅ 로그인 완료")

        # ── 1. 논문 생산 파이프라인 페이지 ──────────────────────────────
        sidebar = page.locator("[data-testid='stSidebar'] button")
        await sidebar.filter(has_text="논문 생산 파이프라인").first.click()
        await asyncio.sleep(3)
        await page.wait_for_load_state("networkidle", timeout=10000)
        body = await page.inner_text("body")
        has_steps = all(f"{n}단계" in body for n in ["1", "2", "3", "4"])
        await page.screenshot(path=str(SS / "flow_01_pipeline.png"))
        print(f"{'✅' if has_steps else '❌'} 파이프라인 페이지 — 1~4단계 표시: {has_steps}")

        # ── 2. 연구 주제 생성 → 주제 생성 ────────────────────────────────
        # 사이드바 버튼은 "🔴  연구 주제 생성", 파이프라인 컨텐츠 버튼은 "📚 연구 주제 생성"
        # 사이드바만 정확히 타겟: [data-testid='stSidebar']로 스코프 제한
        await page.locator("[data-testid='stSidebar']").locator("button").filter(has_text="연구 주제 생성").first.click()
        await asyncio.sleep(2)
        await page.wait_for_load_state("networkidle", timeout=10000)
        await page.get_by_placeholder("예: 청소년 비만과 정신건강").fill("청소년 스마트폰 사용과 수면 질")
        # 메인 컨텐츠 영역으로 스코프 제한 (사이드바 "연구 주제 생성" 버튼과 충돌 방지)
        await page.locator("[data-testid='stMainBlockContainer'] button").filter(has_text="주제 생성").first.click()
        await asyncio.sleep(3)
        print("    → 주제 생성 중 (최대 2분)...")
        for _ in range(25):
            await asyncio.sleep(5)
            body = await page.inner_text("body")
            if "생성 완료" in body or "노출변수" in body or "오류" in body:
                break
        await page.screenshot(path=str(SS / "flow_02_topics_result.png"))
        body = await page.inner_text("body")
        topics_ok = "생성 완료" in body or "노출변수" in body
        print(f"{'✅' if topics_ok else '❌'} 주제 생성 결과 확인")

        # ── 3. 첫 번째 주제 expander 펼치고 신규성 확인 버튼 클릭 ────────
        # expander 클릭 (첫 번째 주제)
        main = page.locator("[data-testid='stMainBlockContainer']")
        expanders = main.locator("[data-testid='stExpander']")
        if await expanders.count() > 0:
            await expanders.first.click()
            await asyncio.sleep(1)
        # 메인 컨텐츠 안의 "신규성 확인" 버튼 (사이드바 버튼과 구분)
        nov_btn = main.locator("button").filter(has_text="신규성 확인").first
        if await nov_btn.count() > 0:
            await nov_btn.click()
            await asyncio.sleep(3)
            await page.wait_for_load_state("networkidle", timeout=10000)
            body = await page.inner_text("body")
            has_banner = "현재 프로젝트" in body
            on_novelty = "연구 제목" in body or "PubMed" in body
            await page.screenshot(path=str(SS / "flow_03_novelty_banner.png"))
            print(f"{'✅' if on_novelty else '❌'} 신규성 확인 페이지 이동")
            print(f"{'✅' if has_banner else '❌'} 현재 프로젝트 배너 표시")
        else:
            print("❌ 신규성 확인 버튼 없음 (expander 미펼침 가능성)")

        # ── 4. 신규성 확인 실행 ──────────────────────────────────────────
        await main.locator("button").filter(has_text="PubMed 신규성 확인").click()
        await asyncio.sleep(3)
        print("    → 신규성 확인 중 (최대 3분)...")
        for _ in range(30):
            await asyncio.sleep(6)
            body = await page.inner_text("body")
            if any(w in body for w in ["신규성 점수", "권고사항", "오류"]):
                break
        await page.screenshot(path=str(SS / "flow_04_novelty_done.png"))
        body = await page.inner_text("body")
        has_result = "신규성 점수" in body or "권고사항" in body
        has_next_btn = "논문 타당성 검증" in body or "타당성 검증으로" in body
        print(f"{'✅' if has_result else '❌'} 신규성 결과 수신")
        print(f"{'✅' if has_next_btn else '❌'} '다음 단계' 버튼 표시 (논문 타당성 검증)")

        # ── 5. 다음 단계 버튼 → 타당성 검증 페이지로 이동 ─────────────────
        next_btn = page.locator("button:has-text('논문 타당성 검증')").first
        if await next_btn.count() > 0:
            await next_btn.click()
            await asyncio.sleep(3)
            await page.wait_for_load_state("networkidle", timeout=10000)
            body = await page.inner_text("body")
            on_feas = "타당성 검증" in body and "주제 JSON" in body
            has_banner2 = "현재 프로젝트" in body
            # 배너에 신규성 점수 표시 확인
            has_score = "신규성" in body and "/10" in body
            await page.screenshot(path=str(SS / "flow_05_feasibility_with_banner.png"))
            print(f"{'✅' if on_feas else '❌'} 타당성 검증 페이지로 자동 이동")
            print(f"{'✅' if has_banner2 else '❌'} 배너 유지 (이전 주제 선택 유지)")
            print(f"{'✅' if has_score else '❌'} 배너에 신규성 점수 표시")
        else:
            print("❌ '논문 타당성 검증' 다음 단계 버튼 없음")

        await browser.close()
        print("\n=== 플로우 검증 완료 ===")
        print("스크린샷: scripts/screenshots/flow_01~05_*.png")

asyncio.run(main())
