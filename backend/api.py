from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")
import bcrypt as _bcrypt_lib
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from jose import JWTError, jwt as _jwt
from pydantic import BaseModel, Field

# ── JWT / Auth helpers ────────────────────────────────────────────────────────

_JWT_SECRET = os.environ.get("JWT_SECRET", "dev-secret-change-in-prod")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_DAYS = 30


def _hash_password(plain: str) -> str:
    return _bcrypt_lib.hashpw(plain.encode("utf-8"), _bcrypt_lib.gensalt()).decode("utf-8")


def _verify_password(plain: str, hashed: str) -> bool:
    return _bcrypt_lib.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _create_token(user_id: str, email: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(days=_JWT_EXPIRE_DAYS)
    return _jwt.encode({"sub": user_id, "email": email, "exp": exp}, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    return _jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])


def _get_current_user(authorization: str = Header(...)) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid token")
    try:
        return _decode_token(authorization[7:])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

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
from agent.tools.web_fetch import fetch_paper_from_url
from agent.search.state import SearchParams
from agent.search.agent import run_search

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

app = FastAPI(title="paper-agent-backend")

# Background thread pool for fire-and-forget tasks (e.g. Supabase cache writes)
_bg_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="bg_")

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


# ── Supabase client for auth (separate from paper_cache singleton) ─────────────

def _supabase_client():
    """Return a Supabase client for auth operations using service role key (bypasses RLS).
    Falls back to anon key if service role key is not set — in that case run:
      ALTER TABLE app_users DISABLE ROW LEVEL SECURITY;
    in the Supabase SQL editor.
    """
    url = os.environ.get("SUPABASE_URL")
    # Service role key bypasses RLS — required for server-side auth operations
    key = (
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_ANON_KEY")
        or os.environ.get("SUPABASE_KEY")
    )
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(url, key)
    except Exception:
        return None


# ── Auth Pydantic models ──────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: str
    password: str
    display_name: str | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class UpdateMeRequest(BaseModel):
    language_pref: Literal['en', 'vi'] | None = None
    display_name: str | None = None


# ── Auth endpoints ────────────────────────────────────────────────────────────

@app.post("/auth/register")
def auth_register(req: RegisterRequest) -> dict:
    if '@' not in req.email or len(req.email) < 5:
        raise HTTPException(400, "Invalid email")
    if len(req.password) < 8:
        raise HTTPException(400, "Password too short")

    client = _supabase_client()
    if not client:
        raise HTTPException(503, "Database not configured")

    existing = client.table("app_users").select("id").eq("email", req.email.lower()).execute()
    if existing.data:
        raise HTTPException(409, "Email already registered")

    hashed = _hash_password(req.password)
    result = client.table("app_users").insert({
        "email": req.email.lower(),
        "password_hash": hashed,
        "display_name": req.display_name,
        "language_pref": "en",
    }).execute()

    user = result.data[0]
    token = _create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user.get("display_name"),
            "language_pref": user.get("language_pref", "en"),
        }
    }


@app.post("/auth/login")
def auth_login(req: LoginRequest) -> dict:
    client = _supabase_client()
    if not client:
        raise HTTPException(503, "Database not configured")

    result = client.table("app_users").select("*").eq("email", req.email.lower()).execute()
    if not result.data:
        raise HTTPException(401, "Invalid credentials")

    user = result.data[0]
    if not _verify_password(req.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = _create_token(user["id"], user["email"])
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user.get("display_name"),
            "language_pref": user.get("language_pref", "en"),
        }
    }


@app.get("/auth/me")
def auth_me(current_user: dict = Depends(_get_current_user)) -> dict:
    client = _supabase_client()
    if not client:
        raise HTTPException(503, "Database not configured")

    result = client.table("app_users").select("id,email,display_name,language_pref").eq("id", current_user["sub"]).execute()
    if not result.data:
        raise HTTPException(404, "User not found")

    user = result.data[0]
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name"),
        "language_pref": user.get("language_pref", "en"),
    }


@app.patch("/auth/me")
def auth_update_me(req: UpdateMeRequest, current_user: dict = Depends(_get_current_user)) -> dict:
    client = _supabase_client()
    if not client:
        raise HTTPException(503, "Database not configured")

    updates: dict = {}
    if req.language_pref is not None:
        updates["language_pref"] = req.language_pref
    if req.display_name is not None:
        updates["display_name"] = req.display_name

    if not updates:
        raise HTTPException(400, "No fields to update")

    result = client.table("app_users").update(updates).eq("id", current_user["sub"]).execute()
    if not result.data:
        raise HTTPException(404, "User not found")

    user = result.data[0]
    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user.get("display_name"),
        "language_pref": user.get("language_pref", "en"),
    }


