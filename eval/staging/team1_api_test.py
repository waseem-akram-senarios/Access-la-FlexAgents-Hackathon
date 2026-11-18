"""Live checks for every Team 1 inquiry service. Reads keys from .env. Never prints them.

Does not reset the database, change the clock, or turn chaos on.
Writes use the fake number 2135550199 and idempotency keys.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
BASE = os.environ.get("TEAM1_API_BASE", "https://team1-inquiry-api.vercel.app")
PHONE = "2135550199"


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


def call(method: str, path: str, key: str | None, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req_headers = {"Accept": "application/json"}
    if key:
        req_headers["X-API-Key"] = key
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = Request(BASE + path, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            parsed = json.loads(raw) if raw else None
            return resp.status, dict(resp.headers), parsed
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = raw[:300]
        return exc.code, dict(exc.headers), parsed


def main() -> None:
    load_env()
    global BASE
    BASE = os.environ.get("TEAM1_API_BASE", BASE)
    directory = os.environ["DIRECTORY_API_KEY"]
    cases = os.environ["CASES_API_KEY"]
    callbacks = os.environ["CALLBACKS_API_KEY"]
    messages = os.environ["MESSAGES_API_KEY"]
    admin = os.environ["ADMIN_API_KEY"]
    results: list[tuple[str, str, bool, str]] = []

    def record(bot: str, name: str, ok: bool, detail: str) -> None:
        results.append((bot, name, ok, detail))
        print(("PASS" if ok else "FAIL"), bot, name, detail)

    status, _, body = call("GET", "/health", None)
    record("shared", "health", status == 200 and isinstance(body, dict) and body.get("ok") is True, f"{status}")

    status, _, body = call("GET", "/departments?need=lost&limit=5", directory)
    rows = body.get("results") if isinstance(body, dict) else None
    chosen = next((d for d in rows if d.get("id") == "lost-and-found"), None) if rows else None
    record(
        "directory",
        "find lost-and-found",
        bool(chosen and chosen.get("phone")),
        f"{status} phone={None if not chosen else chosen.get('phone')} open_now={None if not chosen else chosen.get('open_now')}",
    )

    status, _, body = call("GET", "/departments/lost-and-found", directory)
    record(
        "directory",
        "get department",
        status == 200 and isinstance(body, dict) and body.get("id") == "lost-and-found",
        f"{status}",
    )

    status, _, body = call(
        "POST",
        "/transfers",
        directory,
        {"department_id": "lost-and-found", "summary": "Eval transfer check. Not a real caller.", "caller_phone": PHONE},
        {"Idempotency-Key": "eval-team1-transfer-2135550199"},
    )
    # Closed departments must not pretend the transfer connected.
    transfer_status = body.get("status") if isinstance(body, dict) else None
    closed_ok = status in (409, 422) or transfer_status in {"closed", "not_connected", "unavailable"}
    record(
        "directory",
        "transfer while closed is honest",
        closed_ok,
        f"{status} status={transfer_status}",
    )

    status, _, _ = call("GET", "/departments?need=lost", cases)
    record("directory", "cases key rejected", status == 401, f"{status}")

    case_body = {
        "category": "lost_item",
        "incident_at": "2026-11-17T10:00:00-08:00",
        "description": "Eval test only. Black cane. Not a real rider.",
        "callback_phone": PHONE,
        "department_id": "lost-and-found",
    }
    status, _, body = call("POST", "/cases", cases, case_body, {"Idempotency-Key": "eval-team1-case-2135550199-b"})
    case_number = body.get("case_number") if isinstance(body, dict) else None
    record("cases", "create lost-item case", status in (200, 201) and bool(case_number), f"{status} {case_number}")

    status, headers, body = call("POST", "/cases", cases, case_body, {"Idempotency-Key": "eval-team1-case-2135550199-b"})
    replayed = str(headers.get("Idempotent-Replayed", "")).lower() == "true"
    record("cases", "idempotent replay", status in (200, 201) and replayed and isinstance(body, dict) and body.get("case_number") == case_number, f"{status} replayed={replayed}")

    if case_number:
        status, _, body = call("GET", f"/cases/{case_number}", cases)
        record("cases", "get case", status == 200 and isinstance(body, dict), f"{status}")

    status, _, body = call("GET", f"/cases?phone={PHONE}&limit=5", cases)
    listed = body if isinstance(body, list) else (body.get("results") if isinstance(body, dict) else None)
    record("cases", "list by phone", status == 200 and isinstance(listed, list) and len(listed) >= 1, f"{status} count={len(listed) if isinstance(listed, list) else None}")

    status, _, _ = call("POST", "/cases", directory, case_body, {"Idempotency-Key": "eval-team1-case-wrong-key"})
    record("cases", "directory key rejected", status == 401, f"{status}")

    status, _, body = call("GET", "/slots?dept=lost-and-found&date=2026-11-18", callbacks)
    slots = body if isinstance(body, list) else (body.get("results") or body.get("slots") if isinstance(body, dict) else None)
    slot_id = None
    if isinstance(slots, list) and slots:
        slot_id = slots[0].get("id") or slots[0].get("slot_id")
    record("callbacks", "list slots", status == 200 and bool(slot_id), f"{status} slot={slot_id} count={len(slots) if isinstance(slots, list) else None}")

    status, _, body = call(
        "POST",
        "/callbacks",
        callbacks,
        {"slot_id": slot_id, "phone": PHONE, "topic": "Eval lost-item follow up. Not a real rider."},
        {"Idempotency-Key": "eval-team1-cb-2135550199-b"},
    )
    cb_id = None
    duplicate = False
    if isinstance(body, dict):
        cb_id = body.get("id") or body.get("callback_id")
        existing = body.get("existing") if isinstance(body.get("existing"), dict) else None
        if status == 409 and isinstance(body.get("error"), dict):
            existing = body["error"].get("existing") if isinstance(body["error"].get("existing"), dict) else existing
            duplicate = body["error"].get("code") == "callback_already_scheduled"
            if existing:
                cb_id = existing.get("callback_id")
    record(
        "callbacks",
        "book or keep the one callback",
        (status in (200, 201) and bool(cb_id)) or (duplicate and bool(cb_id)),
        f"{status} {cb_id}",
    )

    if cb_id:
        status, _, body = call("GET", f"/callbacks/{cb_id}", callbacks)
        record("callbacks", "get callback", status == 200, f"{status}")

    status, _, body = call("GET", f"/callbacks?phone={PHONE}", callbacks)
    cbs = body if isinstance(body, list) else (body.get("results") if isinstance(body, dict) else None)
    record("callbacks", "list by phone", status == 200 and isinstance(cbs, list), f"{status} count={len(cbs) if isinstance(cbs, list) else None}")

    status, _, body = call(
        "POST",
        "/messages",
        messages,
        {"to": PHONE, "body": "Eval outbox only. Not a real customer text."},
        {"Idempotency-Key": "eval-team1-msg-2135550199-b"},
    )
    msg_id = body.get("message_id") or body.get("id") if isinstance(body, dict) else None
    record("messages", "outbox sms", status in (200, 201) and bool(msg_id), f"{status} {msg_id}")

    status, _, body = call("GET", f"/messages?to={PHONE}&limit=5", messages)
    msgs = body if isinstance(body, list) else (body.get("results") if isinstance(body, dict) else None)
    record("messages", "list outbox", status == 200 and isinstance(msgs, list), f"{status} count={len(msgs) if isinstance(msgs, list) else None}")

    status, _, body = call(
        "POST",
        "/emails",
        messages,
        {"to": "eval-test@example.com", "subject": "Eval only", "body": "Not a real customer email."},
        {"Idempotency-Key": "eval-team1-email-2135550199"},
    )
    email_id = body.get("email_id") or body.get("id") or body.get("message_id") if isinstance(body, dict) else None
    record("messages", "outbox email", status in (200, 201) and bool(email_id), f"{status} {email_id}")

    status, _, _ = call("POST", "/messages", cases, {"to": PHONE, "body": "should fail"}, {"Idempotency-Key": "eval-team1-msg-wrong-key"})
    record("messages", "cases key rejected", status == 401, f"{status}")

    status, _, body = call("GET", "/admin/stats", admin)
    record("admin", "stats", status == 200, f"{status}")
    status, _, _ = call("GET", "/admin/requests?limit=1", admin)
    record("admin", "request log", status == 200, f"{status}")
    status, _, _ = call("GET", "/admin/chaos", admin)
    record("admin", "chaos stays readable", status == 200, f"{status}")
    status, _, _ = call("POST", "/admin/reset", directory)
    record("admin", "directory key cannot reset", status in (401, 403), f"{status}")

    print()
    bots: dict[str, list[bool]] = {}
    for bot, _, ok, _ in results:
        bots.setdefault(bot, []).append(ok)
    for bot, flags in bots.items():
        print(f"{bot}: {sum(flags)}/{len(flags)}")
    passed = sum(1 for _, _, ok, _ in results if ok)
    print(f"total {passed}/{len(results)}")
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
