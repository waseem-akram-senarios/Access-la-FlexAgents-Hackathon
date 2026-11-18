"""Shared models for the universal evaluation engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Literal


class TestLevel(IntEnum):
    L1_UNIT_CONTRACT = 1
    L2_INTEGRATION_TOOL = 2
    L3_REASONING_RAG_TOOL_CHOICE = 3
    L4_MULTI_AGENT = 4
    L5_END_TO_END = 5
    L6_RELIABILITY_PERF = 6
    L7_BUSINESS_OUTCOME = 7


AgentType = Literal[
    "general_inquiry",
    "answer_policy",
    "find_department",
    "log_case",
    "book_callback",
    "orchestration",
    "support",
    "operations",
    "risk",
    "quality",
]


@dataclass
class AssertionResult:
    name: str
    passed: bool
    detail: str = ""
    category: str = "deterministic"


@dataclass
class TraceStep:
    step: str
    tool: str | None = None
    request: dict[str, Any] = field(default_factory=dict)
    response: dict[str, Any] = field(default_factory=dict)
    status_code: int | None = None
    latency_ms: float | None = None
    forbidden: bool = False


@dataclass
class ScenarioCase:
    id: str
    title: str
    level: TestLevel
    agent: AgentType
    category: str
    input: dict[str, Any]
    expected: dict[str, Any] = field(default_factory=dict)
    required_tools: list[str] = field(default_factory=list)
    forbidden_tools: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    repeats: int = 1
    human_review: bool = False
    hard_fail_on: list[str] = field(default_factory=list)


# Back-compat alias (pytest must not collect this as a test class).
TestCase = ScenarioCase
TestCase.__test__ = False  # type: ignore[attr-defined]
TestLevel.__test__ = False  # type: ignore[attr-defined]


@dataclass
class ScenarioResult:
    case: ScenarioCase
    passed: bool
    assertions: list[AssertionResult] = field(default_factory=list)
    traces: list[TraceStep] = field(default_factory=list)
    score: float = 0.0
    breakdown: dict[str, float] = field(default_factory=dict)
    latency_ms: float = 0.0
    cost_units: float = 0.0
    hard_fail: bool = False
    hard_fail_reasons: list[str] = field(default_factory=list)
    needs_human_review: bool = False
    error: str | None = None
    run_index: int = 1


@dataclass
class AgentScorecard:
    agent: str
    score: float
    passed: int
    failed: int
    critical_failures: int
    levels_covered: list[int] = field(default_factory=list)
    readiness: str = "not_ready"
    recommended_fixes: list[str] = field(default_factory=list)


@dataclass
class EvalReport:
    version: str
    results: list[ScenarioResult]
    scorecards: list[AgentScorecard]
    overall_score: float
    passed: int
    failed: int
    critical_failures: int
    readiness: str
    generated_at: str
