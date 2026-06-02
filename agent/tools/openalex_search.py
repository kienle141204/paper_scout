from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

import requests

from ..model import Paper


OPENALEX_BASE_URL = "https://api.openalex.org"


def _build_user_agent(email: str | None) -> str:
    if email and email.strip():
        return f"paper-agent (mailto:{email.strip()})"
    return "paper-agent"


def _abstract_from_inverted_index(inverted_index: dict[str, list[int]] | None) -> str | None:
    if not inverted_index:
        return None
    pos_to_token: dict[int, str] = {}
    for token, positions in inverted_index.items():
        for pos in positions:
            pos_to_token[int(pos)] = token
    if not pos_to_token:
        return None
    start = min(pos_to_token)
    end = max(pos_to_token)
    return " ".join(pos_to_token[i] for i in range(start, end + 1) if i in pos_to_token)


def _resolve_venue_id(session: requests.Session, venue_query: str) -> str | None:
    params = {"search": venue_query, "per-page": 1}
    resp = session.get(f"{OPENALEX_BASE_URL}/venues", params=params, timeout=60)
    if resp.status_code >= 400:
        return None
    data = resp.json()
    results = data.get("results") or []
    if not results:
        return None
    venue_id = (results[0] or {}).get("id")
    return venue_id if isinstance(venue_id, str) and venue_id else None


def search_openalex(
    *,
    query: str,
    venue: str | None = None,
    year: int | None = None,
    limit: int = 25,
    email: str | None = None,
) -> list[Paper]:
    session = requests.Session()
    session.headers.update({"User-Agent": _build_user_agent(email)})

    filters: list[str] = []
    if year is not None:
        filters.append(f"publication_year:{year}")
    if venue:
        venue_id = _resolve_venue_id(session, venue)
        if venue_id:
            filters.append(f"host_venue.id:{venue_id}")

    params: dict[str, Any] = {"search": query, "per-page": min(max(limit, 1), 200)}
    if filters:
        params["filter"] = ",".join(filters)

    resp = session.get(f"{OPENALEX_BASE_URL}/works", params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    out: list[Paper] = []
    for item in payload.get("results", []):
        abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
        host_venue = item.get("host_venue") or {}
        primary_location = item.get("primary_location") or {}
        source = (primary_location.get("source") or {}) if isinstance(primary_location, dict) else {}
        landing_page_url = primary_location.get("landing_page_url") if isinstance(primary_location, dict) else None
        openalex_id = str(item.get("id") or "")
        out.append(
            Paper(
                source="openalex",
                id=openalex_id or None,
                title=str(item.get("title") or "").strip(),
                year=item.get("publication_year"),
                venue=(host_venue.get("display_name") if isinstance(host_venue, dict) else None) or None,
                doi=item.get("doi"),
                url=landing_page_url or source.get("homepage_url") or openalex_id or None,
                abstract=abstract,
            )
        )
    return out


def related_openalex(
    *,
    work_id: str,
    limit: int = 25,
    email: str | None = None,
) -> list[Paper]:
    session = requests.Session()
    session.headers.update({"User-Agent": _build_user_agent(email)})
    # OpenAlex supports filter=related_to:<work_id> to fetch related works.
    params: dict[str, Any] = {"filter": f"related_to:{work_id}", "per-page": min(max(limit, 1), 200)}
    resp = session.get(f"{OPENALEX_BASE_URL}/works", params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    out: list[Paper] = []
    for item in payload.get("results", []):
        abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
        host_venue = item.get("host_venue") or {}
        openalex_id = str(item.get("id") or "")
        out.append(
            Paper(
                source="openalex",
                id=openalex_id or None,
                title=str(item.get("title") or "").strip(),
                year=item.get("publication_year"),
                venue=(host_venue.get("display_name") if isinstance(host_venue, dict) else None) or None,
                doi=item.get("doi"),
                url=openalex_id or None,
                abstract=abstract,
            )
        )
    return out


def get_openalex_work(*, work_id: str, email: str | None = None) -> dict[str, Any]:
    session = requests.Session()
    session.headers.update({"User-Agent": _build_user_agent(email)})
    wid = work_id.strip()
    # Accept either full URL or short W-id
    if wid.startswith("W"):
        wid = f"https://openalex.org/{wid}"
    resp = session.get(f"{OPENALEX_BASE_URL}/works/{wid}", timeout=60)
    resp.raise_for_status()
    return resp.json()


def citing_openalex(*, work_id: str, limit: int = 25, email: str | None = None) -> list[Paper]:
    session = requests.Session()
    session.headers.update({"User-Agent": _build_user_agent(email)})
    wid = work_id.strip()
    if wid.startswith("https://openalex.org/"):
        wid = wid.split("/")[-1]
    params: dict[str, Any] = {"filter": f"cites:{wid}", "per-page": min(max(limit, 1), 200)}
    resp = session.get(f"{OPENALEX_BASE_URL}/works", params=params, timeout=60)
    resp.raise_for_status()
    payload = resp.json()

    out: list[Paper] = []
    for item in payload.get("results", []):
        abstract = _abstract_from_inverted_index(item.get("abstract_inverted_index"))
        host_venue = item.get("host_venue") or {}
        openalex_id = str(item.get("id") or "")
        out.append(
            Paper(
                source="openalex",
                id=openalex_id or None,
                title=str(item.get("title") or "").strip(),
                year=item.get("publication_year"),
                venue=(host_venue.get("display_name") if isinstance(host_venue, dict) else None) or None,
                doi=item.get("doi"),
                url=openalex_id or None,
                abstract=abstract,
            )
        )
    return out
