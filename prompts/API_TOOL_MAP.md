# API coverage map — every hosted endpoint → sub-agent

Base: `https://access-la-flexagents-api.vercel.app`

| Method | Endpoint | Owner sub-agent | When to call |
|--------|----------|-----------------|--------------|
| GET | `/departments?need=` | `find_department` | Map caller need → department list |
| GET | `/departments/{id}` | `find_department` | Full detail after pick |
| GET | `/departments` | `find_department` | Browse all if need unclear |
| POST | `/cases` | `log_case` | After read-back + yes |
| GET | `/cases/{id}` | `log_case` | Confirm / read back case |
| GET | `/cases?phone=` | `log_case` | Prior cases for this phone |
| GET | `/slots?dept=&date=` | `book_callback` | List open slots |
| POST | `/callbacks` | `book_callback` | After read-back + yes |
| GET | `/callbacks/{id}` | `book_callback` | Confirm booking |
| DELETE | `/callbacks/{id}` | `book_callback` | Caller cancels |
| POST | `/messages` | `log_case` **and** `book_callback` | Fake SMS after success |
| GET | `/messages?to=` | `log_case` **and** `book_callback` | Verify text for judges / “was it sent?” |
| GET | `/health` | (ops only) | Not for callers |
| POST | `/admin/reset` | (ops only) | Never from agents |

`answer_policy` uses the **Knowledge base** only (no HTTP API).

## Register these HTTP tools in FlexAgents (copy)

Base URL for all: `https://access-la-flexagents-api.vercel.app`  
Default header: `X-Spectac-Chaos: off`

### find_department tools
1. `list_departments` — GET `/departments` optional query `need`
2. `get_department` — GET `/departments/{id}`

### log_case tools
3. `create_case` — POST `/cases` + header `Idempotency-Key`
4. `get_case` — GET `/cases/{id}` (id or case_number)
5. `list_cases_by_phone` — GET `/cases?phone=`
6. `send_message` — POST `/messages`
7. `list_messages` — GET `/messages?to=`

### book_callback tools
8. `list_slots` — GET `/slots?dept=&date=`
9. `create_callback` — POST `/callbacks` + header `Idempotency-Key`
10. `get_callback` — GET `/callbacks/{id}`
11. `cancel_callback` — DELETE `/callbacks/{id}`
12. `send_message` — POST `/messages` (same as log_case)
13. `list_messages` — GET `/messages?to=` (same as log_case)
