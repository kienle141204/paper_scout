from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from agent.config import DEFAULT_CONFIG_PATH, load_config
from agent.tools.abstract_tools import summarize_abstract, translate_abstract_vi
from agent.tools.query_parse import parse_query
from agent.tools.prompts import CHAT_AGENT
from agent.tools.library import (
    DEFAULT_DB_PATH,
    add_paper,
    delete_paper,
    get_profile,
    list_papers,
    set_profile,
    update_note,
    update_tags,
)
from agent.tools.major_venues import MAJOR_VENUES, major_search
from agent.tools.paper_cache import get_cached_paper, is_configured, upsert_paper
from agent.tools.paper_detail import fetch_detail
from agent.tools.paper_search import search_papers, search_by_invitation
from agent.tools.relevance import score_batch
from agent.tools.web_fetch import fetch_paper_from_url

# ── Conference metadata ───────────────────────────────────────────────────────

_CONFERENCE_META: dict[str, tuple[str, list[str], str]] = {
    "NeurIPS": ("Neural Information Processing Systems", ["ML", "AI", "Deep Learning"], "https://neurips.cc"),
    "ICML": ("International Conference on Machine Learning", ["ML", "Deep Learning"], "https://icml.cc"),
    "ICLR": ("International Conference on Learning Representations", ["ML", "Deep Learning", "Representation Learning"], "https://iclr.cc"),
    "CVPR": ("Computer Vision and Pattern Recognition", ["Computer Vision", "ML"], "https://cvpr.thecvf.com"),
    "ICCV": ("International Conference on Computer Vision", ["Computer Vision", "ML"], "https://iccv.thecvf.com"),
    "ECCV": ("European Conference on Computer Vision", ["Computer Vision"], "https://eccv.ecva.net"),
    "ACL": ("Association for Computational Linguistics", ["NLP", "Computational Linguistics"], "https://aclanthology.org"),
    "EMNLP": ("Empirical Methods in NLP", ["NLP", "ML"], "https://aclanthology.org"),
    "NAACL": ("North American Chapter of ACL", ["NLP"], "https://aclanthology.org"),
    "AAAI": ("AAAI Conference on Artificial Intelligence", ["AI", "ML"], "https://aaai.org"),
    "IJCAI": ("International Joint Conference on AI", ["AI", "ML"], "https://ijcai.org"),
    "KDD": ("Knowledge Discovery and Data Mining", ["Data Mining", "ML"], "https://kdd.org"),
    "WWW": ("The Web Conference", ["Web", "Information Retrieval", "ML"], "https://www2024.thewebconf.org"),
    "SIGIR": ("Special Interest Group on Information Retrieval", ["Information Retrieval", "NLP"], "https://sigir.org"),
    "ICSE": ("International Conference on Software Engineering", ["Software Engineering"], "https://www.icse-conferences.org"),
}

_CONF_VENUE_ALIASES: dict[str, list[str]] = {
    "NeurIPS": ["NeurIPS", "Neural Information Processing Systems", "NIPS"],
    "ICML": ["ICML", "International Conference on Machine Learning"],
    "ICLR": ["ICLR", "International Conference on Learning Representations"],
    "CVPR": ["CVPR", "Computer Vision and Pattern Recognition"],
    "ICCV": ["ICCV", "International Conference on Computer Vision"],
    "ECCV": ["ECCV", "European Conference on Computer Vision"],
    "ACL": ["ACL", "Association for Computational Linguistics"],
    "EMNLP": ["EMNLP", "Empirical Methods in Natural Language Processing"],
    "NAACL": ["NAACL", "North American Chapter of the Association for Computational Linguistics"],
    "AAAI": ["AAAI", "AAAI Conference on Artificial Intelligence"],
    "IJCAI": ["IJCAI", "International Joint Conference on Artificial Intelligence"],
    "KDD": ["KDD", "Knowledge Discovery and Data Mining"],
    "WWW": ["WWW", "The Web Conference"],
    "SIGIR": ["SIGIR"],
    "ICSE": ["ICSE", "International Conference on Software Engineering"],
}


