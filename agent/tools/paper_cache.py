from __future__ import annotations

import json
import os
from typing import Any


def _get_client():
    """Trả về Supabase client hoặc None nếu chưa cấu hình."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


def get_cached_paper(paper_id: str) -> dict[str, Any] | None:
    """
    Lấy paper từ cache Supabase theo paper_id.
    Trả về None nếu không tìm thấy hoặc Supabase chưa cấu hình.
    """
    client = _get_client()
    if not client:
        return None
    try:
        res = client.table("paper_cache").select("*").eq("paper_id", paper_id).maybe_single().execute()
        return res.data or None
    except Exception:
        return None


def upsert_paper(paper: dict[str, Any]) -> None:
    """
    Lưu hoặc cập nhật paper vào cache Supabase.
    Bỏ qua silently nếu Supabase chưa cấu hình hoặc lỗi.

    Trường bắt buộc trong paper dict: paper_id
    """
    client = _get_client()
    if not client:
        return
    try:
        # Supabase không nhận list Python trực tiếp ở một số version — serialize an toàn
        row = {
            "paper_id": paper.get("paper_id") or paper.get("id"),
            "title": paper.get("title"),
            "abstract_en": paper.get("abstract_en") or paper.get("abstract"),
            "abstract_vi": paper.get("abstract_vi"),
            "authors": json.dumps(paper.get("authors") or [], ensure_ascii=False),
            "keywords": json.dumps(paper.get("keywords") or [], ensure_ascii=False),
            "venue": paper.get("venue"),
            "year": paper.get("year"),
            "url": paper.get("url"),
            "source": paper.get("source"),
        }
        client.table("paper_cache").upsert(row, on_conflict="paper_id").execute()
    except Exception:
        pass


def get_cached_analysis(paper_id: str) -> str | None:
    """Lấy HTML analysis report từ Supabase cache."""
    client = _get_client()
    if not client:
        return None
    try:
        res = (
            client.table("paper_cache")
            .select("analysis_html")
            .eq("paper_id", paper_id)
            .maybe_single()
            .execute()
        )
        if res.data and res.data.get("analysis_html"):
            return res.data["analysis_html"]
        return None
    except Exception:
        return None


def upsert_analysis(paper_id: str, html: str) -> None:
    """Lưu HTML analysis report vào Supabase cache (cột analysis_html)."""
    client = _get_client()
    if not client:
        return
    try:
        client.table("paper_cache").upsert(
            {"paper_id": paper_id, "analysis_html": html},
            on_conflict="paper_id",
        ).execute()
    except Exception:
        pass


def is_configured() -> bool:
    """Kiểm tra Supabase đã được cấu hình chưa."""
    return bool(os.getenv("SUPABASE_URL") and os.getenv("SUPABASE_ANON_KEY"))
