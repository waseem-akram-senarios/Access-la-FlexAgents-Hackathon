# FlexAgents Connections — wire every API

**Base URL (hardcode):** `https://access-la-flexagents-api.vercel.app`  
**Docs:** https://access-la-flexagents-api.vercel.app/docs  
**Full map:** see `API_TOOL_MAP.md`

| Sub-agent | Connection type | Endpoints it must be able to call |
|-----------|-----------------|-----------------------------------|
| `answer_policy` | Knowledge base | *(no HTTP — KB only)* |
| `find_department` | Directory HTTP | `GET /departments`, `GET /departments?need=`, `GET /departments/{id}` |
| `log_case` | Cases + Outbox HTTP | `POST /cases`, `GET /cases/{id}`, `GET /cases?phone=`, `POST /messages`, `GET /messages?to=` |
| `book_callback` | Callbacks + Outbox HTTP | `GET /slots`, `POST /callbacks`, `GET /callbacks/{id}`, `DELETE /callbacks/{id}`, `POST /messages`, `GET /messages?to=` |

## Default headers
- `X-Spectac-Chaos: off`
- Writes: also `Idempotency-Key: <unique>` on `POST /cases` and `POST /callbacks`
- `Content-Type: application/json` on POST bodies

## Checklist before demo
- [ ] Each API sub-agent Connection points at `https://access-la-flexagents-api.vercel.app`
- [ ] All rows in the table above are registered as tools for that sub-agent
- [ ] Prompt files `02_`, `03_`, `04_` pasted into those sub-agents
- [ ] Main prompt `00_` routes to the four sub-agents
- [ ] Smoke: `/health` returns ok
