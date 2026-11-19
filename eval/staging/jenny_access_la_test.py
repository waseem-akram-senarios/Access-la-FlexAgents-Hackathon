"""Run Access LA Jenny's seven caller tests against the Team 1 API.

Reads keys from .env and does not print them. Does not reset the database.
The knowledge-base fare question is recorded, not answered, because this API
has no knowledge base.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[2]
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
    base = os.environ.get("TEAM1_API_BASE", "https://team1-inquiry-api.vercel.app")
    req = Request(base + path, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else None
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else None
        except json.JSONDecodeError:
            parsed = {"raw": raw[:300]}
        return exc.code, parsed


def rows(body, key: str) -> list:
    if isinstance(body, list):
        return body
    if isinstance(body, dict) and isinstance(body.get(key), list):
        return body[key]
    return []


def main() -> None:
    load_env()
    directory = os.environ["DIRECTORY_API_KEY"]
    cases_key = os.environ["CASES_API_KEY"]
    callbacks_key = os.environ["CALLBACKS_API_KEY"]
    messages_key = os.environ["MESSAGES_API_KEY"]
    results: list[tuple[str, bool, str]] = []

    def record(case_id: str, ok: bool, detail: str) -> None:
        results.append((case_id, ok, detail))
        print(("PASS" if ok else "FAIL"), case_id, detail)

    status, health = call("GET", "/health", None)
    now_text = health.get("now") if isinstance(health, dict) else None
    record("setup", status == 200 and bool(now_text), f"api time {now_text}")
    now = datetime.fromisoformat(now_text)
    yesterday = (now - timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
    incident_at = yesterday.isoformat()

    record(
        "JENNY-1",
        False,
        "not run here: the Team 1 API has no knowledge base, so it cannot name the fare document",
    )

    status, body = call("GET", "/departments?need=lost&limit=5", directory)
    found = next((d for d in rows(body, "results") if d.get("id") == "lost-and-found"), None)
    if found:
        status, detail = call("GET", "/departments/lost-and-found", directory)
        if isinstance(detail, dict) and detail.get("id"):
            found = detail
    record(
        "JENNY-2",
        status == 200 and bool(found) and "lost" in str(found.get("name", "")).lower() and bool(found.get("phone")),
        f"{None if not found else found.get('name')} phone={None if not found else found.get('phone')} open_now={None if not found else found.get('open_now')}",
    )

    # Clear this test number's old callback so JENNY-5 can book a new one.
    status, existing = call(f"GET", f"/callbacks?phone={PHONE}", callbacks_key)
    for item in rows(existing, "results"):
        cb = item.get("callback_id") or item.get("id")
        if cb and item.get("status") != "cancelled":
            call(
                "DELETE",
                f"/callbacks/{cb}?sms_body={quote('Eval setup cancel. Not a real rider.')}",
                callbacks_key,
                headers={"Idempotency-Key": f"jenny-setup-cancel-{cb}"},
            )

    status, body = call(
        "POST",
        "/cases",
        cases_key,
        {
            "category": "lost_item",
            "incident_at": incident_at,
            "description": "Backpack left on the 7 bus. Jenny test JENNY-3. Not a real rider.",
            "callback_phone": PHONE,
            "department_id": "lost-and-found",
        },
        {"Idempotency-Key": "jenny-3-lost-backpack"},
    )
    case_number = body.get("case_number") if isinstance(body, dict) else None
    status_m, msg = call(
        "POST",
        "/messages",
        messages_key,
        {"to": PHONE, "body": f"Lost item report {case_number} is filed. We will call 213-555-0199."},
        {"Idempotency-Key": f"jenny-3-sms-{case_number}"},
    )
    msg_id = msg.get("message_id") if isinstance(msg, dict) else None
    record(
        "JENNY-3",
        status in (200, 201) and str(case_number).startswith("AC-") and status_m in (200, 201) and bool(msg_id),
        f"case={case_number} text={msg_id}",
    )

    status, body = call("GET", f"/cases?phone={PHONE}&limit=20", cases_key)
    numbers = [item.get("case_number") for item in rows(body, "results")]
    record("JENNY-4", status == 200 and case_number in numbers, f"found {case_number} among {len(numbers)} cases")

    tomorrow = (now + timedelta(days=1)).date().isoformat()
    status, body = call(f"GET", f"/slots?dept=lost-and-found&date={tomorrow}", callbacks_key)
    morning = [
        slot for slot in rows(body, "results")
        if "AM" in str(slot.get("window_text", ""))
    ]
    slot = morning[0] if morning else None
    slot_id = slot.get("slot_id") if slot else None
    status_b, booked = call(
        "POST",
        "/callbacks",
        callbacks_key,
        {"slot_id": slot_id, "phone": PHONE, "topic": "Jenny test JENNY-5 lost and found callback."},
        {"Idempotency-Key": f"jenny-5-{slot_id}"},
    )
    cb_id = booked.get("callback_id") or booked.get("id") if isinstance(booked, dict) else None
    status_m, msg = call(
        "POST",
        "/messages",
        messages_key,
        {"to": PHONE, "body": f"Callback {cb_id} is booked for {None if not slot else slot.get('window_text')}."},
        {"Idempotency-Key": f"jenny-5-sms-{cb_id}"},
    )
    msg_id = msg.get("message_id") if isinstance(msg, dict) else None
    record(
        "JENNY-5",
        bool(slot_id) and status_b in (200, 201) and str(cb_id).startswith("CB-") and bool(msg_id),
        f"slot={None if not slot else slot.get('window_text')} callback={cb_id} text={msg_id}",
    )

    status, body = call("GET", f"/callbacks?phone={PHONE}", callbacks_key)
    found_cb = next(
        (
            item for item in rows(body, "results")
            if (item.get("callback_id") or item.get("id")) == cb_id and item.get("status") != "cancelled"
        ),
        None,
    )
    status_c, cancelled = call(
        "DELETE",
        f"/callbacks/{cb_id}?sms_body={quote('Your lost and found callback is cancelled.')}",
        callbacks_key,
        headers={"Idempotency-Key": f"jenny-6-cancel-{cb_id}"},
    )
    cancelled_status = cancelled.get("status") if isinstance(cancelled, dict) else None
    record(
        "JENNY-6",
        bool(found_cb) and status_c in (200, 204) and cancelled_status in {None, "cancelled"},
        f"found={bool(found_cb)} cancel={status_c} status={cancelled_status}",
    )

    jobs = [
        ("lost_item", "Bag left on the 7 bus. Jenny test JENNY-7 job 1. Not a real rider.", "jenny-7-lost"),
        ("complaint", "The driver was rude. Jenny test JENNY-7 job 2. Not a real rider.", "jenny-7-complaint"),
    ]
    made: list[tuple[str, str]] = []
    for category, description, key in jobs:
        status, body = call(
            "POST",
            "/cases",
            cases_key,
            {
                "category": category,
                "incident_at": incident_at,
                "description": description,
                "callback_phone": PHONE,
                "department_id": "lost-and-found" if category == "lost_item" else "customer-service",
            },
            {"Idempotency-Key": key},
        )
        number = body.get("case_number") if isinstance(body, dict) else None
        status_m, msg = call(
            "POST",
            "/messages",
            messages_key,
            {"to": PHONE, "body": f"{category} report {number} only. The other issue is separate."},
            {"Idempotency-Key": f"{key}-sms"},
        )
        made.append((str(number), str(msg.get("message_id") if isinstance(msg, dict) else None)))
    separate = len({num for num, _ in made}) == 2 and all(num.startswith("AC-") for num, _ in made)
    record("JENNY-7", separate and all(msg != "None" for _, msg in made), f"cases={made}")

    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} passed")
    raise SystemExit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
