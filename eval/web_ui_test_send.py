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

    page.goto("https://dashboard-staging.flexagents.ai/login", wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    page.goto(TEST_URL, wait_until="networkidle")
    time.sleep(2)

    # Click Start Call
    start_call_btn = page.locator("button:has-text('Start Call')")
    start_call_btn.first.click()
    print("Clicked Start Call, waiting 6s for WebRTC session connection...")
    time.sleep(6)

    # Check status
    diagnostics = page.locator("text=Diagnostics").locator("..").inner_text()
    print("Diagnostics status:\n", diagnostics)

    # Find the input and send button
    input_box = page.locator("input[placeholder='Type a message...']")
    input_box.fill("Hi")
    time.sleep(1)

    # Find the send button next to the input
    send_btn = input_box.locator("..").locator("button")
    if send_btn.count() > 0:
        print("Clicking send button...")
        send_btn.first.click()
    else:
        page.keyboard.press("Enter")

    print("Sent message! Waiting 12 seconds for agent response...")
    time.sleep(12)

    # Check transcript area
    body_text = page.locator("body").inner_text()
    page.screenshot(path="/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/agent_live_response.png")
    
    # Print messages in the center area
    print("\n--- PAGE TEXT SNIPPET ---")
    for line in body_text.splitlines():
        if any(keyword in line.lower() for keyword in ['amelia', 'hi', 'help', 'barwood', 'call', 'speaking', 'rider', 'how can i']):
            print(" >>", line)
    print("-------------------------\n")

    browser.close()
