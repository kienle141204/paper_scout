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
from agent.tools.prompts import ANALYZE_PAPER, CHAT_AGENT
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
from agent.tools.paper_cache import get_cached_analysis, get_cached_paper, is_configured, upsert_analysis, upsert_paper
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


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "docs": "/docs", "frontend": "http://localhost:5173"}


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


# ── Paper analysis HTML template ──────────────────────────────────────────────

_ANALYSIS_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>__TITLE__</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Serif:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
:root {
  --bg: #fafaf9; --surface: #ffffff; --ink: #1c1c1a; --ink-2: #4a4a46; --ink-3: #7a7a74;
  --border: #e5e5e2; --accent: #2563eb; --accent-soft: #eff6ff; --accent-border: #bfdbfe;
  --s1-bg: #f0fdf4; --s1-bdr: #bbf7d0; --s1-clr: #15803d; --s1-num: #dcfce7;
  --s2-bg: #fff7ed; --s2-bdr: #fed7aa; --s2-clr: #c2410c; --s2-num: #ffedd5;
  --s3-bg: #fdf4ff; --s3-bdr: #e9d5ff; --s3-clr: #7c3aed; --s3-num: #f3e8ff;
  --r: 10px; --maxw: 860px;
  --shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body { background: var(--bg); color: var(--ink); font-family: 'Inter', system-ui, sans-serif;
       font-size: 15px; line-height: 1.65; -webkit-font-smoothing: antialiased; }
.container { max-width: var(--maxw); margin: 0 auto; padding: 40px 24px 80px; }
.paper-header { background: var(--surface); border: 1px solid var(--border);
                border-radius: var(--r); padding: 32px; margin-bottom: 28px; box-shadow: var(--shadow); }
.venue-badge { display: inline-flex; align-items: center; gap: 6px;
               font-family: 'JetBrains Mono', monospace; font-size: 11px; font-weight: 500;
               letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent);
               background: var(--accent-soft); border: 1px solid var(--accent-border);
               border-radius: 4px; padding: 3px 10px; margin-bottom: 14px; }
.paper-title { font-family: 'Noto Serif', serif; font-size: 26px; font-weight: 600;
               line-height: 1.3; color: var(--ink); margin-bottom: 10px; letter-spacing: -0.01em; }
.paper-authors { color: var(--ink-2); font-size: 14px; margin-bottom: 16px; }
.paper-keywords { display: flex; flex-wrap: wrap; gap: 6px; }
.kw { display: inline-block; font-size: 12px; background: #f4f4f2; border: 1px solid var(--border);
      border-radius: 4px; padding: 3px 8px; color: var(--ink-2); font-weight: 500; }
.section { background: var(--surface); border: 1px solid var(--border); border-radius: var(--r);
           padding: 28px 32px; margin-bottom: 24px; box-shadow: var(--shadow); }
.section-header { display: flex; align-items: center; gap: 14px; margin-bottom: 22px;
                  padding-bottom: 16px; border-bottom: 1px solid var(--border); }
.section-number { width: 34px; height: 34px; border-radius: 50%; display: flex;
                  align-items: center; justify-content: center; font-size: 14px;
                  font-weight: 700; flex-shrink: 0; }
.section-label { font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 500;
                 letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 2px; }
