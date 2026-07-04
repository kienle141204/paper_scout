"""Supabase Storage cache for paper PDFs (bucket `paper_pdfs`).

Shared, community-wide PDF cache keyed by paper_id — the file counterpart to
`paper_cache` (text) and `paper_chunks` (vectors). One download serves both the
Reader's <iframe> and RAG ingest, and survives the source going offline / gating
anonymous access (e.g. OpenReview).

Fail-soft everywhere: if Supabase is unreachable or the object is missing, every
function returns None / False and the caller falls back to a live fetch. Uses the
publishable (anon) key via shared_supabase; the bucket is public-read with an
anon insert/update policy (see supabase_migration.sql).
"""
from __future__ import annotations

import hashlib
import logging
import re
import threading

import requests

from agent.tools.shared_supabase import (
    PDF_BUCKET,
    get_supabase_anon_key,
    get_supabase_url,
)

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client_obj = None
_client_ready = False

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _get_client():
    global _client_obj, _client_ready
    if _client_ready:
        return _client_obj
    with _lock:
        if _client_ready:
            return _client_obj
        url = get_supabase_url()
        key = get_supabase_anon_key()
        if url and key:
            try:
                from supabase import create_client
                _client_obj = create_client(url, key)
            except Exception:
                # Transient (lib import / network blip). Don't cache None — retry next call.
                _client_obj = None
                return None
        _client_ready = True
    return _client_obj


def is_configured() -> bool:
    return _get_client() is not None


def _object_key(paper_id: str) -> str:
    """Storage key for a paper_id. Sanitised + short hash so arbitrary ids
    (arXiv, S2 hex, OpenReview, even a URL used as id) map to one safe, stable,
    collision-resistant object name."""
    digest = hashlib.sha1(paper_id.encode("utf-8")).hexdigest()[:10]
    slug = _SAFE.sub("_", paper_id).strip("_")[:60] or "paper"
    return f"{slug}_{digest}.pdf"


def public_url(paper_id: str) -> str:
    """Deterministic public URL for a paper's cached PDF (may not exist yet)."""
    base = get_supabase_url().rstrip("/")
    return f"{base}/storage/v1/object/public/{PDF_BUCKET}/{_object_key(paper_id)}"


def cached_pdf_url(paper_id: str) -> str | None:
    """Public URL if the PDF is already cached, else None. Cheap HEAD probe."""
    if not paper_id:
        return None
    url = public_url(paper_id)
    try:
        r = requests.head(url, timeout=8, allow_redirects=True)
        if r.status_code == 200:
            return url
    except Exception:
        pass
    return None


def store_pdf_bytes(paper_id: str, data: bytes) -> bool:
    """Upsert PDF bytes into the bucket. Returns True on success (best-effort)."""
    c = _get_client()
    if not c or not paper_id or not data:
        return False
    try:
        c.storage.from_(PDF_BUCKET).upload(
            _object_key(paper_id),
            data,
            {"content-type": "application/pdf", "upsert": "true"},
        )
        return True
    except Exception as e:
        logger.info("pdf_store: upload failed for %s: %s", paper_id, str(e)[:150])
        return False


def download_pdf(paper_id: str) -> bytes | None:
    """Return cached PDF bytes, or None if not cached / unavailable."""
    c = _get_client()
    if not c or not paper_id:
        return None
    try:
        data = c.storage.from_(PDF_BUCKET).download(_object_key(paper_id))
        return data if data and data[:4] == b"%PDF" else None
    except Exception:
        return None


def _json_object_key(paper_id: str) -> str:
    """Storage key for a paper's cached MinerU content_list.json (same bucket)."""
    digest = hashlib.sha1(paper_id.encode("utf-8")).hexdigest()[:10]
    slug = _SAFE.sub("_", paper_id).strip("_")[:60] or "paper"
    return f"{slug}_{digest}.content_list.json"


def store_parsed_json(paper_id: str, content_list: list | dict) -> bool:
    """Cache MinerU's content_list output so re-ingest skips the (slow) parse.
    Best-effort — returns True on success, False otherwise."""
    import json
    c = _get_client()
    if not c or not paper_id or content_list is None:
        return False
    try:
        payload = json.dumps(content_list).encode("utf-8")
        c.storage.from_(PDF_BUCKET).upload(
            _json_object_key(paper_id),
            payload,
            {"content-type": "application/json", "upsert": "true"},
        )
        return True
    except Exception as e:
        logger.info("pdf_store: parsed-json upload failed for %s: %s", paper_id, str(e)[:150])
        return False


def download_parsed_json(paper_id: str) -> list | None:
    """Return cached MinerU content_list (list of blocks), or None if not cached."""
    import json
    c = _get_client()
    if not c or not paper_id:
        return None
    try:
        data = c.storage.from_(PDF_BUCKET).download(_json_object_key(paper_id))
        if not data:
            return None
        parsed = json.loads(data.decode("utf-8"))
        return parsed if isinstance(parsed, list) else None
    except Exception:
        return None
