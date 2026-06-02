from __future__ import annotations

from typing import Any
from urllib.parse import quote_plus

import requests

from ..model import Paper


DBLP_BASE_URL = "https://dblp.org"


def search_dblp(*, query: str, hits: int = 25) -> list[Paper]:
    # DBLP Search API (JSON)
    url = f"{DBLP_BASE_URL}/search/publ/api"
    params = {"q": query, "h": min(max(hits, 1), 100), "format": "json"}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    hits_data = (((data.get("result") or {}).get("hits") or {}).get("hit")) or []

    out: list[Paper] = []
    for h in hits_data:
        info = h.get("info") or {}
        title = (info.get("title") or "").strip()
        year = None
        try:
            year = int(info.get("year")) if info.get("year") else None
        except Exception:
            year = None
        venue = info.get("venue") or info.get("type") or None
        url = info.get("url") or None
        out.append(Paper(source="dblp", id=info.get("key"), title=title, year=year, venue=venue, url=url))
    return out


def venue_lookup_dblp(*, venue_query: str, hits: int = 10) -> list[dict[str, Any]]:
    url = f"{DBLP_BASE_URL}/search/venue/api"
    params = {"q": venue_query, "h": min(max(hits, 1), 100), "format": "json"}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    hit_list = (((data.get("result") or {}).get("hits") or {}).get("hit")) or []
    out: list[dict[str, Any]] = []
    for h in hit_list:
        info = h.get("info") or {}
        out.append(
            {
                "name": info.get("venue") or info.get("title") or "",
                "url": info.get("url"),
                "acronym": info.get("acronym"),
                "type": info.get("type"),
            }
        )
    return out

