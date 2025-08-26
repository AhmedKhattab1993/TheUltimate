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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
from uuid import uuid4
import time

from .lean_runner import LeanRunner
from .cache_service import CacheService
from ..config import settings
from ..models.backtest import BacktestRequest
from decimal import Decimal

logger = logging.getLogger(__name__)


class ParallelBacktestQueueManager:
    """
    Manages parallel backtests using isolated project directories to avoid
    config file contention and enable true parallel execution.
    """
    
    def __init__(
        self,
        max_parallel: int = 5,
        template_project_path: str = "/home/ahmed/TheUltimate/backend/lean/MarketStructure",
        temp_dir_base: Optional[str] = None,
        cleanup_after_run: bool = True,
        cache_service: Optional[CacheService] = None,
        enable_storage: bool = True
    ):
        """
        Initialize the parallel backtest queue manager.
        
        Args:
            max_parallel: Maximum number of parallel backtests
            template_project_path: Path to the template project directory
            temp_dir_base: Base directory for temporary isolated projects (if None, uses lean/isolated_backtests)
            cleanup_after_run: Whether to cleanup isolated directories after completion
            cache_service: Optional cache service for result caching
            enable_storage: Whether to enable result storage
        """
        self.max_parallel = max_parallel
        self.template_project_path = Path(template_project_path)
        
        # Use a subdirectory under lean to avoid path validation issues
        if temp_dir_base is None:
            self.temp_dir_base = self.template_project_path.parent / "isolated_backtests"
        else:
            self.temp_dir_base = Path(temp_dir_base)
            
        self.cleanup_after_run = cleanup_after_run
        self.cache_service = cache_service
        self.enable_storage = enable_storage
        
        # Ensure template project exists
        if not self.template_project_path.exists():
            raise ValueError(f"Template project path does not exist: {self.template_project_path}")
        
        # Create temp directory base if it doesn't exist
        self.temp_dir_base.mkdir(parents=True, exist_ok=True)
        
        # Initialize lean runner (will be used for each isolated project)
        self.lean_runner_template = LeanRunner()
        
        logger.info(f"Initialized ParallelBacktestQueueManager with max_parallel={max_parallel}")
    
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
        
        try:
            # Copy entire project directory
            shutil.copytree(self.template_project_path, isolated_path, symlinks=True)
            logger.info(f"Created isolated project directory: {isolated_path}")
            
            # Remove any existing backtests directory to start fresh
            backtests_dir = isolated_path / "backtests"
            if backtests_dir.exists():
                shutil.rmtree(backtests_dir)
            
            return isolated_path
            
        except Exception as e:
            logger.error(f"Failed to create isolated project for {symbol}: {e}")
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
            
            # Run backtest using the isolated project
            backtest_id = backtest_config.get('backtest_id', str(uuid4()))
            result = await lean_runner.run_backtest(
                backtest_id=backtest_id,
                request=backtest_request,
                project_name=isolated_path.name
            )
            
            # Add symbol and other metadata to result
            result['symbol'] = backtest_config['symbol']
            result['backtest_id'] = backtest_id
            
            # Extract statistics if available
            if 'statistics' not in result and 'result_path' in result:
                # Try to extract statistics from result files
                result_path = Path(result['result_path'])
                stats = await self._extract_statistics(result_path)
                if stats:
                    result['statistics'] = stats
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to run isolated backtest for {backtest_config['symbol']}: {e}")
            return {
                'symbol': backtest_config['symbol'],
                'error': str(e),
                'success': False
            }
    
    async def _extract_statistics(self, result_path: Path) -> Optional[Dict[str, Any]]:
        """Extract statistics from LEAN result files."""
        try:
            # Look for summary JSON file
            summary_files = list(result_path.glob("*-summary.json"))
            if summary_files:
                with open(summary_files[0], 'r') as f:
                    data = json.load(f)
                    if 'totalPerformance' in data and 'tradeStatistics' in data['totalPerformance']:
                        stats = data['totalPerformance']['tradeStatistics']
                        return {
                            'total_return': float(stats.get('totalProfitLoss', 0)) / 100000,  # Assuming 100k initial
                            'win_rate': float(stats.get('winRate', 0)),
                            'total_trades': int(stats.get('totalNumberOfTrades', 0))
                        }
            return None
        except Exception as e:
            logger.warning(f"Failed to extract statistics: {e}")
            return None
    
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
        isolated_paths = []
        
        logger.info(f"Starting batch of {len(backtest_requests)} backtests with true parallelism")
        
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
                    # Create isolated project
                    isolated_path = await self.create_isolated_project(symbol, backtest_id)
                    isolated_paths.append(isolated_path)
                    
                    # Run backtest with timeout
                    result = await asyncio.wait_for(
                        self.run_isolated_backtest(isolated_path, backtest_config),
                        timeout=timeout_per_backtest
                    )
                    
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
        
        # Run all backtests in parallel
        tasks = [run_single_backtest(config) for config in backtest_requests]
        completed_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for item in completed_results:
            if isinstance(item, Exception):
                logger.error(f"Task failed with exception: {item}")
                if not continue_on_error:
                    raise item
            else:
                symbol, result = item
                results[symbol] = result
        
        # Cleanup if requested
        if self.cleanup_after_run:
            cleanup_tasks = [self.cleanup_isolated_project(path) for path in isolated_paths]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed batch of {len(backtest_requests)} backtests in {elapsed_time:.2f}s")
        logger.info(f"Success rate: {sum(1 for r in results.values() if not r.get('error'))}/{len(results)}")
        
        return results