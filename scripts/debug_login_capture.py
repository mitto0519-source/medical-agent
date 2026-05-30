"""로그인 화면 sapphire 양식 적용 확인."""
from __future__ import annotations
import io, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

OUT = Path("scripts/ui_eval_outputs")

with sync_playwright() as pw:
    browser = pw.chromium.launch(headless=True)
    page = browser.new_context(viewport={"width": 1400, "height": 900},
                                locale="ko-KR").new_page()
    # 로그아웃 상태로 접속 (no session)
    page.goto("http://localhost:8501/", wait_until="networkidle", timeout=30000)
    page.wait_for_timeout(4500)
    page.screenshot(path=str(OUT / "login_gate_sapphire.png"), full_page=True)
    probe = page.evaluate("""
        () => {
          const bg = window.getComputedStyle(document.body).background;
          const card = document.querySelector('.sg-login-card');
          const chromeVisible = ['stToolbar','stDecoration','stAppDeployButton'].map(s => {
            const el = document.querySelector(`[data-testid="${s}"]`);
            if (!el) return [s, 'absent'];
            const cs = window.getComputedStyle(el);
            return [s, (cs.display==='none'||cs.visibility==='hidden')?'hidden':'visible'];
          });
          return {
            purple: bg.includes('linear-gradient') || bg.includes('rgb(76, 29, 128)'),
            sapphire_card: !!card,
            chrome: Object.fromEntries(chromeVisible),
            body_text: (document.body.innerText || '').substring(0, 300)
          };
        }
    """)
    print("purple:", probe["purple"])
    print("sapphire_card:", probe["sapphire_card"])
    print("chrome:", probe["chrome"])
    print("text:", probe["body_text"][:200])
    browser.close()
print(f"saved → {OUT}/login_gate_sapphire.png")
