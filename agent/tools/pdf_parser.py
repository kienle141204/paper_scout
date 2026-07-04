"""PDF parsing, now backed by MinerU (structure-aware) instead of pypdf.

``parse_pdf`` runs MinerU and returns a ``PdfParseResult`` that keeps the old fields
(text / abstract / method / experiments / table & figure mentions) so the
``/api/papers/pdf/parse`` endpoint stays unchanged, plus a new ``blocks`` field that
the RAG ingest path (agent/rag/ingest.py) uses for structure-aware chunking.

MinerU is heavy (torch + models) but only loaded when ``run_mineru`` shells out to the
``mineru`` binary, so importing this module stays cheap.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.tools.mineru_parser import Block, canonical_section, run_mineru


@dataclass(frozen=True)
class PdfParseResult:
    text: str
    abstract: str | None
    method: str | None
    experiments: str | None
    table_mentions: list[str]
    figure_mentions: list[str]
    blocks: list[Block] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstract": self.abstract,
            "method": self.method,
            "experiments": self.experiments,
            "table_mentions": self.table_mentions,
            "figure_mentions": self.figure_mentions,
        }


def parse_pdf(
    path: Path,
    *,
    max_pages: int | None = None,  # limit to first N pages (0 / None = whole doc)
    backend: str = "pipeline",
    device: str = "cpu",
    lang: str = "en",
    model_source: str | None = None,
) -> PdfParseResult:
    blocks = run_mineru(
        path, backend=backend, device=device, lang=lang,
        model_source=model_source, max_pages=max_pages,
    )
    return result_from_blocks(blocks)


def result_from_blocks(blocks: list[Block]) -> PdfParseResult:
    """Build a PdfParseResult from MinerU blocks. Pure — unit-testable without MinerU."""
    text = _blocks_to_markdown(blocks)

    sections = _section_texts(blocks)
    table_mentions = [f"Table {i}" for i in range(1, sum(1 for b in blocks if b.type == "table") + 1)]
    figure_mentions = [f"Figure {i}" for i in range(1, sum(1 for b in blocks if b.type == "image") + 1)]

    return PdfParseResult(
        text=text,
        abstract=sections.get("abstract"),
        method=sections.get("method"),
        experiments=sections.get("experiments"),
        table_mentions=table_mentions,
        figure_mentions=figure_mentions,
        blocks=blocks,
    )


def _blocks_to_markdown(blocks: list[Block]) -> str:
    parts: list[str] = []
    for b in blocks:
        if b.type == "title":
            hashes = "#" * min(b.text_level or 1, 6)
            parts.append(f"{hashes} {b.text}")
        elif b.type == "table":
            cap = f"{b.caption}\n" if b.caption else ""
            parts.append(f"{cap}{b.table_html or b.text}".strip())
        elif b.type == "equation":
            parts.append(f"$$ {b.latex or b.text} $$")
        elif b.type == "image":
            parts.append(f"[Figure] {b.caption or b.text}")
        else:
            parts.append(b.text)
    return "\n\n".join(p for p in parts if p.strip())


def _section_texts(blocks: list[Block]) -> dict[str, str]:
    """Collect body text grouped by canonical section (for the coarse metadata fields)."""
    out: dict[str, list[str]] = {}
    current: str | None = None
    for b in blocks:
        if b.type == "title":
            sec = canonical_section(b.text)
            current = sec
            continue
        if current and b.text.strip():
            out.setdefault(current, []).append(b.text.strip())
    return {k: "\n\n".join(v)[:20000] for k, v in out.items()}
