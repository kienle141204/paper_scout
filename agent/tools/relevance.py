from __future__ import annotations

import math

from .gemini_embeddings import embed as gemini_embed
from .openai_embeddings import embed as openai_embed
from .openai_embeddings import embed_batch as openai_embed_batch


def cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def score_relevance(
    *,
    query: str,
    text: str,
    provider: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
) -> float:
    p = provider.lower().strip()
    if p == "openai":
        qv = openai_embed(text=query, model=model, base_url=base_url)
        tv = openai_embed(text=text, model=model, base_url=base_url)
    elif p == "gemini":
        qv = gemini_embed(text=query, model=model, base_url=base_url or "https://generativelanguage.googleapis.com/v1beta")
        tv = gemini_embed(text=text, model=model, base_url=base_url or "https://generativelanguage.googleapis.com/v1beta")
    else:
        raise ValueError(f"Unknown provider: {provider}")
    return cosine(qv, tv)


def score_batch(
    *,
    query: str,
    texts: list[str],
    provider: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
) -> list[float]:
    """Score all texts against the query in a single batch API call (OpenAI only).
    Falls back to per-item calls for Gemini. Returns cosine similarities in the same order as texts."""
    if not texts:
        return []

    p = provider.lower().strip()
    if p == "openai":
        all_vecs = openai_embed_batch(texts=[query] + texts, model=model, base_url=base_url)
        q_vec = all_vecs[0]
        return [cosine(q_vec, v) for v in all_vecs[1:]]

    if p == "gemini":
        base = base_url or "https://generativelanguage.googleapis.com/v1beta"
        q_vec = gemini_embed(text=query, model=model, base_url=base)
        return [cosine(q_vec, gemini_embed(text=t, model=model, base_url=base)) for t in texts]

    raise ValueError(f"Unknown provider: {provider}")
