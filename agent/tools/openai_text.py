from __future__ import annotations

import os
from typing import Any

import requests


def _require_api_key() -> str:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Missing OPENAI_API_KEY")
    return api_key


def chat_complete(
    *,
    system: str,
    user: str,
    model: str,
    base_url: str | None = None,
    temperature: float = 0.2,
    messages: list[dict[str, str]] | None = None,
) -> str:
    """Call OpenAI chat completions.

    When *messages* is provided it is used as the full turn history (each item
    must have ``role`` and ``content`` keys).  The *system* prompt is still
    prepended as the first message.  When *messages* is None the single-turn
    ``user`` string is used instead — preserving backward compatibility.
    """
    api_key = _require_api_key()
    base = (base_url or "https://api.openai.com/v1").rstrip("/")
    url = f"{base}/chat/completions"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    if messages is not None:
        turn_messages = [{"role": "system", "content": system}, *messages]
    else:
        turn_messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    payload: dict[str, Any] = {
        "model": model,
        "messages": turn_messages,
        "temperature": temperature,
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    data = resp.json()
    return (data.get("choices", [{}])[0].get("message", {}) or {}).get("content", "").strip()

