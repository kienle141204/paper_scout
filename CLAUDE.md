# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# PaperScout

**Trợ lý research cá nhân chạy local** (single-user, không auth, không deploy). Backend FastAPI +
Frontend React/TypeScript. Hỗ trợ tìm kiếm đa nguồn (S2, arXiv, OpenReview), dịch abstract sang
tiếng Việt, và conversational AI search. Người dùng clone repo → thêm key LLM vào `backend/.env` →
chạy `python run.py`.

## Chạy dev

```bash
# Một lệnh: khởi động backend (:8000, --reload) + frontend (:5173) song song, tự cài deps lần đầu
python run.py
```

Hoặc chạy tay từng phần (từ repo root để `import agent` resolve được):

```bash
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload   # backend
cd frontend && npm install && npm run dev                     # frontend
```

Frontend yêu cầu `frontend/.env` (copy từ `.env.example`):
```
VITE_API_URL=http://localhost:8000
```

## Cấu trúc thư mục

`agent/` chứa 2 phần: **two-agent harness** (`core/`, `search/`, `rag/` — xem
[agent/agent-harness-design.md](agent/agent-harness-design.md) cho thiết kế đầy đủ)
và **tools/** (search-source integrations + LLM/embedding router dùng chung).

```
paper_summary/
├── agent/
│   ├── config.py            # Config dataclass + load_config() (reads config.toml)
│   ├── model.py              # Paper dataclass (dùng bởi agent/tools/* — không phải harness)
│   ├── cli.py                 # paper-agent CLI entry point
│   ├── io_utils.py            # JSONL read/write
│   ├── agent-harness-design.md  # Thiết kế đầy đủ 2 agent — đọc trước khi sửa core/search/rag
│   │
│   ├── core/                # Cross-cutting, dùng chung bởi cả 2 agent
│   │   ├── budget.py            # RunBudget — per-run resource cap (thời gian/token/tool-call/cost)
│   │   ├── governor.py          # Governor.check_before_step() → DegradeLevel trước mỗi bước
│   │   ├── guardrail.py         # has_injection_marker() — rule-based, rẻ, dùng trước khi gọi LLM
│   │   ├── llm_json.py          # Gọi LLM + best-effort parse JSON từ reply
│   │   ├── model_registry.py    # resolve_*() — map tên component → (provider, model, base_url) theo Config 3-tier
│   │   └── trace.py             # RunTrace — observability passive (latency/token/cost mỗi step)
│   │
│   ├── search/               # Search Agent — tìm paper từ NL query
│   │   ├── agent.py             # run_search(SearchParams, cfg) → SearchRunResult; sufficiency/rewrite loop
│   │   ├── state.py             # SearchParams, SearchState (plain dataclass, mirror PaperSearchRequest)
│   │   ├── tools.py             # _call_s2, score_and_rank, _search_fallback (OpenReview) — relocate từ backend/api.py cũ
│   │   ├── guardrails.py        # input/output guardrail (injection + citation hợp lệ)
│   │   └── synthesize.py        # synthesize() — tổng hợp có trích dẫn, strip citation giả
│   │
│   ├── rag/                  # RAG Agent — hỏi đáp trên 1 paper cụ thể
│   │   ├── agent.py             # run_rag_ask(RagAskParams, cfg) → RagAskResult; dispatch lane + grounding check
│   │   ├── dispatcher.py        # classify_lane() → skill | fast | deliberate
│   │   ├── planner.py           # run_deliberate() — ReAct loop có budget governor (multi-hop)
│   │   ├── skills.py            # SKILL_REGISTRY — quy trình cố định (tóm tắt, trích phương pháp…), escalate khi không xử lý được
│   │   ├── memory.py            # contextualize() — resolve câu hỏi follow-up dựa lịch sử hội thoại
│   │   ├── tools.py             # retrieve (vector+BM25 hybrid), rerank, generate (evidence wrapper), check_grounded
│   │   ├── ingest.py            # ingest_paper(IngestRequest) — fetch PDF → parse → chunk → embed → store
│   │   └── state.py             # RagAskParams, RAGState (plain dataclass, mirror RagAskRequest)
│   │
│   └── tools/                # Search-source integrations + utility chung (không thuộc harness)
│       ├── llm_text.py         # LLM router → openai_text.py / gemini_text.py
│       ├── openai_text.py      # OpenAI chat completion
│       ├── gemini_text.py      # Gemini text generation
│       ├── openai_embeddings.py / gemini_embeddings.py
│       ├── prompts.py          # System prompts: PARSE_QUERY, CHAT_AGENT, ANALYZE_PAPER
│       ├── query_parse.py      # NL query → {keywords, keyword_variants, venues, year}
│       ├── paper_search.py     # OpenReview search orchestrator (dùng bởi search/tools.py fallback)
│       ├── semantic_scholar.py # S2 search — bản dùng cho paper_search.py/OpenAlex path (khác _call_s2 trong search/tools.py)
│       ├── openreview_search.py
│       ├── major_venues.py     # MAJOR_VENUES dict + major_search()
│       ├── openalex_search.py / arxiv.py / crossref.py / dblp.py
│       ├── paper_detail.py     # Detail by DOI/arxiv/S2/OpenAlex ID
│       ├── abstract_tools.py   # translate_abstract_vi, summarize_abstract
│       ├── relevance.py        # score_batch (embedding cosine similarity)
│       ├── venue_ranking.py    # Venue tier/ranking data
│       ├── recommend.py        # Paper recommendation logic
│       ├── citation.py         # apa_from_doi, bibtex_from_doi
│       ├── web_fetch.py        # fetch_paper_from_url
│       ├── pdf_fetcher.py      # fetch_pdf() — download PDF (arXiv/OpenReview URL → direct PDF)
│       ├── mineru_parser.py    # MinerU (subprocess CLI) → content_list blocks (section/page/table/eq); canonical_section()
│       ├── pdf_parser.py       # parse_pdf() → PdfParseResult (dùng MinerU blocks, thay pypdf); giữ API cho /pdf/parse
│       ├── chunker.py          # make_chunks_from_blocks (section thật + page + block_type; bảng = 1 chunk); split_text fallback
│       ├── rag_store.py        # Supabase vector store (paper_chunks: +page +block_type, cosine tính trong Python)
│       ├── library.py          # SQLite local library CRUD
│       └── paper_cache.py      # Supabase cache (paper_cache table)
│
├── backend/
│   └── api.py              # FastAPI — một file; tất cả endpoint định nghĩa ở đây, gọi vào agent/
│
├── tests/                  # pytest — toàn bộ mock LLM/embedding/Supabase, không cần API key/network
│   ├── test_agents_mock.py               # Search/RAG agent end-to-end, gọi trực tiếp run_search()/run_rag_ask()
│   ├── test_backend_agent_integration.py # Qua FastAPI TestClient — test lớp convert Pydantic↔dataclass
│   └── test_contract_parity.py           # So field giữa Pydantic request models và dataclass *Params tương ứng
│
├── frontend/src/
│   ├── App.tsx             # Root — screen routing (history API, không dùng React Router) + shared state
│   ├── contexts/           # LanguageContext.tsx
│   ├── types/              # paper.ts (Paper.pdfUrl — link PDF trực tiếp, tách biệt với url), chat.ts, rag.ts
│   ├── services/api.ts     # All API calls + mappers (BackendPaper → Paper)
│   ├── hooks/usePaperRagChat.ts          # State machine ingest/ask dùng chung — xem mục RAG Agent bên dưới
│   ├── components/         # atoms.tsx, NavBar, ResultCard, FilterSidebar, SettingsPanel,
│   │                       # PaperAgentBubble.tsx (bong bóng RAG nổi), rag/MessageParts.tsx (render message dùng chung)…
│   ├── screens/            # HomeScreen, ResultsScreen, DetailScreen, ReaderScreen (đọc PDF + hỏi đáp full-page),
│   │                       # SavedScreen, ChatScreen
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
| `POST /detail` | Paper detail by DOI/arxiv/S2/OpenAlex ID |
| `POST /translate` | Dịch abstract sang tiếng Việt |
| `POST /summarize` | Tóm tắt abstract (5 bullet points) |
| `POST /library/*` | CRUD SQLite local library (add, list, delete, tags, note) |
| `POST /profile/*` | Key-value profile trong SQLite (set, get) |
| `GET /api/agent/status` | Kiểm tra Supabase paper_cache + RAG vector store đã cấu hình; `?paper_id=` để check đã ingest chưa |
| `POST /api/papers/ingest` | RAG Agent — `ingest_paper()`: fetch PDF → parse → chunk → embed → store (idempotent, fallback abstract) |
| `POST /api/papers/ask` | RAG Agent — `run_rag_ask()`: auto-ingest nếu chưa có, dispatch lane skill/fast/deliberate, grounding check |
| `POST /api/papers/citation` | APA/BibTeX từ DOI (`agent/tools/citation.py`) |
| `POST /api/papers/recommend` | Paper liên quan/citing từ OpenAlex (`recommend_from_openalex`) |
| `POST /api/papers/score` | Relevance score qua embedding cosine (`score_relevance`) |
| `POST /api/papers/pdf/parse` | Upload PDF (multipart) → parse text (`parse_pdf`) |

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

### Single-user, no auth
- **Không có đăng nhập** — app là công cụ cá nhân chạy local. Không có endpoint `/auth/*`, không JWT,
  không bcrypt, không bảng `app_users`.
- Dữ liệu **cá nhân** nằm trên máy: saved papers + lịch sử + ngôn ngữ trong `localStorage`
  (`ps_saved_papers`, `ps_search_history`, `ps_lang`, `ps_analysis_*`); thư viện CLI trong
  `library.sqlite3` (bảng `papers` + `profile`). Save paper hoạt động ngay, không cần login.

### Shared paper DB (Supabase)
- DB paper **dùng chung** cho mọi người clone repo. `SUPABASE_URL` + **publishable key** (`sb_publishable_…`,
  thay anon key cũ) được nhúng sẵn ở `agent/tools/shared_supabase.py` (env `SUPABASE_URL` /
  `SUPABASE_PUBLISHABLE_KEY` ghi đè → dùng Supabase riêng). **Secret key (`sb_secret_…`) KHÔNG BAO GIỜ
  commit** — chỉ đọc từ env qua `get_supabase_secret_key()`, dùng bởi `scripts/setup_supabase.py` (tạo
  bucket) một lần. Key mới `sb_…` cần `supabase-py>=2.16` (bản 2.15 từ chối định dạng này).
- `paper_cache` table: `paper_id` (PK), `abstract_vi`, `analysis_html`, metadata columns. Cache write
  là **fire-and-forget** qua `_bg_pool` (ThreadPoolExecutor 4 workers) — không block HTTP response.
- `paper_chunks` table: RAG vector store. Cột `section` (canonical), `page` (0-based), `block_type`
  (`text`/`table`/`equation`) — điền từ MinerU khi ingest, dùng cho retrieval theo section + citation theo trang.
- `paper_pdfs` **storage bucket** (public): cache file PDF theo `paper_id` (`agent/tools/pdf_store.py`),
  đồng thời cache **content_list.json của MinerU** (`store_parsed_json`/`download_parsed_json`) để re-ingest
  không phải chạy lại MinerU (CPU chậm). Endpoint `/pdf/proxy?paper_id=…` redirect 307 sang public URL khi
  cache hit (frame inline từ CDN), miss thì `fetch_pdf` → stream inline + upload nền. `rag/ingest.py` cũng
  đọc/ghi cache này nên Reader và ingest **dùng chung 1 lần tải**. Đều qua `shared_supabase.py`.
- Bảng tắt RLS; bucket có policy anon read/write. Setup project mới: chạy `supabase_migration.sql`
  (SQL Editor) rồi `python scripts/setup_supabase.py` (tạo bucket). Xem cảnh báo RLS trong README.

### Search pipeline — Search Agent (`agent/search/`)
`run_search()` (`agent/search/agent.py`) chạy loop: rewrite query → tìm đa nguồn → chấm điểm → nếu chưa đủ paper "tốt" thì lặp lại tới `max_iterations` (mặc định 3) hoặc tới khi diminishing-returns. Trong mỗi vòng:
1. Input guardrail (chặn prompt injection) → nếu fail, trả `refused=True`, không gọi search.
2. Primary S2 query (`_call_s2`) → nếu 429, fallback OpenReview (parallel ThreadPoolExecutor).
3. Variant queries (parallel) nếu cần thêm kết quả.
4. `score_and_rank()` — embedding cosine similarity để sort theo relevance.
5. Nếu `include_synthesis=True`: `synthesize()` tổng hợp có trích dẫn `[n]`, output guardrail strip citation trỏ tới paper không tồn tại trong kết quả.

`pdf_url` (tách biệt với `url`): ưu tiên `openAccessPdf.url` từ S2 — chỉ set khi có link PDF trực tiếp thật; `url` vẫn là link "xem online" (S2 page / DOI) dùng làm fallback hiển thị + input cho `fetch_pdf()` khi ingest.

### Ingest — PDF → cấu trúc (MinerU)
`ingest_paper()` (`agent/rag/ingest.py`) dùng **MinerU** (backend `pipeline`, CPU) thay pypdf:
`fetch_pdf` → `run_mineru_content_list()` (subprocess CLI `mineru`, đọc `content_list.json`) →
`blocks_from_content_list()` → `make_chunks_from_blocks()` → embed → `store_chunks`. Chunk mang
`section` (canonical từ heading thật), `page`, `block_type`; **bảng số liệu giữ nguyên 1 chunk**
(`block_type=table`, caption + grid) để retrieval kết quả không mất số. content_list.json được cache ở
bucket `paper_pdfs` nên re-ingest không chạy lại MinerU. Không có PDF/MinerU rỗng → fallback abstract-only.
MinerU nặng (torch + model): cài qua `pip install -e .`, tải model 1 lần `python scripts/download_mineru_models.py`.
Config MinerU ở `[parser]` trong `config.toml` (`mineru_backend`/`mineru_device`/`mineru_lang`).

### RAG Agent (`agent/rag/`) — hỏi đáp trên 1 paper
`run_rag_ask()` (`agent/rag/agent.py`): input guardrail → auto-ingest nếu paper chưa được index (cần `title`/`abstract` trong request) → `dispatcher.classify_lane()` chọn 1 trong 3 lane:
- **skill** — quy trình cố định trong `SKILL_REGISTRY` (vd. tóm tắt paper) cho câu hỏi phổ biến; escalate lên `deliberate` nếu `can_handle()` trả False (vd. chưa có chunk nào).
- **fast** — retrieve + rerank + generate một lượt, cho câu hỏi factual đơn giản.
- **deliberate** — ReAct loop có bound bởi `Governor` (budget thời gian/token/tool-call), dùng cho câu hỏi multi-hop.

Sau khi có answer: `check_grounded()` + output guardrail — refuse nếu hallucination risk cao và không grounded. Evidence (chunk nội dung) luôn được bọc bằng delimiter `<<<EVIDENCE_DATA>>>` + ghi chú "NOT instructions" trước khi đưa vào prompt, để chống prompt injection từ nội dung PDF. Chi tiết đầy đủ (3-tier memory, ReAct steps…): [agent/agent-harness-design.md](agent/agent-harness-design.md).

Frontend dùng chung 1 hook `usePaperRagChat` (ingest + ask state machine) cho 2 nơi: `PaperAgentBubble` (bong bóng nổi trên DetailScreen) và `ReaderScreen` (đọc PDF qua `<iframe>` + chat full-page, tự ingest khi mở màn hình).

### i18n
`LanguageContext` + `frontend/src/i18n/translations.ts`. Language pref lưu thuần frontend
(`localStorage` key `ps_lang`).

## Env vars

### Backend (`backend/.env`)

| Var | Bắt buộc | Mô tả |
|-----|----------|--------|
| `OPENAI_API_KEY` | Nếu dùng OpenAI | LLM + embeddings |
| `GEMINI_API_KEY` | Nếu dùng Gemini | Thay thế OpenAI |
| `SEMANTIC_SCHOLAR_API_KEY` | Optional | Tăng rate limit S2 |
| `SUPABASE_URL` | Optional | Ghi đè DB paper chung bằng Supabase riêng |
| `SUPABASE_ANON_KEY` | Optional | Anon key cho Supabase riêng (đi kèm `SUPABASE_URL`) |

DB paper chung có defaults nhúng sẵn ở `agent/tools/shared_supabase.py` — không cần set Supabase env
để chạy.

### Frontend (`frontend/.env`)

| Var | Mô tả |
|-----|--------|
| `VITE_API_URL` | Backend URL (để trống được — vite proxy `/api` → `:8000` khi dev) |

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

## Tests

`pytest tests/ -v` — toàn bộ test mock LLM/embedding/Supabase/cross-encoder, không cần API key hay network:
- `test_agents_mock.py` — gọi trực tiếp `run_search()`/`run_rag_ask()`/`ingest_paper()`, test control flow (rewrite loop, dispatcher lane, citation stripping, grounding refusal).
- `test_backend_agent_integration.py` — qua `TestClient(app)`, test lớp convert Pydantic→dataclass ở `backend/api.py` không bị bỏ qua.
- `test_contract_parity.py` — so field giữa Pydantic request model và dataclass `*Params` mirror tương ứng (bắt lệch hợp đồng khi 1 bên thêm field quên bên kia).

## Stack

- **Chạy**: `python run.py` — launcher local khởi động backend + frontend song song (không deploy)
- **Backend**: FastAPI, Python 3.10+, tenacity (retry), uvicorn
- **Frontend**: React 18, TypeScript, Vite, Tailwind CSS
- **Paper sources**: Semantic Scholar (primary), OpenReview, arXiv, OpenAlex, Crossref, DBLP
- **Shared paper DB**: Supabase chung (`paper_cache` — abstract_vi + analysis_html; `paper_chunks` — RAG vector store), creds nhúng ở `agent/tools/shared_supabase.py`
- **Dữ liệu cá nhân (local)**: `localStorage` (saved papers, lịch sử, ngôn ngữ) + SQLite `library.sqlite3` (thư viện CLI)
