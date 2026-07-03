"""Local Search Agent workspace state and cache.

Search sessions are local, single-user state. They intentionally live in the
same SQLite file as the library/profile data, not in the shared Supabase DB.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from agent.tools.library import DEFAULT_DB_PATH


def _connect(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS search_sessions (
          session_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL DEFAULT 'local',
          original_query TEXT NOT NULL,
          normalized_query TEXT NOT NULL,
          filters_json TEXT NOT NULL,
          papers_json TEXT NOT NULL,
          query_plan_json TEXT NOT NULL,
          source_stats_json TEXT NOT NULL,
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS search_cache (
          cache_key TEXT PRIMARY KEY,
          normalized_query TEXT NOT NULL,
          filters_json TEXT NOT NULL,
          papers_json TEXT NOT NULL,
          query_plan_json TEXT NOT NULL,
          source_stats_json TEXT NOT NULL,
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    return con


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def cache_key(*, query: str, filters: dict[str, Any], sources: list[str], limit: int, offset: int) -> str:
    payload = {
        "query": query.strip().lower(),
        "filters": filters,
        "sources": sources,
        "limit": limit,
        "offset": offset,
    }
    return hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()


def get_cached_search(key: str, *, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute(
            """
            SELECT normalized_query, filters_json, papers_json, query_plan_json, source_stats_json
            FROM search_cache WHERE cache_key = ?
            """,
            (key,),
        ).fetchone()
        if not row:
            return None
        return {
            "normalized_query": row[0],
            "filters": json.loads(row[1]),
            "papers": json.loads(row[2]),
            "query_plan": json.loads(row[3]),
            "source_stats": json.loads(row[4]),
        }
    finally:
        con.close()


def put_cached_search(
    key: str,
    *,
    normalized_query: str,
    filters: dict[str, Any],
    papers: list[dict[str, Any]],
    query_plan: dict[str, Any],
    source_stats: dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO search_cache(cache_key, normalized_query, filters_json, papers_json, query_plan_json, source_stats_json)
            VALUES(?, ?, ?, ?, ?, ?)
            ON CONFLICT(cache_key) DO UPDATE SET
              normalized_query=excluded.normalized_query,
              filters_json=excluded.filters_json,
              papers_json=excluded.papers_json,
              query_plan_json=excluded.query_plan_json,
              source_stats_json=excluded.source_stats_json,
              created_at=datetime('now')
            """,
            (key, normalized_query, _json(filters), _json(papers), _json(query_plan), _json(source_stats)),
        )
        con.commit()
    finally:
        con.close()


def save_search_session(
    *,
    session_id: str | None,
    original_query: str,
    normalized_query: str,
    filters: dict[str, Any],
    papers: list[dict[str, Any]],
    query_plan: dict[str, Any],
    source_stats: dict[str, Any],
    user_id: str = "local",
    db_path: Path = DEFAULT_DB_PATH,
) -> str:
    sid = session_id or str(uuid.uuid4())
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO search_sessions(session_id, user_id, original_query, normalized_query, filters_json, papers_json, query_plan_json, source_stats_json)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
              original_query=excluded.original_query,
              normalized_query=excluded.normalized_query,
              filters_json=excluded.filters_json,
              papers_json=excluded.papers_json,
              query_plan_json=excluded.query_plan_json,
              source_stats_json=excluded.source_stats_json
            """,
            (
                sid,
                user_id,
                original_query,
                normalized_query,
                _json(filters),
                _json(papers),
                _json(query_plan),
                _json(source_stats),
            ),
        )
        con.commit()
        return sid
    finally:
        con.close()


def get_search_session(session_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute(
            """
            SELECT session_id, original_query, normalized_query, filters_json, papers_json, query_plan_json, source_stats_json
            FROM search_sessions WHERE session_id = ?
            """,
            (session_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "session_id": row[0],
            "original_query": row[1],
            "normalized_query": row[2],
            "filters": json.loads(row[3]),
            "papers": json.loads(row[4]),
            "query_plan": json.loads(row[5]),
            "source_stats": json.loads(row[6]),
        }
    finally:
        con.close()


def find_paper(paper_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        rows = con.execute(
            "SELECT papers_json FROM search_sessions ORDER BY created_at DESC LIMIT 25"
        ).fetchall()
        for (papers_json,) in rows:
            for paper in json.loads(papers_json):
                if paper.get("paper_id") == paper_id:
                    return paper
    finally:
        con.close()
    return None
