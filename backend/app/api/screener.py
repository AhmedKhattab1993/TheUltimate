"""
Stock screener API endpoints.

This module provides REST API endpoints for stock screening functionality.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import time

from fastapi import APIRouter, HTTPException
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
from app.services.database_screener import DatabaseScreenerEngine
from app.services.database import db_pool, check_database_connection
from app.config import settings

logger = logging.getLogger(__name__)

# Create router
router = APIRouter()


@router.post("/cache/clear", response_model=Dict[str, str])
async def clear_cache():
    """
    Clear cache endpoint (deprecated).
    
    This endpoint is no longer needed as the screener uses database instead of API cache.
    """
    return {"status": "success", "message": "Cache clearing not applicable for database-based screening"}


@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """
    Health check endpoint.
    
    Verifies that the API is running and can connect to database.
    """
    start_time = time.time()
    
    health_status = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
        "checks": {}
    }
    
    # Check database connectivity
    try:
        db_connected = await check_database_connection()
        if db_connected:
            health_status["checks"]["database"] = {
                "status": "healthy",
                "message": "Database connection available"
            }
        else:
            health_status["status"] = "degraded"
            health_status["checks"]["database"] = {
                "status": "unhealthy",
                "error": "Database connection unavailable"
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["checks"]["database"] = {
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
async def get_all_us_stocks():
    """
    Get list of all US stocks available for screening from database.
    
    This endpoint returns all symbols with available data in the database.
    
    Returns:
        List of ticker symbols available in the database
    """
    # Check database connection
    if not await check_database_connection():
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable. Please try again later."
        )
    
    try:
        screener = DatabaseScreenerEngine()
        symbols = await screener.get_available_symbols(min_bars=1)
        return symbols
    except Exception as e:
        logger.error(f"Error fetching available symbols: {e}")
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
async def screen_stocks(request: ScreenRequest):
    """
    Main screening endpoint using database source.
    
    Screens stocks based on the provided filters and date range using data from TimescaleDB.
    
    Parameters:
    - **start_date**: Start date for historical data (YYYY-MM-DD)
    - **end_date**: End date for historical data (YYYY-MM-DD)
    - **symbols**: Optional list of symbols to screen (if not provided, screens all available symbols)
    - **use_all_us_stocks**: If true, screens all available stocks in database (ignores symbols parameter)
    - **filters**: Filter configuration object with volume, price_change, and/or moving_average filters
    
    Returns:
    - List of qualifying stocks with their metrics
    - Execution time and summary statistics
    """
    start_time = time.time()
    
    # Check database connection
    if not await check_database_connection():
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable. Please try again later."
        )
    
    # Determine which symbols to screen
    symbols_to_screen = []
    
    if request.use_all_us_stocks or not request.symbols:
        # Get all available symbols from database
        try:
            screener = DatabaseScreenerEngine()
            symbols_to_screen = await screener.get_available_symbols(
                min_bars=1,
                start_date=request.start_date,
                end_date=request.end_date
            )
            logger.info(f"Found {len(symbols_to_screen)} symbols with data in database")
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving available symbols: {str(e)}"
            )
    else:
        # Use provided symbols
        symbols_to_screen = request.symbols
    
    if not symbols_to_screen:
        raise HTTPException(
            status_code=404,
            detail="No symbols found with data in the specified date range"
        )
    
    logger.info(
        f"Starting database screen for {len(symbols_to_screen)} symbols "
        f"from {request.start_date} to {request.end_date}"
    )
    
    # Build filters from request (same as database endpoint)
    filters = []
    
    # Volume filter
    if request.filters.volume:
        vf = request.filters.volume
        if vf.min_average is not None:
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
        # Run screening using database
        screening_start = time.time()
        screener = DatabaseScreenerEngine()
        
        results = await screener.screen_stocks(
            symbols=symbols_to_screen,
            filters=filters,
            start_date=request.start_date,
            end_date=request.end_date,
            max_workers=100
        )
        
        screening_time = time.time() - screening_start
        
        # Convert results to response format
        screen_results = []
        for symbol, data in results.items():
            result = ScreenResult(
                symbol=symbol,
                qualifying_dates=[data['date']],
                metrics={
                    'latest_price': data['latest_price'],
                    'latest_volume': data['latest_volume'],
                    **{k: v['value'] for k, v in data['filters'].items() if v['value'] is not None}
                }
            )
            screen_results.append(result)
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Build performance metrics
        performance_metrics = PerformanceMetrics(
            data_fetch_time_ms=0,  # No external data fetch needed for database
            screening_time_ms=screening_time * 1000,
            total_execution_time_ms=execution_time_ms,
            used_bulk_endpoint=False,  # Not applicable for database screening
            symbols_fetched=len(symbols_to_screen),
            symbols_failed=0
        )
        
        # Build response
        response = ScreenResponse(
            request_date=date.today(),
            total_symbols_screened=len(symbols_to_screen),
            total_qualifying_stocks=len(screen_results),
            results=screen_results,
            execution_time_ms=execution_time_ms,
            performance_metrics=performance_metrics
        )
        
        logger.info(
            f"Database screen completed: {len(screen_results)} qualifying stocks found "
            f"in {execution_time_ms:.2f}ms"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error during database screening: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@router.post("/screen/database", response_model=ScreenResponse)
async def screen_stocks_database(request: ScreenRequest):
    """
    Screen stocks using data from TimescaleDB database.
    
    This endpoint is much faster than the API-based screening as it reads
    pre-collected data from the local database.
    
    Parameters:
    - **start_date**: Start date for historical data (YYYY-MM-DD)
    - **end_date**: End date for historical data (YYYY-MM-DD)
    - **symbols**: Optional list of symbols to screen (if not provided, screens all available symbols)
    - **filters**: Filter configuration object
    
    Returns:
    - List of qualifying stocks with their metrics
    - Execution time and summary statistics
    """
    start_time = time.time()
    
    # Check database connection
    if not await check_database_connection():
        raise HTTPException(
            status_code=503,
            detail="Database connection unavailable. Please use the regular /screen endpoint."
        )
    
    # Get symbols to screen
    symbols_to_screen = []
    
    if request.symbols:
        symbols_to_screen = request.symbols
    else:
        # Get all available symbols from database
        try:
            screener = DatabaseScreenerEngine()
            symbols_to_screen = await screener.get_available_symbols(
                min_bars=1,
                start_date=request.start_date,
                end_date=request.end_date
            )
            logger.info(f"Found {len(symbols_to_screen)} symbols with data in database")
        except Exception as e:
            logger.error(f"Error getting available symbols: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error retrieving available symbols: {str(e)}"
            )
    
    if not symbols_to_screen:
        raise HTTPException(
            status_code=404,
            detail="No symbols found with data in the specified date range"
        )
    
    logger.info(
        f"Starting database screen for {len(symbols_to_screen)} symbols "
        f"from {request.start_date} to {request.end_date}"
    )
    
    # Build filters (same as regular screen endpoint)
    filters = []
    
    # Volume filter
    if request.filters.volume:
        vf = request.filters.volume
        if vf.min_average is not None:
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
        # Run screening using database
        screening_start = time.time()
        screener = DatabaseScreenerEngine()
        
        results = await screener.screen_stocks(
            symbols=symbols_to_screen,
            filters=filters,
            start_date=request.start_date,
            end_date=request.end_date,
            max_workers=100
        )
        
        screening_time = time.time() - screening_start
        
        # Convert results to response format
        screen_results = []
        for symbol, data in results.items():
            result = ScreenResult(
                symbol=symbol,
                qualifying_dates=[data['date']],
                metrics={
                    'latest_price': data['latest_price'],
                    'latest_volume': data['latest_volume'],
                    **{k: v['value'] for k, v in data['filters'].items() if v['value'] is not None}
                }
            )
            screen_results.append(result)
        
        # Calculate execution time
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Build performance metrics
        performance_metrics = PerformanceMetrics(
            data_fetch_time_ms=0,  # No data fetch needed for database
            screening_time_ms=screening_time * 1000,
            total_execution_time_ms=execution_time_ms,
            used_bulk_endpoint=False,
            symbols_fetched=len(symbols_to_screen),
            symbols_failed=0
        )
        
        # Build response
        response = ScreenResponse(
            request_date=date.today(),
            total_symbols_screened=len(symbols_to_screen),
            total_qualifying_stocks=len(screen_results),
            results=screen_results,
            execution_time_ms=execution_time_ms,
            performance_metrics=performance_metrics
        )
        
        logger.info(
            f"Database screen completed: {len(screen_results)} qualifying stocks found "
            f"in {execution_time_ms:.2f}ms"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error during database screening: {e}", exc_info=True)
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