"""
Backtest Queue Manager for managing parallel/sequential backtest execution.

This service:
- Manages concurrent backtest execution with semaphore control
- Tracks progress across multiple backtests
- Handles timeouts and retries
- Provides real-time progress updates
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import uuid

from ..models.backtest import BacktestRequest, BacktestStatus
from .backtest_manager import backtest_manager

logger = logging.getLogger(__name__)


class BacktestTask:
    """Represents a single backtest task in the queue."""
    
    def __init__(self, symbol: str, request_data: Dict[str, Any]):
        self.id = str(uuid.uuid4())
        self.symbol = symbol
        self.request_data = request_data
        self.status = BacktestStatus.PENDING
        self.result = None
        self.error = None
        self.attempts = 0
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None


class BacktestQueueManager:
    """Manages parallel execution of backtests with concurrency control."""
    
    def __init__(self, max_parallel: int = 5, startup_delay: float = 15.0):
        """
        Initialize the queue manager.
        
        Args:
            max_parallel: Maximum number of concurrent backtests
            startup_delay: Delay in seconds between starting different backtests (default 15s)
        """
        self.max_parallel = max_parallel
        self.startup_delay = startup_delay
        self.semaphore = asyncio.Semaphore(max_parallel)
        self.active_tasks: Dict[str, BacktestTask] = {}
        self.completed_tasks: Dict[str, BacktestTask] = {}
        self.progress_callback: Optional[Callable] = None
        self._last_backtest_start_time: Optional[datetime] = None
        self._startup_lock = asyncio.Lock()
        
    def set_progress_callback(self, callback: Callable):
        """Set a callback function for progress updates."""
        self.progress_callback = callback
    
    async def _run_single_backtest(self, task: BacktestTask, timeout: int) -> Dict[str, Any]:
        """Run a single backtest with timeout control."""
        async with self.semaphore:
            # Apply startup delay for new backtests (not retries)
            if task.attempts == 0 and self.startup_delay > 0:
                async with self._startup_lock:
                    if self._last_backtest_start_time is not None:
                        time_since_last_start = (datetime.now() - self._last_backtest_start_time).total_seconds()
                        if time_since_last_start < self.startup_delay:
                            delay_needed = self.startup_delay - time_since_last_start
                            logger.info(f"Applying startup delay of {delay_needed:.1f}s before starting backtest for {task.symbol}")
                            await asyncio.sleep(delay_needed)
                    
                    self._last_backtest_start_time = datetime.now()
            
            task.status = BacktestStatus.RUNNING
            task.started_at = datetime.now()
            task.attempts += 1
            
            logger.info(f"Starting backtest for {task.symbol} (attempt {task.attempts}), ID: {task.id}")
            
            try:
                # Create BacktestRequest from task data
                request = BacktestRequest(
                    strategy_name=task.request_data['strategy'],
                    start_date=task.request_data['start_date'],
                    end_date=task.request_data['end_date'],
                    initial_cash=task.request_data['initial_cash'],
                    symbols=[task.symbol],
                    resolution=task.request_data.get('resolution', 'Daily'),
                    parameters=task.request_data.get('parameters', {})
                )
                
                logger.info(f"Created backtest request for symbol: {task.symbol} with symbols list: {request.symbols}")
                
                # Run backtest with timeout
                result = await asyncio.wait_for(
                    backtest_manager.start_backtest(request),
                    timeout=timeout
                )
                
                # Wait for completion
                backtest_id = result.backtest_id
                max_wait = timeout
                start_wait = datetime.now()
                
                while (datetime.now() - start_wait).total_seconds() < max_wait:
                    status_info = await backtest_manager.get_backtest_status(backtest_id)
                    
                    if status_info and status_info.status == BacktestStatus.COMPLETED:
                        task.status = BacktestStatus.COMPLETED
                        task.result = {
                            'backtest_id': backtest_id,
                            'status': 'completed',
                            'result_path': status_info.result_path,
                            'symbol': task.symbol
                        }
                        break
                    elif status_info and status_info.status == BacktestStatus.FAILED:
                        raise Exception(f"Backtest failed: {status_info.error_message}")
                    
                    await asyncio.sleep(2)  # Check every 2 seconds
                
                if task.status != BacktestStatus.COMPLETED:
                    raise TimeoutError(f"Backtest did not complete within {timeout} seconds")
                
                task.completed_at = datetime.now()
                logger.info(f"Completed backtest for {task.symbol}")
                
                return task.result
                
            except asyncio.TimeoutError:
                task.status = BacktestStatus.FAILED
                task.error = f"Backtest timed out after {timeout} seconds"
                logger.error(f"Backtest for {task.symbol} timed out")
                raise
            except Exception as e:
                task.status = BacktestStatus.FAILED
                task.error = str(e)
                logger.error(f"Backtest for {task.symbol} failed: {e}")
                raise
            finally:
                task.completed_at = datetime.now()
                self._update_progress()
    
    async def run_batch(
        self,
        backtest_requests: List[Dict[str, Any]],
        timeout_per_backtest: int = 300,
        retry_attempts: int = 2,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Run a batch of backtests with parallel execution.
        
        Args:
            backtest_requests: List of backtest request dictionaries
            timeout_per_backtest: Timeout in seconds for each backtest
            retry_attempts: Number of retry attempts for failed backtests
            continue_on_error: Whether to continue if a backtest fails
            
        Returns:
            Dictionary mapping symbols to results
        """
        # Create tasks
        tasks = []
        for request_data in backtest_requests:
            symbol = request_data['symbol']
            task = BacktestTask(symbol, request_data)
            self.active_tasks[task.id] = task
            tasks.append(task)
        
        logger.info(f"Starting batch of {len(tasks)} backtests with {self.max_parallel} parallel slots")
        if self.startup_delay > 0:
            logger.info(f"Startup delay of {self.startup_delay}s will be applied between different backtests")
        
        # Run all tasks
        results = {}
        failed_tasks = []
        
        async def run_with_retry(task: BacktestTask):
            """Run a task with retry logic."""
            last_error = None
            
            for attempt in range(retry_attempts):
                try:
                    result = await self._run_single_backtest(task, timeout_per_backtest)
                    results[task.symbol] = result
                    return
                except Exception as e:
                    last_error = e
                    if attempt < retry_attempts - 1:
                        logger.warning(f"Retrying backtest for {task.symbol} after error: {e}")
                        await asyncio.sleep(5)  # Wait before retry
                    else:
                        logger.error(f"All retry attempts failed for {task.symbol}")
            
            # All retries failed
            failed_tasks.append(task)
            results[task.symbol] = {
                'status': 'failed',
                'error': str(last_error),
                'symbol': task.symbol
            }
            
            if not continue_on_error:
                raise last_error
        
        # Execute all tasks
        await asyncio.gather(
            *[run_with_retry(task) for task in tasks],
            return_exceptions=continue_on_error
        )
        
        # Move completed tasks
        for task in tasks:
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
                self.completed_tasks[task.id] = task
        
        # Log summary
        successful = sum(1 for r in results.values() if r.get('status') != 'failed')
        logger.info(f"Batch completed: {successful}/{len(tasks)} successful backtests")
        
        if failed_tasks:
            failed_symbols = [t.symbol for t in failed_tasks]
            logger.warning(f"Failed backtests: {', '.join(failed_symbols)}")
        
        return results
    
    def _update_progress(self):
        """Update progress and call callback if set."""
        total = len(self.active_tasks) + len(self.completed_tasks)
        completed = len(self.completed_tasks)
        
        if total > 0:
            progress = (completed / total) * 100
            status = {
                'total': total,
                'completed': completed,
                'active': len(self.active_tasks),
                'progress_percent': progress
            }
            
            logger.info(f"Progress: {completed}/{total} ({progress:.1f}%)")
            
            if self.progress_callback:
                self.progress_callback(status)
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'max_parallel': self.max_parallel,
            'active_symbols': [t.symbol for t in self.active_tasks.values()],
            'completed_symbols': [t.symbol for t in self.completed_tasks.values()]
        }
    
    async def run_backtest_sync(self, request_data: Dict[str, Any], timeout: int = 300) -> Dict[str, Any]:
        """
        Run a single backtest synchronously (for non-batch operations).
        
        Args:
            request_data: Backtest request data
            timeout: Timeout in seconds
            
        Returns:
            Backtest result dictionary
        """
        symbol = request_data['symbol']
        task = BacktestTask(symbol, request_data)
        
        try:
            result = await self._run_single_backtest(task, timeout)
            return result
        except Exception as e:
            logger.error(f"Synchronous backtest failed for {symbol}: {e}")
            return {
                'status': 'failed',
                'error': str(e),
                'symbol': symbol
            }