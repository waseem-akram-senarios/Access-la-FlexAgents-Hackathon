"""Registers with LiveKit as flexagent.staging so staging simulations can join.

Uses the Team 1 directory API. Does not print API keys.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

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


def directory_get(path: str) -> dict:
    base = os.environ.get("TEAM1_API_BASE", "https://team1-inquiry-api.vercel.app")
    req = Request(
        base + path,
        headers={
            "Accept": "application/json",
            "X-API-Key": os.environ["DIRECTORY_API_KEY"],
        },
    )
    with urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


class AccessJenny(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are Jenny, the Access LA phone agent. "
                "For a lost bag or lost item, call find_departments with need lost, "
                "then get_department for lost-and-found. "
                "Tell the caller the department name, the phone number from the tool, "
                "and whether it is open or closed from open_now. "
                "Never invent a phone number. Do not file a case unless they ask. "
                "Keep the reply to two short spoken sentences."
            )
        )

    @function_tool
    async def find_departments(self, ctx: RunContext, need: str) -> str:
        """Find Access LA departments for a caller need such as lost or complaint."""
        body = directory_get("/departments?need=" + quote(need) + "&limit=5")
        results = body.get("results") if isinstance(body, dict) else []
        brief = [
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "phone": item.get("phone"),
                "open_now": item.get("open_now"),
            }
            for item in results or []
        ]
        return json.dumps(brief)

    @function_tool
    async def get_department(self, ctx: RunContext, department_id: str) -> str:
        """Get one department's phone and whether it is open now."""
        body = directory_get("/departments/" + quote(department_id))
        keep = {
            "id": body.get("id"),
            "name": body.get("name"),
            "phone": body.get("phone"),
            "open_now": body.get("open_now"),
            "hours_today_text": body.get("hours_today_text"),
        }
        return json.dumps(keep)


@server.rtc_session(agent_name="")
async def entrypoint(ctx: JobContext) -> None:
    await ctx.connect()
    session = AgentSession(llm="openai/gpt-4.1-mini")
    await session.start(agent=AccessJenny(), room=ctx.room)


if __name__ == "__main__":
    cli.run_app(server)
