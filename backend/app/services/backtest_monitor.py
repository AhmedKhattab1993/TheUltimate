"""
Service for monitoring running backtests and extracting progress.
"""

import asyncio
import json
import logging
import re
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..models.backtest import BacktestStatus, BacktestProgress


logger = logging.getLogger(__name__)


class BacktestMonitor:
    """Monitors running backtests and extracts progress information."""
    
    def __init__(self):
        self.monitored_backtests: Dict[str, Dict[str, Any]] = {}
        
    async def monitor_backtest(self, 
                             backtest_id: str,
                             container_id: str,
                             result_path: str,
                             start_date: date,
                             end_date: date) -> BacktestProgress:
        """
        Monitor a running backtest and extract progress information.
        
        Args:
            backtest_id: Unique identifier for the backtest
            container_id: Docker container ID
            result_path: Path where results will be stored
            start_date: Backtest start date
            end_date: Backtest end date
            
        Returns:
            BacktestProgress with current status
        """
        from .lean_runner import LeanRunner
        runner = LeanRunner()
        
        try:
            # Get container status and logs
            container_info = await runner.get_container_status(container_id)
            
            if container_info["status"] == "not_found":
                # Container finished or was removed
                return await self._check_completed_backtest(backtest_id, result_path)
            
            # Parse logs for progress
            logs = container_info["logs"]
            progress = self._parse_progress_from_logs(logs, start_date, end_date)
            
            # Update status based on container state
            if container_info["status"] == "running":
                progress.status = BacktestStatus.RUNNING
            elif container_info["status"] == "exited":
                # Check if it completed successfully
                result_progress = await self._check_completed_backtest(backtest_id, result_path)
                if result_progress.status == BacktestStatus.COMPLETED:
                    return result_progress
                else:
                    progress.status = BacktestStatus.FAILED
            
            progress.backtest_id = backtest_id
            
            # Store monitoring info
            self.monitored_backtests[backtest_id] = {
                "container_id": container_id,
                "result_path": result_path,
                "last_check": datetime.now(),
                "progress": progress
            }
            
            return progress
            
        except Exception as e:
            logger.error(f"Error monitoring backtest {backtest_id}: {e}")
            return BacktestProgress(
                backtest_id=backtest_id,
                status=BacktestStatus.FAILED,
                log_entries=[f"Monitoring error: {str(e)}"]
            )
    
    def _parse_progress_from_logs(self, 
                                 logs: List[str], 
                                 start_date: date,
                                 end_date: date) -> BacktestProgress:
        """Parse progress information from LEAN logs."""
        progress = BacktestProgress(
            backtest_id="",  # Will be set by caller
            status=BacktestStatus.RUNNING,
            log_entries=[]
        )
        
        # Extract recent log entries
        progress.log_entries = [log for log in logs[-20:] if log.strip()]
        
        # Try to find current processing date
        date_pattern = r'(\d{4}-\d{2}-\d{2})'
        for log in reversed(logs):
            match = re.search(date_pattern, log)
            if match:
                try:
                    current_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
                    progress.current_date = current_date
                    
                    # Calculate progress percentage
                    total_days = (end_date - start_date).days
                    if total_days > 0:
                        days_completed = (current_date - start_date).days
                        progress.progress_percentage = (days_completed / total_days) * 100
                    
                    break
                except ValueError:
                    pass
        
        # Look for statistics in logs
        stats = {}
        
        # Common LEAN log patterns
        patterns = {
            "Total Trades": r"Total Trades[:\s]+(\d+)",
            "Sharpe Ratio": r"Sharpe Ratio[:\s]+([-\d.]+)",
            "Win Rate": r"Win Rate[:\s]+([\d.]+)%?",
            "Total Return": r"Total Return[:\s]+([-\d.]+)%?",
            "Max Drawdown": r"Max Drawdown[:\s]+([-\d.]+)%?"
        }
        
        for log in logs:
            for stat_name, pattern in patterns.items():
                match = re.search(pattern, log, re.IGNORECASE)
                if match:
                    try:
                        value = float(match.group(1))
                        stats[stat_name.lower().replace(" ", "_")] = value
                    except ValueError:
                        pass
        
        if stats:
            progress.statistics = stats
        
        return progress
    
    async def _check_completed_backtest(self, 
                                      backtest_id: str,
                                      result_path: str) -> BacktestProgress:
        """Check if a backtest has completed and read results."""
        result_dir = Path(result_path)
        
        # Look for LEAN result files
        json_files = list(result_dir.glob("*.json"))
        
        # Find the main result file (usually has a numeric name)
        result_file = None
        for f in json_files:
            if f.stem.isdigit():
                result_file = f
                break
        
        if result_file and result_file.exists():
            try:
                with open(result_file, 'r') as f:
                    result_data = json.load(f)
                
                # Extract statistics
                stats = result_data.get("Statistics", {})
                
                return BacktestProgress(
                    backtest_id=backtest_id,
                    status=BacktestStatus.COMPLETED,
                    progress_percentage=100.0,
                    statistics={
                        "total_return": float(stats.get("Total Return", 0)),
                        "sharpe_ratio": float(stats.get("Sharpe Ratio", 0)),
                        "max_drawdown": float(stats.get("Max Drawdown", 0)),
                        "win_rate": float(stats.get("Win Rate", 0)),
                        "total_trades": int(stats.get("Total Trades", 0))
                    },
                    log_entries=["Backtest completed successfully"]
                )
            except Exception as e:
                logger.error(f"Error reading result file: {e}")
        
        # Check for error logs
        log_file = result_dir / "log.txt"
        if log_file.exists():
            try:
                with open(log_file, 'r') as f:
                    logs = f.readlines()
                    
                # Check for error indicators
                for log in logs:
                    if "ERROR" in log or "FAILED" in log:
                        return BacktestProgress(
                            backtest_id=backtest_id,
                            status=BacktestStatus.FAILED,
                            log_entries=logs[-20:]  # Last 20 lines
                        )
            except Exception as e:
                logger.error(f"Error reading log file: {e}")
        
        # If we can't determine status, assume it's still running
        return BacktestProgress(
            backtest_id=backtest_id,
            status=BacktestStatus.RUNNING,
            log_entries=["Unable to determine backtest status"]
        )
    
    async def cleanup_monitoring(self, backtest_id: str):
        """Clean up monitoring resources for a completed backtest."""
        if backtest_id in self.monitored_backtests:
            del self.monitored_backtests[backtest_id]
            logger.info(f"Cleaned up monitoring for backtest {backtest_id}")