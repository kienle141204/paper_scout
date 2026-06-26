# Repository Guidelines

## Project Structure & Module Organization

PaperScout is a Python/FastAPI backend with a React/TypeScript frontend.

- `agent/` contains reusable Python business logic and the `paper-agent` CLI. It has two parts: the **two-agent harness** — `agent/core/` (shared budget/governor/guardrail/trace), `agent/search/` (Search Agent — query rewrite/sufficiency loop), `agent/rag/` (RAG Agent — skill/fast/deliberate dispatcher) — documented in detail in `agent/agent-harness-design.md`; and `agent/tools/` for search-source integrations (Semantic Scholar, arXiv, OpenAlex…) and the shared LLM/embedding router. Add new search-source integrations under `agent/tools/`; add to the harness itself under `agent/core|search|rag/`.
- `backend/api.py` is the FastAPI application and currently owns all HTTP endpoints. It converts Pydantic request models into the harness's plain dataclasses (e.g. `SearchParams`, `RagAskParams`) before calling into `agent/` — keep `agent/` itself FastAPI-free.
- `frontend/src/components/` contains reusable UI pieces, `frontend/src/screens/` contains page-level views, and `frontend/src/services/api.ts` centralizes API calls.
- `frontend/src/types/` holds shared TypeScript models.
- `docker-compose.yml` starts the application stack.

Keep backend transport code in `backend/api.py` and reusable behavior in `agent/`.

## Build, Test, and Development Commands

Run the backend from the **repository root** — `agent/` is imported as `agent.*` and must be on the Python path; running `uvicorn` from inside `backend/` without installing the package first will raise `ModuleNotFoundError: agent`:

```bash
pip install -r backend/requirements.txt
uvicorn backend.api:app --host 0.0.0.0 --port 8000 --reload
```

Run the frontend from `frontend/`:

```bash
npm install
npm run dev       # Vite development server
npm run build     # Type-check and create the production bundle
npm run preview   # Serve the production bundle locally
```

From the repository root, `pip install -e .` installs the CLI. Use `paper-agent init` to create a sample `config.toml`. Run the full stack with `docker-compose up --build`.

## Coding Style & Naming Conventions

Use four-space indentation and `snake_case` for Python modules, functions, and variables. Keep provider-specific integrations in focused modules such as `agent/tools/openalex_search.py`. For TypeScript, follow the existing two-space indentation, use `PascalCase` for React components and screens, and use `camelCase` for functions and values. Keep shared types in `frontend/src/types/`.

No formatter or linter is configured, so match surrounding code and run `npm run build` before submitting frontend changes.

## Testing Guidelines

Run `pytest tests/ -v` from the repository root. The suite mocks every LLM/embedding/Supabase/cross-encoder call — no API key or network access needed:
- `tests/test_agents_mock.py` — calls `run_search()`/`run_rag_ask()`/`ingest_paper()` directly; covers rewrite loop, dispatcher lanes, citation stripping, grounding refusal.
- `tests/test_backend_agent_integration.py` — drives the same flows through `TestClient(app)`, exercising the Pydantic→dataclass conversion layer in `backend/api.py` that the direct-call tests skip.
- `tests/test_contract_parity.py` — diffs fields between each Pydantic request model and its mirrored dataclass (e.g. `PaperSearchRequest` vs `SearchParams`) to catch drift when one side gains a field and the other doesn't.

Use descriptive test names tied to behavior, such as `test_search_falls_back_to_openreview`. Validate frontend changes with `npm run build` and a local browser check.

## Commit & Pull Request Guidelines

Recent commits use short Conventional Commit-style subjects, for example `feat: add conversational chat AI` and `docs: rewrite README`. Continue using prefixes such as `feat:`, `fix:`, and `docs:`.

Pull requests should summarize behavior changes, list verification commands, link relevant issues, and include screenshots for visible UI updates. Do not commit `.env`, `config.toml`, API keys, or local SQLite data.
