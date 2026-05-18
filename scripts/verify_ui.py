"""헤드리스 브라우저로 Streamlit 주제 생성 UI 검증."""
import sys, asyncio
sys.stdout.reconfigure(encoding='utf-8')
from pathlib import Path

SS = Path("scripts/screenshots")
SS.mkdir(exist_ok=True)

async def main():
    from playwright.async_api import async_playwright

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1400, "height": 900})

        print("[1] 로그인...")
        await page.goto("http://localhost:8502", timeout=15000)
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.locator("input[type='text']").first.fill("mitto0519@gmail.com")
        await page.locator("button:has-text('접속하기')").click()
        await page.wait_for_load_state("networkidle", timeout=10000)
        await asyncio.sleep(3)
        print("    OK")

        print("[2] 연구 주제 생성 페이지 이동...")
        await page.locator("[data-testid='stSidebar'] button").filter(has_text="연구 주제 생성").first.click()
        await asyncio.sleep(3)
        print("    OK")

        print("[3] 연구 포커스 입력...")
        await page.mouse.click(565, 310)
        await asyncio.sleep(0.5)
        await page.keyboard.type("청소년 비만과 수면")
        await asyncio.sleep(1)
        await page.screenshot(path=str(SS / "A_filled.png"))
        print("    OK → A_filled.png")

        print("[4] 주제 생성 버튼 클릭...")
        await page.mouse.click(428, 366)
        await asyncio.sleep(2)
        await page.screenshot(path=str(SS / "B_spinner.png"))
        body = await page.inner_text("body")
        if "생성 중" in body:
            print("    ✅ 스피너 확인 — 생성 진행 중")
        else:
            print("    ⚠ 스피너 미감지 — B_spinner.png 확인")

        print("[5] 결과 대기 (최대 5분)...")
        DONE_WORDS = ["완료", "생성된 주제", "노출변수", "오류", "[1]", "exposure", "Associations"]
        for i in range(60):  # 5초 × 60 = 5분
            await asyncio.sleep(5)
            body = await page.inner_text("body")
            if any(w in body for w in DONE_WORDS):
                print(f"    결과 감지! ({(i+1)*5}s)")
                break
            if i % 6 == 5:
                await page.screenshot(path=str(SS / f"wait_{(i+1)*5}s.png"))
                spinner_on = "생성 중" in body
                print(f"    {(i+1)*5}s {'(스피너 작동 중)' if spinner_on else '(완료?)'}")

        await asyncio.sleep(2)
        await page.screenshot(path=str(SS / "C_final.png"))
        print("    → C_final.png")

        body = await page.inner_text("body")
        print("\n=== 결과 ===")
        if "오류" in body:
            for line in body.split("\n"):
                if "오류" in line and line.strip():
                    print(f"  ERROR: {line.strip()[:400]}")
        elif any(w in body for w in ["생성 완료", "생성된 주제", "노출변수"]):
            print("  ✅ SUCCESS — 주제 생성 완료!")
        else:
            print("  결과 불명확 — C_final.png 확인")

        await browser.close()

asyncio.run(main())
