# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PaperScout

Ứng dụng tìm kiếm paper học thuật với AI. Backend FastAPI + Frontend React/TypeScript. Hỗ trợ tìm kiếm đa nguồn (S2, arXiv, OpenReview), dịch abstract sang tiếng Việt, và conversational AI search.

## Chạy dev

```bash
# Backend — chạy từ root (PYTHONPATH cần thấy agent/)
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend && npm install && npm run dev
```

Frontend yêu cầu `frontend/.env` (copy từ `.env.example`):
```
VITE_API_URL=http://localhost:8000
```

## Cấu trúc thư mục

```
paper_summary/
├── agent/                  # Pure Python business logic
│   ├── config.py           # Config dataclass + load_config() (reads config.toml)
│   ├── model.py            # Paper dataclass
│   ├── cli.py              # paper-agent CLI entry point
│   ├── io_utils.py         # JSONL read/write
│   └── tools/
│       ├── llm_text.py         # LLM router → openai_text.py / gemini_text.py
│       ├── openai_text.py      # OpenAI chat completion
│       ├── gemini_text.py      # Gemini text generation
│       ├── openai_embeddings.py / gemini_embeddings.py
│       ├── prompts.py          # System prompts: PARSE_QUERY, CHAT_AGENT, ANALYZE_PAPER
│       ├── query_parse.py      # NL query → {keywords, keyword_variants, venues, year}
│       ├── paper_search.py     # OpenReview search orchestrator
│       ├── semantic_scholar.py # S2 search (primary source)
│       ├── openreview_search.py
│       ├── major_venues.py     # MAJOR_VENUES dict + major_search()
│       ├── openalex_search.py / arxiv.py / crossref.py / dblp.py
│       ├── paper_detail.py     # Detail by DOI/arxiv/S2/OpenAlex ID
│       ├── abstract_tools.py   # translate_abstract_vi, summarize_abstract
│       ├── relevance.py        # score_batch (embedding cosine similarity)
│       ├── venue_ranking.py    # Venue tier/ranking data
│       ├── recommend.py        # Paper recommendation logic
│       ├── citation.py         # Citation graph helpers
│       ├── web_fetch.py        # fetch_paper_from_url
│       ├── pdf_parser.py       # PDF text extraction
│       ├── library.py          # SQLite local library CRUD
│       └── paper_cache.py      # Supabase cache (paper_cache table)
│
├── backend/
│   └── api.py              # FastAPI — единственный файл; все endpoints здесь
│
├── frontend/src/
│   ├── App.tsx             # Root — screen routing + all shared state
│   ├── contexts/           # AuthContext.tsx, LanguageContext.tsx
│   ├── types/              # paper.ts, chat.ts
│   ├── services/api.ts     # All API calls + mappers (BackendPaper → Paper)
│   ├── components/         # atoms.tsx, NavBar, ResultCard, FilterSidebar, AuthModal, SettingsPanel…
│   ├── screens/            # HomeScreen, ResultsScreen, DetailScreen, SavedScreen, ChatScreen
│   ├── utils/filterChat.ts # applyFilterParams() — pure client-side filter for chat action=filter
│   └── i18n/translations.ts  # EN/VI string table (used via useLanguage hook)
│
├── config.toml             # (git-ignored) LLM + OpenAlex config
└── pyproject.toml          # paper-agent package + CLI
```

## API Endpoints (`backend/api.py`)

| Path | Mô tả |
|------|--------|
| `GET /api/conferences` | Danh sách hội nghị hỗ trợ |
| `POST /api/papers/search` | S2 primary + variant queries; fallback OpenReview nếu S2 429 |
| `POST /api/papers/view` | Lấy abstract_vi (Supabase cache → dịch LLM); fire-and-forget cache write |
| `POST /api/papers/analyze` | HTML report 3 sections (motivation/visual/results); cached in `analysis_html` column |
| `POST /api/parse-query` | NL query → keywords/keyword_variants/venues/year |
| `POST /api/chat` | Stateless conversational agent (full history per request) |
| `POST /auth/register` | Tạo tài khoản (bcrypt + JWT) |
| `POST /auth/login` | Đăng nhập → JWT token |
| `GET /auth/me` | Profile user hiện tại (Bearer token) |
| `PATCH /auth/me` | Cập nhật display_name, language_pref |
| `POST /detail` | Paper detail by DOI/arxiv/S2/OpenAlex ID |
| `POST /translate` | Dịch abstract sang tiếng Việt |
| `POST /summarize` | Tóm tắt abstract (5 bullet points) |
| `POST /library/*` | CRUD SQLite local library (add, list, delete, tags, note) |
| `POST /profile/*` | Key-value profile trong SQLite (set, get) |

