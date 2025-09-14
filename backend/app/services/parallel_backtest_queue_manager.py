#!/usr/bin/env python3
"""
Parallel Backtest Queue Manager with Isolated Project Directories

This manager creates isolated project directories for each backtest to enable
true parallel execution without config file contention.
"""

import asyncio
import json
import logging
import shutil
import tempfile
from datetime import datetime, date
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
from uuid import uuid4
import uuid
import time

from .lean_runner import LeanRunner
from .cache_service import CacheService
from ..config import settings
from ..models.backtest import BacktestRequest
from ..models.cache_models import CachedBacktestRequest
from decimal import Decimal
from ..services.database import db_pool

logger = logging.getLogger(__name__)


class ParallelBacktestQueueManager:
    """
    Manages parallel backtests using isolated project directories to avoid
    config file contention and enable true parallel execution.
    """
    
    def __init__(
        self,
        max_parallel: int = 5,
        startup_delay: float = 0.0,  # Not needed for true parallel, but kept for compatibility
        cache_service: Optional[CacheService] = None,
        enable_storage: bool = True,
        enable_cleanup: bool = True,
        screener_session_id: Optional[uuid.UUID] = None,
        bulk_id: Optional[str] = None,
        template_project_path: str = "/home/ahmed/TheUltimate/backend/lean/MarketStructure",
        temp_dir_base: Optional[str] = None
    ):
        """
        Initialize the parallel backtest queue manager.
        
        Args:
            max_parallel: Maximum number of parallel backtests
            startup_delay: Kept for compatibility but not used (no delays needed with isolation)
            cache_service: Optional cache service for result caching
            enable_storage: Whether to enable result storage
            enable_cleanup: Whether to cleanup isolated directories after completion
            screener_session_id: Optional screener session ID for linking results
            bulk_id: Optional bulk ID for this batch of backtests
            template_project_path: Path to the template project directory
            temp_dir_base: Base directory for temporary isolated projects (if None, uses lean/isolated_backtests)
        """
        self.max_parallel = max_parallel
        self.startup_delay = startup_delay  # Kept for compatibility
        self.template_project_path = Path(template_project_path)
        
        # Use a subdirectory under lean to avoid path validation issues
        if temp_dir_base is None:
            self.temp_dir_base = self.template_project_path.parent / "isolated_backtests"
        else:
            self.temp_dir_base = Path(temp_dir_base)
            
        self.cleanup_after_run = enable_cleanup
        self.cache_service = cache_service
        self.enable_storage = enable_storage
        self.screener_session_id = screener_session_id
        self.bulk_id = bulk_id
        
        # Ensure template project exists
        if not self.template_project_path.exists():
            raise ValueError(f"Template project path does not exist: {self.template_project_path}")
        
        # Create temp directory base if it doesn't exist
        self.temp_dir_base.mkdir(parents=True, exist_ok=True)
        
        # Initialize lean runner (will be used for each isolated project)
        self.lean_runner_template = LeanRunner()
        
        # Initialize storage if enabled
        if enable_storage:
            from .backtest_storage import BacktestStorage
            self.backtest_storage = BacktestStorage()
        else:
            self.backtest_storage = None
            
        # Completion callback
        self.completion_callback: Optional[Callable] = None
        
        logger.info(f"[ParallelBacktest] Initialized ParallelBacktestQueueManager with max_parallel={max_parallel}")
        logger.info(f"[ParallelBacktest] Template project path: {self.template_project_path}")
        logger.info(f"[ParallelBacktest] Temp dir base: {self.temp_dir_base}")
        logger.info(f"[ParallelBacktest] Cache service enabled: {cache_service is not None}")
        logger.info(f"[ParallelBacktest] Storage enabled: {enable_storage}")
        logger.info(f"[ParallelBacktest] Cleanup enabled: {enable_cleanup}")
    
    def set_completion_callback(self, callback: Callable):
        """Set a callback function for completion notification."""
        self.completion_callback = callback
    
    async def create_isolated_project(self, symbol: str, backtest_id: str) -> Path:
        """
        Create an isolated project directory for a specific backtest.
        
        Args:
            symbol: The symbol being backtested
            backtest_id: Unique identifier for this backtest
            
        Returns:
            Path to the isolated project directory
        """
        # Create unique directory name
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        dir_name = f"{self.template_project_path.name}_{symbol}_{backtest_id[:8]}_{timestamp}"
        isolated_path = self.temp_dir_base / dir_name
        
        logger.info(f"[IsolatedProject] Creating isolated directory for {symbol}")
        logger.info(f"[IsolatedProject] Template path: {self.template_project_path}")
        logger.info(f"[IsolatedProject] Target path: {isolated_path}")
        
        try:
            # Check if template exists
            if not self.template_project_path.exists():
                logger.error(f"[IsolatedProject] Template path does not exist: {self.template_project_path}")
                raise ValueError(f"Template project path does not exist: {self.template_project_path}")
            
            # Copy entire project directory
            logger.info(f"[IsolatedProject] Copying from {self.template_project_path} to {isolated_path}")
            shutil.copytree(self.template_project_path, isolated_path, symlinks=True)
            logger.info(f"[IsolatedProject] Successfully created isolated project directory: {isolated_path}")
            
            # Remove any existing backtests directory to start fresh
            backtests_dir = isolated_path / "backtests"
            if backtests_dir.exists():
                logger.info(f"[IsolatedProject] Removing existing backtests directory: {backtests_dir}")
                shutil.rmtree(backtests_dir)
            
            return isolated_path
            
        except Exception as e:
            logger.error(f"[IsolatedProject] Failed to create isolated project for {symbol}: {e}")
            logger.error(f"[IsolatedProject] Exception type: {type(e).__name__}")
            logger.error(f"[IsolatedProject] Exception details: {str(e)}")
            raise
    
    def update_isolated_config(self, isolated_path: Path, config_updates: Dict[str, Any]) -> None:
        """
        Update the config.json in an isolated project directory.
        
        Args:
            isolated_path: Path to the isolated project
            config_updates: Dictionary of config updates to apply
        """
        config_path = isolated_path / "config.json"
        
        try:
            # Read existing config
            if config_path.exists():
                with open(config_path, 'r') as f:
                    config_data = json.load(f)
            else:
                config_data = {}
            
            # Apply updates
            if 'parameters' not in config_data:
                config_data['parameters'] = {}
            
            config_data['parameters'].update(config_updates.get('parameters', {}))
            
            # Write updated config
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Updated config for {isolated_path.name}: {config_updates.get('parameters', {}).get('symbols', 'unknown')}")
            
        except Exception as e:
            logger.error(f"Failed to update config in {isolated_path}: {e}")
            raise
    
    async def run_isolated_backtest(
        self,
        isolated_path: Path,
        backtest_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a backtest in an isolated project directory.
        
        Args:
            isolated_path: Path to the isolated project
            backtest_config: Backtest configuration
            
        Returns:
            Backtest results dictionary
        """
        logger.info(f"[IsolatedBacktest] Starting backtest for {backtest_config['symbol']} in {isolated_path}")
        logger.info(f"[IsolatedBacktest] Config: {backtest_config}")
        
        try:
            # Create a LeanRunner instance for this isolated project
            # Use the isolated path's parent as the lean project path
            lean_runner = LeanRunner(lean_project_path=str(isolated_path.parent))
            
            # Create BacktestRequest object from config dictionary
            backtest_request = BacktestRequest(
                strategy_name=backtest_config.get('strategy', 'MarketStructure'),
                start_date=datetime.strptime(backtest_config['start_date'], '%Y-%m-%d').date(),
                end_date=datetime.strptime(backtest_config['end_date'], '%Y-%m-%d').date(),
                initial_cash=Decimal(str(backtest_config.get('initial_cash', 100000))),
                resolution=backtest_config.get('resolution', 'Daily'),
                pivot_bars=backtest_config.get('parameters', {}).get('pivot_bars', 20),
                lower_timeframe=backtest_config.get('parameters', {}).get('lower_timeframe', '5min'),
                parameters=backtest_config.get('parameters', {}),
                symbols=[backtest_config['symbol']],
                use_screener_results=False
            )
            
            # NO config file update needed! Each project is isolated
            # The LeanRunner will update the config in the isolated directory
            
            # Generate a temporary backtest ID for LEAN execution
            temp_backtest_id = str(uuid4())
            result = await lean_runner.run_backtest(
                backtest_id=temp_backtest_id,
                request=backtest_request,
                project_name=isolated_path.name
            )
            
            # Check if backtest succeeded
            if result.get('error') or not result.get('result_path'):
                logger.error(f"Backtest failed for {backtest_config['symbol']}: {result.get('error', 'Unknown error')}")
                return {
                    'symbol': backtest_config['symbol'],
                    'error': result.get('error', 'Unknown error'),
                    'success': False,
                    'status': 'failed'
                }
            
            # Parse and store results using same mechanism as original BacktestQueueManager
            backtest_id = await self._parse_and_store_results(
                symbol=backtest_config['symbol'],
                request_data=backtest_config,
                result_path=result['result_path']
            )
            
            # Add symbol and other metadata to result
            result['symbol'] = backtest_config['symbol']
            result['status'] = 'completed'
            if backtest_id:
                result['backtest_id'] = backtest_id
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to run isolated backtest for {backtest_config['symbol']}: {e}")
            return {
                'symbol': backtest_config['symbol'],
                'error': str(e),
                'success': False,
                'status': 'failed'
            }
    
    async def _parse_and_store_results(self, symbol: str, request_data: Dict[str, Any], result_path: str) -> Optional[str]:
        """
        Parse backtest results and store them to database and cache - EXACT COPY from BacktestQueueManager.
        
        Args:
            symbol: Symbol that was backtested
            request_data: Backtest request configuration
            result_path: Path to the LEAN result files
            
        Returns:
            Backtest ID (cache hash) if successful, None otherwise
        """
        try:
            if not result_path:
                logger.warning(f"No result_path for {symbol}, skipping storage")
                return None
            
            # Parse statistics from result file
            statistics = await self._extract_statistics_from_result(result_path)
            if not statistics:
                logger.warning(f"Could not extract statistics for {symbol}")
                return None
            
            # Store in cache if enabled
            if self.cache_service:
                # Extract parameters from request data
                parameters = request_data.get('parameters', {})
                
                # First create a CachedBacktestRequest to get the deterministic ID
                cache_request = CachedBacktestRequest(
                    symbol=symbol,
                    strategy_name=statistics.get('strategy_name', request_data.get('strategy', 'MarketStructure')),
                    start_date=datetime.strptime(request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(request_data['end_date'], '%Y-%m-%d').date(),
                    initial_cash=statistics.get('initial_cash', request_data.get('initial_cash', 100000)),
                    pivot_bars=statistics.get('pivot_bars', parameters.get('pivot_bars', 20)),
                    lower_timeframe=statistics.get('lower_timeframe', parameters.get('lower_timeframe', '5min'))
                )
                
                # Use cache hash as the backtest ID
                cache_hash = cache_request.get_cache_hash()
                
                # Create comprehensive CachedBacktestResult model with all new fields
                from ..models.cache_models import CachedBacktestResult
                backtest_result = CachedBacktestResult(
                    backtest_id=cache_hash,
                    symbol=symbol,
                    strategy_name=statistics.get('strategy_name', request_data.get('strategy', 'MarketStructure')),
                    
                    # New cache key parameters
                    initial_cash=statistics.get('initial_cash', request_data.get('initial_cash', 100000)),
                    pivot_bars=statistics.get('pivot_bars', parameters.get('pivot_bars', 20)),
                    lower_timeframe=statistics.get('lower_timeframe', parameters.get('lower_timeframe', '5min')),
                    
                    # Date range
                    start_date=datetime.strptime(request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(request_data['end_date'], '%Y-%m-%d').date(),
                    
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
                    execution_time_ms=None,  # Not available in parallel execution
                    result_path=result_path,
                    status='completed',
                    error_message=None,
                    cache_hit=False
                )
                
                success = await self.cache_service.save_backtest_results(backtest_result)
                if success:
                    logger.info(f"Stored backtest results for {symbol} in cache with ID: {cache_hash}")
                else:
                    logger.warning(f"Failed to store backtest results for {symbol} in cache")
            
            # Store in database using BacktestStorage (file storage)
            if self.backtest_storage:
                # Use the same cache hash that was used for cache storage
                if self.cache_service:
                    parameters = request_data.get('parameters', {})
                    cache_request = CachedBacktestRequest(
                        symbol=symbol,
                        strategy_name=statistics.get('strategy_name', request_data.get('strategy', 'MarketStructure')),
                        start_date=datetime.strptime(request_data['start_date'], '%Y-%m-%d').date(),
                        end_date=datetime.strptime(request_data['end_date'], '%Y-%m-%d').date(),
                        initial_cash=statistics.get('initial_cash', request_data.get('initial_cash', 100000)),
                        pivot_bars=statistics.get('pivot_bars', parameters.get('pivot_bars', 20)),
                        lower_timeframe=statistics.get('lower_timeframe', parameters.get('lower_timeframe', '5min'))
                    )
                    cache_hash = cache_request.get_cache_hash()
                else:
                    cache_hash = str(uuid4())
                
                backtest_result = await self.backtest_storage.save_result(
                    backtest_id=cache_hash,
                    symbol=symbol,
                    strategy_name=request_data.get('strategy', 'MarketStructure'),
                    start_date=datetime.strptime(request_data['start_date'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(request_data['end_date'], '%Y-%m-%d').date(),
                    initial_cash=request_data.get('initial_cash', 100000),
                    result_path=result_path,
                    resolution=request_data.get('resolution', 'Daily'),
                    pivot_bars=request_data.get('parameters', {}).get('pivot_bars', 20),
                    lower_timeframe=request_data.get('parameters', {}).get('lower_timeframe', '5min'),
                    screener_session_id=str(self.screener_session_id) if self.screener_session_id else None,
                    bulk_id=self.bulk_id
                )
                if backtest_result:
                    logger.info(f"Stored backtest result for {symbol} in file storage")
                else:
                    logger.warning(f"Failed to store backtest result for {symbol} in file storage")
            
            # Save link to screener_backtest_links if we have a screener_session_id
            if self.screener_session_id and 'screening_date' in request_data:
                # DIAGNOSTIC LOGGING
                logger.info(f"[DIAGNOSTIC] Saving backtest link for {symbol}:")
                logger.info(f"  - Screener session ID: {self.screener_session_id}")
                logger.info(f"  - Backtest ID: {cache_hash}")
                logger.info(f"  - Screening date: {request_data['screening_date']}")
                logger.info(f"  - Bulk ID: {self.bulk_id}")
                
                await self._save_screener_backtest_link(
                    screener_session_id=self.screener_session_id,
                    backtest_id=cache_hash,
                    symbol=symbol,
                    data_date=request_data['screening_date']
                )
                
            # Return the cache hash as the backtest ID
            return cache_hash
                
        except Exception as e:
            logger.error(f"Error parsing and storing results for {symbol}: {e}")
            # Don't raise - storage failures shouldn't fail the backtest
            return None
    
    async def _extract_statistics_from_result(self, result_path: str) -> Optional[Dict[str, Any]]:
        """
        Extract comprehensive statistics from LEAN result files - EXACT COPY from BacktestQueueManager.
        
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
            
            # Build comprehensive statistics dictionary
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
            
            # Insert link with bulk_id
            query = """
            INSERT INTO screener_backtest_links 
                (screener_session_id, backtest_id, symbol, data_date, bulk_id)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (screener_session_id, backtest_id, symbol, data_date) 
            DO UPDATE SET bulk_id = EXCLUDED.bulk_id
            """
            
            await db_pool.execute(
                query, 
                screener_session_id, 
                backtest_id, 
                symbol, 
                date_obj,
                self.bulk_id
            )
            
            logger.info(f"[DIAGNOSTIC] Successfully saved screener-backtest link:")
            logger.info(f"  - Symbol: {symbol}")
            logger.info(f"  - Date: {data_date}") 
            logger.info(f"  - Session: {screener_session_id}")
            logger.info(f"  - Backtest ID: {backtest_id}")
            logger.info(f"  - Bulk ID: {self.bulk_id}")
            
        except Exception as e:
            logger.error(f"Error saving screener-backtest link: {e}")
            # Don't raise - link save failures shouldn't fail the backtest
    
    async def cleanup_isolated_project(self, isolated_path: Path) -> None:
        """
        Clean up an isolated project directory.
        
        Args:
            isolated_path: Path to the isolated project to clean up
        """
        try:
            if isolated_path.exists() and str(isolated_path).startswith(str(self.temp_dir_base)):
                shutil.rmtree(isolated_path)
                logger.info(f"Cleaned up isolated project: {isolated_path}")
        except Exception as e:
            logger.warning(f"Failed to cleanup isolated project {isolated_path}: {e}")
    
    async def run_batch(
        self,
        backtest_requests: List[Dict[str, Any]],
        timeout_per_backtest: int = 300,
        retry_attempts: int = 1,
        continue_on_error: bool = True
    ) -> Dict[str, Any]:
        """
        Run a batch of backtests in parallel using isolated directories.
        
        Args:
            backtest_requests: List of backtest configurations
            timeout_per_backtest: Timeout in seconds for each backtest
            retry_attempts: Number of retry attempts
            continue_on_error: Whether to continue if a backtest fails
            
        Returns:
            Dictionary mapping symbols to results
        """
        start_time = time.time()
        results = {}
        cached_results = {}
        isolated_paths = []
        cache_hit_count = 0
        
        logger.info(f"[ParallelBacktest] Starting batch of {len(backtest_requests)} backtests with true parallelism")
        logger.info(f"[ParallelBacktest] Max parallel: {self.max_parallel}")
        logger.info(f"[ParallelBacktest] Template path: {self.template_project_path}")
        logger.info(f"[ParallelBacktest] Temp dir base: {self.temp_dir_base}")
        
        # Check cache first if cache service is available
        if self.cache_service:
            # Import bulk_websocket_manager if we have a bulk_id
            websocket_manager = None
            if self.bulk_id:
                try:
                    from ..api.bulk_backtest_websocket import bulk_websocket_manager
                    websocket_manager = bulk_websocket_manager
                except ImportError:
                    logger.warning("Could not import bulk_websocket_manager for cache notifications")
            
            for request in backtest_requests:
                # Extract pivot_bars and lower_timeframe from parameters
                parameters = request.get('parameters', {})
                cache_request = CachedBacktestRequest(
                    symbol=request['symbol'],
                    strategy_name=request.get('strategy', 'MarketStructure'),
                    start_date=request['start_date'],
                    end_date=request['end_date'],
                    initial_cash=request.get('initial_cash', 100000),
                    pivot_bars=parameters.get('pivot_bars', 20),
                    lower_timeframe=parameters.get('lower_timeframe', '5min')
                )
                
                cached_result = await self.cache_service.get_backtest_results(cache_request)
                if cached_result:
                    logger.info(f"Cache hit for {request['symbol']} on {request['start_date']}")
                    cache_hit_count += 1
                    # Format cached result to match expected structure - use symbol as key to match original manager
                    symbol = request['symbol']
                    
                    # Build statistics dictionary from individual fields
                    statistics = {
                        'total_return': float(cached_result.total_return) if cached_result.total_return else 0,
                        'net_profit': float(cached_result.net_profit) if cached_result.net_profit else 0,
                        'net_profit_currency': float(cached_result.net_profit_currency) if cached_result.net_profit_currency else 0,
                        'compounding_annual_return': float(cached_result.compounding_annual_return) if cached_result.compounding_annual_return else 0,
                        'final_value': float(cached_result.final_value) if cached_result.final_value else 0,
                        'start_equity': float(cached_result.start_equity) if cached_result.start_equity else 0,
                        'end_equity': float(cached_result.end_equity) if cached_result.end_equity else 0,
                        'sharpe_ratio': float(cached_result.sharpe_ratio) if cached_result.sharpe_ratio else 0,
                        'sortino_ratio': float(cached_result.sortino_ratio) if cached_result.sortino_ratio else 0,
                        'max_drawdown': float(cached_result.max_drawdown) if cached_result.max_drawdown else 0,
                        'probabilistic_sharpe_ratio': float(cached_result.probabilistic_sharpe_ratio) if cached_result.probabilistic_sharpe_ratio else 0,
                        'annual_standard_deviation': float(cached_result.annual_standard_deviation) if cached_result.annual_standard_deviation else 0,
                        'annual_variance': float(cached_result.annual_variance) if cached_result.annual_variance else 0,
                        'beta': float(cached_result.beta) if cached_result.beta else 0,
                        'alpha': float(cached_result.alpha) if cached_result.alpha else 0,
                        'total_trades': cached_result.total_trades,
                        'winning_trades': cached_result.winning_trades,
                        'losing_trades': cached_result.losing_trades,
                        'win_rate': float(cached_result.win_rate),
                        'loss_rate': float(cached_result.loss_rate) if cached_result.loss_rate else 0,
                        'average_win': float(cached_result.average_win) if cached_result.average_win else 0,
                        'average_loss': float(cached_result.average_loss) if cached_result.average_loss else 0,
                        'profit_factor': float(cached_result.profit_factor) if cached_result.profit_factor else 0,
                        'profit_loss_ratio': float(cached_result.profit_loss_ratio) if cached_result.profit_loss_ratio else 0,
                        'expectancy': float(cached_result.expectancy) if cached_result.expectancy else 0,
                        'total_orders': cached_result.total_orders,
                        'information_ratio': float(cached_result.information_ratio) if cached_result.information_ratio else 0,
                        'tracking_error': float(cached_result.tracking_error) if cached_result.tracking_error else 0,
                        'treynor_ratio': float(cached_result.treynor_ratio) if cached_result.treynor_ratio else 0,
                        'total_fees': float(cached_result.total_fees) if cached_result.total_fees else 0,
                        'estimated_strategy_capacity': float(cached_result.estimated_strategy_capacity) if cached_result.estimated_strategy_capacity else 0,
                        'lowest_capacity_asset': cached_result.lowest_capacity_asset,
                        'portfolio_turnover': float(cached_result.portfolio_turnover) if cached_result.portfolio_turnover else 0,
                        'pivot_highs_detected': cached_result.pivot_highs_detected,
                        'pivot_lows_detected': cached_result.pivot_lows_detected,
                        'bos_signals_generated': cached_result.bos_signals_generated,
                        'position_flips': cached_result.position_flips,
                        'liquidation_events': cached_result.liquidation_events,
                        'execution_time_ms': cached_result.execution_time_ms,
                        'symbol': cached_result.symbol,
                        'strategy_name': cached_result.strategy_name,
                        'initial_cash': float(cached_result.initial_cash),
                        'pivot_bars': cached_result.pivot_bars,
                        'lower_timeframe': cached_result.lower_timeframe,
                        'start_date': cached_result.start_date.isoformat(),
                        'end_date': cached_result.end_date.isoformat(),
                    }
                    
                    cached_results[symbol] = {
                        'symbol': request['symbol'],
                        'backtest_id': cached_result.backtest_id,
                        'status': 'completed',
                        'statistics': statistics,
                        'result_path': cached_result.result_path,
                        'from_cache': True,
                        'cache_hit': True
                    }
                    
                    # Note: Cached results are already in the database from when they were first run
                    # No need to save them again - just return them like the original manager
                    
                    # Send WebSocket notification for cached result
                    if websocket_manager and self.bulk_id:
                        try:
                            await websocket_manager.notify_backtest_update(
                                bulk_id=self.bulk_id,
                                backtest_id=cached_result.backtest_id,
                                symbol=request['symbol'],
                                status='completed',
                                cache_hit=True
                            )
                            logger.info(f"Sent WebSocket update for cached result: {request['symbol']}")
                        except Exception as e:
                            logger.warning(f"Failed to send WebSocket update for cached result: {e}")
                    
                    # Create screener link for cached result if needed
                    if self.screener_session_id:
                        try:
                            query = """
                            INSERT INTO screener_backtest_links 
                                (screener_session_id, backtest_id, symbol, data_date, bulk_id)
                            VALUES ($1, $2, $3, $4, $5)
                            ON CONFLICT (screener_session_id, backtest_id, symbol, data_date) 
                            DO UPDATE SET bulk_id = EXCLUDED.bulk_id
                            """
                            
                            await db_pool.execute(
                                query,
                                self.screener_session_id,
                                cached_result.backtest_id,
                                request['symbol'],
                                datetime.strptime(request['start_date'], '%Y-%m-%d').date(),
                                self.bulk_id
                            )
                            logger.info(f"Successfully created screener link for cached result: {symbol}")
                        except Exception as e:
                            logger.warning(f"Failed to create screener link for cached result: {e}")
        
        # Filter out cached requests
        uncached_requests = []
        for request in backtest_requests:
            symbol = request['symbol']
            if symbol not in cached_results:
                uncached_requests.append(request)
        
        # Create semaphore to limit parallelism
        semaphore = asyncio.Semaphore(self.max_parallel)
        
        async def run_single_backtest(backtest_config: Dict[str, Any]) -> tuple:
            """Run a single backtest with isolation."""
            async with semaphore:
                symbol = backtest_config['symbol']
                backtest_id = str(uuid4())
                backtest_config['backtest_id'] = backtest_id
                isolated_path = None
                
                try:
                    logger.info(f"[ParallelBacktest] Processing backtest for {symbol} with ID {backtest_id}")
                    # Create isolated project
                    isolated_path = await self.create_isolated_project(symbol, backtest_id)
                    isolated_paths.append(isolated_path)
                    logger.info(f"[ParallelBacktest] Created isolated path: {isolated_path}")
                    
                    # Run backtest with timeout
                    logger.info(f"[ParallelBacktest] Starting isolated backtest for {symbol}")
                    result = await asyncio.wait_for(
                        self.run_isolated_backtest(isolated_path, backtest_config),
                        timeout=timeout_per_backtest
                    )
                    logger.info(f"[ParallelBacktest] Completed backtest for {symbol} with status: {result.get('status', 'unknown')}")
                    
                    return symbol, result
                    
                except asyncio.TimeoutError:
                    logger.error(f"Backtest for {symbol} timed out after {timeout_per_backtest}s")
                    return symbol, {
                        'symbol': symbol,
                        'error': f'Timeout after {timeout_per_backtest}s',
                        'success': False
                    }
                except Exception as e:
                    logger.error(f"Backtest for {symbol} failed: {e}")
                    return symbol, {
                        'symbol': symbol,
                        'error': str(e),
                        'success': False
                    }
        
        # Run all uncached backtests in parallel
        tasks = [run_single_backtest(config) for config in uncached_requests]
        logger.info(f"[ParallelBacktest] Created {len(tasks)} tasks for parallel execution (cached: {cache_hit_count})")
        if tasks:
            logger.info(f"[ParallelBacktest] Starting asyncio.gather for {len(tasks)} tasks")
            completed_results = await asyncio.gather(*tasks, return_exceptions=True)
            logger.info(f"[ParallelBacktest] asyncio.gather completed")
        else:
            logger.info(f"[ParallelBacktest] All results were cached, no tasks to run")
            completed_results = []
        
        # Import websocket manager for notifications
        websocket_manager = None
        if self.bulk_id:
            try:
                from ..api.bulk_backtest_websocket import bulk_websocket_manager
                websocket_manager = bulk_websocket_manager
            except ImportError:
                logger.warning("Could not import bulk_websocket_manager for notifications")
        
        # Process results
        for item in completed_results:
            if isinstance(item, Exception):
                logger.error(f"Task failed with exception: {item}")
                if not continue_on_error:
                    raise item
            else:
                symbol, result = item
                results[symbol] = result
                
                # Send WebSocket notification for completed non-cached backtest
                if websocket_manager and self.bulk_id and result.get('status') == 'completed':
                    try:
                        await websocket_manager.notify_backtest_update(
                            bulk_id=self.bulk_id,
                            backtest_id=result.get('backtest_id', ''),
                            symbol=result.get('symbol', symbol),
                            status='completed',
                            cache_hit=False
                        )
                        logger.info(f"Sent WebSocket update for completed backtest: {symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to send WebSocket update for completed backtest: {e}")
                elif websocket_manager and self.bulk_id and result.get('status') == 'failed':
                    try:
                        await websocket_manager.notify_backtest_update(
                            bulk_id=self.bulk_id,
                            backtest_id=result.get('backtest_id', ''),
                            symbol=result.get('symbol', symbol),
                            status='failed',
                            cache_hit=False,
                            error=result.get('error', 'Unknown error')
                        )
                        logger.info(f"Sent WebSocket update for failed backtest: {symbol}")
                    except Exception as e:
                        logger.warning(f"Failed to send WebSocket update for failed backtest: {e}")
        
        # Cleanup if requested
        if self.cleanup_after_run:
            cleanup_tasks = [self.cleanup_isolated_project(path) for path in isolated_paths]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        # Merge cached and uncached results
        all_results = {**cached_results, **results}
        
        elapsed_time = time.time() - start_time
        total_requests = len(backtest_requests)
        successful = sum(1 for r in all_results.values() if r.get('status') != 'failed')
        
        logger.info(f"Completed batch of {total_requests} backtests in {elapsed_time:.2f}s")
        logger.info(f"Success rate: {successful}/{total_requests} ({cache_hit_count} from cache)")
        
        # Note: Screener-backtest links are already created in _parse_and_store_results for uncached results
        # and in the cache checking section for cached results - no need to duplicate here
        
        # If all results were from cache and we have a completion callback, call it immediately
        if cache_hit_count == total_requests and self.completion_callback:
            logger.info("All backtests were cache hits, calling completion callback")
            if asyncio.iscoroutinefunction(self.completion_callback):
                await self.completion_callback()
            else:
                self.completion_callback()
        elif self.completion_callback:
            # Call completion callback for non-cached results
            if asyncio.iscoroutinefunction(self.completion_callback):
                await self.completion_callback()
            else:
                self.completion_callback()
        
        return all_results