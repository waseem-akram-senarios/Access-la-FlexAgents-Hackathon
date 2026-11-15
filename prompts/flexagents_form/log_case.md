# FlexAgents form — log_case

## 1. When to use it
(max 1000 chars — paste below)

Use when the caller wants to file a complaint, commendation/compliment, or lost-item report (or the second of two jobs in one call, e.g. rude driver after a lost bag). Pass: category (complaint|commendation|lost_item), description, callback phone, incident date/time if known, route/vehicle if known, department_id if find_department already ran, and rider name if given. For two issues in one utterance, call this once per issue after each read-back—never mix two cases. Do NOT use for general policy answers (answer_policy), department lookup only (find_department), or booking a callback slot (book_callback).

## 2. Instructions
(paste below)

Base URL: https://access-la-flexagents-api.vercel.app
Header: X-Spectac-Chaos: off

1. Collect missing fields one at a time: category, summary/description, phone, incident_at (ISO if known), route, vehicle, department_id, rider_name.
2. Read back category, when, route/vehicle, description, and callback phone. Wait for a clear yes. Do not POST without confirmation.
3. POST /cases with Idempotency-Key unique per filing. Body: phone, topic, category, summary, incident_at, route, vehicle, department_id, rider_name, priority normal.
4. On success: return case_number (ACC-YYYYMMDD-####) and id. Optionally GET /cases/{id} or GET /cases?phone= to confirm.
5. POST /messages with to=phone, from=ACCESS-LA, body including case_number, case_id set. Optionally GET /messages?to= to verify.
6. If SMS fails: case still stands—return case_number and say text failed.
7. Same Idempotency-Key returns the first case; do not treat as a new filing.
8. On API error: say the case could not be filed; do not invent a case number.

## 3. What it can look up
Connection: **Cases + Message Outbox HTTP** → https://access-la-flexagents-api.vercel.app  
Tools: POST /cases, GET /cases/{id}, GET /cases?phone=, POST /messages, GET /messages?to=

## 4. Model
low

## 5. What the caller hears
While working: I’ll prepare that report for you now.
When it can’t finish: I could not complete filing that case safely.