@lru_cache(maxsize=8)
def _cfg(config_path: str | None = None) -> Any:
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
            model = cfg.openai_cheap_model if provider == "openai" else cfg.gemini_cheap_model
            base_url = cfg.openai_base_url if provider == "openai" else cfg.gemini_base_url
            abstract_vi = translate_abstract_vi(
                text=req.abstract, provider=provider, model=model, base_url=base_url
            )
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Lỗi dịch: {e}")

    # 3. Lưu vào Supabase (truly fire-and-forget — không block HTTP response)
    _bg_pool.submit(upsert_paper, {
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
/* ── Timeline ──────────────────────────────── */
.timeline { margin: 18px 0; padding-left: 0; list-style: none; border-left: 2px solid var(--border); margin-left: 16px; }
.tl-item { display: flex; gap: 16px; margin-bottom: 16px; position: relative; }
.tl-dot { width: 28px; height: 28px; border-radius: 50%; border: 2px solid var(--border);
          background: var(--surface); display: flex; align-items: center; justify-content: center;
          font-size: 11px; font-weight: 700; flex-shrink: 0; margin-left: -15px; margin-top: 2px; }
.tl-dot.blue   { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); }
.tl-dot.green  { background: var(--s1-bg); border-color: var(--s1-bdr); color: var(--s1-clr); }
.tl-dot.orange { background: var(--s2-bg); border-color: var(--s2-bdr); color: var(--s2-clr); }
.tl-dot.purple { background: var(--s3-bg); border-color: var(--s3-bdr); color: var(--s3-clr); }
.tl-content { flex: 1; }
.tl-content strong { font-size: 13px; font-weight: 600; color: var(--ink); display: block; margin-bottom: 3px; }
.tl-content span { font-size: 12px; color: var(--ink-2); line-height: 1.5; }
/* ── Layer stack (bottom-up architecture) ──── */
.layer-stack { display: flex; flex-direction: column-reverse; gap: 6px; margin: 18px 0; }
.layer { border-radius: 8px; padding: 10px 18px; font-size: 13px; font-weight: 600;
         text-align: center; border: 1.5px solid var(--border); background: var(--surface); }
.layer-input  { background: var(--s1-bg); border-color: var(--s1-bdr); color: var(--s1-clr); }
.layer-core   { background: var(--accent-soft); border-color: var(--accent-border); color: var(--accent); }
.layer-mid    { background: var(--s2-bg); border-color: var(--s2-bdr); color: var(--s2-clr); }
.layer-output { background: var(--s3-bg); border-color: var(--s3-bdr); color: var(--s3-clr); }
.layer small  { display: block; font-size: 11px; font-weight: 400; opacity: 0.75; margin-top: 2px; }
/* ── Spoke (hub + radiating nodes) ────────── */
.spoke-wrap { margin: 18px 0; }
.spoke-hub { background: var(--ink); color: #fff; border-radius: 10px; padding: 12px 20px;
             text-align: center; font-weight: 700; font-size: 14px; margin-bottom: 12px; }
.spoke-ring { display: flex; flex-wrap: wrap; gap: 10px; justify-content: center; }
.spoke-node { border-radius: 7px; padding: 8px 14px; font-size: 12px; font-weight: 600;
              border: 1.5px solid var(--border); background: var(--surface); text-align: center; min-width: 100px; }
.spoke-node.green  { background: var(--s1-bg); border-color: var(--s1-bdr); color: var(--s1-clr); }
.spoke-node.orange { background: var(--s2-bg); border-color: var(--s2-bdr); color: var(--s2-clr); }
.spoke-node.purple { background: var(--s3-bg); border-color: var(--s3-bdr); color: var(--s3-clr); }
.spoke-node.blue   { background: var(--accent-soft); border-color: var(--accent-border); color: var(--accent); }
.spoke-node small  { display: block; font-size: 10px; font-weight: 400; opacity: 0.75; margin-top: 2px; }
/* ── Badge row ─────────────────────────────── */
.badge-row { display: flex; flex-wrap: wrap; gap: 7px; margin: 12px 0; }
.badge { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 20px;
         font-size: 12px; font-weight: 600; border: 1.5px solid var(--border); background: var(--surface); }
.badge.blue   { background: var(--accent-soft); border-color: var(--accent-border); color: var(--accent); }
.badge.green  { background: var(--s1-bg); border-color: var(--s1-bdr); color: var(--s1-clr); }
.badge.orange { background: var(--s2-bg); border-color: var(--s2-bdr); color: var(--s2-clr); }
.badge.purple { background: var(--s3-bg); border-color: var(--s3-bdr); color: var(--s3-clr); }
.badge.gray   { background: #f4f4f2; border-color: var(--border); color: var(--ink-2); }
/* ── Callout variants ──────────────────────── */
.callout.warn    { background: var(--s2-bg); border-color: var(--s2-clr); color: var(--s2-clr); }
.callout.success { background: var(--s1-bg); border-color: var(--s1-clr); color: var(--s1-clr); }
/* ────────────────────────────────────────────── */
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
<style>__EXTRA_STYLES__</style>
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

    # 2. Generate via LLM (premium model — complex HTML output, result is cached)
    cfg = _cfg(req.config_path)
    provider = cfg.llm_provider
    model = cfg.openai_analysis_model if provider == "openai" else cfg.gemini_analysis_model
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

    # 4. Extract any <style> blocks the model added in the visual section → move to <head>
    import re as _re2
    extra_styles_parts: list[str] = []
    def _collect_style(m: "_re2.Match[str]") -> str:
        extra_styles_parts.append(m.group(1))
        return ""
    visual_clean = _re2.sub(r"<style[^>]*>(.*?)</style>", _collect_style, visual, flags=_re2.DOTALL | _re2.IGNORECASE)
    extra_styles = "\n".join(extra_styles_parts)

    # 5. Inject into HTML template
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
        .replace("__VISUAL__", visual_clean)
        .replace("__RESULTS__", results)
        .replace("__GENERATED_AT__", generated_at)
        .replace("__EXTRA_STYLES__", extra_styles)
    )

    # 5. Cache fire-and-forget (background — không block HTTP response)
    _bg_pool.submit(upsert_analysis, req.paper_id, report_html)

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
    include_synthesis: bool = False
    config_path: str | None = None


@app.post("/api/papers/search")
def api_papers_search(req: PaperSearchRequest) -> dict[str, Any]:
    cfg = _cfg(req.config_path)
    params = SearchParams(
        query=req.query, keyword_variants=req.keyword_variants, conferences=req.conferences,
        year_from=req.year_from, year_to=req.year_to, limit=req.limit, offset=req.offset,
        corrected_query=req.corrected_query, include_synthesis=req.include_synthesis,
    )
    try:
        result = run_search(params, cfg=cfg)
    except requests.HTTPError:
        raise HTTPException(status_code=502, detail="Nguồn dữ liệu phản hồi lỗi. Vui lòng thử lại sau.")
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="Không thể kết nối nguồn dữ liệu. Vui lòng kiểm tra mạng.")
    return result.to_response_dict()


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
        model = req.model or (cfg.openai_cheap_model if provider == "openai" else cfg.gemini_cheap_model)
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
        model = req.model or (cfg.openai_cheap_model if provider == "openai" else cfg.gemini_cheap_model)
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


