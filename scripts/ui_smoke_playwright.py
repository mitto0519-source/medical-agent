"""UI 스모크 — Playwright로 실행 중인 Streamlit 앱을 실제로 클릭하며 에러를 잡는다.

블로그(Anthropic 'evals for AI agents')의 computer-use/browser-agent eval 방식:
실 브라우저로 admin 로그인 → 각 페이지 클릭 → Streamlit 예외/에러 알림 수집 →
논문 작업실 채팅을 실제로 보내 응답이 나오는지 확인 → 페이지별 PASS/FAIL 리포트 + 스크린샷.

전제: 컨테이너/앱이 BASE_URL에서 떠 있어야 함 (docker compose up -d).
실행: python scripts/ui_smoke_playwright.py
결과: scripts/ui_smoke_outputs/ (스크린샷 + report.json + report.md)
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

BASE_URL = "http://localhost:8501"
ADMIN_EMAIL = "mitto0519@gmail.com"
OUT = Path("scripts/ui_smoke_outputs")
OUT.mkdir(parents=True, exist_ok=True)

# 에러로 간주할 키워드 (st.error/예외 텍스트)
_ERR_KW = ["Traceback", "오류", "Error code", "Exception", "찾을 수 없",
           "AttributeError", "KeyError", "ModuleNotFound", "is not defined",
           "credit balance", "실패"]


def wait_idle(page, settle_ms: int = 2500):
    """Streamlit 실행(러닝맨)이 끝날 때까지 대기."""
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=settle_ms)
    except Exception:
        pass
    page.wait_for_timeout(settle_ms)


def capture_errors(page) -> list[dict]:
    errs = []
    for el in page.query_selector_all('[data-testid="stException"]'):
        try:
            errs.append({"kind": "exception", "text": el.inner_text()[:600]})
        except Exception:
            pass
    for el in page.query_selector_all('[data-testid="stAlert"]'):
        try:
            txt = el.inner_text()
        except Exception:
            continue
        if any(k in txt for k in _ERR_KW):
            errs.append({"kind": "alert", "text": txt[:500]})
    return errs


def click_nav(page, label: str) -> bool:
    """사이드바 네비 버튼(텍스트 부분일치) 클릭."""
    try:
        btn = page.get_by_role("button", name=re.compile(re.escape(label))).first
        btn.click(timeout=5000)
        wait_idle(page)
        return True
    except Exception as e:
        print(f"  [nav 실패] {label}: {str(e)[:100]}")
        return False


def main() -> int:
    report = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        console_errors = []
        page.on("console", lambda m: console_errors.append(m.text) if m.type == "error" else None)

        # ── 로그인 (query-param auto-login) ──
        print(f"접속: {BASE_URL}/?email={ADMIN_EMAIL}&auto=1")
        page.goto(f"{BASE_URL}/?email={ADMIN_EMAIL}&auto=1", wait_until="domcontentloaded", timeout=30000)
        wait_idle(page, 6000)

        # 로그인 성공 확인 (사이드바 로고 또는 네비)
        logged_in = page.get_by_text("Medical-Agent").count() > 0 and page.get_by_text("논문 작업실").count() > 0
        page.screenshot(path=str(OUT / "00_landing.png"), full_page=True)
        if not logged_in:
            print("✗ 로그인 실패 — 랜딩이 로그인 폼일 수 있음. 00_landing.png 확인")
            report.append({"page": "(login)", "ok": False, "errors": [{"kind": "login", "text": "auto-login 실패"}]})
        else:
            print("✓ admin 로그인 성공")

        # ── 기본(바이브) 페이지들 ──
        main_pages = ["홈", "논문 작업실", "글쓰기 스타일", "작업 타임라인"]
        for i, pg in enumerate(main_pages, 1):
            if pg != "홈":
                click_nav(page, pg)
            else:
                wait_idle(page)
            errs = capture_errors(page)
            page.screenshot(path=str(OUT / f"{i:02d}_{pg}.png"), full_page=True)
            report.append({"page": pg, "ok": not errs, "errors": errs})
            print(f"  [{pg}] {'OK' if not errs else 'ERR ' + str(len(errs))}")

        # ── 논문 작업실 채팅 실제 전송 테스트 (핵심: 400/폴백) ──
        click_nav(page, "논문 작업실")
        chat_result = {"page": "논문 작업실/채팅", "ok": False, "errors": []}
        try:
            chat = page.locator('textarea[placeholder*="요청"], [data-testid="stChatInput"] textarea').first
            chat.fill("청소년 스마트폰 과사용과 수면부족 연구로 서론 한 단락 써줘")
            chat.press("Enter")
            print("  채팅 전송 — 응답 대기(최대 90s)...")
            # 응답 또는 에러가 채팅 영역에 나타날 때까지 폴링
            got = False
            for _ in range(30):
                page.wait_for_timeout(3000)
                errs = capture_errors(page)
                # assistant 메시지(채팅 버블) 개수
                msgs = page.query_selector_all('[data-testid="stChatMessage"]')
                if errs:
                    chat_result["errors"] = errs
                    break
                if len(msgs) >= 2:  # user + assistant
                    got = True
                    break
            chat_result["ok"] = got and not chat_result["errors"]
            page.screenshot(path=str(OUT / "05_workspace_chat.png"), full_page=True)
            print(f"  [작업실 채팅] {'OK 응답수신' if chat_result['ok'] else 'FAIL ' + str(chat_result['errors'])[:200]}")
        except Exception as e:
            chat_result["errors"] = [{"kind": "exec", "text": str(e)[:300]}]
            print(f"  [작업실 채팅] 예외: {str(e)[:200]}")
        report.append(chat_result)

        # ── 관리자 모드 토글 ON 후 단위 페이지들 ──
        try:
            toggle = page.get_by_text(re.compile("관리자 모드")).first
            toggle.click(timeout=4000)
            wait_idle(page)
            print("✓ 관리자 모드 ON")
        except Exception as e:
            print(f"  관리자 모드 토글 실패: {str(e)[:100]}")

        admin_pages = ["연구 주제 생성", "신규성 확인", "데이터 분석", "논문 작성",
                       "기존 논문 개선", "Agent Q&A", "자가 진단", "지식베이스 관리"]
        for i, pg in enumerate(admin_pages, 6):
            if click_nav(page, pg):
                errs = capture_errors(page)
                page.screenshot(path=str(OUT / f"{i:02d}_{pg}.png"), full_page=True)
                report.append({"page": pg, "ok": not errs, "errors": errs})
                print(f"  [{pg}] {'OK' if not errs else 'ERR ' + str(len(errs))}")

        browser.close()

    # ── 리포트 ──
    (OUT / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    n_ok = sum(1 for r in report if r.get("ok"))
    lines = [f"# UI 스모크 리포트 ({n_ok}/{len(report)} PASS)", ""]
    for r in report:
        mark = "✅" if r.get("ok") else "❌"
        lines.append(f"## {mark} {r['page']}")
        for e in r.get("errors", []):
            lines.append(f"- [{e['kind']}] {e['text'][:300]}")
        lines.append("")
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\n=== 결과: {n_ok}/{len(report)} PASS — scripts/ui_smoke_outputs/report.md ===")
    return 0 if n_ok == len(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
