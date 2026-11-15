# Stable base URL for FlexAgents (hardcode this)

Do **not** hardcode `*.tmp.now` — those expire and change.

## Permanent URL (after one-time claim / Git import)

```
https://access-la-flexagents-api.vercel.app
```

Use that as the API root in all sub-agent Connections / prompts:

| Sub-agent | Base |
|-----------|------|
| find_department | `https://access-la-flexagents-api.vercel.app` |
| log_case | `https://access-la-flexagents-api.vercel.app` |
| book_callback | `https://access-la-flexagents-api.vercel.app` |

Examples:
- `GET https://access-la-flexagents-api.vercel.app/departments?need=lost`
- `POST https://access-la-flexagents-api.vercel.app/cases`
- `GET https://access-la-flexagents-api.vercel.app/slots?dept=dept_lost_found&date=2026-11-15`
- `POST https://access-la-flexagents-api.vercel.app/messages`

## How to lock this name (once)

### Option A — Claim the temp deploy (fastest)
1. Open: https://vercel.com/claim-deployment?code=0a99a218-8206-4e13-9b7b-15bf77a8c3dd  
   (if expired, redeploy then claim the new code)
2. Sign in with GitHub (free Hobby — usually no card for basic)
3. In Project Settings → Domains, keep / set:  
   `access-la-flexagents-api.vercel.app`

### Option B — Import GitHub repo (best long-term)
1. https://vercel.com/new  
2. Import `waseem-akram-senarios/Access-la-FlexAgents-Hackathon`  
3. Project name: `access-la-flexagents-api`  
4. Deploy → URL stays: `https://access-la-flexagents-api.vercel.app`

After that, the URL **does not change** on every deploy (only the deployment ID behind it does).
