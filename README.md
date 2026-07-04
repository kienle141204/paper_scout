<div align="center">

<img src="https://img.shields.io/badge/PaperScout-v2.1-2563eb?style=for-the-badge&logo=bookstack&logoColor=white" alt="PaperScout" height="36"/>

# 🔬 PaperScout

**Trợ lý research cá nhân chạy local — với RAG reasoning agent đọc PDF theo cấu trúc**

Tìm kiếm đa nguồn · Dịch tiếng Việt · Chat AI · RAG Agent per-paper (MinerU) · Chạy 1 lệnh, không cần deploy

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Shared%20Paper%20DB-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com/)

[![MinerU](https://img.shields.io/badge/Parser-MinerU%202-FF6F00?style=flat-square)](https://github.com/opendatalab/MinerU)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com/)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.5-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Semantic Scholar](https://img.shields.io/badge/Source-Semantic%20Scholar-D62728?style=flat-square)](https://www.semanticscholar.org/)
[![arXiv](https://img.shields.io/badge/Source-arXiv-B31B1B?style=flat-square)](https://arxiv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## 📸 Tổng quan

PaperScout là **trợ lý research cá nhân chạy trên máy của bạn** — clone repo, thêm API key LLM, chạy một lệnh là có ngay app tìm kiếm/đọc/phân tích paper bằng AI. Không cần đăng nhập, không cần deploy. Điểm nổi bật là **RAG Agent per-paper**: mỗi bài báo có một AI riêng đọc **toàn bộ PDF theo cấu trúc thật** (section, trang, bảng số liệu) qua [MinerU](https://github.com/opendatalab/MinerU), rồi trả lời câu hỏi kèm **trích dẫn tới đúng đoạn và số trang**.

Dữ liệu **cá nhân** (paper đã lưu, lịch sử, ngôn ngữ) nằm ngay trên máy (trình duyệt / SQLite local). Dữ liệu **paper dùng chung** (bản dịch, RAG chunks, cache PDF) nằm trên một Supabase chung đã cấu hình sẵn — bạn không phải set up gì.

```
📄 Tìm paper → 🧠 AI phân tích → 📖 Đọc PDF + hỏi đáp RAG → 🌐 Dịch tiếng Việt
```

---

## ✨ Tính năng

<table>
<tr>
<td width="50%">

### 🔍 Tìm kiếm thông minh
- Tìm đa nguồn: **Semantic Scholar** (primary), OpenReview, arXiv, OpenAlex, Crossref, DBLP
- Hỗ trợ **15+ hội nghị lớn**: NeurIPS, ICML, ICLR, CVPR, ACL, EMNLP, AAAI…
- Parse NL query → keywords / variants / venues / năm bằng LLM
- Xếp hạng theo **embedding cosine similarity**
- Fallback thông minh khi S2 rate-limit (OpenReview song song)

### 💬 Chat AI
- Conversational agent tìm kiếm bằng ngôn ngữ tự nhiên (VI/EN)
- Actions: `search` · `filter` · `clarify` · `done`
- Filter client-side không cần gọi lại backend

</td>
<td width="50%">

### 🤖 RAG Agent per-paper
- **Parse PDF theo cấu trúc bằng MinerU**: giữ section thật (heading), số trang, và **bảng số liệu nguyên vẹn** — nên câu trả lời không bị mất số
- Trả lời có **trích dẫn `[1][2]`** trỏ đúng đoạn + **số trang** (vd. *"Results, p.6, TABLE"*)
- **Chunk metadata** (title/authors/year/venue) được index → hỏi tác giả / năm / hội nghị đều trả lời được
- **Hybrid retrieval**: vector cosine + BM25 hợp nhất bằng RRF, rồi **cross-encoder rerank**
- **Dispatcher 3-lane**: skill → fast → deliberate (ReAct multi-hop), tự escalate khi lane rẻ hơn không xử lý được
- **Grounding check** thông minh: hiện câu trả lời kèm badge cảnh báo mức rủi ro, chỉ từ chối khi thực sự bịa số/dữ kiện
- 2 cách dùng: **Reader Screen** (đọc PDF thật + chat full-page) hoặc floating bubble ở trang Detail

### 🌐 Đa ngôn ngữ & Phân tích
- Dịch abstract sang **tiếng Việt** tự động (LLM)
- Phân tích paper: HTML report 3 sections với diagram đẹp
- Cache kết quả trong Supabase để tiết kiệm token
- Giao diện **EN/VI** toggle

</td>
</tr>
</table>

---

## 🏗️ Kiến trúc

```
┌─────────────────────────────────────────────────────────────────┐
│                        PaperScout                               │
│                                                                 │
│   Frontend (React + TypeScript + Vite)                         │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌───────┐ │
│   │  Search  │ │  Detail  │ │  Reader  │ │  Chat   │ │  RAG  │ │
│   │  Screen  │ │  Screen  │ │  Screen  │ │  Screen │ │ Bubble│ │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └───┬───┘ │
│        │             │             │             │          │   │
│        └─────────────┴─────────────┴─────────────┴──────────┘   │
│                              │ REST API                         │
├──────────────────────────────┼──────────────────────────────────┤
│   Backend (FastAPI)          │                                  │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │  /api/papers/search  │  /api/chat  │  /api/papers/ask    │ │
│   │  /api/papers/view    │  /pdf/proxy │  /api/papers/ingest │ │
│   └──────────┬────────────────────────────────┬───────────────┘ │
│              │                                │                  │
│   ┌──────────▼──────────┐      ┌─────────────▼─────────────┐   │
│   │  agent/search/      │      │   agent/rag/               │   │
│   │  Search Agent        │      │   RAG Agent (MinerU)       │   │
│   │  rewrite/sufficiency │      │   dispatcher 3-lane        │   │
│   │  loop · synthesis    │      │   skill/fast/deliberate    │   │
│   └──────────┬──────────┘      └─────────────┬─────────────┘   │
│              │      agent/core/ (budget · governor · guardrail · trace) │
│   ┌──────────▼──────────────────────────────────▼─────────────┐ │
│   │  agent/tools/ — S2 · OpenReview · arXiv · OpenAlex ·       │ │
│   │  LLM router · embeddings · MinerU parser · chunker ·       │ │
│   │  pdf_fetcher · pdf_store · rag_store (vector + BM25)       │ │
│   └─────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│   Infrastructure                                                 │
│   ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│   │ Supabase CHUNG│  │  OpenAI/Gemini  │  │  Local (trên máy)│  │
│   │  paper_cache  │  │  LLM · Embed    │  │  localStorage    │  │
│   │  paper_chunks │  │                 │  │  library.sqlite3 │  │
│   │  paper_pdfs 🪣│  │                 │  │                  │  │
│   └───────────────┘  └─────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 🧠 Two-Agent Harness

PaperScout dùng **2 agent độc lập**, chỉ giao nhau ở bước ingest (xem
[`agent/agent-harness-design.md`](agent/agent-harness-design.md) cho thiết kế đầy đủ — budget governor,
3-tier memory, evidence safety wrapper…):

```
Search Agent (agent/search/)                 RAG Agent (agent/rag/)
───────────────────────────────              ───────────────────────────────
input guardrail (chặn injection)             input guardrail
       │                                            │
       ▼                                     auto-ingest nếu chưa index:
search đa nguồn (S2 → fallback OpenReview)    fetch PDF → MinerU parse (section/
       │                                      page/table) → chunk → embed → store
score_and_rank (embedding cosine)                   │
       │                                     dispatcher → chọn lane:
chưa đủ "tốt"? rewrite query, lặp lại        ┌─────────┬────────┬────────────┐
  (tới max_iterations hoặc diminishing)       │  skill  │  fast  │ deliberate │
       │                                     │ quy trình│retrieve│ ReAct loop │
include_synthesis? → synthesize() có trích   │ cố định  │(vector+│ có budget  │
dẫn [n], strip citation giả                  │(tóm tắt…)│ BM25)  │ governor   │
       │                                     │ escalate │+rerank │ (multi-hop)│
       │                                     │ nếu fail │+generate│           │
       ▼                                     └─────────┴────────┴────────────┘
SearchRunResult                                       │
                                             check_grounded() → output guardrail:
                                             hiện answer + badge rủi ro; chỉ refuse
                                             khi risk=high & không truy vết được
                                                      ▼
                                             RagAskResult (answer + citations
                                             theo trang + confidence + coverage)
```

---

## 🚀 Quick Start

Chạy local trong **vài bước**. Không cần đăng nhập, không cần deploy, không cần tự dựng database.

### Yêu cầu

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

> 📦 RAG dùng **MinerU** (kéo theo `torch` + model layout/OCR) — lần cài đầu khá nặng. Nếu chỉ dùng
> tìm kiếm/dịch/chat mà không cần RAG đọc PDF, vẫn chạy được (RAG sẽ fallback về abstract-only).

### 1. Clone

```bash
git clone https://github.com/kienle141204/paper_scout.git
cd paper_scout
```

### 2. Thêm API key

Tạo `backend/.env` (hoặc để `run.py` tự tạo từ mẫu ở lần chạy đầu) và điền **một** key LLM:

```bash
cp backend/.env.example backend/.env
# rồi mở backend/.env, đặt OPENAI_API_KEY=sk-...   (hoặc GEMINI_API_KEY=...)
```

> DB paper dùng chung (Supabase) đã được nhúng sẵn — bạn **không cần** cấu hình gì thêm.

### 3. Tải model MinerU (một lần, cho RAG)

```bash
python scripts/download_mineru_models.py
```

Bước này tải model parse layout/bảng/công thức của MinerU về máy. Chỉ cần chạy **một lần**. Nếu ở VN
mà Hugging Face chập chờn, đặt `mineru_model_source = "modelscope"` trong `config.toml` (xem bên dưới).

### 4. Chạy một lệnh

```bash
python run.py
```

Lệnh này tự lo phần còn lại: cài dependency Python (`pip install -e .`) và frontend
(`npm install`) ở lần đầu, rồi khởi động **cả backend lẫn frontend** song song.

Mở trình duyệt tại **`http://localhost:5173`** · Backend chạy ở `http://localhost:8000`.
Nhấn `Ctrl+C` để dừng cả hai.

<details>
<summary>Tùy chọn: đổi provider/model + cấu hình MinerU qua <code>config.toml</code></summary>

Tạo `config.toml` ở root (mặc định dùng OpenAI + MinerU CPU nếu bỏ qua):

```toml
[llm]
provider = "openai"   # hoặc "gemini"

[openai]
model          = "gpt-4.1-mini"
cheap_model    = "gpt-4.1-nano"
analysis_model = "gpt-4.1"

# [gemini]
# model          = "gemini-2.5-flash"
# cheap_model    = "gemini-2.0-flash-lite"
# analysis_model = "gemini-2.5-pro"

[parser]
parser             = "mineru"
mineru_backend     = "pipeline"      # pipeline = CPU; "vlm-transformers" nếu có GPU NVIDIA
mineru_device      = "cpu"           # cpu | cuda
mineru_lang        = "en"
mineru_model_source = "huggingface"  # đổi "modelscope" nếu HF bị chặn/chập chờn (VN)
mineru_max_pages   = 10              # chỉ OCR 10 trang đầu (0 = toàn bộ). CPU chậm nên giới hạn.
```

</details>

<details>
<summary>Tùy chọn: dùng Supabase RIÊNG của bạn thay vì DB chung</summary>

Đặt `SUPABASE_URL` + `SUPABASE_ANON_KEY` (hoặc publishable key) trong `backend/.env` để ghi đè DB
chung, rồi:

1. Chạy [`supabase_migration.sql`](supabase_migration.sql) trong Supabase SQL Editor — tạo bảng
   `paper_cache` + `paper_chunks` (đủ cột `section` / `page` / `block_type` cho RAG).
2. Chạy `python scripts/setup_supabase.py` — tạo storage bucket `paper_pdfs` (cache PDF + MinerU JSON).

> ⚠️ **Lưu ý DB chung**: các bảng đang tắt Row-Level Security, nên bất kỳ ai có anon key (được
> ship trong repo) cũng có thể ghi vào DB chung. Nếu lo bị lạm dụng, hãy bật RLS + policy
> read-mostly trên Supabase, hoặc dùng Supabase riêng.

</details>

---

## ⚙️ Cấu hình

### Backend (`backend/.env`)

| Biến | Bắt buộc | Mô tả |
|------|----------|--------|
| `OPENAI_API_KEY` | Nếu dùng OpenAI | LLM + embeddings |
| `GEMINI_API_KEY` | Nếu dùng Gemini | Thay thế OpenAI |
| `SEMANTIC_SCHOLAR_API_KEY` | Không | Tăng rate limit S2 |
| `SUPABASE_URL` | Không | Ghi đè DB paper chung bằng Supabase riêng |
| `SUPABASE_ANON_KEY` | Không | Anon/publishable key cho Supabase riêng (đi kèm `SUPABASE_URL`) |

### Frontend (`frontend/.env`)

| Biến | Mô tả |
|------|--------|
| `VITE_API_URL` | Backend URL — để trống cũng được (vite proxy `/api` → `:8000` khi dev) |

### LLM Tiers

| Tier | Dùng cho | OpenAI | Gemini |
|------|----------|--------|--------|
| `cheap_model` | translate, summarize, dispatcher, guardrail, grounding | `gpt-4.1-nano` | `gemini-2.0-flash-lite` |
| `model` | chat, parse-query, RAG answer | `gpt-4.1-mini` | `gemini-2.5-flash` |
| `analysis_model` | paper analyze (cached) | `gpt-4.1` | `gemini-2.5-pro` |

---

## 📡 API Reference

### Search & Discovery

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| `GET` | `/api/conferences` | Danh sách hội nghị hỗ trợ |
| `POST` | `/api/papers/search` | Tìm paper (S2 primary + variant queries) |
| `POST` | `/api/papers/view` | Lấy abstract_vi (cache → dịch LLM) |
| `POST` | `/api/papers/analyze` | HTML analysis report (cached) |
| `POST` | `/api/parse-query` | NL query → keywords / venues / year |
| `POST` | `/detail` | Chi tiết paper theo DOI / arXiv / S2 ID |

### Chat & RAG

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| `POST` | `/api/chat` | Conversational search agent (stateless) |
| `GET` | `/api/agent/status` | Kiểm tra Supabase cache + RAG store; `?paper_id=` để check đã ingest chưa |
| `POST` | `/api/papers/ingest` | Fetch PDF → MinerU parse → chunk → embed → store (idempotent, fallback abstract) |
| `POST` | `/api/papers/ask` | RAG Q&A — dispatcher 3-lane (skill/fast/deliberate) + grounding check |
| `GET` | `/pdf/proxy` | Redirect/stream PDF inline (cache hit từ bucket `paper_pdfs`) |

### Utilities (paper)

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| `POST` | `/api/papers/citation` | APA / BibTeX từ DOI |
| `POST` | `/api/papers/recommend` | Paper liên quan / citing (OpenAlex) |
| `POST` | `/api/papers/score` | Relevance score qua embedding cosine |
| `POST` | `/api/papers/pdf/parse` | Upload PDF → parse text (MinerU) |

### Utilities

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| `POST` | `/translate` | Dịch abstract sang tiếng Việt |
| `POST` | `/summarize` | Tóm tắt abstract (5 bullet points) |
| `POST` | `/library/*` | CRUD thư viện cá nhân (SQLite) |

---

## 📁 Cấu trúc thư mục

```
paper_scout/
├── 📂 agent/
│   ├── config.py                # Config dataclass + load_config() ([parser] MinerU)
│   ├── model.py                 # Paper dataclass
│   ├── cli.py                   # paper-agent CLI
│   ├── agent-harness-design.md  # 📐 Thiết kế đầy đủ 2 agent
│   │
│   ├── core/                    # Dùng chung bởi cả 2 agent
│   │   ├── budget.py / governor.py   # RunBudget + Governor (degrade khi vượt budget)
│   │   ├── guardrail.py              # has_injection_marker() — rule-based
│   │   ├── model_registry.py         # Map tên component → (provider, model)
│   │   └── trace.py                  # Observability passive
│   │
│   ├── search/                  # 🔍 Search Agent
│   │   ├── agent.py                  # run_search() — sufficiency/rewrite loop
│   │   ├── tools.py                  # _call_s2, score_and_rank, OpenReview fallback
│   │   ├── guardrails.py / synthesize.py
│   │   └── state.py                  # SearchParams (mirror PaperSearchRequest)
│   │
│   ├── rag/                     # 🤖 RAG Agent
│   │   ├── agent.py                  # run_rag_ask() — dispatch + grounding check
│   │   ├── dispatcher.py             # classify_lane() → skill | fast | deliberate
│   │   ├── planner.py / skills.py / memory.py
│   │   ├── tools.py                  # retrieve (vector+BM25), rerank, generate, check_grounded
│   │   ├── ingest.py                 # 📄 fetch PDF → MinerU → chunk (+metadata) → embed → store
│   │   └── state.py                  # RagAskParams (mirror RagAskRequest)
│   │
│   └── tools/                   # Search-source integrations + utility chung
│       ├── llm_text.py          # LLM router (OpenAI / Gemini)
│       ├── prompts.py           # System prompts (answerer/verifier/evidence wrapper…)
│       ├── semantic_scholar.py  # S2 search (đường khác — dùng cho paper_search.py/OpenAlex)
│       ├── paper_search.py      # OpenReview orchestrator
│       ├── abstract_tools.py    # translate_abstract_vi, summarize
│       ├── relevance.py         # Embedding cosine ranking
│       ├── pdf_fetcher.py       # 📄 Download PDF (arXiv/OpenReview → direct PDF)
│       ├── mineru_parser.py     # 🧩 MinerU (subprocess) → content_list blocks; canonical_section()
│       ├── pdf_parser.py        # parse_pdf() → dùng MinerU blocks (giữ API cho /pdf/parse)
│       ├── chunker.py           # Structure-aware chunking (section thật + page + block_type; bảng = 1 chunk)
│       ├── rag_store.py         # 🗄️ Supabase vector store (paper_chunks: +page +block_type)
│       ├── pdf_store.py         # 🪣 Cache PDF + MinerU content_list.json ở bucket paper_pdfs
│       ├── paper_cache.py       # Supabase cache (abstract_vi, analysis)
│       └── library.py           # SQLite local library CRUD
│
├── 📂 backend/
│   └── api.py                   # FastAPI — tất cả endpoints
│
├── 📂 tests/                    # pytest — mock LLM/embedding/Supabase, không cần network
│   ├── test_agents_mock.py
│   ├── test_backend_agent_integration.py
│   └── test_contract_parity.py
│
├── 📂 frontend/src/
│   ├── App.tsx                  # Root — routing (History API) + shared state
│   ├── contexts/                # LanguageContext
│   ├── types/                   # paper.ts (Paper.pdfUrl), chat.ts, rag.ts
│   ├── services/api.ts          # API calls + mappers
│   ├── hooks/usePaperRagChat.ts # State machine ingest/ask dùng chung
│   ├── components/
│   │   ├── PaperAgentBubble.tsx # 🤖 RAG floating agent
│   │   ├── rag/MessageParts.tsx # Render message dùng chung (citation, plan, verification badge)
│   │   ├── NavBar.tsx
│   │   ├── ResultCard.tsx
│   │   └── ...
│   ├── screens/                 # HomeScreen, ResultsScreen, DetailScreen,
│   │                             # ReaderScreen (📖 đọc PDF + hỏi đáp full-page), ChatScreen
│   └── i18n/translations.ts    # EN/VI string table
│
├── run.py                       # 🚀 Launcher 1 lệnh (backend + frontend song song)
├── scripts/
│   ├── download_mineru_models.py # Tải model MinerU (chạy 1 lần)
│   └── setup_supabase.py         # Tạo bucket paper_pdfs (khi dùng Supabase riêng)
├── supabase_migration.sql       # SQL migration cho Supabase riêng (paper_cache + paper_chunks)
├── config.toml                  # (git-ignored) LLM + MinerU config
└── pyproject.toml               # paper-agent CLI package + deps
```

---

## 🛠️ Tech Stack

<table>
<tr>
<th>Layer</th>
<th>Technology</th>
</tr>
<tr>
<td>

**Frontend**

</td>
<td>

React 18 · TypeScript · Vite · Tailwind CSS

</td>
</tr>
<tr>
<td>

**Backend**

</td>
<td>

FastAPI · Python 3.10+ · tenacity · uvicorn

</td>
</tr>
<tr>
<td>

**AI / LLM**

</td>
<td>

OpenAI GPT-4.1 family · Google Gemini 2.5 family

</td>
</tr>
<tr>
<td>

**RAG**

</td>
<td>

MinerU (structure-aware PDF parse) · vector cosine + BM25 (RRF) · cross-encoder rerank · grounding verifier

</td>
</tr>
<tr>
<td>

**Paper Sources**

</td>
<td>

Semantic Scholar · OpenReview · arXiv · OpenAlex · Crossref · DBLP

</td>
</tr>
<tr>
<td>

**Storage**

</td>
<td>

Supabase chung (paper cache + RAG chunks + PDF bucket) · localStorage + SQLite (dữ liệu cá nhân, local)

</td>
</tr>
<tr>
<td>

**Chạy**

</td>
<td>

`python run.py` — backend + frontend song song, local, không cần deploy

</td>
</tr>
</table>

---

## 🧪 Tests

```bash
pytest tests/ -v
```

Toàn bộ test **mock LLM / embedding / Supabase / cross-encoder** — không cần API key hay network:

- `test_agents_mock.py` — gọi trực tiếp `run_search()` / `run_rag_ask()` / `ingest_paper()`, test control
  flow (rewrite loop, dispatcher lane, citation stripping, grounding, metadata chunk).
- `test_backend_agent_integration.py` — qua `TestClient(app)`, test lớp convert Pydantic↔dataclass.
- `test_contract_parity.py` — so field giữa Pydantic request model và dataclass `*Params` tương ứng.

---

## 🤝 Contributing

Pull requests are welcome!

1. Fork repo
2. Tạo feature branch: `git checkout -b feat/ten-tinh-nang`
3. Commit: `git commit -m "feat: mô tả ngắn"`
4. Push & mở PR

**Code style:**
- Backend: [Ruff](https://docs.astral.sh/ruff/) + [pyright](https://github.com/microsoft/pyright)
- Frontend: ESLint + TypeScript strict mode

---

## 📄 License

MIT License — xem file [LICENSE](LICENSE) để biết thêm.

---

<div align="center">

Made with ❤️ by [@kienle141204](https://github.com/kienle141204)

⭐ Star repo nếu bạn thấy hữu ích!

</div>
