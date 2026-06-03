"""모든 페이지 sapphire 양식 + chrome hidden  일괄 검수.

대상: ez_home, project_workspace, backlog, dashboard, memory_explorer, workflow
각 페이지 진입 → DOM probe → 스크린샷.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
OUT = Path("scripts/ui_eval_outputs")
OUT.mkdir(parents=True, exist_ok=True)

PAGES = [
    ("ez_home",             "/ez_home"),
    ("project_workspace",   "/project_workspace"),
    ("backlog",             "/backlog"),
    ("dashboard",           "/dashboard"),
    ("memory_explorer",     "/memory_explorer"),
    ("workflow",            "/workflow"),
]


PROBE = """
() => {
  const sapphireStyle = Array.from(document.querySelectorAll('style'))
      .find(s => s.textContent && s.textContent.includes('--sg-bg-from'));
  const bg = window.getComputedStyle(document.body).background;
  const hidden = (sel) => {
    const el = document.querySelector(sel);
    if (!el) return 'absent';
    const cs = window.getComputedStyle(el);
    return (cs.display === 'none' || cs.visibility === 'hidden') ? 'hidden' : 'visible';
  };
  const alerts = Array.from(document.querySelectorAll(
      '.stAlert, [data-baseweb="notification"], [data-testid="stException"]'
  )).map(e => e.textContent.substring(0, 240));
  // 에러 토큰 탐지
  const text = document.body.innerText || '';
  const errKw = ['Traceback','AttributeError','KeyError','ModuleNotFound','is not defined',
                 'ImportError','TypeError','ValueError','오류:','Exception'];
  const found = errKw.filter(k => text.includes(k));
  return {
    sapphire_css_injected: !!sapphireStyle,
    body_bg_purple: bg.includes('linear-gradient') || bg.includes('rgb(76, 29, 128)'),
    toolbar: hidden('[data-testid="stToolbar"]'),
    decoration: hidden('[data-testid="stDecoration"]'),
    deployBtn: hidden('[data-testid="stAppDeployButton"]'),
    mainMenu: hidden('#MainMenu'),
    alerts: alerts,
    error_tokens: found,
  };
};
"""


def main():
    report = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900}, locale="ko-KR")
        page = ctx.new_page()
        for name, path in PAGES:
            print(f"[{name}] {path}")
            try:
                page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(3500)
            except Exception as e:
                report[name] = {"navigate_error": str(e)[:160]}
                print(f"    navigate failed: {e}")
                continue
            try:
                probe = page.evaluate(PROBE)
                report[name] = probe
                fn = OUT / f"all_pages_{name}.png"
                page.screenshot(path=str(fn), full_page=True)
                ok_sapphire = "✓" if probe["sapphire_css_injected"] else "✗"
                ok_purple = "✓" if probe["body_bg_purple"] else "✗"
                chrome_bad = [k for k in ("toolbar","decoration","deployBtn","mainMenu")
                              if probe[k] == "visible"]
                print(f"    sapphire={ok_sapphire} purple={ok_purple}"
                      f" chrome_visible={chrome_bad or 'none'}"
                      f" alerts={len(probe['alerts'])} err={probe['error_tokens']}")
                if probe["alerts"]:
                    for a in probe["alerts"][:3]:
                        print(f"      alert: {a[:120]}")
            except Exception as e:
                report[name] = {"probe_error": str(e)[:160]}
                print(f"    probe failed: {e}")

        browser.close()

    (OUT / "all_pages_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print()
    print(f"saved → {OUT}/all_pages_*.png  +  all_pages_report.json")


if __name__ == "__main__":
    main()
