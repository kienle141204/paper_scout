from __future__ import annotations

import os
from typing import Any

import requests


def generate_text(
    *,
    system: str,
    user: str,
    model: str,
    base_url: str = "https://generativelanguage.googleapis.com/v1beta",
    messages: list[dict[str, str]] | None = None,
) -> str:
    """Minimal Gemini REST wrapper via generateContent.

    Auth: GEMINI_API_KEY as query param ``key``.

    When *messages* is provided it is mapped to Gemini's ``contents`` format
    (``assistant`` role is mapped to ``model``).  When *messages* is None the
    single-turn ``user`` string is used — preserving backward compatibility.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing GEMINI_API_KEY")

    base = base_url.rstrip("/")
    url = f"{base}/models/{model}:generateContent"
    params = {"key": api_key}

    if messages is not None:
        # Map OpenAI-style roles to Gemini roles
        _role_map = {"user": "user", "assistant": "model"}
        contents = [
            {"role": _role_map.get(m["role"], m["role"]), "parts": [{"text": m["content"]}]}
            for m in messages
        ]
    else:
        contents = [{"role": "user", "parts": [{"text": user}]}]

    payload: dict[str, Any] = {
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": contents,
    }
    resp = requests.post(url, params=params, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    candidates = data.get("candidates") or []
    if not candidates:
        return ""
    content = (candidates[0] or {}).get("content") or {}
    parts = content.get("parts") or []
    texts = [p.get("text") for p in parts if isinstance(p, dict) and p.get("text")]
    return "\n".join(texts).strip()

