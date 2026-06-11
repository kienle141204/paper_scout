from __future__ import annotations

import re
import tempfile
from pathlib import Path

import requests

_ARXIV_ABS = re.compile(r"arxiv\.org/abs/(\d{4}\.\d{4,5}(?:v\d+)?)", re.I)
_ARXIV_PDF = re.compile(r"arxiv\.org/pdf/", re.I)
_OPENREVIEW = re.compile(r"openreview\.net", re.I)

_HEADERS = {"User-Agent": "PaperScout/1.0 (academic research tool; contact lekien.2004nek@gmail.com)"}


def _to_pdf_url(url: str) -> str:
    """Convert abstract/forum page URL to direct PDF URL where possible."""
    m = _ARXIV_ABS.search(url)
    if m:
        return f"https://arxiv.org/pdf/{m.group(1)}.pdf"
    if _OPENREVIEW.search(url) and "pdf" not in url.lower():
        # openreview.net/forum?id=XXX  →  openreview.net/pdf?id=XXX
        return re.sub(r"/forum", "/pdf", url)
    return url


def fetch_pdf(url: str, *, timeout: int = 60) -> Path | None:
    """Download a paper PDF from *url* to a temp file.

    Returns the local Path on success, None if the URL is inaccessible,
    redirects to non-PDF content, or any other error occurs.
    Caller is responsible for deleting the temp file.
    """
    if not url:
        return None
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
