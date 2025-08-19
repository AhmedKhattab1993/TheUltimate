"""
Simplified screener API endpoint with day-by-day processing.

This endpoint provides a streamlined interface for stock screening that processes
each trading day individually, matching the pipeline behavior.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional, Dict, Any
import numpy as np
import time
import logging
from datetime import datetime, timedelta, date
from uuid import uuid4

from ..models.simple_requests import (
    SimpleScreenRequest,
    SimpleScreenResponse,
    SimpleScreenResult
)
from ..core.simple_filters import (
    SimplePriceRangeFilter,
    PriceVsMAFilter,
    RSIFilter,
    MinAverageVolumeFilter,
    MinAverageDollarVolumeFilter,
    GapFilter,
    PreviousDayDollarVolumeFilter,
    RelativeVolumeFilter
)
from ..services.polygon_client import PolygonClient
from ..services.db_prefilter import OptimizedDataLoader
from ..models.stock import StockData
from ..config import settings
from ..services.screener_results import screener_results_manager
from ..services.cache_service import CacheService
from ..models.cache_models import CachedScreenerRequest, CachedScreenerResult


router = APIRouter(prefix="/api/v2/simple-screener", tags=["simple-screener"])
logger = logging.getLogger(__name__)


async def get_polygon_client():
    """Dependency to get Polygon client with database pool."""
    from app.main import app
    from app.services.database import db_pool
    
    # Get the shared polygon client from app state
    if hasattr(app.state, 'polygon_client'):
        polygon_client = app.state.polygon_client
        # Ensure it has db_pool access
        if not hasattr(polygon_client, 'db_pool'):
            polygon_client.db_pool = db_pool._pool
        return polygon_client
    
    # Fallback: create new client with db_pool
    client = PolygonClient(api_key=settings.polygon_api_key)
    client.db_pool = db_pool._pool
    return client


def _get_trading_days(start_date: date, end_date: date) -> List[date]:
    """
    Get all trading days between start and end dates (backward order).
    Excludes weekends (Saturday=5, Sunday=6).
    
    Args:
        start_date: Start date
        end_date: End date
        
    Returns:
        List of dates in backward order (end to start)
    """
    trading_days = []
    current = end_date
    
    while current >= start_date:
        # Check if it's a weekday (Monday=0 to Friday=4)
        if current.weekday() < 5:
            trading_days.append(current)
        current = current - timedelta(days=1)
    
    return trading_days


async def _process_single_day(
    trading_date: date,
    filters_list: list,
    polygon_client: PolygonClient,
    enable_db_prefiltering: bool,
    request_filters: Any,
    cache_service: CacheService
) -> Dict[str, Any]:
    """
    Process screening for a single trading day.
    
    Returns:
        Dict with results for this day including symbols and qualifying dates
    """
    single_day_start_time = time.time()
    logger.info(f"[{trading_date}] Starting screening for date")
    
    # Always fetch all active symbols from the database
    if not hasattr(polygon_client, 'db_pool') or polygon_client.db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection not available for fetching all US stocks"
        )
    
    try:
        loader = OptimizedDataLoader(polygon_client.db_pool)
        symbols = await loader.get_all_active_symbols(
            start_date=trading_date,
            end_date=trading_date,
            symbol_types=['CS', 'ETF']  # Common stocks and ETFs
        )
        
        if not symbols:
            logger.info(f"[{trading_date}] No active symbols found for this date")
            return {
                'date': trading_date,
                'symbol_results': {},
                'total_qualifying': 0,
                'total_screened': 0,
                'execution_time_ms': (time.time() - single_day_start_time) * 1000
            }
        
        logger.info(f"[{trading_date}] Found {len(symbols)} active symbols")
    except Exception as e:
        logger.error(f"[{trading_date}] Error fetching symbols: {e}")
        raise
    
    # Calculate required lookback days for all filters
    max_lookback_days = max(f.get_required_lookback_days() for f in filters_list)
    
    # Calculate the actual data start date (screening start date - lookback period)
    # Add extra buffer days for weekends/holidays (50 day MA needs ~70 calendar days)
    data_start_date = trading_date - timedelta(days=max_lookback_days + 30)
    
    # Ensure we don't request data before what's available (we have data from 2025-01-02)
    min_available_date = date(2025, 1, 2)
    if data_start_date < min_available_date:
        data_start_date = min_available_date
        logger.warning(f"[{trading_date}] Adjusted data start date to {min_available_date} (earliest available)")
    
    logger.info(f"[{trading_date}] Data fetch period: {data_start_date} to {trading_date} (lookback: {max_lookback_days} days)")
    
    # Fetch data with optional pre-filtering
    if enable_db_prefiltering and hasattr(polygon_client, 'db_pool'):
        try:
            loader = OptimizedDataLoader(polygon_client.db_pool)
            # Create a temporary request for this specific date
            temp_request = SimpleScreenRequest(
                start_date=trading_date,
                end_date=trading_date,
                filters=request_filters,
                enable_db_prefiltering=enable_db_prefiltering
            )
            data_by_symbol = await loader.load_data_for_screening(
                symbols=symbols,
                start_date=data_start_date,
                end_date=trading_date,
                filters=request_filters,
                enable_prefiltering=True
            )
            db_prefiltered_count = len(symbols) - len(data_by_symbol)
            logger.info(f"[{trading_date}] Database pre-filtering eliminated {db_prefiltered_count} symbols")
        except Exception as e:
            logger.warning(f"[{trading_date}] Database pre-filtering failed, falling back to full load: {e}")
            data_by_symbol = await _fetch_all_data(
                polygon_client, symbols, data_start_date, trading_date
            )
    else:
        data_by_symbol = await _fetch_all_data(
            polygon_client, symbols, data_start_date, trading_date
        )
    
    # Apply filters to each symbol
    symbol_results = {}
    total_qualifying = 0
    
    for symbol, bars in data_by_symbol.items():
        if not bars:
            continue
        
        # Convert to StockData and then numpy array
        stock_data = StockData(symbol=symbol, bars=bars)
        np_data = stock_data.to_numpy()
        
        # Apply filters and collect all filter results
        filter_results = []
        passes_all = True
        
        for filter_obj in filters_list:
            try:
                filter_result = filter_obj.apply(np_data, symbol)
                # Check if any days qualify - if not, filter failed
                if filter_result.num_qualifying_days == 0:
                    passes_all = False
                    break
                filter_results.append(filter_result)
            except ValueError as e:
                # Skip stocks that don't have enough data
                logger.debug(f"[{trading_date}] Skipping {symbol}: {str(e)}")
                passes_all = False
                break
        
        # Only include in results if all filters pass
        if passes_all and filter_results:
            # Combine all filter results to get dates where ALL filters passed
            combined_result = filter_results[0]
            for fr in filter_results[1:]:
                combined_result = combined_result.combine_with(fr)
            
            # Get the qualifying dates where all filters passed
            qualifying_dates_array = combined_result.qualifying_dates
            
            # Check if the trading date is in the qualifying dates
            if trading_date in qualifying_dates_array:
                total_qualifying += 1
                
                # Get metrics for this symbol on this date
                last_bar = bars[-1] if bars else None
                metrics = {
                    'latest_price': float(last_bar['close']) if last_bar else 0.0,
                    'latest_volume': last_bar['volume'] if last_bar else 0,
                    'open_price': float(last_bar['open']) if last_bar else 0.0
                }
                metrics.update(combined_result.metrics)
                
                symbol_results[symbol] = {
                    'qualifying_date': str(trading_date),
                    'metrics': metrics
                }
    
    logger.info(f"[{trading_date}] Found {total_qualifying} qualifying symbols")
    
    # Save results to database if any symbols qualified
    if symbol_results:
        try:
            # Create cache request model based on enabled filters
            cache_request = CachedScreenerRequest(
                start_date=trading_date,
                end_date=trading_date,
                # Extract filter parameters
                min_price=request_filters.price_range.min_price if request_filters.price_range else None,
                max_price=request_filters.price_range.max_price if request_filters.price_range else None,
                price_vs_ma_enabled=request_filters.price_vs_ma is not None,
                price_vs_ma_period=request_filters.price_vs_ma.ma_period if request_filters.price_vs_ma else None,
                price_vs_ma_condition=request_filters.price_vs_ma.condition if request_filters.price_vs_ma else None,
                rsi_enabled=request_filters.rsi is not None,
                rsi_period=request_filters.rsi.rsi_period if request_filters.rsi else None,
                rsi_threshold=request_filters.rsi.threshold if request_filters.rsi else None,
                rsi_condition=request_filters.rsi.condition if request_filters.rsi else None,
                gap_enabled=request_filters.gap is not None,
                gap_threshold=request_filters.gap.gap_threshold if request_filters.gap else None,
                gap_direction=request_filters.gap.direction if request_filters.gap else None,
                prev_day_dollar_volume_enabled=request_filters.prev_day_dollar_volume is not None,
                prev_day_dollar_volume=request_filters.prev_day_dollar_volume.min_dollar_volume if request_filters.prev_day_dollar_volume else None,
                relative_volume_enabled=request_filters.relative_volume is not None,
                relative_volume_recent_days=request_filters.relative_volume.recent_days if request_filters.relative_volume else None,
                relative_volume_lookback_days=request_filters.relative_volume.lookback_days if request_filters.relative_volume else None,
                relative_volume_min_ratio=request_filters.relative_volume.min_ratio if request_filters.relative_volume else None
            )
            
            # Create cache results for each symbol
            cache_results = []
            for symbol, data in symbol_results.items():
                cache_result = CachedScreenerResult(
                    symbol=symbol,
                    company_name=None,
                    data_date=trading_date,
                    # Copy filter parameters from request
                    filter_min_price=request_filters.price_range.min_price if request_filters.price_range else None,
                    filter_max_price=request_filters.price_range.max_price if request_filters.price_range else None,
                    filter_price_vs_ma_enabled=request_filters.price_vs_ma is not None,
                    filter_price_vs_ma_period=request_filters.price_vs_ma.ma_period if request_filters.price_vs_ma else None,
                    filter_price_vs_ma_condition=request_filters.price_vs_ma.condition if request_filters.price_vs_ma else None,
                    filter_rsi_enabled=request_filters.rsi is not None,
                    filter_rsi_period=request_filters.rsi.rsi_period if request_filters.rsi else None,
                    filter_rsi_threshold=request_filters.rsi.threshold if request_filters.rsi else None,
                    filter_rsi_condition=request_filters.rsi.condition if request_filters.rsi else None,
                    filter_gap_enabled=request_filters.gap is not None,
                    filter_gap_threshold=request_filters.gap.gap_threshold if request_filters.gap else None,
                    filter_gap_direction=request_filters.gap.direction if request_filters.gap else None,
                    filter_prev_day_dollar_volume_enabled=request_filters.prev_day_dollar_volume is not None,
                    filter_prev_day_dollar_volume=request_filters.prev_day_dollar_volume.min_dollar_volume if request_filters.prev_day_dollar_volume else None,
                    filter_relative_volume_enabled=request_filters.relative_volume is not None,
                    filter_relative_volume_recent_days=request_filters.relative_volume.recent_days if request_filters.relative_volume else None,
                    filter_relative_volume_lookback_days=request_filters.relative_volume.lookback_days if request_filters.relative_volume else None,
                    filter_relative_volume_min_ratio=request_filters.relative_volume.min_ratio if request_filters.relative_volume else None
                )
                cache_results.append(cache_result)
            
            # Save to database
            success = await cache_service.save_screener_results(cache_request, cache_results)
            if success:
                logger.info(f"[{trading_date}] Saved {len(cache_results)} results to database")
            else:
                logger.warning(f"[{trading_date}] Failed to save results to database")
            
            # Also save to file for backward compatibility
            metadata = {
                "screening_date": str(trading_date),
                "total_symbols_screened": len(data_by_symbol),
                "total_qualifying_stocks": total_qualifying,
                "execution_time_ms": (time.time() - single_day_start_time) * 1000
            }
            
            results_file = screener_results_manager.save_results(
                symbols=list(symbol_results.keys()),
                filters=request_filters.model_dump() if hasattr(request_filters, 'model_dump') else {},
                metadata=metadata
            )
            logger.info(f"[{trading_date}] Saved results to {results_file}")
            
        except Exception as e:
            logger.error(f"[{trading_date}] Failed to save results: {e}")
    
    return {
        'date': trading_date,
        'symbol_results': symbol_results,
        'total_qualifying': total_qualifying,
        'total_screened': len(data_by_symbol),
        'execution_time_ms': (time.time() - single_day_start_time) * 1000
    }


async def _fetch_all_data(
    polygon_client: PolygonClient,
    symbols: List[str],
    start_date: date,
    end_date: date
) -> dict:
    """Fetch data for all symbols from Polygon."""
    data_by_symbol = {}
    
    for symbol in symbols:
        try:
            bars = await polygon_client.get_daily_bars(
                symbol=symbol,
                start_date=start_date,
                end_date=end_date
            )
            if bars:
                data_by_symbol[symbol] = bars
        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
    
    return data_by_symbol


@router.post("/screen", response_model=SimpleScreenResponse)
async def simple_screen_stocks(
    request: SimpleScreenRequest,
    polygon_client: PolygonClient = Depends(get_polygon_client)
) -> SimpleScreenResponse:
    """
    Screen stocks using simplified filters with day-by-day processing.
    
    This endpoint processes each trading day individually (backward from end to start),
    saves results to the database for each day, and returns aggregated results.
    
    This matches the behavior of the pipeline script for consistency.
    
    Uses 8 basic, efficient filters:
    1. **Price Range**: Filter by OPEN price within min/max range
    2. **Price vs MA**: Filter by OPEN price above/below moving average
    3. **RSI**: Filter by RSI above/below threshold
    4. **Min Average Volume**: Filter by minimum average trading volume in shares
    5. **Min Average Dollar Volume**: Filter by minimum average dollar volume (price * volume)
    6. **Gap**: Filter by gap between today's open and yesterday's close
    7. **Previous Day Dollar Volume**: Filter by yesterday's dollar volume only
    8. **Relative Volume**: Filter by ratio of recent to historical volume
    
    All filters use vectorized NumPy operations for maximum performance.
    """
    start_time = time.time()
    
    # Build filters once
    filters = []
    
    if request.filters.price_range:
        filters.append(SimplePriceRangeFilter(
            min_price=request.filters.price_range.min_price,
            max_price=request.filters.price_range.max_price
        ))
    
    if request.filters.price_vs_ma:
        filters.append(PriceVsMAFilter(
            period=request.filters.price_vs_ma.ma_period,
            condition=request.filters.price_vs_ma.condition
        ))
    
    if request.filters.rsi:
        filters.append(RSIFilter(
            period=request.filters.rsi.rsi_period,
            condition=request.filters.rsi.condition,
            threshold=request.filters.rsi.threshold
        ))
    
    if request.filters.min_avg_volume:
        filters.append(MinAverageVolumeFilter(
            lookback_days=request.filters.min_avg_volume.lookback_days,
            min_avg_volume=request.filters.min_avg_volume.min_avg_volume
        ))
    
    if request.filters.min_avg_dollar_volume:
        filters.append(MinAverageDollarVolumeFilter(
            lookback_days=request.filters.min_avg_dollar_volume.lookback_days,
            min_avg_dollar_volume=request.filters.min_avg_dollar_volume.min_avg_dollar_volume
        ))
    
    if request.filters.gap:
        filters.append(GapFilter(
            gap_threshold=request.filters.gap.gap_threshold,
            direction=request.filters.gap.direction
        ))
    
    if request.filters.prev_day_dollar_volume:
        filters.append(PreviousDayDollarVolumeFilter(
            min_dollar_volume=request.filters.prev_day_dollar_volume.min_dollar_volume
        ))
    
    if request.filters.relative_volume:
        filters.append(RelativeVolumeFilter(
            recent_days=request.filters.relative_volume.recent_days,
            lookback_days=request.filters.relative_volume.lookback_days,
            min_ratio=request.filters.relative_volume.min_ratio
        ))
    
    if not filters:
        raise HTTPException(
            status_code=400,
            detail="At least one filter must be specified"
        )
    
    # Initialize cache service
    cache_service = CacheService(
        screener_ttl_hours=24,
        backtest_ttl_days=7
    )
    
    # Get all trading days to process (in backward order)
    trading_days = _get_trading_days(request.start_date, request.end_date)
    logger.info(f"Processing {len(trading_days)} trading days from {request.end_date} to {request.start_date}")
    
    # Check if single day or multiple days
    if len(trading_days) == 1:
        # Single day - use original logic for better performance
        logger.info("Single day request - using optimized single-day processing")
        day_result = await _process_single_day(
            trading_date=trading_days[0],
            filters_list=filters,
            polygon_client=polygon_client,
            enable_db_prefiltering=request.enable_db_prefiltering,
            request_filters=request.filters,
            cache_service=cache_service
        )
        
        # Convert to response format
        results = []
        for symbol, data in day_result['symbol_results'].items():
            result = SimpleScreenResult(
                symbol=symbol,
                qualifying_dates=[data['qualifying_date']],
                total_days_analyzed=1,
                qualifying_days_count=1,
                metrics=data['metrics']
            )
            results.append(result)
        
        return SimpleScreenResponse(
            request=request,
            execution_time_ms=day_result['execution_time_ms'],
            total_symbols_screened=day_result['total_screened'],
            total_qualifying_stocks=day_result['total_qualifying'],
            results=results,
            db_prefiltering_used=request.enable_db_prefiltering,
            symbols_filtered_by_db=0
        )
    
    # Multiple days - process each day individually
    all_symbol_data = {}  # symbol -> {dates: [], metrics: {}}
    total_symbols_screened_max = 0
    
    for i, trading_date in enumerate(trading_days, 1):
        logger.info(f"Processing day {i}/{len(trading_days)}: {trading_date}")
        
        day_result = await _process_single_day(
            trading_date=trading_date,
            filters_list=filters,
            polygon_client=polygon_client,
            enable_db_prefiltering=request.enable_db_prefiltering,
            request_filters=request.filters,
            cache_service=cache_service
        )
        
        # Aggregate results
        for symbol, data in day_result['symbol_results'].items():
            if symbol not in all_symbol_data:
                all_symbol_data[symbol] = {
                    'dates': [],
                    'metrics': data['metrics']  # Use metrics from first qualifying day
                }
            all_symbol_data[symbol]['dates'].append(data['qualifying_date'])
        
        total_symbols_screened_max = max(total_symbols_screened_max, day_result['total_screened'])
    
    # Convert aggregated results to SimpleScreenResult objects
    results = []
    for symbol, data in all_symbol_data.items():
        result = SimpleScreenResult(
            symbol=symbol,
            qualifying_dates=sorted(data['dates']),
            total_days_analyzed=len(trading_days),
            qualifying_days_count=len(data['dates']),
            metrics=data['metrics']
        )
        results.append(result)
    
    # Sort results by number of qualifying days (descending)
    results.sort(key=lambda r: r.qualifying_days_count, reverse=True)
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    logger.info(f"Total processing time: {execution_time_ms:.2f}ms")
    logger.info(f"Total unique symbols found: {len(results)}")
    logger.info(f"Total trading days processed: {len(trading_days)}")
    
    return SimpleScreenResponse(
        request=request,
        execution_time_ms=execution_time_ms,
        total_symbols_screened=total_symbols_screened_max,
        total_qualifying_stocks=len(results),
        results=results,
        db_prefiltering_used=request.enable_db_prefiltering,
        symbols_filtered_by_db=0
    )


@router.get("/filters/info")
async def get_filter_info():
    """
    Get information about available filters and their parameters.
    
    Returns detailed information about each of the filters,
    including parameter ranges and common usage patterns.
    """
    return {
        "filters": {
            "price_range": {
                "description": "Filter stocks by OPEN price within a specified range",
                "parameters": {
                    "min_price": {"type": "float", "min": 0, "default": 1.0},
                    "max_price": {"type": "float", "min": 0, "default": 100.0}
                },
                "efficiency": "Very High - Simple comparison operation",
                "db_prefilter": True,
                "common_usage": {
                    "penny_stocks": {"min_price": 0.01, "max_price": 5.0},
                    "mid_range": {"min_price": 10.0, "max_price": 50.0},
                    "high_priced": {"min_price": 100.0, "max_price": 1000.0}
                }
            },
            "price_vs_ma": {
                "description": "Filter stocks where OPEN price is above/below moving average",
                "parameters": {
                    "ma_period": {
                        "type": "int",
                        "options": [20, 50, 200],
                        "default": 20,
                        "description": "Number of days for MA calculation"
                    },
                    "condition": {
                        "type": "string",
                        "options": ["above", "below"],
                        "default": "above"
                    }
                },
                "efficiency": "High - Vectorized MA calculation",
                "db_prefilter": False,
                "common_usage": {
                    "bullish_20ma": {"ma_period": 20, "condition": "above"},
                    "bearish_50ma": {"ma_period": 50, "condition": "below"},
                    "long_term_trend": {"ma_period": 200, "condition": "above"}
                }
            },
            "rsi": {
                "description": "Filter stocks by RSI (Relative Strength Index) conditions",
                "parameters": {
                    "rsi_period": {
                        "type": "int",
                        "min": 2,
                        "max": 50,
                        "default": 14
                    },
                    "condition": {
                        "type": "string",
                        "options": ["above", "below"],
                        "default": "below"
                    },
                    "threshold": {
                        "type": "float",
                        "min": 0,
                        "max": 100,
                        "default": 30,
                        "description": "RSI threshold value"
                    }
                },
                "efficiency": "Medium - Requires iterative calculation",
                "db_prefilter": False,
                "common_usage": {
                    "oversold": {"rsi_period": 14, "condition": "below", "threshold": 30},
                    "overbought": {"rsi_period": 14, "condition": "above", "threshold": 70},
                    "extreme_oversold": {"rsi_period": 14, "condition": "below", "threshold": 20}
                }
            },
            "gap": {
                "description": "Filter stocks by gap between today's open and yesterday's close",
                "parameters": {
                    "gap_threshold": {
                        "type": "float",
                        "min": 0,
                        "max": 50,
                        "default": 2.0,
                        "description": "Minimum gap percentage to qualify"
                    },
                    "direction": {
                        "type": "string",
                        "options": ["up", "down", "both"],
                        "default": "both",
                        "description": "Gap direction filter"
                    }
                },
                "efficiency": "Very High - Simple comparison between consecutive days",
                "db_prefilter": False,
                "common_usage": {
                    "gap_up": {"gap_threshold": 2.0, "direction": "up"},
                    "gap_down": {"gap_threshold": 2.0, "direction": "down"},
                    "large_gaps": {"gap_threshold": 5.0, "direction": "both"}
                }
            },
            "prev_day_dollar_volume": {
                "description": "Filter stocks by previous day's dollar volume only",
                "parameters": {
                    "min_dollar_volume": {
                        "type": "float",
                        "min": 0,
                        "default": 10000000,
                        "description": "Minimum dollar volume for previous trading day"
                    }
                },
                "efficiency": "High - Simple calculation on previous day data",
                "db_prefilter": False,
                "common_usage": {
                    "liquid_yesterday": {"min_dollar_volume": 10000000},
                    "very_liquid_yesterday": {"min_dollar_volume": 50000000},
                    "institutional_yesterday": {"min_dollar_volume": 100000000}
                }
            },
            "relative_volume": {
                "description": "Filter stocks by relative volume ratio (recent avg / historical avg)",
                "parameters": {
                    "recent_days": {
                        "type": "int",
                        "min": 1,
                        "max": 10,
                        "default": 2,
                        "description": "Number of recent days for volume average"
                    },
                    "lookback_days": {
                        "type": "int",
                        "min": 5,
                        "max": 200,
                        "default": 20,
                        "description": "Number of historical days for volume average"
                    },
                    "min_ratio": {
                        "type": "float",
                        "min": 0.1,
                        "max": 10,
                        "default": 1.5,
                        "description": "Minimum ratio to qualify (1.5 = 50% higher)"
                    }
                },
                "efficiency": "Medium - Requires moving average calculations",
                "db_prefilter": False,
                "common_usage": {
                    "high_rel_volume": {"recent_days": 2, "lookback_days": 20, "min_ratio": 1.5},
                    "very_high_rel_volume": {"recent_days": 2, "lookback_days": 20, "min_ratio": 2.0},
                    "extreme_rel_volume": {"recent_days": 3, "lookback_days": 30, "min_ratio": 3.0}
                }
            }
        },
        "performance_tips": [
            "Price range and gap filters are the most efficient - use them to reduce dataset size",
            "Volume and dollar volume filters support database pre-filtering for better performance",
            "Combine filters for more specific results, but each additional filter reduces performance",
            "Enable database pre-filtering for large symbol lists",
            "When screening multiple days, results are processed day-by-day and saved to the database",
            "Single-day requests are optimized for better performance",
            "RSI calculation is the most computationally intensive of all filters"
        ]
    }


@router.get("/examples")
async def get_example_requests():
    """Get example screening requests for common strategies."""
    examples = [
        {
            "name": "Oversold Value Stocks",
            "description": "Find mid-priced stocks that are oversold",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-05",
                "filters": {
                    "price_range": {"min_price": 10, "max_price": 50},
                    "rsi": {"rsi_period": 14, "condition": "below", "threshold": 30}
                }
            }
        },
        {
            "name": "Momentum Above MA",
            "description": "Find stocks trading above their 50-day MA",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-05",
                "filters": {
                    "price_range": {"min_price": 5, "max_price": 100},
                    "price_vs_ma": {"ma_period": 50, "condition": "above"}
                }
            }
        },
        {
            "name": "Day Trading Candidates",
            "description": "Low-priced stocks with high volatility potential",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-05",
                "filters": {
                    "price_range": {"min_price": 2, "max_price": 20},
                    "price_vs_ma": {"ma_period": 20, "condition": "above"},
                    "rsi": {"rsi_period": 14, "condition": "above", "threshold": 50}
                }
            }
        },
        {
            "name": "Gap Trading Opportunities",
            "description": "Liquid stocks with significant gap movements",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-05",
                "filters": {
                    "gap": {"gap_threshold": 3.0, "direction": "both"},
                    "prev_day_dollar_volume": {"min_dollar_volume": 20000000}
                }
            }
        },
        {
            "name": "High Relative Volume",
            "description": "Stocks with unusual volume activity",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-05",
                "filters": {
                    "relative_volume": {"recent_days": 2, "lookback_days": 20, "min_ratio": 2.0},
                    "prev_day_dollar_volume": {"min_dollar_volume": 50000000}
                }
            }
        }
    ]
    
    return {"examples": examples}