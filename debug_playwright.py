# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright, expect
import time

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)  # Show browser for debugging
    page = browser.new_page(viewport={'width': 1500, 'height': 1000})
    
    print("Navigate to app...")
    page.goto('http://localhost:8501', wait_until='networkidle', timeout=60000)
    
    print("Wait 10 seconds for full render...")
    time.sleep(10)
    
    print("Take screenshot...")
    page.screenshot(path='debug_screenshot.png')
    
    print("Check for any text content...")
    body_text = page.locator('body').inner_text()
    print(f"Body text ({len(body_text)} chars): {body_text[:200]}")
    
    print("Check for any buttons...")
    buttons = page.locator('button').all()
    print(f"Found {len(buttons)} buttons")
    for i, btn in enumerate(buttons[:5]):
        try:
            text = btn.inner_text()
            print(f"  Button {i}: {text}")
        except:
            pass
    
    print("Waiting for user to close browser...")
    # Keep browser open for inspection
    input("Press Enter to close browser...")
    
    browser.close()
