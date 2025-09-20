"""
API endpoints for filter optimization.
"""

from __future__ import annotations

import logging
from datetime import datetime
from copy import deepcopy
from typing import Any, Dict, List

from asyncpg.exceptions import UndefinedTableError
from fastapi import APIRouter, HTTPException

from ..models.filter_optimization import OptimizationRequest, OptimizationResponse
from ..services.filter_optimizer import FilterOptimizer
from ..services.database import db_pool

router = APIRouter(prefix="/api/v2/filter-optimizer", tags=["filter-optimizer"])
logger = logging.getLogger(__name__)


DEFAULT_DATA_SUMMARY = {
    "price_range": [1.0, 100.0],
    "rsi_range": [0.0, 100.0],
    "gap_range": [-10.0, 10.0],
    "volume_range": [1_000_000.0, 50_000_000.0],
    "rel_volume_range": [1.0, 5.0],
}

DEFAULT_SUGGESTED_RANGES = {
    "price_range": {
        "min": {"suggested_min": 1.0, "suggested_max": 50.0, "suggested_step": 5.0},
        "max": {"suggested_min": 10.0, "suggested_max": 150.0, "suggested_step": 10.0},
    },
    "rsi_range": {
        "min": {"suggested_min": 20.0, "suggested_max": 40.0, "suggested_step": 5.0},
        "max": {"suggested_min": 60.0, "suggested_max": 80.0, "suggested_step": 5.0},
    },
    "gap_range": {
        "min": {"suggested_min": -10.0, "suggested_max": 0.0, "suggested_step": 1.0},
        "max": {"suggested_min": 0.0, "suggested_max": 10.0, "suggested_step": 1.0},
    },
    "volume": {
        "min": {"suggested_min": 1_000_000.0, "suggested_max": 50_000_000.0, "suggested_step": 5_000_000.0},
    },
    "relative_volume": {
        "min": {"suggested_min": 1.0, "suggested_max": 3.0, "suggested_step": 0.5},
    },
}


def _as_float(value: Any) -> float | None:
    """Best-effort conversion to float."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def _percentile(values: List[float], percentile: float) -> float | None:
    """Return percentile using linear interpolation (percentile in [0, 100])."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (percentile / 100) * (len(ordered) - 1)
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * weight


def _build_default_response(start_date: str, end_date: str) -> Dict[str, Any]:
    return {
        "date_range": {"start": start_date, "end": end_date},
        "data_summary": deepcopy(DEFAULT_DATA_SUMMARY),
        "suggested_ranges": deepcopy(DEFAULT_SUGGESTED_RANGES),
    }


def _update_price_suggestions(
    summary: Dict[str, List[float]],
    suggestions: Dict[str, Any],
    min_prices: List[float],
    max_prices: List[float],
) -> None:
    if not min_prices and not max_prices:
        return

    if min_prices:
        summary["price_range"][0] = float(min(min_prices))
        min_percentile = _percentile(min_prices, 25) or summary["price_range"][0]
        max_percentile = _percentile(min_prices, 75) or summary["price_range"][0]
        suggestions["price_range"]["min"]["suggested_min"] = float(min_percentile)
        suggestions["price_range"]["min"]["suggested_max"] = float(max_percentile)

    if max_prices:
        summary["price_range"][1] = float(max(max_prices))
        min_percentile = _percentile(max_prices, 25) or summary["price_range"][1]
        max_percentile = _percentile(max_prices, 90) or summary["price_range"][1]
        suggestions["price_range"]["max"]["suggested_min"] = float(min_percentile)
        suggestions["price_range"]["max"]["suggested_max"] = float(max_percentile)


def _update_volume_suggestions(
    summary: Dict[str, List[float]],
    suggestions: Dict[str, Any],
    volumes: List[float],
) -> None:
    if not volumes:
        return

    summary["volume_range"][0] = float(min(volumes))
    summary["volume_range"][1] = float(max(volumes))
    low = _percentile(volumes, 20) or summary["volume_range"][0]
    high = _percentile(volumes, 80) or summary["volume_range"][1]
    suggestions["volume"]["min"]["suggested_min"] = float(low)
    suggestions["volume"]["min"]["suggested_max"] = float(high)


def _update_rel_volume_suggestions(
    summary: Dict[str, List[float]],
    suggestions: Dict[str, Any],
    ratios: List[float],
) -> None:
    if not ratios:
        return

    summary["rel_volume_range"][0] = float(min(ratios))
    summary["rel_volume_range"][1] = float(max(ratios))
    low = _percentile(ratios, 20) or summary["rel_volume_range"][0]
    high = _percentile(ratios, 80) or summary["rel_volume_range"][1]
    suggestions["relative_volume"]["min"]["suggested_min"] = float(low)
    suggestions["relative_volume"]["min"]["suggested_max"] = float(high)


@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_filters(request: OptimizationRequest) -> OptimizationResponse:
    """Optimize screener filter parameters to maximise the target metric."""
    try:
        optimizer = FilterOptimizer()
        return await optimizer.optimize_filters(request)
    except UndefinedTableError as exc:
        logger.warning("Filter optimizer tables unavailable: %s", exc)
        raise HTTPException(
            status_code=503,
            detail="Filter optimizer datasets are not yet available on this deployment.",
        ) from exc
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.exception("Error optimizing filters")
        raise HTTPException(status_code=500, detail="Failed to optimize filters") from exc


@router.get("/suggested-ranges")
async def get_suggested_ranges(start_date: str, end_date: str) -> dict:
    """Suggest reasonable parameter ranges based on recent screener activity."""
    try:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD") from exc

    try:
        rows = await db_pool.fetch(
            """
            SELECT filters
            FROM screener_runs
            WHERE created_at::date BETWEEN $1::date AND $2::date
            """,
            start_date_obj,
            end_date_obj,
        )
    except UndefinedTableError:
        logger.warning("screener_runs table unavailable when computing filter suggestions; falling back to defaults")
        return _build_default_response(start_date, end_date)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed querying suggested ranges from screener_runs")
        return _build_default_response(start_date, end_date)

    if not rows:
        return _build_default_response(start_date, end_date)

    summary = deepcopy(DEFAULT_DATA_SUMMARY)
    suggestions = deepcopy(DEFAULT_SUGGESTED_RANGES)

    min_prices: List[float] = []
    max_prices: List[float] = []
    volumes: List[float] = []
    rel_volumes: List[float] = []

    for row in rows:
        filters = row.get("filters") if isinstance(row, dict) else row["filters"]
        if not isinstance(filters, dict):
            continue

        min_price = _as_float(filters.get("min_price"))
        max_price = _as_float(filters.get("max_price"))
        if min_price is not None:
            min_prices.append(min_price)
        if max_price is not None:
            max_prices.append(max_price)

        prev_day = filters.get("prev_day_dollar_volume") or {}
        vol_value = _as_float(prev_day.get("value"))
        if vol_value is not None:
            volumes.append(vol_value)

        rel_vol = filters.get("relative_volume") or {}
        ratio_value = _as_float(rel_vol.get("min_ratio"))
        if ratio_value is not None:
            rel_volumes.append(ratio_value)

    _update_price_suggestions(summary, suggestions, min_prices, max_prices)
    _update_volume_suggestions(summary, suggestions, volumes)
    _update_rel_volume_suggestions(summary, suggestions, rel_volumes)

    return {
        "date_range": {"start": start_date, "end": end_date},
        "data_summary": summary,
        "suggested_ranges": suggestions,
    }
