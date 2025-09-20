# Repository Refactor Reference

## Overview
- Goal: streamline the codebase for reusable screener, backtest, grid, and optimizer workflows while standardising Lean CLI usage.
- Scope: frontend feature architecture, filter extensibility, Lean job orchestration, database/data ingestion redesign, validation/testing practices.
- Assumption: existing generated datasets can be discarded; new pipelines will recreate what is needed.

## Frontend Architecture
- Replace the monolithic `SimpleStockScreener` shell with router-driven feature modules (`/screener`, `/backtests`, `/grid`, `/optimizer`).
- Each route mounts only the providers it needs and relies on TanStack Query hooks for API calls instead of ad-hoc contexts.
- Co-locate UI state and service hooks inside feature folders so new screens can be added without touching global wiring.

## Filter Registry & Extensibility
- Introduce a shared filter registry (metadata describing id, label, input controls, validation rules, default ranges, backend key mapping) stored in a source-of-truth file that both frontend and backend import (or consume via generated JSON).
- Render filter components dynamically from that registry; store state as `{ [filterId]: FilterState }` to simplify additions/removals.
- On the backend, hydrate the same registry to build `SimpleFilters` instances—no more hand-coded request parsing per filter.
- All features (screener, grid analysis, optimizer, backtest parameter builders) consume the registry so a new filter automatically appears everywhere once its analytics implementation exists.

## Strategy Registry & Algorithms
- Define a strategy registry describing each Lean algorithm: name, project path, summary, available parameters, defaults, constraints, and supported job types.
- Expose registry metadata through `/api/v2/backtest/strategies`; the frontend renders dynamic forms for backtests, screener-driven runs, and grid sweeps from this schema.
- Lean job orchestration reads the registry entry to construct CLI commands, validate parameter payloads, and attach documentation.
- Adding a strategy becomes a single registry update plus the actual Lean project, ensuring consistent availability across all features.

## Lean Job Orchestration
- Collapse `BacktestManager`, `GridBacktestManager`, and `ParallelBacktestQueueManager` into a unified `LeanJobService` facade. 
  - Accept job types (`BacktestJob`, `GridJob`, `OptimizeJob`).
  - Launch Lean CLI (`backtest`, `optimize`) via shared adapters defined per strategy.
  - Stream progress/log events through one websocket channel.
- Grid runs become parameter sweeps executed through the same queue instead of a special-case pipeline.

## Data Model & Storage
- Normalise persistence around new tables (or views):
  - `run_sessions` (job metadata, strategy, timestamps, status, configuration).
  - `run_targets` (symbol-level inputs, screener linkage).
  - `run_metrics` (key/value aggregates including Sharpe, drawdown, etc.).
  - `run_artifacts` (paths to Lean output, logs, equity curves).
- Build materialised views for fast UI reads (`mv_backtest_summary`, `mv_grid_combined`, etc.).
- After backfilling, retire legacy tables such as `grid_screening`, `grid_market_structure`, and filesystem JSON checkpoints.

## Data Ingestion
- Wrap daily/minute download scripts in a scheduler-aware ingestion service that records jobs/checkpoints in the database (`data_jobs`).
- Allow safe deletion of on-disk checkpoints (`minute_data_checkpoint.json`) since state now lives in SQL.
- Provide status endpoints so the frontend can surface data freshness.

## Testing & Verification
- Backend: add unit/integration tests for filter registry hydration, Lean job translation, database persistence. Fix the current pytest recursion issue before broad changes.
- Frontend: create feature-level RTL tests (and/or Cypress component tests) covering filter toggles, backtest submission, grid sorting with mocked APIs.
- CI: enforce `npm run lint`, `npm run test`, `python3 -m pytest`, and a mocked `lean optimize` smoke run to catch command regressions.

## Execution Roadmap
1. Implement the shared filter registry; refactor frontend filters, backend request parsing, and any feature consumers to use it end-to-end.
2. Build the strategy registry and update Lean job orchestration and frontend forms to consume it uniformly.
3. Introduce the unified `LeanJobService` and migrate existing managers incrementally.
4. Design/run database migrations for the new run-session schema; port APIs to materialised views. *(In progress – run-level persistence now backed by `run_sessions`, `run_targets`, and `run_metrics` with automatic bootstrapping.)*
5. Replace ingestion scripts with the managed service and remove obsolete data folders. *(Minute ingestion now queues through the job service; remaining scripts can be folded into the same runner.)*
6. Re-enable full automated testing and smoke Lean workflows before further cleanup tasks.
7. Expose aggregated run metrics for dashboards. *(Summary endpoints now provide per-job counts, best metrics, and target totals for the UI.)*
