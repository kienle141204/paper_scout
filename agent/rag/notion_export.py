"""Notion export orchestration for paper notes."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any, Literal

from agent.tools.notion_client import NotionPaperClient, NotionWriteResult
from agent.search.workspace import find_paper

from .note_builder import build_paper_note_preview


@dataclass
class ExportOptions:
    paper_id: str
    note_type: Literal["summary", "qa", "full_reading_note"] = "summary"
    include_qa_history: bool = False
    target_database_id: str | None = None
    target_page_id: str | None = None
    paper: dict[str, Any] | None = None
    qa_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ExportResult:
    notion_page_id: str | None
    created: bool
    updated: bool
    preview: str

    def to_response_dict(self) -> dict[str, Any]:
        return {
            "notion_page_id": self.notion_page_id,
            "created": self.created,
            "updated": self.updated,
            "preview": self.preview,
        }


def _notion_key(paper: dict[str, Any]) -> str:
    source_ids = paper.get("source_ids") or {}
    if isinstance(source_ids, dict):
        for key in ("doi", "arxiv", "semantic_scholar", "openalex"):
            if source_ids.get(key):
                return f"{key}:{source_ids[key]}"
    if paper.get("paper_id"):
        return f"paper_id:{paper['paper_id']}"
    title = re.sub(r"\W+", "-", str(paper.get("title") or "untitled").lower()).strip("-")
    return f"title:{title}:{paper.get('year') or ''}"


def export_paper_note(options: ExportOptions) -> ExportResult:
    paper = options.paper or find_paper(options.paper_id) or {"paper_id": options.paper_id, "title": options.paper_id}
    preview = build_paper_note_preview(
        paper=paper,
        note_type=options.note_type,
        include_qa_history=options.include_qa_history,
        qa_history=options.qa_history,
    )
    token = os.getenv("NOTION_TOKEN", "")
    database_id = options.target_database_id or os.getenv("NOTION_DATABASE_ID")
    page_id = options.target_page_id or os.getenv("NOTION_PARENT_PAGE_ID")
    client = NotionPaperClient(token=token, database_id=database_id, parent_page_id=page_id)
    title = paper.get("title") or paper.get("paper_id") or options.paper_id
    result: NotionWriteResult = client.upsert_paper_page(notion_key=_notion_key(paper), title=title, preview=preview)
    return ExportResult(
        notion_page_id=result.notion_page_id,
        created=result.created,
        updated=result.updated,
        preview=result.preview,
    )
