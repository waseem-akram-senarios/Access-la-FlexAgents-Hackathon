# FlexAgents form — find_department

## 1. When to use it
(max 1000 chars — paste below)

Use when the caller needs the right Access LA department, its phone number, today’s hours, or whether it is open right now—e.g. who handles lost items, complaints, eligibility, OMC/urgent same-day issues, reservations, WMR tech support, travel training, ADA/Title VI, fare/billing, or Beyond the Curb. Pass a short need keyword or the caller’s need in plain words (lost, complaint, urgent, eligibility, fare, wmr, reservation, etc.). Do NOT use to answer long policy from the KB (answer_policy), file a case (log_case), or book a callback (book_callback)—but DO use before offering transfer or book_callback so the main agent knows open_now and department id.

## 2. Instructions
(paste below)

Base URL: https://access-la-flexagents-api.vercel.app
Header: X-Spectac-Chaos: off

1. Map the need to a keyword (lost, complaint, urgent/omc, eligibility, fare, wmr, reservation, travel training, ada/title vi, beyond the curb).
2. Call GET /departments?need={keyword}. If unclear, GET /departments then pick the best match.
3. Optionally GET /departments/{id} to confirm the full record.
4. Return for the conversation agent: id, name, phone, menu_option (if any), tdd (if any), open_now, closed_today, and today’s hours (America/Los_Angeles from hours/holiday_overrides).
5. If open_now is true, note transfer is appropriate; if false or closed_today, note book_callback should be offered with this id.
6. On API failure: say the directory lookup failed; do not invent phones or hours.

## 3. What it can look up
Connection: **Directory HTTP** → https://access-la-flexagents-api.vercel.app  
Tools: GET /departments, GET /departments?need=, GET /departments/{id}

## 4. Model
low

## 5. What the caller hears
While working: I’ll find the right department for you now.
When it can’t finish: I could not look up that department safely.
