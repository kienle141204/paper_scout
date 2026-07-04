from __future__ import annotations

import logging
import os
import re
import tempfile
import threading
import time
import unicodedata
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

# Cache of title → resolved arXiv PDF URL. Opening one paper triggers *two*
# concurrent resolutions (the Reader's PDF proxy + RAG ingest), and refreshes
# re-trigger them — caching dedupes those so we hit arXiv's flaky, rate-limited
# search API as little as possible. Positive hits are cached forever (arXiv URLs
# are stable); genuine "not on arXiv" misses get a short TTL so a paper that
# later appears can still be found. A per-title lock serialises concurrent
# lookups of the same title so the second waits for the first instead of
# doubling the arXiv load.
_ARXIV_CACHE: dict[str, str | None] = {}
_ARXIV_CACHE_EXPIRY: dict[str, float] = {}
_ARXIV_NEG_TTL = 600.0  # seconds to remember a genuine "not found" before retrying
_ARXIV_CACHE_LOCK = threading.Lock()
_ARXIV_TITLE_LOCKS: dict[str, threading.Lock] = {}

_ARXIV_ABS = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
_ARXIV_PDF = re.compile(r"arxiv\.org/pdf/", re.I)
_OPENREVIEW = re.compile(r"openreview\.net", re.I)

_HEADERS = {"User-Agent": "PaperScout/1.0 (academic research tool; contact lekien.2004nek@gmail.com)"}

# Punctuation-only stripper that KEEPS Unicode letters (so "Schrödinger" survives
# for the arXiv title query — arXiv indexes the diacritic and won't match "schrodinger").
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
# ASCII-folding stripper for the title-similarity check (lenient: ö→o, é→e).
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _ascii_fold(s: str) -> str:
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")