## Kiến trúc và quyết định quan trọng

### LLM tiers (cấu hình trong `config.toml` hoặc mặc định qua `agent/config.py`)

| Tier | Dùng cho | OpenAI default | Gemini default |
|------|----------|----------------|----------------|
| `cheap_model` | translate, summarize | `gpt-4.1-nano` | `gemini-2.0-flash-lite` |
| `model` (standard) | chat, parse-query | `gpt-4.1-mini` | `gemini-2.5-flash` |
| `analysis_model` (premium) | paper analyze/visual (cached) | `gpt-4.1` | `gemini-2.5-pro` |

Provider mặc định: OpenAI. Đổi thành Gemini bằng `llm.provider = "gemini"` trong `config.toml`.

### Chat action flow
LLM trong `/api/chat` trả về JSON `{action: "search"|"clarify"|"filter"|"done"}`. Frontend xử lý:
- `action=search` → gọi `/api/papers/search` với `search_params` từ LLM
- `action=filter` → chạy `applyFilterParams()` local (không gọi backend)
- Chat là **stateless** — server không lưu session; client gửi toàn bộ history mỗi request (cắt tối đa 30 messages)

### Auth system
- JWT (HS256, 30 ngày) do backend tự issue. Secret: env var `JWT_SECRET` (default `dev-secret-change-in-prod`).
- Password hash bằng bcrypt. User lưu trong Supabase table `app_users`.
- Auth dùng `SUPABASE_SERVICE_ROLE_KEY` (bypass RLS). Nếu không có, dùng `SUPABASE_ANON_KEY` nhưng phải tắt RLS trên `app_users`.
- Frontend lưu token trong `localStorage` (`ps_token`, `ps_user`). Saved papers lưu trong `ps_saved_papers`.

### Supabase caching
- `paper_cache` table: `paper_id` (PK), `abstract_vi`, `analysis_html`, metadata columns.
- `paper_cache.py` dùng `SUPABASE_ANON_KEY`; auth dùng `SUPABASE_SERVICE_ROLE_KEY`.
- Cache write là **fire-and-forget** qua `_bg_pool` (ThreadPoolExecutor 4 workers) — không block HTTP response.

### Search pipeline (S2-primary)
1. Parse NL query → `keywords`, `keyword_variants` (2 variants), `venues`, `year_from/to`
2. Primary S2 query → nếu 429, fallback OpenReview (parallel ThreadPoolExecutor)
3. Variant queries (parallel) nếu cần thêm kết quả
4. `score_batch()` — embedding cosine similarity để sort theo relevance

### i18n
`LanguageContext` + `frontend/src/i18n/translations.ts`. Language pref lưu cả frontend (`localStorage`) và backend (cột `language_pref` trong `app_users`).

## Env vars

### Backend (`backend/.env`)

| Var | Bắt buộc | Mô tả |
|-----|----------|--------|
| `OPENAI_API_KEY` | Nếu dùng OpenAI | LLM + embeddings |
| `GEMINI_API_KEY` | Nếu dùng Gemini | Thay thế OpenAI |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | Tăng rate limit S2 |
| `SUPABASE_URL` | Optional | Paper cache + auth |
| `SUPABASE_ANON_KEY` | Optional | Paper cache (`paper_cache` table) |
| `SUPABASE_SERVICE_ROLE_KEY` | Optional | Auth (`app_users` table, bypass RLS) |
| `JWT_SECRET` | Optional | JWT signing (default: insecure dev value) |

### Frontend (`frontend/.env`)

| Var | Mô tả |
|-----|--------|
| `VITE_API_URL` | Backend URL (default: `''` — same origin; dev: `http://localhost:8000`) |

## `config.toml` schema

```toml
[openalex]
email = ""          # khuyến nghị để tăng rate limit

[llm]
provider = "openai" # hoặc "gemini"

[openai]
model = "gpt-4.1-mini"
cheap_model = "gpt-4.1-nano"
analysis_model = "gpt-4.1"
# base_url = "https://api.openai.com/v1"

[gemini]
model = "gemini-2.5-flash"
cheap_model = "gemini-2.0-flash-lite"
analysis_model = "gemini-2.5-pro"
base_url = "https://generativelanguage.googleapis.com/v1beta"
```

## Stack

- **Backend**: FastAPI, Python 3.10+, tenacity (retry), python-jose (JWT), bcrypt
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Paper sources**: Semantic Scholar (primary), OpenReview, arXiv, OpenAlex, Crossref, DBLP
- **Cache**: Supabase (`paper_cache` table — abstract_vi + analysis_html)
- **Auth**: Custom JWT, Supabase `app_users` table
- **Local library**: SQLite via `agent/tools/library.py`
