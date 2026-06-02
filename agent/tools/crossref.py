from __future__ import annotations

from typing import Any

import requests

from ..model import Paper


CROSSREF_BASE_URL = "https://api.crossref.org"


def search_crossref(
    *,
    query: str,
    rows: int = 25,
) -> list[Paper]:
    params = {"query": query, "rows": min(max(rows, 1), 100)}
    resp = requests.get(f"{CROSSREF_BASE_URL}/works", params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    items = (((data.get("message") or {}).get("items")) or []) if isinstance(data, dict) else []

    out: list[Paper] = []
    for it in items:
        title_list = it.get("title") or []
        title = (title_list[0] if title_list else "") or ""
        year = None
        published = it.get("published-print") or it.get("published-online") or it.get("created") or {}
        parts = published.get("date-parts") if isinstance(published, dict) else None
        if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
            year = int(parts[0][0])

        doi = it.get("DOI") or None
        url = it.get("URL") or None
        venue = None
        container = it.get("container-title") or []
        if container:
            venue = container[0]

        out.append(
            Paper(
                source="crossref",
                id=doi,
                title=str(title).strip(),
                year=year,
                venue=venue,
                doi=doi,
                url=url,
                abstract=(it.get("abstract") or None),
            )
        )
    return out


def get_crossref_work(*, doi: str) -> dict[str, Any]:
    doi = doi.strip()
    resp = requests.get(f"{CROSSREF_BASE_URL}/works/{doi}", timeout=60)
    resp.raise_for_status()
    return resp.json()


def doi_to_bibtex(*, doi: str) -> str:
    # Crossref content negotiation
    headers = {"Accept": "application/x-bibtex"}
    resp = requests.get(f"https://doi.org/{doi.strip()}", headers=headers, timeout=60, allow_redirects=True)
    resp.raise_for_status()
    return resp.text.strip()

