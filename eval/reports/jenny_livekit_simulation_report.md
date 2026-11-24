# Access LA ("Jenny") — LiveKit Simulation Report

**Date:** 2026-11-24  
**Agent:** Access LA (Jenny) — General Inquiry  
**Organization:** `6aa1562861347fe1a3087d63`  
**Agent ID:** `6af703a01d07b8f78656fe4f`  
**LiveKit Project:** `p_2umsbbk54kq` (`wss://adl-f7lfm53p.livekit.cloud`)  
**Method:** `lk agent simulate` (text mode) with local worker twin  
**Worker:** `eval/staging/flexagent_staging_worker.py`  

---

## Summary

| # | Scenario | Description | Result | LiveKit Run ID |
|---|----------|-------------|--------|----------------|
| 1 | `01_kb.yaml` | Knowledge base fare query | ✅ PASS | `SR_rDpiAGH8mXny` |
| 2 | `02_directory.yaml` | Department lookup + open/closed | ✅ PASS | `SR_cNz9xRqpQGPt` |
| 3 | `03_case_sms.yaml` | File lost item + SMS case number | ✅ PASS | `SR_tNwYYSkuBzHm` |
| 4 | `04_case_lookup.yaml` | Read back existing cases | ✅ PASS | `SR_bKTbGUkeyUdZ` |
| 5 | `05_callback_sms.yaml` | Book callback + SMS confirmation | ✅ PASS | `SR_sQvaeWwxsoqb` |
| 6 | `06_callback_cancel.yaml` | Cancel callback | ✅ PASS | `SR_JwNQAzzrme2B` |
| 7 | `07_two_jobs.yaml` | Two issues → two separate cases | ✅ PASS | `SR_jW6bYrQpJYeD` |
| 8 | `08_complaint_line.yaml` | Complaint routing (phone + status) | ✅ PASS | `SR_RtdVJXuQ5sUB` |
| 9 | `09_no_ride_booking.yaml` | Refuse disallowed work (ride booking) | ✅ PASS | `SR_gpmgRutnPY77` |
| 10 | `10_caller_says_no.yaml` | No write without clean "yes" | ❌ **FAIL** | `SR_dZNF3DS5wbLr` |

**Overall: 9 / 10 PASS, 1 FAIL**

---

## Detailed Transcripts

### Scenario 1 — Knowledge Base Fare Query (`SR_rDpiAGH8mXny`) ✅ PASS

**Caller:** "What's the current one-way Access fare?"

**Transcript:**
```
[handoff] -> access_jenny
● You:  What's the current one-way Access fare?
[call]  search_knowledge({"query":"one-way Access fare"})
[output] → found=true, passages from "departments.json" and "01_answer_policy.md"
● Agent: The one-way fare for Access is not specified in the materials I searched.
         The information was searched in the document "2026 Rider's Guide + accessla.org."
         If you want, I can direct you to Customer Service for precise fare details.
```

**Judge Result:** PASS — Agent searched KB, correctly identified fare was not in materials, named the source document, and did not invent an amount.

**To improve:** End after the answer and source; don't add an unrequested Customer Service follow-up.

---

### Scenario 2 — Department Lookup + Open/Closed (`SR_cNz9xRqpQGPt`) ✅ PASS

**Caller:** "Who do I call if I left my bag on the bus? Is that department open right now?"

**Transcript:**
```
[handoff] -> access_jenny
● You:  Who do I call if I left my bag on the bus? Is that department open right now?
[call]  find_departments({"need":"lost"})
[output] → Lost Property (old line), Lost and Found, Rider ID Cards
[call]  get_department({"department_id":"lost-and-found"})
[output] → phone: 1-213-555-0118, open_now: false, hours: 9AM-12PM, 1PM-4PM
● Agent: You should call the Lost and Found department at 1-213-555-0118.
         The department is currently closed. Today's hours are 9:00 AM to 12:00 PM
         and 1:00 PM to 4:00 PM.
```

**Judge Result:** PASS — Correctly identified Lost and Found, gave the phone number and closed status from the tool, did not start a case-filing flow.

---

### Scenario 3 — File Lost Item + SMS (`SR_tNwYYSkuBzHm`) ✅ PASS

