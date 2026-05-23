"""A 검증 — 채팅→섹션 자동반영 + 논문 저장/불러오기(영속) 라이브 확인 (Playwright).

전제: 컨테이너가 localhost:8501에서 healthy. 결과는 PASS/FAIL + 스크린샷.
"""
from __future__ import annotations
import io, re, sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
ADMIN = "mitto0519@gmail.com"
OUT = Path("scripts/ui_smoke_outputs"); OUT.mkdir(parents=True, exist_ok=True)


def wait_idle(page, ms=2500):
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=ms)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def goto_workspace(page):
    page.goto(f"{BASE}/?email={ADMIN}&auto=1", wait_until="domcontentloaded", timeout=30000)
    wait_idle(page, 5000)
    page.get_by_role("button", name=re.compile("논문 작업실")).first.click(timeout=8000)
    wait_idle(page, 3000)


def intro_value(page) -> str:
    """우측 편집뷰의 Introduction text_area 값."""
    try:
        return page.get_by_label("Introduction", exact=True).input_value(timeout=4000)
    except Exception:
        # 폴백: 모든 textarea 중 충분히 긴 값
        vals = []
        for ta in page.query_selector_all("textarea"):
            try:
                vals.append(ta.input_value())
            except Exception:
                pass
        return max(vals, key=len) if vals else ""


def main() -> int:
    results = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1500, "height": 1000})

        # ── 1) 채팅 → 섹션 자동반영 ──
        goto_workspace(page)
        chat = page.locator('[data-testid="stChatInput"] textarea, textarea[placeholder*="요청"]').first
        chat.fill("청소년 스마트폰 과사용과 수면부족 연구로 서론 한 단락 써줘")
        chat.press("Enter")
        print("채팅 전송 — 응답/반영 대기...")
        filled = ""
        for _ in range(30):
            page.wait_for_timeout(3000)
            v = intro_value(page)
            if v and len(v.strip()) > 40:
                filled = v
                break
        page.screenshot(path=str(OUT / "A1_section_reflect.png"), full_page=True)
        ok1 = bool(filled)
        results.append(("채팅→Introduction 섹션 자동반영", ok1, filled[:80]))
        print(f"  [{'PASS' if ok1 else 'FAIL'}] Introduction 길이={len(filled)}")

        # ── 2) 저장 ──
        saved_ok = False
        try:
            page.get_by_role("button", name=re.compile("💾 저장")).first.click(timeout=5000)
            wait_idle(page, 2500)
            saved_ok = page.get_by_text(re.compile("저장됨")).count() > 0
        except Exception as e:
            print("  저장 클릭 예외:", str(e)[:120])
        results.append(("논문 저장(영속)", saved_ok, ""))
        print(f"  [{'PASS' if saved_ok else 'FAIL'}] 저장")

        # ── 3) 새 세션에서 불러오기 (영속성) ──
        ctx2 = b.new_context()
        page2 = ctx2.new_page()
        page2.set_viewport_size({"width": 1500, "height": 1000})
        goto_workspace(page2)
        # 새 세션은 섹션이 비어 있어야 정상 (영속 저장본을 열어 복원되는지 확인)
        # 연구정보 expander 열기 → 내 논문 picker → 열기
        loaded = ""
        try:
            # 셀렉트박스 열고 저장본(첫 번째 비-'새 논문' 옵션) 선택
            page2.locator('[data-testid="stSelectbox"]').first.click(timeout=6000)
            page2.wait_for_timeout(800)
            page2.get_by_role("option").nth(1).click(timeout=4000)  # 0=새 논문, 1=최신 저장본
            wait_idle(page2, 1500)
            page2.get_by_role("button", name=re.compile("열기")).first.click(timeout=6000)
            wait_idle(page2, 3000)
            loaded = intro_value(page2)
        except Exception as e:
            print("  불러오기 예외:", str(e)[:120])
        page2.screenshot(path=str(OUT / "A3_reload_restore.png"), full_page=True)
        ok3 = bool(loaded and len(loaded.strip()) > 40)
        results.append(("새 세션에서 저장논문 복원(영속성)", ok3, loaded[:80]))
        print(f"  [{'PASS' if ok3 else 'FAIL'}] 복원 길이={len(loaded)}")

        b.close()

    n = sum(1 for _, ok, _ in results if ok)
    print(f"\n=== A 검증: {n}/{len(results)} PASS ===")
    for name, ok, ex in results:
        print(f"  {'✅' if ok else '❌'} {name}  {('— '+ex) if ex else ''}")
    return 0 if n == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
