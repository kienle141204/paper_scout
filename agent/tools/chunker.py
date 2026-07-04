from __future__ import annotations

import re
from dataclasses import dataclass

from agent.tools.mineru_parser import Block, canonical_section


@dataclass
class Chunk:
    text: str
    section: str
    chunk_index: int
    token_count: int
    page: int | None = None
    block_type: str = "text"


_SECTION_HEAD = re.compile(
    r"^\s*(abstract|introduction|related\s+work|background|preliminaries|"
    r"method(?:ology)?s?|approach|model|framework|"
    r"experiment(?:al)?(?:\s+setup)?|evaluation|results?|analysis|"
    r"ablation|discussion|conclusion|references?|appendix)\s*$",
    re.I | re.M,
)

_CHAR_PER_TOKEN = 4  # rough approximation


def _tok(text: str) -> int:
    return max(1, len(text) // _CHAR_PER_TOKEN)


def split_text(
    text: str,
    *,
    chunk_tokens: int = 400,
    overlap_tokens: int = 80,
    min_tokens: int = 40,
) -> list[Chunk]:
    """Split *text* into overlapping chunks, tracking the current section name."""
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]

    chunks: list[Chunk] = []
    section = "body"
    buf: list[str] = []
    buf_tok = 0
    idx = 0

    def flush() -> None:
        nonlocal idx, buf, buf_tok
        if not buf:
            return
        joined = " ".join(buf)
        if _tok(joined) >= min_tokens:
            chunks.append(Chunk(
                text=joined, section=section,
                chunk_index=idx, token_count=_tok(joined),
            ))
            idx += 1
        buf.clear()
        buf_tok = 0

    def add_overlap() -> None:
        if not chunks:
            return
        words = chunks[-1].text.split()
        tail = words[-(overlap_tokens * _CHAR_PER_TOKEN):]
        if tail:
            overlap_text = " ".join(tail)
            buf.append(overlap_text)
            buf_tok = _tok(overlap_text)

    for para in paragraphs:
        if _SECTION_HEAD.match(para) and len(para) < 80:
            flush()
            section = para.strip().lower().split()[0]
            continue

        ptok = _tok(para)

        if ptok > chunk_tokens:
            # Oversized paragraph — split by sentences
            for sent in re.split(r"(?<=[.!?])\s+", para):
                st = _tok(sent)
                if buf_tok + st > chunk_tokens:
                    flush()
                    add_overlap()
                buf.append(sent)
                buf_tok += st
        else:
            if buf_tok + ptok > chunk_tokens:
                flush()
                add_overlap()
            buf.append(para)
            buf_tok += ptok

    flush()
    return chunks


def make_chunks(
    *,
    abstract: str | None = None,
    method: str | None = None,
    experiments: str | None = None,
    full_text: str | None = None,
) -> list[Chunk]:
    """Build chunks for the RAG index.

    Prefers the *full* PDF text so the whole paper is indexed — ``split_text``
    assigns a section label per chunk from inline headings, so no section is
    dropped. If ``abstract`` is supplied but not already present at the head of
    ``full_text``, it is prepended as its own chunk. Falls back to the coarse
    ``method``/``experiments`` sections only when no full text is available.
    """
    if full_text and full_text.strip():
        result: list[Chunk] = []

        head = full_text[:2000].lower()
        if abstract and abstract.strip() and abstract.strip()[:80].lower() not in head:
            for c in split_text(abstract):
                result.append(Chunk(
                    text=c.text, section="abstract",
                    chunk_index=len(result), token_count=c.token_count,
                ))

        for c in split_text(full_text):
            result.append(Chunk(
                text=c.text, section=c.section,
                chunk_index=len(result), token_count=c.token_count,
            ))
        return result

    # No full text — fall back to whatever coarse sections we have (incl. abstract).
    named = [("abstract", abstract), ("method", method), ("experiments", experiments)]
    available = [(name, text) for name, text in named if text]
    result = []
    for section_name, text in available:
        for c in split_text(text):
            result.append(Chunk(
                text=c.text, section=section_name,
                chunk_index=len(result), token_count=c.token_count,
            ))
    return result


def _html_table_to_text(html: str) -> str:
    """Flatten an HTML table into a readable pipe-separated grid for embedding/LLM."""
    s = re.sub(r"(?i)</t[dh]>", " | ", html)
    s = re.sub(r"(?i)</tr>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"[ \t]*\|[ \t]*\n", "\n", s)
    s = re.sub(r"\n{2,}", "\n", s)
    return s.strip()


def make_chunks_from_blocks(
    blocks: list[Block],
    *,
    abstract: str | None = None,
    chunk_tokens: int = 400,
) -> list[Chunk]:
    """Structure-aware chunking over MinerU blocks.

    - Groups body text under the nearest canonical section heading (see
      ``canonical_section``), splitting long runs to ~``chunk_tokens`` with overlap.
    - Emits each table as a single atomic chunk (caption + flattened grid) tagged
      ``block_type="table"`` so numeric results stay intact for retrieval.
    - Inlines equations (LaTeX) into the surrounding text run.
    - Each chunk carries the page it starts on for page-level citations.
    """
    result: list[Chunk] = []
    idx = 0
    section = "body"
    buf: list[str] = []
    buf_page: int | None = None

    def flush_text() -> None:
        nonlocal idx, buf, buf_page
        if not buf:
            return
        joined = "\n\n".join(buf)
        for c in split_text(joined, chunk_tokens=chunk_tokens):
            result.append(Chunk(
                text=c.text, section=section, chunk_index=idx,
                token_count=c.token_count, page=buf_page, block_type="text",
            ))
            idx += 1
        buf = []
        buf_page = None

    def push(text: str, page: int) -> None:
        nonlocal buf_page
        if buf_page is None:
            buf_page = page
        buf.append(text)

    for b in blocks:
        if b.type == "title":
            sec = canonical_section(b.text)
            if sec:
                flush_text()
                section = sec
            elif b.text.strip():  # sub-heading — keep as text lead-in
                push(b.text.strip(), b.page)
            continue

        if b.type == "table":
            flush_text()
            body = _html_table_to_text(b.table_html) if b.table_html else b.text
            parts = [p for p in (b.caption, body) if p and p.strip()]
            text = "\n".join(parts).strip()
            if text:
                result.append(Chunk(
                    text=text, section=section, chunk_index=idx,
                    token_count=_tok(text), page=b.page, block_type="table",
                ))
                idx += 1
            continue

        if b.type == "equation":
            eq = (b.latex or b.text or "").strip()
            if eq:
                push(f"$$ {eq} $$", b.page)
            continue

        # text / image caption
        if b.text.strip():
            push(b.text.strip(), b.page)

    flush_text()

    # Prepend abstract if MinerU produced content but no abstract section. When there
    # are no content blocks at all, return empty so the caller uses its abstract-only
    # fallback (and labels the source correctly).
    if result and abstract and abstract.strip() and not any(c.section == "abstract" for c in result):
        prepend = [
            Chunk(text=c.text, section="abstract", chunk_index=0,
                  token_count=c.token_count, page=0, block_type="text")
            for c in split_text(abstract)
        ]
        result = prepend + result

    for i, c in enumerate(result):
        c.chunk_index = i
    return result
