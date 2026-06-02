from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


DEFAULT_DB_PATH = Path("library.sqlite3")


def _connect(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS papers (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          source TEXT,
          ext_id TEXT,
          title TEXT,
          year INTEGER,
          venue TEXT,
          doi TEXT,
          url TEXT,
          abstract TEXT,
          tags TEXT,
          note TEXT,
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS profile (
          key TEXT PRIMARY KEY,
          value TEXT
        );
        """
    )
    return con


def add_paper(db_path: Path, paper: dict[str, Any], *, tags: list[str] | None = None, note: str | None = None) -> int:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO papers (source, ext_id, title, year, venue, doi, url, abstract, tags, note)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                paper.get("source"),
                paper.get("id"),
                paper.get("title"),
                paper.get("year"),
                paper.get("venue"),
                paper.get("doi"),
                paper.get("url"),
                paper.get("abstract"),
                ",".join(tags or []),
                note,
            ),
        )
        con.commit()
        return int(con.execute("SELECT last_insert_rowid()").fetchone()[0])
    finally:
        con.close()


def list_papers(db_path: Path, *, tag: str | None = None, q: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    con = _connect(db_path)
    try:
        sql = "SELECT id, source, ext_id, title, year, venue, doi, url, tags, note, created_at FROM papers"
        params: list[Any] = []
        where: list[str] = []
        if tag:
            where.append("tags LIKE ?")
            params.append(f"%{tag}%")
        if q:
            where.append("(title LIKE ? OR abstract LIKE ? OR note LIKE ?)")
            params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(int(limit))
        cur = con.execute(sql, params)
        rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "row_id": r[0],
                    "source": r[1],
                    "id": r[2],
                    "title": r[3],
                    "year": r[4],
                    "venue": r[5],
                    "doi": r[6],
                    "url": r[7],
                    "tags": r[8],
                    "note": r[9],
                    "created_at": r[10],
                }
            )
        return out
    finally:
        con.close()


def delete_paper(db_path: Path, *, row_id: int) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM papers WHERE id = ?", (int(row_id),))
        con.commit()
    finally:
        con.close()


def update_note(db_path: Path, *, row_id: int, note: str) -> None:
    con = _connect(db_path)
    try:
        con.execute("UPDATE papers SET note = ? WHERE id = ?", (note, int(row_id)))
        con.commit()
    finally:
        con.close()


def update_tags(db_path: Path, *, row_id: int, tags: list[str]) -> None:
    con = _connect(db_path)
    try:
        con.execute("UPDATE papers SET tags = ? WHERE id = ?", (",".join(tags), int(row_id)))
        con.commit()
    finally:
        con.close()


def set_profile(db_path: Path, *, key: str, value: str) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO profile(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        con.commit()
    finally:
        con.close()


def get_profile(db_path: Path) -> dict[str, str]:
    con = _connect(db_path)
    try:
        cur = con.execute("SELECT key, value FROM profile")
        return {k: v for (k, v) in cur.fetchall()}
    finally:
        con.close()
