"""Persistent storage for Lean job runs."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import UUID

from ..models.backtest import BacktestRequest, BacktestRunInfo, BacktestStatus
from .database import db_pool

logger = logging.getLogger(__name__)


class DatabaseRunStorage:
    """Stores Lean job runs inside PostgreSQL/Timescale."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._ready = False
        self._disabled = False

    async def _ensure_schema(self) -> bool:
        if self._disabled or self._ready:
            return self._ready

        async with self._lock:
            if self._disabled or self._ready:
                return self._ready

            try:
                await db_pool.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_sessions (
                        id UUID PRIMARY KEY,
                        job_type TEXT NOT NULL,
                        strategy_name TEXT NOT NULL,
                        status TEXT NOT NULL,
                        payload JSONB NOT NULL,
                        result_path TEXT,
                        error_message TEXT,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        started_at TIMESTAMPTZ,
                        completed_at TIMESTAMPTZ,
                        metadata JSONB DEFAULT '{}'::jsonb
                    )
                    """
                )
                await db_pool.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_targets (
                        id UUID PRIMARY KEY,
                        run_id UUID REFERENCES run_sessions(id) ON DELETE CASCADE,
                        symbol TEXT,
                        parameters JSONB DEFAULT '{}'::jsonb,
                        UNIQUE (run_id, symbol)
                    )
                    """
                )
                await db_pool.execute(
                    """
                    CREATE TABLE IF NOT EXISTS run_metrics (
                        id UUID PRIMARY KEY,
                        run_id UUID REFERENCES run_sessions(id) ON DELETE CASCADE,
                        metric_key TEXT NOT NULL,
                        metric_value DOUBLE PRECISION,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        UNIQUE (run_id, metric_key)
                    )
                    """
                )
                await db_pool.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_run_sessions_created_at
                        ON run_sessions (created_at DESC)
                    """
                )
                await db_pool.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_run_sessions_strategy
                        ON run_sessions (strategy_name, created_at DESC)
                    """
                )
                await db_pool.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_run_targets_run
                        ON run_targets (run_id)
                    """
                )
                await db_pool.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_run_metrics_run
                        ON run_metrics (run_id)
                    """
                )
                self._ready = True
                logger.info("run_sessions table ready for Lean job persistence")
            except Exception as exc:  # pragma: no cover - depends on DB availability
                self._disabled = True
                logger.warning("Disabling run storage due to initialization failure: %s", exc)
        return self._ready

    async def record_submission(self, job_id: str, job_type: str, strategy_name: str, run_info: BacktestRunInfo) -> None:
        if not await self._ensure_schema():
            return

        query = """
        INSERT INTO run_sessions (
            id,
            job_type,
            strategy_name,
            status,
            payload,
            result_path,
            error_message,
            created_at,
            started_at,
            completed_at,
            metadata
        ) VALUES ($1, $2, $3, $4, $5::jsonb, $6, $7, $8, $9, $10, $11::jsonb)
        ON CONFLICT (id)
        DO UPDATE SET
            job_type = EXCLUDED.job_type,
            strategy_name = EXCLUDED.strategy_name,
            status = EXCLUDED.status,
            payload = EXCLUDED.payload,
            created_at = EXCLUDED.created_at,
            started_at = EXCLUDED.started_at,
            completed_at = EXCLUDED.completed_at,
            metadata = EXCLUDED.metadata,
            result_path = EXCLUDED.result_path,
            error_message = EXCLUDED.error_message;
        """

        payload = json.dumps(run_info.request.model_dump(mode='json'), default=str)
        metadata = json.dumps({
            "execution_time_ms": run_info.execution_time_ms,
            "cache_hit": run_info.cache_hit,
            "container_id": run_info.container_id,
        }, default=str)

        try:
            run_uuid = UUID(run_info.backtest_id)
        except ValueError:
            logger.debug("Skipping persistence for non-UUID job id %s", run_info.backtest_id)
            return

        try:
            await db_pool.execute(
                query,
                run_uuid,
                job_type,
                strategy_name,
                run_info.status.value,
                payload,
                run_info.result_path,
                run_info.error_message,
                run_info.created_at,
                run_info.started_at,
                run_info.completed_at,
                metadata,
            )
            await self._insert_targets(run_uuid, run_info)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.debug("Failed to persist job submission %s: %s", job_id, exc)

    async def record_update(
        self,
        job_id: str,
        run_info: BacktestRunInfo,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not await self._ensure_schema():
            return

        query = """
        UPDATE run_sessions
        SET
            status = $2,
            result_path = $3,
            error_message = $4,
            started_at = $5,
            completed_at = $6,
            metadata = metadata || $7::jsonb
        WHERE id = $1
        """

        metadata = json.dumps({
            "execution_time_ms": run_info.execution_time_ms,
            "cache_hit": run_info.cache_hit,
            "container_id": run_info.container_id,
        }, default=str)

        try:
            run_uuid = UUID(run_info.backtest_id)
        except ValueError:
            logger.debug("Skipping persistence update for non-UUID job id %s", run_info.backtest_id)
            return

        try:
            await db_pool.execute(
                query,
                run_uuid,
                run_info.status.value,
                run_info.result_path,
                run_info.error_message,
                run_info.started_at,
                run_info.completed_at,
                metadata,
            )
            await self._upsert_metrics(run_uuid, metrics)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.debug("Failed to persist job update %s: %s", job_id, exc)

    async def fetch_runs(self, *, strategy_name: Optional[str] = None, limit: int = 200) -> List[BacktestRunInfo]:
        if not await self._ensure_schema():
            return []

        clause = "WHERE strategy_name = $1" if strategy_name else ""
        params: List[Any] = []
        if strategy_name:
            params.append(strategy_name)
        params.append(limit)

        query = f"""
        SELECT
            id,
            job_type,
            status,
            payload,
            result_path,
            error_message,
            created_at,
            started_at,
            completed_at,
            metadata,
            (
                SELECT jsonb_object_agg(metric_key, metric_value)
                FROM run_metrics rm
                WHERE rm.run_id = run_sessions.id
            ) AS metrics,
            (
                SELECT array_agg(symbol)
                FROM run_targets rt
                WHERE rt.run_id = run_sessions.id
            ) AS targets
        FROM run_sessions
        {clause}
        ORDER BY created_at DESC
        LIMIT ${len(params)}
        """

        try:
            rows = await db_pool.fetch(query, *params)
        except Exception as exc:  # pragma: no cover - depends on DB availability
            logger.debug("Failed to load run history: %s", exc)
            return []

        return [self._row_to_run_info(row) for row in rows]

    async def fetch_run(self, run_id: UUID) -> Optional[BacktestRunInfo]:
        if not await self._ensure_schema():
            return None

        query = """
        SELECT
            id,
            job_type,
            status,
            payload,
            result_path,
            error_message,
            created_at,
            started_at,
            completed_at,
            metadata,
            (
                SELECT jsonb_object_agg(metric_key, metric_value)
                FROM run_metrics rm
                WHERE rm.run_id = run_sessions.id
            ) AS metrics,
            (
                SELECT array_agg(symbol)
                FROM run_targets rt
                WHERE rt.run_id = run_sessions.id
            ) AS targets
        FROM run_sessions
        WHERE id = $1
        """

        row = await db_pool.fetchrow(query, run_id)
        if not row:
            return None
        return self._row_to_run_info(row)

    def _row_to_run_info(self, row) -> BacktestRunInfo:
        payload: Dict[str, Any] = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        metadata: Dict[str, Any] = row["metadata"] or {}
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        request = BacktestRequest.model_validate(payload)
        status = BacktestStatus(row["status"])

        job_type = row["job_type"] if "job_type" in row else "backtest"

        row_keys = set(row.keys())
        metrics_payload = row['metrics'] if 'metrics' in row_keys else None
        targets_payload = row['targets'] if 'targets' in row_keys else None

        metrics_dict: Optional[Dict[str, Decimal]] = None
        if isinstance(metrics_payload, dict):
            metrics_dict = {}
            for key, value in metrics_payload.items():
                try:
                    metrics_dict[key] = Decimal(str(value))
                except (TypeError, ValueError, ArithmeticError):
                    continue

        targets_list: Optional[List[str]] = None
        if isinstance(targets_payload, list):
            targets_list = [str(target) for target in targets_payload if target is not None]

        return BacktestRunInfo(
            backtest_id=str(row["id"]),
            status=status,
            request=request,
            job_type=job_type,
            created_at=row["created_at"],
            started_at=row["started_at"],
            completed_at=row["completed_at"],
            error_message=row["error_message"],
            result_path=row["result_path"],
            cache_hit=metadata.get("cache_hit"),
            execution_time_ms=metadata.get("execution_time_ms"),
            container_id=metadata.get("container_id"),
            metrics=metrics_dict,
            targets=targets_list,
        )

    async def _insert_targets(self, run_uuid: UUID, run_info: BacktestRunInfo) -> None:
        symbols = run_info.targets or run_info.request.symbols or []
        if run_info.request.use_screener_results and not symbols:
            symbols = ["screener"]
        if not symbols:
            symbols = ["*"]

        parameter_payload = {
            **(run_info.request.parameters or {}),
            "pivot_bars": run_info.request.pivot_bars,
            "lower_timeframe": run_info.request.lower_timeframe,
        }
        parameter_json = json.dumps(parameter_payload, default=str)

        for symbol in symbols:
            try:
                await db_pool.execute(
                    """
                    INSERT INTO run_targets (id, run_id, symbol, parameters)
                    VALUES ($1, $2, $3, $4::jsonb)
                    ON CONFLICT (run_id, symbol)
                    DO UPDATE SET parameters = EXCLUDED.parameters
                    """,
                    uuid.uuid4(),
                    run_uuid,
                    symbol,
                    parameter_json,
                )
            except Exception:  # pragma: no cover
                logger.debug("Failed to persist run target for %s", run_uuid, exc_info=True)

    async def record_grid_targets(self, job_id: str, combos: List[Dict[str, Any]]) -> None:
        if not await self._ensure_schema():
            return

        try:
            run_uuid = UUID(job_id)
        except ValueError:
            logger.debug("Skipping grid target persistence for non-UUID id %s", job_id)
            return

        records = []
        for combo in combos:
            label = combo.get("label")
            if not label:
                continue
            parameters = combo.get("parameters") or {}
            records.append(
                (
                    uuid.uuid4(),
                    run_uuid,
                    label,
                    json.dumps(parameters, default=str),
                )
            )

        if not records:
            return

        async with DatabaseTransaction(db_pool) as conn:
            await conn.execute("DELETE FROM run_targets WHERE run_id = $1", run_uuid)
            await conn.copy_records_to_table(
                "run_targets",
                records=records,
                columns=["id", "run_id", "symbol", "parameters"],
            )

    async def _upsert_metrics(self, run_uuid: UUID, metrics: Optional[Dict[str, Any]]) -> None:
        if not metrics:
            return

        statistics = metrics.get("statistics") if isinstance(metrics, dict) else None
        if not statistics:
            return

        for key, value in statistics.items():
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue

            try:
                await db_pool.execute(
                    """
                    INSERT INTO run_metrics (id, run_id, metric_key, metric_value, metadata)
                    VALUES ($1, $2, $3, $4, '{}'::jsonb)
                    ON CONFLICT (run_id, metric_key)
                    DO UPDATE SET metric_value = EXCLUDED.metric_value
                    """,
                    uuid.uuid4(),
                    run_uuid,
                    key,
                    numeric_value,
                )
            except Exception:  # pragma: no cover
                logger.debug("Failed to persist metric %s for %s", key, run_uuid, exc_info=True)


class InMemoryRunStorage:
    """Fallback storage that keeps everything in memory (mainly for tests)."""

    def __init__(self) -> None:
        self._runs: Dict[str, BacktestRunInfo] = {}
        self._targets: Dict[str, List[str]] = {}
        self._metrics: Dict[str, Dict[str, float]] = {}

    async def record_submission(self, job_id: str, job_type: str, strategy_name: str, run_info: BacktestRunInfo) -> None:
        targets = list(run_info.targets or run_info.request.symbols or [])
        self._targets[job_id] = targets
        self._runs[job_id] = run_info.model_copy(update={"targets": targets})

    async def record_update(
        self,
        job_id: str,
        run_info: BacktestRunInfo,
        metrics: Optional[Dict[str, Any]] = None,
    ) -> None:
        stats = (metrics or {}).get("statistics") if isinstance(metrics, dict) else None
        numeric_stats: Dict[str, float] = {}
        if stats:
            for key, value in stats.items():
                try:
                    numeric_stats[key] = float(value)
                except (TypeError, ValueError):
                    continue
            self._metrics[job_id] = numeric_stats
        targets = self._targets.get(job_id, list(run_info.targets or run_info.request.symbols or []))
        self._runs[job_id] = run_info.model_copy(
            update={
                "metrics": numeric_stats or None,
                "targets": targets,
            }
        )

    async def record_grid_targets(self, job_id: str, combos: List[Dict[str, Any]]) -> None:
        labels = [combo.get("label") for combo in combos if combo.get("label")]
        if not labels:
            return

        self._targets[job_id] = labels
        existing = self._runs.get(job_id)
        if existing:
            self._runs[job_id] = existing.model_copy(update={"targets": labels})

    async def fetch_runs(self, *, strategy_name: Optional[str] = None, limit: int = 200) -> List[BacktestRunInfo]:
        runs = list(self._runs.values())
        if strategy_name:
            runs = [run for run in runs if run.request.strategy_name == strategy_name]
        runs.sort(key=lambda run: run.created_at or run.request.start_date, reverse=True)
        return runs[:limit]


__all__ = ["DatabaseRunStorage", "InMemoryRunStorage"]
