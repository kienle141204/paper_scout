<div align="center">

<img src="https://img.shields.io/badge/PaperScout-v2.0-2563eb?style=for-the-badge&logo=bookstack&logoColor=white" alt="PaperScout" height="36"/>

# 🔬 PaperScout

**AI-powered academic paper discovery with a built-in RAG reasoning agent**

Tìm kiếm đa nguồn · Dịch tiếng Việt · Chat AI · RAG Agent per-paper · Xác thực người dùng

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Cache%20%26%20Auth-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com/)
[![Railway](https://img.shields.io/badge/Deploy-Railway-0B0D0E?style=flat-square&logo=railway&logoColor=white)](https://railway.app/)

[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com/)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.5-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Semantic Scholar](https://img.shields.io/badge/Source-Semantic%20Scholar-D62728?style=flat-square)](https://www.semanticscholar.org/)
[![arXiv](https://img.shields.io/badge/Source-arXiv-B31B1B?style=flat-square)](https://arxiv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## 📸 Tổng quan

PaperScout là ứng dụng web hỗ trợ tìm kiếm, đọc và phân tích bài báo khoa học bằng AI. Điểm nổi bật là **RAG Agent per-paper** — mỗi bài báo có một AI riêng đọc toàn bộ PDF và trả lời câu hỏi với trích dẫn chính xác đến từng đoạn.

```
📄 Tìm paper → 🧠 AI phân tích → 💬 Hỏi đáp với RAG Agent → 🌐 Dịch tiếng Việt
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
- Fallback thông minh khi S2 rate-limit

### 💬 Chat AI
- Conversational agent tìm kiếm bằng ngôn ngữ tự nhiên (VI/EN)
- Actions: `search` · `filter` · `clarify` · `done`
- Filter client-side không cần gọi lại backend

</td>
<td width="50%">

### 🤖 RAG Agent per-paper *(mới)*
- Floating bubble ở góc phải, mở thành side-panel 40% màn hình
- **4-phase reasoning**: Plan → Gather → Answer → Verify
- Tải PDF từ arXiv/OpenReview, parse và chunk (~400 tokens, overlap 80)
- Vector store trong Supabase (Python cosine, không cần pgvector)
- Trả lời có **trích dẫn `[1][2]`** kèm đoạn văn gốc
- Hiển thị độ tin cậy, độ phủ, cảnh báo hallucination

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
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐  │
│   │  Search  │ │  Detail  │ │  Chat    │ │  RAG Bubble     │  │
│   │  Screen  │ │  Screen  │ │  Screen  │ │  (side panel)   │  │
│   └────┬─────┘ └────┬─────┘ └────┬─────┘ └────────┬────────┘  │
│        │             │             │                │            │
│        └─────────────┴─────────────┴────────────────┘           │
│                              │ REST API                         │
├──────────────────────────────┼──────────────────────────────────┤
│   Backend (FastAPI)          │                                  │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │  /api/papers/search  │  /api/chat  │  /api/papers/ask    │ │
│   │  /api/papers/view    │  /api/...   │  /api/papers/ingest │ │
│   └──────────┬────────────────────────────────┬───────────────┘ │
│              │                                │                  │
│   ┌──────────▼──────────┐      ┌─────────────▼─────────────┐   │
│   │   agent/ (Python)   │      │   RAG Pipeline             │   │
│   │  S2 · OpenReview    │      │   pdf_fetcher → chunker    │   │
│   │  arXiv · OpenAlex   │      │   rag_store (Supabase)     │   │
│   │  LLM · embeddings   │      │   Plan→Gather→Answer→Verify│   │
│   └─────────────────────┘      └────────────────────────────┘   │
├──────────────────────────────────────────────────────────────────┤
│   Infrastructure                                                 │
│   ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│   │   Supabase    │  │  OpenAI/Gemini  │  │     Railway      │  │
│   │  paper_cache  │  │  LLM · Embed    │  │    Hosting       │  │
│   │  paper_chunks │  │                 │  │                  │  │
│   │  app_users    │  │                 │  │                  │  │
│   └───────────────┘  └─────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 🧠 RAG Agent — 4-Phase Pipeline

```
Question
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 1 · PLAN  (cheap model)                                │
│  Decompose → sub_questions + search_queries + sections       │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 2 · GATHER  (parallel)                                 │
│  Embed queries in parallel → cosine search per query         │
│  + Section-targeted retrieval → deduplicate → ≤14 chunks     │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 3 · ANSWER  (standard model)                           │
│  Numbered context → grounded answer with [1][2] citations    │
│  → confidence (high/medium/low) + coverage (full/partial)    │
└──────────────────────┬───────────────────────────────────────┘
                       │
                       ▼
┌──────────────────────────────────────────────────────────────┐
│ Phase 4 · VERIFY  (cheap model)                              │
│  Check hallucination risk → auto-refine if medium/high       │
└──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### Yêu cầu

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

### 1. Clone & cài đặt

```bash
git clone https://github.com/kienle141204/paper_scout.git
cd paper_scout
```

### 2. Backend

```bash
# Tạo virtual environment
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# Cài dependencies
pip install -r backend/requirements.txt

# Cấu hình
cp backend/.env.example backend/.env   # điền API keys
```

Tạo `config.toml` ở root:

```toml
[llm]
provider = "openai"   # hoặc "gemini"

[openai]
model        = "gpt-4.1-mini"
cheap_model  = "gpt-4.1-nano"
analysis_model = "gpt-4.1"

# Hoặc dùng Gemini:
# [llm]
# provider = "gemini"
# [gemini]
# model          = "gemini-2.5-flash"
# cheap_model    = "gemini-2.0-flash-lite"
# analysis_model = "gemini-2.5-pro"
```

```bash
# Chạy backend
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Frontend

```bash
cd frontend
cp .env.example .env              # VITE_API_URL=http://localhost:8000
npm install
npm run dev
```

Frontend: `http://localhost:5173` · Backend: `http://localhost:8000`

### 4. Supabase (tùy chọn — cần cho cache và RAG)

Vào **Supabase Dashboard → SQL Editor** và chạy:

```sql
-- Bảng cache abstract + analysis
CREATE TABLE IF NOT EXISTS paper_cache (
  paper_id      TEXT PRIMARY KEY,
  abstract_vi   TEXT,
  analysis_html TEXT,
  created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Bảng RAG chunks (vector store)
CREATE TABLE IF NOT EXISTS paper_chunks (
  id          BIGSERIAL PRIMARY KEY,
  paper_id    TEXT NOT NULL,
  chunk_index INT  NOT NULL,
  section     TEXT,
  text        TEXT NOT NULL,
  embedding   TEXT NOT NULL,
  token_count INT,
  created_at  TIMESTAMPTZ DEFAULT NOW(),
  UNIQUE (paper_id, chunk_index)
);
CREATE INDEX IF NOT EXISTS paper_chunks_paper_id_idx ON paper_chunks (paper_id);
ALTER TABLE paper_chunks DISABLE ROW LEVEL SECURITY;

-- Bảng user (auth)
CREATE TABLE IF NOT EXISTS app_users (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email         TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  display_name  TEXT,
  language_pref TEXT DEFAULT 'vi',
  created_at    TIMESTAMPTZ DEFAULT NOW()
);
```

---

## ⚙️ Cấu hình

### Backend (`backend/.env`)

| Biến | Bắt buộc | Mô tả |
|------|----------|--------|
| `OPENAI_API_KEY` | Nếu dùng OpenAI | LLM + embeddings |
| `GEMINI_API_KEY` | Nếu dùng Gemini | Thay thế OpenAI |
| `SEMANTIC_SCHOLAR_API_KEY` | Không | Tăng rate limit S2 |
| `SUPABASE_URL` | Cho cache/RAG/auth | URL project Supabase |
| `SUPABASE_ANON_KEY` | Cho cache & RAG | Anon key (paper_cache, paper_chunks) |
| `SUPABASE_SERVICE_ROLE_KEY` | Cho auth | Service role key (bypass RLS cho app_users) |
| `JWT_SECRET` | Không | JWT signing secret (default: insecure dev value) |

### Frontend (`frontend/.env`)

| Biến | Mô tả |
|------|--------|
| `VITE_API_URL` | Backend URL (`http://localhost:8000` khi dev; `''` khi cùng origin) |

### LLM Tiers

| Tier | Dùng cho | OpenAI | Gemini |
|------|----------|--------|--------|
| `cheap_model` | translate, summarize, plan, verify | `gpt-4.1-nano` | `gemini-2.0-flash-lite` |
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
| `POST` | `/api/papers/ingest` | Download PDF → chunk → embed → store |
| `POST` | `/api/papers/ask` | RAG Q&A với 4-phase reasoning |

### Auth

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| `POST` | `/auth/register` | Đăng ký tài khoản |
| `POST` | `/auth/login` | Đăng nhập → JWT |
| `GET` | `/auth/me` | Profile user (Bearer token) |
| `PATCH` | `/auth/me` | Cập nhật display_name / language_pref |

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
├── 📂 agent/                    # Pure Python business logic
│   ├── config.py                # Config dataclass + load_config()
│   ├── model.py                 # Paper dataclass
│   ├── cli.py                   # paper-agent CLI
│   └── tools/
│       ├── llm_text.py          # LLM router (OpenAI / Gemini)
│       ├── prompts.py           # System prompts (chat, RAG plan/answer/verify)
│       ├── semantic_scholar.py  # S2 search (primary)
│       ├── paper_search.py      # Multi-source orchestrator
│       ├── abstract_tools.py    # translate_abstract_vi, summarize
│       ├── relevance.py         # Embedding cosine ranking
│       ├── pdf_fetcher.py       # 📄 Download PDF (arXiv/OpenReview)
│       ├── pdf_parser.py        # pypdf text extraction
│       ├── chunker.py           # Text chunking (~400 tokens, overlap 80)
│       ├── rag_store.py         # 🗄️ Supabase vector store (paper_chunks)
│       ├── paper_cache.py       # Supabase cache (abstract_vi, analysis)
│       └── library.py           # SQLite local library CRUD
│
├── 📂 backend/
│   └── api.py                   # FastAPI — tất cả endpoints
│
├── 📂 frontend/src/
│   ├── App.tsx                  # Root — routing + shared state
│   ├── contexts/                # AuthContext, LanguageContext
│   ├── types/                   # paper.ts, chat.ts, rag.ts
│   ├── services/api.ts          # API calls + mappers
│   ├── components/
│   │   ├── PaperAgentBubble.tsx # 🤖 RAG floating agent
│   │   ├── NavBar.tsx
│   │   ├── ResultCard.tsx
│   │   └── ...
│   ├── screens/                 # HomeScreen, ResultsScreen, DetailScreen, ChatScreen
│   └── i18n/translations.ts    # EN/VI string table
│
├── supabase_migration_rag.sql   # SQL migration cho paper_chunks
├── config.toml                  # (git-ignored) LLM config
└── pyproject.toml               # paper-agent CLI package
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

FastAPI · Python 3.10+ · tenacity · python-jose · bcrypt

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

Supabase (PostgreSQL) · SQLite (local library)

</td>
</tr>
<tr>
<td>

**Auth**

</td>
<td>

JWT (HS256, 30 ngày) · bcrypt password hashing

</td>
</tr>
<tr>
<td>

**Deploy**

</td>
<td>

Railway (backend) · Vercel-ready (frontend)

</td>
</tr>
</table>

---

## 🚂 Deploy lên Railway

```bash
# Backend tự detect từ railway.toml
# Đặt các env vars sau trong Railway dashboard:
OPENAI_API_KEY=...
SUPABASE_URL=...
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
JWT_SECRET=...
```

Frontend: deploy trực tiếp bằng Vercel hoặc Railway Static Site.
Đặt `VITE_API_URL` trỏ tới URL backend Railway.

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
