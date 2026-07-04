"""Local single-user memory store backed by library.sqlite3."""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from agent.tools.library import DEFAULT_DB_PATH


LOCAL_USER_ID = "local"


def _connect(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS memory_events (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL DEFAULT 'local',
          event_type TEXT NOT NULL,
          paper_id TEXT,
          query TEXT,
          topics_json TEXT NOT NULL DEFAULT '[]',
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS preferences (
          key TEXT PRIMARY KEY,
          value_json TEXT NOT NULL,
          confidence REAL DEFAULT 1.0,
          evidence_count INTEGER DEFAULT 1,
          updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS paper_interactions (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          user_id TEXT NOT NULL DEFAULT 'local',
          paper_id TEXT NOT NULL,
          action TEXT NOT NULL,
          metadata_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS reader_sessions (
          session_id TEXT PRIMARY KEY,
          user_id TEXT NOT NULL DEFAULT 'local',
          paper_id TEXT NOT NULL,
          summary TEXT,
          messages_json TEXT NOT NULL DEFAULT '[]',
          updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    return con


def _json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True)


def append_memory_event(
    *,
    event_type: str,
    user_id: str = LOCAL_USER_ID,
    paper_id: str | None = None,
    query: str | None = None,
    topics: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    db_path: Path = DEFAULT_DB_PATH,
) -> int:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO memory_events(user_id, event_type, paper_id, query, topics_json, metadata_json)
            VALUES(?, ?, ?, ?, ?, ?)
            """,
            (user_id, event_type, paper_id, query, _json(topics or []), _json(metadata or {})),
        )
        if paper_id:
            con.execute(
                """
                INSERT INTO paper_interactions(user_id, paper_id, action, metadata_json)
                VALUES(?, ?, ?, ?)
                """,
                (user_id, paper_id, event_type, _json(metadata or {})),
            )
        con.commit()
        return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        con.close()


def list_memory(*, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH, event_limit: int = 50) -> dict[str, Any]:
    con = _connect(db_path)
    try:
        pref_rows = con.execute(
            "SELECT key, value_json, confidence, evidence_count, updated_at FROM preferences ORDER BY updated_at DESC"
        ).fetchall()
        event_rows = con.execute(
            """
            SELECT id, event_type, paper_id, query, topics_json, metadata_json, created_at
            FROM memory_events
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, int(event_limit)),
        ).fetchall()
        interaction_rows = con.execute(
            """
            SELECT paper_id, action, metadata_json, created_at
            FROM paper_interactions
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, int(event_limit)),
        ).fetchall()
        return {
            "user_id": user_id,
            "preferences": [
                {
                    "key": r[0],
                    "value": json.loads(r[1]),
                    "confidence": r[2],
                    "evidence_count": r[3],
                    "updated_at": r[4],
                }
                for r in pref_rows
            ],
            "events": [
                {
                    "id": r[0],
                    "event_type": r[1],
                    "paper_id": r[2],
                    "query": r[3],
                    "topics": json.loads(r[4]),
                    "metadata": json.loads(r[5]),
                    "created_at": r[6],
                }
                for r in event_rows
            ],
            "paper_interactions": [
                {
                    "paper_id": r[0],
                    "action": r[1],
                    "metadata": json.loads(r[2]),
                    "created_at": r[3],
                }
                for r in interaction_rows
            ],
        }
    finally:
        con.close()


def set_preference(
    *,
    key: str,
    value: Any,
    confidence: float = 1.0,
    evidence_count: int = 1,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO preferences(key, value_json, confidence, evidence_count)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
              value_json=excluded.value_json,
              confidence=excluded.confidence,
              evidence_count=preferences.evidence_count + excluded.evidence_count,
              updated_at=datetime('now')
            """,
            (key, _json(value), float(confidence), int(evidence_count)),
        )
        con.commit()
    finally:
        con.close()


def patch_preferences(preferences: dict[str, Any], *, db_path: Path = DEFAULT_DB_PATH) -> None:
    for key, value in preferences.items():
        set_preference(key=key, value=value, confidence=1.0, evidence_count=1, db_path=db_path)


def delete_topic(topic_id: str, *, db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM preferences WHERE key = ?", (topic_id,))
        con.commit()
    finally:
        con.close()


def delete_all_memory(*, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM memory_events WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM paper_interactions WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM reader_sessions WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM preferences")
        con.commit()
    finally:
        con.close()
