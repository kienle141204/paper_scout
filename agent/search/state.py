"""Search Agent state — plain dataclasses, no FastAPI/Pydantic dependency."""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.core.budget import RunBudget, default_budget
from agent.core.trace import RunTrace


@dataclass
class SearchParams:
    """Plain-dataclass mirror of backend.api.PaperSearchRequest's fields the
    Search Agent needs. backend/api.py converts its Pydantic request into
    this before calling run_search(), keeping agent/ FastAPI-free.
    """
    query: str
    keyword_variants: list[str] = field(default_factory=list)
    conferences: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    language: str = "vi"
    limit: int = 20
    offset: int = 0
    corrected_query: str | None = None
    include_synthesis: bool = False
    session_id: str | None = None
    sources: list[str] = field(default_factory=lambda: ["openreview"])
    use_cache: bool = False
    record_memory_events: bool = False


@dataclass
class SearchState:
    user_query: str
    normalized_query: str | None = None
    search_queries: list[str] = field(default_factory=list)
    candidates: list[dict] = field(default_factory=list)
    selected: list[dict] = field(default_factory=list)
    synthesis: str | None = None
    synthesis_citations: list[dict] = field(default_factory=list)
    query_plan: dict = field(default_factory=dict)
    source_stats: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    iteration: int = 0
    is_sufficient: bool = False
    seen_ids: set[str] = field(default_factory=set)
    degraded: bool = False
    budget: RunBudget = field(default_factory=lambda: default_budget("search"))
    trace: RunTrace | None = None
