"""
Data management API endpoints for TimescaleDB operations
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date, timedelta
import asyncio

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query
from pydantic import BaseModel

from app.services.data_collector import DataCollector
from app.services.database import db_pool, check_database_connection, get_table_count
from app.services.polygon_client import PolygonClient
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data", tags=["data_management"])


class DataCollectionRequest(BaseModel):
    """Request model for data collection"""
    symbols: Optional[List[str]] = None
    start_date: date
    end_date: date
    use_bulk_endpoint: bool = True
    skip_existing: bool = True


class DataCollectionResponse(BaseModel):
    """Response model for data collection"""
    status: str
    message: str
    task_id: Optional[str] = None
    statistics: Optional[Dict[str, Any]] = None


class DataCoverageResponse(BaseModel):
    """Response model for data coverage"""
    symbol: str
    data_type: str
    start_date: date
    end_date: date
    last_updated: datetime
    bar_count: Optional[int] = None
    gaps: Optional[List[date]] = None


class DatabaseStatusResponse(BaseModel):
    """Response model for database status"""
    connected: bool
    tables: Dict[str, int]
    total_daily_bars: int
    total_symbols: int
    latest_data_date: Optional[date] = None
    oldest_data_date: Optional[date] = None


# Track background tasks
background_tasks = {}


@router.get("/status", response_model=DatabaseStatusResponse)
async def get_database_status():
    """Get current database status and statistics"""
    try:
        # Check connection
        connected = await check_database_connection()
        
        if not connected:
            raise HTTPException(status_code=503, detail="Database connection failed")
            
        # Get table counts
        tables = {
            "symbols": await get_table_count("symbols"),
            "daily_bars": await get_table_count("daily_bars"),
            "minute_bars": await get_table_count("minute_bars"),
            "data_fetch_errors": await get_table_count("data_fetch_errors"),
            "market_calendar": await get_table_count("market_calendar"),
            "data_coverage": await get_table_count("data_coverage"),
        }
        
        # Get date range of data
        date_range = await db_pool.fetchrow('''
            SELECT 
                MIN(DATE(time)) as oldest_date,
                MAX(DATE(time)) as latest_date
            FROM daily_bars
        ''')
        
        # Get unique symbol count
        symbol_count = await db_pool.fetchval('''
            SELECT COUNT(DISTINCT symbol) FROM daily_bars
        ''')
        
        return DatabaseStatusResponse(
            connected=connected,
            tables=tables,
            total_daily_bars=tables["daily_bars"],
            total_symbols=symbol_count or 0,
            latest_data_date=date_range['latest_date'] if date_range else None,
            oldest_data_date=date_range['oldest_date'] if date_range else None
        )
        
    except Exception as e:
        logger.error(f"Error getting database status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/coverage", response_model=List[DataCoverageResponse])
async def get_data_coverage(
    symbols: Optional[List[str]] = Query(None, description="Filter by symbols"),
    data_type: str = Query("daily", description="Data type (daily or minute)")
):
    """Get data coverage information for symbols"""
    try:
        # Build query
        conditions = ["data_type = $1"]
        params = [data_type]
        
        if symbols:
            conditions.append(f"symbol = ANY(${len(params) + 1})")
            params.append(symbols)
            
        where_clause = " AND ".join(conditions)
        
        # Get coverage data
        rows = await db_pool.fetch(f'''
            SELECT 
                dc.symbol,
                dc.data_type,
                dc.start_date,
                dc.end_date,
                dc.last_updated,
                COUNT(DISTINCT DATE(db.time)) as bar_count
            FROM data_coverage dc
            LEFT JOIN daily_bars db ON dc.symbol = db.symbol
            WHERE {where_clause}
            GROUP BY dc.symbol, dc.data_type, dc.start_date, dc.end_date, dc.last_updated
            ORDER BY dc.symbol
        ''', *params)
        
        results = []
        for row in rows:
            # Check for gaps
            gaps = []
            if row['bar_count'] and row['bar_count'] > 0:
                # Calculate expected trading days
                current = row['start_date']
                expected_days = 0
                while current <= row['end_date']:
                    if current.weekday() < 5:  # Weekday
                        expected_days += 1
                    current += timedelta(days=1)
                    
                # If bar count is less than expected, there might be gaps
                if row['bar_count'] < expected_days * 0.9:  # Allow 10% for holidays
                    # Get actual dates
                    date_rows = await db_pool.fetch('''
                        SELECT DISTINCT DATE(time) as date
                        FROM daily_bars
                        WHERE symbol = $1
                        AND DATE(time) >= $2
                        AND DATE(time) <= $3
                        ORDER BY date
                    ''', row['symbol'], row['start_date'], row['end_date'])
                    
                    existing_dates = {r['date'] for r in date_rows}
                    
                    # Find gaps
                    current = row['start_date']
                    while current <= row['end_date']:
                        if current.weekday() < 5 and current not in existing_dates:
                            gaps.append(current)
                        current += timedelta(days=1)
                        
            results.append(DataCoverageResponse(
                symbol=row['symbol'],
                data_type=row['data_type'],
                start_date=row['start_date'],
                end_date=row['end_date'],
                last_updated=row['last_updated'],
                bar_count=row['bar_count'],
                gaps=gaps if gaps else None
            ))
            
        return results
        
    except Exception as e:
        logger.error(f"Error getting data coverage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/collect/daily", response_model=DataCollectionResponse)
async def collect_daily_data(
    request: DataCollectionRequest,
    background_tasks: BackgroundTasks
):
    """
    Collect daily data for symbols and date range
    
    This endpoint starts a background task to collect data from Polygon.io
    and store it in the database.
    """
    try:
        # Validate date range
        if request.end_date < request.start_date:
            raise HTTPException(
                status_code=400,
                detail="End date must be after start date"
            )
            
        # Generate task ID
        task_id = f"collect_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Start background task
        background_tasks.add_task(
            _collect_data_task,
            task_id,
            request.symbols,
            request.start_date,
            request.end_date,
            request.use_bulk_endpoint,
            request.skip_existing
        )
        
        background_tasks[task_id] = {
            "status": "started",
            "started_at": datetime.now(),
            "request": request.model_dump()
        }
        
        return DataCollectionResponse(
            status="started",
            message=f"Data collection task started with ID: {task_id}",
            task_id=task_id
        )
        
    except Exception as e:
        logger.error(f"Error starting data collection: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/collect/status/{task_id}")
async def get_collection_status(task_id: str):
    """Get status of a data collection task"""
    if task_id not in background_tasks:
        raise HTTPException(status_code=404, detail="Task not found")
        
    return background_tasks[task_id]


@router.post("/collect/today", response_model=DataCollectionResponse)
async def collect_today_data(
    use_bulk_endpoint: bool = Query(True, description="Use bulk endpoint for faster collection")
):
    """Collect today's data for all US stocks"""
    try:
        today = date.today()
        
        # Check if market is open today
        if today.weekday() >= 5:  # Weekend
            return DataCollectionResponse(
                status="skipped",
                message="Market is closed on weekends"
            )
            
        async with DataCollector() as collector:
            stats = await collector.collect_daily_data_for_date(
                target_date=today,
                use_bulk_endpoint=use_bulk_endpoint
            )
            
        return DataCollectionResponse(
            status="completed",
            message=f"Collected data for {stats['bars_stored']} bars from {stats['total_symbols']} symbols",
            statistics=stats
        )
        
    except Exception as e:
        logger.error(f"Error collecting today's data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/update/symbols", response_model=Dict[str, Any])
