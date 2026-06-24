# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1500, 'height': 1000})
    page = context.new_page()
    
    print("[1] Navigate to app (no params)...")
    try:
        page.goto('http://localhost:8501', wait_until='domcontentloaded', timeout=20000)
        print("[OK] Page loaded")
    except Exception as e:
        print(f"[ERROR] {e}")
        browser.close()
        exit(1)
    
    print("[2] Wait for content render...")
    time.sleep(5)
    
    print("[3] Check page state...")
    body = page.locator('body').inner_text()[:100]
    print(f"  Body content: {body}")
    
    print("[4] Check for login button...")
    try:
        login_btn = page.get_by_role("button", name="접속하기")
        if login_btn.count() > 0:
            print("  Login button found - clicking...")
            login_btn.first.click(timeout=5000)
            print("  Button clicked")
            time.sleep(5)
    except Exception as e:
        print(f"  No login button or error: {e}")
    
    print("[5] Take screenshot...")
    page.screenshot(path='final_screenshot.png')
    print("  Screenshot saved")
    
    print("[OK] Test completed")
    browser.close()
