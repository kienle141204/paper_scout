"""Search query analysis owned by the Search Agent.

The frontend may still call /api/parse-query for eager UI filter suggestions,
but run_search() must be able to analyze a raw natural-language query by
itself. This module keeps that logic FastAPI-free.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from agent.config import Config
from agent.tools.prompts import _KNOWN_VENUES
from agent.tools.query_parse import ParsedQuery, parse_query

from .state import SearchParams
from .source_router import route_sources


_YEAR_RE = re.compile(r"\b(19[8-9]\d|20[0-4]\d|2050)\b")


@dataclass
class QueryAnalysis:
    params: SearchParams
    query_plan: dict


def _heuristic_parse(query: str) -> ParsedQuery:
    upper = query.upper()
    venues = [v for v in _KNOWN_VENUES if re.search(rf"\b{re.escape(v)}\b", upper)]
    years = [int(y) for y in _YEAR_RE.findall(query)]
    year_from = min(years) if years else None
    year_to = max(years) if years else None

    # Keep this intentionally conservative: it is a fallback when LLM parsing
    # is unavailable, so do not attempt complex rewriting.
    keywords = query.strip()
    for v in venues:
        keywords = re.sub(rf"\b{re.escape(v)}\b", "", keywords, flags=re.IGNORECASE).strip()
    for y in years:
        keywords = re.sub(rf"\b{y}\b", "", keywords).strip()
    keywords = re.sub(r"\s+", " ", keywords) or query

    return ParsedQuery(
        keywords=keywords,
        keyword_variants=[],
        venues=venues,
        year_from=year_from,
        year_to=year_to,
        corrected_query=None,
    )


def analyze_search_params(params: SearchParams, *, cfg: Config) -> QueryAnalysis:
    """Fill missing query hints without overriding explicit request filters."""
    has_client_hints = bool(
        params.keyword_variants
        or params.conferences
        or params.year_from is not None
        or params.year_to is not None
        or params.corrected_query
    )

    parsed: ParsedQuery | None = None
    used_llm = False
    fallback_reason: str | None = None

    if not has_client_hints:
        provider = cfg.llm_provider
        model = cfg.openai_model if provider == "openai" else cfg.gemini_model
        base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url
        try:
            parsed = parse_query(query=params.query, provider=provider, model=model, base_url=base_url)
            used_llm = True
        except Exception as exc:
            fallback_reason = str(exc)
            parsed = _heuristic_parse(params.query)
    else:
        parsed = ParsedQuery(
            keywords=params.query,
            keyword_variants=list(params.keyword_variants),
            venues=list(params.conferences),
            year_from=params.year_from,
            year_to=params.year_to,
            corrected_query=params.corrected_query,
        )

    normalized_query = parsed.keywords.strip() or params.query
    next_params = replace(
        params,
        query=normalized_query,
        keyword_variants=params.keyword_variants or parsed.keyword_variants,
        conferences=params.conferences or parsed.venues,
        year_from=params.year_from if params.year_from is not None else parsed.year_from,
        year_to=params.year_to if params.year_to is not None else parsed.year_to,
        corrected_query=params.corrected_query or parsed.corrected_query,
    )

    query_plan = {
        "original_query": params.query,
        "normalized_query": normalized_query,
        "keyword_variants": next_params.keyword_variants,
        "filters": {
            "venues": next_params.conferences,
            "year_from": next_params.year_from,
            "year_to": next_params.year_to,
            "language": next_params.language,
        },
        "sources": route_sources(next_params),
        "analyzer": "llm" if used_llm else ("client_hints" if has_client_hints else "heuristic"),
        "fallback_reason": fallback_reason,
    }
    return QueryAnalysis(params=next_params, query_plan=query_plan)
