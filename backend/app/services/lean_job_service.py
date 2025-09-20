"""Unified Lean job orchestration service."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from ..models.backtest import (
    BacktestProgress,
    BacktestRequest,
    BacktestResult,
    BacktestRunInfo,
    BacktestStatus,
    BacktestStatistics,
    OptimizationRequest,
)
from ..models.ingestion import DataIngestionRequest
from ..models.simple_requests import SimpleFilters
from ..registry import filter_registry, strategy_registry
from .lean_runner import LeanRunner
from .backtest_repository import backtest_repository
from .run_storage import DatabaseRunStorage
from .data_ingestion_runner import DataIngestionRunner

logger = logging.getLogger(__name__)


class JobType(str, Enum):
    """Supported Lean job categories."""

    BACKTEST = "backtest"
    GRID = "grid"
    OPTIMIZE = "optimize"
    DATA = "data"


class JobState(str, Enum):
    """Lifecycle states tracked for a job."""

    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LeanJob:
    """In-memory representation of a Lean job."""

    job_id: str
    job_type: JobType
    strategy_name: str
    request: BacktestRequest
    created_at: datetime = field(default_factory=datetime.utcnow)
    status: JobState = JobState.QUEUED
    progress: Optional[BacktestProgress] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    result_path: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    job_config: Dict[str, Any] = field(default_factory=dict)
    task: Optional[asyncio.Task] = None

    def to_run_info(self) -> BacktestRunInfo:
        status_map = {
            JobState.QUEUED: BacktestStatus.PENDING,
            JobState.RUNNING: BacktestStatus.RUNNING,
            JobState.COMPLETED: BacktestStatus.COMPLETED,
            JobState.FAILED: BacktestStatus.FAILED,
            JobState.CANCELLED: BacktestStatus.CANCELLED,
        }

        metrics: Optional[Dict[str, Decimal]] = None
        result_payload = self.metadata.get("result") if isinstance(self.metadata, dict) else None
        statistics_payload = None
        if isinstance(result_payload, dict):
            statistics_payload = result_payload.get("statistics")

        if isinstance(statistics_payload, dict):
            metrics = {}
            for key, value in statistics_payload.items():
                try:
                    metrics[key] = Decimal(str(value))
                except (TypeError, ValueError, ArithmeticError):
                    continue

        targets = self.job_config.get("targets") if isinstance(self.job_config, dict) else None
        if not targets:
            targets = self.request.symbols or None

        return BacktestRunInfo(
            backtest_id=self.job_id,
            status=status_map[self.status],
            request=self.request,
            job_type=self.job_type.value,
            created_at=self.created_at,
            started_at=self.started_at,
            completed_at=self.completed_at,
            error_message=self.error_message,
            result_path=self.result_path,
            cache_hit=self.metadata.get("cache_hit"),
            execution_time_ms=self.metadata.get("execution_time_ms"),
            metrics=metrics,
            targets=targets,
        )

    def as_result(self) -> Optional[BacktestResult]:
        result_payload = self.metadata.get("result")
        if not result_payload:
            return None
        statistics_payload = result_payload.get("statistics") or {}
        statistics = BacktestStatistics(**statistics_payload)
        return BacktestResult(
            backtest_id=self.job_id,
            run_info=self.to_run_info(),
            statistics=statistics,
            charts=result_payload.get("charts") or {},
            orders=result_payload.get("orders") or [],
        )


class LeanJobService:
    """Facade that executes Lean jobs in a consistent fashion."""

    def __init__(self, runner: Optional[LeanRunner] = None, storage=None, ingestion_runner: Optional[DataIngestionRunner] = None) -> None:
        self._runner = runner or LeanRunner()
        self._jobs: Dict[str, LeanJob] = {}
        self._lock = asyncio.Lock()
        self._storage = storage or DatabaseRunStorage()
        self._ingestion_runner = ingestion_runner or DataIngestionRunner()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def submit_backtest(
        self,
        request: BacktestRequest,
        *,
        job_type: JobType = JobType.BACKTEST,
        job_config: Optional[Dict[str, Any]] = None,
    ) -> BacktestRunInfo:
        """Submit a single backtest job."""

        strategy = None
        if job_type in (JobType.BACKTEST, JobType.GRID, JobType.OPTIMIZE):
            strategy = strategy_registry.require(request.strategy_name)
            strategy_registry.merge_request_with_defaults(request)

        job_id = str(uuid4())
        job = LeanJob(
            job_id=job_id,
            job_type=job_type,
            strategy_name=strategy.id if strategy else request.strategy_name,
            request=request,
            job_config=job_config or {},
        )

        async with self._lock:
            self._jobs[job_id] = job

        run_info = job.to_run_info()
        await self._record_submission(job, run_info)

        project_name = strategy.id if strategy else request.strategy_name
        task = asyncio.create_task(self._execute_job(job, project_name))
        job.task = task

        logger.info(
            "Queued %s job %s for strategy %s",
            job_type.value,
            job_id,
            job.strategy_name,
        )
        return run_info

    async def resubmit_backtest(self, backtest_id: str) -> BacktestRunInfo:
        job = self._jobs.get(backtest_id)
        if not job:
            raise ValueError(f"Unknown backtest '{backtest_id}'")
        strategy = strategy_registry.require(job.strategy_name)
        task = asyncio.create_task(
            self._execute_job(job, strategy.project_path, restart=True)
        )
        job.task = task
        run_info = job.to_run_info()
        await self._record_submission(job, run_info)
        return run_info

    async def submit_grid_job(
        self,
        base_request: BacktestRequest,
        parameter_sweeps: List[Dict[str, Any]],
    ) -> List[BacktestRunInfo]:
        """Submit multiple backtests representing a grid search."""

        strategy = strategy_registry.require(base_request.strategy_name)
        run_infos: List[BacktestRunInfo] = []

        for sweep in parameter_sweeps:
            request = base_request.model_copy(deep=True)
            request.parameters = {**(request.parameters or {}), **sweep}
            run_infos.append(
                await self.submit_backtest(request, job_type=JobType.GRID)
            )

        logger.info(
            "Queued %d grid backtests for strategy %s", len(run_infos), strategy.id
        )
        return run_infos

    async def submit_optimize(self, request: OptimizationRequest) -> BacktestRunInfo:
        """Submit an optimization job backed by Lean CLI."""

        base_request = request.base_request.model_copy(deep=True)
        job_config = {"optimize": request.model_dump(mode="json")}

        return await self.submit_backtest(
            base_request,
            job_type=JobType.OPTIMIZE,
            job_config=job_config,
        )

    async def submit_data_job(self, request: DataIngestionRequest) -> BacktestRunInfo:
        """Submit a historical data ingestion job."""

        base_request = BacktestRequest(
            strategy_name=f"ingestion:{request.dataset}",
            start_date=request.start_date,
            end_date=request.end_date,
            initial_cash=Decimal("1000"),
            resolution="Minute",
            pivot_bars=1,
            lower_timeframe="1min",
            parameters={
                "dataset": request.dataset,
                "resume": request.resume,
            },
            symbols=[],
            use_screener_results=False,
        )

        return await self.submit_backtest(
            base_request,
            job_type=JobType.DATA,
            job_config={
                "ingestion": request.model_dump(mode="json"),
                "targets": [f"{request.start_date}→{request.end_date}"],
            },
        )

    async def get_backtest(self, backtest_id: str) -> Optional[BacktestRunInfo]:
        job = self._jobs.get(backtest_id)
        if not job:
            try:
                run_uuid = UUID(backtest_id)
            except ValueError:
                return None
            if self._storage:
                return await self._storage.fetch_run(run_uuid)
            return None
        return job.to_run_info()

    async def get_progress(self, backtest_id: str) -> Optional[BacktestProgress]:
        job = self._jobs.get(backtest_id)
        if not job:
            return None
        return job.progress

    async def cancel(self, backtest_id: str) -> bool:
        job = self._jobs.get(backtest_id)
        if not job:
            return False
        if job.task and not job.task.done():
            job.task.cancel()
        job.status = JobState.CANCELLED
        job.completed_at = datetime.utcnow()
        await self._record_update(job)
        logger.info("Cancelled job %s", backtest_id)
        return True

    async def list_backtests(self) -> List[BacktestRunInfo]:
        persisted = []
        if self._storage:
            try:
                persisted = await self._storage.fetch_runs()
            except Exception:  # pragma: no cover - defensive safeguard
                persisted = []

        memory_runs = [job.to_run_info() for job in self._jobs.values()]
        combined = {run.backtest_id: run for run in persisted}
        for run in memory_runs:
            combined.setdefault(run.backtest_id, run)
        runs = list(combined.values())
        runs.sort(key=lambda run: (run.created_at or datetime.utcnow()), reverse=True)
        return runs

    # ------------------------------------------------------------------
    # Internal execution helpers
    # ------------------------------------------------------------------
    async def _execute_job(
        self,
        job: LeanJob,
        project_name: str,
        restart: bool = False,
    ) -> None:
        job.status = JobState.RUNNING
        job.started_at = datetime.utcnow()
        logger.info("Starting Lean %s job %s", job.job_type.value, job.job_id)

        try:
            if job.job_type is JobType.OPTIMIZE:
                optimize_config = job.job_config.get("optimize", {})
                result = await self._runner.run_optimize(
                    job_id=job.job_id,
                    request=job.request,
                    project_name=project_name,
                    optimize_config=optimize_config,
                )
            elif job.job_type is JobType.DATA:
                ingestion_config = job.job_config.get("ingestion", {})
                result = await self._ingestion_runner.run(
                    job.job_id,
                    ingestion_config,
                )
            else:
                result = await self._runner.run_backtest(
                    backtest_id=job.job_id,
                    request=job.request,
                    project_name=project_name,
                )
            job.status = JobState.COMPLETED
            job.completed_at = datetime.utcnow()
            job.result_path = result.get("result_path")
            job.metadata.update(result)
            await self._record_update(job)
            logger.info(
                "%s job %s completed -> %s",
                job.job_type.value,
                job.job_id,
                job.result_path or "no result path",
            )
        except asyncio.CancelledError:
            job.status = JobState.CANCELLED
            job.completed_at = datetime.utcnow()
            await self._record_update(job)
            logger.warning("%s job %s cancelled", job.job_type.value, job.job_id)
            raise
        except Exception as exc:  # noqa: BLE001
            job.status = JobState.FAILED
            job.completed_at = datetime.utcnow()
            job.error_message = str(exc)
            await self._record_update(job)
            logger.exception("%s job %s failed: %s", job.job_type.value, job.job_id, exc)

    # ------------------------------------------------------------------
    # Screener integration
    # ------------------------------------------------------------------
    def build_filters_from_registry(self, payload: Dict[str, dict]) -> SimpleFilters:
        """Expose registry hydration to API layer for dependency injection."""

        return filter_registry.build_simple_filters(payload)

    async def _record_submission(self, job: LeanJob, run_info: BacktestRunInfo) -> None:
        if not self._storage:
            return
        try:
            await self._storage.record_submission(job.job_id, job.job_type.value, job.strategy_name, run_info)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to record job submission for %s", job.job_id, exc_info=True)

    async def _record_update(self, job: LeanJob) -> None:
        if not self._storage:
            return
        try:
            run_info = job.to_run_info()
            metrics_payload = job.metadata.get("result")

            await self._storage.record_update(
                job.job_id,
                run_info,
                metrics_payload,
            )

            if metrics_payload:
                await self._persist_backtest_result(job, run_info, metrics_payload)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to record job update for %s", job.job_id, exc_info=True)

    async def _persist_backtest_result(
        self,
        job: LeanJob,
        run_info: BacktestRunInfo,
        metrics_payload: Dict[str, Any],
    ) -> None:
        """Persist aggregated Lean results into the backtest repository."""

        try:
            run_uuid = UUID(run_info.backtest_id)
        except ValueError:
            logger.debug("Skipping backtest persistence for non-UUID id %s", run_info.backtest_id)
            return

        parameters_payload: Dict[str, Any] = {
            "strategy": job.strategy_name,
            "job_type": job.job_type.value,
            "start_date": job.request.start_date.isoformat(),
            "end_date": job.request.end_date.isoformat(),
            "resolution": job.request.resolution,
            "pivot_bars": job.request.pivot_bars,
            "lower_timeframe": job.request.lower_timeframe,
            "use_screener_results": job.request.use_screener_results,
            "request_parameters": job.request.parameters or {},
        }

        if job.request.symbols:
            parameters_payload["symbols"] = job.request.symbols
        if job.job_config:
            parameters_payload["job_config"] = job.job_config

        symbol = None
        if job.request.symbols and len(job.request.symbols) == 1:
            symbol = job.request.symbols[0]

        metrics_payload = dict(metrics_payload)
        metrics_payload.setdefault("result_path", job.result_path)

        await backtest_repository.upsert_result(
            run_uuid,
            symbol=symbol,
            parameters=parameters_payload,
            metrics=metrics_payload,
            status=job.status.value,
        )


lean_job_service = LeanJobService()
