"""Discovered agents in this codebase (FlexAgents prompts + API tools)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AgentSpec:
    id: str
    display_name: str
    domain: str
    prompt_path: str | None
    tools: tuple[str, ...]
    staging_hint: str | None = None
    implemented: bool = True


# FlexAgents staging dashboard agents (login required; IDs from user-provided URLs).
# Order matches eval/staging/agents.json — test step-by-step starting at Agent 1.
STAGING_AGENTS = {
    "6af703a01d07b8f78656fe4f": {
        "key": "answer_policy",
        "step": 1,
        "org": "6aa1562861347fe1a3087d63",
        "url": "https://dashboard-staging.flexagents.ai/organization/6aa1562861347fe1a3087d63/agent/6af703a01d07b8f78656fe4f/test",
    },
    "6af97679bdbf32a95ff46702": {
        "key": "find_department",
        "step": 2,
        "org": "6af96a0fbdbf32a95ff4651b",
        "url": "https://dashboard-staging.flexagents.ai/organization/6af96a0fbdbf32a95ff4651b/agent/6af97679bdbf32a95ff46702/test",
    },
    "6af96f45bdbf32a95ff46533": {
        "key": "log_case",
        "step": 3,
        "org": "6af9699dbdbf32a95ff46515",
        "url": "https://dashboard-staging.flexagents.ai/organization/6af9699dbdbf32a95ff46515/agent/6af96f45bdbf32a95ff46533/test",
    },
    "6af72aab4431b640e6041709": {
        "key": "book_callback",
        "step": 4,
        "org": "6af72a3c4431b640e6041707",
        "url": "https://dashboard-staging.flexagents.ai/organization/6af72a3c4431b640e6041707/agent/6af72aab4431b640e6041709/test",
    },
}


def discover_agents() -> list[AgentSpec]:
    """Return agents that exist as prompts/tools in this repo.

    Absent domains (sales, finance, growth, development) are listed as not implemented.
    """

    specs = [
        AgentSpec(
            id="general_inquiry",
            display_name="Main General Inquiry",
            domain="support/orchestration",
            prompt_path="prompts/00_main_general_inquiry.md",
            tools=(
                "answer_policy",
                "find_department",
                "log_case",
                "book_callback",
            ),
            staging_hint="dashboard-staging FlexAgents main GI",
        ),
        AgentSpec(
            id="answer_policy",
            display_name="Answer Policy (KB)",
            domain="support",
            prompt_path="prompts/01_answer_policy.md",
            tools=("knowledge_base",),
            staging_hint=STAGING_AGENTS["6af703a01d07b8f78656fe4f"]["url"],
        ),
        AgentSpec(
            id="find_department",
            display_name="Find Department",
            domain="operations",
            prompt_path="prompts/02_find_department.md",
            tools=("list_departments", "get_department"),
            staging_hint=STAGING_AGENTS["6af97679bdbf32a95ff46702"]["url"],
        ),
        AgentSpec(
            id="log_case",
            display_name="Log Case",
            domain="support",
            prompt_path="prompts/03_log_case.md",
            tools=(
                "create_case",
                "get_case",
                "list_cases_by_phone",
                "send_message",
                "list_messages",
            ),
            staging_hint=STAGING_AGENTS["6af96f45bdbf32a95ff46533"]["url"],
        ),
        AgentSpec(
            id="book_callback",
            display_name="Book Callback",
            domain="operations",
            prompt_path="prompts/04_book_callback.md",
            tools=(
                "list_slots",
                "create_callback",
                "get_callback",
                "cancel_callback",
                "send_message",
                "list_messages",
            ),
            staging_hint=STAGING_AGENTS["6af72aab4431b640e6041709"]["url"],
        ),
        AgentSpec(
            id="sales",
            display_name="Sales Agent",
            domain="sales",
            prompt_path=None,
            tools=(),
            implemented=False,
        ),
        AgentSpec(
            id="finance",
            display_name="Finance Agent",
            domain="finance",
            prompt_path=None,
            tools=(),
            implemented=False,
        ),
        AgentSpec(
            id="growth",
            display_name="Growth Agent",
            domain="growth",
            prompt_path=None,
            tools=(),
            implemented=False,
        ),
        AgentSpec(
            id="development",
            display_name="Development Agent",
            domain="development",
            prompt_path=None,
            tools=(),
            implemented=False,
        ),
    ]
    return specs


def implemented_agents() -> list[AgentSpec]:
    return [a for a in discover_agents() if a.implemented]


def prompt_exists(spec: AgentSpec) -> bool:
    if not spec.prompt_path:
        return False
    return (ROOT / spec.prompt_path).is_file()
