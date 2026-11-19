"""Ana worker for LiveKit simulations. Tools enforce her booking rules."""

from __future__ import annotations

import json
import os
from pathlib import Path

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli, function_tool, RunContext

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)


load_env()
server = AgentServer()
STATE: dict = {"fixture": "no_account", "lookups": 0}


def fixture() -> str:
    return str(STATE.get("fixture") or "no_account")


class Ana(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Ana, a patient transportation assistant. Ask one short question. "
                "Do not repeat a greeting. Never invent a phone number. "
                "Call lookup_account once. If they say you already have the number, use it. "
                "Never look up the same number twice. "
                "If no profile is found, say that, then ask whether they use DART or ACCESS. "
                "Do not ask for a place until they answer. "
                "If they say DART, do not ask for a rider ID. Continue the booking if they asked for a ride. "
                "If they say ACCESS and there is no account, ask for the rider ID. ACCESS is program 17. "
                "Check eligibility with that rider ID and program 17. Then ask booking or transfer. "
                "If they have no rider ID, ask if they want a transfer and stop. "
                "If ProgramID is above 0, ask for the rider ID even when the profile already has one. "
                "A name does not replace a rider ID. If they have no rider ID, say this service needs one and stop. "
                "If ProgramID is -1, do not ask for a rider ID. "
                "Never send program 17 unless the profile says 17 or they chose ACCESS with no account. "
                "Keep -1 as -1. "
                "If they ask about a booked trip, status, ETA, confirmation, pickup, or drop-off, "
                "call lookup_rides once the client id is known. Do not ask which trip. "
                "For a new ride, ask pickup, then drop-off. Read each match and wait for yes. "
                "If several places match, say the choices once and do not ask again. "
                "Then ask for a pickup time or an arrive-by time. Never use the current time as the pickup. "
                "Arrive-by: call dispatch_pickup, then check_service_hours. A refusal stops the booking. "
                "Then passengers and mobility, fare_quote, payment only if the fare is above zero, "
                "notes once, ask about a return, then book_ride. Do not read the trip back. "
                "Do not ask for a yes yourself. Do not ask for a home address. "
                "Call each step once. Do not book again after it succeeds. "
                "To cancel, call cancel_ride with the confirmation they named. "
                "Do not look up rides yourself for a cancel. Say which rides were cancelled."
            )
        )

    @function_tool
    async def lookup_account(self, ctx: RunContext, phone: str) -> str:
        """Look up an account once by phone."""
        STATE["lookups"] = int(STATE.get("lookups") or 0) + 1
        if STATE["lookups"] > 1:
            return json.dumps({"error": "already_looked_up", "message": "This number was already looked up."})
        mode = fixture()
        if mode in {"no_account", "access_no_account"}:
            return json.dumps({"found": False, "message": "No profile was found for that number."})
        if mode == "several_people":
            return json.dumps({"found": True, "several": True, "message": "Several people match. Ask for their name. Do not suggest one."})
        if mode == "program_minus_one":
            return json.dumps({"found": True, "client_id": "C-100", "name": "Jamie", "program_id": -1, "rider_id": None})
        if mode == "program_positive":
            return json.dumps({"found": True, "client_id": "C-200", "name": "Jamie", "program_id": 5, "rider_id": "R-55"})
        if mode == "has_ride":
            return json.dumps({"found": True, "client_id": "C-300", "name": "Jamie", "program_id": -1})
        return json.dumps({"found": True, "client_id": "C-400", "name": "Jamie", "program_id": -1})

    @function_tool
    async def check_eligibility(self, ctx: RunContext, rider_id: str, program_id: int) -> str:
        """Check eligibility. Program -1 must stay -1. Program 17 only for ACCESS with no account."""
        if program_id == 17 and fixture() != "access_no_account":
            return json.dumps({"ok": False, "code": "wrong_program", "message": "Program 17 was not allowed for this profile."})
        if fixture() == "program_positive" and program_id != 5:
            return json.dumps({"ok": False, "code": "wrong_program", "message": "Use the profile ProgramID."})
        if not rider_id:
            return json.dumps({"ok": False, "code": "rider_id_required", "message": "This service needs a rider ID."})
        return json.dumps({"ok": True, "rider_id": rider_id, "program_id": program_id})

    @function_tool
    async def lookup_rides(self, ctx: RunContext, client_id: str) -> str:
        """Existing rides. Do not ask the caller which trip."""
        return json.dumps({
            "confirmation": "ANA-1001",
            "time": "2:00 PM",
            "pickup": "Library",
            "dropoff": "Clinic",
            "status": "booked",
        })

    @function_tool
    async def match_place(self, ctx: RunContext, place: str) -> str:
        """Match a pickup or drop-off. Several matches are returned once."""
        if fixture() == "multi_place" and "main" in place.lower():
            return json.dumps({"matches": ["Main Street Clinic", "Main Street Library"]})
        return json.dumps({"matches": [place]})

    @function_tool
    async def dispatch_pickup(self, ctx: RunContext, arrive_by: str) -> str:
        """Turn an arrive-by time into a pickup time. Never uses the current time."""
        return json.dumps({"pickup_time": "1:10 PM", "arrive_by": arrive_by})

    @function_tool
    async def check_service_hours(self, ctx: RunContext, pickup_time: str) -> str:
        """A refusal stops the booking."""
        if fixture() == "hours_refused" or pickup_time.strip().lower() in {"now", "right now"}:
            return json.dumps({"ok": False, "message": "Dispatch cannot serve that pickup. Stop the booking."})
        return json.dumps({"ok": True, "pickup_time": pickup_time})

    @function_tool
    async def fare_quote(self, ctx: RunContext, passengers: int, mobility: str) -> str:
        """Quote the fare. Payment is asked only when the fare is above zero."""
        fare = 0 if fixture() != "fare_positive" else 12
        return json.dumps({"fare": fare, "ask_payment": fare > 0})

    @function_tool
    async def book_ride(self, ctx: RunContext, pickup: str, dropoff: str, pickup_time: str, passengers: int, mobility: str, pickup_notes: str, dropoff_notes: str, need_return: bool) -> str:
        """Book once. The booking step asks for the yes. Do not ask for it yourself."""
        if pickup_time.strip().lower() in {"now", "right now"}:
            return json.dumps({"ok": False, "message": "Do not use the current time as the pickup."})
        return json.dumps({
            "ok": True,
            "confirmation": "ANA-2002",
            "pickup": pickup,
            "dropoff": dropoff,
            "pickup_time": pickup_time,
            "pickup_notes": pickup_notes,
            "dropoff_notes": dropoff_notes,
            "need_return": need_return,
            "asked_yes": True,
        })

    @function_tool
    async def cancel_ride(self, ctx: RunContext, confirmation: str) -> str:
        """Cancel by the confirmation the caller named. This step asks for the yes."""
        return json.dumps({
            "ok": True,
            "cancelled": [confirmation],
            "still_booked": [],
            "message": f"{confirmation} was cancelled. No other ride was cancelled.",
        })


@server.rtc_session(agent_name="")
async def entrypoint(ctx: JobContext) -> None:
    global STATE
    sim = ctx.simulation_context()
    raw = {}
    if sim is not None:
        loaded = sim.userdata() if callable(sim.userdata) else sim.userdata
        raw = loaded if isinstance(loaded, dict) else {}
    STATE = {"fixture": raw.get("fixture", "no_account"), "lookups": 0}
    await ctx.connect()
    session = AgentSession(llm="openai/gpt-4.1-mini", max_tool_steps=10)
    await session.start(agent=Ana(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
