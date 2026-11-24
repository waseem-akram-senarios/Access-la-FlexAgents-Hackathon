"""Barwood and Regency worker for LiveKit simulations.

Tools enforce the booking rules. Scenario userdata selects the rider fixture.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, RunContext, cli, function_tool

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
STATE: dict = {"fixture": "named", "trips": []}


def fixture() -> str:
    return str(STATE.get("fixture") or "named")


class Amelia(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Amelia at Barwood and Regency. The greeting was already spoken. "
                "Do not introduce yourself. Before any trip question, call rider_lookup. "
                "Never invent a fare, time, address, or confirmation number. Speak only what tools return. "
                "Ask one short question at a time. "
                "Cash, credit card, and Call and Ride are allowed. Call and Ride takes the last 6 digits only. "
                "Any other payment is unsupported: say so and offer a transfer. Do not book it. "
                "Pickup and drop-off cannot be the same. If book_trip or fare_quote says same_place, "
                "say the drop-off cannot be the same as the pickup. "
                "If the rider already has an upcoming trip, read that trip and do not start a new booking. "
                "Offer a transfer or ask if they want something else. "
                "If the profile has no name, ask for the name before booking. "
                "After an outbound confirmation, ask once: Do you need a return trip? "
                "If they say now or a return time that is too early, speak the earliest_pickup from the tool. "
                "Changing the pickup address or drop-off is not allowed. Say they must cancel and rebook. "
                "Pickup time can be changed with change_pickup_time. "
                "A will-call trip has a day and no clock time. Activate it only when they say they are ready. "
                "For where is my ride, call trip_status and speak its message exactly."
            )
        )

    @function_tool
    async def rider_lookup(self, ctx: RunContext) -> str:
        """Look up the caller by the incoming phone number before any trip question."""
        mode = fixture()
        if mode == "blank_name":
            return json.dumps({"phone": "3015550100", "name": "", "trips": []})
        if mode == "has_trip":
            trip = {
                "confirmation": "213701700",
                "pickup": "Boyds, MD",
                "dropoff": "BWI Airport",
                "when": "today at 2:00 PM",
                "status": "booked",
            }
            return json.dumps({"phone": "3015550101", "name": "Jamie", "trips": [trip]})
        if mode == "status_unassigned":
            trip = {
                "confirmation": "213701701",
                "pickup": "Boyds, MD",
                "dropoff": "BWI Airport",
                "when": "today, more than 15 minutes away",
                "status": "unassigned",
            }
            return json.dumps({"phone": "3015550102", "name": "Jamie", "trips": [trip]})
        if mode == "status_cancelled":
            trip = {
                "confirmation": "213701702",
                "pickup": "Boyds, MD",
                "dropoff": "BWI Airport",
                "when": "today at 4:00 PM",
                "status": "cancelled",
            }
            return json.dumps({"phone": "3015550103", "name": "Jamie", "trips": [trip]})
        return json.dumps({"phone": "3015550104", "name": "Jamie", "trips": STATE.get("trips") or []})

    @function_tool
    async def fare_quote(self, ctx: RunContext, pickup: str, dropoff: str, passengers: int, wheelchair: bool, payment: str) -> str:
        """Quote a fare. Rejects the same place, too many passengers, and unsupported payment."""
        if pickup.strip().lower() == dropoff.strip().lower():
            return json.dumps({"ok": False, "code": "same_place", "message": "The drop-off cannot be the same as the pickup."})
        pay = payment.lower()
        if pay not in {"cash", "credit", "credit card", "call and ride"}:
            return json.dumps({"ok": False, "code": "unsupported_payment", "message": "That payment method is not supported. I can transfer you to a dispatcher."})
        if wheelchair and passengers > 3:
            return json.dumps({"ok": False, "code": "wheelchair_limit", "message": "A wheelchair trip can have at most 3 passengers."})
        if passengers > 5:
            return json.dumps({"ok": False, "code": "passenger_limit", "message": "A trip can have at most 5 passengers."})
        return json.dumps({"ok": True, "fare": "120.50", "currency": "USD", "travel_minutes": 40, "pickup": pickup, "dropoff": dropoff})

    @function_tool
    async def book_trip(self, ctx: RunContext, pickup: str, dropoff: str, when: str, passengers: int, wheelchair: bool, payment: str, will_call: bool = False) -> str:
        """Book one trip and return a confirmation number. Will-call stores the day only."""
        quote = json.loads(await self.fare_quote(ctx, pickup, dropoff, passengers, wheelchair, payment))
        if not quote.get("ok"):
            return json.dumps(quote)
        number = "213701786" if not will_call else "213701790"
        trip = {"confirmation": number, "pickup": pickup, "dropoff": dropoff, "when": "will-call" if will_call else when, "fare": quote["fare"], "status": "booked"}
        STATE.setdefault("trips", []).append(trip)
        return json.dumps({"ok": True, **trip, "travel_minutes": quote["travel_minutes"]})

    @function_tool
    async def earliest_return(self, ctx: RunContext, outbound_pickup: str, travel_minutes: int) -> str:
        """Earliest return is outbound pickup plus travel minutes plus 10."""
        earliest = f"{outbound_pickup} plus {travel_minutes} minutes plus 10 minutes"
        return json.dumps({"ok": True, "earliest_pickup": earliest, "message": f"The earliest return pickup is {earliest}."})

    @function_tool
    async def change_pickup_time(self, ctx: RunContext, confirmation: str, new_time: str) -> str:
        """Change only the pickup time of an existing trip."""
        return json.dumps({"ok": True, "confirmation": confirmation, "pickup_time": new_time, "message": f"Pickup time for {confirmation} is now {new_time}."})

    @function_tool
    async def change_address(self, ctx: RunContext, confirmation: str) -> str:
        """Address changes are blocked. The caller must cancel and rebook."""
        return json.dumps({"ok": False, "code": "address_change_blocked", "message": "I can't change the pickup or drop-off address. I can cancel this trip and book a new one."})

    @function_tool
    async def cancel_trip(self, ctx: RunContext, confirmation: str) -> str:
        """Cancel an existing trip after the caller confirms."""
        return json.dumps({"ok": True, "confirmation": confirmation, "status": "cancelled", "message": f"Trip {confirmation} is cancelled."})

    @function_tool
    async def activate_will_call(self, ctx: RunContext, confirmation: str) -> str:
        """Activate a will-call trip when the rider says they are ready."""
        return json.dumps({"ok": True, "confirmation": confirmation, "status": "activated", "message": f"Will-call trip {confirmation} is activated."})

    @function_tool
    async def trip_status(self, ctx: RunContext) -> str:
        """Status line for the caller's current trip."""
        mode = fixture()
        if mode == "status_cancelled":
            return json.dumps({"message": "Your trip has been cancelled."})
        if mode == "status_unassigned":
            return json.dumps({"message": "Dispatch Service is finding a nearby vehicle for your trip."})
        return json.dumps({"message": "I don't have a trip status for this call."})


@server.rtc_session(agent_name="")
async def entrypoint(ctx: JobContext) -> None:
    global STATE
    sim = ctx.simulation_context()
    raw = {}
    if sim is not None:
        loaded = sim.userdata() if callable(sim.userdata) else sim.userdata
        raw = loaded if isinstance(loaded, dict) else {}
    STATE = {"fixture": raw.get("fixture", "named"), "trips": []}
    await ctx.connect()
    session = AgentSession(
        stt="assemblyai/universal-streaming:en",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic",
        max_tool_steps=8,
    )
    await session.start(agent=Amelia(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
