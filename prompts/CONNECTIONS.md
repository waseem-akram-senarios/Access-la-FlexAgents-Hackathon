# FlexAgents Connections cheat sheet

Permanent API base (hardcode everywhere for API sub-agents):

```
https://access-la-flexagents-api.vercel.app
```

| Sub-agent | Mode | Connection |
|-----------|------|------------|
| `answer_policy` | look-up | Knowledge base (organizers’ source pack) |
| `find_department` | look-up | Directory API → base URL above |
| `log_case` | changes data | Cases + Message Outbox → base URL above |
| `book_callback` | changes data | Callbacks + Message Outbox → base URL above |

OpenAPI: https://access-la-flexagents-api.vercel.app/docs

## Suggested HTTP tools to register
- `GET {base}/departments?need=`
- `GET {base}/departments/{id}`
- `POST {base}/cases` (+ header `Idempotency-Key`)
- `GET {base}/cases/{id}`
- `GET {base}/cases?phone=`
- `GET {base}/slots?dept=&date=`
- `POST {base}/callbacks` (+ `Idempotency-Key`)
- `DELETE {base}/callbacks/{id}`
- `POST {base}/messages`
- `GET {base}/messages?to=`

Optional header on all: `X-Spectac-Chaos: off`
