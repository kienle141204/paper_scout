from __future__ import annotations

from ..model import Paper
from .openalex_search import citing_openalex, related_openalex


def recommend_from_openalex(
    *,
    seed_work_id: str,
    limit: int = 25,
    openalex_email: str | None = None,
) -> dict[str, list[Paper]]:
    """
    Simple recommender:
    - related_to: OpenAlex's related works
    - citing: newer works that cite seed
    """
    rel = related_openalex(work_id=seed_work_id, limit=limit, email=openalex_email)
    citing = citing_openalex(work_id=seed_work_id, limit=limit, email=openalex_email)
    return {"related": rel, "citing": citing}

