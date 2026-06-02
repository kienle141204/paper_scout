from __future__ import annotations

from .crossref import doi_to_bibtex, get_crossref_work


def bibtex_from_doi(doi: str) -> str:
    return doi_to_bibtex(doi=doi)


def apa_from_doi(doi: str) -> str:
    data = get_crossref_work(doi=doi)
    msg = data.get("message") or {}
    title_list = msg.get("title") or []
    title = title_list[0] if title_list else ""
    authors = []
    for a in msg.get("author") or []:
        family = (a.get("family") or "").strip()
        given = (a.get("given") or "").strip()
        initial = (given[:1] + ".") if given else ""
        if family:
            authors.append(f"{family}, {initial}".strip())
    author_str = "; ".join(authors) if authors else "Unknown"
    year = ""
    published = msg.get("published-print") or msg.get("published-online") or msg.get("created") or {}
    parts = published.get("date-parts") if isinstance(published, dict) else None
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        year = str(parts[0][0])
    venue_list = msg.get("container-title") or []
    venue = venue_list[0] if venue_list else ""
    return f"{author_str} ({year}). {title}. {venue}. https://doi.org/{doi.strip()}"

