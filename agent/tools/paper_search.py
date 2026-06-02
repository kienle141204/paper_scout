from __future__ import annotations

from ..model import Paper
from .major_venues import major_search
from .openreview_search import OPENREVIEW_VENUES, fetch_openreview_papers


def search_papers(
    *,
    query: str,
    venue_key: str,
    year: int,
    limit: int = 10,
    offset: int = 0,
    accepted_only: bool = False,
) -> list[Paper]:
    """
    Tìm kiếm paper từ OpenReview theo venue và năm, có phân trang.

    Trả về tối đa limit+1 paper — nếu len(result) > limit thì còn trang tiếp.
    """
    return major_search(
        venue_key=venue_key,
        year=year,
        query=query,
        limit=limit,
        offset=offset,
        accepted_only=accepted_only,
    )


def search_by_invitation(
    *,
    invitation: str,
    query: str | None = None,
    limit: int = 10,
    offset: int = 0,
    accepted_only: bool = False,
) -> list[Paper]:
    """Tìm kiếm paper bằng invitation string OpenReview trực tiếp, có phân trang."""
    return fetch_openreview_papers(
        invitation=invitation,
        keyword=query,
        accepted_only=accepted_only,
        limit=limit,
        offset=offset,
    )


def list_supported_venues() -> list[str]:
    return sorted(OPENREVIEW_VENUES.keys())
