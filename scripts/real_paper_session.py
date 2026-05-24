"""실제 논문 작성 세션 — 멍청/고장 탐지용 (탐색적, 비회귀).

워크플로를 실제로 돌려 '생성된 텍스트'를 파일로 덤프 → 사람이 읽고 품질/버그 판정.
ui_eval(회귀)과 목적이 다름: 이건 'AI가 실제로 쓴 결과물의 질'을 보려는 것.

실행: python scripts/real_paper_session.py
결과: scripts/real_session_out/transcript.md (생성 텍스트 전문 + 에러)
"""
from __future__ import annotations
import io, re, sys, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from playwright.sync_api import sync_playwright

BASE = "http://localhost:8501"
ADMIN = "mitto0519@gmail.com"
OUT = Path("scripts/real_session_out"); OUT.mkdir(parents=True, exist_ok=True)
LOG = []


def wait_idle(page, ms=2500):
    try:
        page.wait_for_selector('[data-testid="stStatusWidget"]', state="detached", timeout=ms)
    except Exception:
        pass
    page.wait_for_timeout(ms)


def chat_and_capture(page, msg: str, label: str, wait_s: int = 90):
    """채팅 전송 → 응답/섹션 반영 대기 → 채팅 답변 + 섹션 내용 캡처."""
    LOG.append(f"\n## 요청: {msg}\n")
    chat = page.locator('[data-testid="stChatInput"] textarea, textarea[placeholder*="요청"]').first
    chat.fill(msg)
    chat.press("Enter")
    # 마지막 assistant 버블이 안정될 때까지 폴링
    last = ""
    for _ in range(wait_s // 3):
        page.wait_for_timeout(3000)
        bubbles = page.query_selector_all('[data-testid="stChatMessage"]')
        if bubbles:
            try:
                cur = bubbles[-1].inner_text()
            except Exception:
                cur = ""
            if cur and cur == last and len(cur) > 10:
                break
            last = cur
    LOG.append(f"**AI 채팅 답변:**\n```\n{last[:800]}\n```\n")
    # 우측 섹션 내용 캡처 (편집 뷰)
    secs = {}
    for sec in ["title", "abstract", "introduction", "methods", "results", "discussion"]:
        lab = {"title": "title", "abstract": "Abstract", "introduction": "Introduction",
               "methods": "Methods", "results": "Results", "discussion": "Discussion"}[sec]
        try:
            v = page.get_by_label(lab, exact=True).input_value(timeout=1500)
            if v and v.strip():
                secs[sec] = v
        except Exception:
            pass
    LOG.append(f"**현재 채워진 섹션:** {list(secs.keys())}\n")
    for k, v in secs.items():
        LOG.append(f"### [{label}] 섹션 '{k}' ({len(v)}자)\n```\n{v[:1200]}\n```\n")
    page.screenshot(path=str(OUT / f"{label}.png"), full_page=True)
    return secs


def main() -> int:
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": 1500, "height": 1000})
        pg.goto(f"{BASE}/?email={ADMIN}&auto=1", wait_until="domcontentloaded", timeout=30000)
        wait_idle(pg, 5000)
        # 논문 작업실로
        pg.get_by_role("button", name=re.compile("논문 작업실")).first.click(timeout=8000)
        wait_idle(pg, 3000)

        # 연구 정보 설정 (expander 열고 입력)
        try:
            pg.get_by_text(re.compile("연구 정보")).first.click(timeout=4000)
            wait_idle(pg, 1500)
            for lab, val in [("노출변수", "제로칼로리 음료 섭취"), ("결과변수", "우울 증상"),
                             ("대상", "한국 청소년"), ("데이터셋", "KYRBS")]:
                try:
                    el = pg.get_by_label(lab, exact=True).first
                    el.fill(val)
                except Exception:
                    pass
            wait_idle(pg, 1500)
        except Exception as e:
            LOG.append(f"(연구정보 입력 실패: {str(e)[:100]})")

        # 실제 논문 작성 시퀀스
        chat_and_capture(pg, "이 주제로 서론 한 단락 써줘", "01_intro")
        chat_and_capture(pg, "방법 섹션을 KYRBS 복합표본 분석으로 써줘", "02_methods")
        chat_and_capture(pg, "서론을 더 간결하게 다듬어줘", "03_refine")
        chat_and_capture(pg, "이 주제 신규성 확인해줘", "04_novelty", wait_s=120)

        b.close()

    (OUT / "transcript.md").write_text("\n".join(LOG), encoding="utf-8")
    print(f"=== 세션 완료 — scripts/real_session_out/transcript.md ({len(LOG)} 블록) ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
