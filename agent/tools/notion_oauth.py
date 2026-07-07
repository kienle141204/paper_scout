"""Local Notion OAuth token and export mapping store."""
from __future__ import annotations

import base64
import json
import os
import secrets
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

import requests

from agent.tools.library import DEFAULT_DB_PATH


NOTION_AUTH_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
NOTION_VERSION = "2026-03-11"
LOCAL_USER_ID = "local"


class NotionOAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class NotionOAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str


def _connect(path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    con = sqlite3.connect(str(path))
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS notion_oauth_tokens (
          user_id TEXT PRIMARY KEY,
          access_token TEXT NOT NULL,
          refresh_token TEXT,
          workspace_id TEXT,
          workspace_name TEXT,
          bot_id TEXT,
          owner_json TEXT NOT NULL DEFAULT '{}',
          created_at TEXT DEFAULT (datetime('now')),
          updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS notion_oauth_states (
          state TEXT PRIMARY KEY,
          user_id TEXT NOT NULL DEFAULT 'local',
          created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS notion_exports (
          notion_key TEXT PRIMARY KEY,
          user_id TEXT NOT NULL DEFAULT 'local',
          paper_id TEXT,
          notion_page_id TEXT NOT NULL,
          updated_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    return con


def oauth_config_from_env() -> NotionOAuthConfig:
    client_id = os.getenv("NOTION_OAUTH_CLIENT_ID", "").strip()
    client_secret = os.getenv("NOTION_OAUTH_CLIENT_SECRET", "").strip()
    redirect_uri = os.getenv("NOTION_OAUTH_REDIRECT_URI", "http://localhost:8000/api/notion/callback").strip()
    if not client_id or not client_secret:
        raise NotionOAuthError("Set NOTION_OAUTH_CLIENT_ID and NOTION_OAUTH_CLIENT_SECRET.")
    if not redirect_uri:
        raise NotionOAuthError("Set NOTION_OAUTH_REDIRECT_URI.")
    return NotionOAuthConfig(client_id=client_id, client_secret=client_secret, redirect_uri=redirect_uri)


def create_state(*, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> str:
    state = secrets.token_urlsafe(24)
    con = _connect(db_path)
    try:
        con.execute(
            "INSERT INTO notion_oauth_states(state, user_id) VALUES(?, ?)",
            (state, user_id),
        )
        con.commit()
        return state
    finally:
        con.close()


def consume_state(state: str, *, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> bool:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT state FROM notion_oauth_states WHERE state = ? AND user_id = ?",
            (state, user_id),
        ).fetchone()
        if not row:
            return False
        con.execute("DELETE FROM notion_oauth_states WHERE state = ?", (state,))
        con.commit()
        return True
    finally:
        con.close()


def authorization_url(config: NotionOAuthConfig, *, state: str) -> str:
    query = urlencode({
        "owner": "user",
        "client_id": config.client_id,
        "redirect_uri": config.redirect_uri,
        "response_type": "code",
        "state": state,
    })
    return f"{NOTION_AUTH_URL}?{query}"


def exchange_code_for_token(config: NotionOAuthConfig, *, code: str) -> dict[str, Any]:
    basic = base64.b64encode(f"{config.client_id}:{config.client_secret}".encode("utf-8")).decode("ascii")
    response = requests.post(
        NOTION_TOKEN_URL,
        headers={
            "Authorization": f"Basic {basic}",
            "Content-Type": "application/json",
            "Notion-Version": NOTION_VERSION,
        },
        json={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": config.redirect_uri,
        },
        timeout=30,
    )
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise NotionOAuthError(f"Notion OAuth token exchange failed: {detail}")
    data = response.json()
    if not data.get("access_token"):
        raise NotionOAuthError("Notion OAuth response did not include an access token.")
    return data


def save_connection(token_response: dict[str, Any], *, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO notion_oauth_tokens(
              user_id, access_token, refresh_token, workspace_id, workspace_name, bot_id, owner_json
            )
            VALUES(?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
              access_token=excluded.access_token,
              refresh_token=excluded.refresh_token,
              workspace_id=excluded.workspace_id,
              workspace_name=excluded.workspace_name,
              bot_id=excluded.bot_id,
              owner_json=excluded.owner_json,
              updated_at=datetime('now')
            """,
            (
                user_id,
                token_response["access_token"],
                token_response.get("refresh_token"),
                token_response.get("workspace_id"),
                token_response.get("workspace_name"),
                token_response.get("bot_id"),
                json.dumps(token_response.get("owner") or {}, ensure_ascii=False, sort_keys=True),
            ),
        )
        con.commit()
    finally:
        con.close()


def get_connection(*, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> dict[str, Any] | None:
    con = _connect(db_path)
    try:
        row = con.execute(
            """
            SELECT access_token, refresh_token, workspace_id, workspace_name, bot_id, owner_json, updated_at
            FROM notion_oauth_tokens WHERE user_id = ?
            """,
            (user_id,),
        ).fetchone()
        if not row:
            return None
        return {
            "access_token": row[0],
            "refresh_token": row[1],
            "workspace_id": row[2],
            "workspace_name": row[3],
            "bot_id": row[4],
            "owner": json.loads(row[5] or "{}"),
            "updated_at": row[6],
        }
    finally:
        con.close()


def delete_connection(*, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> None:
    con = _connect(db_path)
    try:
        con.execute("DELETE FROM notion_oauth_tokens WHERE user_id = ?", (user_id,))
        con.execute("DELETE FROM notion_oauth_states WHERE user_id = ?", (user_id,))
        con.commit()
    finally:
        con.close()


def get_export_page(notion_key: str, *, user_id: str = LOCAL_USER_ID, db_path: Path = DEFAULT_DB_PATH) -> str | None:
    con = _connect(db_path)
    try:
        row = con.execute(
            "SELECT notion_page_id FROM notion_exports WHERE notion_key = ? AND user_id = ?",
            (notion_key, user_id),
        ).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def save_export_page(
    *,
    notion_key: str,
    notion_page_id: str,
    paper_id: str | None = None,
    user_id: str = LOCAL_USER_ID,
    db_path: Path = DEFAULT_DB_PATH,
) -> None:
    con = _connect(db_path)
    try:
        con.execute(
            """
            INSERT INTO notion_exports(notion_key, user_id, paper_id, notion_page_id)
            VALUES(?, ?, ?, ?)
            ON CONFLICT(notion_key) DO UPDATE SET
              paper_id=excluded.paper_id,
              notion_page_id=excluded.notion_page_id,
              updated_at=datetime('now')
            """,
            (notion_key, user_id, paper_id, notion_page_id),
        )
        con.commit()
    finally:
        con.close()
