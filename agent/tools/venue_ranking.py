from __future__ import annotations

import re
from dataclasses import dataclass
from html import unescape
from typing import Any

import requests

from .dblp import venue_lookup_dblp


@dataclass(frozen=True)
class VenueItem:
    name: str
    url: str | None = None
    acronym: str | None = None
    kind: str | None = None
    source: str = "unknown"
    deadline: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "url": self.url,
            "acronym": self.acronym,
            "kind": self.kind,
            "source": self.source,
            "deadline": self.deadline,
        }


def lookup_venue(*, query: str, sources: list[str] | None = None, limit: int = 10) -> list[VenueItem]:
    sources = sources or ["dblp", "wikicfp"]
    out: list[VenueItem] = []
    for src in sources:
        s = src.lower().strip()
        if s == "dblp":
            for it in venue_lookup_dblp(venue_query=query, hits=limit):
                out.append(
                    VenueItem(
                        name=str(it.get("name") or ""),
                        url=it.get("url"),
                        acronym=it.get("acronym"),
                        kind=it.get("type"),
                        source="dblp",
                    )
                )
        elif s == "wikicfp":
            out.extend(_lookup_wikicfp(query=query, limit=limit))
        elif s in {"core", "scimago"}:
            # Placeholder: CORE/Scimago không có API public ổn định.
            # Khi bạn cung cấp file dump/API key, mình sẽ tích hợp tiếp.
            continue
        else:
            raise ValueError(f"Unknown venue source: {src}")
    # dedupe by (name,url)
    seen: set[tuple[str, str | None]] = set()
    deduped: list[VenueItem] = []
    for v in out:
        key = (v.name.lower().strip(), v.url)
        if key in seen or not v.name.strip():
            continue
        seen.add(key)
        deduped.append(v)
    return deduped


_RE_TAGS = re.compile(r"<[^>]+>")


def _strip_html(s: str) -> str:
    s = unescape(s)
    s = _RE_TAGS.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _lookup_wikicfp(*, query: str, limit: int) -> list[VenueItem]:
    # Best effort HTML scrape
    url = "http://www.wikicfp.com/cfp/servlet/tool.search"
    resp = requests.get(url, params={"q": query}, timeout=60, headers={"User-Agent": "paper-agent"})
    if resp.status_code >= 400:
        return []
    html = resp.text

    # Results are often in a table with rows containing <a href="event.showcfp?...">
    items: list[VenueItem] = []
    for m in re.finditer(r'href="(event\.showcfp\?[^"]+)"[^>]*>([^<]+)</a>', html, re.I):
        rel = m.group(1)
        name = _strip_html(m.group(2))
        link = f"http://www.wikicfp.com/cfp/{rel}"
        items.append(VenueItem(name=name, url=link, source="wikicfp"))
        if len(items) >= limit:
            break
    return items

