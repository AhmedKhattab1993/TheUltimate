"""
Simplified screener API endpoint with just 3 basic filters.

This endpoint provides a streamlined interface for stock screening using:
1. Price Range Filter (OPEN price)
2. Price vs Moving Average Filter
3. RSI Filter
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List, Optional
import numpy as np
import time
import logging
from datetime import datetime, timedelta
from datetime import date

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


@router.post("/screen", response_model=SimpleScreenResponse)
async def simple_screen_stocks(
    request: SimpleScreenRequest,
    polygon_client: PolygonClient = Depends(get_polygon_client)
) -> SimpleScreenResponse:
    """
    Screen stocks using simplified filters.
    
    This endpoint uses 8 basic, efficient filters:
    1. **Price Range**: Filter by OPEN price within min/max range
    2. **Price vs MA**: Filter by OPEN price above/below moving average
    3. **RSI**: Filter by RSI above/below threshold
    4. **Min Average Volume**: Filter by minimum average trading volume in shares
    5. **Min Average Dollar Volume**: Filter by minimum average dollar volume (price * volume)
    6. **Gap**: Filter by gap between today's open and yesterday's close
    7. **Previous Day Dollar Volume**: Filter by yesterday's dollar volume only
    8. **Relative Volume**: Filter by ratio of recent to historical volume
    
    All filters use vectorized NumPy operations for maximum performance.
    Database pre-filtering is applied where possible.
    """
    start_time = time.time()
    
    # Always fetch all active symbols from the database
    if not hasattr(polygon_client, 'db_pool') or polygon_client.db_pool is None:
        raise HTTPException(
            status_code=503,
            detail="Database connection not available for fetching all US stocks"
        )
    
    try:
        loader = OptimizedDataLoader(polygon_client.db_pool)
        symbols = await loader.get_all_active_symbols(
            start_date=request.start_date,
            end_date=request.end_date,
            symbol_types=['CS', 'ETF']  # Common stocks and ETFs
        )
        
        if not symbols:
            raise HTTPException(
                status_code=404,
                detail=f"No active symbols found with data between {request.start_date} and {request.end_date}"
            )
        
        logger.info(f"Screening all US stocks: {len(symbols)} symbols found")
    except Exception as e:
        logger.error(f"Error fetching all US stocks: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch all US stocks: {str(e)}"
        )
    
    # Build filters
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
    
    # Calculate required lookback days for all filters
    max_lookback_days = max(f.get_required_lookback_days() for f in filters)
    
    # Calculate the actual data start date (screening start date - lookback period)
    # Add extra buffer days for weekends/holidays (50 day MA needs ~70 calendar days)
    data_start_date = request.start_date - timedelta(days=max_lookback_days + 30)
    
    # Ensure we don't request data before what's available (we have data from 2025-01-02)
    min_available_date = date(2025, 1, 2)
    if data_start_date < min_available_date:
        data_start_date = min_available_date
        logger.warning(f"Adjusted data start date to {min_available_date} (earliest available)")
    
    logger.info(f"Screening period: {request.start_date} to {request.end_date}")
    logger.info(f"Data fetch period: {data_start_date} to {request.end_date} (lookback: {max_lookback_days} days)")
    
    # We'll apply filters individually instead of using composite
    
    # Fetch data with optional pre-filtering
    db_prefiltered_count = 0
    
    if request.enable_db_prefiltering and hasattr(polygon_client, 'db_pool'):
        # Use database pre-filtering if available
        try:
            loader = OptimizedDataLoader(polygon_client.db_pool)
            data_by_symbol = await loader.load_data_for_screening(
                symbols=symbols,
                start_date=data_start_date,  # Use extended date range for lookback
                end_date=request.end_date,
                filters=request.filters,
                enable_prefiltering=True
            )
            db_prefiltered_count = len(symbols) - len(data_by_symbol)
            logger.info(f"Database pre-filtering eliminated {db_prefiltered_count} symbols")
        except Exception as e:
            logger.warning(f"Database pre-filtering failed, falling back to full load: {e}")
            # Fall back to standard loading
            data_by_symbol = await _fetch_all_data(
                polygon_client, symbols, data_start_date, request.end_date
            )
    else:
        # Standard data loading without pre-filtering
        data_by_symbol = await _fetch_all_data(
            polygon_client, symbols, data_start_date, request.end_date
        )
    
    # Apply filters to each symbol
    results = []
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
        
        for filter_obj in filters:
            try:
                filter_result = filter_obj.apply(np_data, symbol)
                # Check if any days qualify - if not, filter failed
                if filter_result.num_qualifying_days == 0:
                    passes_all = False
                    break
                filter_results.append(filter_result)
            except ValueError as e:
                # Skip stocks that don't have enough data
                logger.debug(f"Skipping {symbol}: {str(e)}")
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
            
            # Filter to only include dates within the requested screening period
            screening_dates = []
            for qual_date in qualifying_dates_array:
                if request.start_date <= qual_date <= request.end_date:
                    screening_dates.append(qual_date)
            
            # Only include if there are qualifying dates in the screening period
            if not screening_dates:
                continue
                
            total_qualifying += 1
            
            # Convert to strings and deduplicate (in case of duplicates)
            qualifying_dates_str = sorted(list(set(str(d) for d in screening_dates)))
            
            # Get basic metrics from the last bar
            last_bar = bars[-1] if bars else None
            
            # Also get metrics from the combined filter result
            combined_metrics = {
                'latest_price': float(last_bar['close']) if last_bar else 0.0,
                'latest_volume': last_bar['volume'] if last_bar else 0,
                'open_price': float(last_bar['open']) if last_bar else 0.0
            }
            # Add any metrics from filters (like RSI, price_vs_ma)
            combined_metrics.update(combined_result.metrics)
            
            result = SimpleScreenResult(
                symbol=symbol,
                qualifying_dates=qualifying_dates_str,
                total_days_analyzed=len(bars),
                qualifying_days_count=len(qualifying_dates_str),
                metrics=combined_metrics
            )
            results.append(result)
    
    # Sort results by number of qualifying days (descending)
    results.sort(key=lambda r: r.qualifying_days_count, reverse=True)
    
    execution_time_ms = (time.time() - start_time) * 1000
    
    # Save screener results to file for backtest access
    if results:
        try:
            symbols = [r.symbol for r in results]
            filters_dict = request.dict()
            metadata = {
                "total_symbols_screened": len(data_by_symbol),
                "total_qualifying_stocks": total_qualifying,
                "execution_time_ms": execution_time_ms,
                "db_prefiltering_used": db_prefiltered_count > 0
            }
            
            results_file = screener_results_manager.save_results(
                symbols=symbols,
                filters=filters_dict,
                metadata=metadata
            )
            logger.info(f"Saved screener results to {results_file}")
        except Exception as e:
            logger.error(f"Failed to save screener results: {e}")
            # Don't fail the request if saving fails
    
    return SimpleScreenResponse(
        request=request,
        execution_time_ms=execution_time_ms,
        total_symbols_screened=len(data_by_symbol),
        total_qualifying_stocks=total_qualifying,
        results=results,
        db_prefiltering_used=db_prefiltered_count > 0,
        symbols_filtered_by_db=db_prefiltered_count
    )


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


@router.get("/filters/info")
async def get_filter_info():
    """
    Get information about available filters and their parameters.
    
    Returns detailed information about each of the 6 simple filters,
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
            "min_avg_volume": {
                "description": "Filter stocks by minimum average trading volume in shares",
                "parameters": {
                    "lookback_days": {
                        "type": "int",
                        "min": 1,
                        "max": 200,
                        "default": 20,
                        "description": "Number of days to calculate average volume"
                    },
                    "min_avg_volume": {
                        "type": "float",
                        "min": 0,
                        "default": 1000000,
                        "description": "Minimum average volume in shares"
                    }
                },
                "efficiency": "High - Simple moving average calculation",
                "db_prefilter": True,
                "common_usage": {
                    "liquid_stocks": {"lookback_days": 20, "min_avg_volume": 1000000},
                    "very_liquid": {"lookback_days": 20, "min_avg_volume": 5000000},
                    "institutional": {"lookback_days": 50, "min_avg_volume": 10000000}
                }
            },
            "min_avg_dollar_volume": {
                "description": "Filter stocks by minimum average dollar volume (price * volume)",
                "parameters": {
                    "lookback_days": {
                        "type": "int",
                        "min": 1,
                        "max": 200,
                        "default": 20,
                        "description": "Number of days to calculate average dollar volume"
                    },
                    "min_avg_dollar_volume": {
                        "type": "float",
                        "min": 0,
                        "default": 10000000,
                        "description": "Minimum average dollar volume"
                    }
                },
                "efficiency": "High - Simple calculation with price * volume",
                "db_prefilter": True,
                "common_usage": {
                    "day_trading": {"lookback_days": 20, "min_avg_dollar_volume": 10000000},
                    "swing_trading": {"lookback_days": 20, "min_avg_dollar_volume": 5000000},
                    "institutional": {"lookback_days": 50, "min_avg_dollar_volume": 50000000}
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
            "Limit date ranges to improve performance",
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
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
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
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
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
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
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
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "filters": {
                    "gap": {"gap_threshold": 3.0, "direction": "both"},
                    "min_avg_dollar_volume": {"lookback_days": 20, "min_avg_dollar_volume": 20000000}
                }
            }
        },
        {
            "name": "High Relative Volume",
            "description": "Stocks with unusual volume activity",
            "request": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "filters": {
                    "relative_volume": {"recent_days": 2, "lookback_days": 20, "min_ratio": 2.0},
                    "prev_day_dollar_volume": {"min_dollar_volume": 50000000}
                }
            }
        }
    ]
    
    return {"examples": examples}