from __future__ import annotations

import os
from typing import Any

import requests


def embed(
    *,
    text: str,
    model: str = "gemini-embedding-001",
    base_url: str = "https://generativelanguage.googleapis.com/v1beta",
) -> list[float]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    base = base_url.rstrip("/")
    url = f"{base}/models/{model}:embedContent"
    params = {"key": api_key}
    payload: dict[str, Any] = {"content": {"parts": [{"text": text}]}}
    resp = requests.post(url, params=params, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    vec = (data.get("embedding") or {}).get("values") or []
    return [float(x) for x in vec]

