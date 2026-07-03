from __future__ import annotations

import logging
import re
import time
from types import SimpleNamespace
from typing import Any

import requests

try:
    import openreview
except ModuleNotFoundError:  # pragma: no cover - depends on optional runtime extra
    openreview = None

from ..model import Paper

logger = logging.getLogger(__name__)

_INTER_BATCH_DELAY = 1.0   # seconds between batch requests (stay under 60 req/min)
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

_BATCH_SIZE = 500  # số note tải mỗi lần từ OpenReview khi cần filter


def _val(field: Any) -> Any:
    """API v2 trả content dạng {'value': ...}, hàm này extract giá trị thực."""
    if isinstance(field, dict):
        return field.get("value")
    return field


def _get_client() -> Any:
    if openreview is None:
        return None
    return openreview.api.OpenReviewClient(baseurl=OPENREVIEW_BASE_URL)


def _get_notes_http(**kwargs: Any) -> list[Any]:
    resp = requests.get(f"{OPENREVIEW_BASE_URL}/notes", params=kwargs, timeout=30)
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


def _get_notes_with_retry(client: Any, **kwargs: Any) -> list[Any]:
    """Wrapper around client.get_notes() với retry khi bị rate-limit (HTTP 429)."""
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            if client is None:
                return _get_notes_http(**kwargs)
            return client.get_notes(**kwargs)
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


def _matches_keyword(note: Any, q: str) -> bool:
    content = getattr(note, "content", {}) or {}
    title_text = (_val(content.get("title")) or "").lower()
    abstract_text = (_val(content.get("abstract")) or "").lower()
    kw_list = _val(content.get("keywords")) or []
    kw_text = " ".join(kw_list).lower() if isinstance(kw_list, list) else ""
    return q in title_text or q in abstract_text or q in kw_text


def fetch_openreview_papers(
    *,
    invitation: str,
    keyword: str | None = None,
    accepted_only: bool = False,
    limit: int = 10,
    offset: int = 0,
) -> list[Paper]:
    """
    Lấy paper từ OpenReview với hỗ trợ phân trang (offset/limit).

    Trả về tối đa limit+1 paper — nếu len(result) > limit thì còn trang tiếp theo.

    Args:
        invitation: ví dụ 'ICLR.cc/2025/Conference/-/Submission'
        keyword: lọc theo từ khóa trong title/abstract/keywords
        accepted_only: chỉ lấy paper được chấp nhận
        limit: số paper tối đa cần trả về (tải limit+1 để phát hiện has_more)
        offset: bỏ qua bao nhiêu paper (đã lọc) trước khi bắt đầu thu thập
    """
    client = _get_client()
    q = keyword.lower().strip() if keyword else None
    need_filter = bool(q) or accepted_only

    # Trường hợp không cần lọc: dùng native offset/limit của OpenReview — cực nhanh
    if not need_filter:
        notes = _get_notes_with_retry(client, invitation=invitation, offset=offset, limit=limit + 1)
        out: list[Paper] = []
        for note in notes:
            p = _note_to_paper(note)
            if p:
                out.append(p)
        return out

    # Trường hợp cần lọc: scan theo batch, bỏ qua offset kết quả phù hợp đầu tiên
    skipped = 0
    collected: list[Paper] = []
    or_offset = 0

    while True:
        notes = _get_notes_with_retry(client, invitation=invitation, offset=or_offset, limit=_BATCH_SIZE)
        if not notes:
            break

        for note in notes:
            if accepted_only and not _is_accepted(note):
                continue
            if q and not _matches_keyword(note, q):
                continue

            if skipped < offset:
                skipped += 1
                continue

            p = _note_to_paper(note)
            if p:
                collected.append(p)

            if len(collected) >= limit + 1:
                return collected

        if len(notes) < _BATCH_SIZE:
            break  # hết dữ liệu từ server

        or_offset += _BATCH_SIZE
        time.sleep(_INTER_BATCH_DELAY)  # tránh vượt 60 req/min

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