def _to_pdf_url(url: str) -> str:
    """Convert abstract/forum page URL to direct PDF URL where possible."""
    m = _ARXIV_ABS.search(url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
    if _OPENREVIEW.search(url) and "pdf" not in url.lower():
        # openreview.net/forum?id=XXX  →  openreview.net/pdf?id=XXX
        return re.sub(r"/forum", "/pdf", url)
    return url


def _title_tokens(title: str) -> set[str]:
    return {w for w in _NON_ALNUM_RE.sub(" ", _ascii_fold(title).lower()).split() if len(w) > 2}


def _titles_match(a: str, b: str, *, threshold: float = 0.8) -> bool:
    """True if two titles share enough significant tokens to be the same paper."""
    ta, tb = _title_tokens(a), _title_tokens(b)
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= threshold


def _fetch_pdf_direct(url: str, *, timeout: int) -> Path | None:
    """Download from a direct/derivable PDF URL, verifying the %PDF magic bytes."""
    pdf_url = _to_pdf_url(url)
    try:
        resp = requests.get(
            pdf_url,
            headers=_HEADERS,
            timeout=timeout,
            allow_redirects=True,
            stream=True,
        )
        resp.raise_for_status()

        # Read first 8 bytes to verify PDF magic number
        first_chunk = b""
        for data in resp.iter_content(chunk_size=8):
            first_chunk = data
            break
        if not first_chunk.startswith(b"%PDF"):
            return None

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
        tmp.write(first_chunk)
        for data in resp.iter_content(chunk_size=65536):
            tmp.write(data)
        tmp.close()
        return Path(tmp.name)
    except Exception:
        return None


def _cache_get(key: str) -> tuple[bool, str | None]:
    """Return (hit, value). A negative entry past its TTL counts as a miss."""
    with _ARXIV_CACHE_LOCK:
        if key not in _ARXIV_CACHE:
            return False, None
        value = _ARXIV_CACHE[key]
        if value is None:
            expiry = _ARXIV_CACHE_EXPIRY.get(key, 0.0)
            if time.monotonic() >= expiry:
                _ARXIV_CACHE.pop(key, None)
                _ARXIV_CACHE_EXPIRY.pop(key, None)
                return False, None
        return True, value


def _cache_put(key: str, value: str | None) -> None:
    with _ARXIV_CACHE_LOCK:
        _ARXIV_CACHE[key] = value
        if value is None:
            _ARXIV_CACHE_EXPIRY[key] = time.monotonic() + _ARXIV_NEG_TTL
        else:
            _ARXIV_CACHE_EXPIRY.pop(key, None)


def _title_lock(key: str) -> threading.Lock:
    with _ARXIV_CACHE_LOCK:
        lock = _ARXIV_TITLE_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _ARXIV_TITLE_LOCKS[key] = lock
        return lock


def _clean_title_for_query(title: str) -> str:
    # Strip only ASCII punctuation (e.g. a leading "SEGNO:") that would break
    # arXiv's `field:term` query syntax, but KEEP Unicode letters — arXiv indexes
    # diacritics, so folding "Schrödinger"→"schrodinger" makes the query miss.
    clean = _PUNCT_RE.sub(" ", title).strip()
    return re.sub(r"\s+", " ", clean)


def _resolve_pdf_by_title(
    title: str,
    namespace: str,
    query_fn: "callable[[str, str], tuple[str | None, bool]]",
) -> str | None:
    """Resolve a direct PDF URL for *title* via *query_fn*, cached + serialised.

    *namespace* keeps each source's results in a separate cache slot (so an arXiv
    miss doesn't shadow an OpenAlex hit). Serialised per (namespace, title) so the
    Reader's proxy call and the concurrent RAG-ingest call share one upstream
    lookup instead of each hammering a rate-limited search API."""
    clean_title = _clean_title_for_query(title)
    if not clean_title:
        return None

    cache_key = f"{namespace}:{clean_title.lower()}"
    hit, value = _cache_get(cache_key)
    if hit:
        return value

    with _title_lock(cache_key):
        hit, value = _cache_get(cache_key)  # re-check: the first waiter may have filled it
        if hit:
            return value
        resolved, errored = query_fn(title, clean_title)
        # Only cache a definitive result. On a transient upstream error (e.g.
        # rate-limit), leave the cache empty so the next attempt retries instead
        # of remembering a throttle-induced miss.
        if not errored:
            _cache_put(cache_key, resolved)
        return resolved


def _resolve_arxiv_pdf_url(title: str) -> str | None:
    """Look up a paper by title on arXiv and return its direct PDF URL if the
    top match's title is close enough to be the same paper."""
    return _resolve_pdf_by_title(title, "arxiv", _query_arxiv_pdf_url)


def _resolve_oa_pdf_url(title: str) -> str | None:
    """Look up a paper by title on other open-access aggregators (Semantic
    Scholar's openAccessPdf, then OpenAlex's OA location) and return a direct
    PDF URL for a close title match."""
    return _resolve_pdf_by_title(title, "oa", _query_oa_pdf_url)


def _resolve_fallback_pdf_url(title: str) -> str | None:
    """Best-effort open-access PDF for *title*, used when the primary source
    (e.g. OpenReview) blocks anonymous downloads. Tries arXiv first — fast, and
    its direct PDFs frame reliably — then broader OA aggregators."""
    return _resolve_arxiv_pdf_url(title) or _resolve_oa_pdf_url(title)


def _query_arxiv_pdf_url(title: str, clean_title: str) -> tuple[str | None, bool]:
    """Hit arXiv. Returns (pdf_url_or_None, errored) — *errored* is True when
    arXiv itself failed (rate-limited), distinct from a genuine no-match."""
    from agent.tools.arxiv import arxiv_pdf_url, search_arxiv

    def _first_match(query: str) -> str | None:
        results = search_arxiv(query=query, max_results=5)
        for paper in results:
            if paper.id and paper.title and _titles_match(title, paper.title):
                return arxiv_pdf_url(paper.id)
        return None

    # A title-field phrase query (`ti:"..."`) pins the search to the title, which
    # is far more precise than a full-text `all:` search — the latter buries the
    # real paper when the title contains common words (e.g. "MOMENT", "moment").
    try:
        hit = _first_match(f'ti:"{clean_title}"')
    except Exception:
        # arXiv errored (typically rate-limited even after retries). Don't pile on
        # a second `all:` query that would just hit the same throttle — bail out.
        return None, True
    if hit:
        return hit, False

    # `ti:` ran but found no confident match — retry once with a broader `all:` query.
    try:
        return _first_match(clean_title), False
    except Exception:
        return None, True


_S2_API_KEY = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")


def _s2_openaccess_pdf(title: str, clean_title: str) -> tuple[str | None, bool]:
    """Semantic Scholar `openAccessPdf` by title. Returns (pdf_url_or_None,
    errored). Sends the API key when configured so we don't get 429'd — the
    anonymous S2 tier rate-limits aggressively."""
    headers = dict(_HEADERS)
    if _S2_API_KEY:
        headers["x-api-key"] = _S2_API_KEY
    try:
        resp = requests.get(
            "https://api.semanticscholar.org/graph/v1/paper/search",
            params={"query": clean_title, "limit": 5, "fields": "title,openAccessPdf"},
            headers=headers,
            timeout=30,
        )
        if resp.status_code == 429:
            return None, True
        resp.raise_for_status()
    except Exception:
        return None, True
    for item in resp.json().get("data") or []:
        oa = item.get("openAccessPdf") or {}
        url = oa.get("url")
        if url and item.get("title") and _titles_match(title, item["title"]):
            return url, False
    return None, False


def _openalex_oa_pdf(title: str, clean_title: str) -> tuple[str | None, bool]:
    """OpenAlex best/primary open-access location by title. Returns
    (pdf_url_or_None, errored). `pdf_url` is a direct-PDF field, so it frames
    through the proxy like arXiv does."""
    params: dict[str, object] = {"search": clean_title, "per-page": 5}
    email = os.environ.get("OPENALEX_EMAIL", "").strip()
    if email:
        params["mailto"] = email
    try:
        resp = requests.get(
            "https://api.openalex.org/works", params=params, headers=_HEADERS, timeout=30
        )
        resp.raise_for_status()
    except Exception:
        return None, True
    for work in resp.json().get("results") or []:
        wtitle = work.get("title") or ""
        if not _titles_match(title, wtitle):
            continue
        for loc_key in ("best_oa_location", "primary_location"):
            loc = work.get(loc_key) or {}
            url = loc.get("pdf_url")
            if url:
                return url, False
    return None, False


def _query_oa_pdf_url(title: str, clean_title: str) -> tuple[str | None, bool]:
    """Locate an open-access direct PDF for *title* from sources other than
    arXiv — Semantic Scholar first, then OpenAlex. Returns (pdf_url_or_None,
    errored); *errored* is True only when a source failed transiently and none
    matched, so the caller retries instead of caching a throttle-induced miss."""
    url, s2_err = _s2_openaccess_pdf(title, clean_title)
    if url:
        return url, False
    url, oa_err = _openalex_oa_pdf(title, clean_title)
    if url:
        return url, False
    return None, (s2_err or oa_err)


def fetch_pdf(url: str, *, title: str | None = None, timeout: int = 60) -> Path | None:
    """Download a paper PDF from *url* to a temp file.

    Tries the direct URL first. If that fails (e.g. OpenReview now gates
    anonymous PDF downloads behind challenge verification → HTTP 403) and a
    *title* is provided, falls back to locating an open-access copy on arXiv.

    Returns the local Path on success, None if no valid PDF could be fetched.
    Caller is responsible for deleting the temp file.
    """
    if not url and not title:
        return None

    if url:
        path = _fetch_pdf_direct(url, timeout=timeout)
        if path:
            return path

    # Fallback: the primary source failed — try to find an open-access PDF by
    # title (arXiv, then Semantic Scholar / OpenAlex).
    if title:
        oa_url = _resolve_fallback_pdf_url(title)
        if oa_url:
            logger.info("Primary PDF fetch failed for %r; using open-access fallback %s", url, oa_url)
            return _fetch_pdf_direct(oa_url, timeout=timeout)

    return None


def resolve_embeddable_url(url: str | None, title: str | None = None) -> str | None:
    """Return a PDF URL the frontend can embed in an <iframe> (via our proxy), or
    None if no embeddable copy exists.

    OpenReview blocks both anonymous server-side fetch (403 challenge) *and*
    cross-origin framing, so for OpenReview links the only embeddable option is
    an open-access copy found by title (arXiv → Semantic Scholar → OpenAlex).
    Every other source (arXiv, ACL Anthology, S2 open-access PDFs…) is returned
    as-is — the proxy fetches it and it frames.

    Lets the Reader decide up-front whether to embed the PDF or fall back to the
    reading view, instead of dumping a raw 404 JSON body inside the iframe."""
    if url and not _OPENREVIEW.search(url):
        return url
    if title:
        oa_url = _resolve_fallback_pdf_url(title)
        if oa_url:
            return oa_url
    return None
