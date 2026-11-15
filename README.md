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

## Deploy free (no credit card) → PythonAnywhere

See **[PYTHONANYWHERE.md](PYTHONANYWHERE.md)**.

Free forever Beginner plan → `https://YOUR_USERNAME.pythonanywhere.com`  
No card required. Best option when Render/Railway ask for billing.

Other no-card free hosts (also sleep when idle): [Faable](https://faable.com/deploy/fastapi), [EthioDeploy](https://ethiodeploy.com/deploy/fastapi).

## Endpoints

| API | Methods |
|-----|---------|
| Directory | `GET /departments?need=`, `GET /departments/{id}` |
| Cases | `POST /cases` (+ `Idempotency-Key`), `GET /cases/{id}`, `GET /cases?phone=` |
| Callbacks | `GET /slots?dept=&date=`, `POST /callbacks`, `DELETE /callbacks/{id}` |
| Outbox | `POST /messages`, `GET /messages?to=` |

### Env

| Var | Default | Meaning |
|-----|---------|---------|
| `PORT` / `SPECTAC_PORT` | `8787` | Listen port |
| `SPECTAC_CHAOS` | `0` | `1` = random 503s |
| `SPECTAC_TZ` | `America/Los_Angeles` | Hours / open_now |

## Tests

```bash
PYTHONPATH=. pytest -q
```
