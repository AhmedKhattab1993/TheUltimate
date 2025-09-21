# Repository Guidelines

## Project Structure & Module Organization
- `backend/app` contains the FastAPI service: `api/` for routers, `services/` for data pipelines, and `models/` for Pydantic schemas. Reuse shared utilities instead of duplicating logic.
- `backend/tests` mirrors the service layout; add new suites next to the code they exercise. Data fixtures live under `backend/tests/data`.
- `frontend/src` holds the Vite + React client. Place UI primitives in `components/ui`, feature views in the matching `components/*` folder, and shared state under `contexts/`.
- Integration helpers sit in `scripts/` and orchestration entry points (`start.py`, `stop.py`, `Makefile`).
- Minute bars live in `backend/lean/data/equity/usa/minute/<symbol>/<YYYYMMDD>_trade.zip` (QuantConnect format). Daily OHLCV is stored in Timescale `daily_bars`; inspect with `psql postgresql://postgres:postgres@localhost:5432/stock_screener -c "SELECT MIN(time), MAX(time) FROM daily_bars"`.
- Top-level `data/` holds shared resources such as `symbol_mapping.json` used by ingestion jobs.

## Build, Test, and Development Commands
- `make start` boots both services (same as `python3 start.py`).
- `cd backend && python3 run.py` runs the API locally; pair with `npm run dev` in `frontend/` for the UI.
- `make test` executes backend pytest suites and the API smoke check (`python3 test_screener.py`).
- Frontend quality gates: `npm run lint`, `npm run test`, and `npm run test:coverage` for Vitest coverage output.

## Coding Style & Naming Conventions
- Python: target Python 3.11, follow PEP 8 with 4-space indents, keep functions typed, and group imports (stdlib, third-party, local). FastAPI endpoints should return Pydantic models defined in `app/models`.
- TypeScript/React: enable strict types, prefer `PascalCase` for components and `camelCase` for hooks/utils. Styling follows Tailwind tokens; colocate component-specific styles. Run `npm run lint` before pushing to satisfy the ESLint config in `frontend/eslint.config.js`.

## Testing Guidelines
- Backend unit and async tests belong in `backend/tests` with filenames matching `test_*.py`; mark coroutine tests with `pytest.mark.asyncio`. Use factories or fixtures instead of hitting live APIs.
- Frontend tests live alongside code (`*.test.tsx`). Import helpers from `frontend/src/test/test-utils.tsx` for consistent providers. Include coverage runs when touching shared state or hooks.

## Commit & Pull Request Guidelines
- Follow the existing short, imperative commit style (`feat: refine filter thresholds`). Group related changes and avoid multi-feature commits.
- Before opening a PR, ensure both lint and test suites pass, describe user-facing changes, link relevant tickets, and add screenshots or curl samples when API or UI output changes.

## Security & Configuration Tips
- Never commit secrets; copy `backend/.env.example` and supply keys locally. Backend service URLs are configured in `frontend/src/services/api.ts`—update documentation if endpoints move.
