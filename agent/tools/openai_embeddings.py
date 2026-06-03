from __future__ import annotations

import os
from typing import Any

import requests

_session = requests.Session()


def _api_key() -> str:
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return key


def embed(
    *,
    text: str,
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
) -> list[float]:
    return embed_batch(texts=[text], model=model, base_url=base_url)[0]


def embed_batch(
    *,
    texts: list[str],
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
) -> list[list[float]]:
    """Embed multiple texts in one API call. Returns embeddings in the same order."""
    if not texts:
        return []
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/embeddings"
    headers = {"Authorization": f"Bearer {_api_key()}", "Content-Type": "application/json"}
    payload: dict[str, Any] = {"model": model, "input": texts}
    resp = _session.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    # API returns list sorted by "index" field
    items = sorted(data.get("data") or [], key=lambda x: x.get("index", 0))
    return [[float(v) for v in (item.get("embedding") or [])] for item in items]

