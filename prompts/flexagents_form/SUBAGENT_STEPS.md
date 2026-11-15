# Each sub-agent — tools + step-by-step

**API base:** `https://access-la-flexagents-api.vercel.app`  
**Header on all HTTP calls:** `X-Spectac-Chaos: off`  
Jenny (conversation agent) does **not** call these tools; she hands off to the sub-agent.

---

# 1) answer_policy

### Tools
| Tool | Type | Changes? |
|------|------|----------|
| Knowledge base search | KB connection | No |

**No** Directory / Cases / Callbacks / Outbox HTTP tools.

### Step by step
1. Jenny detects a **policy / how-to** question (fares, hours, holiday, accessibility, L&F process, complaints process, eligibility overview, WMR help, etc.).
2. Jenny hands the **exact question** to `answer_policy`.
3. Sub-agent **searches the Knowledge base**.
4. If old + new fare sheets conflict → use **current/newer only** and **name the document**.
5. **Success:** return short answer + document title → Jenny speaks it.
6. **Not found:** return “not found in materials” → Jenny says that (no guessing).
7. Never file cases, book callbacks, or invent phones/fares.

### Caller hears
- Working: *I’ll look that up in our materials now.*
- Fail: *I could not complete that research safely.*

---

# 2) find_department

### Tools
| Tool name | Method | URL | Changes? |
|-----------|--------|-----|----------|
| `list_departments` | GET | `/departments?need={need}` or `/departments` | No |
| `get_department` | GET | `/departments/{department_id}` | No |

### Step by step
1. Jenny detects need for a **department / phone / open now** (lost item who to call, complaint line, OMC, eligibility, fare, WMR, etc.).
2. Pass a short **need** keyword (`lost`, `complaint`, `urgent`, `eligibility`, `fare`, `wmr`, `reservation`, …).
3. Call **`list_departments`** with `need=…`.
4. If unclear, call **`list_departments`** with no filter, then pick best match.
5. Call **`get_department`** with chosen `id` (e.g. `dept_lost_found`) to confirm.
6. Return to Jenny: `id`, `name`, `phone`, `menu_option`, `open_now`, `closed_today`, today’s hours.
7. Jenny next:
   - if `open_now` = true → offer **transfer** to `phone`
   - if closed → offer **`book_callback`** with that `department_id`

### Caller hears
- Working: *I’ll find the right department for you now.*
- Fail: *I could not look up that department safely.*

---

# 3) log_case

### Tools
| Tool name | Method | URL | Changes? |
|-----------|--------|-----|----------|
| `create_case` | POST | `/cases` + `Idempotency-Key` | **Yes** |
| `get_case` | GET | `/cases/{case_id}` | No |
| `list_cases_by_phone` | GET | `/cases?phone={phone}` | No |
| `send_message` | POST | `/messages` | **Yes** |
| `list_messages` | GET | `/messages?to={phone}` | No |

### Step by step
1. Jenny detects **complaint / commendation / lost item** (or one job of a two-job call).
2. Collect (one field at a time if needed):
   - `category`: `complaint` | `commendation` | `lost_item`
   - `summary` (description)
   - `phone` (callback number)
   - `incident_at` if known
   - `route` / `vehicle` if known
   - `department_id` if `find_department` already ran
3. **Read back** all of the above → wait for clear **yes**.
4. Call **`create_case`** (POST `/cases`) with unique `Idempotency-Key`.
5. Optional: **`get_case`** to confirm; or **`list_cases_by_phone`** if checking history.
6. Speak **`case_number`** (`ACC-YYYYMMDD-####`).
7. Call **`send_message`** with body including case number (`to` = callback phone, `from` = `ACCESS-LA`).
8. Optional: **`list_messages`** to verify outbox.
9. If SMS fails → case **still stands**; say case number aloud + text failed.
10. Two jobs: finish this whole chain + pause, then run again for the second issue.

### Caller hears
- Working: *I’ll prepare that report for you now.*
- Fail: *I could not complete filing that case safely.*

### Example create_case body
```json
{
  "phone": "2135550100",
  "topic": "lost item",
  "category": "lost_item",
  "summary": "Left bag on the 7 bus.",
  "incident_at": "2026-11-14T14:00:00-08:00",
  "route": "7",
  "department_id": "dept_lost_found"
}
```

---

# 4) book_callback

### Tools
| Tool name | Method | URL | Changes? |
|-----------|--------|-----|----------|
| `list_slots` | GET | `/slots?dept={department_id}&date={date}` | No |
| `create_callback` | POST | `/callbacks` + `Idempotency-Key` | **Yes** |
| `get_callback` | GET | `/callbacks/{callback_id}` | No |
| `cancel_callback` | DELETE | `/callbacks/{callback_id}` | **Yes** |
| `send_message` | POST | `/messages` | **Yes** |
| `list_messages` | GET | `/messages?to={phone}` | No |

### Step by step
1. Jenny uses this when department is **closed** / transfer failed and caller wants a callback.
2. Need: `department_id`, `phone`, `date` (`YYYY-MM-DD`, default today LA time).
3. Call **`list_slots`** → pick a slot with `"available": true`.
4. **Read back** date + start–end + department → wait for clear **yes**.
5. Call **`create_callback`** (POST `/callbacks`) with unique `Idempotency-Key`.
6. If **409** (slot taken): go back to step 3, pick another slot.
7. Optional: **`get_callback`** to confirm `status: booked`.
8. Call **`send_message`** with date/time + callback id.
9. Optional: **`list_messages`** to verify.
10. If SMS fails → **booking stands**; say date/time verbally + text failed.
11. If caller wants cancel → **`cancel_callback`** (DELETE).

### Caller hears
- Working: *I’ll check callback times for you now.*
- Fail: *I could not complete that callback booking safely.*

### Example create_callback body
```json
{
  "department_id": "dept_customer_service",
  "slot_id": "slot_dept_customer_service_2026-11-15_0900",
  "phone": "2135550100",
  "name": "Alex",
  "reason": "Department closed"
}
```

---

# Full call flow (typical)

```
Caller question
    │
    ├─ Policy / fares / process ──► answer_policy (KB)
    │
    ├─ Who do I call? / open now? ──► find_department
    │         │
    │         ├─ open_now true ──► Jenny offers TRANSFER
    │         └─ closed ──► book_callback (slots → book → SMS)
    │
    └─ Complaint / lost item / compliment ──► log_case
              (read-back → create_case → send_message)
```

**Two jobs example:** “bag on the 7 bus + driver was rude”  
→ `log_case` (lost_item) end-to-end → pause → `log_case` (complaint) end-to-end.
