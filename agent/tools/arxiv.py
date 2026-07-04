from __future__ import annotations

import re
from typing import Any

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from ..model import Paper


ARXIV_API_URL = "http://export.arxiv.org/api/query"


def _arxiv_retriable(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in (429, 500, 503)
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


@retry(
    retry=retry_if_exception(_arxiv_retriable),
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=3, max=30),
    reraise=True,
)
def _arxiv_get(params: dict[str, Any]) -> requests.Response:
    resp = requests.get(ARXIV_API_URL, params=params, timeout=60)
    resp.raise_for_status()
    return resp


def search_arxiv(*, query: str, max_results: int = 25) -> list[Paper]:
    import feedparser

    # ArXiv uses its own query syntax. We'll pass through and also allow plain text.
    params = {
        "search_query": f"all:{query}" if ":" not in query else query,
        "start": 0,
        "max_results": min(max(max_results, 1), 100),
    }
    resp = _arxiv_get(params)
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
