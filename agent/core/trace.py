"""RunTrace — passive observability: per-step latency/tokens/cost, never blocks a request."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from typing import Callable, Literal

logger = logging.getLogger("agent.trace")


@dataclass
class RunStep:
    name: str
    latency_ms: int = 0
    tokens: int = 0
    cost_usd: float = 0.0
    model: str = ""


@dataclass
class RunTrace:
    trace_id: str
    agent: Literal["search", "rag"]
    session_id: str | None = None
    paper_id: str | None = None
    steps: list[RunStep] = field(default_factory=list)
    guardrails: dict[str, bool] = field(default_factory=dict)
    outcome: Literal["answered", "refused", "budget_exceeded", "error"] | None = None

    @property
    def total_latency_ms(self) -> int:
        return sum(s.latency_ms for s in self.steps)

    @property
    def total_cost_usd(self) -> float:
        return sum(s.cost_usd for s in self.steps)

    @property
    def total_tokens(self) -> int:
        return sum(s.tokens for s in self.steps)

    def elapsed_ms(self) -> int:
        return self.total_latency_ms

    def log(self) -> None:
        """Best-effort structured log of the full trace. Never raises."""
        try:
            logger.info("run_trace %s", asdict(self))
        except Exception:
            pass


def new_trace(agent: Literal["search", "rag"], *, session_id: str | None = None, paper_id: str | None = None) -> RunTrace:
    return RunTrace(trace_id=uuid.uuid4().hex, agent=agent, session_id=session_id, paper_id=paper_id)


def _estimate_tokens(*texts: str) -> int:
    return sum(len(t) for t in texts if t) // 4


@contextmanager
def traced_step(
    trace: RunTrace,
    name: str,
    *,
    model: str = "",
    cost_per_1k: float = 0.0,
    tokens_estimator: Callable[[], int] | None = None,
):
    """Time a block, append a RunStep to *trace* on exit. Never swallows the
    wrapped block's own exceptions — only the trace bookkeeping itself is
    defensive (a tracer bug must never break a request).
    """
    start = time.monotonic()
    try:
        yield
    finally:
        latency_ms = int((time.monotonic() - start) * 1000)
        try:
            tokens = tokens_estimator() if tokens_estimator else 0
            cost_usd = round((tokens / 1000.0) * cost_per_1k, 6)
            trace.steps.append(RunStep(name=name, latency_ms=latency_ms, tokens=tokens, cost_usd=cost_usd, model=model))
        except Exception:
            pass
