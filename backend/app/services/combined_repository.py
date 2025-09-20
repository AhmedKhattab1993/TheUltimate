"""Repository for combined screener/backtest lookups using normalized tables."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from asyncpg import Record

from .database import db_pool


@dataclass
class CombinedRow:
    screener_result_id: UUID
    screener_run_id: UUID
    symbol: str
    screener_created_at: datetime
    screener_metrics: Dict[str, Any]
    filters: Dict[str, Any]
    screener_metadata: Dict[str, Any]
    run_id: Optional[UUID]
    run_created_at: Optional[datetime]
    run_status: Optional[str]
    strategy_name: Optional[str]
    backtest_parameters: Dict[str, Any]
    backtest_metrics: Dict[str, Any]


class CombinedRepository:
    async def list_rows(
        self,
        *,
        symbol: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        source: Optional[str] = None,
        limit: int,
        offset: int,
    ) -> Tuple[int, List[CombinedRow]]:
        where_clauses: List[str] = []
        params: List[Any] = []

        if symbol:
            where_clauses.append(f"sr.symbol = ${len(params) + 1}")
            params.append(symbol.upper())
        if start_date:
            where_clauses.append(f"sr.created_at::date >= ${len(params) + 1}")
            params.append(start_date)
        if end_date:
            where_clauses.append(f"sr.created_at::date <= ${len(params) + 1}")
            params.append(end_date)
        if source:
            where_clauses.append(f"COALESCE(run.metadata->>'source', run.metadata->>'dataset_source') = ${len(params) + 1}")
            params.append(source)

        where_sql = " WHERE " + " AND ".join(where_clauses) if where_clauses else ""

        base_query = f"""
        SELECT
            sr.id AS screener_result_id,
            sr.screener_run_id,
            sr.symbol,
            sr.created_at AS screener_created_at,
            sr.metrics AS screener_metrics,
            run.filters,
            run.metadata
        FROM screener_results sr
        JOIN screener_runs run ON run.id = sr.screener_run_id
        {where_sql}
        """

        count_query = f"SELECT COUNT(*) FROM ({base_query}) base"
        total = await db_pool.fetchval(count_query, *params) or 0

        query = f"""
        WITH base AS (
            {base_query}
        )
        SELECT
            base.screener_result_id,
            base.screener_run_id,
            base.symbol,
            base.screener_created_at,
            base.screener_metrics,
            base.filters,
            base.metadata,
            latest_run.run_id,
            latest_run.strategy_name,
            latest_run.status,
            latest_run.run_created_at,
            latest_run.backtest_parameters,
            latest_run.backtest_metrics
        FROM base
        LEFT JOIN LATERAL (
            SELECT
                rs.id AS run_id,
                rs.strategy_name,
                rs.status,
                rs.created_at AS run_created_at,
                COALESCE(br.parameters, '{{}}'::jsonb) AS backtest_parameters,
                COALESCE(br.metrics, '{{}}'::jsonb) AS backtest_metrics
            FROM run_targets rt
            JOIN run_sessions rs ON rs.id = rt.run_id
            LEFT JOIN backtest_results br ON br.run_id = rs.id AND (br.symbol = base.symbol OR br.symbol IS NULL)
            WHERE rt.symbol = base.symbol OR rt.symbol = '*'
            ORDER BY rs.created_at DESC
            LIMIT 1
        ) latest_run ON TRUE
        ORDER BY base.screener_created_at DESC
        LIMIT ${len(params) + 1}
        OFFSET ${len(params) + 2}
        """

        rows = await db_pool.fetch(query, *params, limit, offset)
        return total, [self._row_to_combined(row) for row in rows]

    def _row_to_combined(self, row: Record) -> CombinedRow:
        return CombinedRow(
            screener_result_id=row["screener_result_id"],
            screener_run_id=row["screener_run_id"],
            symbol=row["symbol"],
            screener_created_at=row["screener_created_at"],
            screener_metrics=self._coerce_json(row["screener_metrics"]),
            filters=self._coerce_json(row["filters"]),
            screener_metadata=self._coerce_json(row["metadata"]),
            run_id=row["run_id"],
            run_created_at=row["run_created_at"],
            run_status=row["status"],
            strategy_name=row["strategy_name"],
            backtest_parameters=self._coerce_json(row["backtest_parameters"]),
            backtest_metrics=self._coerce_json(row["backtest_metrics"]),
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


combined_repository = CombinedRepository()

__all__ = ["CombinedRepository", "CombinedRow", "combined_repository"]
