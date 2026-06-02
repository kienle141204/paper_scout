from __future__ import annotations

import re
from typing import Any

import requests

from ..model import Paper


ARXIV_API_URL = "http://export.arxiv.org/api/query"


def search_arxiv(*, query: str, max_results: int = 25) -> list[Paper]:
    import feedparser

    # ArXiv uses its own query syntax. We'll pass through and also allow plain text.
    params = {
        "search_query": f"all:{query}" if ":" not in query else query,
        "start": 0,
        "max_results": min(max(max_results, 1), 100),
    }
    resp = requests.get(ARXIV_API_URL, params=params, timeout=60)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)

    out: list[Paper] = []
    for e in feed.entries:
        title = (e.get("title") or "").replace("\n", " ").strip()
        abstract = (e.get("summary") or "").replace("\n", " ").strip() or None
        url = e.get("link") or None
        arxiv_id = None
        m = re.search(r"arxiv\.org/abs/([^?/]+)", url or "")
        if m:
            arxiv_id = m.group(1)
        year = None
        published = e.get("published")
        if isinstance(published, str) and len(published) >= 4 and published[:4].isdigit():
            year = int(published[:4])
        out.append(
            Paper(
                source="arxiv",
                id=arxiv_id,
                title=title,
                year=year,
                venue="arXiv",
                url=url,
                abstract=abstract,
            )
        )
    return out


def arxiv_pdf_url(arxiv_id: str) -> str:
    return f"https://arxiv.org/pdf/{arxiv_id}.pdf"
