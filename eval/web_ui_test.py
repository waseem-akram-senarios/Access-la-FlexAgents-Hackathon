import json
import os
import time
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

TEST_URL = os.getenv("FLEXAGENTS_TEST_URL", "https://dashboard-staging.flexagents.ai/organization/6af96a0fbdbf32a95ff4651b/agent/6af97679bdbf32a95ff46702/test")
EMAIL = os.getenv("FLEXAGENTS_USERNAME")
PASS = os.getenv("FLEXAGENTS_PASSWORD")

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/google-chrome', headless=True, args=['--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream'])
    context = browser.new_context(permissions=['microphone'])
    page = context.new_page()

    print("[1/5] Navigating to login page...")
    page.goto("https://dashboard-staging.flexagents.ai/login", wait_until="networkidle")

    print("[2/5] Filling credentials and signing in...")
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASS)
    page.click('button[type="submit"]')

    # Wait for navigation after login
    page.wait_for_load_state("networkidle")
    time.sleep(3)
    print("Post-login URL:", page.url)

    print("[3/5] Navigating to Agent Test page...")
    page.goto(TEST_URL, wait_until="networkidle")
    time.sleep(3)
    print("Agent Test Page Title:", page.title())

    # Take screenshot before call
    page.screenshot(path="/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/agent_test_before_call.png")

    print("[4/5] Looking for Start Call button...")
    # Find button containing "Start Call"
    start_call_btn = page.locator("button:has-text('Start Call')")
    if start_call_btn.count() > 0:
        print("Found Start Call button! Clicking...")
        start_call_btn.first.click()
        time.sleep(5)
    else:
        print("Start Call button selector not found directly, looking at buttons:")
        for b in page.query_selector_all('button'):
            print(" - Button:", b.inner_text().strip())

    # Take screenshot after clicking Start Call
    page.screenshot(path="/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/agent_test_call_active.png")

    print("[5/5] Sending 'Hi' into message input...")
    # Find input for chat
    inputs = page.query_selector_all('input')
    for inp in inputs:
        ph = inp.get_attribute('placeholder') or ''
        print("Found input with placeholder:", ph)

    # Try to find chat input
    chat_input = page.locator("input[placeholder*='message'], input[placeholder*='Message'], textarea[placeholder*='message']")
    if chat_input.count() > 0:
        print("Typing 'Hi'...")
        chat_input.first.fill("Hi")
        time.sleep(1)
        # Hit Enter or click send button
        page.keyboard.press("Enter")
        print("Pressed Enter. Waiting for response...")
        time.sleep(10)
    else:
        print("Chat input not immediately identified.")

    # Screenshot after message
    page.screenshot(path="/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/agent_test_after_hi.png")

    # Extract Transcript content
    transcript_el = page.locator("text=Transcript").locator("..")
    if transcript_el.count() > 0:
        print("\n--- TRANSCRIPT SECTION ---")
        print(transcript_el.first.inner_text())
        print("--------------------------\n")

    browser.close()
    print("Done!")
