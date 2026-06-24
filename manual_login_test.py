# -*- coding: utf-8 -*-
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from playwright.sync_api import sync_playwright
import time
import re

with sync_playwright() as p:
    browser = p.chromium.launch()
    context = browser.new_context(viewport={'width': 1500, 'height': 1000})
    page = context.new_page()
    
    print("[1] Navigate to app...")
    page.goto('http://localhost:8501', wait_until='domcontentloaded', timeout=20000)
    print("[OK] App loaded")
    
    print("[2] Wait for login form...")
    time.sleep(2)
    
    print("[3] Fill email...")
    email_input = page.get_by_label(re.compile(r'.*메일|email', re.IGNORECASE))
    if email_input.count() > 0:
        email_input.first.fill('mitto0519@gmail.com')
        print("[OK] Email filled")
    else:
        print("[WARN] Email input not found, trying alternative selector...")
        try:
            page.fill('input[type="text"]', 'mitto0519@gmail.com')
            print("[OK] Email filled (alternative)")
        except:
            print("[ERROR] Could not fill email")
    
    print("[4] Click login button...")
    try:
        login_btn = page.get_by_role("button", name=re.compile(r".*접속|login", re.IGNORECASE))
        if login_btn.count() > 0:
            login_btn.first.click(timeout=5000)
            print("[OK] Login clicked")
        else:
            print("[WARN] Login button not found")
    except Exception as e:
        print(f"[ERROR] Could not click login: {e}")
    
    print("[5] Wait for page to load...")
    time.sleep(10)
    
    print("[6] Take screenshot...")
    page.screenshot(path='after_login_test.png')
    print("[OK] Screenshot saved")
    
    print("[7] Check page content...")
    body = page.locator('body').inner_text()[:200]
    print(f"  Content: {body}")
    
    browser.close()
    print("\n[OK] Test completed")
