"""Persistence helpers for screener run storage."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Tuple
from uuid import UUID, uuid4

from asyncpg import Record

from .database import DatabasePool, DatabaseTransaction, db_pool


@dataclass
class ScreenerResultEntry:
    """Single symbol result captured by a screener run."""

    id: UUID
    screener_run_id: UUID
    symbol: str
    metrics: Dict[str, Any]
    rank: Optional[int]
    created_at: datetime


@dataclass
class ScreenerRunSummary:
    """Summary metadata for a screener run."""

    id: UUID
    created_at: datetime
    filters: Dict[str, Any]
    metadata: Dict[str, Any]
    symbol_count: int
    run_session_id: Optional[UUID]
    session_id: Optional[UUID]
    last_result_at: Optional[datetime]


@dataclass
class ScreenerRunDetail(ScreenerRunSummary):
    """Detailed screener run including symbol results."""

    results: List[ScreenerResultEntry]


class ScreenerRepository:
    """Repository that persists screener runs/results in PostgreSQL."""

    def __init__(self, pool: DatabasePool | None = None) -> None:
        self._pool = pool or db_pool

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    async def create_run(
        self,
        *,
        filters: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        symbol_count: int = 0,
        run_session_id: Optional[UUID] = None,
        session_id: Optional[UUID] = None,
        screener_run_id: Optional[UUID] = None,
    ) -> ScreenerRunSummary:
        """Insert a new screener run row and return the stored summary."""

        run_uuid = screener_run_id or uuid4()
        filters_json = json.dumps(filters or {}, default=str)
        metadata_json = json.dumps(metadata or {}, default=str)

        query = """
        INSERT INTO screener_runs (
            id,
            session_id,
            run_id,
            filters,
            metadata,
            symbol_count
        ) VALUES ($1, $2, $3, $4::jsonb, $5::jsonb, $6)
        ON CONFLICT (id) DO UPDATE SET
            session_id = EXCLUDED.session_id,
            run_id = EXCLUDED.run_id,
            filters = EXCLUDED.filters,
            metadata = EXCLUDED.metadata,
            symbol_count = EXCLUDED.symbol_count
        RETURNING id, session_id, run_id, created_at, filters, metadata, symbol_count
        """

        row = await self._pool.fetchrow(
            query,
            run_uuid,
            session_id,
            run_session_id,
            filters_json,
            metadata_json,
            symbol_count,
        )
        return self._row_to_summary(row)

    async def save_results(
        self,
        screener_run_id: UUID,
        results: Iterable[
            ScreenerResultEntry | Dict[str, Any] | Tuple[str, Dict[str, Any], Optional[int]]
        ],
    ) -> None:
        """Replace symbol results for a screener run."""

        result_list: List[Tuple[UUID, str, Dict[str, Any], Optional[int]]] = []
        for item in results:
            if isinstance(item, ScreenerResultEntry):
                result_id = item.id
                symbol = item.symbol
                metrics = item.metrics
                rank = item.rank
            elif isinstance(item, dict):
                result_id = item.get("id", uuid4())
                symbol = item["symbol"]
                metrics = item.get("metrics", {})
                rank = item.get("rank")
            else:
                symbol, metrics, rank = item
                result_id = uuid4()

            result_list.append((result_id, symbol, metrics, rank))

        async with DatabaseTransaction(self._pool) as conn:
            await conn.execute(
                "DELETE FROM screener_results WHERE screener_run_id = $1",
                screener_run_id,
            )

            if result_list:
                records = [
                    (
                        result_id,
                        screener_run_id,
                        symbol,
                        json.dumps(metrics or {}, default=str),
                        rank,
                    )
                    for result_id, symbol, metrics, rank in result_list
                ]
                await conn.copy_records_to_table(
                    "screener_results",
                    records=records,
                    columns=["id", "screener_run_id", "symbol", "metrics", "rank"],
                )

                await conn.execute(
                    "UPDATE screener_runs SET symbol_count = $1 WHERE id = $2",
                    len(result_list),
                    screener_run_id,
                )
            else:
                await conn.execute(
                    "UPDATE screener_runs SET symbol_count = 0 WHERE id = $1",
                    screener_run_id,
                )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    async def list_runs(
        self,
        *,
        limit: int = 20,
        offset: int = 0,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> Tuple[int, List[ScreenerRunSummary]]:
        """Return paginated screener runs ordered by recency."""

        where_clauses: List[str] = []
        params: List[Any] = []

        if start_date:
            where_clauses.append("sr.created_at::date >= $%d" % (len(params) + 1))
            params.append(start_date)
        if end_date:
            where_clauses.append("sr.created_at::date <= $%d" % (len(params) + 1))
            params.append(end_date)

        where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

        count_query = f"SELECT COUNT(*) FROM screener_runs sr {where_sql}"
        total = await self._pool.fetchval(count_query, *params) or 0

        query = f"""
        SELECT
            sr.id,
            sr.session_id,
            sr.run_id,
            sr.created_at,
            sr.filters,
            sr.metadata,
            sr.symbol_count,
            MAX(res.created_at) AS last_result_at,
            COUNT(res.id) AS result_count
        FROM screener_runs sr
        LEFT JOIN screener_results res ON res.screener_run_id = sr.id
        {where_sql}
        GROUP BY sr.id
        ORDER BY sr.created_at DESC
        LIMIT $%d
        OFFSET $%d
        """ % (len(params) + 1, len(params) + 2)

        rows = await self._pool.fetch(query, *params, limit, offset)
        summaries = [self._row_to_summary(row) for row in rows]
        return total, summaries

    async def get_run(self, screener_run_id: UUID) -> Optional[ScreenerRunDetail]:
        """Return a screener run with symbol results."""

        run_query = """
        SELECT
            id,
            session_id,
            run_id,
            created_at,
            filters,
            metadata,
            symbol_count,
            NULL::timestamp AS last_result_at
        FROM screener_runs
        WHERE id = $1
        """
        row = await self._pool.fetchrow(run_query, screener_run_id)
        if not row:
            return None

        summary = self._row_to_summary(row)

        results_query = """
        SELECT
            id,
            screener_run_id,
            symbol,
            metrics,
            rank,
            created_at
        FROM screener_results
        WHERE screener_run_id = $1
        ORDER BY COALESCE(rank, 10_000), symbol
        """

        result_rows = await self._pool.fetch(results_query, screener_run_id)
        results = [self._row_to_result(record) for record in result_rows]

        return ScreenerRunDetail(
            **summary.__dict__,
            results=results,
        )

    # ------------------------------------------------------------------
    # Conversion helpers
    # ------------------------------------------------------------------
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

    def _row_to_summary(self, row: Record) -> ScreenerRunSummary:
        filters = self._coerce_json(row["filters"])
        metadata = self._coerce_json(row["metadata"])
        symbol_count = row.get("symbol_count") if isinstance(row, Record) else row["symbol_count"]
        result_count = row.get("result_count") if isinstance(row, Record) else None
        effective_count = symbol_count or (result_count or 0)

        return ScreenerRunSummary(
            id=row["id"],
            created_at=row["created_at"],
            filters=filters,
            metadata=metadata,
            symbol_count=effective_count,
            run_session_id=row.get("run_id") if isinstance(row, Record) else row["run_id"],
            session_id=row.get("session_id") if isinstance(row, Record) else row["session_id"],
            last_result_at=row.get("last_result_at") if isinstance(row, Record) else None,
        )

    def _row_to_result(self, row: Record) -> ScreenerResultEntry:
        metrics = self._coerce_json(row["metrics"])
        return ScreenerResultEntry(
            id=row["id"],
            screener_run_id=row["screener_run_id"],
            symbol=row["symbol"],
            metrics=metrics,
            rank=row["rank"],
            created_at=row["created_at"],
        )


screener_repository = ScreenerRepository()

__all__ = [
    "ScreenerRepository",
    "ScreenerRunSummary",
    "ScreenerRunDetail",
    "ScreenerResultEntry",
    "screener_repository",
]
