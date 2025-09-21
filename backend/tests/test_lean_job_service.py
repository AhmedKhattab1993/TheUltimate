import asyncio
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict
from uuid import UUID

import pytest

BACKEND_PATH = Path(__file__).resolve().parents[1]
if str(BACKEND_PATH) not in sys.path:
    sys.path.insert(0, str(BACKEND_PATH))

from app.models.backtest import (
    BacktestRequest,
    BacktestStatus,
    OptimizationParameterRange,
    OptimizationRequest,
)
from app.models.ingestion import DataIngestionRequest
from app.services.lean_job_service import LeanJobService
from app.services.run_storage import InMemoryRunStorage


class FakeRunner:
    async def run_optimize(self, job_id: str, request: BacktestRequest, project_name: str, optimize_config):
        await asyncio.sleep(0)
        return {
            "result_path": f"/tmp/{job_id}",
            "result": {},
        }

    async def run_grid(
        self,
        job_id: str,
        request: BacktestRequest,
        project_name: str,
        job_config,
        on_result,
    ):
        combos = (job_config or {}).get("grid", {}).get("combos", [])

        def _stats(seed: float) -> Dict[str, float]:
            return {
                "total_return": seed,
                "net_profit": seed,
                "net_profit_currency": seed * 1000,
                "final_value": 100000.0 + seed * 1000,
                "SharpeRatio": seed,
            }

        for index, combo in enumerate(combos, start=1):
            if on_result:
                await asyncio.sleep(0)
                await on_result(
                    {
                        "result_path": f"/tmp/{job_id}/combo-{index}",
                        "parameters": combo.get("parameters", {}),
                        "statistics": _stats(float(index)),
                    }
                )

        await asyncio.sleep(0)
        return {
            "result_path": f"/tmp/{job_id}/grid",
            "result": {
                "statistics": _stats(float(len(combos) or 1)),
            },
            "processed_runs": len(combos),
            "execution_time_ms": 10,
        }


class FakeIngestionRunner:
    async def run(self, job_id: str, config):
        await asyncio.sleep(0)
        return {"result_path": f"/tmp/{job_id}-data.log"}


class FakeBacktestRepository:
    def __init__(self):
        self.records = []

    async def upsert_result(self, run_id, *, symbol, parameters, metrics, status):  # noqa: D401 - test helper
        self.records.append(
            {
                "run_id": run_id,
                "symbol": symbol,
                "parameters": parameters,
                "metrics": metrics,
                "status": status,
            }
        )


@pytest.fixture(autouse=True)
def patched_backtest_repository(monkeypatch):
    repo = FakeBacktestRepository()
    monkeypatch.setattr('app.services.lean_job_service.backtest_repository', repo)
    return repo


@pytest.mark.asyncio
async def test_submit_backtest_completes_job(patched_backtest_repository):
    service = LeanJobService(
        runner=FakeRunner(),
        storage=InMemoryRunStorage(),
        ingestion_runner=FakeIngestionRunner(),
    )

    request = BacktestRequest(
        strategy_name="MarketStructure",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        initial_cash=Decimal("100000"),
        resolution="Minute",
        pivot_bars=5,
        lower_timeframe="5min",
        symbols=["AAPL"],
    )

    run_info = await service.submit_backtest(request)
    job = service._jobs[run_info.backtest_id]

    # Wait for the background task to finish
    await job.task

    runs = await service.list_backtests()

    assert runs
    assert runs[0].backtest_id == run_info.backtest_id
    assert runs[0].status == BacktestStatus.COMPLETED
    assert runs[0].job_type == "backtest"
    assert run_info.targets == ["AAPL"]
    assert run_info.job_type == "backtest"
    assert job.result_path and run_info.backtest_id in job.result_path
    assert patched_backtest_repository.records
    record = patched_backtest_repository.records[0]
    assert record["run_id"] == UUID(run_info.backtest_id)
    assert record["status"] == BacktestStatus.COMPLETED.value
    assert record["metrics"]["statistics"]["total_return"] == 1.0
    assert record["symbol"] == "AAPL"
    assert record["parameters"].get("symbol") == "AAPL"


