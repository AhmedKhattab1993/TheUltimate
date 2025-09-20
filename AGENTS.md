# Repository Guidelines

## Project Structure & Module Organization
- `backend/app/` contains the FastAPI application: `api/` routers, `services/` integrations, `core/` business rules, and `schemas/` for Pydantic models. Entry point lives in `backend/run.py`.
- `frontend/src/` houses the React + TypeScript UI. Key folders are `components/`, `hooks/`, `services/` for API clients, and `utils/` for shared helpers.
- Root-level `data/`, `grid/`, and `pipeline_results/` store generated datasets and analysis artifacts; keep large exports out of version control.
- The top-level `Makefile` orchestrates cross-cutting tasks, while `docker-compose.yml` and `start.sh` provide full-stack startup scripts.

## Build, Test, and Development Commands
- `make install` installs Python and Node dependencies (`backend/requirements.txt`, `frontend/package.json`).
- `make start` or `./start.sh` launches both services; `make backend` and `make frontend` run them individually.
- `python3 backend/run.py` starts the API; `npm run dev --prefix frontend` spins up Vite with hot reload.
- `make test` sequences backend pytest runs and API smoke checks; use `npm run test`, `npm run lint`, and `npm run build` inside `frontend/` for UI validation.

## Coding Style & Naming Conventions
- Python code follows PEP 8 with four-space indents, type hints, and descriptive function names (e.g., `fetch_screener_results`). Prefer module-level constants over magic numbers.
- TypeScript uses ESLint’s recommended + React Hooks configs; keep components PascalCase and hooks camelCase. Favor `src/services/*` for API adapters and colocate styles with components.
- Run `npm run lint` and format imports before opening PRs; align Python logging with the structured patterns in `app/main.py`.

## Testing Guidelines
- Backend tests live under `backend/` and root-level `test_*.py` utilities; execute with `python -m pytest`. Name new suites `test_<feature>.py` and isolate Polygon calls behind fixtures.
- Frontend tests reside in `frontend/src/test/` and `.test.tsx` files; run `npm run test` (or `npm run test:coverage` before releases). Snapshot tests should include stable seed data from `data/` exports.

## Commit & Pull Request Guidelines
- Git history favors imperative, high-level summaries (e.g., “Add filter toggle functionality…”). Keep subject lines under 72 characters and highlight the surface area touched.
- Each PR should describe the user-facing impact, list manual/run tests, and link related issues. Include screenshots or GIFs for UI tweaks and note any new environment variables or migrations.
- Request reviews early for large backend changes so API contracts stay aligned with the frontend.
