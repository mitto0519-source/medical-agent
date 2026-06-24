# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={'width': 1500, 'height': 1000})
    
    print("Step 1: Navigate to app...")
    page.goto('http://localhost:8501', wait_until='domcontentloaded', timeout=60000)
    
    print("Step 2: Wait for Streamlit to render content...")
    # Wait for Streamlit's main content element
    try:
        page.wait_for_selector('[data-testid="stAppViewContainer"], [class*="main"]', timeout=15000)
        print("[OK] Streamlit content appeared")
    except Exception as e:
        print(f"[WARN] Content wait timeout: {e}")
    
    # Give it more time to render
    time.sleep(5)
    
    print("Step 3: Check page content...")
    content = page.locator('body').inner_text()
    print(f"  Content length: {len(content)} chars")
    print(f"  First 500 chars: {content[:500]}")
    
    print("Step 4: Take screenshot...")
    page.screenshot(path='rendered_screenshot.png')
    print("[OK] Screenshot saved")
    
    print("Step 5: Check for login button...")
    login_btn = page.get_by_role("button", name="접속하기").count()
    print(f"  Login button count: {login_btn}")
    
    if login_btn > 0:
        print("Step 6: Click login button...")
        page.get_by_role("button", name="접속하기").first.click(timeout=10000)
        time.sleep(10)
        page.screenshot(path='after_login_screenshot.png')
        print("[OK] After login screenshot saved")
    
    browser.close()
    print("\n[OK] Test completed")