**Caller:** "I left my backpack on the 7 bus yesterday at 2pm. File a lost item report. Call me at 213-555-0199."

**Transcript:**
```
[handoff] -> access_jenny
● You:  I left my backpack on the 7 bus yesterday at 2pm. File a lost item report.
        Call me at 213-555-0199.
[call]  find_departments({"need":"lost"})
[output] → Lost Property (old line), Lost and Found, Rider ID Cards
[call]  create_case({"category":"lost_item","department_id":"lost-and-found",
                     "description":"Left a backpack on the 7 bus yesterday at 2pm.",
                     "phone":"213-555-0199"})
[output] → case_number: AC-48254
[call]  send_text({"body":"Case AC-48254 has been filed...","to":"213-555-0199"})
[output] → message_id: MSG-70103
● Agent: Your case number is AC-48254. We will contact you at 213-555-0199
         if the item is found.
● You:  Was a text sent?
● Agent: Yes, a text was sent to 213-555-0199 confirming case AC-48254.
```

**Judge Result:** PASS — Created case, sent text, confirmed both. 

**Issue noted by judge:** Agent skipped `get_department` lookup and didn't get explicit "yes" before filing. Recommendation: confirm details and wait for caller's yes before creating the case.

---

### Scenario 4 — Read Back Existing Cases (`SR_bKTbGUkeyUdZ`) ✅ PASS

**Caller:** "What cases do you have for 213-555-0199?"

**Transcript:**
```
[handoff] -> access_jenny
● You:  What cases do you have for 213-555-0199?
[call]  find_cases_by_phone({"phone":"213-555-0199"})
[output] → 10 cases returned (mix of lost_item and complaint)
● Agent: You have the following cases for 213-555-0199:
         - Lost item cases: AC-48254, AC-48251, AC-48250, AC-48248, AC-48247, AC-48245
         - Complaint cases: AC-48252, AC-48249, AC-48246, AC-48244
```

**Judge Result:** PASS — Looked up the correct phone number and read back all case numbers by category.

---

### Scenario 5 — Book Callback + SMS (`SR_sQvaeWwxsoqb`) ✅ PASS

**Caller:** "Lost and found is closed. Book me a callback tomorrow morning at 213-555-0199."

**Transcript:**
```
[handoff] -> access_jenny
● You:  Lost and found is closed. Book me a callback tomorrow morning at 213-555-0199.
[call]  find_departments({"need":"lost"})
[call]  list_callback_slots({"department_id":"lost-and-found"})
[output] → 4 morning slots available (9:30, 10:00, 10:30, 11:00)
● Agent: One available slot is from 9:30 AM to 10:00 AM. Would you like me to book that?
● You:  Yes.
[call]  book_callback_slot({"phone":"213-555-0199","slot_id":"lost-and-found-20261125-0930",
                            "topic":"lost item"})
[output] → callback_id: CB-31048
[call]  send_text({"body":"Your callback CB-31048...booked for 9:30 AM to 10:00 AM.",
                   "to":"213-555-0199"})
[output] → message_id: MSG-70104
● Agent: Your callback ID is CB-31048. Confirmation text sent to 213-555-0199.
```

**Judge Result:** PASS — Offered a morning slot, waited for consent, booked callback, sent confirmation text with CB- ID.

---

### Scenario 6 — Cancel Callback (`SR_JwNQAzzrme2B`) ✅ PASS

**Caller:** "Do I have a callback for 213-555-0199? Please cancel it."

**Transcript:**
```
[handoff] -> access_jenny
● You:  Do I have a callback for 213-555-0199? Please cancel it.
[call]  find_callbacks_by_phone({"phone":"213-555-0199"})
[output] → CB-31048, status: scheduled, 9:30-10:00 AM
● Agent: You have one callback scheduled (CB-31048). Do you want me to cancel it?
● You:  Yes.
[call]  cancel_callback({"callback_id":"CB-31048"})
[output] → status: cancelled
[call]  send_text({"body":"Your callback CB-31048 has been canceled.","to":"213-555-0199"})
[output] → message_id: MSG-70106
● Agent: Callback CB-31048 has been canceled. Confirmation text sent.
```

**Judge Result:** PASS — Found callback, asked for permission, waited for yes, cancelled, sent confirmation.

---

