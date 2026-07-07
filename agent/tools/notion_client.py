"""Deterministic Notion client wrapper.

This module owns the Notion SDK boundary. It contains no RAG/search business
logic and is safe to fake in tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class NotionConfigError(RuntimeError):
    pass


@dataclass
class NotionWriteResult:
    notion_page_id: str
    created: bool
    updated: bool
    preview: str


_KEY_PROPERTY = "PaperScout Key"
_NOTION_API_VERSION = "2026-03-11"


def _rich_text(content: str) -> list[dict[str, Any]]:
    return [{"type": "text", "text": {"content": content[:1900]}}]


def _blocks_from_markdown_preview(preview: str) -> list[dict[str, Any]]:
    blocks = []
    for raw_line in preview.splitlines()[:80]:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": _rich_text(line[2:])}})
        elif line.startswith("## "):
            blocks.append({"object": "block", "type": "heading_2", "heading_2": {"rich_text": _rich_text(line[3:])}})
        elif line.startswith("### "):
            blocks.append({"object": "block", "type": "heading_3", "heading_3": {"rich_text": _rich_text(line[4:])}})
        elif line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": _rich_text(line[2:])}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": _rich_text(line)}})
    return blocks


class NotionPaperClient:
    def __init__(
        self,
        *,
        token: str,
        database_id: str | None = None,
        parent_page_id: str | None = None,
        workspace_parent: bool = False,
        known_page_id: str | None = None,
    ):
        if not token:
            raise NotionConfigError("NOTION_TOKEN is not configured.")
        if not database_id and not parent_page_id and not workspace_parent:
            raise NotionConfigError("Set NOTION_DATABASE_ID or NOTION_PARENT_PAGE_ID.")
        try:
            from notion_client import Client
        except Exception as exc:  # pragma: no cover - exercised via config tests
            raise NotionConfigError("notion-client is not installed.") from exc
        self.token = token
        self.client = Client(auth=token)
        self.database_id = database_id
        self.parent_page_id = parent_page_id
        self.workspace_parent = workspace_parent
        self.known_page_id = known_page_id
        self.title_property = "Name"
        if self.database_id:
            self._load_database_schema()

    def _load_database_schema(self) -> None:
        try:
            database = self.client.databases.retrieve(database_id=self.database_id)
        except Exception as exc:
            raise NotionConfigError(f"Cannot read Notion database schema: {exc}") from exc

        properties = database.get("properties") or {}
        title_properties = [
            name for name, prop in properties.items()
            if isinstance(prop, dict) and prop.get("type") == "title"
        ]
        if not title_properties:
            raise NotionConfigError("Notion database needs a title property.")
        self.title_property = title_properties[0]

        key_property = properties.get(_KEY_PROPERTY)
        if not isinstance(key_property, dict) or key_property.get("type") != "rich_text":
            raise NotionConfigError(
                f'Notion database needs a rich_text property named "{_KEY_PROPERTY}".'
            )

    def _find_existing(self, notion_key: str) -> str | None:
        if self.known_page_id:
            return self.known_page_id
        if not self.database_id:
            return None
        try:
            res = self.client.databases.query(
                database_id=self.database_id,
                filter={"property": _KEY_PROPERTY, "rich_text": {"equals": notion_key}},
                page_size=1,
            )
        except Exception as exc:
            raise RuntimeError(f"Cannot query Notion database: {exc}") from exc
        results = res.get("results") or []
        return results[0].get("id") if results else None

    def _raw_request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        response = requests.request(
            method,
            f"https://api.notion.com/v1{path}",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Notion-Version": _NOTION_API_VERSION,
            },
            json=payload,
            timeout=30,
        )
        if response.status_code >= 400:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise RuntimeError(f"Notion API request failed: {detail}")
        return response.json() if response.content else {}

    def _create_workspace_page(self, *, title: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
        return self._raw_request(
            "POST",
            "/pages",
            {
                "parent": {"workspace": True},
                "properties": {"title": {"title": _rich_text(title)}},
                "children": blocks,
            },
        )

    def upsert_paper_page(self, *, notion_key: str, title: str, preview: str) -> NotionWriteResult:
        existing_id = self._find_existing(notion_key)
        blocks = _blocks_from_markdown_preview(preview)
        if existing_id:
            if blocks:
                self.client.blocks.children.append(block_id=existing_id, children=blocks)
            return NotionWriteResult(notion_page_id=existing_id, created=False, updated=True, preview=preview)

        if self.database_id:
            properties = {
                self.title_property: {"title": _rich_text(title)},
                _KEY_PROPERTY: {"rich_text": _rich_text(notion_key)},
            }
            parent = {"database_id": self.database_id}
        else:
            properties = {"title": {"title": _rich_text(title)}}
            parent = {"page_id": self.parent_page_id}
        if self.workspace_parent:
            page = self._create_workspace_page(title=title, blocks=blocks)
        else:
            page = self.client.pages.create(parent=parent, properties=properties, children=blocks)
        return NotionWriteResult(notion_page_id=page["id"], created=True, updated=False, preview=preview)
