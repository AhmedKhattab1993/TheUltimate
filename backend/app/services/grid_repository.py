"""Repository helpers for grid run summaries powered by normalized run tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from asyncpg import Record

from .database import db_pool


@dataclass
class GridRunSummaryRow:
    run_id: UUID
    strategy_name: str
    job_type: str
    status: str
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    metadata: Dict[str, Any]
    metrics: Dict[str, Any]
    target_count: int


@dataclass
class GridRunDetailRow(GridRunSummaryRow):
    pass


@dataclass
class GridRunResultRow:
    symbol: Optional[str]
    parameters: Dict[str, Any]
    metrics: Dict[str, Any]
    status: str
    created_at: datetime


class GridRepository:
    """Queries grid/optimization runs from the normalized persistence tables."""

    async def list_runs(
        self,
        *,
        page: int,
        page_size: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        strategy_name: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> Tuple[int, List[GridRunSummaryRow]]:
        where_clauses: List[str] = ["rs.job_type = 'grid'"]
        params: List[Any] = []

        if start_date:
            where_clauses.append(f"rs.created_at::date >= ${len(params) + 1}")
            params.append(start_date)
        if end_date:
            where_clauses.append(f"rs.created_at::date <= ${len(params) + 1}")
            params.append(end_date)
        if strategy_name:
            where_clauses.append(f"rs.strategy_name = ${len(params) + 1}")
            params.append(strategy_name)
        if symbol:
            where_clauses.append(
                f"EXISTS (SELECT 1 FROM run_targets rt WHERE rt.run_id = rs.id AND rt.symbol = ${len(params) + 1})"
            )
            params.append(symbol)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        total_query = f"SELECT COUNT(*) FROM run_sessions rs{where_sql}"
        total = await db_pool.fetchval(total_query, *params) or 0

        query = f"""
        WITH metrics AS (
            SELECT run_id, jsonb_object_agg(metric_key, metric_value) AS metrics
            FROM run_metrics
            GROUP BY run_id
        ), targets AS (
            SELECT run_id, COUNT(*) AS target_count
            FROM run_targets
            GROUP BY run_id
        )
        SELECT
            rs.id,
            rs.strategy_name,
            rs.job_type,
            rs.status,
            rs.created_at,
            rs.started_at,
            rs.completed_at,
            rs.metadata,
            COALESCE(m.metrics, '{{}}'::jsonb) AS metrics,
            COALESCE(t.target_count, 0) AS target_count
        FROM run_sessions rs
        LEFT JOIN metrics m ON m.run_id = rs.id
        LEFT JOIN targets t ON t.run_id = rs.id
        {where_sql}
        ORDER BY rs.created_at DESC
        LIMIT ${len(params) + 1}
        OFFSET ${len(params) + 2}
        """

        rows = await db_pool.fetch(query, *params, page_size, (page - 1) * page_size)
        summaries = [self._record_to_summary(row) for row in rows]
        return total, summaries

    async def get_run(self, run_id: UUID) -> Optional[GridRunDetailRow]:
        query = """
        SELECT
            rs.id,
            rs.strategy_name,
            rs.job_type,
            rs.status,
            rs.created_at,
            rs.started_at,
            rs.completed_at,
            rs.metadata,
            COALESCE(m.metrics, '{{}}'::jsonb) AS metrics,
            COALESCE(t.target_count, 0) AS target_count
        FROM run_sessions rs
        LEFT JOIN (
            SELECT run_id, jsonb_object_agg(metric_key, metric_value) AS metrics
            FROM run_metrics
            GROUP BY run_id
        ) m ON m.run_id = rs.id
        LEFT JOIN (
            SELECT run_id, COUNT(*) AS target_count
            FROM run_targets
            GROUP BY run_id
        ) t ON t.run_id = rs.id
        WHERE rs.id = $1 AND rs.job_type = 'grid'
        """

        row = await db_pool.fetchrow(query, run_id)
        if not row:
            return None
        return self._record_to_summary(row)

    async def list_results(self, run_id: UUID) -> List[GridRunResultRow]:
        results_query = """
        SELECT symbol, parameters, metrics, status, created_at
        FROM backtest_results
        WHERE run_id = $1
        ORDER BY created_at DESC, symbol NULLS FIRST
        """

        rows = await db_pool.fetch(results_query, run_id)
        if rows:
            return [self._record_to_result(row) for row in rows]

        # Fallback to run_targets if no persisted metrics yet
        targets_query = """
        SELECT symbol, parameters, 'pending' AS status
        FROM run_targets
        WHERE run_id = $1
        ORDER BY symbol
        """
        target_rows = await db_pool.fetch(targets_query, run_id)
        return [
            GridRunResultRow(
                symbol=row["symbol"],
                parameters=self._coerce_json(row["parameters"]),
                metrics={},
                status=row["status"],
                created_at=datetime.utcnow(),
            )
            for row in target_rows
        ]

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _record_to_summary(self, row: Record) -> GridRunSummaryRow:
        metadata = self._coerce_json(row["metadata"])
        metrics = self._coerce_json(row["metrics"])
        return GridRunSummaryRow(
            run_id=row["id"],
            strategy_name=row["strategy_name"],
            job_type=row["job_type"],
            status=row["status"],
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            metadata=metadata,
            metrics=metrics,
            target_count=row["target_count"],
        )

    def _record_to_result(self, row: Record) -> GridRunResultRow:
        parameters = self._coerce_json(row["parameters"])
        metrics = self._coerce_json(row["metrics"])
        return GridRunResultRow(
            symbol=row["symbol"],
            parameters=parameters,
            metrics=metrics,
            status=row["status"],
            created_at=row["created_at"],
        )

    @staticmethod
    def _coerce_json(value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            try:
                import json

                return json.loads(value)
            except Exception:
                return {}
        return {}


grid_repository = GridRepository()

__all__ = [
    "GridRepository",
    "GridRunSummaryRow",
    "GridRunResultRow",
    "grid_repository",
]
