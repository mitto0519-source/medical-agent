"""ez_home 페이지를 실 브라우저로 띄우고 진단.

목표:
    1) 첫 진입 — 보라 sapphire 양식인지 확인
    2) 'Research Question' chip 클릭 (사용자 시나리오 재현)
    3) chip 클릭 후 dark theme 양식 깨지는지 진단
    4) DOM 점검: <style> 안 sapphire CSS 박혀있나, stToolbar 보이나
    5) 스크린샷 2장 저장

실행: python scripts/debug_ez_home_capture.py
출력: scripts/ui_eval_outputs/debug_ez_home_*.png + debug_ez_home_report.json
"""
from __future__ import annotations

import io
import json
import re
import sys
import time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
OUT = Path("scripts/ui_eval_outputs")
OUT.mkdir(parents=True, exist_ok=True)


def probe(page) -> dict:
    """현재 페이지의 sapphire 적용 여부를 DOM에서 측정."""
    return page.evaluate("""
        () => {
          const body = document.body;
          const root = document.documentElement;
          const sapphireStyle = Array.from(document.querySelectorAll('style'))
              .find(s => s.textContent.includes('--sg-bg-from'));
          const bg = window.getComputedStyle(body).background;
          const chrome = {
            toolbar:    !!document.querySelector('[data-testid="stToolbar"]'),
            decoration: !!document.querySelector('[data-testid="stDecoration"]'),
            mainMenu:   !!document.querySelector('#MainMenu'),
            statusWidget: !!document.querySelector('[data-testid="stStatusWidget"]'),
            deployBtn:  !!document.querySelector('[data-testid="stAppDeployButton"]')
          };
          const chromeVisible = Object.entries(chrome).reduce((acc,[k,exists])=>{
            if (!exists) { acc[k] = 'absent'; return acc; }
            const el = document.querySelector(`[data-testid="${k==='mainMenu'?'':'st'+k.charAt(0).toUpperCase()+k.slice(1)}"]`) ||
                        document.querySelector('#MainMenu');
            if (!el) { acc[k] = 'absent'; return acc; }
            const cs = window.getComputedStyle(el);
            acc[k] = (cs.display === 'none' || cs.visibility === 'hidden') ? 'hidden' : 'visible';
            return acc;
          }, {});
          // body 배경에 보라 그라데이션 키워드 포함?
          const isPurple = bg.includes('rgb(76, 29, 128)') || bg.includes('rgb(184, 58, 142)')
                          || bg.includes('linear-gradient');
          return {
            url: location.href,
            title: document.title,
            sapphire_css_injected: !!sapphireStyle,
            body_bg_purple: isPurple,
            body_bg_sample: bg.substring(0, 240),
            chrome_visible: chromeVisible,
            chip_count: document.querySelectorAll('button').length,
            error_text: Array.from(document.querySelectorAll('.stAlert, [data-baseweb="notification"]'))
                .map(e => e.textContent.substring(0, 200))
          };
        }
    """)


def main():
    report = {"steps": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900},
                                    locale="ko-KR")
        page = ctx.new_page()

        # 1) ez_home 직접 진입
        print("[1] navigate to /ez_home")
        page.goto(f"{BASE}/ez_home", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(3500)
        page.screenshot(path=str(OUT / "debug_ez_home_01_initial.png"), full_page=True)
        s1 = probe(page)
        report["steps"].append({"name": "initial", "probe": s1})
        print(f"    sapphire_css: {s1['sapphire_css_injected']}  bg_purple: {s1['body_bg_purple']}")
        print(f"    chrome: {s1['chrome_visible']}")
        if s1["error_text"]:
            print(f"    ALERTS: {s1['error_text']}")

        # 2) Research Question chip 클릭 (사용자 시나리오 재현)
        print("[2] click 'Research Question' chip (no prompt)")
        try:
            chip = page.get_by_role("button", name=re.compile(r"Research Question")).first
            chip.scroll_into_view_if_needed(timeout=4000)
            chip.click(timeout=5000)
            page.wait_for_timeout(4000)
        except Exception as e:
            print(f"    click failed: {e}")
            report["steps"].append({"name": "click_fail", "error": str(e)})

        page.screenshot(path=str(OUT / "debug_ez_home_02_after_click_no_prompt.png"), full_page=True)
        s2 = probe(page)
        report["steps"].append({"name": "after_click_no_prompt", "probe": s2})
        print(f"    sapphire_css: {s2['sapphire_css_injected']}  bg_purple: {s2['body_bg_purple']}")
        print(f"    chrome: {s2['chrome_visible']}")
        if s2["error_text"]:
            print(f"    ALERTS: {s2['error_text']}")

        # 3) 이번엔 입력바에 텍스트 채워서 chip 클릭 — 새 fix가 prompt 자동주입 양식 검증
        print("[3] fill input + click chip (prompt autofill 양식)")
        try:
            # textarea (placeholder 포함)
            ta = page.locator('textarea').first
            ta.fill("청소년 ZCB 섭취와 우울증 연관성")
            page.wait_for_timeout(500)
            # 같은 chip 다시 클릭
            chip = page.get_by_role("button", name=re.compile(r"Research Question")).first
            chip.click(timeout=5000)
            page.wait_for_timeout(15000)  # slash 실행 — PubMed search 30초까지 대기 가능
        except Exception as e:
            print(f"    step3 failed: {e}")
            report["steps"].append({"name": "step3_fail", "error": str(e)})

        page.screenshot(path=str(OUT / "debug_ez_home_03_after_autofill.png"), full_page=True)
        s3 = probe(page)
        report["steps"].append({"name": "after_autofill_click", "probe": s3})
        print(f"    sapphire_css: {s3['sapphire_css_injected']}  bg_purple: {s3['body_bg_purple']}")
        print(f"    chrome: {s3['chrome_visible']}")
        if s3["error_text"]:
            print(f"    ALERTS: {s3['error_text']}")

        # 3) 페이지 전체 HTML 머리 — 디버깅용
        head_html = page.evaluate("() => document.head.outerHTML.substring(0, 8000)")
        (OUT / "debug_ez_home_head.html").write_text(head_html, encoding="utf-8")

        browser.close()

    (OUT / "debug_ez_home_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"saved → {OUT}/debug_ez_home_01_initial.png, 02_after_click.png")


if __name__ == "__main__":
    main()