@pytest.mark.asyncio
async def test_submit_optimize_records_job():
    service = LeanJobService(
        runner=FakeRunner(),
        storage=InMemoryRunStorage(),
        ingestion_runner=FakeIngestionRunner(),
    )

    base_request = BacktestRequest(
        strategy_name="MarketStructure",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        initial_cash=Decimal("100000"),
        resolution="Minute",
        pivot_bars=5,
        lower_timeframe="5min",
    )

    optimize_request = OptimizationRequest(
        base_request=base_request,
        target_metric="SharpeRatio",
        target_direction="maximize",
        parameters=[
            OptimizationParameterRange(name="pivot_bars", min=3, max=7, step=1),
        ],
        max_concurrent_backtests=2,
    )

    run_info = await service.submit_optimize(optimize_request)
    job = service._jobs[run_info.backtest_id]

    await job.task

    runs = await service.list_backtests()
    optimize_run = next(run for run in runs if run.backtest_id == run_info.backtest_id)

    assert optimize_run.job_type == "optimize"
    assert optimize_run.status == BacktestStatus.COMPLETED


@pytest.mark.asyncio
async def test_submit_data_job_records_job():
    service = LeanJobService(
        runner=FakeRunner(),
        storage=InMemoryRunStorage(),
        ingestion_runner=FakeIngestionRunner(),
    )

    request = DataIngestionRequest(
        dataset='minute',
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 5),
        resume=False,
    )

    run_info = await service.submit_data_job(request)
    job = service._jobs[run_info.backtest_id]

    await job.task

    runs = await service.list_backtests()
    data_run = next(run for run in runs if run.backtest_id == run_info.backtest_id)

    assert data_run.job_type == "data"
    assert data_run.status == BacktestStatus.COMPLETED


@pytest.mark.asyncio
async def test_submit_grid_job_streams_results(patched_backtest_repository):
    service = LeanJobService(
        runner=FakeRunner(),
        storage=InMemoryRunStorage(),
        ingestion_runner=FakeIngestionRunner(),
    )

    base_request = BacktestRequest(
        strategy_name="MarketStructure",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        initial_cash=Decimal("100000"),
        resolution="Minute",
        pivot_bars=5,
        lower_timeframe="5min",
    )

    run_infos = await service.submit_grid_job(
        base_request,
        parameter_sweeps=[
            {"pivot_bars": 4},
            {"pivot_bars": 6},
        ],
    )

    assert len(run_infos) == 1

    run_info = run_infos[0]
    assert run_info.job_type == "grid"
    assert run_info.targets == ["combo-0001", "combo-0002"]

    job = service._jobs[run_info.backtest_id]
    await job.task

    stored_labels = {
        record["symbol"]
        for record in patched_backtest_repository.records
        if record["symbol"]
    }
    assert stored_labels == {"combo-0001", "combo-0002"}

    final_info = await service.get_backtest(run_info.backtest_id)
    assert final_info is not None
    assert final_info.targets == ["combo-0001", "combo-0002"]
    assert final_info.metrics and final_info.metrics["SharpeRatio"] == Decimal("2.0")


@pytest.mark.asyncio
async def test_submit_grid_job_rejects_non_numeric_parameters():
    service = LeanJobService(
        runner=FakeRunner(),
        storage=InMemoryRunStorage(),
        ingestion_runner=FakeIngestionRunner(),
    )

    base_request = BacktestRequest(
        strategy_name="MarketStructure",
        start_date=date(2024, 1, 1),
        end_date=date(2024, 1, 2),
        initial_cash=Decimal("100000"),
        resolution="Minute",
        pivot_bars=5,
        lower_timeframe="5min",
    )

    with pytest.raises(ValueError):
        await service.submit_grid_job(
            base_request,
            parameter_sweeps=[{"pivot_bars": "fast"}],
        )
