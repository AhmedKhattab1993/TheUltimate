"""
Stock screener API endpoints.

This module provides REST API endpoints for stock screening functionality.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models.requests import (
    ScreenRequest, 
    ScreenResponse, 
    ScreenResult,
    PerformanceMetrics,
    VolumeFilterParams,
    PriceChangeFilterParams,
    MovingAverageFilterParams,
    ComparisonOperator,
    GapFilterParams,
    PriceRangeFilterParams,
    FloatFilterParams,
    RelativeVolumeFilterParams,
    MarketCapFilterParams,
)
from app.core.filters import (
    BaseFilter,
    VolumeFilter,
    PriceChangeFilter,
    MovingAverageFilter
)
from app.core.day_trading_filters import (
    GapFilter,
    PriceRangeFilter,
    RelativeVolumeFilter,
    FloatFilter,
    MarketCapFilter
)
from app.services.screener import ScreenerEngine
from app.services.polygon_client import PolygonClient, PolygonAPIError
from app.services.ticker_discovery import TickerDiscoveryService
from app.config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


def get_polygon_client(request: Request) -> PolygonClient:
    """Get Polygon client from app state."""
    return request.app.state.polygon_client


@router.post("/cache/clear", response_model=Dict[str, str])
async def clear_cache(polygon_client: PolygonClient = Depends(get_polygon_client)):
    """
    Clear the in-memory cache.
    
    This endpoint can be used to manually clear the cache when needed.
    """
    polygon_client.clear_cache()
    return {"status": "success", "message": "Cache cleared successfully"}


@router.get("/health", response_model=Dict[str, Any])
async def health_check(polygon_client: PolygonClient = Depends(get_polygon_client)):
    """
    Health check endpoint.
    
    Verifies that the API is running and can connect to external services.
    """
    start_time = time.time()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check Polygon API connectivity
    try:
        market_status = await polygon_client.check_market_status()
        health_status["checks"]["polygon_api"] = {
            "status": "healthy",
            "market_status": market_status.get("market", "unknown")
        }
    except PolygonAPIError as e:
        health_status["status"] = "degraded"
        health_status["checks"]["polygon_api"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["polygon_api"] = {
            "status": "unhealthy",
            "error": f"Unexpected error: {str(e)}"
        }
    
    # Add response time
    health_status["response_time_ms"] = (time.time() - start_time) * 1000
    
    return health_status


@router.get("/symbols", response_model=List[str])
async def get_available_symbols():
    """
    Get list of available symbols for screening.
    
    Returns the default symbol universe configured in settings.
    """
    return settings.default_symbols


@router.get("/symbols/us-stocks", response_model=List[str])
async def get_all_us_stocks(polygon_client: PolygonClient = Depends(get_polygon_client)):
    """
    Get list of all US common stocks available for screening.
    
    This endpoint fetches all active US common stocks from Polygon API.
    Note: This may take a few seconds as it needs to paginate through all results.
    
    Returns:
        List of ticker symbols for all US common stocks
    """
    try:
        ticker_discovery = TickerDiscoveryService(polygon_client)
        symbols = await ticker_discovery.fetch_all_us_common_stocks()
        return symbols
    except PolygonAPIError as e:
        logger.error(f"Failed to fetch US stocks: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to fetch US stocks: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error fetching US stocks: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.get("/filters", response_model=Dict[str, Any])
async def get_available_filters():
    """
    Get available filters with their parameters and descriptions.
    
    Returns detailed information about each filter type and its configuration options.
    """
    return {
        "volume": {
            "description": "Filter stocks based on average trading volume",
            "parameters": {
                "min_average": {
                    "type": "float",
                    "required": False,
                    "description": "Minimum average volume",
                    "minimum": 0
                },
                "max_average": {
                    "type": "float",
                    "required": False,
                    "description": "Maximum average volume",
                    "minimum": 0
                },
                "lookback_days": {
                    "type": "integer",
                    "required": False,
                    "default": 20,
                    "description": "Number of days to calculate average",
                    "minimum": 1,
                    "maximum": 252
                }
            }
        },
        "price_change": {
            "description": "Filter stocks based on price change percentage",
            "parameters": {
                "min_change": {
                    "type": "float",
                    "required": False,
                    "description": "Minimum price change percentage"
                },
                "max_change": {
                    "type": "float",
                    "required": False,
                    "description": "Maximum price change percentage"
                },
                "period_days": {
                    "type": "integer",
                    "required": False,
                    "default": 1,
                    "description": "Period for calculating change",
                    "minimum": 1,
                    "maximum": 252
                }
            }
        },
        "moving_average": {
            "description": "Filter stocks based on price position relative to moving average",
            "parameters": {
                "period": {
                    "type": "integer",
                    "required": False,
                    "default": 50,
                    "description": "Moving average period in days",
                    "minimum": 2,
                    "maximum": 200
                },
                "condition": {
                    "type": "string",
                    "required": False,
                    "default": "above",
                    "description": "Price condition relative to MA",
                    "enum": ["above", "below", "crosses_above", "crosses_below"]
                }
            }
        },
        "gap": {
            "description": "Filter stocks based on gap percentage from previous day's close",
            "parameters": {
                "min_gap_percent": {
                    "type": "float",
                    "required": False,
                    "default": 4.0,
                    "description": "Minimum gap percentage from previous close",
                    "minimum": 0
                },
                "max_gap_percent": {
                    "type": "float",
                    "required": False,
                    "description": "Maximum gap percentage from previous close",
                    "minimum": 0
                }
            }
        },
        "price_range": {
            "description": "Filter stocks within a specific price range",
            "parameters": {
                "min_price": {
                    "type": "float",
                    "required": False,
                    "default": 2.0,
                    "description": "Minimum stock price",
                    "minimum": 0
                },
                "max_price": {
                    "type": "float",
                    "required": False,
                    "default": 10.0,
                    "description": "Maximum stock price",
                    "minimum": 0
                }
            }
        },
        "float": {
            "description": "Filter stocks based on share float (shares available for trading)",
            "parameters": {
                "max_float": {
                    "type": "float",
                    "required": False,
                    "default": 100000000,
                    "description": "Maximum share float",
                    "minimum": 0
                },
                "preferred_max_float": {
                    "type": "float",
                    "required": False,
                    "default": 20000000,
                    "description": "Preferred maximum float for ideal setups",
                    "minimum": 0
                }
            }
        },
        "relative_volume": {
            "description": "Filter stocks based on relative volume compared to average",
            "parameters": {
                "min_relative_volume": {
                    "type": "float",
                    "required": False,
                    "default": 2.0,
                    "description": "Minimum relative volume vs average",
                    "minimum": 1.0
                },
                "lookback_days": {
                    "type": "integer",
                    "required": False,
                    "default": 20,
                    "description": "Days to calculate average volume",
                    "minimum": 5,
                    "maximum": 60
                }
            }
        },
        "premarket_volume": {
            "description": "Filter stocks based on pre-market trading volume",
            "parameters": {
                "min_volume": {
                    "type": "integer",
                    "required": False,
                    "default": 100000,
                    "description": "Minimum pre-market volume",
                    "minimum": 0
                },
                "cutoff_time": {
                    "type": "string",
                    "required": False,
                    "default": "09:00",
                    "description": "Time cutoff for pre-market volume (EST)"
                }
            }
        },
        "market_cap": {
            "description": "Filter stocks based on market capitalization",
            "parameters": {
                "max_market_cap": {
                    "type": "float",
                    "required": False,
                    "default": 300000000,
                    "description": "Maximum market capitalization",
                    "minimum": 0
                },
                "min_market_cap": {
                    "type": "float",
                    "required": False,
                    "description": "Minimum market capitalization",
                    "minimum": 0
                }
            }
        },
        "news_catalyst": {
            "description": "Filter stocks based on recent news catalyst",
            "parameters": {
                "hours_lookback": {
                    "type": "integer",
                    "required": False,
                    "default": 24,
                    "description": "Hours to look back for news",
                    "minimum": 1,
                    "maximum": 72
                },
                "require_news": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Require news catalyst for qualification"
                }
            }
        }
    }


@router.post("/screen", response_model=ScreenResponse)
async def screen_stocks(
    request: ScreenRequest,
    polygon_client: PolygonClient = Depends(get_polygon_client)
):
    """
    Main screening endpoint.
    
    Screens stocks based on the provided filters and date range.
    
    Parameters:
    - **start_date**: Start date for historical data (YYYY-MM-DD)
    - **end_date**: End date for historical data (YYYY-MM-DD)
    - **symbols**: Optional list of symbols to screen (defaults to preset universe)
    - **use_all_us_stocks**: If true, screens all US common stocks (ignores symbols parameter)
    - **filters**: Filter configuration object with volume, price_change, and/or moving_average filters
    
    Returns:
    - List of qualifying stocks with their metrics
    - Execution time and summary statistics
    """
    start_time = time.time()
    
    # Determine which symbols to screen
    symbols_to_screen = []
    
    if request.use_all_us_stocks:
        # Fetch all US common stocks
        logger.info("Fetching all US common stocks for screening...")
        ticker_discovery = TickerDiscoveryService(polygon_client)
        try:
            symbols_to_screen = await ticker_discovery.fetch_all_us_common_stocks()
            logger.info(f"Found {len(symbols_to_screen)} US common stocks")
        except PolygonAPIError as e:
            logger.error(f"Failed to fetch US stock universe: {e}")
            raise HTTPException(
                status_code=503,
                detail=f"Failed to fetch stock universe: {str(e)}"
            )
    elif request.symbols:
        # Use provided symbols
        symbols_to_screen = request.symbols
    else:
        # Use default universe
        symbols_to_screen = settings.default_symbols
    
    logger.info(
        f"Starting screen for {len(symbols_to_screen)} symbols "
        f"from {request.start_date} to {request.end_date}"
    )
    
    # Build filters from request
    filters = []
    
    # Volume filter
    if request.filters.volume:
        vf = request.filters.volume
        if vf.min_average is not None and vf.max_average is not None:
            # Create a volume range filter
            filters.append(
                VolumeFilter(
                    lookback_days=vf.lookback_days,
                    threshold=vf.min_average,
                    name="VolumeFilterMin"
                )
            )
            # Note: For max volume, we'd need to modify the VolumeFilter or create a new one
            # For now, we'll just use the minimum threshold
        elif vf.min_average is not None:
            filters.append(
                VolumeFilter(
                    lookback_days=vf.lookback_days,
                    threshold=vf.min_average,
                    name="VolumeFilter"
                )
            )
    
    # Price change filter
    if request.filters.price_change:
        pcf = request.filters.price_change
        # Set defaults if not provided
        min_change = pcf.min_change if pcf.min_change is not None else -float('inf')
        max_change = pcf.max_change if pcf.max_change is not None else float('inf')
        
        filters.append(
            PriceChangeFilter(
                min_change=min_change,
                max_change=max_change,
                name=f"PriceChange{pcf.period_days}d"
            )
        )
    
    # Moving average filter
    if request.filters.moving_average:
        maf = request.filters.moving_average
        position = "above" if maf.condition in [ComparisonOperator.ABOVE, ComparisonOperator.CROSSES_ABOVE] else "below"
        
        filters.append(
            MovingAverageFilter(
                period=maf.period,
                position=position,
                name=f"MA{maf.period}"
            )
        )
    
    # Gap filter
    if request.filters.gap:
        gf = request.filters.gap
        filters.append(
            GapFilter(
                min_gap_percent=gf.min_gap_percent,
                max_gap_percent=gf.max_gap_percent,
                name="GapFilter"
            )
        )
    
    # Price range filter
    if request.filters.price_range:
        prf = request.filters.price_range
        filters.append(
            PriceRangeFilter(
                min_price=prf.min_price,
                max_price=prf.max_price,
                name="PriceRangeFilter"
            )
        )
    
    # Relative volume filter
    if request.filters.relative_volume:
        rvf = request.filters.relative_volume
        filters.append(
            RelativeVolumeFilter(
                min_relative_volume=rvf.min_relative_volume,
                lookback_days=rvf.lookback_days,
                name="RelativeVolumeFilter"
            )
        )
    
    # Float filter
    if request.filters.float:
        ff = request.filters.float
        filters.append(
            FloatFilter(
                max_float=ff.max_float,
                name="FloatFilter"
            )
        )
    
    
    # Market cap filter
    if request.filters.market_cap:
        mcf = request.filters.market_cap
        filters.append(
            MarketCapFilter(
                max_market_cap=mcf.max_market_cap,
                min_market_cap=mcf.min_market_cap,
                name="MarketCapFilter"
            )
        )
    
    
    if not filters:
        raise HTTPException(
            status_code=400,
            detail="At least one filter must be specified"
        )
    
    try:
        # Run screening with automatic period extension for filters requiring historical data
        screening_start = time.time()
        screener = ScreenerEngine(max_workers=8, polygon_client=polygon_client)
        
        # Use the new period extension method which automatically handles data fetching and filtering
        screen_result_obj, extension_metadata = await screener.screen_with_period_extension(
            symbols=symbols_to_screen,
            filters=filters,
            start_date=request.start_date,
            end_date=request.end_date,
            polygon_client=polygon_client,
            auto_slice_results=True,  # Slice results back to original date range
            adjusted=True,
            max_concurrent=200,
            prefer_bulk=(request.start_date == request.end_date) or request.use_all_us_stocks
        )
        
        screening_time = time.time() - screening_start
        
        # Convert ScreenerResult to the format expected by screen_with_metrics
        screen_result = {
            'summary': screen_result_obj.get_summary(),
            'qualifying_symbols': [],
            'aggregated_metrics': {}
        }
        
        # Process qualifying symbols
        for symbol in screen_result_obj.qualifying_symbols:
            result_obj = screen_result_obj.results[symbol]
            symbol_info = {
                'symbol': symbol,
                'qualifying_days': result_obj.num_qualifying_days,
                'first_qualifying_date': str(result_obj.qualifying_dates[0]) if result_obj.num_qualifying_days > 0 else None,
                'last_qualifying_date': str(result_obj.qualifying_dates[-1]) if result_obj.num_qualifying_days > 0 else None,
                'metrics': result_obj.metrics
            }
            screen_result['qualifying_symbols'].append(symbol_info)
        
        # Add extension metadata to logging
        if extension_metadata.get('period_extension_applied', False):
            logger.info(f"Period extension applied: extended from {extension_metadata['original_start_date']} "
                       f"to {extension_metadata['extended_start_date']} "
                       f"(+{extension_metadata['extension_days']} days) for filter requirements")
        
        logger.info(f"Screening completed in {screening_time:.2f} seconds")
        
        # Convert results to response format
        results = []
        for symbol_info in screen_result['qualifying_symbols']:
            result = ScreenResult(
                symbol=symbol_info['symbol'],
                qualifying_dates=[
                    datetime.strptime(d, '%Y-%m-%d').date() if isinstance(d, str) else d
                    for d in [symbol_info['first_qualifying_date'], symbol_info['last_qualifying_date']]
                    if d is not None
                ],
                metrics=symbol_info['metrics']
            )
            results.append(result)
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Build performance metrics using extension metadata
        symbols_fetched = extension_metadata.get('symbols_fetched', len(symbols_to_screen))
        symbols_failed = extension_metadata.get('total_symbols_requested', len(symbols_to_screen)) - symbols_fetched
        data_fetch_time_ms = extension_metadata.get('fetch_time_seconds', 0) * 1000
        
        performance_metrics = PerformanceMetrics(
            data_fetch_time_ms=data_fetch_time_ms,
            screening_time_ms=screening_time * 1000,
            total_execution_time_ms=execution_time_ms,
            used_bulk_endpoint=extension_metadata.get('bulk_endpoint_used', False),
            symbols_fetched=symbols_fetched,
            symbols_failed=symbols_failed
        )
        
        # Build response
        response = ScreenResponse(
            request_date=date.today(),
            total_symbols_screened=len(symbols_to_screen),
            total_qualifying_stocks=len(results),
            results=results,
            execution_time_ms=execution_time_ms,
            performance_metrics=performance_metrics
        )
        
        # Enhanced performance logging with period extension info
        extension_info = ""
        if extension_metadata.get('period_extension_applied', False):
            extension_info = f", Period extension: +{extension_metadata.get('extension_days', 0)} days"
        
        logger.info(
            f"Screen completed: {len(results)} qualifying stocks found "
            f"in {execution_time_ms:.2f}ms total "
            f"(Data fetch: {data_fetch_time_ms:.2f}ms, "
            f"Screening: {screening_time * 1000:.2f}ms, "
            f"Bulk endpoint: {'Yes' if performance_metrics.used_bulk_endpoint else 'No'}, "
            f"Success rate: {symbols_fetched}/{len(symbols_to_screen)} symbols{extension_info})"
        )
        
        return response
        
    except PolygonAPIError as e:
        logger.error(f"Polygon API error during screening: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"External API error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error during screening: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.options("/screen")
async def screen_options():
    """
    Handle preflight OPTIONS request for the /screen endpoint.
    
    This explicitly handles CORS preflight requests.
    """
    return JSONResponse(
        status_code=200,
        content={"message": "OK"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )