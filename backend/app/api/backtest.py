"""
API endpoints for backtesting functionality.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from typing import List, Optional, Dict, Any
from datetime import date, datetime, timedelta
import logging
import json

from ..models.backtest import (
    BacktestRequest, BacktestRunInfo, BacktestResult,
    BacktestListResponse, StrategyInfo, BacktestProgress, BacktestStatus,
    BacktestStatistics, ScreenerBacktestRequest
)
from ..services.backtest_manager import backtest_manager
from ..services.lean_runner import LeanRunner
from ..services.backtest_storage import BacktestStorage
from ..services.backtest_queue_manager import BacktestQueueManager
from ..services.cache_service import CacheService
from ..services.screener_results import screener_results_manager
from ..services.database import db_pool
from .bulk_backtest_websocket import bulk_websocket_manager
import uuid


router = APIRouter(prefix="/api/v2/backtest", tags=["backtest"])
logger = logging.getLogger(__name__)


@router.get("/strategies", response_model=List[StrategyInfo])
async def list_strategies():
    """
    List all available LEAN strategies.
    
    Returns a list of strategies found in the LEAN project directory,
    including their names, file paths, and basic information.
    """
    try:
        runner = LeanRunner()
        strategies = runner.list_strategies()
        
        return [
            StrategyInfo(
                name=s["name"],
                file_path=s.get("main_py_path", s.get("project_path", "")),
                description=s.get("description"),
                last_modified=s.get("last_modified")
            )
            for s in strategies
        ]
    except Exception as e:
        logger.error(f"Error listing strategies: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/strategies/{name}", response_model=StrategyInfo)
async def get_strategy_details(name: str):
    """
    Get detailed information about a specific strategy.
    
    Args:
        name: The name of the strategy
        
    Returns:
        Detailed strategy information including available parameters
    """
    try:
        runner = LeanRunner()
        details = runner.get_strategy_details(name)
        
        if not details:
            raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
        
        return StrategyInfo(
            name=details["name"],
            file_path=details.get("main_py_path", details.get("project_path", "")),
            description=details.get("description"),
            parameters=details.get("parameters", {}),
            last_modified=details.get("last_modified")
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting strategy details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run", response_model=BacktestRunInfo)
async def start_backtest(request: BacktestRequest):
    """
    Start a new backtest run.
    
    This endpoint initiates a backtest using the specified strategy and parameters.
    The backtest runs asynchronously in a Docker container, and you can monitor
    its progress using the status endpoint or WebSocket connection.
    
    Args:
        request: Backtest configuration including strategy, date range, and parameters
        
    Returns:
        BacktestRunInfo with the backtest ID and initial status
    """
    try:
        run_info = await backtest_manager.start_backtest(request)
        return run_info
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error starting backtest: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{backtest_id}", response_model=BacktestRunInfo)
async def get_backtest_status(backtest_id: str):
    """
    Get the current status of a backtest.
    
    Args:
        backtest_id: The unique identifier of the backtest
        
    Returns:
        Current status and information about the backtest
    """
    run_info = await backtest_manager.get_backtest_status(backtest_id)
    
    if not run_info:
        raise HTTPException(status_code=404, detail=f"Backtest '{backtest_id}' not found")
    
    return run_info


@router.get("/progress/{backtest_id}", response_model=BacktestProgress)
async def get_backtest_progress(backtest_id: str):
    """
    Get detailed progress information for a running backtest.
    
    This endpoint provides real-time progress updates including current processing date,
    completion percentage, and partial statistics.
    
    Args:
        backtest_id: The unique identifier of the backtest
        
    Returns:
        Detailed progress information
    """
    progress = await backtest_manager.get_backtest_progress(backtest_id)
    
    if not progress:
        raise HTTPException(status_code=404, detail=f"Backtest '{backtest_id}' not found")
    
    return progress


@router.delete("/cancel/{backtest_id}")
async def cancel_backtest(backtest_id: str):
    """
    Cancel a running backtest.
    
    Args:
        backtest_id: The unique identifier of the backtest to cancel
        
    Returns:
        Success message if cancelled
    """
    success = await backtest_manager.cancel_backtest(backtest_id)
    
    if not success:
        raise HTTPException(
            status_code=400, 
            detail=f"Cannot cancel backtest '{backtest_id}' - not found or not running"
        )
    
    return {"message": f"Backtest '{backtest_id}' cancelled successfully"}


@router.get("/results", response_model=BacktestListResponse)
async def list_backtest_results(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    strategy_name: Optional[str] = Query(None, description="Filter by strategy name")
):
    """
    List historical backtest results with pagination.
    
    Args:
        page: Page number (1-based)
        page_size: Number of results per page
        strategy_name: Optional filter by strategy name
        
    Returns:
        Paginated list of backtest results
    """
    try:
        # Aggregate results from multiple strategy directories
        all_results = []
        
        # Get available strategies
        lean_runner = LeanRunner()
        strategies = lean_runner.list_strategies()
        
        # Collect results from each strategy's backtests folder
        for strategy in strategies:
            try:
                strategy_storage = BacktestStorage(strategy_name=strategy["name"])
                strategy_results = await strategy_storage.list_results(
                    page=1,
                    page_size=1000,  # Get all results for aggregation
                    strategy_name=strategy_name
                )
                all_results.extend(strategy_results.results)
            except Exception as e:
                # Log error but continue with other strategies
                logger.warning(f"Error loading results for strategy '{strategy['name']}': {e}")
        
        # Sort all results by created_at date
        all_results.sort(key=lambda x: x.created_at, reverse=True)
        
        # Apply pagination
        total_count = len(all_results)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_results = all_results[start_idx:end_idx]
        
        # Remove orders from list response to reduce payload size
        # Orders can be fetched separately via /results/{timestamp}
        for result in paginated_results:
            result.orders = None
        
        return BacktestListResponse(
            results=paginated_results,
            total_count=total_count,
            page=page,
            page_size=page_size
        )
    except Exception as e:
        logger.error(f"Error listing backtest results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/results/{timestamp}", response_model=BacktestResult)
async def get_backtest_result(timestamp: str):
    """
    Get detailed results for a specific backtest.
    
    Args:
        timestamp: The timestamp folder name (e.g., "2025-08-10_05-09-01")
        
    Returns:
        Complete backtest result including statistics, trades, and equity curve
    """
    try:
        # Try to find the result in any strategy's backtest folder
        lean_runner = LeanRunner()
        strategies = lean_runner.list_strategies()
        
        for strategy in strategies:
            strategy_storage = BacktestStorage(strategy_name=strategy["name"])
            result = await strategy_storage.get_result(timestamp)
            if result:
                return result
        
        # If not found in any strategy folder, check default location
        storage = BacktestStorage()
        result = await storage.get_result(timestamp)
        
        if not result:
            raise HTTPException(status_code=404, detail=f"Backtest result '{timestamp}' not found")
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting backtest result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/results/{timestamp}")
async def delete_backtest_result(timestamp: str):
    """
    Delete a backtest result.
    
    Args:
        timestamp: The timestamp folder name to delete
        
    Returns:
        Success message if deleted
    """
    try:
        storage = BacktestStorage()
        success = await storage.delete_result(timestamp)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Backtest result '{timestamp}' not found")
        
        return {"message": f"Backtest result '{timestamp}' deleted successfully"}
    except Exception as e:
        logger.error(f"Error deleting backtest result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/monitor/{backtest_id}")
async def monitor_backtest(websocket: WebSocket, backtest_id: str):
    """
    WebSocket endpoint for real-time backtest monitoring.
    
    Connect to this endpoint to receive real-time updates about a running backtest,
    including progress updates, log entries, and completion notifications.
    
    Message types:
    - progress_update: Regular progress updates with statistics
    - backtest_completed: Sent when backtest finishes successfully
    - backtest_failed: Sent when backtest fails
    - backtest_cancelled: Sent when backtest is cancelled
    """
    await websocket.accept()
    
    # Check if backtest exists
    run_info = await backtest_manager.get_backtest_status(backtest_id)
    if not run_info:
        await websocket.send_json({
            "event": "error",
            "message": f"Backtest '{backtest_id}' not found"
        })
        await websocket.close()
        return
    
    # Add WebSocket to manager
    await backtest_manager.add_websocket_connection(backtest_id, websocket)
    
    try:
        # Send initial status in frontend-expected format
        if run_info.status == BacktestStatus.COMPLETED:
            # Parse LEAN results and send complete data
            parsed_result = backtest_manager._parse_lean_results(run_info.result_path, backtest_id)
            if parsed_result:
                await websocket.send_json({
                    "type": "result",
                    "result": parsed_result
                })
            else:
                # Fallback to basic result structure if parsing fails
                from pathlib import Path
                timestamp = Path(run_info.result_path).name if run_info.result_path else backtest_id
                await websocket.send_json({
                    "type": "result",
                    "result": {
                        "timestamp": timestamp,
                        "statistics": {
                            "totalReturn": 0, "sharpeRatio": 0, "maxDrawdown": 0, 
                            "winRate": 0, "totalTrades": 0, "profitableTrades": 0,
                            "averageWin": 0, "averageLoss": 0
                        },
                        "equityCurve": [],
                        "orders": [],
                        "logs": ["Backtest completed but result parsing failed"]
                    }
                })
        elif run_info.status == BacktestStatus.FAILED:
            await websocket.send_json({
                "type": "error", 
                "message": run_info.error_message or "Backtest failed"
            })
        else:
            await websocket.send_json({
                "type": "progress",
                "percentage": 0 if run_info.status == BacktestStatus.RUNNING else 100,
                "message": f"Backtest {run_info.status.value}..."
            })
        
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any message from client (ping/pong)
                data = await websocket.receive_text()
                
                # Handle ping
                if data == "ping":
                    await websocket.send_text("pong")
                
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    finally:
        # Remove WebSocket from manager
        await backtest_manager.remove_websocket_connection(backtest_id, websocket)


@router.websocket("/monitor/bulk/{bulk_id}")
async def monitor_bulk_backtest(websocket: WebSocket, bulk_id: str):
    """
    WebSocket endpoint for monitoring bulk backtest operations.
    
    Connect to this endpoint to receive real-time updates about multiple backtests
    running as part of a bulk operation.
    
    Message types:
    - bulk_progress: Overall progress of the bulk operation
    - backtest_update: Individual backtest status updates
    """
    await bulk_websocket_manager.connect(bulk_id, websocket)
    
    try:
        # Keep connection alive and handle messages
        while True:
            try:
                # Wait for messages from client
                data = await websocket.receive_text()
                # Could handle specific commands if needed
                if data == "ping":
                    await websocket.send_text("pong")
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    finally:
        bulk_websocket_manager.disconnect(bulk_id, websocket)


@router.get("/screener-results/latest")
async def get_latest_screener_results():
    """
    Get the latest screener results.
    
    Returns the most recent screener results that can be used for backtesting.
    """
    try:
        results = screener_results_manager.get_latest_results()
        if not results:
            raise HTTPException(status_code=404, detail="No screener results found")
        
        return results
    except Exception as e:
        logger.error(f"Error getting latest screener results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screener-results")
async def list_screener_results():
    """
    List all available screener results.
    
    Returns a list of all screener result files with their metadata.
    """
    try:
        results = screener_results_manager.list_results()
        return {"results": results}
    except Exception as e:
        logger.error(f"Error listing screener results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-bulk")
async def start_bulk_backtests(request: BacktestRequest):
    """
    Start multiple backtests - one per symbol per trading day.
    
    This endpoint processes each trading day individually (backward from end to start),
    creating separate backtests for each symbol on each day. This matches the behavior
    of the pipeline script for consistency.
    
    Uses BacktestQueueManager for:
    - Parallel execution with concurrency control
    - Database storage of results
    - Cleanup of temporary files
    
    Args:
        request: Backtest configuration with date range and symbols
        
    Returns:
        List of backtest IDs and summary information
    """
    try:
        # Validate request
        if not request.symbols and not request.use_screener_results:
            raise HTTPException(
                status_code=400,
                detail="Please provide symbols or enable use_screener_results"
            )
        
        # Get trading days in reverse order (end to start)
        trading_days = []
        current = request.end_date
        while current >= request.start_date:
            # Check if it's a weekday (Monday=0 to Friday=4)
            if current.weekday() < 5:
                trading_days.append(current)
            current = current - timedelta(days=1)
        
        if not trading_days:
            raise HTTPException(
                status_code=400,
                detail="No trading days found in the specified date range"
            )
        
        # Get symbols to backtest
        symbols = request.symbols
        if request.use_screener_results:
            # Get latest screener results
            latest_results = screener_results_manager.get_latest_results()
            if not latest_results:
                raise HTTPException(
                    status_code=400,
                    detail="No screener results found to use"
                )
            symbols = latest_results.get("symbols", [])
        
        if not symbols:
            raise HTTPException(
                status_code=400,
                detail="No symbols to backtest"
            )
        
        # Create cache service for database storage
        cache_service = CacheService(
            screener_ttl_hours=24,
            backtest_ttl_days=7
        )
        
        # Generate unique bulk ID for this operation
        bulk_id = str(uuid.uuid4())
        
        # Create queue manager with same settings as pipeline
        queue_manager = BacktestQueueManager(
            max_parallel=5,  # Same as pipeline default
            startup_delay=15.0,  # Same as pipeline default
            cache_service=cache_service,
            enable_storage=True,  # Enable database storage
            enable_cleanup=True   # Enable cleanup after storage
        )
        
        # Create backtest requests for queue manager
        backtest_requests = []
        backtest_tasks_preview = []  # For WebSocket registration
        total_backtests = len(trading_days) * len(symbols)
        
        logger.info(f"Starting bulk backtest: {len(trading_days)} days × {len(symbols)} symbols = {total_backtests} backtests")
        
        for trading_day in trading_days:
            for symbol in symbols:
                # Pre-generate backtest ID for tracking
                backtest_id = str(uuid.uuid4())
                
                # Create request in the format expected by queue manager
                backtest_request = {
                    'symbol': symbol,
                    'strategy': request.strategy_name,
                    'start_date': trading_day.strftime('%Y-%m-%d'),
                    'end_date': trading_day.strftime('%Y-%m-%d'),
                    'initial_cash': float(request.initial_cash),
                    'resolution': request.resolution,
                    'parameters': request.parameters or {},
                    'task_id': backtest_id  # Pass the pre-generated ID
                }
                backtest_requests.append(backtest_request)
                
                # Create preview task for WebSocket tracking
                backtest_tasks_preview.append({
                    'backtest_id': backtest_id,  # Use same ID
                    'symbol': symbol,
                    'date': trading_day.strftime('%Y-%m-%d'),
                    'status': 'pending'
                })
        
        # Set up completion callback for WebSocket notification
        async def completion_callback():
            logger.info(f"[BulkBacktest] All backtests completed for bulk_id: {bulk_id}")
            # Notify WebSocket clients that all backtests are complete
            await bulk_websocket_manager.notify_completion(bulk_id)
        
        queue_manager.set_completion_callback(completion_callback)
        
        # Register bulk backtest with WebSocket manager
        bulk_websocket_manager.register_bulk_backtest(bulk_id)
        
        # Run backtests through queue manager (parallel execution)
        results = await queue_manager.run_batch(
            backtest_requests,
            timeout_per_backtest=300,  # 5 minutes per backtest
            retry_attempts=2,
            continue_on_error=True
        )
        
        # Process results
        backtest_tasks = []
        successful_count = 0
        failed_count = 0
        
        for symbol, result in results.items():
            if result.get('status') == 'completed':
                successful_count += 1
                status = 'completed'
            else:
                failed_count += 1
                status = 'failed'
            
            # Extract date from symbol key (format: "SYMBOL_YYYY-MM-DD")
            parts = symbol.split('_')
            if len(parts) > 1:
                date_str = parts[-1]
                symbol_name = '_'.join(parts[:-1])
            else:
                date_str = trading_days[0].strftime('%Y-%m-%d')
                symbol_name = symbol
            
            backtest_tasks.append({
                "backtest_id": result.get('backtest_id'),
                "symbol": symbol_name,
                "date": date_str,
                "status": status,
                "error": result.get('error') if status == 'failed' else None
            })
        
        # Return summary with bulk_id for WebSocket connection
        return {
            "bulk_id": bulk_id,  # Frontend uses this to connect WebSocket
            "total_backtests": total_backtests,
            "successful_starts": successful_count,
            "failed_starts": failed_count,
            "trading_days": len(trading_days),
            "symbols": len(symbols),
            "date_range": {
                "start": request.start_date.isoformat(),
                "end": request.end_date.isoformat()
            },
            "backtests": backtest_tasks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting bulk backtests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screener-results/grouped")
async def get_screener_results_grouped():
    """
    Get screener results grouped by date for Import Scanner functionality.
    
    Returns screener results from the database grouped by data_date,
    showing which symbols were found on each screening day.
    """
    try:
        # Query the database for screener results grouped by date
        query = """
        SELECT 
            data_date,
            session_id,
            COUNT(DISTINCT symbol) as symbol_count,
            ARRAY_AGG(DISTINCT symbol ORDER BY symbol) as symbols
        FROM screener_results
        WHERE data_date IS NOT NULL
        GROUP BY data_date, session_id
        ORDER BY data_date DESC, session_id DESC
        """
        
        rows = await db_pool.fetch(query)
        
        # Group by date
        results_by_date = {}
        for row in rows:
            date_str = row['data_date'].isoformat()
            if date_str not in results_by_date:
                results_by_date[date_str] = {
                    "date": date_str,
                    "sessions": [],
                    "total_symbols": 0,
                    "all_symbols": set()
                }
            
            results_by_date[date_str]["sessions"].append({
                "session_id": row['session_id'],
                "symbol_count": row['symbol_count'],
                "symbols": row['symbols']
            })
            
            # Add to total unique symbols for this date
            results_by_date[date_str]["all_symbols"].update(row['symbols'])
        
        # Convert to list and finalize
        grouped_results = []
        for date_str, data in results_by_date.items():
            data["total_symbols"] = len(data["all_symbols"])
            data["all_symbols"] = sorted(list(data["all_symbols"]))
            grouped_results.append(data)
        
        return {
            "total_dates": len(grouped_results),
            "results": grouped_results
        }
        
    except Exception as e:
        logger.error(f"Error getting grouped screener results: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/screener-results/latest-ui-session")
async def get_latest_ui_screener_session():
    """
    Get the latest screener session from UI runs only.
    
    Returns the most recent screener session that was run from the UI,
    with all symbols and their respective screening dates.
    """
    try:
        # Query for the latest UI session
        query = """
        WITH latest_session AS (
            SELECT session_id, MAX(created_at) as latest_created
            FROM screener_results
            WHERE source = 'ui'
            GROUP BY session_id
            ORDER BY latest_created DESC
            LIMIT 1
        )
        SELECT 
            sr.data_date,
            sr.symbol,
            sr.session_id,
            sr.created_at
        FROM screener_results sr
        JOIN latest_session ls ON sr.session_id = ls.session_id
        WHERE sr.source = 'ui'
        ORDER BY sr.data_date DESC, sr.symbol
        """
        
        rows = await db_pool.fetch(query)
        
        if not rows:
            raise HTTPException(
                status_code=404,
                detail="No UI screener sessions found"
            )
        
        # Group symbols by date
        session_id = rows[0]['session_id']
        created_at = rows[0]['created_at']
        symbols_by_date = {}
        all_symbols = set()
        
        for row in rows:
            date_str = row['data_date'].isoformat()
            if date_str not in symbols_by_date:
                symbols_by_date[date_str] = []
            symbols_by_date[date_str].append(row['symbol'])
            all_symbols.add(row['symbol'])
        
        # Get date range
        dates = sorted(symbols_by_date.keys())
        
        return {
            "session_id": session_id,
            "created_at": created_at.isoformat(),
            "date_range": {
                "start": dates[-1] if dates else None,  # Earliest date
                "end": dates[0] if dates else None      # Latest date
            },
            "total_days": len(symbols_by_date),
            "total_symbols": len(all_symbols),
            "symbols_by_date": symbols_by_date,
            "all_symbols": sorted(list(all_symbols))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting latest UI screener session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/run-screener-backtests")
async def start_screener_backtests(request: ScreenerBacktestRequest):
    """
    Start backtests for screener results.
    
    If use_latest_ui_session is True, uses the most recent UI screener session.
    Otherwise, queries screener results within the provided date range.
    
    Runs backtests for each symbol on its respective screening day.
    Uses BacktestQueueManager for parallel execution and database storage.
    """
    # Log the incoming request parameters
    logger.info(f"Screener backtest request received: strategy={request.strategy_name}, "
                f"initial_cash={request.initial_cash}, resolution={request.resolution}, "
                f"use_latest_ui_session={request.use_latest_ui_session}, "
                f"parameters={request.parameters}")
    
    try:
        if request.use_latest_ui_session:
            # Query for the latest UI session
            query = """
            WITH latest_session AS (
                SELECT session_id
                FROM screener_results
                WHERE source = 'ui'
                GROUP BY session_id
                ORDER BY MAX(created_at) DESC
                LIMIT 1
            )
            SELECT DISTINCT
                data_date,
                symbol
            FROM screener_results
            WHERE session_id = (SELECT session_id FROM latest_session)
            ORDER BY data_date DESC, symbol
            """
            rows = await db_pool.fetch(query)
        else:
            # Original behavior - query by date range
            if not request.start_date or not request.end_date:
                raise HTTPException(
                    status_code=400,
                    detail="Either provide start_date and end_date, or set use_latest_ui_session=true"
                )
            
            query = """
            SELECT DISTINCT
                data_date,
                symbol
            FROM screener_results
            WHERE data_date >= $1 AND data_date <= $2
            ORDER BY data_date DESC, symbol
            """
            rows = await db_pool.fetch(query, request.start_date, request.end_date)
        
        if not rows:
            if request.use_latest_ui_session:
                detail = "No UI screener results found in the latest session"
            else:
                detail = f"No screener results found between {request.start_date} and {request.end_date}"
            raise HTTPException(status_code=404, detail=detail)
        
        # Group symbols by date
        symbols_by_date = {}
        for row in rows:
            date_str = row['data_date'].isoformat()
            if date_str not in symbols_by_date:
                symbols_by_date[date_str] = []
            symbols_by_date[date_str].append(row['symbol'])
        
        # Create cache service for database storage
        cache_service = CacheService(
            screener_ttl_hours=24,
            backtest_ttl_days=7
        )
        
        # Create queue manager with same settings as pipeline
        queue_manager = BacktestQueueManager(
            max_parallel=5,
            startup_delay=15.0,
            cache_service=cache_service,
            enable_storage=True,
            enable_cleanup=True
        )
        
        # Create backtest requests for queue manager
        backtest_requests = []
        total_backtests = sum(len(symbols) for symbols in symbols_by_date.values())
        
        logger.info(f"Starting screener-based backtests: {len(symbols_by_date)} days, {total_backtests} total backtests")
        
        for date_str, symbols in symbols_by_date.items():
            for symbol in symbols:
                # Create request in the format expected by queue manager
                backtest_request = {
                    'symbol': symbol,
                    'strategy': request.strategy_name,
                    'start_date': date_str,
                    'end_date': date_str,
                    'initial_cash': float(request.initial_cash),
                    'resolution': request.resolution,
                    'parameters': request.parameters or {}
                }
                backtest_requests.append(backtest_request)
        
        # Run backtests through queue manager (parallel execution)
        results = await queue_manager.run_batch(
            backtest_requests,
            timeout_per_backtest=300,
            retry_attempts=2,
            continue_on_error=True
        )
        
        # Process results
        backtest_tasks = []
        successful_count = 0
        failed_count = 0
        
        for symbol, result in results.items():
            if result.get('status') == 'completed':
                successful_count += 1
                status = 'completed'
            else:
                failed_count += 1
                status = 'failed'
            
            # Extract date from symbol key
            parts = symbol.split('_')
            if len(parts) > 1:
                date_str = parts[-1]
                symbol_name = '_'.join(parts[:-1])
            else:
                # Find the date for this symbol from our original data
                symbol_name = symbol
                date_str = None
                for date_key, syms in symbols_by_date.items():
                    if symbol_name in syms:
                        date_str = date_key
                        break
            
            backtest_tasks.append({
                "backtest_id": result.get('backtest_id'),
                "symbol": symbol_name,
                "screening_date": date_str,
                "status": status,
                "error": result.get('error') if status == 'failed' else None
            })
        
        # Return summary
        return {
            "total_backtests": total_backtests,
            "successful_starts": successful_count,
            "failed_starts": failed_count,
            "screening_days": len(symbols_by_date),
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "backtests_by_date": symbols_by_date,
            "backtests": backtest_tasks
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting screener backtests: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/examples")
async def get_example_requests():
    """Get example backtest requests for common strategies."""
    examples = [
        {
            "name": "Simple Buy and Hold",
            "description": "Basic buy and hold strategy for SPY",
            "request": {
                "strategy_name": "main",
                "start_date": "2013-10-07",
                "end_date": "2013-10-11",
                "initial_cash": 100000,
                "symbols": ["SPY"],
                "resolution": "Minute"
            }
        },
        {
            "name": "Multi-Symbol Portfolio",
            "description": "Test strategy with multiple symbols",
            "request": {
                "strategy_name": "main",
                "start_date": "2013-10-01",
                "end_date": "2013-10-31",
                "initial_cash": 250000,
                "symbols": ["SPY", "QQQ", "IWM"],
                "resolution": "Hour",
                "parameters": {
                    "risk_level": "moderate"
                }
            }
        },
        {
            "name": "High Frequency Test",
            "description": "Test with second-level data",
            "request": {
                "strategy_name": "main",
                "start_date": "2013-10-07",
                "end_date": "2013-10-07",
                "initial_cash": 50000,
                "symbols": ["SPY"],
                "resolution": "Second"
            }
        }
    ]
    
    return {"examples": examples}


@router.get("/db/results", response_model=BacktestListResponse)
async def list_backtest_results_from_db(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    strategy_name: Optional[str] = Query(None, description="Filter by strategy name"),
    initial_cash: Optional[float] = Query(None, description="Filter by initial cash amount"),
    pivot_bars: Optional[int] = Query(None, description="Filter by pivot bars setting"),
    lower_timeframe: Optional[str] = Query(None, description="Filter by lower timeframe"),
    start_date: Optional[date] = Query(None, description="Filter results after this date"),
    end_date: Optional[date] = Query(None, description="Filter results before this date"),
    sort_by: Optional[str] = Query("created_at", description="Sort by field (created_at, total_return, sharpe_ratio, max_drawdown, win_rate, profit_factor)"),
    sort_order: Optional[str] = Query("desc", description="Sort order (asc, desc)")
):
    """
    List historical backtest results from database with pagination and comprehensive filtering.
    
    This endpoint reads from the market_structure_results table with enhanced schema support.
    
    Args:
        page: Page number (1-based)
        page_size: Number of results per page
        symbol: Optional filter by symbol
        strategy_name: Optional filter by strategy name
        initial_cash: Optional filter by initial cash amount
        pivot_bars: Optional filter by pivot bars setting
        lower_timeframe: Optional filter by lower timeframe
        start_date: Optional filter for results after this date
        end_date: Optional filter for results before this date
        sort_by: Sort by field (created_at, total_return, sharpe_ratio, max_drawdown, win_rate, profit_factor)
        sort_order: Sort order (asc, desc)
        
    Returns:
        Paginated list of backtest results with comprehensive metrics
    """
    try:
        # Validate input parameters
        if page_size > 100:
            raise HTTPException(status_code=400, detail="page_size cannot exceed 100")
        
        if initial_cash is not None and initial_cash <= 0:
            raise HTTPException(status_code=400, detail="initial_cash must be greater than 0")
        
        if pivot_bars is not None and pivot_bars <= 0:
            raise HTTPException(status_code=400, detail="pivot_bars must be greater than 0")
        
        if start_date and end_date and end_date < start_date:
            raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
        
        # Validate sort parameters
        valid_sort_fields = ['created_at', 'total_return', 'sharpe_ratio', 'max_drawdown', 'win_rate', 'profit_factor', 'net_profit', 'compounding_annual_return']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        sort_order = sort_order.lower()
        if sort_order not in ['asc', 'desc']:
            sort_order = 'desc'
        
        # Build comprehensive query to fetch all new performance metrics
        query = """
        SELECT 
            id,
            backtest_id,
            symbol,
            strategy_name,
            start_date,
            end_date,
            initial_cash,
            resolution,
            pivot_bars,
            lower_timeframe,
            -- Core Performance Results
            total_return,
            net_profit,
            net_profit_currency,
            compounding_annual_return,
            final_value,
            start_equity,
            end_equity,
            -- Risk Metrics
            sharpe_ratio,
            sortino_ratio,
            max_drawdown,
            probabilistic_sharpe_ratio,
            annual_standard_deviation,
            annual_variance,
            beta,
            alpha,
            -- Trading Statistics
            total_trades,
            winning_trades,
            losing_trades,
            win_rate,
            loss_rate,
            average_win,
            average_loss,
            profit_factor,
            profit_loss_ratio,
            expectancy,
            total_orders,
            -- Advanced Metrics
            information_ratio,
            tracking_error,
            treynor_ratio,
            total_fees,
            estimated_strategy_capacity,
            lowest_capacity_asset,
            portfolio_turnover,
            -- Strategy-Specific Metrics
            pivot_highs_detected,
            pivot_lows_detected,
            bos_signals_generated,
            position_flips,
            liquidation_events,
            -- Execution Metadata
            execution_time_ms,
            result_path,
            status,
            error_message,
            cache_hit,
            created_at
        FROM market_structure_results
        WHERE 1=1
        """
        params = []
        param_count = 0
        
        # Add cache key parameter filters
        if symbol:
            param_count += 1
            query += f" AND symbol = ${param_count}"
            params.append(symbol)
            
        if strategy_name:
            param_count += 1
            query += f" AND strategy_name = ${param_count}"
            params.append(strategy_name)
            
        if initial_cash is not None:
            param_count += 1
            query += f" AND initial_cash = ${param_count}"
            params.append(initial_cash)
            
        if pivot_bars is not None:
            param_count += 1
            query += f" AND pivot_bars = ${param_count}"
            params.append(pivot_bars)
            
        if lower_timeframe:
            param_count += 1
            query += f" AND lower_timeframe = ${param_count}"
            params.append(lower_timeframe)
            
        # Add date filters
        if start_date:
            param_count += 1
            query += f" AND start_date >= ${param_count}"
            params.append(start_date)
            
        if end_date:
            param_count += 1
            query += f" AND end_date <= ${param_count}"
            params.append(end_date)
            
        # Add ordering with proper null handling
        query += f" ORDER BY {sort_by} {sort_order.upper()} NULLS LAST"
        
        # Get total count for pagination
        count_query = "SELECT COUNT(*) FROM market_structure_results WHERE 1=1"
        count_params = []
        count_param_num = 0
        
        # Apply same filters to count query
        if symbol:
            count_param_num += 1
            count_query += f" AND symbol = ${count_param_num}"
            count_params.append(symbol)
            
        if strategy_name:
            count_param_num += 1
            count_query += f" AND strategy_name = ${count_param_num}"
            count_params.append(strategy_name)
            
        if initial_cash is not None:
            count_param_num += 1
            count_query += f" AND initial_cash = ${count_param_num}"
            count_params.append(initial_cash)
            
        if pivot_bars is not None:
            count_param_num += 1
            count_query += f" AND pivot_bars = ${count_param_num}"
            count_params.append(pivot_bars)
            
        if lower_timeframe:
            count_param_num += 1
            count_query += f" AND lower_timeframe = ${count_param_num}"
            count_params.append(lower_timeframe)
            
        if start_date:
            count_param_num += 1
            count_query += f" AND start_date >= ${count_param_num}"
            count_params.append(start_date)
            
        if end_date:
            count_param_num += 1
            count_query += f" AND end_date <= ${count_param_num}"
            count_params.append(end_date)
        
        total_count = await db_pool.fetchval(count_query, *count_params)
        
        # Add limit and offset for pagination
        param_count += 1
        query += f" LIMIT ${param_count}"
        params.append(page_size)
        
        param_count += 1
        query += f" OFFSET ${param_count}"
        params.append((page - 1) * page_size)
        
        # Execute query
        rows = await db_pool.fetch(query, *params)
        
        # Convert to response models using comprehensive data
        results = []
        skipped_count = 0
        for row in rows:
            try:
                # Create BacktestStatistics with all available metrics
                backtest_stats = BacktestStatistics(
                    # Core Performance Metrics
                    total_return=float(row['total_return']) if row['total_return'] is not None else 0,
                    net_profit=float(row['net_profit']) if row['net_profit'] is not None else 0,
                    net_profit_currency=float(row['net_profit_currency']) if row['net_profit_currency'] is not None else 0,
                    compounding_annual_return=float(row['compounding_annual_return']) if row['compounding_annual_return'] is not None else 0,
                    final_value=float(row['final_value']) if row['final_value'] is not None else 0,
                    start_equity=float(row['start_equity']) if row['start_equity'] is not None else 0,
                    end_equity=float(row['end_equity']) if row['end_equity'] is not None else 0,
                    
                    # Risk Metrics
                    sharpe_ratio=float(row['sharpe_ratio']) if row['sharpe_ratio'] is not None else 0,
                    sortino_ratio=float(row['sortino_ratio']) if row['sortino_ratio'] is not None else 0,
                    max_drawdown=float(row['max_drawdown']) if row['max_drawdown'] is not None else 0,
                    probabilistic_sharpe_ratio=float(row['probabilistic_sharpe_ratio']) if row['probabilistic_sharpe_ratio'] is not None else 0,
                    annual_standard_deviation=float(row['annual_standard_deviation']) if row['annual_standard_deviation'] is not None else 0,
                    annual_variance=float(row['annual_variance']) if row['annual_variance'] is not None else 0,
                    beta=float(row['beta']) if row['beta'] is not None else 0,
                    alpha=float(row['alpha']) if row['alpha'] is not None else 0,
                    
                    # Trading Statistics
                    total_orders=int(row['total_orders']) if row['total_orders'] is not None else 0,
                    total_trades=int(row['total_trades']) if row['total_trades'] is not None else 0,
                    winning_trades=int(row['winning_trades']) if row['winning_trades'] is not None else 0,
                    losing_trades=int(row['losing_trades']) if row['losing_trades'] is not None else 0,
                    win_rate=float(row['win_rate']) if row['win_rate'] is not None else 0,
                    loss_rate=float(row['loss_rate']) if row['loss_rate'] is not None else 0,
                    average_win=float(row['average_win']) if row['average_win'] is not None else 0,
                    average_loss=float(row['average_loss']) if row['average_loss'] is not None else 0,
                    profit_factor=float(row['profit_factor']) if row['profit_factor'] is not None else 0,
                    profit_loss_ratio=float(row['profit_loss_ratio']) if row['profit_loss_ratio'] is not None else 0,
                    expectancy=float(row['expectancy']) if row['expectancy'] is not None else 0,
                    
                    # Advanced Metrics
                    information_ratio=float(row['information_ratio']) if row['information_ratio'] is not None else 0,
                    tracking_error=float(row['tracking_error']) if row['tracking_error'] is not None else 0,
                    treynor_ratio=float(row['treynor_ratio']) if row['treynor_ratio'] is not None else 0,
                    total_fees=float(row['total_fees']) if row['total_fees'] is not None else 0,
                    estimated_strategy_capacity=float(row['estimated_strategy_capacity']) if row['estimated_strategy_capacity'] is not None else 1000000,
                    lowest_capacity_asset=row['lowest_capacity_asset'] if row['lowest_capacity_asset'] else row['symbol'],
                    portfolio_turnover=float(row['portfolio_turnover']) if row['portfolio_turnover'] is not None else 0,
                    
                    # Strategy-Specific Metrics
                    pivot_highs_detected=int(row['pivot_highs_detected']) if row['pivot_highs_detected'] is not None else None,
                    pivot_lows_detected=int(row['pivot_lows_detected']) if row['pivot_lows_detected'] is not None else None,
                    bos_signals_generated=int(row['bos_signals_generated']) if row['bos_signals_generated'] is not None else None,
                    position_flips=int(row['position_flips']) if row['position_flips'] is not None else None,
                    liquidation_events=int(row['liquidation_events']) if row['liquidation_events'] is not None else None
                )
                
                # Create BacktestResult with comprehensive data
                result = BacktestResult(
                    backtest_id=row['backtest_id'],
                    symbol=row['symbol'],
                    strategy_name=row['strategy_name'] if row['strategy_name'] else 'MarketStructure',
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    initial_cash=float(row['initial_cash']) if row['initial_cash'] is not None else 100000,
                    resolution=row['resolution'] if row['resolution'] else 'Minute',
                    pivot_bars=int(row['pivot_bars']) if row['pivot_bars'] is not None else 5,
                    lower_timeframe=row['lower_timeframe'] if row['lower_timeframe'] else '5min',
                    final_value=float(row['final_value']) if row['final_value'] is not None else 0,
                    statistics=backtest_stats,
                    execution_time_ms=int(row['execution_time_ms']) if row['execution_time_ms'] is not None else None,
                    result_path=row['result_path'] if row['result_path'] else f"db:{str(row['id'])}",
                    status=row['status'] if row['status'] else 'completed',
                    error_message=row['error_message'],
                    cache_hit=row['cache_hit'],
                    orders=None,  # Orders not included in list view
                    equity_curve=None,  # Equity curve not included in list view
                    created_at=row['created_at']
                )
                results.append(result)
            except Exception as e:
                # Skip this result and log the error
                skipped_count += 1
                logger.warning(f"Skipping backtest result due to validation error: {e}. Row ID: {row.get('id', 'unknown')}")
                continue
        
        # Log if any results were skipped
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} backtest results due to validation errors")
        
        return BacktestListResponse(
            results=results,
            total_count=int(total_count) if total_count else 0,
            page=page,
            page_size=page_size
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error in list_backtest_results_from_db: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing backtest results from database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve backtest results: {str(e)}")


@router.get("/db/results/{result_id}", response_model=BacktestResult)
async def get_backtest_result_from_db(result_id: str):
    """
    Get detailed backtest result from database with comprehensive metrics.
    
    This endpoint reads from the market_structure_results table with enhanced schema support.
    
    Args:
        result_id: The backtest_id (cache hash)
        
    Returns:
        Complete backtest result including all performance statistics and metadata
    """
    try:
        # No validation needed for cache hash - it's a string
        
        # Query the market_structure_results table with all comprehensive fields
        query = """
        SELECT 
            id,
            backtest_id,
            symbol,
            strategy_name,
            start_date,
            end_date,
            initial_cash,
            resolution,
            pivot_bars,
            lower_timeframe,
            -- Core Performance Results
            total_return,
            net_profit,
            net_profit_currency,
            compounding_annual_return,
            final_value,
            start_equity,
            end_equity,
            -- Risk Metrics
            sharpe_ratio,
            sortino_ratio,
            max_drawdown,
            probabilistic_sharpe_ratio,
            annual_standard_deviation,
            annual_variance,
            beta,
            alpha,
            -- Trading Statistics
            total_trades,
            winning_trades,
            losing_trades,
            win_rate,
            loss_rate,
            average_win,
            average_loss,
            profit_factor,
            profit_loss_ratio,
            expectancy,
            total_orders,
            -- Advanced Metrics
            information_ratio,
            tracking_error,
            treynor_ratio,
            total_fees,
            estimated_strategy_capacity,
            lowest_capacity_asset,
            portfolio_turnover,
            -- Strategy-Specific Metrics
            pivot_highs_detected,
            pivot_lows_detected,
            bos_signals_generated,
            position_flips,
            liquidation_events,
            -- Execution Metadata
            execution_time_ms,
            result_path,
            status,
            error_message,
            cache_hit,
            created_at
        FROM market_structure_results
        WHERE backtest_id = $1
        """
        
        row = await db_pool.fetchrow(query, result_id)
        
        if not row:
            raise HTTPException(status_code=404, detail=f"Backtest result '{result_id}' not found")
        
        try:
            # Create BacktestStatistics with all comprehensive metrics
            backtest_stats = BacktestStatistics(
                # Core Performance Metrics
                total_return=float(row['total_return']) if row['total_return'] is not None else 0,
                net_profit=float(row['net_profit']) if row['net_profit'] is not None else 0,
                net_profit_currency=float(row['net_profit_currency']) if row['net_profit_currency'] is not None else 0,
                compounding_annual_return=float(row['compounding_annual_return']) if row['compounding_annual_return'] is not None else 0,
                final_value=float(row['final_value']) if row['final_value'] is not None else 0,
                start_equity=float(row['start_equity']) if row['start_equity'] is not None else 0,
                end_equity=float(row['end_equity']) if row['end_equity'] is not None else 0,
                
                # Risk Metrics
                sharpe_ratio=float(row['sharpe_ratio']) if row['sharpe_ratio'] is not None else 0,
                sortino_ratio=float(row['sortino_ratio']) if row['sortino_ratio'] is not None else 0,
                max_drawdown=float(row['max_drawdown']) if row['max_drawdown'] is not None else 0,
                probabilistic_sharpe_ratio=float(row['probabilistic_sharpe_ratio']) if row['probabilistic_sharpe_ratio'] is not None else 0,
                annual_standard_deviation=float(row['annual_standard_deviation']) if row['annual_standard_deviation'] is not None else 0,
                annual_variance=float(row['annual_variance']) if row['annual_variance'] is not None else 0,
                beta=float(row['beta']) if row['beta'] is not None else 0,
                alpha=float(row['alpha']) if row['alpha'] is not None else 0,
                
                # Trading Statistics
                total_orders=int(row['total_orders']) if row['total_orders'] is not None else 0,
                total_trades=int(row['total_trades']) if row['total_trades'] is not None else 0,
                winning_trades=int(row['winning_trades']) if row['winning_trades'] is not None else 0,
                losing_trades=int(row['losing_trades']) if row['losing_trades'] is not None else 0,
                win_rate=float(row['win_rate']) if row['win_rate'] is not None else 0,
                loss_rate=float(row['loss_rate']) if row['loss_rate'] is not None else 0,
                average_win=float(row['average_win']) if row['average_win'] is not None else 0,
                average_loss=float(row['average_loss']) if row['average_loss'] is not None else 0,
                profit_factor=float(row['profit_factor']) if row['profit_factor'] is not None else 0,
                profit_loss_ratio=float(row['profit_loss_ratio']) if row['profit_loss_ratio'] is not None else 0,
                expectancy=float(row['expectancy']) if row['expectancy'] is not None else 0,
                
                # Advanced Metrics
                information_ratio=float(row['information_ratio']) if row['information_ratio'] is not None else 0,
                tracking_error=float(row['tracking_error']) if row['tracking_error'] is not None else 0,
                treynor_ratio=float(row['treynor_ratio']) if row['treynor_ratio'] is not None else 0,
                total_fees=float(row['total_fees']) if row['total_fees'] is not None else 0,
                estimated_strategy_capacity=float(row['estimated_strategy_capacity']) if row['estimated_strategy_capacity'] is not None else 1000000,
                lowest_capacity_asset=row['lowest_capacity_asset'] if row['lowest_capacity_asset'] else row['symbol'],
                portfolio_turnover=float(row['portfolio_turnover']) if row['portfolio_turnover'] is not None else 0,
                
                # Strategy-Specific Metrics
                pivot_highs_detected=int(row['pivot_highs_detected']) if row['pivot_highs_detected'] is not None else None,
                pivot_lows_detected=int(row['pivot_lows_detected']) if row['pivot_lows_detected'] is not None else None,
                bos_signals_generated=int(row['bos_signals_generated']) if row['bos_signals_generated'] is not None else None,
                position_flips=int(row['position_flips']) if row['position_flips'] is not None else None,
                liquidation_events=int(row['liquidation_events']) if row['liquidation_events'] is not None else None
            )
            
            # Create BacktestResult with comprehensive data
            result = BacktestResult(
                backtest_id=row['backtest_id'],
                symbol=row['symbol'],
                strategy_name=row['strategy_name'] if row['strategy_name'] else 'MarketStructure',
                start_date=row['start_date'],
                end_date=row['end_date'],
                initial_cash=float(row['initial_cash']) if row['initial_cash'] is not None else 100000,
                resolution=row['resolution'] if row['resolution'] else 'Minute',
                pivot_bars=int(row['pivot_bars']) if row['pivot_bars'] is not None else 5,
                lower_timeframe=row['lower_timeframe'] if row['lower_timeframe'] else '5min',
                final_value=float(row['final_value']) if row['final_value'] is not None else 0,
                statistics=backtest_stats,
                execution_time_ms=int(row['execution_time_ms']) if row['execution_time_ms'] is not None else None,
                result_path=row['result_path'] if row['result_path'] else f"db:{str(row['id'])}",
                status=row['status'] if row['status'] else 'completed',
                error_message=row['error_message'],
                cache_hit=row['cache_hit'],
                # For detailed view, we could include orders and equity curve if they're stored separately
                # For now, they remain None as they're not part of the current schema design
                orders=None,
                equity_curve=None,
                created_at=row['created_at']
            )
            
            return result
        except Exception as e:
            logger.error(f"Error parsing backtest result from database: {e}. Row ID: {row.get('id', 'unknown')}")
            raise HTTPException(status_code=404, detail=f"Backtest result has invalid data and cannot be displayed")
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error in get_backtest_result_from_db: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting backtest result from database: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve backtest result: {str(e)}")


@router.get("/db/cache-lookup", response_model=BacktestResult)
async def lookup_cached_backtest_result(
    symbol: str = Query(..., description="Stock symbol"),
    strategy_name: str = Query(..., description="Strategy name"),
    start_date: date = Query(..., description="Backtest start date"),
    end_date: date = Query(..., description="Backtest end date"),
    initial_cash: float = Query(..., description="Initial cash amount"),
    pivot_bars: int = Query(..., description="Pivot bars setting"),
    lower_timeframe: str = Query(..., description="Lower timeframe")
):
    """
    Lookup cached backtest result using cache key parameters.
    
    This endpoint uses the composite index on cache key parameters for optimal performance.
    All cache key parameters are required to perform the lookup.
    
    Args:
        symbol: Stock symbol
        strategy_name: Strategy name
        start_date: Backtest start date
        end_date: Backtest end date
        initial_cash: Initial cash amount
        pivot_bars: Pivot bars setting
        lower_timeframe: Lower timeframe
        
    Returns:
        Cached backtest result if found
    """
    try:
        # Validate input parameters
        if pivot_bars <= 0:
            raise HTTPException(status_code=400, detail="pivot_bars must be greater than 0")
        
        if initial_cash <= 0:
            raise HTTPException(status_code=400, detail="initial_cash must be greater than 0")
        
        if end_date < start_date:
            raise HTTPException(status_code=400, detail="end_date must be on or after start_date")
        
        # Query using the composite index on cache key parameters
        # This should be extremely fast due to the index: (symbol, strategy_name, start_date, end_date, initial_cash, pivot_bars, lower_timeframe)
        query = """
        SELECT 
            id,
            backtest_id,
            symbol,
            strategy_name,
            start_date,
            end_date,
            initial_cash,
            resolution,
            pivot_bars,
            lower_timeframe,
            -- Core Performance Results
            total_return,
            net_profit,
            net_profit_currency,
            compounding_annual_return,
            final_value,
            start_equity,
            end_equity,
            -- Risk Metrics
            sharpe_ratio,
            sortino_ratio,
            max_drawdown,
            probabilistic_sharpe_ratio,
            annual_standard_deviation,
            annual_variance,
            beta,
            alpha,
            -- Trading Statistics
            total_trades,
            winning_trades,
            losing_trades,
            win_rate,
            loss_rate,
            average_win,
            average_loss,
            profit_factor,
            profit_loss_ratio,
            expectancy,
            total_orders,
            -- Advanced Metrics
            information_ratio,
            tracking_error,
            treynor_ratio,
            total_fees,
            estimated_strategy_capacity,
            lowest_capacity_asset,
            portfolio_turnover,
            -- Strategy-Specific Metrics
            pivot_highs_detected,
            pivot_lows_detected,
            bos_signals_generated,
            position_flips,
            liquidation_events,
            -- Execution Metadata
            execution_time_ms,
            result_path,
            status,
            error_message,
            cache_hit,
            created_at
        FROM market_structure_results
        WHERE symbol = $1 
          AND strategy_name = $2 
          AND start_date = $3 
          AND end_date = $4 
          AND initial_cash = $5 
          AND pivot_bars = $6 
          AND lower_timeframe = $7
        ORDER BY created_at DESC
        LIMIT 1
        """
        
        row = await db_pool.fetchrow(
            query, 
            symbol, 
            strategy_name, 
            start_date, 
            end_date, 
            initial_cash, 
            pivot_bars, 
            lower_timeframe
        )
        
        if not row:
            raise HTTPException(
                status_code=404, 
                detail=f"No cached backtest result found for the specified parameters"
            )
        
        try:
            # Create comprehensive BacktestStatistics
            backtest_stats = BacktestStatistics(
                # Core Performance Metrics
                total_return=float(row['total_return']) if row['total_return'] is not None else 0,
                net_profit=float(row['net_profit']) if row['net_profit'] is not None else 0,
                net_profit_currency=float(row['net_profit_currency']) if row['net_profit_currency'] is not None else 0,
                compounding_annual_return=float(row['compounding_annual_return']) if row['compounding_annual_return'] is not None else 0,
                final_value=float(row['final_value']) if row['final_value'] is not None else 0,
                start_equity=float(row['start_equity']) if row['start_equity'] is not None else 0,
                end_equity=float(row['end_equity']) if row['end_equity'] is not None else 0,
                
                # Risk Metrics
                sharpe_ratio=float(row['sharpe_ratio']) if row['sharpe_ratio'] is not None else 0,
                sortino_ratio=float(row['sortino_ratio']) if row['sortino_ratio'] is not None else 0,
                max_drawdown=float(row['max_drawdown']) if row['max_drawdown'] is not None else 0,
                probabilistic_sharpe_ratio=float(row['probabilistic_sharpe_ratio']) if row['probabilistic_sharpe_ratio'] is not None else 0,
                annual_standard_deviation=float(row['annual_standard_deviation']) if row['annual_standard_deviation'] is not None else 0,
                annual_variance=float(row['annual_variance']) if row['annual_variance'] is not None else 0,
                beta=float(row['beta']) if row['beta'] is not None else 0,
                alpha=float(row['alpha']) if row['alpha'] is not None else 0,
                
                # Trading Statistics
                total_orders=int(row['total_orders']) if row['total_orders'] is not None else 0,
                total_trades=int(row['total_trades']) if row['total_trades'] is not None else 0,
                winning_trades=int(row['winning_trades']) if row['winning_trades'] is not None else 0,
                losing_trades=int(row['losing_trades']) if row['losing_trades'] is not None else 0,
                win_rate=float(row['win_rate']) if row['win_rate'] is not None else 0,
                loss_rate=float(row['loss_rate']) if row['loss_rate'] is not None else 0,
                average_win=float(row['average_win']) if row['average_win'] is not None else 0,
                average_loss=float(row['average_loss']) if row['average_loss'] is not None else 0,
                profit_factor=float(row['profit_factor']) if row['profit_factor'] is not None else 0,
                profit_loss_ratio=float(row['profit_loss_ratio']) if row['profit_loss_ratio'] is not None else 0,
                expectancy=float(row['expectancy']) if row['expectancy'] is not None else 0,
                
                # Advanced Metrics
                information_ratio=float(row['information_ratio']) if row['information_ratio'] is not None else 0,
                tracking_error=float(row['tracking_error']) if row['tracking_error'] is not None else 0,
                treynor_ratio=float(row['treynor_ratio']) if row['treynor_ratio'] is not None else 0,
                total_fees=float(row['total_fees']) if row['total_fees'] is not None else 0,
                estimated_strategy_capacity=float(row['estimated_strategy_capacity']) if row['estimated_strategy_capacity'] is not None else 1000000,
                lowest_capacity_asset=row['lowest_capacity_asset'] if row['lowest_capacity_asset'] else row['symbol'],
                portfolio_turnover=float(row['portfolio_turnover']) if row['portfolio_turnover'] is not None else 0,
                
                # Strategy-Specific Metrics
                pivot_highs_detected=int(row['pivot_highs_detected']) if row['pivot_highs_detected'] is not None else None,
                pivot_lows_detected=int(row['pivot_lows_detected']) if row['pivot_lows_detected'] is not None else None,
                bos_signals_generated=int(row['bos_signals_generated']) if row['bos_signals_generated'] is not None else None,
                position_flips=int(row['position_flips']) if row['position_flips'] is not None else None,
                liquidation_events=int(row['liquidation_events']) if row['liquidation_events'] is not None else None
            )
            
            # Create comprehensive BacktestResult
            result = BacktestResult(
                backtest_id=str(row['id']),
                symbol=row['symbol'],
                strategy_name=row['strategy_name'] if row['strategy_name'] else 'MarketStructure',
                start_date=row['start_date'],
                end_date=row['end_date'],
                initial_cash=float(row['initial_cash']) if row['initial_cash'] is not None else 100000,
                resolution=row['resolution'] if row['resolution'] else 'Minute',
                pivot_bars=int(row['pivot_bars']) if row['pivot_bars'] is not None else 5,
                lower_timeframe=row['lower_timeframe'] if row['lower_timeframe'] else '5min',
                final_value=float(row['final_value']) if row['final_value'] is not None else 0,
                statistics=backtest_stats,
                execution_time_ms=int(row['execution_time_ms']) if row['execution_time_ms'] is not None else None,
                result_path=row['result_path'] if row['result_path'] else f"db:{str(row['id'])}",
                status=row['status'] if row['status'] else 'completed',
                error_message=row['error_message'],
                cache_hit=True,  # This is definitely a cache hit since we found an existing result
                orders=None,
                equity_curve=None,
                created_at=row['created_at']
            )
            
            return result
        except Exception as e:
            logger.error(f"Error parsing cached backtest result: {e}. Row ID: {row.get('id', 'unknown')}")
            raise HTTPException(
                status_code=404, 
                detail=f"Cached backtest result has invalid data and cannot be displayed"
            )
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Validation error in cache lookup: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error performing cache lookup: {e}")
        raise HTTPException(status_code=500, detail=f"Cache lookup failed: {str(e)}")


@router.delete("/db/results/{result_id}")
async def delete_backtest_result_from_db(result_id: str):
    """
    Delete a backtest result from database.
    
    Args:
        result_id: The result ID to delete
        
    Returns:
        Success message if deleted
    """
    try:
        # Validate UUID format
        try:
            from uuid import UUID
            UUID(result_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid result ID format")
        
        # Delete from database with new table name
        query = "DELETE FROM market_structure_results WHERE backtest_id = $1 RETURNING backtest_id"
        
        deleted_id = await db_pool.fetchval(query, result_id)
        
        if not deleted_id:
            raise HTTPException(status_code=404, detail=f"Backtest result '{result_id}' not found")
        
        return {"message": f"Backtest result '{result_id}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting backtest result from database: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/db/statistics")
async def get_backtest_statistics(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    strategy_name: Optional[str] = Query(None, description="Filter by strategy name"),
    start_date: Optional[date] = Query(None, description="Filter results after this date"),
    end_date: Optional[date] = Query(None, description="Filter results before this date")
):
    """
    Get aggregated statistics across multiple backtest results.
    
    This endpoint provides summary statistics and insights across filtered backtest results,
    useful for analyzing performance patterns and strategy effectiveness.
    
    Args:
        symbol: Optional filter by symbol
        strategy_name: Optional filter by strategy name
        start_date: Optional filter for results after this date
        end_date: Optional filter for results before this date
        
    Returns:
        Aggregated statistics including count, averages, and performance metrics
    """
    try:
        # Build base query with filters
        where_conditions = []
        params = []
        param_count = 0
        
        if symbol:
            param_count += 1
            where_conditions.append(f"symbol = ${param_count}")
            params.append(symbol)
            
        if strategy_name:
            param_count += 1
            where_conditions.append(f"strategy_name = ${param_count}")
            params.append(strategy_name)
            
        if start_date:
            param_count += 1
            where_conditions.append(f"start_date >= ${param_count}")
            params.append(start_date)
            
        if end_date:
            param_count += 1
            where_conditions.append(f"end_date <= ${param_count}")
            params.append(end_date)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get comprehensive statistics
        query = f"""
        SELECT 
            COUNT(*) as total_backtests,
            COUNT(DISTINCT symbol) as unique_symbols,
            COUNT(DISTINCT strategy_name) as unique_strategies,
            AVG(total_return) as avg_total_return,
            STDDEV(total_return) as stddev_total_return,
            MIN(total_return) as min_total_return,
            MAX(total_return) as max_total_return,
            AVG(sharpe_ratio) as avg_sharpe_ratio,
            AVG(max_drawdown) as avg_max_drawdown,
            AVG(win_rate) as avg_win_rate,
            AVG(profit_factor) as avg_profit_factor,
            AVG(total_trades) as avg_total_trades,
            AVG(execution_time_ms) as avg_execution_time_ms,
            COUNT(CASE WHEN cache_hit = true THEN 1 END) as cache_hits,
            COUNT(CASE WHEN total_return > 0 THEN 1 END) as profitable_backtests,
            MIN(created_at) as earliest_backtest,
            MAX(created_at) as latest_backtest
        FROM market_structure_results
        {where_clause}
        """
        
        row = await db_pool.fetchrow(query, *params)
        
        if not row or row['total_backtests'] == 0:
            return {
                "total_backtests": 0,
                "message": "No backtest results found matching the specified criteria"
            }
        
        # Calculate additional metrics
        cache_hit_rate = (row['cache_hits'] / row['total_backtests'] * 100) if row['total_backtests'] > 0 else 0
        profitability_rate = (row['profitable_backtests'] / row['total_backtests'] * 100) if row['total_backtests'] > 0 else 0
        
        # Get top performers
        top_performers_query = f"""
        SELECT symbol, strategy_name, total_return, sharpe_ratio, created_at
        FROM market_structure_results
        {where_clause}
        ORDER BY total_return DESC
        LIMIT 5
        """
        
        top_performers = await db_pool.fetch(top_performers_query, *params)
        
        return {
            "summary": {
                "total_backtests": int(row['total_backtests']),
                "unique_symbols": int(row['unique_symbols']),
                "unique_strategies": int(row['unique_strategies']),
                "cache_hit_rate": round(cache_hit_rate, 2),
                "profitability_rate": round(profitability_rate, 2),
                "date_range": {
                    "earliest": row['earliest_backtest'].isoformat() if row['earliest_backtest'] else None,
                    "latest": row['latest_backtest'].isoformat() if row['latest_backtest'] else None
                }
            },
            "performance_metrics": {
                "returns": {
                    "average": round(float(row['avg_total_return']), 4) if row['avg_total_return'] else 0,
                    "standard_deviation": round(float(row['stddev_total_return']), 4) if row['stddev_total_return'] else 0,
                    "minimum": round(float(row['min_total_return']), 4) if row['min_total_return'] else 0,
                    "maximum": round(float(row['max_total_return']), 4) if row['max_total_return'] else 0
                },
                "risk_metrics": {
                    "average_sharpe_ratio": round(float(row['avg_sharpe_ratio']), 4) if row['avg_sharpe_ratio'] else 0,
                    "average_max_drawdown": round(float(row['avg_max_drawdown']), 4) if row['avg_max_drawdown'] else 0
                },
                "trading_metrics": {
                    "average_win_rate": round(float(row['avg_win_rate']), 4) if row['avg_win_rate'] else 0,
                    "average_profit_factor": round(float(row['avg_profit_factor']), 4) if row['avg_profit_factor'] else 0,
                    "average_total_trades": round(float(row['avg_total_trades']), 2) if row['avg_total_trades'] else 0
                }
            },
            "execution_metrics": {
                "average_execution_time_ms": round(float(row['avg_execution_time_ms']), 2) if row['avg_execution_time_ms'] else 0,
                "cache_hits": int(row['cache_hits']),
                "profitable_backtests": int(row['profitable_backtests'])
            },
            "top_performers": [
                {
                    "symbol": performer['symbol'],
                    "strategy_name": performer['strategy_name'],
                    "total_return": round(float(performer['total_return']), 4) if performer['total_return'] else 0,
                    "sharpe_ratio": round(float(performer['sharpe_ratio']), 4) if performer['sharpe_ratio'] else 0,
                    "created_at": performer['created_at'].isoformat()
                }
                for performer in top_performers
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting backtest statistics: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve statistics: {str(e)}")


@router.get("/db/results/{backtest_id}/trades", response_model=List[Dict[str, Any]])
async def get_backtest_trades(
    backtest_id: str,
    limit: int = Query(50, description="Maximum number of trades to return", ge=1, le=500)
):
    """
    Get trades for a specific backtest result.
    Returns the last N trades (default 50) ordered by trade time descending.
    """
    try:
        # First verify the backtest exists
        backtest_exists = await db_pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM market_structure_results WHERE backtest_id = $1)",
            backtest_id
        )
        
        if not backtest_exists:
            raise HTTPException(status_code=404, detail=f"Backtest result {backtest_id} not found")
        
        # Fetch trades ordered by trade time descending (most recent first)
        # Then limit to the requested number
        query = """
            SELECT 
                symbol_value,
                trade_time AT TIME ZONE 'America/New_York' as trade_time_et,
                direction,
                quantity,
                fill_price,
                order_fee_amount,
                fill_quantity,
                trade_time_unix
            FROM backtest_trades
            WHERE backtest_id = $1
            ORDER BY trade_time DESC
            LIMIT $2
        """
        
        rows = await db_pool.fetch(query, backtest_id, limit)
        
        # Convert to list of dicts with formatted data
        trades = []
        for row in rows:
            trades.append({
                "symbol": row['symbol_value'],
                "tradeTime": row['trade_time_et'].isoformat(),
                "tradeTimeUnix": row['trade_time_unix'],
                "direction": row['direction'],
                "quantity": abs(float(row['quantity'])),  # Make quantity positive
                "fillPrice": float(row['fill_price']) if row['fill_price'] else 0,
                "fillQuantity": float(row['fill_quantity']) if row['fill_quantity'] else abs(float(row['quantity'])),
                "orderFee": float(row['order_fee_amount']) if row['order_fee_amount'] else 0
            })
        
        # Return trades in chronological order (oldest first) for display
        trades.reverse()
        
        return trades
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching trades for backtest {backtest_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve trades: {str(e)}")