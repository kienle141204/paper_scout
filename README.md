<div align="center">

<img src="https://img.shields.io/badge/PaperScout-v2.0-2563eb?style=for-the-badge&logo=bookstack&logoColor=white" alt="PaperScout" height="36"/>

# 🔬 PaperScout

**Trợ lý research cá nhân chạy local — với RAG reasoning agent tích hợp**

Tìm kiếm đa nguồn · Dịch tiếng Việt · Chat AI · RAG Agent per-paper · Chạy 1 lệnh, không cần deploy

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vitejs.dev/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3-06B6D4?style=flat-square&logo=tailwindcss&logoColor=white)](https://tailwindcss.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Shared%20Paper%20DB-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com/)

[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com/)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.5-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Semantic Scholar](https://img.shields.io/badge/Source-Semantic%20Scholar-D62728?style=flat-square)](https://www.semanticscholar.org/)
[![arXiv](https://img.shields.io/badge/Source-arXiv-B31B1B?style=flat-square)](https://arxiv.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)

</div>

---

## 📸 Tổng quan

PaperScout là **trợ lý research cá nhân chạy trên máy của bạn** — clone repo, thêm API key LLM, chạy một lệnh là có ngay app tìm kiếm/đọc/phân tích paper bằng AI. Không cần đăng nhập, không cần deploy. Điểm nổi bật là **RAG Agent per-paper** — mỗi bài báo có một AI riêng đọc toàn bộ PDF và trả lời câu hỏi với trích dẫn chính xác đến từng đoạn.

Dữ liệu **cá nhân** (paper đã lưu, lịch sử, ngôn ngữ) nằm ngay trên máy (trình duyệt / SQLite local). Dữ liệu **paper dùng chung** (bản dịch, RAG chunks) nằm trên một Supabase chung đã được cấu hình sẵn — bạn không phải set up gì.

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

### 🤖 RAG Agent per-paper
- 2 cách dùng: floating bubble (góc phải, mở thành side-panel 40% màn hình) hoặc **Reader Screen** *(mới)* — đọc PDF thật qua iframe + chat full-page, mở từ nút "Đọc & hỏi đáp" ở trang Detail
- **Dispatcher 3-lane**: skill (quy trình cố định) → fast (1-lượt) → deliberate (ReAct loop multi-hop), tự escalate khi lane rẻ hơn không xử lý được
- Tải PDF từ arXiv/OpenReview/openAccessPdf link, parse và chunk (~400 tokens, overlap 80)
- Vector store trong Supabase (Python cosine, không cần pgvector)
- Trả lời có **trích dẫn `[1][2]`** kèm đoạn văn gốc
- Hiển thị độ tin cậy, độ phủ, cảnh báo hallucination; budget governor tự giảm cấp khi vượt thời gian/token cho phép

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
│   │  /api/papers/view    │  /api/...   │  /api/papers/ingest │ │
│   └──────────┬────────────────────────────────┬───────────────┘ │
│              │                                │                  │
│   ┌──────────▼──────────┐      ┌─────────────▼─────────────┐   │
│   │  agent/search/      │      │   agent/rag/               │   │
│   │  Search Agent        │      │   RAG Agent                │   │
│   │  rewrite/sufficiency │      │   dispatcher 3-lane        │   │
│   │  loop · synthesis    │      │   skill/fast/deliberate    │   │
│   └──────────┬──────────┘      └─────────────┬─────────────┘   │
│              │      agent/core/ (budget · governor · guardrail · trace) │
│   ┌──────────▼──────────────────────────────────▼─────────────┐ │
│   │  agent/tools/ — S2 · OpenReview · arXiv · OpenAlex ·       │ │
│   │  LLM router · embeddings · pdf_fetcher · chunker · rag_store│ │
│   └─────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│   Infrastructure                                                 │
│   ┌───────────────┐  ┌─────────────────┐  ┌──────────────────┐  │
│   │ Supabase CHUNG│  │  OpenAI/Gemini  │  │  Local (trên máy)│  │
│   │  paper_cache  │  │  LLM · Embed    │  │  localStorage    │  │
│   │  paper_chunks │  │                 │  │  library.sqlite3 │  │
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
       ▼                                     dispatcher → chọn lane:
search đa nguồn (S2 → fallback OpenReview)   ┌─────────┬────────┬────────────┐
       │                                     │  skill  │  fast  │ deliberate │
score_and_rank (embedding cosine)            │ quy trình│ 1-lượt │ ReAct loop │
       │                                     │ cố định  │retrieve│  có budget │
chưa đủ "tốt"? rewrite query, lặp lại        │(tóm tắt…)│+rerank │  governor  │
  (tới max_iterations hoặc diminishing)       │ escalate │+generate│ (multi-hop)│
       │                                     │ nếu fail │        │            │
include_synthesis? → synthesize() có trích   └─────────┴────────┴────────────┘
dẫn [n], strip citation giả                          │
       │                                     check_grounded() → output guardrail
       ▼                                     refuse nếu hallucination risk cao
SearchRunResult                                       ▼
                                              RagAskResult (answer + citations
                                              + confidence + coverage)
```

---

## 🚀 Quick Start

Chạy local trong **3 bước**. Không cần đăng nhập, không cần deploy, không cần tự dựng database.

### Yêu cầu

| Tool | Version |
|------|---------|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

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

### 3. Chạy một lệnh

```bash
python run.py
```

Lệnh này tự lo phần còn lại: cài dependency Python (`pip install -e .`) và frontend
(`npm install`) ở lần đầu, rồi khởi động **cả backend lẫn frontend** song song.

Mở trình duyệt tại **`http://localhost:5173`** · Backend chạy ở `http://localhost:8000`.
Nhấn `Ctrl+C` để dừng cả hai.

<details>
<summary>Tùy chọn: đổi provider/model qua <code>config.toml</code></summary>

Tạo `config.toml` ở root (mặc định dùng OpenAI nếu bỏ qua):

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
```

</details>

<details>
<summary>Tùy chọn: dùng Supabase RIÊNG của bạn thay vì DB chung</summary>

Đặt `SUPABASE_URL` + `SUPABASE_ANON_KEY` trong `backend/.env` để ghi đè DB chung, rồi chạy
[`supabase_migration_rag.sql`](supabase_migration_rag.sql) trong Supabase SQL Editor để tạo bảng
`paper_cache` + `paper_chunks`.

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
| `SUPABASE_ANON_KEY` | Không | Anon key cho Supabase riêng (đi kèm `SUPABASE_URL`) |

### Frontend (`frontend/.env`)

| Biến | Mô tả |
|------|--------|
| `VITE_API_URL` | Backend URL — để trống cũng được (vite proxy `/api` → `:8000` khi dev) |

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
| `GET` | `/api/agent/status` | Kiểm tra Supabase cache + RAG vector store đã cấu hình chưa |
| `POST` | `/api/papers/ingest` | Download PDF → chunk → embed → store (idempotent, fallback abstract) |
| `POST` | `/api/papers/ask` | RAG Q&A — dispatcher 3-lane (skill/fast/deliberate) + grounding check |

### Utilities (paper)

| Method | Endpoint | Mô tả |
|--------|----------|--------|
| `POST` | `/api/papers/citation` | APA / BibTeX từ DOI |
| `POST` | `/api/papers/recommend` | Paper liên quan / citing (OpenAlex) |
| `POST` | `/api/papers/score` | Relevance score qua embedding cosine |
| `POST` | `/api/papers/pdf/parse` | Upload PDF → parse text |

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
│   ├── config.py                # Config dataclass + load_config()
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
│   │   ├── tools.py                  # retrieve, rerank, generate, check_grounded
│   │   ├── ingest.py                 # 📄 fetch PDF → chunk → embed → store
│   │   └── state.py                  # RagAskParams (mirror RagAskRequest)
│   │
│   └── tools/                   # Search-source integrations + utility chung
│       ├── llm_text.py          # LLM router (OpenAI / Gemini)
│       ├── prompts.py           # System prompts
│       ├── semantic_scholar.py  # S2 search (đường khác — dùng cho paper_search.py/OpenAlex)
│       ├── paper_search.py      # OpenReview orchestrator
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
│   │   ├── rag/MessageParts.tsx # Render message dùng chung (citation, plan, verification)
│   │   ├── NavBar.tsx
│   │   ├── ResultCard.tsx
│   │   └── ...
│   ├── screens/                 # HomeScreen, ResultsScreen, DetailScreen,
│   │                             # ReaderScreen (📖 đọc PDF + hỏi đáp full-page), ChatScreen
│   └── i18n/translations.ts    # EN/VI string table
│
├── run.py                       # 🚀 Launcher 1 lệnh (backend + frontend song song)
├── supabase_migration_rag.sql   # SQL migration cho Supabase riêng (tùy chọn)
├── config.toml                  # (git-ignored) LLM config
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

Supabase chung (paper cache + RAG chunks) · localStorage + SQLite (dữ liệu cá nhân, local)

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
