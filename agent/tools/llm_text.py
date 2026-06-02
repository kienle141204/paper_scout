from __future__ import annotations

from .gemini_text import generate_text as gemini_generate_text
from .openai_text import chat_complete as openai_chat_complete


def generate_text(
    *,
    provider: str,
    system: str,
    user: str,
    model: str,
    base_url: str | None = None,
    messages: list[dict[str, str]] | None = None,
) -> str:
    """Route an LLM text generation call to the configured provider.

    Pass *messages* for multi-turn conversations (list of
    ``{"role": "user"|"assistant", "content": "..."}`` dicts).  When
    *messages* is None the call falls back to the single-turn *user* string,
    preserving full backward compatibility with all existing call sites.
    """
    p = provider.lower().strip()
    if p == "openai":
        return openai_chat_complete(
            system=system, user=user, model=model, base_url=base_url, messages=messages
        )
    if p == "gemini":
        return gemini_generate_text(
            system=system,
            user=user,
            model=model,
            base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
            messages=messages,
        )
    raise ValueError(f"Unknown provider: {provider}")

