<div align="center">

<img src="https://img.shields.io/badge/PaperScout-v2.1-2563eb?style=for-the-badge&logo=bookstack&logoColor=white" alt="PaperScout" height="36"/>

# 🔬 PaperScout

**Trợ lý research cá nhân chạy local — tìm paper hội nghị lớn trên OpenReview, đọc PDF bằng RAG, lưu note sang Notion**

OpenReview-first · ICLR/NeurIPS/ICML/COLM/EMNLP · Reader + RAG Agent · Notion OAuth · Chạy 1 lệnh, không cần deploy

---

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black)](https://react.dev/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6?style=flat-square&logo=typescript&logoColor=white)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-6-646CFF?style=flat-square&logo=vite&logoColor=white)](https://vite.dev/)
[![OpenReview](https://img.shields.io/badge/Source-OpenReview-8B5CF6?style=flat-square)](https://openreview.net/)

[![MinerU](https://img.shields.io/badge/Parser-MinerU%202-FF6F00?style=flat-square)](https://github.com/opendatalab/MinerU)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4.1-412991?style=flat-square&logo=openai&logoColor=white)](https://openai.com/)
[![Google Gemini](https://img.shields.io/badge/Google-Gemini%202.5-4285F4?style=flat-square&logo=google&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Notion](https://img.shields.io/badge/Export-Notion%20OAuth-000000?style=flat-square&logo=notion&logoColor=white)](https://developers.notion.com/)
[![Supabase](https://img.shields.io/badge/Cache-Shared%20Supabase-3ECF8E?style=flat-square&logo=supabase&logoColor=white)](https://supabase.com/)

</div>

---

## 📸 Tổng quan

PaperScout là **trợ lý research cá nhân chạy trên máy của bạn**. Luồng chính hiện tại là tìm paper ở các hội nghị lớn trên **OpenReview**, mở paper trong Reader, đọc PDF/abstract bằng RAG Agent, rồi lưu reading note sang Notion khi bạn yêu cầu.

Ứng dụng này không cố làm một search engine học thuật tổng quát. Nó ưu tiên một use case hẹp nhưng hữu ích: **tìm paper conference gần đây**, đọc nhanh, hỏi đáp có căn cứ, và gom note vào workspace cá nhân.

Dữ liệu **cá nhân** nằm local: saved papers, memory, Notion OAuth token và mapping paper → Notion page được lưu trong `library.sqlite3` hoặc local browser state. Dữ liệu **paper/cache dùng chung** như cached PDF/chunks có thể dùng Supabase đã cấu hình sẵn trong repo.

```txt
🔍 Tìm paper OpenReview → 📄 Mở Reader → 🤖 Hỏi đáp RAG → 📝 Save to Notion
```

---

## ✨ Tính năng

<table>
<tr>
<td width="50%">

### 🔍 OpenReview-first Search
- Nguồn tìm kiếm chính: **OpenReview API v2** qua `/notes/search`
- Tập trung hội nghị lớn: **ICLR, NeurIPS, ICML, COLM, EMNLP**
- Tìm theo topic/method/task và có thể lọc venue/năm
- Search Agent có guardrail, query analysis, cache/session local
- Xếp hạng kết quả theo relevance score và quality signals

### 💬 Chat & Reader
- Reader Screen hiển thị PDF nếu resolve được link nhúng
- Fallback sang abstract khi PDF bị chặn hoặc không có mirror
- Chat hỏi đáp theo từng paper, giữ history hội thoại
- UI hỗ trợ tiếng Anh/tiếng Việt

</td>
<td width="50%">

### 🤖 RAG Agent per-paper
- Auto-ingest paper khi mở Reader hoặc hỏi đáp
- Parse PDF bằng **MinerU** để giữ section, page, table/block type
- Chunk metadata title/authors/year/venue để hỏi thông tin bibliographic
- Retrieval hybrid: vector + BM25/RRF, có rerank khi khả dụng
- Dispatcher 3 lane: skill → fast → deliberate
- Grounding check: trả lời kèm citation/chunk/page khi có evidence

### 📝 Notion Export
- Chỉ ghi Notion khi người dùng bấm nút `Notion`
- Hỗ trợ **OAuth Public Connection** kiểu "Connect Notion"
- Vẫn hỗ trợ `NOTION_TOKEN` tĩnh cho setup cá nhân nhanh
- Idempotent: lưu mapping paper → Notion page để tránh tạo trùng
- Có thể export summary hoặc full reading note kèm Q&A history

</td>
</tr>
</table>

---

## 🎯 Phạm vi tìm kiếm hiện tại

PaperScout hiện ưu tiên OpenReview thay vì search đa nguồn rộng. Backend endpoint `/api/papers/search` luôn route source về:

```python
sources=["openreview"]
```

Các venue OpenReview đang có trong code:

| Key | Venue |
|---|---|
| `iclr` | ICLR |
| `neurips` | NeurIPS |
| `icml` | ICML |
| `colm` | COLM |
| `emnlp` | EMNLP |

Các nguồn khác vẫn có trong repo nhưng không phải luồng search chính:

| Source | Vai trò hiện tại |
|---|---|
| Semantic Scholar | resolve PDF/citation, detail hoặc flow phụ |
| arXiv | tìm mirror PDF/open-access copy |
| OpenAlex | resolve PDF, related/citation hỗ trợ |
| Crossref/DBLP | helper metadata/citation trong các endpoint phụ |

> OpenReview `/notes/search` yêu cầu có keyword, nên PaperScout không phù hợp để browse toàn bộ conference với query rỗng. Hãy nhập topic cụ thể như `diffusion medical image segmentation`, `long context transformer retrieval`, hoặc `LLM alignment preference optimization`.

---

## 🏗️ Kiến trúc

```txt
┌──────────────────────────────────────────────────────────────────┐
│                            PaperScout                            │
│                                                                  │
│  Frontend (React + TypeScript + Vite)                            │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌─────────┐ │
│  │  Home    │ │ Results  │ │  Detail  │ │ Reader  │ │ Saved   │ │
│  │  Search  │ │ Screen   │ │ Screen   │ │ + RAG   │ │ Library │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬────┘ └────┬────┘ │
│       └────────────┴────────────┴────────────┴───────────┘      │
│                              │ REST API                          │
├──────────────────────────────┼───────────────────────────────────┤
│  Backend (FastAPI)           │                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │ /api/papers/search     OpenReview-first search               │ │
│  │ /api/papers/ingest     PDF/abstract ingest for RAG           │ │
│  │ /api/papers/ask        paper Q&A                             │ │
│  │ /api/notion/connect    Notion OAuth                          │ │
│  │ /api/papers/export/notion  save/update reading note          │ │
│  └───────────┬──────────────────────────────┬───────────────────┘ │
│              │                              │                     │
│  ┌───────────▼───────────┐      ┌───────────▼───────────┐         │
│  │ agent/search/          │      │ agent/rag/             │         │
│  │ Search Agent           │      │ RAG Agent              │         │
│  │ OpenReview route       │      │ ingest/retrieve/answer │         │
│  │ rank/cache/session     │      │ Notion export          │         │
│  └───────────┬───────────┘      └───────────┬───────────┘         │
│              │          agent/core/ budget · guardrail · trace     │
│  ┌───────────▼──────────────────────────────▼───────────────────┐ │
│  │ agent/tools/ OpenReview · PDF resolver · MinerU · Supabase ·  │ │
│  │ LLM/embedding router · Notion SDK/OAuth · local SQLite store  │ │
│  └──────────────────────────────────────────────────────────────┘ │
├──────────────────────────────────────────────────────────────────┤
│  Storage                                                         │
│  ┌──────────────────┐ ┌─────────────────┐ ┌───────────────────┐ │
│  │ OpenReview API   │ │ Shared Supabase │ │ Local SQLite      │ │
│  │ paper metadata   │ │ PDF/chunk cache │ │ memory/notion map │ │
│  └──────────────────┘ └─────────────────┘ └───────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### 🧠 Two-Agent Harness

PaperScout dùng hai agent chính:

```txt
Search Agent (agent/search/)                 RAG Agent (agent/rag/)
─────────────────────────────                ─────────────────────────────
input guardrail                               input guardrail
       │                                             │
       ▼                                             ▼
query analysis / heuristic fallback            auto-ingest if needed
       │                                      PDF → MinerU → chunks → embed
       ▼                                             │
OpenReview `/notes/search`                           ▼
       │                                      dispatcher chooses lane:
score + rank + dedupe                         skill | fast | deliberate
       │                                             │
cache/session optional                               ▼
       ▼                                      grounded answer + citations
SearchRunResult                                      │
                                                     ▼
                                            optional Notion export
```

---

## 🚀 Quick Start

Chạy local trong vài bước. Không cần deploy, không cần account app.

### Yêu cầu

| Tool | Version |
|---|---|
| Python | 3.10+ |
| Node.js | 18+ |
| npm | 9+ |

> RAG PDF parsing dùng **MinerU** nên lần cài đầu có thể nặng. Nếu chỉ tìm paper và đọc abstract, app vẫn chạy được; Reader sẽ fallback abstract-only khi PDF parse không khả dụng.

### 1. Clone

```bash
git clone https://github.com/kienle141204/paper_scout.git
cd paper_scout
```

### 2. Tạo env

```bash
cp backend/.env.example backend/.env
```

Điền ít nhất một provider LLM:

```env
OPENAI_API_KEY=sk-...
# hoặc:
GEMINI_API_KEY=...
```

### 3. Chạy một lệnh

```bash
python run.py
```

Lệnh này tự lo:

- cài Python deps (`pip install -e .`) khi cần;
- cài frontend deps (`npm install`) khi cần;
- chạy backend tại `http://127.0.0.1:8000`;
- chạy frontend tại `http://localhost:5173`.

Mở browser ở:

```txt
http://localhost:5173
```

---

## 🔧 Cấu hình tùy chọn

<details>
<summary>Notion OAuth: bấm Connect giống các app hiện đại</summary>

Tạo Public Connection trong Notion Developer Portal và đặt redirect URI:

```txt
http://localhost:8000/api/notion/callback
```

Thêm vào `backend/.env`:

```env
NOTION_OAUTH_CLIENT_ID=...
NOTION_OAUTH_CLIENT_SECRET=...
NOTION_OAUTH_REDIRECT_URI=http://localhost:8000/api/notion/callback
```

Trong Reader, bấm `Connect`/`Notion`, chọn page/workspace trong Notion, rồi quay lại PaperScout. Token OAuth được lưu local trong `library.sqlite3`. Nếu không đặt target database/page, PaperScout tạo private page ở workspace level và lưu mapping để lần sau update cùng page.

</details>

<details>
<summary>Notion token tĩnh: phù hợp cho setup cá nhân nhanh</summary>

Thêm vào `backend/.env`:

```env
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=...
# hoặc:
NOTION_PARENT_PAGE_ID=...
```

Nếu dùng `NOTION_DATABASE_ID`, database cần có property dạng `rich_text` tên:

```txt
PaperScout Key
```

Property này dùng để tìm page đã có và tránh duplicate.

</details>

<details>
<summary>Model và parser qua <code>config.toml</code></summary>

Tạo `config.toml` ở repo root nếu muốn đổi model/provider:

```toml
[llm]
provider = "openai"   # hoặc "gemini"

[openai]
model = "gpt-4.1-mini"
cheap_model = "gpt-4.1-nano"
analysis_model = "gpt-4.1"

[gemini]
model = "gemini-2.5-flash"
cheap_model = "gemini-2.0-flash-lite"
analysis_model = "gemini-2.5-pro"
base_url = "https://generativelanguage.googleapis.com/v1beta"

[parser]
parser = "mineru"
mineru_backend = "pipeline"
mineru_device = "cpu"
mineru_lang = "en"
mineru_model_source = "huggingface"
mineru_max_pages = 10
```

Nếu cần tải model MinerU trước:

```bash
python scripts/download_mineru_models.py
```

</details>

<details>
<summary>Dùng Supabase riêng thay vì DB/cache chung</summary>

PaperScout có shared Supabase mặc định trong `agent/tools/shared_supabase.py`. Nếu muốn dùng Supabase riêng:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_PUBLISHABLE_KEY=sb_publishable_...
# hoặc SUPABASE_ANON_KEY nếu dùng key JWT cũ
SUPABASE_SECRET_KEY=sb_secret_...
```

Sau đó chạy migration SQL trong Supabase SQL Editor:

- `supabase_migration.sql`
- `supabase_migration_rag.sql`

Và tạo storage bucket bằng:

```bash
python scripts/setup_supabase.py
```

</details>

---

## 🧪 Tests

```bash
pytest tests/ -v
```

Toàn bộ test mock LLM, embedding, Supabase, cross-encoder và Notion network/SDK, nên không cần API key thật.

- `tests/test_agents_mock.py` — Search Agent/RAG Agent trực tiếp.
- `tests/test_backend_agent_integration.py` — FastAPI endpoint qua `TestClient`.
- `tests/test_contract_parity.py` — parity Pydantic request model ↔ dataclass params.
- `tests/test_notion_client.py` — Notion wrapper, OAuth local store, payload create/update.

Validate frontend:

```bash
cd frontend
npm run build
```

---

## 🖥️ Chạy thủ công

Backend từ repo root:

```bash
pip install -e .
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

Frontend từ `frontend/`:

```bash
npm install
npm run dev
npm run build
npm run preview
```

CLI sau khi `pip install -e .`:

```bash
paper-agent init
paper-agent search "diffusion medical image segmentation"
paper-agent major-search --venue iclr --year 2025 --query "retrieval augmented generation"
```

---

## ⚠️ Giới hạn hiện tại

- Search chính là OpenReview-first, chưa phải search tổng quát trên toàn bộ web học thuật.
- `/api/papers/search` hiện ép source về `openreview` để giữ UX ổn định.
- OpenReview `/notes/search` cần keyword; query rỗng hoặc quá chung sẽ ít hữu ích.
- OpenReview thường chặn anonymous PDF download/iframe; backend sẽ resolve mirror qua arXiv/Semantic Scholar/OpenAlex hoặc fallback abstract.
- RAG tốt nhất khi parse được PDF. Abstract-only mode chỉ trả lời được những gì có trong abstract/metadata.
- Notion export là side effect có chủ ý, chỉ chạy khi người dùng bấm nút hoặc gọi endpoint export.

---

## 🤝 Contributing

Pull requests nên:

1. Tóm tắt thay đổi hành vi.
2. Liệt kê command đã verify.
3. Có screenshot nếu thay đổi UI.
4. Không commit `.env`, `config.toml`, token/API key, SQLite local data.
5. Chạy `pytest tests/ -v` cho backend/agent và `npm run build` cho frontend.

**Code style:**

- Python: 4-space indentation, `snake_case`.
- TypeScript/React: 2-space indentation, component `PascalCase`, function/value `camelCase`.
- Giữ transport code trong `backend/api.py`; reusable behavior ở `agent/`.

---

## 📄 License

MIT License — xem file [LICENSE](LICENSE) để biết thêm.

---

<div align="center">

Made with ❤️ by [@kienle141204](https://github.com/kienle141204)

⭐ Star repo nếu bạn thấy hữu ích!

</div>
