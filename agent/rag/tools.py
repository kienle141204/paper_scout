"""RAG Agent atomic tools — retrieve (hybrid vector+BM25), rerank (cross-encoder),
get_section, generate (with the untrusted-evidence safety wrapper), check_grounded.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from agent.config import Config
from agent.core.governor import DegradeLevel
from agent.core.llm_json import llm_json
from agent.core.model_registry import embed_one, resolve
from agent.tools import rag_store
from agent.tools.prompts import PAPER_RAG_ANSWERER, PAPER_RAG_VERIFIER, RAG_EVIDENCE_WRAPPER

# ── BM25 index cache (one per paper_id, built once per process — the chunk
# corpus is static after ingestion, so this is a cheap one-time cost) ────────
_bm25_lock = threading.Lock()
_bm25_cache: dict[str, tuple[Any, list[dict[str, Any]]]] = {}


def _get_bm25_index(paper_id: str):
    if paper_id in _bm25_cache:
        return _bm25_cache[paper_id]
    with _bm25_lock:
        if paper_id in _bm25_cache:
            return _bm25_cache[paper_id]
        chunks = rag_store.get_all_chunks(paper_id)
        if not chunks:
            _bm25_cache[paper_id] = (None, [])
            return _bm25_cache[paper_id]
        try:
            from rank_bm25 import BM25Okapi
            tokenized = [c["text"].lower().split() for c in chunks]
            index = BM25Okapi(tokenized)
        except Exception:
            index = None
        _bm25_cache[paper_id] = (index, chunks)
        return _bm25_cache[paper_id]


def _bm25_search(query: str, paper_id: str, k: int) -> list[dict[str, Any]]:
    index, chunks = _get_bm25_index(paper_id)
    if index is None or not chunks:
        return []
    scores = index.get_scores(query.lower().split())
    ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
    return [{**c, "bm25_score": float(s)} for s, c in ranked[:k] if s > 0]


def retrieve(query: str, paper_id: str, k: int, *, cfg: Config) -> list[dict[str, Any]]:
    """Hybrid retrieval: vector cosine-similarity search + BM25 sparse search,
    merged via reciprocal rank fusion (RRF). Vector-only fallback if BM25 is
    unavailable (e.g. rank_bm25 not installed or paper not yet chunked).
    """
    try:
        query_emb = embed_one(query, cfg)
        vector_hits = rag_store.retrieve_chunks(paper_id, query_emb, top_k=max(k, 8))
    except Exception:
        vector_hits = []

    bm25_hits = _bm25_search(query, paper_id, max(k, 8))

    if not bm25_hits:
        return vector_hits[:k]

    # Reciprocal rank fusion: score = sum(1 / (60 + rank)) across each list.
    rrf_scores: dict[int, float] = {}
    chunk_by_idx: dict[int, dict[str, Any]] = {}
    for rank, c in enumerate(vector_hits):
        idx = c["chunk_index"]
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (60 + rank)
        chunk_by_idx[idx] = c
    for rank, c in enumerate(bm25_hits):
        idx = c["chunk_index"]
        rrf_scores[idx] = rrf_scores.get(idx, 0.0) + 1.0 / (60 + rank)
        chunk_by_idx.setdefault(idx, c)

    ranked_idx = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
    return [chunk_by_idx[idx] for idx, _ in ranked_idx[:k]]


def get_section(paper_id: str, name: str, k: int = 3) -> list[dict[str, Any]]:
    return rag_store.retrieve_by_section(paper_id, name, top_k=k)


# ── Reranker: real cross-encoder, lazily loaded once per process ───────────
_reranker_lock = threading.Lock()
_reranker_model = None
_reranker_unavailable = False


def _get_reranker():
    global _reranker_model, _reranker_unavailable
    if _reranker_model is not None or _reranker_unavailable:
        return _reranker_model
    with _reranker_lock:
        if _reranker_model is not None or _reranker_unavailable:
            return _reranker_model
        try:
            from sentence_transformers import CrossEncoder
            _reranker_model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
        except Exception:
            _reranker_unavailable = True
            _reranker_model = None
        return _reranker_model


def rerank(chunks: list[dict[str, Any]], query: str, *, cfg: Config) -> list[dict[str, Any]]:
    """Cross-encoder rerank. Falls back to a stable pass-through sort by the
    chunk's existing similarity/bm25 score if the model can't be loaded
    (e.g. sentence-transformers not installed) — the architecture keeps this
    seam regardless, so a real reranker can always be dropped in later.
    """
    if not chunks:
        return chunks
    model = _get_reranker()
    if model is None:
        return sorted(chunks, key=lambda c: c.get("similarity") or c.get("bm25_score") or 0, reverse=True)
    try:
        pairs = [(query, c["text"]) for c in chunks]
        scores = model.predict(pairs)
        ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
        return [c for _, c in ranked]
    except Exception:
        return chunks


@dataclass
class AnswerResult:
    answer: str
    citations: list[dict] = field(default_factory=list)
    chunks_used: list[dict] = field(default_factory=list)
    confidence: str = "medium"
    coverage: str = "partial"
    plan_meta: dict = field(default_factory=dict)
    warning: str | None = None


def _chunk_tag(c: dict[str, Any]) -> str:
    """Render a chunk's provenance for the evidence header, e.g. '(METHOD, p.4)' or
    '(RESULTS, p.6, TABLE)'."""
    parts = [c.get("section", "body").upper()]
    page = c.get("page")
    if page is not None:
        parts.append(f"p.{int(page) + 1}")  # 0-based index -> human page number
    if c.get("block_type") == "table":
        parts.append("TABLE")
    return "(" + ", ".join(parts) + ")"


def generate(
    question: str,
    chunks: list[dict[str, Any]],
    history: list[dict],
    *,
    cfg: Config,
    degrade: DegradeLevel = DegradeLevel.NONE,
    component: str = "skill",
) -> AnswerResult:
    """Wraps PAPER_RAG_ANSWERER. Wraps the evidence chunks in RAG_EVIDENCE_WRAPPER
    so the model treats them as untrusted data, never as instructions — the
    project's main defense against indirect prompt injection from PDF content.
    """
    context_parts = [f"[{i}] {_chunk_tag(c)}\n{c['text']}" for i, c in enumerate(chunks, 1)]
    evidence = RAG_EVIDENCE_WRAPPER.format(evidence="\n\n".join(context_parts))

    messages = [{"role": m.get("role"), "content": m.get("content")} for m in history[-8:]]
    messages.append({"role": "user", "content": f"{evidence}\n\n---\nQuestion: {question}"})

    spec = resolve(component, cfg, degrade=degrade)
    data = llm_json(PAPER_RAG_ANSWERER, "", provider=spec.provider, model=spec.model, base_url=spec.base_url, messages=messages)

    chunk_index_set = {c["chunk_index"] for c in chunks}
    chunks_by_idx = {c["chunk_index"]: c for c in chunks}
    citations = []
    for cite in (data.get("citations") or []):
        idx = cite.get("chunk_index")
        matched = chunks_by_idx.get(idx)
        citations.append({
            "ref": cite.get("ref"),
            "chunk_index": idx,
            "section": cite.get("section") or (matched or {}).get("section", "body"),
            "page": (matched or {}).get("page"),
            "quote": str(cite.get("quote") or "")[:160],
            "valid": idx in chunk_index_set,
        })

    return AnswerResult(
        answer=str(data.get("answer") or "").strip(),
        citations=citations,
        chunks_used=chunks,
        confidence=str(data.get("confidence") or "medium"),
        coverage=str(data.get("coverage") or "partial"),
    )


@dataclass
class GroundingResult:
    is_grounded: bool = True
    hallucination_risk: str = "low"
    issues: list[str] = field(default_factory=list)
    refined_answer: str | None = None


def check_grounded(answer: str, chunks: list[dict[str, Any]], *, cfg: Config, question: str = "") -> GroundingResult:
    context_str = "\n\n".join(f"[{i}] {c['text']}" for i, c in enumerate(chunks, 1))
    spec = resolve("grounding", cfg)
    try:
        data = llm_json(
            PAPER_RAG_VERIFIER,
            f"Original question: {question}\n\nGenerated answer:\n{answer}\n\nEvidence chunks:\n{context_str}",
            provider=spec.provider, model=spec.model, base_url=spec.base_url,
        )
    except Exception:
        return GroundingResult()

    if not data:
        return GroundingResult()

    return GroundingResult(
        is_grounded=bool(data.get("is_grounded", True)),
        hallucination_risk=str(data.get("hallucination_risk") or "low"),
        issues=list(data.get("issues") or []),
        refined_answer=data.get("refined_answer") or None,
    )
