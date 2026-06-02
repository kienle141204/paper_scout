from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Paper:
    source: str
    id: str | None
    title: str
    year: int | None = None
    venue: str | None = None
    url: str | None = None
    doi: str | None = None
    abstract: str | None = None
    authors: tuple[str, ...] = ()
    keywords: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "id": self.id,
            "title": self.title,
            "year": self.year,
            "venue": self.venue,
            "url": self.url,
            "doi": self.doi,
            "abstract": self.abstract,
            "authors": list(self.authors),
            "keywords": list(self.keywords),
        }