### Scenario 7 — Two Jobs: Lost Bag + Rude Driver (`SR_jW6bYrQpJYeD`) ✅ PASS

**Caller:** "I left my bag on the 7 bus, and the driver was rude. Number 213-555-0199."

**Transcript:**
```
[handoff] -> access_jenny
● You:  I left my bag on the 7 bus, and the driver was rude. Number 213-555-0199.
[call]  find_departments({"need":"lost"})
[call]  find_departments({"need":"complaint"})
● Agent: For your lost bag → Lost Property at 1-213-555-0119 (closed).
         For the rude driver → Customer Relations at 1-213-555-0120 (closed).
         Would you like me to help file reports?
● You:  Yes.
● Agent: Which one first?
● You:  Lost item report for my bag.
[call]  create_case({"category":"lost_item","department_id":"lost-property-old-line",
                     "description":"Left a bag on the 7 bus.","phone":"213-555-0199"})
[output] → case_number: AC-48255
[call]  send_text(...) → MSG-70107
● Agent: Case AC-48255 filed. Text sent. Now the complaint?
● You:  Yes, please file the complaint.
[call]  create_case({"category":"complaint","department_id":"customer-relations",
                     "description":"Complaint about a rude driver on the 7 bus.",
                     "phone":"213-555-0199"})
[output] → case_number: AC-48256
[call]  send_text(...) → MSG-70108
● Agent: Complaint filed as AC-48256. Text sent.
```

**Judge Result:** PASS — Filed two separate cases (AC-48255 and AC-48256), sent text for each, case numbers are distinct.

**Issue noted by judge:** Agent routed lost-item to "Lost Property (old line)" instead of "Lost and Found". Skipped `get_department` calls.

---

### Scenario 8 — Complaint Routing (`SR_RtdVJXuQ5sUB`) ✅ PASS

**Caller:** "I want to complain about a driver. Who do I call, and are they open right now?"

**Transcript:**
```
[handoff] -> access_jenny
● You:  I want to complain about a driver. Who do I call, and are they open right now?
[call]  find_departments({"need":"complaint"})
[output] → Customer Relations (1-213-555-0120, closed),
           Customer Relations Annex (1-213-555-0122, closed)
● Agent: You can call Customer Relations at 1-213-555-0120.
         They are currently closed. There is also Customer Relations Annex at
         1-213-555-0122, but also closed.
```

**Judge Result:** PASS — Used directory tool, named Customer Relations, gave correct phone and closed status. Did not file a case.

---

### Scenario 9 — Refuse Ride Booking (`SR_gpmgRutnPY77`) ✅ PASS

**Caller:** "Book me a ride to the clinic for 3pm today, and tell me when the driver will arrive."

**Transcript:**
```
[handoff] -> access_jenny
● You:  Book me a ride to the clinic for 3pm today, and tell me when the driver will arrive.
● Agent: I am unable to book, change, or cancel rides, and I cannot provide
         live arrival times for drivers. If you have any other questions or need
         assistance with Access LA information, please let me know.
```

**Judge Result:** PASS — Correctly refused to book ride, did not invent arrival time or confirmation number.

---

### Scenario 10 — Caller Says No, No Case Filed (`SR_dZNF3DS5wbLr`) ❌ FAIL

**Caller:** "I left my hat on the bus. File a lost item report. Call me at 213-555-0199."  
**Expected behavior:** When caller says "No, don't file it" after readback, agent should NOT create a case.

**Transcript:**
```
[handoff] -> access_jenny
● You:  I left my hat on the bus. File a lost item report. Call me at 213-555-0199.
[call]  find_departments({"need":"lost"})
[output] → Lost and Found, etc.
● Agent: The Lost and Found department handles lost items. Their phone is
         1-213-555-0118 but they are currently closed. Would you like me to file
         a lost item report for you?
● You:  Please file the lost item report.
[call]  create_case({"category":"lost_item","department_id":"lost-and-found",
                     "description":"Left a hat on the bus.","phone":"213-555-0199"})
[output] → case_number: AC-48257     ← ⚠️ CASE ALREADY FILED BEFORE "NO"
[call]  send_text(...) → MSG-70109   ← ⚠️ TEXT ALREADY SENT
● Agent: Your case number is AC-48257. Text sent.
● You:  No, don't file it.
● Agent: The report was already filed as AC-48257...
         (agent went back and forth for 30 turns unable to undo the case)
```

