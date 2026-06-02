from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

from .llm_text import generate_text
from .prompts import PARSE_QUERY, _KNOWN_VENUES


@dataclass
class ParsedQuery:
    keywords: str
    venues: list[str] = field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None


def parse_query(
    *,
    query: str,
    provider: str,
    model: str,
    base_url: str | None = None,
) -> ParsedQuery:
    raw = generate_text(
        provider=provider,
        system=PARSE_QUERY,
        user=query,
        model=model,
        base_url=base_url,
    )

    # Extract JSON from response (handles extra text)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return ParsedQuery(keywords=query)

    try:
        data = json.loads(m.group())
    except json.JSONDecodeError:
        return ParsedQuery(keywords=query)

    keywords = (data.get("keywords") or "").strip() or query
    raw_venues = data.get("venues") or []
    venues = [v for v in raw_venues if v in _KNOWN_VENUES]

    year_from = data.get("year_from")
    year_to = data.get("year_to")

    return ParsedQuery(
        keywords=keywords,
        venues=venues,
        year_from=int(year_from) if year_from else None,
        year_to=int(year_to) if year_to else None,
    )
