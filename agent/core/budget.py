"""RunBudget — per-run resource caps consulted by the governor before each step."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class RunBudget:
    max_wall_clock_ms: int = 15000
    max_tokens: int = 8000
    max_tool_calls: int = 12
    max_cost_usd: float = 0.05
    max_retries: int = 2


def default_budget(
    agent: Literal["search", "rag"],
    mode: Literal["skill", "fast", "deliberate"] | None = None,
) -> RunBudget:
    """Return the default budget for an agent/lane.

    RAG's "fast" and "skill" lanes are single-shot by design — they get a much
    smaller budget than "deliberate" (the ReAct planner), which keeps the full
    doc defaults since it's the only lane that actually loops.
    """
    if agent == "rag" and mode in ("fast", "skill"):
        return RunBudget(max_wall_clock_ms=6000, max_tokens=4000, max_tool_calls=4, max_cost_usd=0.02, max_retries=1)
    return RunBudget()
