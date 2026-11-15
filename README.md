# Access LA — FlexAgents Hackathon (Team 1 Track B APIs)

FastAPI backend for **Dr. Atif / Team 1 General Inquiry**: Directory, Cases, Callbacks, and Message Outbox.  
Access LA–aligned department phones/hours (2026 Rider’s Guide + accessla.org).

Repo: https://github.com/waseem-akram-senarios/Access-la-FlexAgents-Hackathon

## Run locally

```bash
pip install -r requirements.txt
PYTHONPATH=. python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8787
```

- OpenAPI: http://127.0.0.1:8787/docs  
- Health: http://127.0.0.1:8787/health

## Deploy (Render — free public HTTPS)

1. Open [Render Blueprint](https://dashboard.render.com/blueprints) → **New Blueprint Instance**
2. Connect this GitHub repo
3. Confirm `render.yaml` → Create
4. Use the `*.onrender.com` URL in FlexAgents Connections

Or create a **Web Service** manually:

| Setting | Value |
|---------|--------|
| Runtime | Python 3 |
| Build | `pip install -r requirements.txt` |
| Start | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check | `/health` |
| Plan | Free |

Docker:

```bash
docker build -t access-la-api .
docker run -p 8787:8787 -e PORT=8787 access-la-api
```

### Env

| Var | Default | Meaning |
|-----|---------|---------|
| `PORT` / `SPECTAC_PORT` | `8787` | Listen port (cloud hosts set `PORT`) |
| `SPECTAC_CHAOS` | `0` | `1` = random 503s |
| `SPECTAC_CHAOS_RATE` | `0.15` | Fail fraction when chaos on |
| `SPECTAC_TZ` | `America/Los_Angeles` | Hours / open_now |

Bypass chaos per request: header `X-Spectac-Chaos: off`.

## Endpoints

| API | Methods |
|-----|---------|
| Directory | `GET /departments?need=`, `GET /departments/{id}` |
| Cases | `POST /cases` (+ `Idempotency-Key`), `GET /cases/{id}`, `GET /cases?phone=` |
| Callbacks | `GET /slots?dept=&date=`, `POST /callbacks`, `DELETE /callbacks/{id}` |
| Outbox | `POST /messages`, `GET /messages?to=` |

## FlexAgents Connections

Point sub-agents at the deployed base URL:

- `find_department` → Directory
- `log_case` → Cases + Message Outbox
- `book_callback` → Callbacks + Message Outbox

## Tests

```bash
PYTHONPATH=. pytest -q
```
