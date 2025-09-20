"""Repository helpers for backtest results persisted in PostgreSQL."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional
from uuid import UUID, uuid4

from asyncpg import Record

from .database import DatabasePool, DatabaseTransaction, db_pool


@dataclass
class BacktestResultEntry:
    """Stored metrics for a single symbol produced by a Lean run."""

    id: UUID
    run_id: UUID
    symbol: Optional[str]
    parameters: Dict[str, Any]
    metrics: Dict[str, Any]
    status: str
    created_at: datetime


class BacktestRepository:
    """CRUD helpers for the `backtest_results` table."""

    def __init__(self, pool: DatabasePool | None = None) -> None:
        self._pool = pool or db_pool

    async def upsert_result(
        self,
        run_id: UUID,
        *,
        symbol: Optional[str],
        parameters: Optional[Dict[str, Any]] = None,
        metrics: Optional[Dict[str, Any]] = None,
        status: str = "completed",
    ) -> None:
        """Upsert a single backtest result row."""

        params_json = json.dumps(parameters or {}, default=str)
        metrics_json = json.dumps(metrics or {}, default=str)

        query = """
        INSERT INTO backtest_results (
            id,
            run_id,
            symbol,
            parameters,
            metrics,
            status
        ) VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)
        ON CONFLICT (run_id, symbol)
        DO UPDATE SET
            parameters = EXCLUDED.parameters,
            metrics = EXCLUDED.metrics,
            status = EXCLUDED.status
        """

        await self._pool.execute(
            query,
            uuid4(),
            run_id,
            symbol,
            params_json,
            metrics_json,
            status,
        )

    async def replace_results(
        self,
        run_id: UUID,
        results: Iterable[BacktestResultEntry | Dict[str, Any]],
    ) -> None:
        """Replace all stored results for a run in a single transaction."""

        records = []
        for item in results:
            if isinstance(item, BacktestResultEntry):
                symbol = item.symbol
                parameters = item.parameters
                metrics = item.metrics
                status = item.status
            else:
                symbol = item.get("symbol")
                parameters = item.get("parameters")
                metrics = item.get("metrics")
                status = item.get("status", "completed")

            records.append(
                (
                    uuid4(),
                    run_id,
                    symbol,
                    json.dumps(parameters or {}, default=str),
                    json.dumps(metrics or {}, default=str),
                    status,
                )
            )

        async with DatabaseTransaction(self._pool) as conn:
            await conn.execute("DELETE FROM backtest_results WHERE run_id = $1", run_id)
            if records:
                await conn.copy_records_to_table(
                    "backtest_results",
                    records=records,
                    columns=[
                        "id",
                        "run_id",
                        "symbol",
                        "parameters",
                        "metrics",
                        "status",
                    ],
                )

    async def fetch_results(self, run_id: UUID) -> List[BacktestResultEntry]:
        """Return all stored results for a given Lean run."""

        query = """
        SELECT id, run_id, symbol, parameters, metrics, status, created_at
        FROM backtest_results
        WHERE run_id = $1
        ORDER BY created_at DESC, symbol NULLS FIRST
        """
        rows = await self._pool.fetch(query, run_id)
        return [self._row_to_entry(row) for row in rows]

    @staticmethod
    def _coerce_json(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return {}
        return {}

    def _row_to_entry(self, row: Record) -> BacktestResultEntry:
        return BacktestResultEntry(
            id=row["id"],
            run_id=row["run_id"],
            symbol=row["symbol"],
            parameters=self._coerce_json(row["parameters"]),
            metrics=self._coerce_json(row["metrics"]),
            status=row["status"],
            created_at=row["created_at"],
        )


backtest_repository = BacktestRepository()

__all__ = ["BacktestRepository", "BacktestResultEntry", "backtest_repository"]
