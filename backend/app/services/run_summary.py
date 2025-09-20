"""Aggregate summaries for Lean job runs."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Dict, List

from ..models.backtest import JobTypeSummary, MetricSummary, RunSummaryResponse, TargetSummary
from .database import db_pool

logger = logging.getLogger(__name__)


class RunSummaryService:
    async def get_summary(self) -> RunSummaryResponse:
        job_types = await self._fetch_job_type_summary()
        metrics = await self._fetch_metric_summary()
        targets = await self._fetch_target_summary()
        return RunSummaryResponse(job_types=job_types, metrics=metrics, targets=targets)

    async def _fetch_job_type_summary(self) -> List[JobTypeSummary]:
        query = """
        WITH latest AS (
            SELECT DISTINCT ON (job_type)
                job_type,
                id AS last_run_id,
                created_at AS last_created
            FROM run_sessions
            ORDER BY job_type, created_at DESC
        )
        SELECT
            rs.job_type,
            COUNT(*) AS total_runs,
            COUNT(*) FILTER (WHERE status = 'completed') AS completed_runs,
            COUNT(*) FILTER (WHERE status = 'failed') AS failed_runs,
            latest.last_run_id,
            latest.last_created
        FROM run_sessions rs
        LEFT JOIN latest ON latest.job_type = rs.job_type
        GROUP BY rs.job_type, latest.last_run_id, latest.last_created
        ORDER BY rs.job_type
        """

        rows = await db_pool.fetch(query)
        summaries: List[JobTypeSummary] = []
        for row in rows:
            summaries.append(
                JobTypeSummary(
                    job_type=row['job_type'],
                    total_runs=row['total_runs'],
                    completed_runs=row['completed_runs'],
                    failed_runs=row['failed_runs'],
                    last_run_id=str(row['last_run_id']) if row['last_run_id'] else None,
                    last_run_at=row['last_created'],
                )
            )
        return summaries

    async def _fetch_metric_summary(self) -> List[MetricSummary]:
        query = """
        SELECT DISTINCT ON (rs.job_type, rm.metric_key)
            rs.job_type,
            rm.metric_key,
            rm.metric_value,
            rs.id AS run_id,
            rs.strategy_name,
            rs.created_at
        FROM run_metrics rm
        JOIN run_sessions rs ON rm.run_id = rs.id
        WHERE rs.status = 'completed'
        ORDER BY rs.job_type, rm.metric_key, rm.metric_value DESC
        """

        rows = await db_pool.fetch(query)
        entries: List[MetricSummary] = []
        for row in rows:
            try:
                metric_value = Decimal(str(row['metric_value']))
            except (TypeError, ValueError, ArithmeticError):
                continue
            entries.append(
                MetricSummary(
                    job_type=row['job_type'],
                    metric_key=row['metric_key'],
                    metric_value=metric_value,
                    run_id=str(row['run_id']),
                    strategy_name=row['strategy_name'],
                    created_at=row['created_at'],
                )
            )
        return entries

    async def _fetch_target_summary(self) -> List[TargetSummary]:
        query = """
        SELECT rs.job_type, COUNT(*) AS target_count
        FROM run_targets rt
        JOIN run_sessions rs ON rt.run_id = rs.id
        GROUP BY rs.job_type
        ORDER BY rs.job_type
        """

        rows = await db_pool.fetch(query)
        return [
            TargetSummary(job_type=row['job_type'], target_count=row['target_count'])
            for row in rows
        ]


run_summary_service = RunSummaryService()

__all__ = ['run_summary_service']
