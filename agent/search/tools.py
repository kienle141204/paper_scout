"""Search Agent tools — multi-source search, scoring, dedup, sufficiency.

Most of this module is relocated near-verbatim from backend/api.py's former
inline `/api/papers/search` implementation (_call_s2, _build_s2_params,
_collect_from_raw, _search_fallback, _paper_from_s2, _score_papers,
_enrich_citation_counts) so the endpoint's behavior stays identical. New
functions (not present before): is_sufficient, stopping_reason, rewrite_query,
dedupe — these implement the doc's sufficiency/rewrite loop.
"""
from __future__ import annotations

import datetime
import math
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from agent.config import Config
from agent.model import Paper
from agent.tools.arxiv import arxiv_pdf_url, search_arxiv
from agent.tools.openalex_search import search_openalex
from agent.tools.paper_search import search_papers
from agent.tools.relevance import score_batch

from .source_router import route_sources
from .state import SearchParams, SearchState

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "paperId,title,abstract,authors,year,venue,externalIds,openAccessPdf,citationCount"
_S2_API_KEY: str = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

_CONF_VENUE_ALIASES: dict[str, list[str]] = {
    "NeurIPS": ["NeurIPS", "Neural Information Processing Systems", "NIPS"],
    "ICML": ["ICML", "International Conference on Machine Learning"],
    "ICLR": ["ICLR", "International Conference on Learning Representations"],
    "CVPR": ["CVPR", "Computer Vision and Pattern Recognition"],
    "ICCV": ["ICCV", "International Conference on Computer Vision"],
    "ECCV": ["ECCV", "European Conference on Computer Vision"],
    "ACL": ["ACL", "Association for Computational Linguistics"],
    "EMNLP": ["EMNLP", "Empirical Methods in Natural Language Processing"],
    "NAACL": ["NAACL", "North American Chapter of the Association for Computational Linguistics"],
    "AAAI": ["AAAI", "AAAI Conference on Artificial Intelligence"],
    "IJCAI": ["IJCAI", "International Joint Conference on Artificial Intelligence"],
    "KDD": ["KDD", "Knowledge Discovery and Data Mining"],
    "WWW": ["WWW", "The Web Conference"],
    "SIGIR": ["SIGIR"],
    "ICSE": ["ICSE", "International Conference on Software Engineering"],
}


def normalize_venue(venue: str | None) -> str | None:
    if not venue:
        return None
    v = venue.upper()
    for key, aliases in _CONF_VENUE_ALIASES.items():
        if any(alias.upper() in v for alias in aliases):
            return key
    return venue


def _s2_headers() -> dict[str, str]:
    return {"x-api-key": _S2_API_KEY} if _S2_API_KEY else {}


