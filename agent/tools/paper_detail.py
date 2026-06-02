from __future__ import annotations

from typing import Any

from .arxiv import arxiv_pdf_url
from .crossref import get_crossref_work
from .openalex_search import get_openalex_work
from .semantic_scholar import get_semantic_scholar_paper


def fetch_detail(
    *,
    identifier: str,
    id_type: str,
    openalex_email: str | None = None,
) -> dict[str, Any]:
    """
    Return normalized metadata dict.
    id_type: doi|openalex|semanticscholar|arxiv
    """
    t = id_type.lower().strip()
    if t == "doi":
        return _normalize_crossref(get_crossref_work(doi=identifier))
    if t == "openalex":
        return _normalize_openalex(get_openalex_work(work_id=identifier, email=openalex_email))
    if t in {"semanticscholar", "semantic_scholar", "s2"}:
        return _normalize_s2(get_semantic_scholar_paper(paper_id=identifier))
    if t == "arxiv":
        return {
            "source": "arxiv",
            "id": identifier,
            "pdf_url": arxiv_pdf_url(identifier),
        }
    raise ValueError(f"Unsupported id_type: {id_type}")


def _normalize_crossref(payload: dict[str, Any]) -> dict[str, Any]:
    msg = payload.get("message") or {}
    title_list = msg.get("title") or []
    title = title_list[0] if title_list else None
    doi = msg.get("DOI")
    container = msg.get("container-title") or []
    venue = container[0] if container else None
    year = None
    published = msg.get("published-print") or msg.get("published-online") or msg.get("created") or {}
    parts = published.get("date-parts") if isinstance(published, dict) else None
    if isinstance(parts, list) and parts and isinstance(parts[0], list) and parts[0]:
        year = int(parts[0][0])
    authors = []
    for a in msg.get("author") or []:
        given = a.get("given") or ""
        family = a.get("family") or ""
        name = (given + " " + family).strip()
        if name:
            authors.append(name)
    return {
        "source": "crossref",
        "title": title,
        "authors": authors,
        "abstract": msg.get("abstract"),
        "year": year,
        "venue": venue,
        "doi": doi,
        "url": msg.get("URL"),
        "citation_count": msg.get("is-referenced-by-count"),
        "pdf_url": None,
        "code_url": None,
    }


def _normalize_openalex(work: dict[str, Any]) -> dict[str, Any]:
    host_venue = work.get("host_venue") or {}
    abstract = None
    inv = work.get("abstract_inverted_index")
    if isinstance(inv, dict):
        from .openalex_search import _abstract_from_inverted_index  # type: ignore

        abstract = _abstract_from_inverted_index(inv)
    authors = []
    for au in work.get("authorships") or []:
        author = (au.get("author") or {}) if isinstance(au, dict) else {}
        name = author.get("display_name")
        if name:
            authors.append(name)
    primary_location = work.get("primary_location") or {}
    pdf_url = None
    if isinstance(primary_location, dict):
        pdf_url = primary_location.get("pdf_url")
    return {
        "source": "openalex",
        "title": work.get("title"),
        "authors": authors,
        "abstract": abstract,
        "year": work.get("publication_year"),
        "venue": (host_venue.get("display_name") if isinstance(host_venue, dict) else None),
        "doi": work.get("doi"),
        "url": work.get("id"),
        "citation_count": work.get("cited_by_count"),
        "pdf_url": pdf_url,
        "code_url": None,
    }


def _normalize_s2(paper: dict[str, Any]) -> dict[str, Any]:
    authors = [a.get("name") for a in (paper.get("authors") or []) if a.get("name")]
    external = paper.get("externalIds") or {}
    doi = external.get("DOI") if isinstance(external, dict) else None
    pdf_url = None
    oapdf = paper.get("openAccessPdf") or {}
    if isinstance(oapdf, dict):
        pdf_url = oapdf.get("url")
    return {
        "source": "semanticscholar",
        "title": paper.get("title"),
        "authors": authors,
        "abstract": paper.get("abstract"),
        "year": paper.get("year"),
        "venue": paper.get("venue"),
        "doi": doi,
        "url": paper.get("url"),
        "citation_count": paper.get("citationCount"),
        "pdf_url": pdf_url,
        "code_url": None,
    }
