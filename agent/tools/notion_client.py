"""Deterministic Notion client wrapper.

This module owns the Notion SDK boundary. It contains no RAG/search business
logic and is safe to fake in tests.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class NotionConfigError(RuntimeError):
    pass


@dataclass
class NotionWriteResult:
    notion_page_id: str
    created: bool
    updated: bool
    preview: str


def _blocks_from_markdown_preview(preview: str) -> list[dict[str, Any]]:
    blocks = []
    for raw_line in preview.splitlines()[:80]:
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append({"object": "block", "type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": line[2:][:1900]}}]}})
        elif line.startswith("- "):
            blocks.append({"object": "block", "type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": line[2:][:1900]}}]}})
        else:
            blocks.append({"object": "block", "type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": line[:1900]}}]}})
    return blocks


class NotionPaperClient:
    def __init__(self, *, token: str, database_id: str | None = None, parent_page_id: str | None = None):
        if not token:
            raise NotionConfigError("NOTION_TOKEN is not configured.")
        if not database_id and not parent_page_id:
            raise NotionConfigError("Set NOTION_DATABASE_ID or NOTION_PARENT_PAGE_ID.")
        try:
            from notion_client import Client
        except Exception as exc:  # pragma: no cover - exercised via config tests
            raise NotionConfigError("notion-client is not installed.") from exc
        self.client = Client(auth=token)
        self.database_id = database_id
        self.parent_page_id = parent_page_id

    def _find_existing(self, notion_key: str) -> str | None:
        if not self.database_id:
            return None
        try:
            res = self.client.databases.query(
                database_id=self.database_id,
                filter={"property": "PaperScout Key", "rich_text": {"equals": notion_key}},
                page_size=1,
            )
        except Exception:
            return None
        results = res.get("results") or []
        return results[0].get("id") if results else None

    def upsert_paper_page(self, *, notion_key: str, title: str, preview: str) -> NotionWriteResult:
        existing_id = self._find_existing(notion_key)
        blocks = _blocks_from_markdown_preview(preview)
        if existing_id:
            if blocks:
                self.client.blocks.children.append(block_id=existing_id, children=blocks)
            return NotionWriteResult(notion_page_id=existing_id, created=False, updated=True, preview=preview)

        properties = {
            "Name": {"title": [{"type": "text", "text": {"content": title[:1900]}}]},
            "PaperScout Key": {"rich_text": [{"type": "text", "text": {"content": notion_key[:1900]}}]},
        }
        parent = {"database_id": self.database_id} if self.database_id else {"page_id": self.parent_page_id}
        page = self.client.pages.create(parent=parent, properties=properties, children=blocks)
        return NotionWriteResult(notion_page_id=page["id"], created=True, updated=False, preview=preview)
