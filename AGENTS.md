# Repository Guidelines

## Project Structure & Module Organization

PaperScout is a Python/FastAPI backend with a React/TypeScript frontend.

- `agent/` contains reusable Python business logic and the `paper-agent` CLI. Add integrations and search logic under `agent/tools/`.
- `backend/api.py` is the FastAPI application and currently owns all HTTP endpoints.
- `frontend/src/components/` contains reusable UI pieces, `frontend/src/screens/` contains page-level views, and `frontend/src/services/api.ts` centralizes API calls.
- `frontend/src/types/` holds shared TypeScript models.
- `docker-compose.yml` starts the application stack.

Keep backend transport code in `backend/api.py` and reusable behavior in `agent/`.

## Build, Test, and Development Commands

Run the backend from `backend/`:

```bash
pip install -r requirements.txt
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
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

There is no committed automated test suite yet. Validate backend changes by exercising affected FastAPI endpoints or CLI commands. Validate frontend changes with `npm run build` and a local browser check. When adding tests, use descriptive names tied to behavior, such as `test_search_falls_back_to_openreview`.

## Commit & Pull Request Guidelines

Recent commits use short Conventional Commit-style subjects, for example `feat: add conversational chat AI` and `docs: rewrite README`. Continue using prefixes such as `feat:`, `fix:`, and `docs:`.

Pull requests should summarize behavior changes, list verification commands, link relevant issues, and include screenshots for visible UI updates. Do not commit `.env`, `config.toml`, API keys, or local SQLite data.
