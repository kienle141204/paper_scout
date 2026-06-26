"""RAG Agent state — plain dataclasses, no FastAPI/Pydantic dependency."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from agent.core.budget import RunBudget, default_budget
from agent.core.trace import RunTrace


@dataclass
class ReActStep:
    thought: str | None = None
    action: str | None = None
    observation: str | None = None


@dataclass
class RAGState:
    paper_id: str
    question: str
    standalone_query: str | None = None
    mode: Literal["skill", "fast", "deliberate"] | None = None
    active_skill: str | None = None
    scratchpad: list[ReActStep] = field(default_factory=list)
    retrieved: list[dict] = field(default_factory=list)
    answer: str | None = None
    citations: list[dict] = field(default_factory=list)
    is_grounded: bool = True
    history: list[dict] = field(default_factory=list)
    budget: RunBudget = field(default_factory=lambda: default_budget("rag"))
    trace: RunTrace | None = None