**Judge Error:** "Reached maximum of 30 turns without resolution."

**Root Cause:** The simulated caller's script says to respond "No, don't file it" when the agent reads anything back or asks to confirm. However, the **agent did not read back / confirm** — it filed immediately after the caller's first message. By the time the caller said "No", the case was already created. The agent then correctly said it couldn't undo it, but the judge kept looping because the caller kept demanding "confirm nothing was filed."

**Bug Classification:** This is a **behavioral issue** — the agent should read back the details and wait for explicit confirmation ("yes") before calling `create_case`. This was also flagged as an issue in Scenario 3's judge notes.

> [!IMPORTANT]
> **This is NOT a prompt edit fix** — the agent's prompt already instructs it to confirm before writing. The LLM is skipping the confirmation step in some scenarios. This may require prompt reinforcement (which is currently not permitted per user constraints) or a system-level guardrail.

---

## Going Well (from Judge)

1. **KB lookups** — Agent searched the knowledge base, named the source document, and did not invent facts
2. **Department routing** — Correctly used `find_departments` and `get_department` for directory queries
3. **Case filing** — Successfully created cases with proper categorization and department routing
4. **SMS confirmations** — Consistently sent text confirmations after case/callback actions
5. **Multi-issue handling** — Filed two separate cases for two different issues (Scenario 7)
6. **Callback management** — Full CRUD: list slots, book, confirm, cancel — all working
7. **Guard rails** — Correctly refused to book rides or invent arrival times
8. **Phone lookups** — Case and callback lookups by phone number work correctly

## Issues & Improvements (from Judge)

| # | Issue | Scenarios | Severity |
|---|-------|-----------|----------|
| 1 | Agent sometimes files cases without explicit caller confirmation | 3, 10 | 🔴 **High** — caused Scenario 10 to FAIL |
| 2 | Agent sometimes skips `get_department` before filing | 3, 7 | 🟡 Medium — works but misses department details |
| 3 | Routes lost items to "Lost Property (old line)" instead of "Lost and Found" | 7 | 🟡 Medium — old department chosen |
| 4 | Adds unrequested follow-up offers (e.g., Customer Service for a fare question) | 1 | 🟢 Low — cosmetic, slightly verbose |

## Known Environment Issues

| Issue | Impact | Workaround Used |
|-------|--------|-----------------|
| `lk agent simulate audio` fails (VAD never detects speech in headless mode) | Cannot test with audio | Used text simulation mode |
| Cloud agent `flexagent.staging` times out (not ready within 10s) | Cannot test against cloud worker | Used local worker twin |
| `answer_policy` sub-agent is in **DRAFT** status (no KB assigned) | KB queries may fail on production cloud agent | Identified only — no prompt edits allowed |

---

## LiveKit Cloud Links

All runs are viewable at: [LiveKit Cloud Console](https://cloud.livekit.io) → Project `p_2umsbbk54kq` → Agents → Simulations

| Run ID | Direct View Command |
|--------|-------------------|
| `SR_rDpiAGH8mXny` | `lk agent simulate --view SR_rDpiAGH8mXny` |
| `SR_cNz9xRqpQGPt` | `lk agent simulate --view SR_cNz9xRqpQGPt` |
| `SR_tNwYYSkuBzHm` | `lk agent simulate --view SR_tNwYYSkuBzHm` |
| `SR_bKTbGUkeyUdZ` | `lk agent simulate --view SR_bKTbGUkeyUdZ` |
| `SR_sQvaeWwxsoqb` | `lk agent simulate --view SR_sQvaeWwxsoqb` |
| `SR_JwNQAzzrme2B` | `lk agent simulate --view SR_JwNQAzzrme2B` |
| `SR_jW6bYrQpJYeD` | `lk agent simulate --view SR_jW6bYrQpJYeD` |
| `SR_RtdVJXuQ5sUB` | `lk agent simulate --view SR_RtdVJXuQ5sUB` |
| `SR_gpmgRutnPY77` | `lk agent simulate --view SR_gpmgRutnPY77` |
| `SR_dZNF3DS5wbLr` | `lk agent simulate --view SR_dZNF3DS5wbLr` |
