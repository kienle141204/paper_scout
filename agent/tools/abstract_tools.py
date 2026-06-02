from __future__ import annotations

from .llm_text import generate_text
from .prompts import TRANSLATE_ABSTRACT, SUMMARIZE_ABSTRACT


def translate_abstract_vi(
    *,
    text: str,
    provider: str,
    model: str,
    base_url: str | None = None,
) -> str:
    return generate_text(
        provider=provider,
        system=TRANSLATE_ABSTRACT,
        user=text,
        model=model,
        base_url=base_url,
    )


def summarize_abstract(
    *,
    text: str,
    provider: str,
    model: str,
    base_url: str | None = None,
) -> str:
    return generate_text(
        provider=provider,
        system=SUMMARIZE_ABSTRACT,
        user=text,
        model=model,
        base_url=base_url,
    )