# ── RAG paper agent ───────────────────────────────────────────────────────────

from agent.tools.rag_store import is_configured as rag_configured
from agent.rag.ingest import IngestError, ingest_paper
from agent.rag.ingest import IngestRequest as _IngestArgs
from agent.rag.agent import RagAskParams, run_rag_ask


class IngestRequest(BaseModel):
    paper_id: str
    title: str
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    url: str | None = None
    conference: str | None = None
    year: int | None = None
    force: bool = False
    config_path: str | None = None


@app.post("/api/papers/ingest")
def api_papers_ingest(req: IngestRequest) -> dict[str, Any]:
    """Download, parse, chunk, embed and store a paper for RAG.

    Idempotent — skips processing if paper is already ingested (unless force=True).
    Falls back to abstract-only if the PDF cannot be fetched.
    """
    cfg = _cfg(req.config_path)
    args = _IngestArgs(
        paper_id=req.paper_id, title=req.title, abstract=req.abstract,
        authors=req.authors, url=req.url, conference=req.conference,
        year=req.year, force=req.force,
    )
    try:
        result = ingest_paper(args, cfg=cfg)
    except IngestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    return result.to_response_dict()


class RagAskRequest(BaseModel):
    paper_id: str
    question: str
    history: list[ChatMessageModel] = Field(default_factory=list)
    # Optional metadata — used for auto-ingest if paper not yet indexed
    title: str | None = None
    abstract: str | None = None
    authors: list[str] = Field(default_factory=list)
    url: str | None = None
    conference: str | None = None
    year: int | None = None
    config_path: str | None = None


@app.post("/api/papers/ask")
def api_papers_ask(req: RagAskRequest) -> dict[str, Any]:
    """Answer a question about a specific paper using RAG.

    Auto-ingests the paper if not yet indexed (using metadata fields).
    Dispatches to the skill/fast/deliberate lane via agent.rag.agent.run_rag_ask,
    then converges on a grounding check before returning.
    """
    if not rag_configured():
        raise HTTPException(status_code=503, detail="Vector store (Supabase) chưa được cấu hình.")

    cfg = _cfg(req.config_path)
    params = RagAskParams(
        paper_id=req.paper_id, question=req.question,
        history=[{"role": m.role, "content": m.content} for m in req.history],
        title=req.title, abstract=req.abstract, authors=req.authors,
        url=req.url, conference=req.conference, year=req.year,
    )
    try:
        result = run_rag_ask(params, cfg=cfg)
    except IngestError as e:
        raise HTTPException(status_code=e.status_code, detail=e.detail)
    if result.refused and not result.answer and not result.chunks:
        raise HTTPException(status_code=404, detail=result.refusal_reason or "Câu hỏi không hợp lệ.")
    return result.to_response_dict()
