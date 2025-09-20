"""Combined screener/backtest endpoints backed by normalized repositories."""

from __future__ import annotations

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..models.combined_results import CombinedResponse
from ..services.combined_repository import combined_repository

router = APIRouter(prefix="/api/v2/combined-results", tags=["combined-results"])


@router.get("/", response_model=CombinedResponse)
async def list_combined_results(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    start_date: Optional[date] = Query(None, description="Filter screener results from this date"),
    end_date: Optional[date] = Query(None, description="Filter screener results up to this date"),
    source: Optional[str] = Query(None, description="Filter by screener source metadata"),
    limit: int = Query(100, ge=1, le=500, description="Page size"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> CombinedResponse:
    try:
        total, rows = await combined_repository.list_rows(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            source=source,
            limit=limit,
            offset=offset,
        )
        return CombinedResponse(
            results=[
                {
                    "screener_result_id": row.screener_result_id,
                    "screener_run_id": row.screener_run_id,
                    "symbol": row.symbol,
                    "screener_created_at": row.screener_created_at.isoformat(),
                    "screener_metrics": row.screener_metrics,
                    "filters": row.filters,
                    "screener_metadata": row.screener_metadata,
                    "run_id": row.run_id,
                    "run_created_at": row.run_created_at.isoformat() if row.run_created_at else None,
                    "run_status": row.run_status,
                    "strategy_name": row.strategy_name,
                    "backtest_parameters": row.backtest_parameters,
                    "backtest_metrics": row.backtest_metrics,
                }
                for row in rows
            ],
            total_count=total,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:  # pragma: no cover - defensive logging
        raise HTTPException(status_code=500, detail="Failed to load combined results") from exc