def _s2_retriable(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in (429, 500, 503)
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


@retry(
    retry=retry_if_exception(_s2_retriable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
def _call_s2(params: dict[str, Any]) -> list[dict[str, Any]]:
    resp = requests.get(f"{_S2_BASE}/paper/search", params=params, headers=_s2_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _paper_from_s2(item: dict[str, Any]) -> dict[str, Any]:
    ext = item.get("externalIds") or {}
    pdf = item.get("openAccessPdf") or {}
    url = pdf.get("url") or (f"https://doi.org/{ext['DOI']}" if ext.get("DOI") else None)
    url = url or f"https://www.semanticscholar.org/paper/{item['paperId']}"
    source_ids = {
        "semantic_scholar": item.get("paperId"),
        "openalex": ext.get("OpenAlex"),
        "arxiv": ext.get("ArXiv"),
        "doi": ext.get("DOI"),
        "openreview": ext.get("OpenReview"),
    }
    return {
        "paper_id": item["paperId"],
        "source": "semantic_scholar",
        "source_ids": source_ids,
        "title": item.get("title") or "",
        "abstract": item.get("abstract"),
        "summary": None,
        "title_vi": None,
        "authors": [
            {"name": a.get("name", ""), "author_id": a.get("authorId")}
            for a in (item.get("authors") or [])
        ],
        "year": item.get("year"),
        "venue": item.get("venue") or "",
        "conference": normalize_venue(item.get("venue")),
        "url": url,
        "pdf_url": pdf.get("url") or None,
        "citation_count": item.get("citationCount"),
        "relevance_score": None,
        "rank_score": None,
        "quality_signals": {
            "matched_filters": [],
            "source_count": 1,
            "has_pdf": bool(pdf.get("url")),
        },
        "why_recommended": None,
        "key_contributions": [],
        "tags": [],
    }


def _paper_from_model(paper: Paper) -> dict[str, Any]:
    source_ids = {
        "semantic_scholar": None,
        "openalex": paper.id if paper.source == "openalex" else None,
        "arxiv": paper.id if paper.source == "arxiv" else None,
        "doi": paper.doi,
        "openreview": paper.id if paper.source == "openreview" else None,
    }
    pdf_url = arxiv_pdf_url(paper.id) if paper.source == "arxiv" and paper.id else None
    return {
        "paper_id": paper.id or paper.doi or paper.url or paper.title,
        "source": paper.source,
        "source_ids": source_ids,
        "title": paper.title or "",
        "abstract": paper.abstract,
        "summary": None,
        "title_vi": None,
        "authors": [{"name": a} for a in paper.authors],
        "year": paper.year,
        "venue": paper.venue or "",
        "conference": normalize_venue(paper.venue),
        "url": paper.url,
        "pdf_url": pdf_url,
        "citation_count": None,
        "relevance_score": None,
        "rank_score": None,
        "quality_signals": {
            "matched_filters": [],
            "source_count": 1,
            "has_pdf": bool(pdf_url),
        },
        "why_recommended": None,
        "key_contributions": [],
        "tags": list(paper.keywords),
    }


def score_and_rank(query: str, papers: list[dict[str, Any]], *, cfg: Config) -> list[dict[str, Any]]:
    """Compute embedding relevance, then sort by blended rank_score."""
    texts = [f"{p.get('title', '')}. {(p.get('abstract') or '')[:500]}" for p in papers]
    try:
        provider = cfg.llm_provider
        model = "text-embedding-3-small" if provider == "openai" else "gemini-embedding-001"
        base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url
        scores = score_batch(query=query, texts=texts, provider=provider, model=model, base_url=base_url)
        for paper, score in zip(papers, scores):
            paper["relevance_score"] = round(score, 4)
    except Exception:
        pass  # embedding failed — keep papers as-is with relevance_score=None

    for paper in papers:
        paper["rank_score"] = _rank_score(paper)
        paper["why_recommended"] = _why_recommended(paper)

    papers.sort(key=lambda p: p.get("rank_score") or p.get("relevance_score") or 0, reverse=True)
    return papers


def _rank_score(paper: dict[str, Any]) -> float:
    relevance = float(paper.get("relevance_score") or 0)
    current_year = datetime.datetime.now().year
    try:
        year = int(paper.get("year") or 0)
        recency = max(0.0, 1.0 - min(max(current_year - year, 0), 10) / 10)
    except Exception:
        recency = 0.0
    try:
        citations = min(1.0, math.log10(max(int(paper.get("citation_count") or 0), 0) + 1) / 4)
    except Exception:
        citations = 0.0
    quality = paper.get("quality_signals") or {}
    filter_match = 1.0 if quality.get("matched_filters") else 0.0
    source_quality = 0.0
    if quality.get("has_pdf"):
        source_quality += 0.5
    source_quality += min(0.5, 0.15 * int(quality.get("source_count") or 1))
    score = 0.65 * relevance + 0.15 * recency + 0.10 * citations + 0.05 * filter_match + 0.05 * source_quality
    return round(score, 4)


def _why_recommended(paper: dict[str, Any]) -> str:
    bits = []
    if paper.get("relevance_score") is not None:
        bits.append("strong abstract/title match")
    if (paper.get("quality_signals") or {}).get("matched_filters"):
        bits.append("matches requested filters")
    if paper.get("pdf_url"):
        bits.append("has an open PDF")
    if paper.get("citation_count"):
        bits.append("has citation signal")
    if not bits:
        bits.append("matches the search query metadata")
    return "Recommended because it " + ", ".join(bits[:3]) + "."


def _enrich_citation_counts(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best-effort: batch-lookup citation counts from S2 for papers that lack them."""
    missing_idx = [i for i, p in enumerate(papers) if p.get("citation_count") is None]
    if not missing_idx:
        return papers

    ids = [papers[i]["paper_id"] for i in missing_idx if papers[i].get("paper_id")]
    if not ids:
        return papers

    try:
        resp = requests.post(
            f"{_S2_BASE}/paper/batch",
            headers=_s2_headers(),
            params={"fields": "paperId,citationCount"},
            json={"ids": ids[:100]},
            timeout=15,
        )
        if not resp.ok:
            return papers
        batch: list[dict[str, Any]] = resp.json()
        cite_map: dict[str, int] = {}
        for item in batch:
            if item and item.get("paperId") and item.get("citationCount") is not None:
                cite_map[item["paperId"]] = item["citationCount"]
        for i in missing_idx:
            pid = papers[i].get("paper_id", "")
            if pid in cite_map:
                papers[i] = {**papers[i], "citation_count": cite_map[pid]}
    except Exception:
        pass

    return papers


def _search_fallback(query: str, params: SearchParams) -> list[dict[str, Any]]:
    """Fallback: search OpenReview across recent major conferences."""
    current_year = datetime.datetime.now().year
    venue_keys = [c.lower() for c in params.conferences] if params.conferences else ["iclr", "neurips", "icml"]
    if params.year_from or params.year_to:
        y_start = params.year_from or current_year - 3
        y_end = params.year_to or current_year
        years = list(range(y_start, y_end + 1))
    else:
        years = [current_year, current_year - 1]

    def _fetch_one(venue_key: str, year: int) -> list:
        try:
            return search_papers(query=query, venue_key=venue_key, year=year, limit=params.limit * 2, accepted_only=True)
        except Exception:
            return []

    tasks = [(v, y) for v in venue_keys for y in sorted(years, reverse=True)]
    all_raw: list = []
    with ThreadPoolExecutor(max_workers=min(len(tasks), 3)) as pool:
        futures = [pool.submit(_fetch_one, v, y) for v, y in tasks]
        for f in as_completed(futures):
            all_raw.extend(f.result())

    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for p in all_raw:
        if not p.abstract:
            continue
        key = p.id or p.title
        if key in seen:
            continue
        seen.add(key)
        venue = p.venue or ""
        conference = normalize_venue(venue) or (p.id or "").split("/")[0].upper()
        papers.append({
            "paper_id": p.id or "",
            "source": "openreview",
            "source_ids": {
                "semantic_scholar": None,
                "openalex": None,
                "arxiv": None,
                "doi": None,
                "openreview": p.id or None,
            },
            "title": p.title,
            "abstract": p.abstract,
            "summary": None,
            "title_vi": None,
            "authors": [{"name": a} for a in p.authors],
            "year": p.year,
            "venue": venue,
            "conference": conference,
            "url": p.url,
            "pdf_url": f"https://openreview.net/pdf?id={p.id}" if p.id else None,
            "citation_count": None,
            "relevance_score": None,
            "rank_score": None,
            "quality_signals": {
                "matched_filters": [],
                "source_count": 1,
                "has_pdf": bool(p.id),
            },
            "why_recommended": None,
            "key_contributions": [],
            "tags": list(p.keywords),
        })
        if len(papers) >= params.limit:
            break
    return _enrich_citation_counts(papers)


def _build_s2_params(query: str, params: SearchParams, batch_limit: int, *, relax_filters: bool = False) -> dict[str, Any]:
    """Build S2 search params dict for a given query string."""
    s2_params: dict[str, Any] = {
        "query": query,
        "fields": _S2_FIELDS,
        "limit": batch_limit,
        "offset": params.offset,
    }
    if relax_filters:
        return s2_params
    if params.year_from is not None and params.year_to is not None:
        s2_params["year"] = f"{params.year_from}-{params.year_to}"
    elif params.year_from is not None:
        s2_params["year"] = f"{params.year_from}-"
    elif params.year_to is not None:
        s2_params["year"] = f"-{params.year_to}"
    if len(params.conferences) == 1:
        aliases = _CONF_VENUE_ALIASES.get(params.conferences[0], [params.conferences[0]])
        s2_params["venue"] = ",".join(aliases)
    return s2_params


def _collect_from_raw(
    raw: list[dict[str, Any]],
    params: SearchParams,
    seen_ids: set[str],
    papers: list[dict[str, Any]],
    limit: int,
    *,
    relax_filters: bool = False,
) -> None:
    """Filter and append papers from a S2 raw response, deduplicating by paper_id."""
    for item in raw:
        if len(papers) >= limit:
            break
        if not item.get("abstract"):
            continue
        p = _paper_from_s2(item)
        if not relax_filters and params.conferences and p["conference"] not in params.conferences:
            continue
        pid = p["paper_id"]
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        papers.append(p)


def _title_key(title: str | None, year: Any = None) -> str | None:
    if not title:
        return None
    normalized = _NON_ALNUM_RE.sub(" ", title.lower()).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    if not normalized:
        return None
    return f"title:{normalized}:{year or ''}"


def _canonical_keys(paper: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    source_ids = paper.get("source_ids") or {}
    if isinstance(source_ids, dict):
        for label in ("doi", "arxiv", "semantic_scholar", "openalex", "openreview"):
            value = source_ids.get(label)
            if value:
                keys.append(f"{label}:{str(value).lower()}")
    for label in ("doi", "paper_id", "url"):
        value = paper.get(label)
        if value:
            keys.append(f"{label}:{str(value).lower()}")
    title_key = _title_key(paper.get("title"), paper.get("year"))
    if title_key:
        keys.append(title_key)
    return keys


def _merge_papers(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for field in ("abstract", "url", "pdf_url", "venue", "conference", "year", "citation_count"):
        if not merged.get(field) and incoming.get(field):
            merged[field] = incoming[field]

    existing_ids = dict(merged.get("source_ids") or {})
    incoming_ids = incoming.get("source_ids") or {}
    if isinstance(incoming_ids, dict):
        for key, value in incoming_ids.items():
            if value and not existing_ids.get(key):
                existing_ids[key] = value
    merged["source_ids"] = existing_ids

    existing_authors = merged.get("authors") or []
    names = {a.get("name") for a in existing_authors if isinstance(a, dict)}
    for author in incoming.get("authors") or []:
        name = author.get("name") if isinstance(author, dict) else str(author)
        if name and name not in names:
            existing_authors.append({"name": name})
            names.add(name)
    merged["authors"] = existing_authors

    existing_tags = set(merged.get("tags") or [])
    for tag in incoming.get("tags") or []:
        if tag not in existing_tags:
            merged.setdefault("tags", []).append(tag)
            existing_tags.add(tag)

    quality = dict(merged.get("quality_signals") or {})
    incoming_quality = incoming.get("quality_signals") or {}
    sources = {merged.get("source"), incoming.get("source")}
    ids = merged.get("source_ids") or {}
    sources.update(k for k, v in ids.items() if v)
    quality["source_count"] = max(int(quality.get("source_count") or 1), len([s for s in sources if s]))
    quality["has_pdf"] = bool(merged.get("pdf_url") or incoming.get("pdf_url") or quality.get("has_pdf") or incoming_quality.get("has_pdf"))
    matched = list(dict.fromkeys((quality.get("matched_filters") or []) + (incoming_quality.get("matched_filters") or [])))
    quality["matched_filters"] = matched
    merged["quality_signals"] = quality
    return merged


def _dedupe_merged(papers: list[dict[str, Any]], seen_ids: set[str] | None = None) -> list[dict[str, Any]]:
    seen_ids = seen_ids or set()
    key_to_idx: dict[str, int] = {}
    merged: list[dict[str, Any]] = []
    for paper in papers:
        keys = _canonical_keys(paper)
        idx = next((key_to_idx[k] for k in keys if k in key_to_idx), None)
        if idx is not None:
            merged[idx] = _merge_papers(merged[idx], paper)
            continue
        pid = paper.get("paper_id")
        if pid in seen_ids:
            continue
        if pid:
            seen_ids.add(pid)
        key_idx = len(merged)
        for key in keys:
            key_to_idx[key] = key_idx
        merged.append(paper)
    return merged


def _matches_filters(paper: dict[str, Any], params: SearchParams) -> bool:
    year = paper.get("year")
    if params.year_from is not None and year is not None and int(year) < params.year_from:
        return False
    if params.year_to is not None and year is not None and int(year) > params.year_to:
        return False
    if params.conferences:
        conference = normalize_venue(paper.get("conference") or paper.get("venue"))
        if conference not in params.conferences:
            return False
        paper["conference"] = conference
    return True


def _mark_matched_filters(paper: dict[str, Any], params: SearchParams) -> None:
    matched: list[str] = []
    if params.year_from is not None or params.year_to is not None:
        matched.append("year")
    if params.conferences and normalize_venue(paper.get("conference") or paper.get("venue")) in params.conferences:
        matched.append("venue")
    quality = dict(paper.get("quality_signals") or {})
    quality["matched_filters"] = matched
    quality["has_pdf"] = bool(paper.get("pdf_url") or quality.get("has_pdf"))
    quality["source_count"] = int(quality.get("source_count") or 1)
    paper["quality_signals"] = quality


def _filter_and_finalize(papers: list[dict[str, Any]], params: SearchParams, seen_ids: set[str] | None = None) -> list[dict[str, Any]]:
    filtered = []
    for paper in papers:
        if not paper.get("abstract"):
            continue
        if not _matches_filters(paper, params):
            continue
        _mark_matched_filters(paper, params)
        filtered.append(paper)
    return _dedupe_merged(filtered, seen_ids)


def search_multi_source(
    primary_query: str,
    variant_queries: list[str],
    params: SearchParams,
    seen_ids: set[str],
    *,
    limit: int,
    batch_limit: int | None = None,
    relax_filters: bool = False,
    openalex_email: str | None = None,
) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
    """Run one search round: primary S2 query (fallback to OpenReview on 429)
    + variant queries fanned out in parallel. Mutates *seen_ids* in place so
    repeated rounds in the sufficiency loop don't re-collect the same papers.
    Returns (new_papers_this_round, has_more, source_stats).
    """
    batch_limit = batch_limit or min(limit * 3, 100)
    sources = route_sources(params)
    stats: dict[str, Any] = {
        "sources": {s: {"attempted": False, "count": 0, "error": None} for s in sources},
        "routed_sources": sources,
    }
    papers: list[dict[str, Any]] = []

    primary_raw: list[dict[str, Any]] = []
    has_more = False
    if "semantic_scholar" in sources:
        stats["sources"]["semantic_scholar"]["attempted"] = True
        try:
            primary_raw = _call_s2(_build_s2_params(primary_query, params, batch_limit, relax_filters=relax_filters))
            _collect_from_raw(primary_raw, params, seen_ids, papers, batch_limit, relax_filters=relax_filters)
            has_more = len(primary_raw) >= batch_limit
            stats["sources"]["semantic_scholar"]["count"] = len(primary_raw)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            stats["sources"]["semantic_scholar"]["error"] = f"http_{status}"
            if status == 429 and "openreview" not in sources:
                sources.append("openreview")
                stats["sources"]["openreview"] = {"attempted": False, "count": 0, "error": None}
            elif status != 429:
                raise
        except requests.RequestException:
            stats["sources"]["semantic_scholar"]["error"] = "request_error"
            raise

    if "semantic_scholar" in sources and variant_queries and len(papers) < limit:
        variant_params = [_build_s2_params(q, params, batch_limit, relax_filters=relax_filters) for q in variant_queries]
        with ThreadPoolExecutor(max_workers=len(variant_params)) as pool:
            futures = {pool.submit(_call_s2, p): p for p in variant_params}
            for future in as_completed(futures):
                if len(papers) >= limit:
                    break
                try:
                    raw = future.result()
                    _collect_from_raw(raw, params, seen_ids, papers, batch_limit, relax_filters=relax_filters)
                except Exception:
                    pass  # variant failure is non-critical

    if "openreview" in sources and len(papers) < batch_limit:
        stats["sources"]["openreview"]["attempted"] = True
        try:
            fallback = _search_fallback(primary_query, params)
            stats["sources"]["openreview"]["count"] = len(fallback)
            papers.extend(fallback)
        except Exception as exc:
            stats["sources"]["openreview"]["error"] = exc.__class__.__name__

    if "openalex" in sources and len(papers) < batch_limit:
        stats["sources"]["openalex"]["attempted"] = True
        try:
            year = params.year_from if params.year_from == params.year_to else None
            venue = params.conferences[0] if len(params.conferences) == 1 else None
            raw_openalex = search_openalex(
                query=primary_query,
                venue=venue,
                year=year,
                limit=max(5, min(batch_limit, limit * 2)),
                email=openalex_email,
            )
            openalex_papers = [_paper_from_model(p) for p in raw_openalex if p.abstract]
            stats["sources"]["openalex"]["count"] = len(openalex_papers)
            papers.extend(openalex_papers)
        except Exception as exc:
            stats["sources"]["openalex"]["error"] = exc.__class__.__name__

    if "arxiv" in sources and len(papers) < batch_limit:
        stats["sources"]["arxiv"]["attempted"] = True
        try:
            raw_arxiv = search_arxiv(query=primary_query, max_results=max(5, min(batch_limit, limit * 2)))
            arxiv_papers = [_paper_from_model(p) for p in raw_arxiv if p.abstract]
            stats["sources"]["arxiv"]["count"] = len(arxiv_papers)
            papers.extend(arxiv_papers)
        except Exception as exc:
            stats["sources"]["arxiv"]["error"] = exc.__class__.__name__

    papers = _filter_and_finalize(papers, params, seen_ids if "semantic_scholar" not in sources else set())
    for p in papers:
        if p.get("paper_id"):
            seen_ids.add(p["paper_id"])
    return papers, has_more, stats


def dedupe(papers: list[dict[str, Any]], seen_ids: set[str]) -> tuple[list[dict[str, Any]], set[str]]:
    """Deduplicate by DOI/arXiv/source ids/title-year, merging metadata."""
    new_papers = _dedupe_merged(papers, seen_ids)
    for p in new_papers:
        if p.get("paper_id"):
            seen_ids.add(p["paper_id"])
    return new_papers, seen_ids


def is_sufficient(state: SearchState, *, min_good: int = 5, relevance_threshold: float = 0.35) -> bool:
    """True iff at least *min_good* selected papers clear the relevance threshold."""
    count = sum(1 for p in state.selected if (p.get("relevance_score") or 0) >= relevance_threshold)
    return count >= min_good


def stopping_reason(
    state: SearchState, max_iterations: int, new_unique_count: int
) -> Literal["sufficient", "max_iterations", "diminishing_returns"] | None:
    if is_sufficient(state):
        return "sufficient"
    if state.iteration + 1 >= max_iterations:
        return "max_iterations"
    if state.iteration > 0 and new_unique_count == 0:
        return "diminishing_returns"
    return None


def rewrite_query(params: SearchParams, strategy: Literal["expand", "narrow", "reangle"], iteration: int) -> list[str]:
    """Pure heuristic over parse_query()'s already-returned keyword_variants —
    no extra LLM round-trip per loop iteration.
    """
    variants = [v for v in params.keyword_variants if v]
    if strategy == "expand":
        if variants:
            return [f"{params.query} {variants[0]}"]
        return [params.query]
    if strategy == "narrow":
        return [params.query]
    # reangle
    if variants:
        return [variants[iteration % len(variants)]]
    return [params.query]
