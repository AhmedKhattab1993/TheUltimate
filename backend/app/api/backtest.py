"""
API endpoints for backtesting functionality.
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, Query, Depends
from typing import List, Optional
import logging
import json

from ..models.backtest import (
    BacktestRequest, BacktestRunInfo, BacktestResult,
    BacktestListResponse, StrategyInfo, BacktestProgress, BacktestStatus
)
from ..services.backtest_manager import backtest_manager
from ..services.lean_runner import LeanRunner
from ..services.backtest_storage import BacktestStorage
from ..services.screener_results import screener_results_manager


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
            strategy_storage = BacktestStorage(strategy_name=strategy["name"])
            strategy_results = await strategy_storage.list_results(
                page=1,
                page_size=1000,  # Get all results for aggregation
                strategy_name=strategy_name
            )
            all_results.extend(strategy_results.results)
        
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