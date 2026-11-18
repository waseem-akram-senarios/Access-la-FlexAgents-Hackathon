import json
import time
import os
from dotenv import load_dotenv
from playwright.sync_api import sync_playwright

load_dotenv()

TEST_URL = os.getenv("FLEXAGENTS_TEST_URL", "https://dashboard-staging.flexagents.ai/organization/6af96a0fbdbf32a95ff4651b/agent/6af97679bdbf32a95ff46702/test")
EMAIL = os.getenv("FLEXAGENTS_USERNAME")
PASS = os.getenv("FLEXAGENTS_PASSWORD")

QUESTIONS = [
    ("Q1: New Booking", "I need a ride to the airport tomorrow at 9 am, and I'll be traveling with two kids."),
    ("Q2: Fare Quote", "What is the fare from my home to downtown if I pay with cash?"),
    ("Q3: Ride Status & ETA", "My driver is 20 minutes late, what is the ETA?"),
    ("Q4: Change Pickup Time", "Can I change the pickup time for my 3 pm trip to 4 pm?"),
    ("Q5: Cancel Trip", "I want to cancel my trip to the museum on Friday."),
    ("Q6: Trips Today Check", "Do I have any trips booked for today?"),
    ("Q7: Already Booked Trip", "I have an upcoming trip at 2 pm, can I book another one for tomorrow?"),
    ("Q8: Will-Call Activation", "Please activate will-call for my pickup at 5 pm."),
    ("Q9: SMS Request", "Send me a text with the details of my current reservation."),
    ("Q10: Emergency Transfer", "I am stuck at the hospital and need an emergency ride right now, can you help?")
]

results = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path='/usr/bin/google-chrome',
        headless=True,
        args=['--no-sandbox', '--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream']
    )
    context = browser.new_context(permissions=['microphone'])
    page = context.new_page()

    print("[1] Logging in...")
    page.goto("https://dashboard-staging.flexagents.ai/login", wait_until="networkidle")
    page.fill('input[type="email"]', EMAIL)
    page.fill('input[type="password"]', PASS)
    page.click('button[type="submit"]')
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    print("[2] Opening Agent Test Page...")
    page.goto(TEST_URL, wait_until="networkidle")
    time.sleep(3)

    # Click Start Call
    start_call_btn = page.locator("button:has-text('Start Call')")
    if start_call_btn.count() > 0:
        start_call_btn.first.click()
        print("[3] Call started. Waiting for connection...")
        time.sleep(6)
    else:
        print("Start Call button not found!")

    input_box = page.locator("input[placeholder='Type a message...']")
    send_btn = input_box.locator("..").locator("button")

    print("[4] Testing 10 Questions on Live Web Agent...")

    for idx, (label, question) in enumerate(QUESTIONS, 1):
        print(f"\n--- Testing {label} ---")
        print(f"User: {question}")

        # Count current agent messages before sending
        prev_agent_msgs = page.locator("text=Agent").count()

        input_box.fill(question)
        time.sleep(0.5)
        if send_btn.count() > 0:
            send_btn.first.click()
        else:
            page.keyboard.press("Enter")

        # Wait for agent message count to increase or up to 12s
        agent_reply = ""
        start_time = time.time()
        while time.time() - start_time < 14:
            time.sleep(2)
            curr_msgs = page.locator("text=Agent").count()
            if curr_msgs > prev_agent_msgs:
                break

        # Extract latest message from transcript
        # Look for messages in the transcript container
        transcript_container = page.locator("text=Transcript").locator("..")
        full_transcript = transcript_container.inner_text()
        
        # Parse out agent response
        lines = full_transcript.splitlines()
        extracted = []
        capture = False
        for line in reversed(lines):
            if "Agent" in line:
                break
            if line.strip() and "Type a message" not in line and "Listening" not in line and "Transcript" not in line:
                extracted.insert(0, line.strip())

        agent_reply = " ".join(extracted) if extracted else "(Response pending / audio output)"
        print(f"Amelia: {agent_reply}")

        results.append({
            "number": idx,
            "category": label,
            "question": question,
            "response": agent_reply,
            "timestamp": time.strftime("%H:%M:%S")
        })
        time.sleep(2)

    # Save final screenshot
    screenshot_path = "/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/all_10_questions_web_test.png"
    page.screenshot(path=screenshot_path)
    
    artifact_dir = "/home/senarios/.gemini/antigravity/brain/2aee1ebe-10fa-41ef-911e-bb850bb6a2ae"
    os.system(f"cp {screenshot_path} {artifact_dir}/all_10_questions_web_test.png")

    # Save JSON results
    out_json = "/home/senarios/Desktop/Waseem/HacktopFexlagesnts/eval/reports/10_questions_web_results.json"
    with open(out_json, "w") as f:
        json.dump(results, f, indent=2)

    browser.close()
    print("\n[5] Completed all 10 questions! Saved results and screenshot.")
