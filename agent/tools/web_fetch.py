from __future__ import annotations

import re
from html import unescape

import requests

from ..model import Paper


_RE_TAGS = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    s = unescape(s)
    s = _RE_TAGS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fetch_paper_from_url(url: str, *, timeout: int = 60) -> Paper:
    """
    Best-effort fetch a paper-like page and extract title/abstract.
    This is heuristic and will vary by conference site.
    """
    resp = requests.get(url, timeout=timeout, headers={"User-Agent": "paper-agent"})
    resp.raise_for_status()
    html = resp.text

    m = re.search(r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']', html, re.I)
    title = m.group(1).strip() if m else ""
    if not title:
        m2 = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        title = _strip_html(m2.group(1)) if m2 else url

    abstract = ""
    for pat in [
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']citation_abstract["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+name=["\']dc\.description["\'][^>]+content=["\']([^"\']+)["\']',
    ]:
        mm = re.search(pat, html, re.I)
        if mm:
            abstract = mm.group(1).strip()
            break
    abstract = abstract or None

    return Paper(source="web", id=None, title=title, url=url, abstract=abstract)
