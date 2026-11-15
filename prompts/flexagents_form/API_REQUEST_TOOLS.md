# FlexAgents — Create API Request Tool (paste each one)

**Base:** `https://access-la-flexagents-api.vercel.app`  
**Default headers (all tools):**
- `Accept: application/json`
- `X-Spectac-Chaos: off`  
**Timeout:** `10000` (or `15000` if cold starts)

Only **sub-agents** call these tools. Attach them on the sub-agent under “What it can look up”.

---

## 1) list_departments
| Field | Value |
|--------|--------|
| Name | `list_departments` |
| Makes changes? | **No** (look-up) |
| What it does | Lists Access LA departments; optional `need` filter returns matching depts with phone, hours, open_now, closed_today. |
| When / why | Use when find_department must route a caller need (lost, complaint, urgent, fare, etc.) or browse all departments. |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/departments?need={need}` |
| Notes | If need unknown, call without query: `.../departments` |

---

## 2) get_department
| Field | Value |
|--------|--------|
| Name | `get_department` |
| Makes changes? | **No** |
| What it does | Returns one department by id (phone, menu_option, hours, open_now, closed_today). |
| When / why | After list_departments picks an id, confirm full detail before speaking or handing off. |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/departments/{department_id}` |
| Example id | `dept_lost_found` |

**Attach to:** `find_department`

---

## 3) create_case
| Field | Value |
|--------|--------|
| Name | `create_case` |
| Makes changes? | **Yes** |
| What it does | Creates a complaint, commendation, or lost_item case; returns case_number `ACC-YYYYMMDD-####`. Same Idempotency-Key returns the first case. |
| When / why | Only after log_case read-back and clear yes from the caller. |
| Method | `POST` |
| URL | `https://access-la-flexagents-api.vercel.app/cases` |
| Headers | `Content-Type: application/json` · `Idempotency-Key: {idempotency_key}` · `X-Spectac-Chaos: off` |
| Body | `{"phone":"{phone}","topic":"{topic}","category":"{category}","summary":"{summary}","incident_at":"{incident_at}","route":"{route}","vehicle":"{vehicle}","department_id":"{department_id}","rider_name":"{rider_name}","priority":"normal"}` |
| category | `complaint` \| `commendation` \| `lost_item` \| `other` |

---

## 4) get_case
| Field | Value |
|--------|--------|
| Name | `get_case` |
| Makes changes? | **No** |
| What it does | Fetches a case by id or case_number. |
| When / why | Confirm a filing or look up an existing case. |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/cases/{case_id}` |

---

## 5) list_cases_by_phone
| Field | Value |
|--------|--------|
| Name | `list_cases_by_phone` |
| Makes changes? | **No** |
| What it does | Lists cases for a callback phone number. |
| When / why | Caller asks about prior reports or follow-up by phone. |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/cases?phone={phone}` |

**Attach 3–5 (+ messages below) to:** `log_case`

---

## 6) list_slots
| Field | Value |
|--------|--------|
| Name | `list_slots` |
| Makes changes? | **No** |
| What it does | Lists callback slots for a department and date; shows available capacity. |
| When / why | Before booking a callback when department is closed. |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/slots?dept={department_id}&date={date}` |
| date | `YYYY-MM-DD` |

---

## 7) create_callback
| Field | Value |
|--------|--------|
| Name | `create_callback` |
| Makes changes? | **Yes** |
| What it does | Books a callback slot. Returns 409 if slot is full. |
| When / why | After book_callback reads back a slot and caller says yes. |
| Method | `POST` |
| URL | `https://access-la-flexagents-api.vercel.app/callbacks` |
| Headers | `Content-Type: application/json` · `Idempotency-Key: {idempotency_key}` · `X-Spectac-Chaos: off` |
| Body | `{"department_id":"{department_id}","slot_id":"{slot_id}","phone":"{phone}","name":"{name}","reason":"{reason}"}` |

---

## 8) get_callback
| Field | Value |
|--------|--------|
| Name | `get_callback` |
| Makes changes? | **No** |
| What it does | Fetches a callback booking by id (status booked/cancelled). |
| When / why | Confirm a booking after create. |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/callbacks/{callback_id}` |

---

## 9) cancel_callback
| Field | Value |
|--------|--------|
| Name | `cancel_callback` |
| Makes changes? | **Yes** |
| What it does | Cancels a callback and frees the slot. |
| When / why | Caller asks to cancel a booked callback. |
| Method | `DELETE` |
| URL | `https://access-la-flexagents-api.vercel.app/callbacks/{callback_id}` |

**Attach 6–9 (+ messages) to:** `book_callback`

---

## 10) send_message
| Field | Value |
|--------|--------|
| Name | `send_message` |
| Makes changes? | **Yes** |
| What it does | Stores a fake SMS in the Message Outbox for judges (case number or callback confirm). |
| When / why | After a successful create_case or create_callback; text the confirmation to the caller’s phone. |
| Method | `POST` |
| URL | `https://access-la-flexagents-api.vercel.app/messages` |
| Headers | `Content-Type: application/json` · `X-Spectac-Chaos: off` |
| Body | `{"to":"{phone}","from":"ACCESS-LA","body":"{body}","case_id":"{case_id}"}` |
| Notes | If this fails, case/callback still stands—tell the caller verbally. |

---

## 11) list_messages
| Field | Value |
|--------|--------|
| Name | `list_messages` |
| Makes changes? | **No** |
| What it does | Lists outbox messages for a phone so judges/agent can verify what was “sent”. |
| When / why | Verify SMS after send_message, or answer “was a text sent?” |
| Method | `GET` |
| URL | `https://access-la-flexagents-api.vercel.app/messages?to={phone}` |

**Attach 10–11 to:** both `log_case` and `book_callback`

---

## Sub-agent checklist

| Sub-agent | Select these tools |
|-----------|-------------------|
| `answer_policy` | *(Knowledge base connection only — no API Request tools)* |
| `find_department` | `list_departments`, `get_department` |
| `log_case` | `create_case`, `get_case`, `list_cases_by_phone`, `send_message`, `list_messages` |
| `book_callback` | `list_slots`, `create_callback`, `get_callback`, `cancel_callback`, `send_message`, `list_messages` |

## Conversation agent (Jenny)
Jenny does **not** call these tools directly. She hands off to sub-agents that have the tools selected.
