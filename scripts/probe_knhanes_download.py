"""Probe KNHANES KDCA download path with Playwright headless.

Goal: find out *exactly* where automation breaks (form vs CAPTCHA vs identity verification).
We try to:
    1. Open https://knhanes.kdca.go.kr/
    2. Navigate to '원시자료 다운로드' (raw data download)
    3. Capture form fields, screenshots, and whatever blocks the path

This is a diagnostic — NOT a real download. It tells us what the user must do manually.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright not installed. pip install playwright && playwright install chromium")
        return 1

    out_dir = Path("data/diagnostics/knhanes_probe")
    out_dir.mkdir(parents=True, exist_ok=True)
    log: list[str] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0 Safari/537.36"),
            locale="ko-KR",
        )
        page = ctx.new_page()

        try:
            # Step 1: KNHANES home
            page.goto("https://knhanes.kdca.go.kr/", timeout=20000,
                        wait_until="domcontentloaded")
            log.append(f"[home] title={page.title()!r} url={page.url}")
            page.screenshot(path=str(out_dir / "01_home.png"), full_page=True)

            # Step 2: try common '원시자료' links
            candidates = [
                "text=원시자료",
                "text=다운로드",
                "text=Data Download",
                "a:has-text('자료')",
            ]
            navigated = False
            for sel in candidates:
                try:
                    el = page.query_selector(sel)
                    if el:
                        href = el.get_attribute("href") or ""
                        log.append(f"[link] selector={sel} text={(el.text_content() or '').strip()[:50]} href={href}")
                        if href:
                            full = href if href.startswith("http") else page.url.rsplit("/", 1)[0] + "/" + href.lstrip("/")
                            page.goto(full, timeout=15000, wait_until="domcontentloaded")
                            navigated = True
                            break
                except Exception as e:
                    log.append(f"[link-err] {sel}: {e}")

            if navigated:
                page.screenshot(path=str(out_dir / "02_data_page.png"), full_page=True)
                log.append(f"[data_page] url={page.url} title={page.title()!r}")

                # Form discovery
                inputs = page.query_selector_all("input,select,textarea,button")
                log.append(f"[form] {len(inputs)} interactive elements")
                for i, el in enumerate(inputs[:30]):
                    try:
                        name = el.get_attribute("name") or ""
                        typ = el.get_attribute("type") or el.evaluate("el => el.tagName")
                        log.append(f"  [{i}] type={typ} name={name}")
                    except Exception:
                        pass

                # Detect identity-verification keywords
                html = page.content()[:50000]
                blockers = []
                for kw in ("본인인증", "공인인증", "휴대폰 인증", "I-PIN", "신청서",
                            "회원가입", "로그인", "captcha", "캡차", "승인"):
                    if kw in html:
                        blockers.append(kw)
                log.append(f"[blockers] keywords detected: {blockers}")
            else:
                log.append("[nav] no '원시자료/다운로드' link found from home page (likely SPA-rendered)")

            browser.close()
        except Exception as e:
            log.append(f"[error] {type(e).__name__}: {e}")
            browser.close()

    report_path = out_dir / "probe_report.txt"
    report_path.write_text("\n".join(log), encoding="utf-8")
    print("=" * 60)
    print("KNHANES download path probe — summary")
    print("=" * 60)
    print("\n".join(log))
    print(f"\nScreenshots + report → {out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
