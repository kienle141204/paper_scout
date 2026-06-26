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
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Literal

import requests
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from agent.config import Config
from agent.tools.paper_search import search_papers
from agent.tools.relevance import score_batch

from .state import SearchParams, SearchState

_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "paperId,title,abstract,authors,year,venue,externalIds,openAccessPdf,citationCount"
_S2_API_KEY: str = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")

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
    return {
        "paper_id": item["paperId"],
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
        "citation_count": item.get("citationCount"),
        "relevance_score": None,
        "key_contributions": [],
        "tags": [],
    }


def score_and_rank(query: str, papers: list[dict[str, Any]], *, cfg: Config) -> list[dict[str, Any]]:
    """Compute embedding-based relevance scores in one batched API call, then sort descending."""
    texts = [f"{p.get('title', '')}. {(p.get('abstract') or '')[:500]}" for p in papers]
    try:
        provider = cfg.llm_provider
        model = "text-embedding-3-small" if provider == "openai" else "gemini-embedding-001"
        base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url
        scores = score_batch(query=query, texts=texts, provider=provider, model=model, base_url=base_url)
        for paper, score in zip(papers, scores):
            paper["relevance_score"] = round(score, 4)
        papers.sort(key=lambda p: p.get("relevance_score") or 0, reverse=True)
    except Exception:
        pass  # embedding failed — keep papers as-is with relevance_score=None
    return papers


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
            "title": p.title,
            "abstract": p.abstract,
            "summary": None,
            "title_vi": None,
            "authors": [{"name": a} for a in p.authors],
            "year": p.year,
            "venue": venue,
            "conference": conference,
            "url": p.url,
            "citation_count": None,
            "relevance_score": None,
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


def search_multi_source(
    primary_query: str,
    variant_queries: list[str],
    params: SearchParams,
    seen_ids: set[str],
    *,
    limit: int,
    batch_limit: int | None = None,
    relax_filters: bool = False,
) -> tuple[list[dict[str, Any]], bool]:
    """Run one search round: primary S2 query (fallback to OpenReview on 429)
    + variant queries fanned out in parallel. Mutates *seen_ids* in place so
    repeated rounds in the sufficiency loop don't re-collect the same papers.
    Returns (new_papers_this_round, has_more).
    """
    batch_limit = batch_limit or min(limit * 3, 100)
    papers: list[dict[str, Any]] = []

    try:
        primary_raw = _call_s2(_build_s2_params(primary_query, params, batch_limit, relax_filters=relax_filters))
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            fallback = _search_fallback(primary_query, params)
            new_fallback = [p for p in fallback if p["paper_id"] not in seen_ids]
            for p in new_fallback:
                seen_ids.add(p["paper_id"])
            return new_fallback, len(new_fallback) >= limit
        raise
    except requests.RequestException:
        raise

    _collect_from_raw(primary_raw, params, seen_ids, papers, limit, relax_filters=relax_filters)
    has_more = len(primary_raw) >= batch_limit

    if variant_queries and len(papers) < limit:
        variant_params = [_build_s2_params(q, params, batch_limit, relax_filters=relax_filters) for q in variant_queries]
        with ThreadPoolExecutor(max_workers=len(variant_params)) as pool:
            futures = {pool.submit(_call_s2, p): p for p in variant_params}
            for future in as_completed(futures):
                if len(papers) >= limit:
                    break
                try:
                    _collect_from_raw(future.result(), params, seen_ids, papers, limit, relax_filters=relax_filters)
                except Exception:
                    pass  # variant failure is non-critical

    return papers, has_more


def dedupe(papers: list[dict[str, Any]], seen_ids: set[str]) -> tuple[list[dict[str, Any]], set[str]]:
    """Standalone dedup helper for callers that already have a raw paper list
    (search_multi_source already dedupes internally against seen_ids — this
    is for any additional merge step, e.g. combining sources outside the
    normal round flow).
    """
    new_papers = []
    for p in papers:
        pid = p.get("paper_id")
        if not pid or pid in seen_ids:
            continue
        seen_ids.add(pid)
        new_papers.append(p)
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
