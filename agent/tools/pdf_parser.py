from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any



@dataclass(frozen=True)
class PdfParseResult:
    text: str
    abstract: str | None
    method: str | None
    experiments: str | None
    table_mentions: list[str]
    figure_mentions: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "abstract": self.abstract,
            "method": self.method,
            "experiments": self.experiments,
            "table_mentions": self.table_mentions,
            "figure_mentions": self.figure_mentions,
        }


def read_pdf_text(path: Path, *, max_pages: int | None = None) -> str:
    """Extract text from a PDF. Reads every page by default (``max_pages=None``)."""
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    pages = reader.pages[: max_pages or len(reader.pages)]
    chunks: list[str] = []
    for p in pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        if t:
            chunks.append(t)
    return "\n".join(chunks)


def parse_pdf(path: Path, *, max_pages: int | None = None) -> PdfParseResult:
    text = read_pdf_text(path, max_pages=max_pages)
    clean = re.sub(r"[ \t]+", " ", text)
    clean = re.sub(r"\n{3,}", "\n\n", clean)

    abstract = _extract_section(clean, ["abstract"], stop_heads=["introduction", "1 introduction"])
    method = _extract_section(clean, ["method", "methods", "approach"], stop_heads=["experiments", "experimental", "results"])
    experiments = _extract_section(clean, ["experiments", "experimental setup", "experimental"], stop_heads=["results", "discussion", "conclusion"])

    table_mentions = _collect_mentions(clean, r"\bTable\s+\d+")
    figure_mentions = _collect_mentions(clean, r"\bFigure\s+\d+")

    return PdfParseResult(
        text=text,
        abstract=abstract,
        method=method,
        experiments=experiments,
        table_mentions=table_mentions,
        figure_mentions=figure_mentions,
    )


def _collect_mentions(text: str, pat: str) -> list[str]:
    hits = sorted(set(re.findall(pat, text)))
    return hits[:50]


def _extract_section(text: str, heads: list[str], *, stop_heads: list[str]) -> str | None:
    lower = text.lower()
    start = None
    for h in heads:
        m = re.search(rf"(^|\n)\s*{re.escape(h)}\s*(\n|:)", lower)
        if m:
            start = m.end()
            break
    if start is None:
        return None
    end = len(text)
    for sh in stop_heads:
        m2 = re.search(rf"(^|\n)\s*{re.escape(sh)}\s*(\n|:)", lower[start:])
        if m2:
            end = start + m2.start()
            break
    chunk = text[start:end].strip()
    chunk = re.sub(r"\n{3,}", "\n\n", chunk)
    # These regex sections are now only lightweight metadata (the RAG index chunks
    # the full text instead), so keep a generous cap just to bound pathological output.
    return chunk[:20000] if chunk else None
