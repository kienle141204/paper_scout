"""Governor — checks RunBudget before each step and signals how aggressively to degrade.

Generic across agents: it only computes a DegradeLevel from elapsed time /
tokens / tool calls / cost vs. the budget. Each agent's own agent.py decides
what a given level concretely means (drop rerank, cheaper model, etc).
"""
from __future__ import annotations

import time
from enum import IntEnum

from .budget import RunBudget
from .trace import RunTrace


class DegradeLevel(IntEnum):
    NONE = 0
    LIGHT = 1     # e.g. drop rerank / reduce top_k
    MODERATE = 2  # switch to cheaper model
    SEVERE = 3    # return partial answer with warning


class BudgetExceeded(Exception):
    """Raised only at hard wall-clock timeout — every other dimension degrades instead."""


_LIGHT_FRACTION = 0.70
_MODERATE_FRACTION = 0.85
_SEVERE_FRACTION = 0.95


class Governor:
    def __init__(self, budget: RunBudget, trace: RunTrace, started_at: float | None = None):
        self.budget = budget
        self.trace = trace
        self.started_at = started_at if started_at is not None else time.monotonic()
        self._tool_calls = 0

    def note_tool_call(self) -> None:
        self._tool_calls += 1

    def check_before_step(self, step_name: str) -> DegradeLevel:
        elapsed_ms = (time.monotonic() - self.started_at) * 1000
        tokens_used = self.trace.total_tokens
        cost_used = self.trace.total_cost_usd
        tool_calls_used = max(self._tool_calls, len(self.trace.steps))

        if elapsed_ms >= self.budget.max_wall_clock_ms:
            raise BudgetExceeded(f"wall clock exceeded before step '{step_name}'")

        fractions = [
            elapsed_ms / self.budget.max_wall_clock_ms if self.budget.max_wall_clock_ms else 0,
            tokens_used / self.budget.max_tokens if self.budget.max_tokens else 0,
            tool_calls_used / self.budget.max_tool_calls if self.budget.max_tool_calls else 0,
            cost_used / self.budget.max_cost_usd if self.budget.max_cost_usd else 0,
        ]
        worst = max(fractions) if fractions else 0.0

        if worst >= _SEVERE_FRACTION:
            return DegradeLevel.SEVERE
        if worst >= _MODERATE_FRACTION:
            return DegradeLevel.MODERATE
        if worst >= _LIGHT_FRACTION:
            return DegradeLevel.LIGHT
        return DegradeLevel.NONE
