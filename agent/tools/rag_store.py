"""Supabase-backed RAG store for paper chunks.

Stores text chunks + JSON-encoded embeddings in the `paper_chunks` table.
Similarity search is done in Python (cosine) — no pgvector extension required.
Suitable for up to ~500 chunks per paper.
"""
from __future__ import annotations

import json
import math
import os
import threading
from typing import Any

_lock = threading.Lock()
_client_obj = None
_client_ready = False


def _get_client():
    global _client_obj, _client_ready
    if _client_ready:
        return _client_obj
    with _lock:
        if _client_ready:
            return _client_obj
        url = os.getenv("SUPABASE_URL")
        key = (
            os.getenv("SUPABASE_SERVICE_ROLE_KEY")
            or os.getenv("SUPABASE_ANON_KEY")
            or os.getenv("SUPABASE_KEY")
        )
        if url and key:
            try:
                from supabase import create_client
                _client_obj = create_client(url, key)
            except Exception:
                _client_obj = None
        _client_ready = True
    return _client_obj


def is_configured() -> bool:
    return _get_client() is not None


def is_ingested(paper_id: str) -> bool:
    c = _get_client()
    if not c:
        return False
    try:
        res = c.table("paper_chunks").select("id").eq("paper_id", paper_id).limit(1).execute()
        return bool(res.data)
    except Exception:
        return False


def store_chunks(paper_id: str, chunks: list[dict[str, Any]]) -> None:
    """Upsert chunk rows. Each dict must have: chunk_index, text, embedding (list[float]).
    Optional: section, token_count.
    Raises RuntimeError if the write fails (e.g. table does not exist).
    """
    c = _get_client()
    if not c:
        raise RuntimeError("Supabase chưa được cấu hình (SUPABASE_URL / SUPABASE_ANON_KEY thiếu).")
    rows = [
        {
            "paper_id": paper_id,
            "chunk_index": ch["chunk_index"],
            "section": ch.get("section"),
            "text": ch["text"],
            "embedding": json.dumps(ch["embedding"]),
            "token_count": ch.get("token_count"),
        }
        for ch in chunks
    ]
    try:
        c.table("paper_chunks").upsert(rows, on_conflict="paper_id,chunk_index").execute()
    except Exception as e:
        msg = str(e)
        if "42501" in msg or "row-level security" in msg.lower():
            raise RuntimeError(
                "Bảng paper_chunks bị chặn bởi Row-Level Security. "
                "Vào Supabase Dashboard → SQL Editor và chạy:\n"
                "  ALTER TABLE paper_chunks DISABLE ROW LEVEL SECURITY;"
            ) from e
        raise RuntimeError(
            f"Không thể lưu chunks vào Supabase: {e}. "
            "Hãy chạy supabase_migration_rag.sql trong Supabase SQL Editor."
        ) from e


def retrieve_by_section(
    paper_id: str,
    section: str,
    *,
    top_k: int = 4,
) -> list[dict[str, Any]]:
    """Return up to top_k chunks whose section field contains *section* (case-insensitive)."""
    c = _get_client()
    if not c:
        return []
    try:
        res = (
            c.table("paper_chunks")
            .select("chunk_index,section,text")
            .eq("paper_id", paper_id)
            .ilike("section", f"%{section}%")
            .limit(top_k)
            .execute()
        )
        return [
            {"chunk_index": r["chunk_index"], "section": r.get("section") or "body", "text": r["text"]}
            for r in (res.data or [])
        ]
    except Exception:
        return []


def _cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def retrieve_chunks(
    paper_id: str,
    query_embedding: list[float],
    *,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Return the top_k most similar chunks for *paper_id*."""
    c = _get_client()
    if not c:
        return []
    try:
        res = (
            c.table("paper_chunks")
            .select("chunk_index,section,text,embedding")
            .eq("paper_id", paper_id)
            .execute()
        )
        rows = res.data or []
    except Exception:
        return []

    scored: list[tuple[float, dict[str, Any]]] = []
    for row in rows:
        try:
            emb = json.loads(row["embedding"])
            sim = _cosine(query_embedding, emb)
            scored.append((sim, {
                "chunk_index": row["chunk_index"],
                "section": row.get("section") or "body",
                "text": row["text"],
                "similarity": round(sim, 4),
            }))
        except Exception:
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for _, r in scored[:top_k]]