def _normalize_venue(venue: str | None) -> str | None:
    if not venue:
        return None
    v = venue.upper()
    for key, aliases in _CONF_VENUE_ALIASES.items():
        if any(alias.upper() in v for alias in aliases):
            return key
    return venue


app = FastAPI(title="paper-agent-backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _cfg(config_path: str | None) -> Any:
    return load_config(Path(config_path) if config_path else DEFAULT_CONFIG_PATH)


class SearchRequest(BaseModel):
    query: str
    venue: str
    year: int
    limit: int = 10
    offset: int = 0
    accepted_only: bool = False
    config_path: str | None = None


@app.post("/search")
def search(req: SearchRequest) -> dict[str, Any]:
    try:
        raw = search_papers(
            query=req.query,
            venue_key=req.venue,
            year=req.year,
            limit=req.limit,
            offset=req.offset,
            accepted_only=req.accepted_only,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    has_more = len(raw) > req.limit
    return {"papers": [p.to_dict() for p in raw[: req.limit]], "has_more": has_more, "offset": req.offset}


class MajorSearchRequest(BaseModel):
    venue: str = Field(description=f"One of: {', '.join(sorted(MAJOR_VENUES))}")
    query: str
    year: int | None = None
    limit: int = 10
    offset: int = 0
    accepted_only: bool = False
    config_path: str | None = None


@app.post("/major-search")
def major_search_api(req: MajorSearchRequest) -> dict[str, Any]:
    try:
        raw = major_search(
            venue_key=req.venue,
            query=req.query,
            year=req.year,
            limit=req.limit,
            offset=req.offset,
            accepted_only=req.accepted_only,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    has_more = len(raw) > req.limit
    return {"papers": [p.to_dict() for p in raw[: req.limit]], "has_more": has_more, "offset": req.offset}


# ── Frontend-facing API endpoints ─────────────────────────────────────────────

@app.get("/api/conferences")
def api_conferences() -> dict[str, Any]:
    confs = [
        {"name": k, "full_name": v[0], "areas": v[1], "url": v[2]}
        for k, v in _CONFERENCE_META.items()
    ]
    return {"conferences": confs}


class PaperViewRequest(BaseModel):
    paper_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    url: str | None = None
    source: str | None = None
    conference: str | None = None
    config_path: str | None = None


@app.post("/api/papers/view")
def api_papers_view(req: PaperViewRequest) -> dict[str, Any]:
    """
    Ghi nhận lượt xem paper. Trả về thông tin đầy đủ kèm abstract_vi (từ cache hoặc dịch mới).
    Cache được lưu trên Supabase để tái sử dụng lần sau.
    """
    cfg = _cfg(req.config_path)

    # 1. Thử lấy từ cache Supabase
    cached = get_cached_paper(req.paper_id)
    if cached and cached.get("abstract_vi"):
        return {
            "paper_id": req.paper_id,
            "abstract_vi": cached["abstract_vi"],
            "from_cache": True,
        }

    # 2. Cache miss hoặc chưa có abstract_vi → dịch bằng LLM
    abstract_vi: str | None = None
    if req.abstract:
        try:
            provider = cfg.llm_provider
            model = cfg.openai_model if provider == "openai" else cfg.gemini_model
            base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url
            abstract_vi = translate_abstract_vi(
                text=req.abstract, provider=provider, model=model, base_url=base_url
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Lỗi dịch: {e}")

    # 3. Lưu vào Supabase (fire-and-forget, lỗi không ảnh hưởng response)
    upsert_paper({
        "paper_id": req.paper_id,
        "title": req.title,
        "abstract_en": req.abstract,
        "abstract_vi": abstract_vi,
        "authors": req.authors,
        "keywords": req.keywords,
        "venue": req.venue,
        "year": req.year,
        "url": req.url,
        "source": req.source or "openreview",
    })

    return {
        "paper_id": req.paper_id,
        "abstract_vi": abstract_vi,
        "from_cache": False,
    }


@app.get("/api/cache/status")
def api_cache_status() -> dict[str, Any]:
    return {"supabase_configured": is_configured()}


class PaperSearchRequest(BaseModel):
    query: str
    conferences: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    language: str = "vi"
    limit: int = Field(default=20, ge=1, le=50)


_S2_BASE = "https://api.semanticscholar.org/graph/v1"
_S2_FIELDS = "paperId,title,abstract,authors,year,venue,externalIds,openAccessPdf,citationCount"
_S2_API_KEY: str = os.environ.get("SEMANTIC_SCHOLAR_API_KEY", "")


def _s2_headers() -> dict[str, str]:
    return {"x-api-key": _S2_API_KEY} if _S2_API_KEY else {}


def _s2_retriable(exc: Exception) -> bool:
    if isinstance(exc, requests.HTTPError):
        return exc.response is not None and exc.response.status_code in (429, 500, 503)
    return isinstance(exc, (requests.ConnectionError, requests.Timeout))


@retry(
    retry=retry_if_exception(_s2_retriable),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=8),
    reraise=True,
)
def _call_s2(params: dict[str, Any]) -> list[dict[str, Any]]:
    resp = requests.get(f"{_S2_BASE}/paper/search", params=params, headers=_s2_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json().get("data", [])


def _paper_from_s2(item: dict[str, Any]) -> dict[str, Any]:
    ext = item.get("externalIds") or {}
    pdf = item.get("openAccessPdf") or {}
    url = pdf.get("url") or (f"https://doi.org/{ext['DOI']}" if ext.get("DOI") else None)
    url = url or f"https://www.semanticscholar.org/paper/{item['paperId']}"
    return {
        "paper_id": item["paperId"],
        "title": item.get("title") or "",
        "abstract": item.get("abstract"),
        "summary": None,
        "title_vi": None,
        "authors": [
            {"name": a.get("name", ""), "author_id": a.get("authorId")}
            for a in (item.get("authors") or [])
        ],
        "year": item.get("year"),
        "venue": item.get("venue") or "",
        "conference": _normalize_venue(item.get("venue")),
        "url": url,
        "citation_count": item.get("citationCount"),
        "relevance_score": None,
        "key_contributions": [],
        "tags": [],
    }


def _score_papers(query: str, papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute embedding-based relevance scores in one batched API call, then sort descending."""
    texts = [
        f"{p.get('title', '')}. {(p.get('abstract') or '')[:500]}"
        for p in papers
    ]
    try:
        cfg = _cfg(None)
        provider = cfg.llm_provider
        model = "text-embedding-3-small" if provider == "openai" else "gemini-embedding-001"
        base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url
        scores = score_batch(query=query, texts=texts, provider=provider, model=model, base_url=base_url)
        for paper, score in zip(papers, scores):
            paper["relevance_score"] = round(score, 4)
        papers.sort(key=lambda p: p.get("relevance_score") or 0, reverse=True)
    except Exception:
        pass  # embedding failed — keep papers as-is with relevance_score=None
    return papers


def _enrich_citation_counts(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Best-effort: batch-lookup citation counts from S2 for papers that lack them.

    Uses the S2 bulk paper endpoint. Failures are silently ignored — papers keep
    citation_count=None rather than crashing the response.
    """
    missing_idx = [i for i, p in enumerate(papers) if p.get("citation_count") is None]
    if not missing_idx:
        return papers

    # Build ID list: prefer paper_id (S2 format), else skip (S2 batch needs S2 IDs)
    ids = [papers[i]["paper_id"] for i in missing_idx if papers[i].get("paper_id")]
    if not ids:
        return papers

    try:
        resp = requests.post(
            f"{_S2_BASE}/paper/batch",
            headers=_s2_headers(),
            params={"fields": "paperId,citationCount"},
            json={"ids": ids[:100]},  # S2 batch limit is 500 but keep it conservative
            timeout=15,
        )
        if not resp.ok:
            return papers
        batch: list[dict[str, Any]] = resp.json()
        cite_map: dict[str, int] = {}
        for item in batch:
            if item and item.get("paperId") and item.get("citationCount") is not None:
                cite_map[item["paperId"]] = item["citationCount"]
        for i in missing_idx:
            pid = papers[i].get("paper_id", "")
            if pid in cite_map:
                papers[i] = {**papers[i], "citation_count": cite_map[pid]}
    except Exception:
        pass  # enrichment is best-effort

    return papers


def _search_fallback(req: PaperSearchRequest) -> list[dict[str, Any]]:
    """Fallback: search OpenReview across recent major conferences."""
    import datetime

    current_year = datetime.datetime.now().year
    venue_keys = [c.lower() for c in req.conferences] if req.conferences else ["iclr", "neurips", "icml"]
    years: list[int] = []
    if req.year_from or req.year_to:
        y_start = req.year_from or current_year - 3
        y_end = req.year_to or current_year
        years = list(range(y_start, y_end + 1))
    else:
        years = [current_year, current_year - 1]

    papers: list[dict[str, Any]] = []
    seen: set[str] = set()
    for venue_key in venue_keys:
        for year in sorted(years, reverse=True):
            try:
                results = search_papers(
                    query=req.query,
                    venue_key=venue_key,
                    year=year,
                    limit=req.limit * 2,
                    accepted_only=True,
                )
            except ValueError:
                continue
            for p in results:
                if not p.abstract:
                    continue
                key = p.id or p.title
                if key in seen:
                    continue
                seen.add(key)
                venue = p.venue or ""
                conference = _normalize_venue(venue) or venue_key.upper()
                papers.append({
                    "paper_id": p.id or "",
                    "title": p.title,
                    "abstract": p.abstract,
                    "summary": None,
                    "title_vi": None,
                    "authors": [{"name": a} for a in p.authors],
                    "year": p.year,
                    "venue": venue,
                    "conference": conference,
                    "url": p.url,
                    "citation_count": None,
                    "relevance_score": None,
                    "key_contributions": [],
                    "tags": list(p.keywords),
                })
                if len(papers) >= req.limit:
                    return _enrich_citation_counts(papers)
    return _enrich_citation_counts(papers)


@app.post("/api/papers/search")
def api_papers_search(req: PaperSearchRequest) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": req.query,
        "fields": _S2_FIELDS,
        "limit": min(req.limit * 3, 100),
    }

    if req.year_from and req.year_to:
        params["year"] = f"{req.year_from}-{req.year_to}"
    elif req.year_from:
        params["year"] = f"{req.year_from}-"
    elif req.year_to:
        params["year"] = f"-{req.year_to}"

    # Only send venue filter to S2 for single-conference searches
    if len(req.conferences) == 1:
        aliases = _CONF_VENUE_ALIASES.get(req.conferences[0], [req.conferences[0]])
        params["venue"] = ",".join(aliases)

    raw: list[dict[str, Any]] | None = None
    try:
        raw = _call_s2(params)
    except requests.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        if status == 429:
            # Rate limited after retries — fall back to OpenAlex/arXiv
            papers = _search_fallback(req)
            papers = _score_papers(req.query, papers)
            return {"papers": papers, "total": len(papers), "query": req.query}
        raise HTTPException(status_code=502, detail="Nguồn dữ liệu phản hồi lỗi. Vui lòng thử lại sau.")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Không thể kết nối nguồn dữ liệu. Vui lòng kiểm tra mạng.")

    papers: list[dict[str, Any]] = []
    for item in raw:
        if not item.get("abstract"):
            continue
        p = _paper_from_s2(item)
        if req.conferences and p["conference"] not in req.conferences:
            continue
        papers.append(p)
        if len(papers) >= req.limit:
            break

    papers = _score_papers(req.query, papers)
    return {"papers": papers, "total": len(papers), "query": req.query}


# ── Conversational chat endpoint ──────────────────────────────────────────────

_MAX_CHAT_MESSAGES = 30  # truncate oldest turns beyond this to stay within context window


class ChatMessageModel(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class PaperSummaryModel(BaseModel):
    paper_id: str
    title: str
    conference: str | None = None
    year: int | None = None


class ChatContextModel(BaseModel):
    keywords: str | None = None
    venues: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    papers_shown: list[PaperSummaryModel] = Field(default_factory=list)


class ChatSearchParams(BaseModel):
    keywords: str
    venues: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    limit: int = 20


class ChatFilterParams(BaseModel):
    exclude_keywords: list[str] = Field(default_factory=list)
    include_only_keywords: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    venues: list[str] | None = None


class ChatRequestModel(BaseModel):
    messages: list[ChatMessageModel] = Field(min_length=1)
    context: ChatContextModel = Field(default_factory=ChatContextModel)
    session_id: str | None = None  # frontend-generated UUID; backend does not persist this
    config_path: str | None = None


class ChatResponseModel(BaseModel):
    reply: str
    action: Literal["search", "clarify", "filter", "done"]
    search_params: ChatSearchParams | None = None
    filter_params: ChatFilterParams | None = None
    follow_up_question: str | None = None


def _build_context_summary(ctx: ChatContextModel) -> str:
    """Produce a short human-readable summary of the current search context for the LLM."""
    parts: list[str] = []
    if ctx.keywords:
        parts.append(f"Current keywords: {ctx.keywords}")
    if ctx.venues:
        parts.append(f"Active venues: {', '.join(ctx.venues)}")
    if ctx.year_from or ctx.year_to:
        yr = f"{ctx.year_from or ''}–{ctx.year_to or ''}"
        parts.append(f"Year range: {yr}")
    if ctx.papers_shown:
        titles = [f"- {p.title[:80]} ({p.conference or 'N/A'} {p.year or '?'})" for p in ctx.papers_shown[:5]]
        parts.append("Papers currently shown (first 5):\n" + "\n".join(titles))
    return "\n".join(parts) if parts else "No active search context yet."


@app.post("/api/chat", response_model=ChatResponseModel)
def api_chat(req: ChatRequestModel) -> ChatResponseModel:
    """Stateless conversational endpoint.

    The full conversation history and current search context are supplied in
    every request — the backend stores nothing between calls.
    """
    cfg = _cfg(req.config_path)
    provider = cfg.llm_provider
    model = cfg.openai_model if provider == "openai" else cfg.gemini_model
    base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url

    # Trim history to avoid overflowing the context window
    raw_messages = req.messages[-_MAX_CHAT_MESSAGES:]

    # Inject context summary as a hidden system-level note before the last user turn
    context_note = f"\n\n[Current search context]\n{_build_context_summary(req.context)}"
    llm_messages: list[dict[str, str]] = []
    for i, msg in enumerate(raw_messages):
        if i == len(raw_messages) - 1 and msg.role == "user":
            llm_messages.append({"role": "user", "content": msg.content + context_note})
        else:
            llm_messages.append({"role": msg.role, "content": msg.content})

    # Call LLM
    try:
        from agent.tools.llm_text import generate_text
        raw = generate_text(
            provider=provider,
            system=CHAT_AGENT,
            user="",  # unused when messages is provided
            model=model,
            base_url=base_url,
            messages=llm_messages,
        )
    except Exception as e:
        return ChatResponseModel(
            reply="Xin lỗi, tôi gặp sự cố khi kết nối AI. Vui lòng thử lại.",
            action="clarify",
        )

    # Parse JSON response
    import re as _re
    import json as _json
    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if not m:
        return ChatResponseModel(
            reply=raw or "Tôi chưa hiểu rõ yêu cầu. Bạn có thể mô tả cụ thể hơn không?",
            action="clarify",
        )

    try:
        data = _json.loads(m.group())
    except _json.JSONDecodeError:
        return ChatResponseModel(
            reply="Tôi chưa hiểu rõ yêu cầu. Bạn có thể mô tả cụ thể hơn không?",
            action="clarify",
        )

    reply = str(data.get("reply") or "").strip() or "Bạn muốn tìm gì?"
    raw_action = str(data.get("action") or "")
    action: Literal["search", "clarify", "filter", "done"] = (
        raw_action if raw_action in ("search", "clarify", "filter", "done") else "clarify"
    )
    follow_up = data.get("follow_up_question") or None

    search_params: ChatSearchParams | None = None
    filter_params: ChatFilterParams | None = None

    if action == "search":
        sp = data.get("search_params") or {}
        if not sp.get("keywords"):
            # LLM forgot to include search_params — fall back to clarify
            return ChatResponseModel(reply=reply, action="clarify", follow_up_question=follow_up)
        search_params = ChatSearchParams(
            keywords=str(sp.get("keywords", "")),
            venues=[v for v in (sp.get("venues") or []) if isinstance(v, str)],
            year_from=int(sp["year_from"]) if sp.get("year_from") else None,
            year_to=int(sp["year_to"]) if sp.get("year_to") else None,
            limit=int(sp.get("limit") or 20),
        )

    elif action == "filter":
        fp = data.get("filter_params") or {}
        filter_params = ChatFilterParams(
            exclude_keywords=[str(k) for k in (fp.get("exclude_keywords") or [])],
            include_only_keywords=[str(k) for k in (fp.get("include_only_keywords") or [])],
            year_from=int(fp["year_from"]) if fp.get("year_from") else None,
            year_to=int(fp["year_to"]) if fp.get("year_to") else None,
            venues=fp.get("venues"),  # null means keep current
        )

    return ChatResponseModel(
        reply=reply,
        action=action,
        search_params=search_params,
        filter_params=filter_params,
        follow_up_question=follow_up,
    )


class ParseQueryRequest(BaseModel):
    query: str
    provider: Literal["openai", "gemini"] | None = None
    model: str | None = None
    base_url: str | None = None
    config_path: str | None = None


@app.post("/api/parse-query")
def api_parse_query(req: ParseQueryRequest) -> dict[str, Any]:
    """Extract keywords, venues, and year range from a natural-language query."""
    cfg = _cfg(req.config_path)
    try:
        provider = req.provider or cfg.llm_provider
        model = req.model or (cfg.openai_model if provider == "openai" else cfg.gemini_model)
        base_url = req.base_url or (cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url)
        parsed = parse_query(query=req.query, provider=provider, model=model, base_url=base_url)
    except Exception as e:
        # Graceful fallback: return original query unchanged
        return {
            "keywords": req.query,
            "venues": [],
            "year_from": None,
            "year_to": None,
            "fallback": True,
            "error": str(e),
        }
    return {
        "keywords": parsed.keywords,
        "venues": parsed.venues,
        "year_from": parsed.year_from,
        "year_to": parsed.year_to,
        "fallback": False,
    }


class FetchRequest(BaseModel):
    url: str


@app.post("/fetch")
def fetch(req: FetchRequest) -> dict[str, Any]:
    p = fetch_paper_from_url(req.url)
    return {"paper": p.to_dict()}


class DetailRequest(BaseModel):
    type: Literal["doi", "openalex", "semanticscholar", "arxiv"]
    id: str
    config_path: str | None = None


@app.post("/detail")
def detail(req: DetailRequest) -> dict[str, Any]:
    cfg = _cfg(req.config_path)
    try:
        d = fetch_detail(identifier=req.id, id_type=req.type, openalex_email=cfg.openalex_email)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"detail": d}


class TranslateRequest(BaseModel):
    abstract: str
    provider: Literal["openai", "gemini"] | None = None
    model: str | None = None
    base_url: str | None = None
    config_path: str | None = None


@app.post("/translate")
def translate(req: TranslateRequest) -> dict[str, Any]:
    cfg = _cfg(req.config_path)
    try:
        provider = req.provider or cfg.llm_provider
        model = req.model or (cfg.openai_model if provider == "openai" else cfg.gemini_model)
        base_url = req.base_url or (cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url)
        vi = translate_abstract_vi(text=req.abstract, provider=provider, model=model, base_url=base_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"abstract_vi": vi}


class SummarizeRequest(BaseModel):
    abstract: str
    provider: Literal["openai", "gemini"] | None = None
    model: str | None = None
    base_url: str | None = None
    config_path: str | None = None


@app.post("/summarize")
def summarize(req: SummarizeRequest) -> dict[str, Any]:
    cfg = _cfg(req.config_path)
    try:
        provider = req.provider or cfg.llm_provider
        model = req.model or (cfg.openai_model if provider == "openai" else cfg.gemini_model)
        base_url = req.base_url or (cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url)
        s = summarize_abstract(text=req.abstract, provider=provider, model=model, base_url=base_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"summary": s}


class LibraryAddRequest(BaseModel):
    db_path: str | None = None
    url: str | None = None
    paper: dict[str, Any] | None = None
    tags: list[str] = Field(default_factory=list)
    note: str | None = None


@app.post("/library/add")
def library_add(req: LibraryAddRequest) -> dict[str, Any]:
    if not req.url and not req.paper:
        raise HTTPException(status_code=400, detail="Provide url or paper")
    paper = fetch_paper_from_url(req.url).to_dict() if req.url else (req.paper or {})
    row_id = add_paper(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH, paper, tags=req.tags, note=req.note)
    return {"row_id": row_id}


class LibraryListRequest(BaseModel):
    db_path: str | None = None
    tag: str | None = None
    q: str | None = None
    limit: int = 50


@app.post("/library/list")
def library_list(req: LibraryListRequest) -> dict[str, Any]:
    rows = list_papers(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH, tag=req.tag, q=req.q, limit=req.limit)
    return {"papers": rows}


class LibraryDeleteRequest(BaseModel):
    db_path: str | None = None
    row_id: int


@app.post("/library/delete")
def library_delete(req: LibraryDeleteRequest) -> dict[str, Any]:
    delete_paper(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH, row_id=req.row_id)
    return {"ok": True}


class LibraryUpdateTagsRequest(BaseModel):
    db_path: str | None = None
    row_id: int
    tags: list[str] = Field(default_factory=list)


@app.post("/library/tags")
def library_tags(req: LibraryUpdateTagsRequest) -> dict[str, Any]:
    update_tags(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH, row_id=req.row_id, tags=req.tags)
    return {"ok": True}


class LibraryUpdateNoteRequest(BaseModel):
    db_path: str | None = None
    row_id: int
    note: str


@app.post("/library/note")
def library_note(req: LibraryUpdateNoteRequest) -> dict[str, Any]:
    update_note(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH, row_id=req.row_id, note=req.note)
    return {"ok": True}


class ProfileSetRequest(BaseModel):
    db_path: str | None = None
    key: str
    value: str


@app.post("/profile/set")
def profile_set(req: ProfileSetRequest) -> dict[str, Any]:
    set_profile(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH, key=req.key, value=req.value)
    return {"ok": True}


class ProfileGetRequest(BaseModel):
    db_path: str | None = None


@app.post("/profile/get")
def profile_get(req: ProfileGetRequest) -> dict[str, Any]:
    return {"profile": get_profile(Path(req.db_path) if req.db_path else DEFAULT_DB_PATH)}
