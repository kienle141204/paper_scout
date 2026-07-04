from __future__ import annotations

import logging
import re
import time
from types import SimpleNamespace
from typing import Any

import requests

from ..model import Paper

logger = logging.getLogger(__name__)

_RATE_LIMIT_WAIT   = 10    # seconds to wait on 429 before retrying
_MAX_RETRIES       = 3


OPENREVIEW_BASE_URL = "https://api2.openreview.net"

OPENREVIEW_VENUES: dict[str, str] = {
    "iclr":    "ICLR.cc",
    "neurips": "NeurIPS.cc",
    "icml":    "ICML.cc",
    "colm":    "COLM.cc",
    "emnlp":   "EMNLP",
}


def _val(field: Any) -> Any:
    """API v2 trả content dạng {'value': ...}, hàm này extract giá trị thực."""
    if isinstance(field, dict):
        return field.get("value")
    return field


def _search_notes_http(term: str, venueid: str | None, *, limit: int, offset: int) -> list[Any]:
    """Gọi endpoint `/notes/search` (còn cho phép anonymous — khác `/notes` đã bị
    chặn bằng challenge verification). Trả về list SimpleNamespace giống get_notes.

    - `term`: từ khóa (bắt buộc, endpoint 400 nếu rỗng) — server-side relevance match.
    - `venueid`: ví dụ 'ICLR.cc/2024/Conference' để giới hạn về đúng venue+năm.
      venueid dạng '.../Conference' chỉ chứa paper đã được nhận (accepted).
    """
    params: dict[str, Any] = {
        "term": term,
        "content": "all",
        "group": "all",
        "source": "all",
        "limit": limit,
        "offset": offset,
    }
    if venueid:
        params["venueid"] = venueid
    resp = requests.get(f"{OPENREVIEW_BASE_URL}/notes/search", params=params, timeout=30)
    resp.raise_for_status()
    payload = resp.json()
    notes = payload.get("notes") or payload.get("results") or []
    return [
        SimpleNamespace(
            id=note.get("id"),
            content=note.get("content") or {},
            invitation=note.get("invitation"),
            invitations=note.get("invitations"),
        )
        for note in notes
        if isinstance(note, dict)
    ]


