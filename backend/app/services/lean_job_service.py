"""Unified Lean job orchestration service."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from collections import defaultdict

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
from .screener_repository import screener_repository

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
        self._symbol_mapping: Optional[Dict[str, str]] = None

    # ------------------------------------------------------------------
    # Grid helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _coerce_decimal(value: Any) -> Decimal:
        """Convert a grid parameter value to Decimal for canonical comparisons."""

        if isinstance(value, Decimal):
            return value
        if isinstance(value, bool):
            return Decimal(1 if value else 0)
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        if isinstance(value, str):
            stripped = value.strip()
            try:
                return Decimal(stripped)
            except (InvalidOperation, ValueError) as exc:  # pragma: no cover - defensive
                raise ValueError(f"Value '{value}' is not numeric") from exc
        raise ValueError(f"Unsupported value type for grid parameter: {value!r}")

    @staticmethod
    def _decimal_to_str(value: Decimal) -> str:
        """Normalise a Decimal to a plain string without scientific notation."""

        quantised = value.normalize()
        text = format(quantised, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text or "0"

    @classmethod
    def _make_combo_key(cls, parameter_names: List[str], numeric_parameters: Dict[str, Decimal]) -> str:
        parts: List[str] = []
        for name in parameter_names:
            if name not in numeric_parameters:
                continue
            parts.append(f"{name}={cls._decimal_to_str(numeric_parameters[name])}")
        return "|".join(parts) if parts else "__default__"

    def _build_grid_definition(
        self,
        request: BacktestRequest,
        parameter_sweeps: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not parameter_sweeps:
            raise ValueError("parameter_sweeps must contain at least one entry")

        value_sets: Dict[str, set[Decimal]] = {}
        first_raw_values: Dict[str, Any] = {}
        combos_raw: List[Dict[str, Any]] = []

        for index, sweep in enumerate(parameter_sweeps):
            numeric_params: Dict[str, Decimal] = {}
            for name, raw_value in sweep.items():
                try:
                    numeric_value = self._coerce_decimal(raw_value)
                except ValueError as exc:
                    raise ValueError(
                        f"Grid parameter '{name}' must be numeric-compatible (value: {raw_value!r})"
                    ) from exc
                numeric_params[name] = numeric_value
                value_sets.setdefault(name, set()).add(numeric_value)
                first_raw_values.setdefault(name, raw_value)

            combos_raw.append(
                {
                    "index": index,
                    "parameters": sweep,
                    "numeric": numeric_params,
                }
            )

        parameter_names = sorted(value_sets.keys())
        combos: List[Dict[str, Any]] = []
        seen_keys: set[str] = set()

        for raw in combos_raw:
            key = self._make_combo_key(parameter_names, raw["numeric"])
            if key in seen_keys:
                raise ValueError(
                    "Duplicate grid parameter combination detected. Ensure sweeps contain unique combinations."
                )
            seen_keys.add(key)

            label = f"combo-{raw['index'] + 1:04d}"
            display_parts = [
                f"{name}={raw['parameters'][name]!r}"
                for name in parameter_names
                if name in raw["parameters"]
            ]
            display = ", ".join(display_parts)

            combos.append(
                {
                    "key": key,
                    "label": label,
                    "display": display,
                    "parameters": raw["parameters"],
                }
            )

        parameter_ranges: List[Dict[str, Any]] = []
        for name in parameter_names:
            ordered = sorted(value_sets[name])
            if len(ordered) == 1:
                step = Decimal("1")
            else:
                deltas = {ordered[i + 1] - ordered[i] for i in range(len(ordered) - 1)}
                if len(deltas) != 1:
                    raise ValueError(
                        f"Grid parameter '{name}' must use a consistent step size (received values: {[self._decimal_to_str(v) for v in ordered]})"
                    )
                step = deltas.pop()
                if step <= 0:
                    raise ValueError(f"Grid parameter '{name}' step must be positive (calculated {step})")

            parameter_ranges.append(
                {
                    "name": name,
                    "min": self._decimal_to_str(ordered[0]),
                    "max": self._decimal_to_str(ordered[-1]),
                    "step": self._decimal_to_str(step),
                }
            )

        # Ensure the base request carries defaults for single-value parameters so Lean config is deterministic
        request.parameters = request.parameters or {}
        for name, raw_value in first_raw_values.items():
            request.parameters.setdefault(name, raw_value)

        return {
            "parameter_names": parameter_names,
            "parameter_ranges": parameter_ranges,
            "combos": combos,
            "total_combos": len(combos),
            "defaults": first_raw_values,
        }

    def _lazy_symbol_mapping(self) -> Dict[str, str]:
        if self._symbol_mapping is None:
            try:
                mapping_path = Path(__file__).resolve().parents[3] / "lean" / "MarketStructure" / "symbol_mapping.json"
                data = json.loads(mapping_path.read_text())
                mapping = data.get("index_to_symbol", {})
                if not isinstance(mapping, dict):
                    mapping = {}
            except Exception:  # pragma: no cover - depends on filesystem
                mapping = {}
            if not mapping:
                mapping = {"0": "SPY"}
            self._symbol_mapping = mapping
        return self._symbol_mapping

    def _default_symbol(self) -> str:
        mapping = self._lazy_symbol_mapping()
        if "0" in mapping:
            return mapping["0"]
        first = next(iter(mapping.values()), None)
        return first or "SPY"

    def _normalise_symbols(self, symbols: List[str]) -> List[str]:
        ordered: List[str] = []
        seen: set[str] = set()
        for symbol in symbols:
            if not isinstance(symbol, str):
                continue
            upper = symbol.upper().strip()
            if not upper or upper in seen:
                continue
            seen.add(upper)
            ordered.append(upper)
        return ordered

    @staticmethod
    def _generate_trading_days(start: date, end: date) -> List[date]:
        days: List[date] = []
        current = start
        while current <= end:
            if current.weekday() < 5:
                days.append(current)
            current += timedelta(days=1)
        return days

    @staticmethod
    def _make_parameter_sweeps(symbols: List[str]) -> List[Dict[str, Any]]:
        if not symbols:
            return [{"symbol_slot": 0}]
        return [{"symbol_slot": index} for index in range(len(symbols))]

    def _build_symbol_slot_optimize_params(self, parameter_sweeps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not parameter_sweeps:
            return [
                {
                    "name": "symbol_slot",
                    "min": self._decimal_to_str(Decimal(0)),
                    "max": self._decimal_to_str(Decimal(0)),
                    "step": self._decimal_to_str(Decimal("1")),
                }
            ]

        slot_values: List[Decimal] = []
        for sweep in parameter_sweeps:
            try:
                slot_value = self._coerce_decimal(sweep.get("symbol_slot", 0))
            except ValueError:
                slot_value = Decimal(0)
            slot_values.append(slot_value)

        min_slot = min(slot_values)
        max_slot = max(slot_values)

        return [
            {
                "name": "symbol_slot",
                "min": self._decimal_to_str(min_slot),
                "max": self._decimal_to_str(max_slot),
                "step": self._decimal_to_str(Decimal("1")),
            }
        ]

    def _build_manual_daily_runs(self, request: BacktestRequest) -> Tuple[List[Dict[str, Any]], List[str]]:
        days = self._generate_trading_days(request.start_date, request.end_date)
        symbols = self._normalise_symbols(request.symbols or [])
        if not symbols:
            symbols = [self._default_symbol()]

        targets: List[str] = list(symbols)
        daily_runs: List[Dict[str, Any]] = []
        for trading_day in days:
            parameter_sweeps = self._make_parameter_sweeps(symbols)
            symbol_map = {str(index): symbol for index, symbol in enumerate(symbols)}
            day_targets = [f"{trading_day.isoformat()}:{symbol}" for symbol in symbols]
            symbols_snapshot = list(symbols)
            daily_runs.append(
                {
                    "date": trading_day.isoformat(),
                    "symbols": symbols_snapshot,
                    "parameter_sweeps": parameter_sweeps,
                    "symbol_map": symbol_map,
                    "targets": day_targets,
                }
            )
        return daily_runs, targets

    async def _build_screener_daily_runs(self, request: BacktestRequest) -> Tuple[List[Dict[str, Any]], List[str]]:
        total, runs = await screener_repository.list_runs(limit=1)
        if total == 0 or not runs:
            raise ValueError("No screener runs available for backtesting")

        run_detail = await screener_repository.get_run(runs[0].id)
        if not run_detail or not run_detail.results:
            raise ValueError("Latest screener run does not contain any symbols")

        start = request.start_date
        end = request.end_date

        symbols_by_day: Dict[date, List[str]] = defaultdict(list)
        for entry in run_detail.results:
            symbol = entry.symbol.upper()
            metrics = entry.metrics or {}
            qualifying_dates = metrics.get("qualifying_dates") or []
            if isinstance(qualifying_dates, str):
                qualifying_dates = [qualifying_dates]
            for date_str in qualifying_dates:
                try:
                    parsed = date.fromisoformat(str(date_str)[:10])
                except ValueError:
                    continue
                if parsed < start or parsed > end:
                    continue
                if parsed.weekday() >= 5:
                    continue
                current_symbols = symbols_by_day[parsed]
                if symbol not in current_symbols:
                    current_symbols.append(symbol)

        if not symbols_by_day:
            # Fallback: use data_date from metrics if qualifying dates missing
            for entry in run_detail.results:
                symbol = entry.symbol.upper()
                metrics = entry.metrics or {}
                data_date = metrics.get("data_date") or metrics.get("date")
                if not data_date:
                    continue
                try:
                    parsed = date.fromisoformat(str(data_date)[:10])
                except ValueError:
                    continue
                if parsed < start or parsed > end or parsed.weekday() >= 5:
                    continue
                current_symbols = symbols_by_day[parsed]
                if symbol not in current_symbols:
                    current_symbols.append(symbol)

        if not symbols_by_day:
            raise ValueError("Screener run does not cover the selected date range")

        daily_runs: List[Dict[str, Any]] = []
        targets_set: List[str] = []
        sorted_days = sorted(symbols_by_day.keys())

        shared_payload = {
            "run_id": str(run_detail.id),
            "timestamp": run_detail.created_at.isoformat(),
            "filters": run_detail.filters,
            "metadata": run_detail.metadata,
        }

        for trading_day in sorted_days:
            symbols = self._normalise_symbols(symbols_by_day[trading_day])
            if not symbols:
                continue
            parameter_sweeps = self._make_parameter_sweeps(symbols)
            symbol_map = {str(index): symbol for index, symbol in enumerate(symbols)}
            day_targets = [f"{trading_day.isoformat()}:{symbol}" for symbol in symbols]
            daily_runs.append(
                {
                    "date": trading_day.isoformat(),
                    "symbols": symbols,
                    "parameter_sweeps": parameter_sweeps,
                    "symbol_map": symbol_map,
                    "screener_payload": {
                        **shared_payload,
                        "date": trading_day.isoformat(),
                        "symbols": symbols,
                    },
                    "parameter_overrides": {
                        "screener_target_date": trading_day.isoformat(),
                    },
                    "targets": day_targets,
                }
            )
            for symbol in symbols:
                if symbol not in targets_set:
                    targets_set.append(symbol)

        return daily_runs, targets_set

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

        if job_type is JobType.BACKTEST and job_config is None:
            if request.start_date > request.end_date:
                raise ValueError("start_date must be on or before end_date")

            if request.use_screener_results:
                daily_runs, targets = await self._build_screener_daily_runs(request)
            else:
                daily_runs, targets = self._build_manual_daily_runs(request)

            job_config = {
                "daily_runs": daily_runs,
                "targets": targets,
            }

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

        grid_config = (job.job_config or {}).get("grid") or {}
        combos = grid_config.get("combos") or []
        if job_type in (JobType.BACKTEST, JobType.GRID) and combos:
            await self._record_grid_targets(job_id, combos)

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
        """Submit a grid run powered by Lean CLI optimize for faster execution."""

        strategy = strategy_registry.require(base_request.strategy_name)
        strategy_registry.merge_request_with_defaults(base_request)

        grid_definition = self._build_grid_definition(base_request, parameter_sweeps)
        parameter_ranges = grid_definition["parameter_ranges"]

        if not parameter_ranges:
            raise ValueError("Grid requests require at least one parameter to sweep")

        optimize_config: Dict[str, Any] = {
            "target_metric": "SharpeRatio",
            "target_direction": "maximize",
            "parameters": parameter_ranges,
        }

        parallelism = getattr(strategy.capabilities, "parallelism", None)
        if parallelism:
            optimize_config["max_concurrent_backtests"] = parallelism

        job_config = {
            "optimize": optimize_config,
            "grid": grid_definition,
            "targets": [combo["label"] for combo in grid_definition["combos"]],
        }

        run_info = await self.submit_backtest(
            base_request,
            job_type=JobType.GRID,
            job_config=job_config,
        )

        logger.info(
            "Queued grid optimization job %s (%d combinations) for strategy %s",
            run_info.backtest_id,
            grid_definition["total_combos"],
            strategy.id,
        )
        return [run_info]

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
            if job.job_type in (JobType.BACKTEST, JobType.GRID):
                result = await self._run_grid_job(job, project_name)
            elif job.job_type is JobType.OPTIMIZE:
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
                raise ValueError(f"Unsupported job type {job.job_type}")
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

    async def _record_grid_targets(self, job_id: str, combos: List[Dict[str, Any]]) -> None:
        if not self._storage or not combos:
            return
        try:
            await self._storage.record_grid_targets(job_id, combos)
        except Exception:  # pragma: no cover - defensive
            logger.debug("Failed to persist grid targets for %s", job_id, exc_info=True)

    async def _run_single_grid_run(
        self,
        job: LeanJob,
        project_name: str,
        request: BacktestRequest,
        job_config: Dict[str, Any],
        *,
        day_label: Optional[str] = None,
        day_index: int = 1,
        total_days: int = 1,
    ) -> Dict[str, Any]:
        grid_config = (job_config or {}).get("grid") or {}
        parameter_names: List[str] = list(grid_config.get("parameter_names") or [])
        combos: List[Dict[str, Any]] = list(grid_config.get("combos") or [])
        defaults: Dict[str, Any] = dict(grid_config.get("defaults") or {})
        total_expected = int(grid_config.get("total_combos") or len(combos))

        combos_map = {combo.get("key"): combo for combo in combos if combo.get("key")}

        symbol_slots_lookup = (job_config or {}).get("symbol_slots") or {}

        progress_state = {
            "seen": set(),
            "completed": 0,
            "total": total_expected,
        }
        progress_lock = asyncio.Lock()

        async def handle_result(payload: Dict[str, Any]) -> None:
            parameters = payload.get("parameters") or {}
            numeric_map: Dict[str, Decimal] = {}

            for name in parameter_names:
                value = parameters.get(name, defaults.get(name))
                if value is None:
                    continue
                try:
                    numeric_map[name] = self._coerce_decimal(value)
                except ValueError:
                    continue

            key = self._make_combo_key(parameter_names, numeric_map)
            combo = combos_map.get(key)

            base_label = combo.get("label") if combo else f"auto-{len(progress_state['seen']) + 1:04d}"
            label = base_label
            if day_label:
                label = f"{day_label}:{base_label}"
            parameters_to_store = dict(combo.get("parameters", {})) if combo else {
                name: parameters.get(name, defaults.get(name))
                for name in parameter_names
                if parameters.get(name, defaults.get(name)) is not None
            }

            actual_symbol: Optional[str] = None
            if "symbol_slot" in numeric_map:
                slot_index = int(numeric_map["symbol_slot"])
                actual_symbol = symbol_slots_lookup.get(str(slot_index)) or symbol_slots_lookup.get(slot_index)
                if actual_symbol:
                    parameters_to_store.setdefault("symbol", actual_symbol)

            status = payload.get("status", "completed")

            await self._persist_grid_result(
                job,
                label=label,
                parameters=parameters_to_store,
                result_payload=payload,
                status=status,
                target_symbol=actual_symbol,
            )

            async with progress_lock:
                if key not in progress_state["seen"]:
                    progress_state["seen"].add(key)
                    progress_state["completed"] += 1

                job.metadata.setdefault("grid_progress", {})
                job.metadata["grid_progress"]["completed"] = progress_state["completed"]
                job.metadata["grid_progress"]["total"] = progress_state["total"]
                job.metadata["grid_progress"]["last_label"] = label
                job.metadata["grid_progress"]["day_index"] = day_index
                job.metadata["grid_progress"]["total_days"] = total_days
                if day_label:
                    job.metadata["grid_progress"]["day"] = day_label

                result_path = payload.get("result_path")
                if result_path:
                    job.metadata.setdefault("grid_results", {})[label] = {
                        "result_path": result_path,
                    }

                await self._record_update(job)

        result = await self._runner.run_grid(
            job_id=job.job_id,
            request=request,
            project_name=project_name,
            job_config=job_config,
            on_result=handle_result,
        )

        job.metadata.setdefault("grid_progress", {})
        job.metadata["grid_progress"].update(
            {
                "completed": progress_state["completed"],
                "total": progress_state["total"],
                "finished": True,
            }
        )

        return result

    async def _run_grid_job(self, job: LeanJob, project_name: str) -> Dict[str, Any]:
        job_config = job.job_config or {}
        daily_runs = list(job_config.get("daily_runs") or [])

        if daily_runs:
            combined_result: Dict[str, Any] = {"daily_results": []}
            total_days = len(daily_runs)
            accumulated_execution_ms = 0.0
            last_result_path: Optional[str] = None

            for index, daily in enumerate(daily_runs, start=1):
                day_str = daily.get("date")
                try:
                    day_date = date.fromisoformat(day_str) if day_str else job.request.start_date
                except ValueError:
                    day_date = job.request.start_date

                request_copy = job.request.model_copy(deep=True)
                request_copy.start_date = day_date
                request_copy.end_date = day_date
                request_copy.symbols = list(daily.get("symbols") or [])

                if daily.get("parameter_overrides"):
                    overrides = dict(request_copy.parameters or {})
                    overrides.update(daily["parameter_overrides"])
                    request_copy.parameters = overrides

                parameter_sweeps = list(daily.get("parameter_sweeps") or self._make_parameter_sweeps(request_copy.symbols or []))
                grid_definition = self._build_grid_definition(request_copy, parameter_sweeps)
                optimize_parameters = self._build_symbol_slot_optimize_params(parameter_sweeps)
                symbol_map = daily.get("symbol_map") or {str(index): symbol for index, symbol in enumerate(request_copy.symbols or [])}

                day_job_config: Dict[str, Any] = {
                    "grid": grid_definition,
                    "symbol_slots": symbol_map,
                    "targets": daily.get("targets"),
                    "optimize": {
                        "target_metric": "SharpeRatio",
                        "target_direction": "maximize",
                        "parameters": optimize_parameters,
                    },
                }
                if symbol_map:
                    mapping_payload = {
                        "index_to_symbol": {
                            str(slot): symbol for slot, symbol in symbol_map.items()
                        }
                    }
                    day_job_config["symbol_map"] = mapping_payload

                if daily.get("screener_payload"):
                    payload = dict(daily["screener_payload"])
                    payload.setdefault("symbols", request_copy.symbols)
                    payload.setdefault("date", day_str)
                    day_job_config["screener_payload"] = payload

                day_result = await self._run_single_grid_run(
                    job,
                    project_name,
                    request_copy,
                    day_job_config,
                    day_label=day_str,
                    day_index=index,
                    total_days=total_days,
                )

                combined_result["daily_results"].append({
                    "date": day_str,
                    "result": day_result,
                })

                execution_ms = day_result.get("execution_time_ms")
                if isinstance(execution_ms, (int, float)):
                    accumulated_execution_ms += float(execution_ms)

                result_payload = day_result.get("result")
                if isinstance(result_payload, dict):
                    combined_result["result"] = result_payload
                    if result_payload.get("result_path"):
                        last_result_path = result_payload["result_path"]
                elif isinstance(day_result.get("statistics"), dict):
                    combined_result["result"] = day_result

                if day_result.get("result_path"):
                    last_result_path = day_result["result_path"]

            if accumulated_execution_ms:
                combined_result["execution_time_ms"] = accumulated_execution_ms
            if last_result_path:
                combined_result["result_path"] = last_result_path

            return combined_result

        return await self._run_single_grid_run(
            job,
            project_name,
            job.request,
            job_config,
        )

    async def _persist_grid_result(
        self,
        job: LeanJob,
        *,
        label: str,
        parameters: Dict[str, Any],
        result_payload: Dict[str, Any],
        status: str,
        target_symbol: Optional[str] = None,
    ) -> None:
        try:
            run_uuid = UUID(job.job_id)
        except ValueError:
            return

        metrics_payload = {
            "statistics": result_payload.get("statistics") or {},
            "runtime_statistics": result_payload.get("runtime_statistics") or {},
            "raw_statistics": result_payload.get("raw_statistics") or {},
        }

        try:
            await backtest_repository.upsert_result(
                run_uuid,
                symbol=target_symbol or label,
                parameters=parameters,
                metrics=metrics_payload,
                status=status,
            )
        except Exception:  # pragma: no cover - depends on DB availability
            logger.debug("Failed to persist grid result %s for %s", label, job.job_id, exc_info=True)

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
