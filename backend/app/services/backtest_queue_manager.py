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
from decimal import Decimal
from typing import Dict, Any, List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import uuid
import json
from pathlib import Path
import asyncpg

from ..models.backtest import BacktestRequest, BacktestStatus
from ..models.cache_models import CachedBacktestResult, CachedBacktestRequest
from .backtest_manager import backtest_manager
from .cache_service import CacheService
from .backtest_storage import BacktestStorage
from ..config import settings

logger = logging.getLogger(__name__)


class BacktestTask:
    """Represents a single backtest task in the queue."""
    
    def __init__(self, symbol: str, request_data: Dict[str, Any], task_id: Optional[str] = None):
        self.id = task_id if task_id else str(uuid.uuid4())
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
    
    def __init__(self, max_parallel: int = 5, startup_delay: float = 15.0, 
                 cache_service: Optional[CacheService] = None,
                 enable_storage: bool = True,
                 enable_cleanup: bool = True,
                 screener_session_id: Optional[uuid.UUID] = None):
        """
        Initialize the queue manager.
        
        Args:
            max_parallel: Maximum number of concurrent backtests
            startup_delay: Delay in seconds between starting different backtests (default 15s)
            cache_service: Optional cache service for checking/storing results
            enable_storage: Whether to store results to database
            enable_cleanup: Whether to cleanup files after storage
            screener_session_id: Optional screener session ID for linking results
        """
        self.max_parallel = max_parallel
        self.startup_delay = startup_delay
        self.semaphore = asyncio.Semaphore(max_parallel)
        self.active_tasks: Dict[str, BacktestTask] = {}
        self.completed_tasks: Dict[str, BacktestTask] = {}
        self.completion_callback: Optional[Callable] = None
        self._last_backtest_start_time: Optional[datetime] = None
        self._startup_lock = asyncio.Lock()
        self.cache_service = cache_service
        self.enable_storage = enable_storage
        self.enable_cleanup = enable_cleanup
        self.backtest_storage = BacktestStorage() if enable_storage else None
        self.screener_session_id = screener_session_id
        
    def set_completion_callback(self, callback: Callable):
        """Set a callback function for completion notification."""
        self.completion_callback = callback
    
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
                parameters = task.request_data.get('parameters', {})
                
                # Extract fields that should be direct attributes on BacktestRequest
                # Use .get() instead of .pop() to keep values in parameters dict for LEAN config
                lower_timeframe = parameters.get('lower_timeframe', '5min')
                pivot_bars = parameters.get('pivot_bars', 20)
                
                logger.info(f"Parameters for {task.symbol}: lower_timeframe={lower_timeframe}, pivot_bars={pivot_bars}, all_params={parameters}")
                
                request = BacktestRequest(
                    strategy_name=task.request_data['strategy'],
                    start_date=task.request_data['start_date'],
                    end_date=task.request_data['end_date'],
                    initial_cash=task.request_data['initial_cash'],
                    symbols=[task.symbol],
                    resolution=task.request_data.get('resolution', 'Daily'),
                    lower_timeframe=lower_timeframe,
                    pivot_bars=pivot_bars,
                    parameters=parameters  # Remaining parameters
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
                            'backtest_id': task.id,  # Use task ID for WebSocket tracking
                            'lean_backtest_id': backtest_id,  # Store LEAN ID separately
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
                
                # Parse and store results if enabled
                if self.enable_storage and task.result.get('result_path'):
                    await self._parse_and_store_results(task)
                
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
                self._check_completion()
    
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
        # Create tasks and check cache
        tasks = []
        cached_results = {}
        
        for request_data in backtest_requests:
            symbol = request_data['symbol']
            
            # Check cache if enabled
            if self.cache_service:
                from ..models.cache_models import CachedBacktestRequest
                
                # Extract parameters from request data
                parameters = request_data.get('parameters', {})
                
                # Create cache request model using new cache key parameters
                cache_request = CachedBacktestRequest(
                    symbol=symbol,
                    strategy_name=request_data.get('strategy', 'MarketStructure'),
                    start_date=datetime.strptime(request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(request_data['end_date'], '%Y-%m-%d').date(),
                    initial_cash=request_data.get('initial_cash', 100000),
                    pivot_bars=parameters.get('pivot_bars', 20),
                    lower_timeframe=parameters.get('lower_timeframe', '5min'),
                    # Legacy parameters for backward compatibility
                    holding_period=parameters.get('holding_period', 10),
                    gap_threshold=parameters.get('gap_threshold', 2.0),
                    stop_loss=parameters.get('stop_loss'),
                    take_profit=parameters.get('take_profit')
                )
                
                cached_result = await self.cache_service.get_backtest_results(cache_request)
                
                if cached_result is not None:
                    logger.info(f"Cache hit for {symbol} - skipping backtest")
                    # Convert cached result to expected format with comprehensive metrics
                    cached_results[symbol] = {
                        'status': 'completed',
                        'symbol': symbol,
                        'statistics': {
                            # Core performance metrics
                            'total_return': float(cached_result.total_return),
                            'net_profit': float(cached_result.net_profit) if cached_result.net_profit else 0.0,
                            'net_profit_currency': float(cached_result.net_profit_currency) if cached_result.net_profit_currency else 0.0,
                            'compounding_annual_return': float(cached_result.compounding_annual_return) if cached_result.compounding_annual_return else 0.0,
                            'final_value': float(cached_result.final_value) if cached_result.final_value else 0.0,
                            'start_equity': float(cached_result.start_equity) if cached_result.start_equity else 0.0,
                            'end_equity': float(cached_result.end_equity) if cached_result.end_equity else 0.0,
                            
                            # Enhanced risk metrics
                            'sharpe_ratio': float(cached_result.sharpe_ratio) if cached_result.sharpe_ratio else 0.0,
                            'sortino_ratio': float(cached_result.sortino_ratio) if cached_result.sortino_ratio else 0.0,
                            'max_drawdown': float(cached_result.max_drawdown) if cached_result.max_drawdown else 0.0,
                            'probabilistic_sharpe_ratio': float(cached_result.probabilistic_sharpe_ratio) if cached_result.probabilistic_sharpe_ratio else 0.0,
                            'annual_standard_deviation': float(cached_result.annual_standard_deviation) if cached_result.annual_standard_deviation else 0.0,
                            'annual_variance': float(cached_result.annual_variance) if cached_result.annual_variance else 0.0,
                            'beta': float(cached_result.beta) if cached_result.beta else 0.0,
                            'alpha': float(cached_result.alpha) if cached_result.alpha else 0.0,
                            
                            # Advanced trading statistics
                            'total_trades': cached_result.total_trades,
                            'winning_trades': cached_result.winning_trades,
                            'losing_trades': cached_result.losing_trades,
                            'win_rate': float(cached_result.win_rate),
                            'loss_rate': float(cached_result.loss_rate) if cached_result.loss_rate else 0.0,
                            'average_win': float(cached_result.average_win) if cached_result.average_win else 0.0,
                            'average_loss': float(cached_result.average_loss) if cached_result.average_loss else 0.0,
                            'profit_factor': float(cached_result.profit_factor) if cached_result.profit_factor else 0.0,
                            'profit_loss_ratio': float(cached_result.profit_loss_ratio) if cached_result.profit_loss_ratio else 0.0,
                            'expectancy': float(cached_result.expectancy) if cached_result.expectancy else 0.0,
                            'total_orders': cached_result.total_orders if cached_result.total_orders else 0,
                            
                            # Advanced metrics
                            'information_ratio': float(cached_result.information_ratio) if cached_result.information_ratio else 0.0,
                            'tracking_error': float(cached_result.tracking_error) if cached_result.tracking_error else 0.0,
                            'treynor_ratio': float(cached_result.treynor_ratio) if cached_result.treynor_ratio else 0.0,
                            'total_fees': float(cached_result.total_fees) if cached_result.total_fees else 0.0,
                            'estimated_strategy_capacity': float(cached_result.estimated_strategy_capacity) if cached_result.estimated_strategy_capacity else 0.0,
                            'lowest_capacity_asset': cached_result.lowest_capacity_asset or "",
                            'portfolio_turnover': float(cached_result.portfolio_turnover) if cached_result.portfolio_turnover else 0.0,
                            
                            # Strategy-specific metrics
                            'pivot_highs_detected': cached_result.pivot_highs_detected if cached_result.pivot_highs_detected else 0,
                            'pivot_lows_detected': cached_result.pivot_lows_detected if cached_result.pivot_lows_detected else 0,
                            'bos_signals_generated': cached_result.bos_signals_generated if cached_result.bos_signals_generated else 0,
                            'position_flips': cached_result.position_flips if cached_result.position_flips else 0,
                            'liquidation_events': cached_result.liquidation_events if cached_result.liquidation_events else 0,
                            
                            # Algorithm parameters
                            'initial_cash': float(cached_result.initial_cash),
                            'pivot_bars': cached_result.pivot_bars,
                            'lower_timeframe': cached_result.lower_timeframe,
                            'strategy_name': cached_result.strategy_name
                        },
                        'from_cache': True,
                        'cache_hit': True
                    }
                    continue
            
            # Not in cache, create task
            # Use provided task_id if available
            task_id = request_data.get('task_id')
            
            # Log the request data for debugging
            logger.info(f"Creating backtest task for {symbol} with parameters: {request_data.get('parameters', {})}")
            
            task = BacktestTask(symbol, request_data, task_id)
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
                'symbol': task.symbol,
                'backtest_id': task.id  # Include task ID for tracking
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
        
        # Check for completion after all tasks are processed
        self._check_completion()
        
        # Merge cached results with new results
        all_results = {**cached_results, **results}
        
        # Log summary
        total_requests = len(backtest_requests)
        cached_count = len(cached_results)
        successful = sum(1 for r in all_results.values() if r.get('status') != 'failed')
        logger.info(f"Batch completed: {successful}/{total_requests} successful backtests ({cached_count} from cache)")
        
        if failed_tasks:
            failed_symbols = [t.symbol for t in failed_tasks]
            logger.warning(f"Failed backtests: {', '.join(failed_symbols)}")
        
        return all_results
    
    def _check_completion(self):
        """Check if all backtests are complete and call completion callback."""
        total = len(self.active_tasks) + len(self.completed_tasks)
        completed = len(self.completed_tasks)
        
        logger.info(f"Backtest progress: {completed}/{total}")
        
        # Check if all backtests are complete
        if len(self.active_tasks) == 0 and len(self.completed_tasks) > 0:
            logger.info("All backtests completed")
            if self.completion_callback:
                # If callback is async, create a task to run it
                if asyncio.iscoroutinefunction(self.completion_callback):
                    asyncio.create_task(self.completion_callback())
                else:
                    self.completion_callback()
    
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
        task_id = request_data.get('task_id')
        task = BacktestTask(symbol, request_data, task_id)
        
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
    
    async def _parse_and_store_results(self, task: BacktestTask) -> None:
        """
        Parse backtest results and store them to database and cache.
        
        Args:
            task: Completed backtest task with result_path
        """
        try:
            result_path = task.result.get('result_path')
            if not result_path:
                logger.warning(f"No result_path for {task.symbol}, skipping storage")
                return
            
            # Parse statistics from result file
            statistics = await self._extract_statistics_from_result(result_path)
            if not statistics:
                logger.warning(f"Could not extract statistics for {task.symbol}")
                return
            
            # Store in cache if enabled
            if self.cache_service:
                # Extract parameters from request data
                parameters = task.request_data.get('parameters', {})
                
                # First create a CachedBacktestRequest to get the deterministic ID
                cache_request = CachedBacktestRequest(
                    symbol=task.symbol,
                    strategy_name=statistics.get('strategy_name', task.request_data.get('strategy', 'MarketStructure')),
                    start_date=datetime.strptime(task.request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(task.request_data['end_date'], '%Y-%m-%d').date(),
                    initial_cash=statistics.get('initial_cash', task.request_data.get('initial_cash', 100000)),
                    pivot_bars=statistics.get('pivot_bars', parameters.get('pivot_bars', 20)),
                    lower_timeframe=statistics.get('lower_timeframe', parameters.get('lower_timeframe', '5min'))
                )
                
                # Use cache hash as the backtest ID
                cache_hash = cache_request.get_cache_hash()
                
                # Create comprehensive CachedBacktestResult model with all new fields
                backtest_result = CachedBacktestResult(
                    backtest_id=cache_hash,
                    symbol=task.symbol,
                    strategy_name=statistics.get('strategy_name', task.request_data.get('strategy', 'MarketStructure')),
                    
                    # New cache key parameters
                    initial_cash=statistics.get('initial_cash', task.request_data.get('initial_cash', 100000)),
                    pivot_bars=statistics.get('pivot_bars', parameters.get('pivot_bars', 20)),
                    lower_timeframe=statistics.get('lower_timeframe', parameters.get('lower_timeframe', '5min')),
                    
                    # Date range
                    start_date=datetime.strptime(task.request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(task.request_data['end_date'], '%Y-%m-%d').date(),
                    
                    # Core performance metrics
                    total_return=statistics.get('total_return', 0.0),
                    net_profit=statistics.get('net_profit', 0.0),
                    net_profit_currency=statistics.get('net_profit_currency', 0.0),
                    compounding_annual_return=statistics.get('compounding_annual_return', 0.0),
                    final_value=statistics.get('final_value', statistics.get('end_equity', 0.0)),
                    start_equity=statistics.get('start_equity', statistics.get('initial_cash', 100000)),
                    end_equity=statistics.get('end_equity', 0.0),
                    
                    # Enhanced risk metrics
                    sharpe_ratio=statistics.get('sharpe_ratio', 0.0),
                    sortino_ratio=statistics.get('sortino_ratio', 0.0),
                    max_drawdown=statistics.get('max_drawdown', 0.0),
                    probabilistic_sharpe_ratio=statistics.get('probabilistic_sharpe_ratio', 0.0),
                    annual_standard_deviation=statistics.get('annual_standard_deviation', 0.0),
                    annual_variance=statistics.get('annual_variance', 0.0),
                    beta=statistics.get('beta', 0.0),
                    alpha=statistics.get('alpha', 0.0),
                    
                    # Advanced trading statistics
                    total_trades=statistics.get('total_trades', 0),
                    winning_trades=statistics.get('winning_trades', 0),
                    losing_trades=statistics.get('losing_trades', 0),
                    win_rate=statistics.get('win_rate', 0.0),
                    loss_rate=statistics.get('loss_rate', 0.0),
                    average_win=statistics.get('average_win', 0.0),
                    average_loss=statistics.get('average_loss', 0.0),
                    profit_factor=statistics.get('profit_factor', 0.0),
                    profit_loss_ratio=statistics.get('profit_loss_ratio', 0.0),
                    expectancy=statistics.get('expectancy', 0.0),
                    total_orders=statistics.get('total_orders', 0),
                    
                    # Advanced metrics
                    information_ratio=statistics.get('information_ratio', 0.0),
                    tracking_error=statistics.get('tracking_error', 0.0),
                    treynor_ratio=statistics.get('treynor_ratio', 0.0),
                    total_fees=statistics.get('total_fees', 0.0),
                    estimated_strategy_capacity=statistics.get('estimated_strategy_capacity', 0.0),
                    lowest_capacity_asset=statistics.get('lowest_capacity_asset', ""),
                    portfolio_turnover=statistics.get('portfolio_turnover', 0.0),
                    
                    # Strategy-specific metrics
                    pivot_highs_detected=statistics.get('pivot_highs_detected', 0),
                    pivot_lows_detected=statistics.get('pivot_lows_detected', 0),
                    bos_signals_generated=statistics.get('bos_signals_generated', 0),
                    position_flips=statistics.get('position_flips', 0),
                    liquidation_events=statistics.get('liquidation_events', 0),
                    
                    # Execution metadata
                    execution_time_ms=int((task.completed_at - task.started_at).total_seconds() * 1000) if task.started_at and task.completed_at else None,
                    result_path=result_path,
                    status='completed',
                    error_message=None,
                    cache_hit=False
                )
                
                success = await self.cache_service.save_backtest_results(backtest_result)
                if success:
                    logger.info(f"Stored backtest results for {task.symbol} in cache")
                else:
                    logger.warning(f"Failed to store backtest results for {task.symbol} in cache")
            
            # Store in database using BacktestStorage (file storage)
            if self.backtest_storage:
                # Use the same cache hash that was used for cache storage
                backtest_result = await self.backtest_storage.save_result(
                    backtest_id=cache_hash,
                    symbol=task.symbol,
                    strategy_name=task.request_data.get('strategy', 'MarketStructure'),
                    start_date=datetime.strptime(task.request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(task.request_data['end_date'], '%Y-%m-%d').date(),
                    initial_cash=task.request_data.get('initial_cash', 100000),
                    result_path=result_path,
                    resolution=task.request_data.get('resolution', 'Daily'),
                    pivot_bars=task.request_data.get('pivot_bars', 20),
                    lower_timeframe=task.request_data.get('lower_timeframe', '5min')
                )
                if backtest_result:
                    logger.info(f"Stored backtest result for {task.symbol} in file storage")
                else:
                    logger.warning(f"Failed to store backtest result for {task.symbol} in file storage")
            
            # Database save is already handled by cache_service.save_backtest_results() above
            # Removed duplicate database save operation to prevent duplicate entries
            
            # Save link to screener_backtest_links if we have a screener_session_id
            if self.screener_session_id and 'screening_date' in task.request_data:
                # DIAGNOSTIC LOGGING
                logger.info(f"[DIAGNOSTIC] Saving backtest link for {task.symbol}:")
                logger.info(f"  - Screener session ID: {self.screener_session_id}")
                logger.info(f"  - Backtest ID: {cache_hash}")
                logger.info(f"  - Screening date: {task.request_data['screening_date']}")
                
                await self._save_screener_backtest_link(
                    screener_session_id=self.screener_session_id,
                    backtest_id=cache_hash,
                    symbol=task.symbol,
                    data_date=task.request_data['screening_date']
                )
            
            # Add statistics to task result for immediate use
            task.result['statistics'] = statistics
            
            # Cleanup files if enabled
            if self.enable_cleanup and result_path:
                await self._cleanup_backtest_files(result_path)
                
        except Exception as e:
            logger.error(f"Error parsing and storing results for {task.symbol}: {e}")
            # Don't raise - storage failures shouldn't fail the backtest
    
    async def _extract_statistics_from_result(self, result_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract comprehensive statistics from LEAN result files according to schema alignment plan.
        
        Args:
            result_path: Path to LEAN result directory
            
        Returns:
            Dictionary of statistics or None if extraction fails
        """
        try:
            result_dir = Path(result_path)
            
            # Find the summary file
            summary_file = None
            for f in result_dir.glob("*-summary.json"):
                summary_file = f
                break
            
            if not summary_file:
                # Fallback to main result file
                for f in result_dir.glob("*.json"):
                    if f.stem.isdigit():
                        summary_file = f
                        break
            
            if not summary_file or not summary_file.exists():
                logger.error(f"No result file found in {result_path}")
                return None
            
            # Read and parse statistics
            with open(summary_file, 'r') as f:
                lean_result = json.load(f)
                
            logger.info(f"Extracting comprehensive metrics from LEAN result file: {summary_file.name}")
            
            # Extract different sections from LEAN output
            stats_data = lean_result.get("statistics", {})
            if not stats_data:
                stats_data = lean_result.get("Statistics", {})
            
            runtime_stats = lean_result.get("runtimeStatistics", {})
            trade_stats = lean_result.get("totalPerformance", {}).get("tradeStatistics", {})
            portfolio_stats = lean_result.get("totalPerformance", {}).get("portfolioStatistics", {})
            algorithm_config = lean_result.get("algorithmConfiguration", {})
            algorithm_params = algorithm_config.get("parameters", {})
            
            # Helper functions for parsing different data types
            def parse_percentage(value) -> float:
                """Parse percentage values from LEAN output."""
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    # Handle percentage strings like "5.23%" or "0.0523"
                    cleaned = value.strip().rstrip('%')
                    try:
                        return float(cleaned)
                    except ValueError:
                        logger.warning(f"Could not parse percentage value: {value}")
                        return 0.0
                return 0.0
            
            def parse_currency(value) -> float:
                """Parse currency values from LEAN output."""
                if isinstance(value, str):
                    # Remove currency symbols and commas
                    value = value.replace('$', '').replace(',', '').strip()
                    if value.startswith('-') and not value[1:].replace('.', '').replace('-', '').isdigit():
                        # Handle format like "$-23,603.13" 
                        value = '-' + value[1:].replace('-', '')
                    try:
                        return float(value)
                    except ValueError:
                        logger.warning(f"Could not parse currency value: {value}")
                        return 0.0
                elif isinstance(value, (int, float)):
                    return float(value)
                return 0.0
            
            def parse_integer(value) -> int:
                """Parse integer values from LEAN output."""
                if isinstance(value, int):
                    return value
                if isinstance(value, (str, float)):
                    try:
                        return int(float(value))
                    except ValueError:
                        logger.warning(f"Could not parse integer value: {value}")
                        return 0
                return 0
            
            def parse_duration(value) -> float:
                """Parse duration from various formats (seconds, HH:MM:SS, etc)."""
                if isinstance(value, (int, float)):
                    return float(value)
                if isinstance(value, str):
                    # Check if it's in HH:MM:SS format
                    if ':' in value:
                        parts = value.split(':')
                        if len(parts) == 3:
                            # Convert HH:MM:SS to total seconds
                            try:
                                hours, minutes, seconds = map(float, parts)
                                return hours * 3600 + minutes * 60 + seconds
                            except ValueError:
                                pass
                        elif len(parts) == 2:
                            # Convert MM:SS to total seconds
                            try:
                                minutes, seconds = map(float, parts)
                                return minutes * 60 + seconds
                            except ValueError:
                                pass
                    # Try to parse as a number
                    try:
                        return float(value)
                    except ValueError:
                        logger.warning(f"Could not parse duration value: {value}")
                        return 0.0
                return 0.0
            
            # Build comprehensive statistics dictionary according to schema alignment plan
            statistics = {
                # Core Performance Results
                'total_return': parse_percentage(runtime_stats.get("Return", stats_data.get("Total Return", "0%"))),
                'net_profit': parse_percentage(stats_data.get("Net Profit", "0%")),
                'net_profit_currency': parse_currency(runtime_stats.get("Net Profit", "$0")),
                'compounding_annual_return': parse_percentage(stats_data.get("Compounding Annual Return", "0%")),
                'final_value': parse_currency(runtime_stats.get("Equity", stats_data.get("End Equity", "$0"))),
                'start_equity': parse_currency(stats_data.get("Start Equity", portfolio_stats.get("startEquity", "100000"))),
                'end_equity': parse_currency(stats_data.get("End Equity", portfolio_stats.get("endEquity", "100000"))),
                
                # Enhanced Risk Metrics - Use trade statistics if portfolio statistics are zero
                'sharpe_ratio': float(trade_stats.get("sharpeRatio", stats_data.get("Sharpe Ratio", portfolio_stats.get("sharpeRatio", 0)))) if float(stats_data.get("Sharpe Ratio", 0)) == 0 else float(stats_data.get("Sharpe Ratio", 0)),
                'sortino_ratio': float(trade_stats.get("sortinoRatio", stats_data.get("Sortino Ratio", portfolio_stats.get("sortinoRatio", 0)))) if float(stats_data.get("Sortino Ratio", 0)) == 0 else float(stats_data.get("Sortino Ratio", 0)),
                'max_drawdown': abs(float(trade_stats.get("maximumClosedTradeDrawdown", 0)) / parse_currency(algorithm_params.get("cash", "100000")) * 100) if trade_stats.get("maximumClosedTradeDrawdown") and parse_percentage(stats_data.get("Drawdown", "0%")) == 0 else abs(parse_percentage(stats_data.get("Drawdown", portfolio_stats.get("drawdown", "0%")))) * -1,
                'probabilistic_sharpe_ratio': parse_percentage(stats_data.get("Probabilistic Sharpe Ratio", portfolio_stats.get("probabilisticSharpeRatio", "0%"))),
                'annual_standard_deviation': parse_percentage(stats_data.get("Annual Standard Deviation", portfolio_stats.get("annualStandardDeviation", "0%"))),
                'annual_variance': parse_percentage(stats_data.get("Annual Variance", portfolio_stats.get("annualVariance", "0%"))),
                'beta': float(stats_data.get("Beta", portfolio_stats.get("beta", 0))),
                'alpha': float(stats_data.get("Alpha", portfolio_stats.get("alpha", 0))),
                
                # Advanced Trading Statistics
                'total_trades': parse_integer(trade_stats.get("totalNumberOfTrades", stats_data.get("Total Trades", 0))),
                'winning_trades': parse_integer(trade_stats.get("numberOfWinningTrades", 0)),
                'losing_trades': parse_integer(trade_stats.get("numberOfLosingTrades", 0)),
                'win_rate': float(trade_stats.get("winRate", 0)) * 100 if trade_stats.get("winRate") and parse_percentage(stats_data.get("Win Rate", "0%")) == 0 else parse_percentage(stats_data.get("Win Rate", "0%")),
                'loss_rate': float(trade_stats.get("lossRate", 0)) * 100 if trade_stats.get("lossRate") and parse_percentage(stats_data.get("Loss Rate", "0%")) == 0 else parse_percentage(stats_data.get("Loss Rate", "0%")),
                'average_win': parse_percentage(stats_data.get("Average Win", trade_stats.get("averageProfit", "0%"))),
                'average_loss': parse_percentage(stats_data.get("Average Loss", trade_stats.get("averageLoss", "0%"))),
                'profit_factor': float(trade_stats.get("profitFactor", stats_data.get("Profit Factor", 0))) if float(stats_data.get("Profit Factor", 0)) == 0 else float(stats_data.get("Profit Factor", 0)),
                'profit_loss_ratio': float(trade_stats.get("profitLossRatio", stats_data.get("Profit-Loss Ratio", 0))) if float(stats_data.get("Profit-Loss Ratio", 0)) == 0 else float(stats_data.get("Profit-Loss Ratio", 0)),
                'expectancy': float(stats_data.get("Expectancy", portfolio_stats.get("expectancy", 0))),
                'total_orders': parse_integer(stats_data.get("Total Orders", 0)),
                
                # Advanced Metrics
                'information_ratio': float(stats_data.get("Information Ratio", portfolio_stats.get("informationRatio", 0))),
                'tracking_error': float(stats_data.get("Tracking Error", portfolio_stats.get("trackingError", 0))),
                'treynor_ratio': float(stats_data.get("Treynor Ratio", portfolio_stats.get("treynorRatio", 0))),
                'total_fees': parse_currency(stats_data.get("Total Fees", trade_stats.get("totalFees", "$0"))),
                'estimated_strategy_capacity': parse_currency(stats_data.get("Estimated Strategy Capacity", "$0")),
                'lowest_capacity_asset': stats_data.get("Lowest Capacity Asset", ""),
                'portfolio_turnover': parse_percentage(stats_data.get("Portfolio Turnover", portfolio_stats.get("portfolioTurnover", "0%"))),
                
                # Strategy-Specific Metrics (may not be available in all LEAN outputs)
                'pivot_highs_detected': parse_integer(stats_data.get("Pivot Highs Detected", 0)),
                'pivot_lows_detected': parse_integer(stats_data.get("Pivot Lows Detected", 0)),
                'bos_signals_generated': parse_integer(stats_data.get("BOS Signals Generated", 0)),
                'position_flips': parse_integer(stats_data.get("Position Flips", 0)),
                'liquidation_events': parse_integer(stats_data.get("Liquidation Events", 0)),
                
                # Additional useful metrics for debugging and analysis
                'largest_win': parse_currency(trade_stats.get("largestProfit", stats_data.get("Largest Win", "$0"))),
                'largest_loss': parse_currency(trade_stats.get("largestLoss", stats_data.get("Largest Loss", "$0"))),
                'average_trade_duration': parse_duration(trade_stats.get("averageTradeDuration", 0)),
                'market_exposure': parse_percentage(stats_data.get("Market Exposure", "0%")),
                
                # Algorithm Parameters (extract from configuration section)
                'initial_cash': parse_currency(algorithm_params.get("cash", "100000")),
                'pivot_bars': parse_integer(algorithm_params.get("pivot_bars", 20)),
                'lower_timeframe': algorithm_params.get("lower_timeframe", "5min"),
                'strategy_name': "MarketStructure",  # Default strategy name
                'resolution': "Daily"  # Default resolution
            }
            
            # Log successful extraction
            metrics_count = sum(1 for v in statistics.values() if v != 0 and v != "" and v is not None)
            logger.info(f"Successfully extracted {metrics_count} non-zero metrics from LEAN result")
            
            return statistics
            
        except Exception as e:
            logger.error(f"Error extracting statistics from {result_path}: {e}", exc_info=True)
            return None
    
    async def _cleanup_backtest_files(self, result_path: str) -> None:
        """
        Clean up backtest result files after successful storage.
        
        Args:
            result_path: Path to LEAN result directory
        """
        try:
            result_dir = Path(result_path)
            if not result_dir.exists():
                return
            
            # Archive important files before deletion (optional)
            important_files = []
            for pattern in ["*-summary.json", "*.json", "*-order-events.json"]:
                important_files.extend(result_dir.glob(pattern))
            
            if important_files:
                # Create archive directory
                archive_dir = result_dir.parent / "archived"
                archive_dir.mkdir(exist_ok=True)
                
                # Move important files to archive
                import shutil
                archive_subdir = archive_dir / result_dir.name
                archive_subdir.mkdir(exist_ok=True)
                
                for file in important_files:
                    shutil.copy2(file, archive_subdir / file.name)
                
                logger.info(f"Archived {len(important_files)} files from {result_path}")
            
            # Remove the result directory
            import shutil
            shutil.rmtree(result_dir)
            logger.info(f"Cleaned up backtest files at {result_path}")
            
        except Exception as e:
            logger.error(f"Error cleaning up backtest files at {result_path}: {e}")
            # Don't raise - cleanup failures shouldn't affect the pipeline
    
    async def _save_screener_backtest_link(self, screener_session_id: uuid.UUID, 
                                          backtest_id: str, symbol: str, 
                                          data_date: str) -> None:
        """
        Save link between screener session and backtest result.
        
        Args:
            screener_session_id: UUID of the screener session
            backtest_id: Cache hash/ID of the backtest
            symbol: Stock symbol
            data_date: Date of screening that triggered this backtest
        """
        try:
            # Get database connection
            from ..services.database import db_pool
            
            # Convert date string to date object if needed
            from datetime import datetime
            if isinstance(data_date, str):
                date_obj = datetime.strptime(data_date, '%Y-%m-%d').date()
            else:
                date_obj = data_date
            
            # Insert link
            query = """
            INSERT INTO screener_backtest_links 
                (screener_session_id, backtest_id, symbol, data_date)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (screener_session_id, backtest_id, symbol, data_date) 
            DO NOTHING
            """
            
            await db_pool.execute(
                query, 
                screener_session_id, 
                backtest_id, 
                symbol, 
                date_obj
            )
            
            logger.info(f"[DIAGNOSTIC] Successfully saved screener-backtest link:")
            logger.info(f"  - Symbol: {symbol}")
            logger.info(f"  - Date: {data_date}") 
            logger.info(f"  - Session: {screener_session_id}")
            logger.info(f"  - Backtest ID: {backtest_id}")
            
        except Exception as e:
            logger.error(f"Error saving screener-backtest link: {e}")
            # Don't raise - link save failures shouldn't fail the backtest
    
