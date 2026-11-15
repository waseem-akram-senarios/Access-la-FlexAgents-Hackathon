# FlexAgents form — book_callback

## 1. When to use it
(max 1000 chars — paste below)

Use when find_department shows the department is closed (open_now false or closed_today true), or transfer was offered but did not complete, and the caller agrees to a callback. Pass: department_id (required), callback phone, preferred date YYYY-MM-DD (default today America/Los_Angeles), name and reason if given. Also use when the caller asks to cancel an existing callback (pass callback id). Do NOT use for KB policy answers, department lookup alone, or filing complaint/lost-item cases (use answer_policy, find_department, log_case).

## 2. Instructions
(paste below)

Base URL: https://access-la-flexagents-api.vercel.app
Header: X-Spectac-Chaos: off

1. Confirm department_id and phone. Date = caller’s date or today (YYYY-MM-DD).
2. GET /slots?dept={department_id}&date={date}. Pick a slot with available true.
3. Read back date, start–end time, and department. Wait for clear yes before booking.
4. POST /callbacks with Idempotency-Key unique per booking: department_id, slot_id, phone, name, reason.
5. If 409 slot_taken: GET /slots again and offer another available slot—never force a full slot.
6. On success: optionally GET /callbacks/{id} to confirm status booked.
7. POST /messages to=phone, from=ACCESS-LA, body with date/time and callback id. Optionally GET /messages?to= to verify.
8. If SMS fails: booking still stands—tell date/time verbally and that text failed.
9. Cancel only if asked: DELETE /callbacks/{id}.
10. On API failure: say booking could not be completed; do not invent a slot.

## 3. What it can look up
Connection: **Callbacks + Message Outbox HTTP** → https://access-la-flexagents-api.vercel.app  
Tools: GET /slots, POST /callbacks, GET /callbacks/{id}, DELETE /callbacks/{id}, POST /messages, GET /messages?to=

## 4. Model
low

## 5. What the caller hears
While working: I’ll check callback times for you now.
When it can’t finish: I could not complete that callback booking safely.
