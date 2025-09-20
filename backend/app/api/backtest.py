"""Lean backtest API powered by the unified job service."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.backtest import (
    BacktestListResponse,
    BacktestProgress,
    BacktestRequest,
    BacktestRunInfo,
    GridBacktestSweepRequest,
    RunSummaryResponse,
    OptimizationRequest,
    StrategyInfo,
)
from ..registry import strategy_registry
from ..services.lean_job_service import lean_job_service
from ..services.run_summary import run_summary_service

router = APIRouter(prefix="/api/v2/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)


def _as_strategy_info(definition) -> StrategyInfo:
    """Convert registry definition to legacy StrategyInfo shape."""

    parameter_map: Dict[str, Dict[str, object]] = {}
    for parameter in definition.parameters:
        options = [option.model_dump() for option in parameter.options or []]
        parameter_map[parameter.name] = {
            "label": parameter.label,
            "description": parameter.description,
            "default": parameter.default,
            "control_type": parameter.control_type,
            "options": options,
            "required": parameter.required,
            "min_value": parameter.min_value,
            "max_value": parameter.max_value,
            "step": parameter.step,
        }

    return StrategyInfo(
        name=definition.id,
        file_path=definition.project_path,
        description=definition.description,
        parameters=parameter_map,
    )


@router.get("/strategies", response_model=List[StrategyInfo])
async def list_strategies() -> List[StrategyInfo]:
    """Expose Lean strategies registered in the catalogue."""

    return [_as_strategy_info(definition) for definition in strategy_registry.list()]


@router.get("/strategies/{strategy_id}", response_model=StrategyInfo)
async def get_strategy(strategy_id: str) -> StrategyInfo:
    try:
        definition = strategy_registry.require(strategy_id)
    except ValueError as exc:  # pragma: no cover - FastAPI handles response
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return _as_strategy_info(definition)


@router.post("/run", response_model=BacktestRunInfo)
async def start_backtest(request: BacktestRequest) -> BacktestRunInfo:
    """Submit a Lean backtest through the job service."""

    try:
        return await lean_job_service.submit_backtest(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to queue backtest: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to queue backtest") from exc


@router.post("/grid/run", response_model=List[BacktestRunInfo])
async def start_grid_backtests(request: GridBacktestSweepRequest) -> List[BacktestRunInfo]:
    base_request = request.base_request
    try:
        return await lean_job_service.submit_grid_job(
            base_request,
            parameter_sweeps=request.parameter_sweeps,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to queue grid backtests: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to queue grid backtests") from exc


@router.post("/optimize/run", response_model=BacktestRunInfo)
async def start_optimize(request: OptimizationRequest) -> BacktestRunInfo:
    """Submit a Lean optimization job."""

    try:
        return await lean_job_service.submit_optimize(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to queue optimization: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to queue optimization") from exc


@router.get("/status/{backtest_id}", response_model=BacktestRunInfo)
async def get_backtest_status(backtest_id: str) -> BacktestRunInfo:
    run_info = await lean_job_service.get_backtest(backtest_id)
    if not run_info:
        raise HTTPException(status_code=404, detail="Backtest not found")
    return run_info


@router.get("/progress/{backtest_id}", response_model=BacktestProgress | None)
async def get_backtest_progress(backtest_id: str) -> Optional[BacktestProgress]:
    return await lean_job_service.get_progress(backtest_id)


@router.delete("/cancel/{backtest_id}")
async def cancel_backtest(backtest_id: str) -> Dict[str, str]:
    cancelled = await lean_job_service.cancel(backtest_id)
    if not cancelled:
        raise HTTPException(status_code=404, detail="Backtest not found or already finished")
    return {"message": f"Backtest '{backtest_id}' cancelled"}


@router.get("/runs", response_model=BacktestListResponse)
async def list_backtests(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Page size"),
    strategy_name: Optional[str] = Query(None, description="Filter by strategy"),
) -> BacktestListResponse:
    """List recent backtest runs from the in-memory catalogue."""

    runs = await lean_job_service.list_backtests()
    if strategy_name:
        runs = [run for run in runs if run.request.strategy_name == strategy_name]

    total = len(runs)
    start_index = (page - 1) * page_size
    end_index = start_index + page_size
    slice_ = runs[start_index:end_index]

    return BacktestListResponse(
        runs=slice_,
        total_count=total,
        page=page,
        page_size=page_size,
    )


@router.get("/summary", response_model=RunSummaryResponse)
async def get_run_summary() -> RunSummaryResponse:
    try:
        return await run_summary_service.get_summary()
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to build run summary: %s", exc)
        raise HTTPException(status_code=500, detail="Failed to load run summary") from exc
