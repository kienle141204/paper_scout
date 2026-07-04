"""Paper ingestion pipeline: fetch PDF -> parse -> chunk -> embed -> store.

Moved out of backend/api.py near-verbatim. Stays FastAPI-free — raises
IngestError on failure; the API boundary converts that to HTTPException.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from agent.config import Config
from agent.core.model_registry import resolve_embedding
from agent.tools import rag_store
from agent.tools.chunker import Chunk, make_chunks, split_text
from agent.tools.pdf_fetcher import fetch_pdf
from agent.tools.pdf_parser import parse_pdf


class IngestError(Exception):
    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class IngestRequest:
    paper_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = field(default_factory=list)
    url: str | None = None
    pdf_url: str | None = None
    conference: str | None = None
    year: int | None = None
    force: bool = False


@dataclass
class IngestResult:
    paper_id: str
    already_done: bool
    chunk_count: int
    source: str

    def to_response_dict(self) -> dict:
        return {
            "paper_id": self.paper_id,
            "already_done": self.already_done,
            "chunk_count": self.chunk_count,
            "source": self.source,
        }


# Sub-batch size for embedding. Reading the whole PDF can produce 100s of chunks;
# sending them all in one request risks exceeding the provider's per-request limits.
_EMBED_BATCH_SIZE = 64


def _embed_texts(texts: list[str], cfg: Config) -> list[list[float]]:
    spec = resolve_embedding(cfg)
    if spec.provider == "openai":
        from agent.tools.openai_embeddings import embed_batch
        out: list[list[float]] = []
        for i in range(0, len(texts), _EMBED_BATCH_SIZE):
            batch = texts[i : i + _EMBED_BATCH_SIZE]
            out.extend(embed_batch(texts=batch, model=spec.model, base_url=spec.base_url))
        return out
    from agent.tools.gemini_embeddings import embed as gemini_embed
    from concurrent.futures import ThreadPoolExecutor
    base_url = spec.base_url or "https://generativelanguage.googleapis.com/v1beta"
    # Gemini embeds one text per call; cap the pool so huge papers don't spawn 100s of threads.
    with ThreadPoolExecutor(max_workers=min(max(len(texts), 1), 8)) as pool:
        return list(pool.map(lambda t: gemini_embed(text=t, model=spec.model, base_url=base_url), texts))


def ingest_paper(req: IngestRequest, *, cfg: Config) -> IngestResult:
    """Download, parse, chunk, embed and store a paper for RAG.

    Idempotent — skips processing if the paper is already ingested unless
    req.force is set. Falls back to abstract-only chunking if the PDF cannot
    be fetched.
    """
    if not rag_store.is_configured():
        raise IngestError(503, "Vector store (Supabase) chưa được cấu hình.")

    if not req.force and rag_store.is_ingested(req.paper_id):
        return IngestResult(paper_id=req.paper_id, already_done=True, chunk_count=-1, source="cached")

    # 1. Try to fetch + parse PDF. Prefer the shared Supabase cache (one download
    #    serves both the Reader iframe and this ingest); fall back to a live fetch
    #    and populate the cache so the next open is instant.
    from agent.tools import pdf_store
    import tempfile
    from pathlib import Path

    source = "abstract"
    chunks: list[Chunk] = []
    pdf_path = None
    try:
        cached = pdf_store.download_pdf(req.paper_id)
        if cached:
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")
            tmp.write(cached)
            tmp.close()
            pdf_path = Path(tmp.name)
        elif req.pdf_url or req.url:
            pdf_path = fetch_pdf(req.pdf_url or req.url, title=req.title)
            if pdf_path:
                try:
                    pdf_store.store_pdf_bytes(req.paper_id, pdf_path.read_bytes())
                except Exception:
                    pass
        if pdf_path:
            parsed = parse_pdf(pdf_path)  # max_pages=None → reads every page
            # Index the full paper text (all pages, all sections). split_text tags
            # each chunk with its section, so nothing beyond abstract/method is lost.
            chunks = make_chunks(
                full_text=parsed.text,
                abstract=parsed.abstract or req.abstract,
            )
            if chunks:
                source = "pdf"
    except Exception:
        chunks = []
    finally:
        if pdf_path and pdf_path.exists():
            try:
                pdf_path.unlink()
            except Exception:
                pass

    # 2. Fall back to abstract-only if PDF failed
    if not chunks and req.abstract:
        abstract_chunks = split_text(req.abstract)
        if not abstract_chunks:
            abstract_chunks = [Chunk(text=req.abstract, section="abstract", chunk_index=0, token_count=len(req.abstract) // 4)]
        chunks = abstract_chunks
        source = "abstract"

    if not chunks:
        raise IngestError(422, "Không thể tạo chunks — không có PDF hay abstract.")

    # 3. Embed all chunks
    texts = [c.text for c in chunks]
    try:
        embeddings = _embed_texts(texts, cfg)
    except Exception as e:
        raise IngestError(502, f"Lỗi embedding: {e}")

    # 4. Store
    rows = [
        {"chunk_index": c.chunk_index, "section": c.section, "text": c.text, "token_count": c.token_count, "embedding": embeddings[i]}
        for i, c in enumerate(chunks)
    ]
    rag_store.store_chunks(req.paper_id, rows)

    return IngestResult(paper_id=req.paper_id, already_done=False, chunk_count=len(chunks), source=source)
