"""Search Agent core loop — sufficiency/rewrite loop, governor/tracer/guardrails."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from agent.config import Config
from agent.core.budget import default_budget
from agent.core.governor import BudgetExceeded, Governor
from agent.core.trace import new_trace

from . import tools as search_tools
from .guardrails import input_guardrail, output_guardrail
from .query_analyzer import analyze_search_params
from .state import SearchParams, SearchState
from .synthesize import synthesize
from .workspace import cache_key, get_cached_search, put_cached_search, save_search_session


@dataclass
class SearchRunResult:
    papers: list[dict]
    total: int
    query: str
    has_more: bool
    corrected_query: str | None
    session_id: str | None = None
    query_plan: dict = field(default_factory=dict)
    source_stats: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    synthesis: str | None = None
    synthesis_citations: list[dict] = field(default_factory=list)
    degraded: bool = False
    refused: bool = False
    refusal_reason: str | None = None

    def to_response_dict(self) -> dict:
        out = {
            "papers": self.papers,
            "total": self.total,
            "query": self.query,
            "has_more": self.has_more,
            "corrected_query": self.corrected_query,
            "session_id": self.session_id,
            "query_plan": self.query_plan,
            "source_stats": self.source_stats,
            "warnings": self.warnings,
        }
        if self.synthesis is not None or self.synthesis_citations:
            out["synthesis"] = self.synthesis
            out["synthesis_citations"] = self.synthesis_citations
        return out


def run_search(
    params: SearchParams,
    *,
    cfg: Config,
    session_id: str | None = None,
    max_iterations: int = 3,
) -> SearchRunResult:
    trace = new_trace("search", session_id=session_id)
    governor = Governor(default_budget("search"), trace, time.monotonic())

    original_query = params.query
    gr = input_guardrail(params.query, cfg=cfg)
    trace.guardrails["input_pass"] = gr.passed
    if not gr.passed:
        trace.outcome = "refused"
        trace.log()
        return SearchRunResult(
            papers=[], total=0, query=params.query, has_more=False,
            corrected_query=params.corrected_query, session_id=params.session_id,
            refused=True, refusal_reason=gr.reason,
        )

    analysis = analyze_search_params(params, cfg=cfg)
    params = analysis.params
    state = SearchState(user_query=original_query, normalized_query=params.query)
    state.query_plan = analysis.query_plan
    state.search_queries = [params.query]
    filters = {
        "venues": params.conferences,
        "year_from": params.year_from,
        "year_to": params.year_to,
        "language": params.language,
    }
    should_persist_workspace = bool(params.use_cache or params.record_memory_events or params.session_id)
    cache_key_value = cache_key(
        query=params.query,
        filters=filters,
        sources=params.sources,
        limit=params.limit,
        offset=params.offset,
    )
    if params.use_cache:
        cached = get_cached_search(cache_key_value)
        if cached:
            cached_stats = dict(cached.get("source_stats") or {})
            cached_stats["cache_hit"] = True
            sid = None
            if should_persist_workspace:
                sid = save_search_session(
                    session_id=params.session_id,
                    original_query=original_query,
                    normalized_query=params.query,
                    filters=filters,
                    papers=cached["papers"],
                    query_plan=cached.get("query_plan") or state.query_plan,
                    source_stats=cached_stats,
                )
            trace.outcome = "answered"
            trace.log()
            selected = cached["papers"][: params.limit]
            return SearchRunResult(
                papers=selected,
                total=len(cached["papers"]),
                query=params.query,
                has_more=len(cached["papers"]) > params.limit,
                corrected_query=params.corrected_query,
                session_id=sid,
                query_plan=cached.get("query_plan") or state.query_plan,
                source_stats=cached_stats,
            )

    try:
        for iteration in range(max_iterations):
            state.iteration = iteration
            try:
                level = governor.check_before_step(f"search_round_{iteration}")
            except BudgetExceeded:
                trace.outcome = "budget_exceeded"
                break

            batch_limit = None
            relax_filters = False
            variant_queries: list[str] = []
            if iteration == 0:
                query = params.query
                variant_queries = [v for v in params.keyword_variants[:2] if v and v != params.query]
            else:
                rewritten = state.search_queries[-1:]
                query = rewritten[0] if rewritten else params.query

            if level >= 1:  # LIGHT — halve batch size
                batch_limit = max(10, min(params.limit * 3, 100) // 2)
            if level >= 2:  # MODERATE — drop variant fan-out
                variant_queries = []

            try:
                new_papers, has_more_this_round, round_stats = search_tools.search_multi_source(
                    query, variant_queries, params, state.seen_ids,
                    limit=params.limit, batch_limit=batch_limit, relax_filters=relax_filters,
                    openalex_email=cfg.openalex_email,
                )
                state.source_stats[f"round_{iteration}"] = round_stats
            except Exception:
                # A round failing outright shouldn't kill the whole run — stop
                # iterating and synthesize/return whatever we already have.
                state.warnings.append(f"search_round_{iteration}_failed")
                break

            state.candidates += new_papers
            state.selected = search_tools.score_and_rank(params.query, list(state.candidates), cfg=cfg)

            reason = search_tools.stopping_reason(state, max_iterations, len(new_papers))
            if reason:
                state.is_sufficient = reason == "sufficient" or search_tools.is_sufficient(state)
                break

            if level >= 3:  # SEVERE — stop iterating regardless of sufficiency
                state.degraded = True
                break

            strategy = "expand" if len(state.candidates) < 5 else ("narrow" if len(state.candidates) > params.limit * 4 else "reangle")
            state.search_queries += search_tools.rewrite_query(params, strategy, iteration)
    except BudgetExceeded:
        trace.outcome = "budget_exceeded"
        state.degraded = True

    selected = state.selected[: params.limit]
    has_more = len(state.selected) > params.limit

    synth_text: str | None = None
    synth_citations: list[dict] = []
    degraded = state.degraded
    if params.include_synthesis:
        try:
            level = governor.check_before_step("synthesize")
        except BudgetExceeded:
            level = None
        if level is not None:
            synth = synthesize(params.query, selected, cfg=cfg, degrade=level)
            synth = output_guardrail(synth, state.candidates)
            synth_text, synth_citations, degraded = synth.text, synth.citations, degraded or synth.degraded
        else:
            degraded = True

    trace.outcome = trace.outcome or "answered"
    trace.log()

    sid = None
    if should_persist_workspace:
        sid = save_search_session(
            session_id=params.session_id,
            original_query=original_query,
            normalized_query=params.query,
            filters=filters,
            papers=state.selected,
            query_plan=state.query_plan,
            source_stats=state.source_stats,
        )
    if params.use_cache and state.selected:
        put_cached_search(
            cache_key_value,
            normalized_query=params.query,
            filters=filters,
            papers=state.selected,
            query_plan=state.query_plan,
            source_stats=state.source_stats,
        )

    return SearchRunResult(
        papers=selected,
        total=len(state.selected),
        query=params.query,
        has_more=has_more,
        corrected_query=params.corrected_query,
        session_id=sid,
        query_plan=state.query_plan,
        source_stats=state.source_stats,
        warnings=state.warnings,
        synthesis=synth_text,
        synthesis_citations=synth_citations,
        degraded=degraded,
    )
