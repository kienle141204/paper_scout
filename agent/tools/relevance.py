from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from functools import lru_cache

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


@lru_cache(maxsize=4096)
def _embed_single_cached(text: str, model: str, provider: str, base_url: str | None) -> tuple[float, ...]:
    """Cached single-text embedding — avoids re-embedding the same abstract across requests."""
    if provider == "openai":
        return tuple(openai_embed(text=text, model=model, base_url=base_url))
    return tuple(gemini_embed(
        text=text, model=model,
        base_url=base_url or "https://generativelanguage.googleapis.com/v1beta",
    ))


def score_relevance(
    *,
    query: str,
    text: str,
    provider: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
) -> float:
    p = provider.lower().strip()
    qv = list(_embed_single_cached(query, model, p, base_url))
    tv = list(_embed_single_cached(text, model, p, base_url))
    return cosine(qv, tv)


def score_batch(
    *,
    query: str,
    texts: list[str],
    provider: str = "openai",
    model: str = "text-embedding-3-small",
    base_url: str | None = None,
) -> list[float]:
    """Score all texts against the query.

    OpenAI: single batch call (already optimal — 1 API round-trip for all texts).
    Gemini: parallel per-text calls via ThreadPoolExecutor + per-text LRU cache.
    """
    if not texts:
        return []

    p = provider.lower().strip()

    if p == "openai":
        all_vecs = openai_embed_batch(texts=[query] + texts, model=model, base_url=base_url)
        q_vec = all_vecs[0]
        return [cosine(q_vec, v) for v in all_vecs[1:]]

    if p == "gemini":
        base = base_url or "https://generativelanguage.googleapis.com/v1beta"
        all_texts = [query] + texts
        with ThreadPoolExecutor(max_workers=min(len(all_texts), 8)) as pool:
            all_vecs = list(pool.map(
                lambda t: list(_embed_single_cached(t, model, p, base)),
                all_texts,
            ))
        q_vec = all_vecs[0]
        return [cosine(q_vec, v) for v in all_vecs[1:]]

    raise ValueError(f"Unknown provider: {provider}")
