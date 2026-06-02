from __future__ import annotations

from dataclasses import dataclass

from ..model import Paper
from .openreview_search import OPENREVIEW_VENUES, build_invitation, fetch_openreview_papers


@dataclass(frozen=True)
class MajorVenue:
    key: str
    display: str
    openreview_prefix: str


MAJOR_VENUES: dict[str, MajorVenue] = {
    key: MajorVenue(key=key, display=key.upper(), openreview_prefix=prefix)
    for key, prefix in OPENREVIEW_VENUES.items()
}

# Override display name cho một số venue
MAJOR_VENUES["neurips"] = MajorVenue(key="neurips", display="NeurIPS", openreview_prefix="NeurIPS.cc")
MAJOR_VENUES["emnlp"]   = MajorVenue(key="emnlp",   display="EMNLP",   openreview_prefix="EMNLP")


def major_search(
    *,
    venue_key: str,
    year: int | None = None,
    query: str,
    limit: int = 10,
    offset: int = 0,
    accepted_only: bool = False,
    openalex_email: str | None = None,  # ignored, backward compat
) -> list[Paper]:
    """
    Tìm kiếm paper từ hội nghị lớn qua OpenReview.

    Args:
        venue_key: 'iclr' | 'neurips' | 'icml' | 'colm' | 'emnlp'
        year: năm hội nghị, ví dụ 2024
        query: từ khóa tìm kiếm
        limit: số kết quả tối đa
        accepted_only: chỉ lấy paper được chấp nhận
    """
    import datetime

    venue = MAJOR_VENUES.get(venue_key.lower().strip())
    if not venue:
        raise ValueError(
            f"Venue '{venue_key}' không hỗ trợ. "
            f"Các venue có sẵn: {', '.join(sorted(MAJOR_VENUES))}"
        )

    resolved_year = year if year is not None else datetime.datetime.now().year
    invitation = build_invitation(venue_key=venue_key, year=resolved_year)
    return fetch_openreview_papers(
        invitation=invitation,
        keyword=query or None,
        accepted_only=accepted_only,
        limit=limit,
        offset=offset,
    )