.section-title { font-size: 17px; font-weight: 700; letter-spacing: -0.01em; color: var(--ink); }
.sec1 .section-number { background: var(--s1-num); color: var(--s1-clr); border: 1px solid var(--s1-bdr); }
.sec1 .section-label { color: var(--s1-clr); }
.sec2 .section-number { background: var(--s2-num); color: var(--s2-clr); border: 1px solid var(--s2-bdr); }
.sec2 .section-label { color: var(--s2-clr); }
.sec3 .section-number { background: var(--s3-num); color: var(--s3-clr); border: 1px solid var(--s3-bdr); }
.sec3 .section-label { color: var(--s3-clr); }
.content p { margin-bottom: 13px; }
.content p:last-child { margin-bottom: 0; }
.content ul, .content ol { padding-left: 22px; margin-bottom: 13px; }
.content li { margin-bottom: 6px; line-height: 1.6; }
.content strong { font-weight: 600; color: var(--ink); }
.content em { font-style: italic; color: var(--ink-2); }
.callout { background: var(--accent-soft); border-left: 3px solid var(--accent);
           border-radius: 0 var(--r) var(--r) 0; padding: 13px 16px; margin: 16px 0;
           font-size: 14px; color: #1e40af; line-height: 1.6; }
.diagram { font-family: 'JetBrains Mono', monospace; font-size: 12.5px; background: #f8f8f7;
           border: 1px solid var(--border); border-radius: var(--r); padding: 18px 22px;
           margin: 16px 0; overflow-x: auto; white-space: pre; line-height: 1.65; color: #3d3d3a; }
/* ── Visual diagram components ─────────────── */
.pipeline { display: flex; align-items: stretch; flex-wrap: wrap; gap: 0; margin: 20px 0; }
.pipeline-step { background: var(--accent-soft); border: 1.5px solid var(--accent-border);
                 border-radius: 8px; padding: 11px 16px; text-align: center; font-size: 13px;
                 font-weight: 600; color: var(--accent); min-width: 90px; flex: 1 1 auto; }
.pipeline-step small { display: block; font-size: 11px; font-weight: 400; margin-top: 3px; opacity: 0.75; }
.pipeline-step.green { background: var(--s1-bg); border-color: var(--s1-bdr); color: var(--s1-clr); }
.pipeline-step.orange { background: var(--s2-bg); border-color: var(--s2-bdr); color: var(--s2-clr); }
.pipeline-step.purple { background: var(--s3-bg); border-color: var(--s3-bdr); color: var(--s3-clr); }
.pipeline-step.dark { background: var(--ink); color: #fff; border-color: var(--ink); }
.pipeline-step.gray { background: #f4f4f2; color: var(--ink-2); border-color: var(--border); }
.pipeline-arrow { display: flex; align-items: center; padding: 0 6px; color: var(--ink-3);
                  font-size: 20px; flex-shrink: 0; align-self: center; }
.flow-diagram { background: #f8f8f7; border: 1px solid var(--border); border-radius: var(--r);
                padding: 28px 24px; margin: 18px 0; }
.flow-row { display: flex; align-items: center; justify-content: center; gap: 10px;
            margin: 4px 0; flex-wrap: wrap; }
.flow-box { background: #fff; border: 1.5px solid var(--border); border-radius: 7px;
            padding: 9px 16px; font-size: 13px; font-weight: 500; color: var(--ink-2);
            text-align: center; min-width: 80px; }
.flow-box small { display: block; font-size: 11px; font-weight: 400; opacity: 0.75; margin-top: 2px; }
.flow-box.primary { background: var(--accent-soft); border-color: var(--accent-border);
                    color: var(--accent); font-weight: 700; }
.flow-box.input  { background: var(--s1-bg); border-color: var(--s1-bdr); color: var(--s1-clr); }
.flow-box.output { background: var(--s3-bg); border-color: var(--s3-bdr); color: var(--s3-clr); }
.flow-box.mid    { background: var(--s2-bg); border-color: var(--s2-bdr); color: var(--s2-clr); }
.flow-box.dark   { background: var(--ink); color: #fff; border-color: var(--ink); }
.flow-sep { color: var(--ink-3); font-size: 18px; align-self: center; }
.flow-down { text-align: center; color: var(--ink-3); font-size: 18px; margin: 4px 0;
             letter-spacing: 2px; }
.flow-label { font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 500;
              letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-3);
              text-align: center; margin: 10px 0 4px; }
.compare-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 18px 0; }
.compare-card { border: 1.5px solid var(--border); border-radius: 9px; padding: 18px; }
.compare-card.before { border-color: #fca5a5; background: #fff5f5; }
.compare-card.after  { border-color: var(--s1-bdr); background: var(--s1-bg); }
.compare-card h4 { font-size: 12px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase;
                   margin-bottom: 11px; display: flex; align-items: center; gap: 5px; }
.compare-card.before h4 { color: #dc2626; }
.compare-card.after  h4 { color: var(--s1-clr); }
.compare-card ul { padding-left: 16px; }
.compare-card li { font-size: 13px; color: var(--ink-2); margin-bottom: 6px; line-height: 1.5; }
.arch-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
             gap: 12px; margin: 16px 0; }
.arch-box { border: 1.5px solid var(--border); border-radius: 8px; padding: 14px 16px;
            background: var(--surface); }
.arch-box.blue   { border-color: var(--accent-border); background: var(--accent-soft); }
.arch-box.green  { border-color: var(--s1-bdr); background: var(--s1-bg); }
.arch-box.orange { border-color: var(--s2-bdr); background: var(--s2-bg); }
.arch-box.purple { border-color: var(--s3-bdr); background: var(--s3-bg); }
.arch-label { font-size: 11px; font-family: 'JetBrains Mono', monospace; font-weight: 600;
              letter-spacing: 0.06em; text-transform: uppercase; color: var(--ink-3); margin-bottom: 5px; }
.arch-box.blue .arch-label   { color: var(--accent); }
.arch-box.green .arch-label  { color: var(--s1-clr); }
.arch-box.orange .arch-label { color: var(--s2-clr); }
.arch-box.purple .arch-label { color: var(--s3-clr); }
.arch-content { font-size: 13px; color: var(--ink-2); line-height: 1.55; }
@media (max-width: 600px) {
  .compare-grid { grid-template-columns: 1fr; }
  .pipeline { flex-direction: column; }
  .pipeline-arrow { transform: rotate(90deg); align-self: center; }
}
/* ────────────────────────────────────────────── */
.results-table { width: 100%; border-collapse: collapse; margin: 16px 0; font-size: 14px; }
.results-table th { background: #f4f4f2; font-weight: 600; text-align: left;
                    padding: 9px 13px; border: 1px solid var(--border); color: var(--ink); }
.results-table td { padding: 9px 13px; border: 1px solid var(--border); color: var(--ink-2); }
.results-table tr:nth-child(even) td { background: #fafaf9; }
.results-table .highlight td { background: var(--accent-soft); font-weight: 600; color: var(--accent); }
.footer { text-align: center; color: var(--ink-3); font-size: 12px; margin-top: 48px;
          padding-top: 20px; border-top: 1px solid var(--border); }
@media (max-width: 600px) {
  .container { padding: 20px 16px 60px; }
  .paper-header, .section { padding: 20px; }
  .paper-title { font-size: 20px; }
}
@media print { body { background: white; } .section { break-inside: avoid; box-shadow: none; } }
</style>
</head>
<body>
<div class="container">
  <div class="paper-header">
    <div class="venue-badge">__VENUE_BADGE__</div>
    <h1 class="paper-title">__TITLE__</h1>
    <p class="paper-authors">__AUTHORS__</p>
    <div class="paper-keywords">__KEYWORDS_HTML__</div>
  </div>
  <div class="section sec1">
    <div class="section-header">
      <div class="section-number">1</div>
      <div><div class="section-label">Motivation</div><div class="section-title">Động lực nghiên cứu</div></div>
    </div>
    <div class="content">__MOTIVATION__</div>
  </div>
  <div class="section sec2">
    <div class="section-header">
      <div class="section-number">2</div>
      <div><div class="section-label">Visual</div><div class="section-title">Trực quan hóa phương pháp</div></div>
    </div>
    <div class="content">__VISUAL__</div>
  </div>
  <div class="section sec3">
    <div class="section-header">
      <div class="section-number">3</div>
      <div><div class="section-label">Results</div><div class="section-title">Kết quả đạt được</div></div>
    </div>
    <div class="content">__RESULTS__</div>
  </div>
  <div class="footer">Phân tích tự động bởi PaperScout &middot; __GENERATED_AT__</div>
</div>
</body>
</html>"""


class PaperAnalyzeRequest(BaseModel):
    paper_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)
    venue: str | None = None
    year: int | None = None
    url: str | None = None
    conference: str | None = None
    config_path: str | None = None


@app.post("/api/papers/analyze")
def api_papers_analyze(req: PaperAnalyzeRequest) -> dict[str, Any]:
    """Generate (or return cached) an HTML analysis report for a paper.

    The report has 3 sections: motivation, visual, results.
    Generated by LLM; cached in Supabase column analysis_html.
    """
    # 1. Serve from cache if available
    cached = get_cached_analysis(req.paper_id)
    if cached:
        return {"html": cached, "from_cache": True}

    # 2. Generate via LLM
    cfg = _cfg(req.config_path)
    provider = cfg.llm_provider
    model = cfg.openai_model if provider == "openai" else cfg.gemini_model
    base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url

    authors_display = ", ".join(req.authors[:5]) + (" et al." if len(req.authors) > 5 else "")
    venue_display = f"{req.conference or req.venue or 'N/A'} {req.year or ''}".strip()

    user_msg = (
        f"Phân tích paper sau:\n\n"
        f"Tiêu đề: {req.title}\n"
        f"Tác giả: {authors_display or 'Không rõ'}\n"
        f"Venue/Hội nghị: {venue_display}\n"
        f"Từ khóa: {', '.join(req.keywords[:10]) or 'Không có'}\n\n"
        f"Abstract:\n{req.abstract or '(Abstract không có sẵn)'}"
    )

    try:
        from agent.tools.llm_text import generate_text
        raw = generate_text(
            provider=provider,
            system=ANALYZE_PAPER,
            user=user_msg,
            model=model,
            base_url=base_url,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Lỗi AI: {e}")

    # 3. Parse JSON from LLM
    import json as _json
    import re as _re

    m = _re.search(r"\{.*\}", raw, _re.DOTALL)
    if not m:
        raise HTTPException(status_code=502, detail="AI không trả về kết quả hợp lệ")
    try:
        data = _json.loads(m.group())
    except _json.JSONDecodeError:
        raise HTTPException(status_code=502, detail="AI trả về JSON không hợp lệ")

    motivation = str(data.get("motivation") or "<p>Không có dữ liệu.</p>")
    visual = str(data.get("visual") or "<p>Không có dữ liệu.</p>")
    results = str(data.get("results") or "<p>Không có dữ liệu.</p>")

    # 4. Inject into HTML template
    import datetime
    import html as _html

    venue_badge = f"{req.conference or req.venue or 'N/A'} · {req.year or '?'}"
    keywords_html = "".join(f'<span class="kw">{_html.escape(k)}</span>' for k in req.keywords[:12])
    generated_at = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")

    report_html = (
        _ANALYSIS_HTML_TEMPLATE
        .replace("__TITLE__", _html.escape(req.title))
        .replace("__VENUE_BADGE__", _html.escape(venue_badge))
        .replace("__AUTHORS__", _html.escape(authors_display or "Không rõ tác giả"))
        .replace("__KEYWORDS_HTML__", keywords_html)
        .replace("__MOTIVATION__", motivation)
        .replace("__VISUAL__", visual)
        .replace("__RESULTS__", results)
        .replace("__GENERATED_AT__", generated_at)
    )

    # 5. Cache fire-and-forget
    upsert_analysis(req.paper_id, report_html)

    return {"html": report_html, "from_cache": False}


class PaperSearchRequest(BaseModel):
    query: str
    keyword_variants: list[str] = Field(default_factory=list)
    conferences: list[str] = Field(default_factory=list)
    year_from: int | None = None
    year_to: int | None = None
    language: str = "vi"
    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)
    corrected_query: str | None = None


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


def _build_s2_params(query: str, req: PaperSearchRequest, batch_limit: int) -> dict[str, Any]:
    """Build S2 search params dict for a given query string."""
    params: dict[str, Any] = {
        "query": query,
        "fields": _S2_FIELDS,
        "limit": batch_limit,
        "offset": req.offset,
    }
    if req.year_from is not None and req.year_to is not None:
        params["year"] = f"{req.year_from}-{req.year_to}"
    elif req.year_from is not None:
        params["year"] = f"{req.year_from}-"
    elif req.year_to is not None:
        params["year"] = f"-{req.year_to}"
    if len(req.conferences) == 1:
        aliases = _CONF_VENUE_ALIASES.get(req.conferences[0], [req.conferences[0]])
        params["venue"] = ",".join(aliases)
    return params


def _collect_from_raw(
    raw: list[dict[str, Any]],
    req: PaperSearchRequest,
    seen_ids: set[str],
    papers: list[dict[str, Any]],
) -> None:
    """Filter and append papers from a S2 raw response into papers list, deduplicating by paper_id."""
    for item in raw:
        if len(papers) >= req.limit:
            break
        if not item.get("abstract"):
            continue
        p = _paper_from_s2(item)
        if req.conferences and p["conference"] not in req.conferences:
            continue
        pid = p["paper_id"]
        if pid in seen_ids:
            continue
        seen_ids.add(pid)
        papers.append(p)


@app.post("/api/papers/search")
def api_papers_search(req: PaperSearchRequest) -> dict[str, Any]:
    batch_limit = min(req.limit * 3, 100)
    seen_ids: set[str] = set()
    papers: list[dict[str, Any]] = []
    has_more = False

    # Build ordered list of queries to try: primary first, then variants
    queries_to_try = [req.query] + [v for v in req.keyword_variants[:2] if v and v != req.query]

    for i, query in enumerate(queries_to_try):
        if len(papers) >= req.limit:
            break
        params = _build_s2_params(query, req, batch_limit)
        try:
            raw = _call_s2(params)
        except requests.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status == 429 and i == 0:
                # Rate limited on primary — fall back to OpenReview
                fallback = _search_fallback(req)
                fallback = _score_papers(req.query, fallback)
                has_more = len(fallback) >= req.limit
                return {
                    "papers": fallback, "total": len(fallback),
                    "query": req.query, "has_more": has_more,
                    "corrected_query": req.corrected_query,
                }
            if status == 429:
                break  # rate limited on variant — skip remaining
            raise HTTPException(status_code=502, detail="Nguồn dữ liệu phản hồi lỗi. Vui lòng thử lại sau.")
        except requests.RequestException:
            if i == 0:
                raise HTTPException(status_code=502, detail="Không thể kết nối nguồn dữ liệu. Vui lòng kiểm tra mạng.")
            break  # network error on variant — use what we have

        _collect_from_raw(raw, req, seen_ids, papers)

        # has_more is true if primary batch was full (indicates more pages exist)
        if i == 0:
            has_more = len(raw) >= batch_limit

    papers = _score_papers(req.query, papers)
    return {
        "papers": papers, "total": len(papers),
        "query": req.query, "has_more": has_more,
        "corrected_query": req.corrected_query,
    }


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
            year_from=int(sp["year_from"]) if sp.get("year_from") is not None else None,
            year_to=int(sp["year_to"]) if sp.get("year_to") is not None else None,
            limit=int(sp.get("limit") or 20),
        )

    elif action == "filter":
        fp = data.get("filter_params") or {}
        filter_params = ChatFilterParams(
            exclude_keywords=[str(k) for k in (fp.get("exclude_keywords") or [])],
            include_only_keywords=[str(k) for k in (fp.get("include_only_keywords") or [])],
            year_from=int(fp["year_from"]) if fp.get("year_from") is not None else None,
            year_to=int(fp["year_to"]) if fp.get("year_to") is not None else None,
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
        return {
            "keywords": req.query,
            "keyword_variants": [],
            "venues": [],
            "year_from": None,
            "year_to": None,
            "corrected_query": None,
            "fallback": True,
            "error": str(e),
        }
    return {
        "keywords": parsed.keywords,
        "keyword_variants": parsed.keyword_variants,
        "venues": parsed.venues,
        "year_from": parsed.year_from,
        "year_to": parsed.year_to,
        "corrected_query": parsed.corrected_query,
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
