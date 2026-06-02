from __future__ import annotations

from typing import Any

import requests

from ..model import Paper


S2_BASE_URL = "https://api.semanticscholar.org/graph/v1"


def search_semantic_scholar(
    *,
    query: str,
    limit: int = 25,
    fields: str = "title,abstract,year,venue,authors,url,externalIds,citationCount,openAccessPdf",
) -> list[Paper]:
    """
    Semantic Scholar search endpoint.
    Docs: https://api.semanticscholar.org/
    """
    params = {"query": query, "limit": min(max(limit, 1), 100), "fields": fields}
    resp = requests.get(f"{S2_BASE_URL}/paper/search", params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    out: list[Paper] = []
    for item in data.get("data", []):
        external = item.get("externalIds") or {}
        doi = external.get("DOI") if isinstance(external, dict) else None
        url = item.get("url") or None
        if not url and item.get("paperId"):
            url = f"https://www.semanticscholar.org/paper/{item['paperId']}"
        out.append(
            Paper(
                source="semanticscholar",
                id=item.get("paperId"),
                title=(item.get("title") or "").strip(),
                year=item.get("year"),
                venue=item.get("venue"),
                doi=doi,
                url=url,
                abstract=(item.get("abstract") or None),
            )
        )
    return out


def get_semantic_scholar_paper(*, paper_id: str) -> dict[str, Any]:
    params = {
        "fields": "title,abstract,year,venue,authors,url,externalIds,citationCount,referenceCount,influentialCitationCount,openAccessPdf",
    }
    resp = requests.get(f"{S2_BASE_URL}/paper/{paper_id}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()

