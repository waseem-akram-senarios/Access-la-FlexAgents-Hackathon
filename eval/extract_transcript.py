import os
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
    
    page.goto(TEST_URL, wait_until="networkidle")
    
    # Check if there is any history or inspect how messages are rendered
    # Let's inspect the HTML of the transcript container
    print("Page title:", page.title())
    browser.close()
