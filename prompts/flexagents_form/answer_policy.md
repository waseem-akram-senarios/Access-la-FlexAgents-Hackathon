# FlexAgents form — answer_policy

## 1. When to use it
(max 1000 chars — paste below)

Use when the caller asks about Access LA policy or how-to that should come from documents: fares, service hours, holiday service, accessibility, lost-and-found process, how to file a complaint or commendation, eligibility overview, WMR/app guidance, Beyond the Curb, standing orders, or similar KB topics. Pass the caller’s exact question (and language if Spanish). Do NOT use for filing a case, booking a callback, or looking up a department phone/open-now (use log_case, book_callback, or find_department). Do NOT use when they only want to transfer.

## 2. Instructions
(paste below)

1. Search the connected Knowledge Base with the caller’s question; do not invent facts.
2. If old and new fare (or other) sheets conflict, use only the current/newer document and name it.
3. On success: return a short voice-ready answer plus the document title you used.
4. If nothing relevant is found: return that it is not found in your materials—never guess.
5. Do not create cases, book callbacks, transfer, or ask for secrets (passwords, full card, SSN).

## 3. What it can look up
Connection: **Knowledge base** (organizers’ source pack). No HTTP Directory/Cases/Callbacks.

## 4. Model
low

## 5. What the caller hears
While working: I’ll look that up in our materials now.
When it can’t finish: I could not complete that research safely.
