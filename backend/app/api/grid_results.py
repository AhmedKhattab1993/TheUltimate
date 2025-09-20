"""Grid results API backed by normalized run tables."""

from __future__ import annotations

from datetime import date
from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..models.grid_results import GridRunDetail, GridRunResult, GridRunSummary, GridResultsListResponse
from ..services.grid_repository import grid_repository

router = APIRouter(prefix="/api/v2/grid/results", tags=["grid-results"])


def _duration_ms(started_at, completed_at) -> Optional[float]:
    if started_at and completed_at:
        return (completed_at - started_at).total_seconds() * 1000
    return None


def _to_float_map(payload: Dict[str, object]) -> Dict[str, float]:
    output: Dict[str, float] = {}
    for key, value in (payload or {}).items():
        try:
            output[key] = float(value)
        except (TypeError, ValueError):
            continue
    return output


@router.get("", response_model=GridResultsListResponse)
async def list_grid_runs(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    start_date: Optional[date] = Query(None, description="Filter runs created after this date"),
    end_date: Optional[date] = Query(None, description="Filter runs created before this date"),
    strategy_name: Optional[str] = Query(None, description="Filter by strategy"),
    symbol: Optional[str] = Query(None, description="Filter runs that targeted a specific symbol"),
):
    total, rows = await grid_repository.list_runs(
        page=page,
        page_size=page_size,
        start_date=start_date,
        end_date=end_date,
        strategy_name=strategy_name,
        symbol=symbol,
    )

    summaries = [
        GridRunSummary(
            run_id=str(row.run_id),
            strategy_name=row.strategy_name,
            status=row.status,
            job_type=row.job_type,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            duration_ms=_duration_ms(row.started_at, row.completed_at),
            target_count=row.target_count,
            metrics=_to_float_map(row.metrics),
            metadata=row.metadata,
        )
        for row in rows
    ]

    return GridResultsListResponse(
        results=summaries,
        total_count=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{run_id}", response_model=GridRunDetail)
async def get_grid_run(run_id: str) -> GridRunDetail:
    try:
        run_uuid = UUID(run_id)
    except ValueError as exc:  # pragma: no cover - FastAPI handles response formatting
        raise HTTPException(status_code=400, detail="Invalid grid run id") from exc

    run = await grid_repository.get_run(run_uuid)
    if not run:
        raise HTTPException(status_code=404, detail="Grid run not found")

    results_rows = await grid_repository.list_results(run_uuid)
    results = [
        GridRunResult(
            symbol=row.symbol,
            status=row.status,
            created_at=row.created_at,
            parameters=row.parameters,
            metrics=row.metrics,
        )
        for row in results_rows
    ]

    return GridRunDetail(
        run_id=str(run.run_id),
        strategy_name=run.strategy_name,
        status=run.status,
        job_type=run.job_type,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        duration_ms=_duration_ms(run.started_at, run.completed_at),
        target_count=run.target_count,
        metrics=_to_float_map(run.metrics),
        metadata=run.metadata,
        results=results,
    )
