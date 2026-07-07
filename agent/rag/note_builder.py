"""Build deterministic paper-note previews for export targets."""
from __future__ import annotations

from typing import Any


def build_paper_note_preview(
    *,
    paper: dict[str, Any],
    note_type: str,
    include_qa_history: bool = False,
    qa_history: list[dict[str, Any]] | None = None,
) -> str:
    title = paper.get("title") or paper.get("titleEn") or paper.get("paper_id") or "Untitled paper"
    authors = paper.get("authors") or []
    if authors and isinstance(authors[0], dict):
        author_text = ", ".join(a.get("name", "") for a in authors if a.get("name"))
    else:
        author_text = ", ".join(str(a) for a in authors)
    lines = [
        f"# {title}",
        "",
        "## Metadata",
        f"- Authors: {author_text or 'Unknown'}",
        f"- Year: {paper.get('year') or 'Unknown'}",
        f"- Venue: {paper.get('venue') or paper.get('conference') or 'Unknown'}",
        f"- DOI/arXiv/S2/OpenAlex: {_ids_text(paper)}",
        f"- URL: {paper.get('url') or ''}",
        f"- PDF: {paper.get('pdf_url') or paper.get('pdfUrl') or ''}",
        "",
    ]
    abstract = paper.get("abstract") or paper.get("abstractEn")
    if note_type in ("summary", "full_reading_note") and abstract:
        lines += ["## Summary", abstract[:2000], ""]
    if note_type in ("qa", "full_reading_note") and include_qa_history and qa_history:
        lines.append("## Q&A")
        for item in qa_history[-10:]:
            role = item.get("role", "user")
            content = str(item.get("content") or "").strip()
            if content:
                lines.append(f"- {role}: {content}")
        lines.append("")
    lines += ["## My Notes", ""]
    return "\n".join(lines).strip()


def _ids_text(paper: dict[str, Any]) -> str:
    source_ids = paper.get("source_ids") or paper.get("sourceIds") or {}
    if not isinstance(source_ids, dict):
        return ""
    parts = [str(v) for v in source_ids.values() if v]
    return ", ".join(parts)
