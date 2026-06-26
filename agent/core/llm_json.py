"""Shared helper: call an LLM and best-effort extract a JSON object from its reply."""
from __future__ import annotations

import json
import re
from typing import Any

from agent.tools.llm_text import generate_text


def llm_json(
    system: str,
    user: str,
    *,
    provider: str,
    model: str,
    base_url: str | None,
    messages: list[dict] | None = None,
) -> dict[str, Any]:
    raw = generate_text(provider=provider, system=system, user=user, model=model, base_url=base_url, messages=messages)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except Exception:
            pass
    return {}
