"""Neo worker for Ben Franklin Transit GTFS simulations."""

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


class Neo(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Neo, a warm call-center agent for Ben Franklin Transit. "
                "Ask one short question. No markdown, bullets, or emojis. "
                "Do not offer a call transfer. Do not offer a knowledge-base search. "
                "If the route or stop is missing, ask for it before you call a tool. "
                "Keep the route and stop the caller already gave. "
                "Phase 1 schedule answers must say scheduled. Never say the bus is minutes away "
                "unless a realtime tool returned a prediction. "
                "Speak the tool result. Do not invent a time, route, or stop."
            )
        )

    @function_tool
    async def next_scheduled_bus(self, ctx: RunContext, route: str, stop: str) -> str:
        """Next scheduled departures for a route at a stop."""
        if route.strip() in {"1", "Route 1"} and "knight" in stop.lower():
            return json.dumps({
                "scheduled": True,
                "next": "2:35 PM",
                "following": "3:05 PM",
                "stop": "Knight Street Transit Center",
                "route": "Route 1",
            })
        return json.dumps({"found": False, "message": "No scheduled trip was found."})

    @function_tool
    async def routes_at_stop(self, ctx: RunContext, stop: str) -> str:
        """Routes that serve a stop."""
        if "knight" in stop.lower():
            return json.dumps({"stop": "Knight Street Transit Center", "routes": ["Route 1", "Route 2", "Route 4"]})
        return json.dumps({"found": False})

    @function_tool
    async def route_serves_stop(self, ctx: RunContext, route: str, stop: str) -> str:
        """Whether a route serves a stop."""
        yes = route.strip() in {"1", "Route 1"} and "knight" in stop.lower()
        return json.dumps({"serves": yes, "route": "Route 1", "stop": "Knight Street Transit Center"})

    @function_tool
    async def service_day(self, ctx: RunContext, route: str, day: str) -> str:
        """Whether a route runs on a day."""
        runs = day.lower() not in {"saturday", "sunday"}
        return json.dumps({"route": "Route 1", "day": day, "runs": runs})

    @function_tool
    async def frequency(self, ctx: RunContext, route: str, stop: str) -> str:
        """Scheduled frequency."""
        return json.dumps({"route": "Route 1", "every_minutes": 30, "scheduled": True})

    @function_tool
    async def realtime_trip(self, ctx: RunContext, route: str, stop: str) -> str:
        """Live prediction. Only this tool may support a minutes-away statement."""
        return json.dumps({
            "scheduled": "2:35 PM",
            "predicted": "2:42 PM",
            "late_minutes": 7,
            "stop": "Knight Street Transit Center",
        })

    @function_tool
    async def service_alert(self, ctx: RunContext, route: str, stop: str) -> str:
        """Current detour or stop closure."""
        return json.dumps({
            "alert": "Route 1 is on a detour. Knight Street Transit Center is closed today.",
        })

    @function_tool
    async def missed_bus(self, ctx: RunContext, route: str, stop: str) -> str:
        """Whether the expected bus has already passed the stop."""
        return json.dumps({
            "passed": True,
            "message": "The Route 1 bus scheduled at 2:05 PM has already passed Knight Street Transit Center. The next is scheduled at 2:35 PM.",
        })


@server.rtc_session(agent_name="")
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    session = AgentSession(
        stt="assemblyai/universal-streaming",
        llm="openai/gpt-4.1-mini",
        tts="cartesia/sonic",
        max_tool_steps=6,
    )
    await session.start(agent=Neo(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