def _search_with_retry(term: str, venueid: str | None, *, limit: int, offset: int) -> list[Any]:
    """Wrapper around `_search_notes_http` với retry khi bị rate-limit (HTTP 429)."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            return _search_notes_http(term, venueid, limit=limit, offset=offset)
        except Exception as exc:
            msg = str(exc)
            status_code = getattr(getattr(exc, "response", None), "status_code", None)
            if status_code == 429 or "429" in msg or "RateLimitError" in msg or "Too many requests" in msg:
                # Cố trích thời gian chờ từ message, nếu không lấy được dùng default
                wait = _RATE_LIMIT_WAIT
                m = re.search(r"try again in (\d+) second", msg, re.IGNORECASE)
                if m:
                    wait = int(m.group(1)) + 1
                if attempt < _MAX_RETRIES:
                    logger.warning("OpenReview rate-limit hit, waiting %ss (attempt %d/%d)…", wait, attempt, _MAX_RETRIES)
                    time.sleep(wait)
                    continue
            raise
    return []  # unreachable


def _note_to_paper(note: Any) -> Paper | None:
    content = getattr(note, "content", {}) or {}

    title = (_val(content.get("title")) or "").strip()
    if not title:
        return None

    abstract = (_val(content.get("abstract")) or "").strip() or None

    venueid = _val(content.get("venueid")) or ""
    venue = _val(content.get("venue")) or venueid or None
    if venue:
        venue = str(venue).strip() or None

    year: int | None = None
    try:
        year = int((_val(content.get("year")) or 0) or 0) or None
    except Exception:
        pass
    if year is None:
        for part in venueid.split("/"):
            if len(part) == 4 and part.isdigit():
                year = int(part)
                break

    authors_raw = _val(content.get("authors")) or []
    authors = tuple(str(a) for a in authors_raw if a) if isinstance(authors_raw, list) else ()

    keywords_raw = _val(content.get("keywords")) or []
    keywords = tuple(str(k) for k in keywords_raw if k) if isinstance(keywords_raw, list) else ()

    note_id = getattr(note, "id", None)
    url = f"https://openreview.net/forum?id={note_id}" if note_id else None

    return Paper(
        source="openreview",
        id=note_id,
        title=title,
        year=year,
        venue=venue,
        url=url,
        abstract=abstract,
        authors=authors,
        keywords=keywords,
    )


def _is_accepted(note: Any) -> bool:
    content = getattr(note, "content", {}) or {}
    venueid = _val(content.get("venueid")) or ""
    venue = _val(content.get("venue")) or ""
    rejected = "Rejected" in venueid or "Withdrawn" in venueid
    submitted_only = venue.lower().startswith("submitted to")
    return not rejected and not submitted_only


def _venueid_from_invitation(invitation: str) -> str:
    """'ICLR.cc/2024/Conference/-/Submission' → 'ICLR.cc/2024/Conference'.

    venueid dạng '.../Conference' là venueid của các paper đã accepted trên
    OpenReview API v2 — đúng cái ta cần để lọc theo venue+năm qua `/notes/search`.
    """
    return invitation.split("/-/", 1)[0]


def fetch_openreview_papers(
    *,
    invitation: str,
    keyword: str | None = None,
    accepted_only: bool = False,
    limit: int = 10,
    offset: int = 0,
) -> list[Paper]:
    """
    Lấy paper từ OpenReview qua endpoint `/notes/search`, có phân trang (offset/limit).

    Endpoint `/notes` (liệt kê theo invitation) hiện bị OpenReview chặn bằng
    challenge verification (HTTP 403) với request anonymous, nên ta chuyển sang
    `/notes/search` — vẫn cho phép anonymous và tự lọc relevance theo `term`.

    Vì `/notes/search` bắt buộc có `term`, hàm cần `keyword` để hoạt động; nếu
    thiếu keyword sẽ trả về [] (không còn cách liệt kê toàn bộ khi ẩn danh).

    Trả về tối đa limit+1 paper — nếu len(result) > limit thì còn trang tiếp theo.

    Args:
        invitation: ví dụ 'ICLR.cc/2025/Conference/-/Submission' (dùng để suy ra venueid)
        keyword: từ khóa tìm kiếm (bắt buộc với endpoint search)
        accepted_only: giữ lại tham số cho tương thích; venueid '.../Conference'
            vốn chỉ chứa paper đã accepted nên kết quả mặc định đã là accepted.
        limit: số paper tối đa cần trả về (tải limit+1 để phát hiện has_more)
        offset: bỏ qua bao nhiêu paper trước khi bắt đầu thu thập
    """
    q = keyword.strip() if keyword else ""
    if not q:
        logger.warning(
            "OpenReview `/notes/search` yêu cầu keyword; bỏ qua invitation=%s vì không có keyword.",
            invitation,
        )
        return []

    venueid = _venueid_from_invitation(invitation)
    notes = _search_with_retry(q, venueid, limit=limit + 1, offset=offset)

    collected: list[Paper] = []
    for note in notes:
        if accepted_only and not _is_accepted(note):
            continue
        p = _note_to_paper(note)
        if p:
            collected.append(p)
        if len(collected) >= limit + 1:
            break
    return collected


def build_invitation(*, venue_key: str, year: int) -> str:
    """Tạo invitation string từ venue key và năm."""
    prefix = OPENREVIEW_VENUES.get(venue_key.lower())
    if not prefix:
        raise ValueError(
            f"Venue '{venue_key}' không có trên OpenReview. "
            f"Hỗ trợ: {', '.join(sorted(OPENREVIEW_VENUES))}"
        )
    return f"{prefix}/{year}/Conference/-/Submission"
