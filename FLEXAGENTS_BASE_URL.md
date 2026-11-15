# Stable base URL for FlexAgents (hardcode this)

## Permanent production URL

```
https://access-la-flexagents-api.vercel.app
```

Dashboard: https://vercel.com/waseem-c23c/access-la-flexagents-api

Use this root in all sub-agent Connections / prompts — **it does not change**:

| Sub-agent | Base |
|-----------|------|
| find_department | `https://access-la-flexagents-api.vercel.app` |
| log_case | `https://access-la-flexagents-api.vercel.app` |
| book_callback | `https://access-la-flexagents-api.vercel.app` |

Examples:
- `GET /departments?need=lost`
- `POST /cases` (+ `Idempotency-Key`)
- `GET /slots?dept=&date=`
- `POST /messages`

Docs: https://access-la-flexagents-api.vercel.app/docs  
Health: https://access-la-flexagents-api.vercel.app/health

Do **not** use `*.tmp.now` URLs in prompts.
