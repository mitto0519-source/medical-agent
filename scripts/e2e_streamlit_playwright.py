from playwright.sync_api import sync_playwright, TimeoutError
import time, os, json, pathlib, re

BASE = os.environ.get('BASE_URL', 'http://localhost:8501/?email=mitto0519@gmail.com&auto=1')
OUT_DIR = pathlib.Path('scripts/e2e_outputs')
OUT_DIR.mkdir(parents=True, exist_ok=True)

# target keywords to look for in sidebar buttons
TARGET_KEYWORDS = [
    "홈",
    "논문 작업실",
    "글쓰기 스타일",
    "작업 타임라인",
    "논문 생산 파이프라인",
    "기존 논문 개선",
    "논문 업로드",
    "Agent Q&A",
    "워크플로우",
    "Notebook 에디터",
    "자동 학습 루프",
    "자가 진단",
    "지식베이스 관리",
]

results = {"pages": []}

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context()
    page = context.new_page()

    console_msgs = []
    page_errors = []

    page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text}))
    page.on("pageerror", lambda err: page_errors.append(str(err)))

    try:
        page.goto(BASE, timeout=20000)
        time.sleep(1)
    except Exception as e:
        results['error_on_open'] = str(e)

    # helper to save snapshot
    def save_state(name):
        safe = re.sub(r"[^0-9a-zA-Z-_]+", "_", name)
        png = OUT_DIR / f"{safe}.png"
        html = OUT_DIR / f"{safe}.html"
        try:
            page.screenshot(path=str(png), full_page=True)
        except Exception as e:
            console_msgs.append({"screenshot_error": str(e)})
        try:
            html.write_text(page.content(), encoding="utf-8")
        except Exception as e:
            console_msgs.append({"html_write_error": str(e)})

    # initial snapshot
    save_state('home_loaded')

    for kw in TARGET_KEYWORDS:
        entry = {"keyword": kw, "clicked": False, "console": [], "page_errors": [], "html_file": None, "screenshot": None}
        try:
            # try to find a button containing the keyword
            locator = page.locator(f"button:has-text('{kw}')").first
            if locator.count() == 0:
                # fallback: any element with text
                locator = page.locator(f"text={kw}").first
            if locator.count() == 0:
                entry['note'] = 'not_found'
            else:
                try:
                    locator.click(timeout=8000)
                    time.sleep(1.2)
                    entry['clicked'] = True
                except TimeoutError:
                    entry['note'] = 'click_timeout'
                except Exception as e:
                    entry['note'] = f'click_error: {e}'
            # save state after click/attempt
            safe = re.sub(r"[^0-9a-zA-Z-_]+", "_", kw)
            entry['screenshot'] = str((OUT_DIR / f"{safe}.png").resolve())
            entry['html_file'] = str((OUT_DIR / f"{safe}.html").resolve())
            save_state(kw)
            entry['console'] = list(console_msgs)
            entry['page_errors'] = list(page_errors)
        except Exception as e:
            entry['exception'] = str(e)
        results['pages'].append(entry)

    # final state
    save_state('final')
    results['final_console'] = console_msgs
    results['final_page_errors'] = page_errors

    browser.close()

# write results
with open(OUT_DIR / 'results.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print('E2E run complete. Outputs in scripts/e2e_outputs')
