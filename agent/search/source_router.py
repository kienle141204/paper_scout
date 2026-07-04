"""Source routing for the Search Agent.

This is deliberately small and deterministic. The app defaults to OpenReview
for the MVP; callers can still pass explicit sources in tests or specialized
flows.
"""
from __future__ import annotations

from typing import Iterable

from .state import SearchParams

SUPPORTED_SOURCES = {"semantic_scholar", "openreview", "openalex", "arxiv"}
DEFAULT_SEARCH_SOURCES = ["openreview"]


def normalize_sources(sources: Iterable[str] | None) -> list[str]:
    out: list[str] = []
    for source in sources or []:
        s = str(source).strip().lower().replace("-", "_")
        if s in SUPPORTED_SOURCES and s not in out:
            out.append(s)
    return out


def route_sources(params: SearchParams) -> list[str]:
    explicit = normalize_sources(params.sources)
    if explicit:
        return explicit

    return list(DEFAULT_SEARCH_SOURCES)
