"""API endpoints for screener runs backed by the normalized schema."""

from __future__ import annotations

from datetime import date
from typing import Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..models.screener_results import (
    ScreenerResultDetail,
    ScreenerResultSummary,
    ScreenerResultsListResponse,
    SymbolMetrics,
)
from ..services.screener_repository import screener_repository

router = APIRouter(prefix="/api/v2/screener/results", tags=["screener-results"])


def create_filter_description(filters: dict) -> str:
    """Create a user-friendly description of the filters applied."""
    descriptions: List[str] = []

    min_price = filters.get("min_price")
    max_price = filters.get("max_price")
    if min_price is not None or max_price is not None:
        if min_price is not None and max_price is not None:
            descriptions.append(f"Price: ${min_price:.2f} - ${max_price:.2f}")
        elif min_price is not None:
            descriptions.append(f"Price: ≥ ${min_price:.2f}")
        elif max_price is not None:
            descriptions.append(f"Price: ≤ ${max_price:.2f}")

    price_vs_ma = filters.get("price_vs_ma") or {}
    if price_vs_ma.get("enabled"):
        period = price_vs_ma.get("period", 20)
        condition = price_vs_ma.get("condition", "above")
        descriptions.append(f"Price {condition} SMA{period}")

    rsi = filters.get("rsi") or {}
    if rsi.get("enabled"):
        period = rsi.get("period", 14)
        threshold = rsi.get("threshold", 0)
        condition = rsi.get("condition", "above")
        descriptions.append(f"RSI{period} {condition} {threshold}")

    gap = filters.get("gap") or {}
    if gap.get("enabled"):
        threshold = gap.get("threshold", 0)
        direction = gap.get("direction", "any")
        if direction == "any":
            descriptions.append(f"Gap ≥ {threshold}%")
        else:
            descriptions.append(f"Gap {direction} ≥ {threshold}%")

    prev_day = filters.get("prev_day_dollar_volume") or {}
    if prev_day.get("enabled"):
        min_vol = prev_day.get("value", 0)
        if min_vol >= 1_000_000:
            descriptions.append(f"Volume ≥ ${min_vol / 1_000_000:.1f}M")
        elif min_vol >= 1_000:
            descriptions.append(f"Volume ≥ ${min_vol / 1_000:.0f}K")
        else:
            descriptions.append(f"Volume ≥ ${min_vol:,.0f}")

    rel_vol = filters.get("relative_volume") or {}
    if rel_vol.get("enabled"):
        ratio = rel_vol.get("min_ratio", 1.0)
        recent = rel_vol.get("recent_days", 1)
        lookback = rel_vol.get("lookback_days", 20)
        descriptions.append(f"Relative Volume ({recent}d vs {lookback}d) ≥ {ratio}x")

    return "; ".join(descriptions) if descriptions else "No filters applied"


def _normalise_filters(filters: Dict[str, object] | None, metadata: Dict[str, object] | None) -> Dict[str, object]:
    payload = dict(filters or {})
    date_range = payload.pop("date_range", {})
    start_date = date_range.get("start") or (metadata or {}).get("start_date")
    end_date = date_range.get("end") or (metadata or {}).get("end_date")
    if start_date:
        payload["start_date"] = start_date
    if end_date:
        payload["end_date"] = end_date
    payload["description"] = create_filter_description(payload)
    return payload


@router.get("", response_model=ScreenerResultsListResponse)
async def list_screener_results(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    start_date: Optional[date] = Query(None, description="Filter results after this date"),
    end_date: Optional[date] = Query(None, description="Filter results before this date"),
) -> ScreenerResultsListResponse:
    """List screener runs stored in the repository."""

    offset = (page - 1) * page_size
    total, runs = await screener_repository.list_runs(
        limit=page_size,
        offset=offset,
        start_date=start_date,
        end_date=end_date,
    )

    summaries: List[ScreenerResultSummary] = []
    for run in runs:
        filters = _normalise_filters(run.filters, run.metadata)
        execution_time_ms = run.metadata.get("execution_time_ms", 0) if isinstance(run.metadata, dict) else 0
        total_symbols = run.metadata.get("total_symbols_screened") if isinstance(run.metadata, dict) else None
        summaries.append(
            ScreenerResultSummary(
                id=str(run.id),
                timestamp=run.created_at.isoformat(),
                symbol_count=run.symbol_count,
                filters=filters,
                execution_time_ms=float(execution_time_ms or 0),
                total_symbols_screened=int(total_symbols or run.symbol_count),
            )
        )

    return ScreenerResultsListResponse(
        results=summaries,
        total_count=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{result_id}", response_model=ScreenerResultDetail)
async def get_screener_result(result_id: str) -> ScreenerResultDetail:
    try:
        run_uuid = UUID(result_id)
    except ValueError as exc:  # pragma: no cover - FastAPI validation fallback
        raise HTTPException(status_code=400, detail="Invalid screener result id") from exc

    run_detail = await screener_repository.get_run(run_uuid)
    if not run_detail:
        raise HTTPException(status_code=404, detail=f"Screener result '{result_id}' not found")

    filters = _normalise_filters(run_detail.filters, run_detail.metadata)
    metadata = dict(run_detail.metadata or {})
    companies: Dict[str, str] = {}
    symbols: List[SymbolMetrics] = []
    for entry in run_detail.results:
        company_name = entry.metrics.get("company_name") if isinstance(entry.metrics, dict) else None
        if company_name:
            companies[entry.symbol] = company_name
        symbols.append(SymbolMetrics(symbol=entry.symbol))

    if companies:
        metadata.setdefault("companies", companies)

    return ScreenerResultDetail(
        id=str(run_detail.id),
        timestamp=run_detail.created_at.isoformat(),
        symbol_count=len(symbols),
        filters=filters,
        metadata=metadata,
        symbols=symbols,
    )
