# PaperScout

Ứng dụng tìm kiếm paper học thuật với AI. Backend FastAPI + Frontend React/TypeScript. Hỗ trợ tìm kiếm đa nguồn (S2, arXiv, OpenReview), dịch abstract sang tiếng Việt, và conversational AI search.

## Cấu trúc thư mục

```
paper_summary/
├── agent/                  # Pure Python business logic (CLI + tools)
│   ├── cli.py              # Entry point CLI (paper-agent command)
│   ├── model.py            # Paper dataclass
│   ├── config.py           # Config loader (config.toml)
│   ├── io_utils.py         # JSONL read/write
│   └── tools/
│       ├── llm_text.py         # LLM router (OpenAI / Gemini)
│       ├── prompts.py          # System prompts (PARSE_QUERY, CHAT_AGENT, …)
│       ├── query_parse.py      # NL query → {keywords, venues, year}
│       ├── paper_search.py     # Search orchestrator
│       ├── semantic_scholar.py # S2 primary source
│       ├── openreview_search.py
│       ├── major_venues.py     # MAJOR_VENUES dict
│       ├── openalex_search.py / arxiv.py / crossref.py / dblp.py
│       ├── paper_detail.py     # Detail by DOI/arxiv/S2/OpenAlex ID
│       ├── abstract_tools.py   # translate_abstract_vi, summarize_abstract
│       ├── relevance.py        # score_relevance (embeddings)
│       ├── library.py          # SQLite local library
│       └── paper_cache.py      # Supabase cache
│
├── backend/
│   ├── api.py              # FastAPI app — single-file, tất cả endpoints ở đây
│   ├── requirements.txt
│   └── .env                # (git-ignored)
│
├── frontend/src/
│   ├── App.tsx             # Root — screen routing + shared state
│   ├── types/              # paper.ts, chat.ts
│   ├── services/api.ts     # Tất cả API calls
│   ├── components/         # atoms.tsx, NavBar, ResultCard, FilterSidebar, …
│   ├── screens/            # HomeScreen, ResultsScreen, DetailScreen, SavedScreen, ChatScreen
│   └── utils/filterChat.ts # applyFilterParams() cho chat filter action
│
├── docker-compose.yml
├── pyproject.toml
├── config.toml             # (git-ignored) LLM + OpenAlex config
└── CLAUDE.md
```

## Chạy dev

```bash
# Backend
cd backend
uvicorn api:app --host 0.0.0.0 --port 8000 --reload

# Frontend
cd frontend
npm install && npm run dev
```

## API Endpoints chính (`backend/api.py`)

| Path | Mô tả |
|------|--------|
| `GET /api/conferences` | Danh sách hội nghị hỗ trợ |
| `POST /api/papers/search` | Tìm paper (S2 primary, OpenReview fallback) |
| `POST /api/papers/view` | Lấy abstract_vi (cache Supabase → dịch LLM) |
| `POST /api/parse-query` | Parse NL query → keywords/venues/year |
| `POST /api/chat` | Conversational agent (stateless, full history per request) |
| `POST /detail` | Paper detail by ID |
| `POST /translate` | Dịch abstract sang tiếng Việt |
| `POST /summarize` | Tóm tắt abstract (5 bullet points) |
| `POST /library/*` | CRUD SQLite local library |

## Kiến trúc quyết định quan trọng

1. **`backend/api.py` là single-file server** — không có routing module hay service layer. Mọi endpoint trong một file.
2. **Chat là stateless** — server không lưu session. Client giữ toàn bộ conversation history và gửi lại mỗi request.
3. **Chat action flow** — LLM trả về JSON `{action: "search"|"clarify"|"filter"|"done"}`. Frontend xử lý: `action=search` → gọi `/api/papers/search`; `action=filter` → chạy `applyFilterParams()` local.
4. **`agent/` và `backend/` tách biệt** — `agent/` là pure Python logic, `backend/api.py` import và wrap thành HTTP endpoints.
5. **Citation count: S2 primary** — nếu S2 trả 429 thì fallback OpenReview + best-effort enrich citation qua S2 batch API.
6. **LLM provider** — mặc định OpenAI, chuyển sang Gemini trong `config.toml`.

## Env vars (`backend/.env`)

| Var | Bắt buộc | Mô tả |
|-----|----------|--------|
| `OPENAI_API_KEY` | Nếu dùng OpenAI | LLM + embeddings |
| `GEMINI_API_KEY` | Nếu dùng Gemini | Thay thế OpenAI |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | Tăng rate limit S2 |
| `SUPABASE_URL` | Optional | Paper cache |
| `SUPABASE_KEY` | Optional | Paper cache |

## Stack

- **Backend**: FastAPI, Python 3.10+
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Paper sources**: Semantic Scholar (primary), OpenReview, arXiv, OpenAlex, Crossref, DBLP
- **Cache**: Supabase (optional) — lưu abstract_vi đã dịch
- **Local library**: SQLite via `agent/tools/library.py`
