"""실제 LLM 논문 작성 시나리오 재현 + 에러 정확히 캡처.

시나리오 (사용자 양식):
    1) ez_home 진입
    2) 입력바에 "ZCB와 청소년 우울증 연관성을 KYRBS 2025로 분석한 논문" 입력
    3) Build 클릭 → project_workspace 진입
    4) workspace에서 agentic loop 실행
    5) chat / preview / 에러 다 캡처

목표: 어떤 단계에서 어떤 에러가 나는지, LLM이 진짜로 논문을 만들어내는지 확인
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


def main():
    report = {"steps": []}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(viewport={"width": 1400, "height": 900}, locale="ko-KR")
        page = ctx.new_page()

        # console / page error 수집
        console_logs = []
        page.on("console", lambda msg: console_logs.append(f"{msg.type}: {msg.text[:300]}"))
        page.on("pageerror", lambda exc: console_logs.append(f"pageerror: {str(exc)[:300]}"))

        # 1. ez_home 진입
        print("[1] navigate /ez_home")
        page.goto(f"{BASE}/ez_home", wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(4000)
        page.screenshot(path=str(OUT / "paper_flow_01_ez_home.png"), full_page=True)

        # 2. 입력바에 양식
        print("[2] type research prompt into textarea")
        prompt = "ZCB와 청소년 우울증 연관성을 KYRBS 2025로 분석한 논문 한 편 작성해줘"
        try:
            ta = page.locator('textarea[placeholder*="아이디어"]').first
            ta.fill(prompt)
            page.wait_for_timeout(800)
        except Exception as e:
            print(f"    textarea fill failed: {e}")
            report["steps"].append({"step": "fill_prompt", "error": str(e)})

        # 3. Build 클릭
        print("[3] click Build")
        try:
            build = page.get_by_role("button", name=re.compile(r"Build|✨")).first
            build.click(timeout=5000)
            page.wait_for_timeout(8000)  # workspace 전환 대기
        except Exception as e:
            print(f"    Build click failed: {e}")
            report["steps"].append({"step": "build_click", "error": str(e)})

        page.screenshot(path=str(OUT / "paper_flow_02_after_build.png"), full_page=True)
        print(f"    url after Build: {page.url}")

        # 4. workspace 안 — 에러/chat/preview 살피기
        probe = page.evaluate("""
            () => {
              const alerts = Array.from(document.querySelectorAll(
                '.stAlert, [data-baseweb="notification"], [data-testid="stException"]'
              )).map(e => e.textContent.substring(0, 400));
              const codes = Array.from(document.querySelectorAll('code, pre')).slice(0, 8)
                .map(e => e.textContent.substring(0, 400));
              const tabs = Array.from(document.querySelectorAll('[role="tab"]')).map(e => e.textContent);
              const buttons = Array.from(document.querySelectorAll('button')).slice(0, 30)
                .map(e => e.textContent.substring(0, 50));
              return {
                url: location.href,
                alerts: alerts,
                code_blocks: codes,
                tabs_present: tabs,
                button_labels: buttons,
                body_text_len: document.body.innerText.length
              };
            }
        """)
        report["steps"].append({"step": "post_build", "probe": probe})
        print(f"    alerts: {len(probe['alerts'])}")
        for a in probe["alerts"][:5]:
            print(f"      ! {a[:200]}")
        print(f"    tabs: {probe['tabs_present']}")

        # 5. workspace의 chat input에 보조 메시지 양식 양식 양식 → agentic step 트리거
        print("[5] try submit a chat message in workspace")
        try:
            # chat form 안의 textarea
            ta = page.locator('textarea').last
            ta.fill("KYRBS 2025로 ZCB 노출 → 우울증 결과 분석해서 Introduction과 Methods 섹션을 써줘. 통계는 logistic regression 양식 양식 양식.")
            page.wait_for_timeout(600)
            # submit (➤ 양식 양식 양식 'send')
            send = page.get_by_role("button", name=re.compile(r"^➤$|Build|✨")).first
            send.click(timeout=4000)
            print("    submitted; waiting 35s for LLM/tool loop...")
            page.wait_for_timeout(35000)
        except Exception as e:
            print(f"    submit failed: {e}")
            report["steps"].append({"step": "chat_submit", "error": str(e)})

        page.screenshot(path=str(OUT / "paper_flow_03_after_chat.png"), full_page=True)

        # 6. 최종 진단
        probe_final = page.evaluate("""
            () => {
              const alerts = Array.from(document.querySelectorAll(
                '.stAlert, [data-baseweb="notification"], [data-testid="stException"]'
              )).map(e => e.textContent.substring(0, 600));
              // sg-msg-assistant 같은 sapphire 메시지
              const msgs = Array.from(document.querySelectorAll(
                '.sg-msg-user, .sg-msg-assistant, [class*="msg"]'
              )).map(e => ({cls: e.className, text: e.textContent.substring(0, 400)}));
              const errs = Array.from(document.querySelectorAll('[data-testid="stException"]'))
                .map(e => e.textContent.substring(0, 600));
              return { url: location.href, alerts, messages: msgs.slice(0, 10), exceptions: errs };
            }
        """)
        report["steps"].append({"step": "final", "probe": probe_final})
        print()
        print(f"=== FINAL ALERTS ({len(probe_final['alerts'])}) ===")
        for a in probe_final["alerts"]:
            print(f"  ! {a}")
        print(f"=== MESSAGES ({len(probe_final['messages'])}) ===")
        for m in probe_final["messages"][:8]:
            print(f"  [{m['cls'][:30]}] {m['text'][:160]}")
        print(f"=== EXCEPTIONS ({len(probe_final['exceptions'])}) ===")
        for e in probe_final["exceptions"][:3]:
            print(f"  X {e}")

        # 7. console logs
        if console_logs:
            print(f"\n=== console ({len(console_logs)}) ===")
            for l in console_logs[-15:]:
                print(f"  | {l}")
            report["console"] = console_logs[-30:]

        browser.close()

    (OUT / "paper_flow_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nsaved → {OUT}/paper_flow_*.png + paper_flow_report.json")


if __name__ == "__main__":
    main()