async def update_symbols():
    """Update symbols table with latest ticker information from Polygon"""
    try:
        async with PolygonClient() as polygon_client:
            async with DataCollector(polygon_client) as collector:
                updated_count = await collector.update_symbols_table()
                
        return {
            "status": "completed",
            "symbols_updated": updated_count
        }
        
    except Exception as e:
        logger.error(f"Error updating symbols: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fill/gaps", response_model=DataCollectionResponse)
async def fill_data_gaps(
    symbols: List[str],
    start_date: date,
    end_date: date
):
    """Fill missing data gaps for specified symbols and date range"""
    try:
        async with DataCollector() as collector:
            stats = await collector.fill_missing_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date
            )
            
        return DataCollectionResponse(
            status="completed",
            message=f"Filled {stats['dates_filled']} missing dates for {stats['symbols_with_gaps']} symbols",
            statistics=stats
        )
        
    except Exception as e:
        logger.error(f"Error filling data gaps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quality/check")
async def check_data_quality(
    symbols: List[str] = Query(..., description="Symbols to check"),
    start_date: date = Query(..., description="Start date"),
    end_date: date = Query(..., description="End date")
):
    """Check data quality for symbols"""
    try:
        from app.services.database_screener import DatabaseScreenerEngine
        
        engine = DatabaseScreenerEngine()
        quality_report = await engine.check_data_quality(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date
        )
        
        return quality_report
        
    except Exception as e:
        logger.error(f"Error checking data quality: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Background task function
async def _collect_data_task(
    task_id: str,
    symbols: Optional[List[str]],
    start_date: date,
    end_date: date,
    use_bulk_endpoint: bool,
    skip_existing: bool
):
    """Background task for data collection"""
    try:
        background_tasks[task_id]["status"] = "running"
        background_tasks[task_id]["started_at"] = datetime.now()
        
        async with DataCollector() as collector:
            if symbols:
                # Collect for specific symbols
                stats = await collector.collect_historical_data(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    skip_existing=skip_existing
                )
            else:
                # Collect all data day by day
                stats = {
                    "total_days": 0,
                    "bars_stored": 0,
                    "errors": 0
                }
                
                current = start_date
                while current <= end_date:
                    if current.weekday() < 5:  # Weekday
                        try:
                            day_stats = await collector.collect_daily_data_for_date(
                                target_date=current,
                                use_bulk_endpoint=use_bulk_endpoint
                            )
                            stats["total_days"] += 1
                            stats["bars_stored"] += day_stats["bars_stored"]
                            stats["errors"] += day_stats["errors"]
                        except Exception as e:
                            logger.error(f"Error collecting data for {current}: {e}")
                            stats["errors"] += 1
                            
                    current += timedelta(days=1)
                    
        background_tasks[task_id]["status"] = "completed"
        background_tasks[task_id]["completed_at"] = datetime.now()
        background_tasks[task_id]["statistics"] = stats
        
    except Exception as e:
        logger.error(f"Background task {task_id} failed: {e}")
        background_tasks[task_id]["status"] = "failed"
        background_tasks[task_id]["error"] = str(e)
        background_tasks[task_id]["completed_at"] = datetime.now()