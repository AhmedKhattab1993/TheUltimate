"""
Central manager for backtest operations.
"""

import asyncio
import logging
import uuid
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from collections import defaultdict
from pathlib import Path

from ..models.backtest import (
    BacktestRequest, BacktestStatus, BacktestRunInfo,
    BacktestProgress, BacktestResult
)
from .lean_runner import LeanRunner
from .backtest_monitor import BacktestMonitor
from .backtest_storage import BacktestStorage


logger = logging.getLogger(__name__)


class BacktestManager:
    """Manages the lifecycle of backtests."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if not hasattr(self, 'initialized'):
            self.lean_runner = LeanRunner()
            self.monitor = BacktestMonitor()
            self.storage = BacktestStorage()
            self.active_backtests: Dict[str, BacktestRunInfo] = {}
            self.websocket_connections: Dict[str, List[Any]] = defaultdict(list)
            self.backtest_metadata_dir = Path("/home/ahmed/TheUltimate/backend/lean") / "backtest_metadata"
            self.backtest_metadata_dir.mkdir(exist_ok=True)
            self.initialized = True
            self._background_task = None
            
            # Background task will be started on first use
            self._ensure_background_task()
    
    def _ensure_background_task(self):
        """Ensure background monitoring task is running."""
        try:
            # Check if we have an event loop
            loop = asyncio.get_running_loop()
            # If we have a loop and no task, create one
            if self._background_task is None:
                self._background_task = asyncio.create_task(self._background_monitor())
        except RuntimeError:
            # No event loop running yet, task will be created when needed
            pass
    
    def _save_backtest_metadata(self, backtest_id: str, run_info: BacktestRunInfo):
        """Save backtest metadata to file for persistence."""
        try:
            metadata_file = self.backtest_metadata_dir / f"{backtest_id}.json"
            metadata = {
                "backtest_id": run_info.backtest_id,
                "status": run_info.status.value,
                "request": {
                    "strategy_name": run_info.request.strategy_name,
                    "start_date": run_info.request.start_date.isoformat(),
                    "end_date": run_info.request.end_date.isoformat(),
                    "initial_cash": run_info.request.initial_cash,
                    "symbols": run_info.request.symbols,
                    "resolution": run_info.request.resolution,
                    "parameters": run_info.request.parameters
                },
                "created_at": run_info.created_at.isoformat() if run_info.created_at else None,
                "started_at": run_info.started_at.isoformat() if run_info.started_at else None,
                "completed_at": run_info.completed_at.isoformat() if run_info.completed_at else None,
                "result_path": run_info.result_path,
                "error_message": run_info.error_message
            }
            
            with open(metadata_file, 'w') as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save backtest metadata for {backtest_id}: {e}")
    
    def _load_backtest_metadata(self, backtest_id: str) -> Optional[BacktestRunInfo]:
        """Load backtest metadata from file."""
        try:
            metadata_file = self.backtest_metadata_dir / f"{backtest_id}.json"
            if not metadata_file.exists():
                return None
                
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            # Reconstruct BacktestRequest
            request_data = metadata["request"]
            request = BacktestRequest(
                strategy_name=request_data["strategy_name"],
                start_date=datetime.fromisoformat(request_data["start_date"]).date(),
                end_date=datetime.fromisoformat(request_data["end_date"]).date(),
                initial_cash=request_data["initial_cash"],
                symbols=request_data["symbols"],
                resolution=request_data["resolution"],
                parameters=request_data.get("parameters", {})
            )
            
            # Create BacktestRunInfo
            run_info = BacktestRunInfo(
                backtest_id=metadata["backtest_id"],
                status=BacktestStatus(metadata["status"]),
                request=request,
                created_at=datetime.fromisoformat(metadata["created_at"]) if metadata["created_at"] else None,
                started_at=datetime.fromisoformat(metadata["started_at"]) if metadata["started_at"] else None,
                completed_at=datetime.fromisoformat(metadata["completed_at"]) if metadata["completed_at"] else None,
                result_path=metadata.get("result_path"),
                error_message=metadata.get("error_message")
            )
            
            return run_info
        except Exception as e:
            logger.error(f"Failed to load backtest metadata for {backtest_id}: {e}")
            return None
    
    def _determine_status_from_folder(self, result_path: str) -> BacktestStatus:
        """Determine backtest status by examining the result folder."""
        if not result_path:
            return BacktestStatus.FAILED
            
        result_dir = Path(result_path)
        if not result_dir.exists():
            return BacktestStatus.RUNNING
        
        # Check for LEAN completion indicators (LEAN uses numeric IDs, not "main")
        # Look for pattern: {number}.json and {number}-summary.json
        json_files = list(result_dir.glob("*.json"))
        summary_files = list(result_dir.glob("*-summary.json"))
        log_files = list(result_dir.glob("*.txt"))
        
        # Filter out non-result JSON files
        result_json_files = [f for f in json_files 
                           if f.name.replace('.json', '').isdigit()]
        
        # If we have numbered result files, it's completed
        if result_json_files or summary_files:
            return BacktestStatus.COMPLETED
            
        # Check log files for errors
        for log_file in log_files:
            if "log" in log_file.name.lower():
                try:
                    with open(log_file, 'r') as f:
                        log_content = f.read()
                        if "error" in log_content.lower() or "exception" in log_content.lower():
                            return BacktestStatus.FAILED
                except:
                    pass
        
        # If folder exists but no results yet, probably still running
        return BacktestStatus.RUNNING
    
    def _parse_lean_results(self, result_path: str, backtest_id: str) -> Optional[Dict[str, Any]]:
        """Parse LEAN result files and format for frontend."""
        if not result_path:
            return None
            
        result_dir = Path(result_path)
        if not result_dir.exists():
            return None
        
        # Find the summary JSON file (pattern: {number}-summary.json)
        summary_files = list(result_dir.glob("*-summary.json"))
        if not summary_files:
            return None
        
        try:
            summary_file = summary_files[0]  # Take first summary file
            with open(summary_file, 'r') as f:
                lean_data = json.load(f)
            
            # Extract timestamp from folder name (e.g., "2025-08-10_08-51-44")
            timestamp = result_dir.name
            
            # Parse statistics
            stats = lean_data.get('statistics', {})
            portfolio_stats = lean_data.get('totalPerformance', {}).get('portfolioStatistics', {})
            
            def safe_float(value, default=0.0):
                """Safely convert to float, handling string percentages and None values."""
                if value is None:
                    return default
                if isinstance(value, str):
                    # Remove % and convert
                    value = value.replace('%', '')
                    try:
                        return float(value)
                    except ValueError:
                        return default
                return float(value) if value else default
            
            # Format statistics for frontend
            statistics = {
                "totalReturn": safe_float(stats.get("Net Profit", "0").replace("%", "")),
                "sharpeRatio": safe_float(stats.get("Sharpe Ratio", "0")),
                "maxDrawdown": safe_float(stats.get("Drawdown", "0").replace("%", "")),
                "winRate": safe_float(stats.get("Win Rate", "0").replace("%", "")),
                "totalTrades": int(safe_float(stats.get("Total Orders", "0"))),
                "profitableTrades": int(safe_float(portfolio_stats.get("numberOfWinningTrades", 0))),
                "averageWin": safe_float(stats.get("Average Win", "0").replace("%", "")),
                "averageLoss": safe_float(stats.get("Average Loss", "0").replace("%", ""))
            }
            
            # Parse equity curve
            equity_curve = []
            charts = lean_data.get('charts', {})
            strategy_equity = charts.get('Strategy Equity', {})
            equity_series = strategy_equity.get('series', {}).get('Equity', {})
            equity_values = equity_series.get('values', [])
            
            for point in equity_values:
                if len(point) >= 2:
                    # Convert Unix timestamp to ISO string
                    timestamp_unix = point[0]
                    equity_value = point[1]  # Use the close value (second value)
                    
                    # Convert Unix timestamp to datetime
                    dt = datetime.fromtimestamp(timestamp_unix, tz=timezone.utc)
                    date_str = dt.isoformat()
                    
                    equity_curve.append({
                        "date": date_str,
                        "value": equity_value
                    })
            
            # Parse orders/trades
            orders = []
            closed_trades = lean_data.get('totalPerformance', {}).get('closedTrades', [])
            
            for trade in closed_trades:
                # LEAN closed trades don't have individual order details by default
                # For now, create a summary order for each trade
                if trade:
                    orders.append({
                        "time": trade.get("entryTime", ""),
                        "symbol": trade.get("symbol", ""),
                        "type": "Market",  # Default type
                        "direction": "Buy" if trade.get("quantity", 0) > 0 else "Sell",
                        "quantity": abs(trade.get("quantity", 0)),
                        "price": trade.get("entryPrice", 0),
                        "status": "Filled",
                        "fillPrice": trade.get("entryPrice", 0),
                        "fillTime": trade.get("entryTime", "")
                    })
                    
                    # Add exit order if available
                    if trade.get("exitTime") and trade.get("exitPrice"):
                        orders.append({
                            "time": trade.get("exitTime", ""),
                            "symbol": trade.get("symbol", ""),
                            "type": "Market",
                            "direction": "Sell" if trade.get("quantity", 0) > 0 else "Buy",
                            "quantity": abs(trade.get("quantity", 0)),
                            "price": trade.get("exitPrice", 0),
                            "status": "Filled",
                            "fillPrice": trade.get("exitPrice", 0),
                            "fillTime": trade.get("exitTime", "")
                        })
            
            # Format complete result for frontend
            result = {
                "timestamp": timestamp,
                "statistics": statistics,
                "equityCurve": equity_curve,
                "orders": orders,
                "logs": []  # Could add log parsing later if needed
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to parse LEAN results from {result_path}: {e}")
            return None
    
    async def start_backtest(self, request: BacktestRequest) -> BacktestRunInfo:
        """
        Start a new backtest.
        
        Args:
            request: Backtest configuration
            
        Returns:
            BacktestRunInfo with backtest ID and initial status
        """
        # Ensure background task is running
        self._ensure_background_task()
        
        # Generate unique ID
        backtest_id = str(uuid.uuid4())
        
        # Create run info
        run_info = BacktestRunInfo(
            backtest_id=backtest_id,
            status=BacktestStatus.PENDING,
            request=request,
            created_at=datetime.now()
        )
        
        # Store in active backtests
        self.active_backtests[backtest_id] = run_info
        
        try:
            # Verify strategy exists
            strategy_details = self.lean_runner.get_strategy_details(request.strategy_name)
            if not strategy_details:
                raise ValueError(f"Strategy '{request.strategy_name}' not found")
            
            # Start the backtest
            run_info.status = BacktestStatus.RUNNING
            run_info.started_at = datetime.now()
            
            # Save initial metadata
            self._save_backtest_metadata(backtest_id, run_info)
            
            result = await self.lean_runner.run_backtest(
                backtest_id=backtest_id,
                request=request,
                project_name=request.strategy_name
            )
            
            run_info.container_id = result["container_id"]
            run_info.result_path = result["result_path"]
            
            # Update status based on result folder
            if run_info.result_path:
                actual_status = self._determine_status_from_folder(run_info.result_path)
                if actual_status == BacktestStatus.COMPLETED:
                    run_info.status = BacktestStatus.COMPLETED
                    run_info.completed_at = datetime.now()
            
            # Save updated metadata
            self._save_backtest_metadata(backtest_id, run_info)
            
            logger.info(f"Completed backtest {backtest_id} for strategy {request.strategy_name}")
            
            # Don't send completion notifications immediately - let background monitor handle them
            # This ensures WebSocket connections are established before sending completion messages
            logger.info(f"Backtest {backtest_id} completed with status {run_info.status}, will be handled by background monitor")
            
        except Exception as e:
            logger.error(f"Failed to start backtest: {e}")
            run_info.status = BacktestStatus.FAILED
            run_info.error_message = str(e)
            run_info.completed_at = datetime.now()
            # Save failed metadata
            self._save_backtest_metadata(backtest_id, run_info)
            # Notify WebSocket clients of failure
            await self._notify_websocket_clients(backtest_id, {
                "type": "error",
                "message": str(e)
            })
        
        return run_info
    
    async def get_backtest_status(self, backtest_id: str) -> Optional[BacktestRunInfo]:
        """Get the current status of a backtest from memory or filesystem."""
        # First check in-memory active backtests
        run_info = self.active_backtests.get(backtest_id)
        if run_info:
            # Update status from folder if we have a result path
            if run_info.result_path:
                folder_status = self._determine_status_from_folder(run_info.result_path)
                if folder_status != run_info.status:
                    run_info.status = folder_status
                    if folder_status == BacktestStatus.COMPLETED and not run_info.completed_at:
                        run_info.completed_at = datetime.now()
                    # Save updated status
                    self._save_backtest_metadata(backtest_id, run_info)
            return run_info
        
        # If not in memory, try to load from filesystem
        run_info = self._load_backtest_metadata(backtest_id)
        if run_info and run_info.result_path:
            # Update status from folder
            folder_status = self._determine_status_from_folder(run_info.result_path)
            if folder_status != run_info.status:
                run_info.status = folder_status
                if folder_status == BacktestStatus.COMPLETED and not run_info.completed_at:
                    run_info.completed_at = datetime.now()
                # Save updated status
                self._save_backtest_metadata(backtest_id, run_info)
        
        return run_info
    
    async def cancel_backtest(self, backtest_id: str) -> bool:
        """Cancel a running backtest."""
        if backtest_id not in self.active_backtests:
            return False
        
        run_info = self.active_backtests[backtest_id]
        
        if run_info.status not in [BacktestStatus.PENDING, BacktestStatus.RUNNING]:
            return False
        
        try:
            # Stop the container if running
            if run_info.container_id:
                await self.lean_runner.stop_backtest(run_info.container_id)
            
            # Update status
            run_info.status = BacktestStatus.CANCELLED
            run_info.completed_at = datetime.now()
            
            # Notify WebSocket clients
            await self._notify_websocket_clients(backtest_id, {
                "event": "backtest_cancelled",
                "backtest_id": backtest_id
            })
            
            # Clean up monitoring
            await self.monitor.cleanup_monitoring(backtest_id)
            
            logger.info(f"Cancelled backtest {backtest_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling backtest {backtest_id}: {e}")
            return False
    
    async def get_backtest_progress(self, backtest_id: str) -> Optional[BacktestProgress]:
        """Get real-time progress of a running backtest."""
        if backtest_id not in self.active_backtests:
            return None
        
        run_info = self.active_backtests[backtest_id]
        
        if run_info.status != BacktestStatus.RUNNING:
            return BacktestProgress(
                backtest_id=backtest_id,
                status=run_info.status,
                log_entries=[run_info.error_message] if run_info.error_message else []
            )
        
        # Get progress from monitor
        progress = await self.monitor.monitor_backtest(
            backtest_id=backtest_id,
            container_id=run_info.container_id,
            result_path=run_info.result_path,
            start_date=run_info.request.start_date,
            end_date=run_info.request.end_date
        )
        
        return progress
    
    async def add_websocket_connection(self, backtest_id: str, websocket: Any):
        """Add a WebSocket connection for a backtest."""
        self.websocket_connections[backtest_id].append(websocket)
        logger.info(f"Added WebSocket connection for backtest {backtest_id}")
    
    async def remove_websocket_connection(self, backtest_id: str, websocket: Any):
        """Remove a WebSocket connection for a backtest."""
        if backtest_id in self.websocket_connections:
            self.websocket_connections[backtest_id].remove(websocket)
            if not self.websocket_connections[backtest_id]:
                del self.websocket_connections[backtest_id]
        logger.info(f"Removed WebSocket connection for backtest {backtest_id}")
    
    async def _notify_websocket_clients(self, backtest_id: str, message: Dict[str, Any]):
        """Send a message to all WebSocket clients monitoring a backtest."""
        logger.info(f"Attempting to notify WebSocket clients for backtest {backtest_id}")
        logger.info(f"Registered connections: {list(self.websocket_connections.keys())}")
        logger.info(f"Message: {message}")
        
        if backtest_id in self.websocket_connections:
            connection_count = len(self.websocket_connections[backtest_id])
            logger.info(f"Sending message to {connection_count} WebSocket connections for backtest {backtest_id}")
            disconnected = []
            
            for websocket in self.websocket_connections[backtest_id]:
                try:
                    await websocket.send_json(message)
                    logger.info(f"Successfully sent WebSocket message to client")
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    disconnected.append(websocket)
            
            # Remove disconnected clients
            for ws in disconnected:
                await self.remove_websocket_connection(backtest_id, ws)
        else:
            logger.warning(f"No WebSocket connections found for backtest {backtest_id}")
            logger.warning(f"Available connections: {list(self.websocket_connections.keys())}")
    
    async def _background_monitor(self):
        """Background task to monitor running backtests."""
        while True:
            try:
                # Check all running backtests
                for backtest_id, run_info in list(self.active_backtests.items()):
                    if run_info.status == BacktestStatus.RUNNING:
                        # Check actual status from folder-based detection
                        if run_info.result_path:
                            actual_status = self._determine_status_from_folder(run_info.result_path)
                            if actual_status != BacktestStatus.RUNNING:
                                # Status changed - notify clients
                                run_info.status = actual_status
                                run_info.completed_at = datetime.now()
                                
                                if actual_status == BacktestStatus.COMPLETED:
                                    # Parse LEAN results and send complete data in frontend-expected format
                                    parsed_result = self._parse_lean_results(run_info.result_path, backtest_id)
                                    if parsed_result:
                                        await self._notify_websocket_clients(backtest_id, {
                                            "type": "result",
                                            "result": parsed_result
                                        })
                                    else:
                                        # Fallback to basic status if parsing fails
                                        timestamp = Path(run_info.result_path).name if run_info.result_path else backtest_id
                                        await self._notify_websocket_clients(backtest_id, {
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
                                    
                                    # Also save to storage for historical results
                                    try:
                                        # Create strategy-specific storage
                                        strategy_storage = BacktestStorage(strategy_name=run_info.request.strategy_name)
                                        result = await strategy_storage.save_result(
                                            backtest_id=backtest_id,
                                            strategy_name=run_info.request.strategy_name,
                                            start_date=run_info.request.start_date,
                                            end_date=run_info.request.end_date,
                                            initial_cash=run_info.request.initial_cash,
                                            result_path=run_info.result_path
                                        )
                                    except Exception as e:
                                        logger.warning(f"Failed to save backtest result to storage: {e}")
                                else:
                                    # Notify failure in frontend-expected format
                                    await self._notify_websocket_clients(backtest_id, {
                                        "type": "error",
                                        "message": run_info.error_message or "Backtest failed"
                                    })
                        else:
                            # Send progress update - still running
                            await self._notify_websocket_clients(backtest_id, {
                                "type": "progress",
                                "percentage": 50,  # Intermediate progress for running backtests
                                "message": "Running backtest..."
                            })
                
                # Clean up completed backtests after 1 hour
                now = datetime.now()
                to_remove = []
                for backtest_id, run_info in self.active_backtests.items():
                    if run_info.completed_at:
                        if (now - run_info.completed_at).total_seconds() > 3600:
                            to_remove.append(backtest_id)
                
                for backtest_id in to_remove:
                    del self.active_backtests[backtest_id]
                    logger.info(f"Removed completed backtest {backtest_id} from active list")
                
            except Exception as e:
                logger.error(f"Error in background monitor: {e}")
            
            # Sleep for 5 seconds
            await asyncio.sleep(5)
    
    async def _monitor_container(self, backtest_id: str, run_info: BacktestRunInfo):
        """Monitor a Docker container for completion or failure."""
        try:
            container = self.lean_runner.docker_client.containers.get(run_info.container_id)
            
            # Wait for container to finish
            result = await asyncio.get_event_loop().run_in_executor(
                None, container.wait
            )
            
            exit_code = result.get('StatusCode', -1)
            
            if exit_code == 0:
                # Success - check for results
                run_info.status = BacktestStatus.COMPLETED
                run_info.completed_at = datetime.now()
                
                # TODO: Parse results from output directory
                await self._notify_websocket_clients(backtest_id, {
                    "type": "complete",
                    "message": "Backtest completed successfully"
                })
            else:
                # Failure
                run_info.status = BacktestStatus.FAILED
                run_info.completed_at = datetime.now()
                run_info.error_message = f"Container exited with code {exit_code}"
                
                # Get container logs for debugging
                logs = container.logs(tail=100).decode('utf-8')
                logger.error(f"Backtest {backtest_id} failed with exit code {exit_code}. Logs: {logs}")
                
                await self._notify_websocket_clients(backtest_id, {
                    "type": "error",
                    "message": f"Backtest failed with exit code {exit_code}"
                })
                
        except Exception as e:
            logger.error(f"Error monitoring container for backtest {backtest_id}: {e}")
            run_info.status = BacktestStatus.FAILED
            run_info.completed_at = datetime.now()
            run_info.error_message = str(e)
            
            await self._notify_websocket_clients(backtest_id, {
                "type": "error",
                "message": f"Container monitoring error: {str(e)}"
            })
    
    def run_backtest_sync(self, request: BacktestRequest) -> BacktestRunInfo:
        """
        Run a backtest synchronously (blocking).
        
        This is a convenience method for synchronous code that needs to run backtests.
        It creates an event loop if none exists and runs the async method.
        
        Args:
            request: Backtest configuration
            
        Returns:
            BacktestRunInfo with backtest results
        """
        import asyncio
        
        # Check if we're already in an async context
        try:
            loop = asyncio.get_running_loop()
            # We're already in an async context, can't use run_until_complete
            # Create a task and wait for it
            future = asyncio.create_task(self.start_backtest(request))
            # This will raise an error - synchronous method can't be called from async context
            raise RuntimeError("Cannot call run_backtest_sync from within an async context. Use start_backtest directly.")
        except RuntimeError:
            # No event loop running, we can create one
            return asyncio.run(self.start_backtest(request))


# Global instance
backtest_manager = BacktestManager()