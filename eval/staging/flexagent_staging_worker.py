"""Jenny worker for separate LiveKit simulations.

Reads API keys from .env and does not print them.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://team1-inquiry-api.vercel.app"


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)
        if key == "TEAM1_API_BASE" and value:
            global BASE
            BASE = value


load_env()
server = AgentServer()


def api(method: str, path: str, key_name: str, body: dict | None = None, headers: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    req_headers = {"Accept": "application/json", "X-API-Key": os.environ[key_name]}
    if body is not None:
        req_headers["Content-Type"] = "application/json"
    if headers:
        req_headers.update(headers)
    req = Request(BASE + path, data=data, headers=req_headers, method=method)
    try:
        with urlopen(req, timeout=25) as resp:
            raw = resp.read().decode()
            return resp.status, json.loads(raw) if raw else {}
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:400]}
        return exc.code, parsed


def api_now() -> datetime:
    _, body = api("GET", "/health", "DIRECTORY_API_KEY")
    return datetime.fromisoformat(body["now"])


class AccessJenny(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Jenny, Access LA phone support. Use tools for every fact. "
                "Never invent a fare, phone number, case number, or callback id. "
                "Fare or policy questions: call search_knowledge only. If it has no dollar amount, "
                "say the one-way fare is not in your materials and name the document title it searched. "
                "Lost item routing: find_departments then get_department. Say the name, phone, and open or closed. "
                "Filing a report: after the caller says yes, create_case then send_text. "
                "Read the case number back. "
                "Looking up cases: find_cases_by_phone and read the case numbers. "
                "Booking a callback: list_callback_slots, tell them one morning slot, and after they say yes "
                "call book_callback_slot then send_text. Read the CB number. "
                "Cancelling: find_callbacks_by_phone, then after yes call cancel_callback. "
                "Two issues: finish one case and its text before starting the second. "
                "Do not mix the two case numbers. "
                "A complaint about who to call: find_departments with need complaint, then get_department. "
                "Say that department name, its phone, and whether it is open or closed. Do not file a case. "
                "If they ask to book, change, or cancel a ride, or for a live arrival time, refuse. "
                "Do not invent a time and do not call create_case. "
                "If they say no, stop, or don't file it, do not call create_case or send_text. "
                "Say that nothing was filed."
            )
        )

    @function_tool
    async def search_knowledge(self, ctx: RunContext, query: str) -> str:
        """Search local Access LA materials. Returns a document title and excerpt, or not found."""
        docs = [
            ROOT / "app/seed/departments.json",
            ROOT / "prompts/01_answer_policy.md",
            ROOT / "prompts/00_main_general_inquiry.md",
        ]
        hits = []
        needle = query.lower()
        for path in docs:
            if not path.is_file():
                continue
            text = path.read_text(encoding="utf-8")
            if "fare" in needle or "one-way" in needle or "one way" in needle:
                if "fare" not in text.lower():
                    continue
            elif needle.split()[0] not in text.lower():
                continue
            hits.append({"document": path.name, "excerpt": text[:700]})
        if not hits:
            return json.dumps({"found": False, "document": "2026 Rider's Guide notes", "excerpt": ""})
        return json.dumps({"found": True, "passages": hits[:2]})

    @function_tool
    async def find_departments(self, ctx: RunContext, need: str) -> str:
        """Find departments for a need such as lost or complaint."""
        _, body = api("GET", "/departments?need=" + quote(need) + "&limit=5", "DIRECTORY_API_KEY")
        results = body.get("results") if isinstance(body, dict) else []
        brief = [
            {"id": item.get("id"), "name": item.get("name"), "phone": item.get("phone"), "open_now": item.get("open_now")}
            for item in results or []
        ]
        return json.dumps(brief)

    @function_tool
    async def get_department(self, ctx: RunContext, department_id: str) -> str:
        """Get one department phone, open_now, and today's hours."""
        _, body = api("GET", "/departments/" + quote(department_id), "DIRECTORY_API_KEY")
        keep = {key: body.get(key) for key in ("id", "name", "phone", "open_now", "hours_today_text")}
        return json.dumps(keep)

    @function_tool
    async def create_case(self, ctx: RunContext, category: str, description: str, phone: str, department_id: str) -> str:
        """Create a lost_item or complaint case. category is lost_item or complaint."""
        now = api_now()
        incident = (now - timedelta(days=1)).replace(hour=14, minute=0, second=0, microsecond=0)
        status, body = api(
            "POST",
            "/cases",
            "CASES_API_KEY",
            {
                "category": category,
                "incident_at": incident.isoformat(),
                "description": description,
                "callback_phone": phone,
                "department_id": department_id,
            },
            {"Idempotency-Key": "jenny-sim-" + uuid.uuid4().hex[:12]},
        )
        if not isinstance(body, dict):
            return json.dumps({"status": status})
        return json.dumps({"http_status": status, "case_number": body.get("case_number"), "error": body.get("error")})

    @function_tool
    async def send_text(self, ctx: RunContext, to: str, body: str) -> str:
        """Send a sandbox text. body must include the case or callback number."""
        status, payload = api(
            "POST",
            "/messages",
            "MESSAGES_API_KEY",
            {"to": to, "body": body},
            {"Idempotency-Key": "jenny-sms-" + uuid.uuid4().hex[:12]},
        )
        message_id = payload.get("message_id") if isinstance(payload, dict) else None
        return json.dumps({"http_status": status, "message_id": message_id, "error": payload.get("error") if isinstance(payload, dict) else None})

    @function_tool
    async def find_cases_by_phone(self, ctx: RunContext, phone: str) -> str:
        """List cases already filed for a phone number."""
        _, body = api("GET", "/cases?phone=" + quote(phone) + "&limit=10", "CASES_API_KEY")
        results = body.get("results") if isinstance(body, dict) else []
        brief = [
            {"case_number": item.get("case_number"), "category": item.get("category")}
            for item in results or []
        ]
        return json.dumps(brief)

    @function_tool
    async def list_callback_slots(self, ctx: RunContext, department_id: str) -> str:
        """List tomorrow morning callback slots for a department."""
        tomorrow = (api_now() + timedelta(days=1)).date().isoformat()
        _, body = api(
            "GET",
            f"/slots?dept={quote(department_id)}&date={tomorrow}",
            "CALLBACKS_API_KEY",
        )
        results = body.get("results") if isinstance(body, dict) else []
        morning = [item for item in results or [] if "AM" in str(item.get("window_text", ""))]
        brief = [
            {"slot_id": item.get("slot_id"), "window_text": item.get("window_text")}
            for item in morning[:4]
        ]
        return json.dumps({"date": tomorrow, "slots": brief})

    @function_tool
    async def book_callback_slot(self, ctx: RunContext, slot_id: str, phone: str, topic: str) -> str:
        """Book a callback. If one already exists, return that callback id."""
        status, body = api(
            "POST",
            "/callbacks",
            "CALLBACKS_API_KEY",
            {"slot_id": slot_id, "phone": phone, "topic": topic},
            {"Idempotency-Key": "jenny-cb-" + uuid.uuid4().hex[:12]},
        )
        if not isinstance(body, dict):
            return json.dumps({"http_status": status})
        existing = None
        error = body.get("error") if isinstance(body.get("error"), dict) else None
        if error and isinstance(error.get("existing"), dict):
            existing = error["existing"].get("callback_id")
        return json.dumps(
            {
                "http_status": status,
                "callback_id": body.get("callback_id") or body.get("id") or existing,
                "error_code": None if not error else error.get("code"),
            }
        )

    @function_tool
    async def find_callbacks_by_phone(self, ctx: RunContext, phone: str) -> str:
        """List callbacks for a phone number."""
        _, body = api("GET", "/callbacks?phone=" + quote(phone), "CALLBACKS_API_KEY")
        results = body.get("results") if isinstance(body, dict) else []
        brief = [
            {
                "callback_id": item.get("callback_id") or item.get("id"),
                "status": item.get("status"),
                "window_text": item.get("window_text"),
            }
            for item in results or []
            if item.get("status") != "cancelled"
        ]
        return json.dumps(brief)

    @function_tool
    async def cancel_callback(self, ctx: RunContext, callback_id: str) -> str:
        """Cancel one callback after the caller says yes."""
        status, body = api(
            "DELETE",
            f"/callbacks/{quote(callback_id)}?sms_body={quote('Your callback is cancelled.')}",
            "CALLBACKS_API_KEY",
            headers={"Idempotency-Key": "jenny-cancel-" + uuid.uuid4().hex[:12]},
        )
        cancelled = body.get("status") if isinstance(body, dict) else None
        return json.dumps({"http_status": status, "status": cancelled, "callback_id": callback_id})


@server.rtc_session(agent_name="")
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    session = AgentSession(llm="openai/gpt-4.1-mini", max_tool_steps=8)
    await session.start(agent=AccessJenny(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
