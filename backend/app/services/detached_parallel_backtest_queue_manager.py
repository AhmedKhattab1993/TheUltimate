#!/usr/bin/env python3
"""
Detached Parallel Backtest Queue Manager

This version uses LEAN CLI's --detach flag to achieve true parallel execution
by running backtests in detached Docker containers.
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
import subprocess

from .cache_service import CacheService
from ..config import settings
from ..models.backtest import BacktestRequest
from decimal import Decimal

logger = logging.getLogger(__name__)


class DetachedParallelBacktestQueueManager:
    """
    Manages parallel backtests using isolated project directories and detached
    Docker containers for true parallel execution.
    """
    
    def __init__(
        self,
        max_parallel: int = 20,
        template_project_path: str = "/home/ahmed/TheUltimate/backend/lean/MarketStructure",
        temp_dir_base: Optional[str] = None,
        cleanup_after_run: bool = True,
        cache_service: Optional[CacheService] = None,
        enable_storage: bool = True
    ):
        """Initialize the detached parallel backtest queue manager."""
        self.max_parallel = max_parallel
        self.template_project_path = Path(template_project_path)
        
        # Use a subdirectory under lean to avoid path validation issues
        if temp_dir_base is None:
            self.temp_dir_base = self.template_project_path.parent / "isolated_backtests_detached"
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
        
        # LEAN CLI binary
        self.lean_bin = "/home/ahmed/TheUltimate/backend/lean_venv/bin/lean"
        
        logger.info(f"Initialized DetachedParallelBacktestQueueManager with max_parallel={max_parallel}")
    
    async def create_isolated_project(self, symbol: str, backtest_id: str) -> Path:
        """Create an isolated project directory for a specific backtest."""
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
    
    def update_isolated_config(self, isolated_path: Path, backtest_config: Dict[str, Any]) -> None:
        """Update the config.json in an isolated project directory."""
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
            
            # Update parameters
            config_data['parameters']['symbols'] = backtest_config['symbol']
            config_data['parameters']['startDate'] = backtest_config['start_date'].replace('-', '')
            config_data['parameters']['endDate'] = backtest_config['end_date'].replace('-', '')
            config_data['parameters']['cash'] = str(backtest_config.get('initial_cash', 100000))
            
            # Add strategy parameters
            for key, value in backtest_config.get('parameters', {}).items():
                config_data['parameters'][key] = str(value)
            
            # Write updated config
            with open(config_path, 'w') as f:
                json.dump(config_data, f, indent=2)
            
            logger.info(f"Updated config for {isolated_path.name}: {backtest_config['symbol']}")
            
        except Exception as e:
            logger.error(f"Failed to update config in {isolated_path}: {e}")
            raise
    
    async def run_detached_backtest(
        self,
        isolated_path: Path,
        backtest_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Run a backtest in detached mode using isolated project directory.
        """
        symbol = backtest_config['symbol']
        backtest_id = backtest_config.get('backtest_id', str(uuid4()))
        
        try:
            # Update the isolated config
            self.update_isolated_config(isolated_path, backtest_config)
            
            # Change to the isolated project's parent directory
            original_cwd = Path.cwd()
            os.chdir(isolated_path.parent)
            
            # Build LEAN command with detached mode
            lean_cmd = [
                self.lean_bin,
                "backtest",
                isolated_path.name,
                "--detach",  # Run in detached mode
                "--data-provider-historical", "polygon",
                "--polygon-api-key", settings.polygon_api_key
            ]
            
            logger.info(f"Starting detached backtest for {symbol}")
            
            # Run the backtest command
            start_time = time.time()
            process = await asyncio.create_subprocess_exec(
                *lean_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            # Change back to original directory
            os.chdir(original_cwd)
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else stdout.decode()
                logger.error(f"LEAN CLI failed for {symbol}: {error_msg}")
                return {
                    'symbol': symbol,
                    'error': f"LEAN CLI failed: {error_msg}",
                    'success': False
                }
            
            # Extract container ID from output
            output = stdout.decode()
            container_id = None
            for line in output.split('\n'):
                if 'Successfully started backtest' in line or 'container' in line.lower():
                    # Try to extract container ID
                    parts = line.split()
                    for part in parts:
                        if len(part) >= 12:  # Container IDs are typically 12+ chars
                            container_id = part
                            break
            
            logger.info(f"Detached backtest started for {symbol} in {time.time() - start_time:.2f}s")
            
            return {
                'symbol': symbol,
                'backtest_id': backtest_id,
                'isolated_path': str(isolated_path),
                'container_id': container_id,
                'start_time': start_time,
                'status': 'running',
                'success': True
            }
            
        except Exception as e:
            logger.error(f"Failed to run detached backtest for {symbol}: {e}")
            return {
                'symbol': symbol,
                'error': str(e),
                'success': False
            }
    
    async def wait_for_completion(self, running_backtests: List[Dict[str, Any]], timeout: int = 300) -> Dict[str, Any]:
        """
        Wait for detached backtests to complete and collect results.
        """
        results = {}
        start_wait = time.time()
        
        while running_backtests and (time.time() - start_wait) < timeout:
            completed = []
            
            for backtest in running_backtests:
                symbol = backtest['symbol']
                isolated_path = Path(backtest['isolated_path'])
                
                # Check if backtest has completed by looking for summary file
                backtest_dirs = list((isolated_path / "backtests").glob("*/"))
                
                for backtest_dir in backtest_dirs:
                    summary_files = list(backtest_dir.glob("*-summary.json"))
                    if summary_files:
                        # Backtest completed!
                        duration = time.time() - backtest['start_time']
                        logger.info(f"{symbol} completed in {duration:.2f}s")
                        
                        # Extract statistics
                        stats = await self._extract_statistics(backtest_dir)
                        
                        results[symbol] = {
                            'symbol': symbol,
                            'backtest_id': backtest['backtest_id'],
                            'result_path': str(backtest_dir),
                            'duration': duration,
                            'statistics': stats,
                            'success': True
                        }
                        
                        completed.append(backtest)
                        break
            
            # Remove completed backtests from running list
            for backtest in completed:
                running_backtests.remove(backtest)
            
            if running_backtests:
                await asyncio.sleep(1)  # Check every second
        
        # Handle timeouts
        for backtest in running_backtests:
            symbol = backtest['symbol']
            logger.error(f"{symbol} timed out after {timeout}s")
            results[symbol] = {
                'symbol': symbol,
                'error': f'Timeout after {timeout}s',
                'success': False
            }
        
        return results
    
    async def _extract_statistics(self, result_path: Path) -> Optional[Dict[str, Any]]:
        """Extract statistics from LEAN result files."""
        try:
            summary_files = list(result_path.glob("*-summary.json"))
            if summary_files:
                with open(summary_files[0], 'r') as f:
                    data = json.load(f)
                    if 'totalPerformance' in data and 'tradeStatistics' in data['totalPerformance']:
                        stats = data['totalPerformance']['tradeStatistics']
                        return {
                            'total_return': float(stats.get('totalProfitLoss', 0)) / 100000,
                            'win_rate': float(stats.get('winRate', 0)),
                            'total_trades': int(stats.get('totalNumberOfTrades', 0))
                        }
            return None
        except Exception as e:
            logger.warning(f"Failed to extract statistics: {e}")
            return None
    
    async def cleanup_isolated_project(self, isolated_path: Path) -> None:
        """Clean up an isolated project directory."""
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
        Run a batch of backtests in detached mode for true parallel execution.
        """
        start_time = time.time()
        results = {}
        isolated_paths = []
        running_backtests = []
        
        logger.info(f"Starting batch of {len(backtest_requests)} backtests in detached mode")
        
        # Start all backtests in detached mode
        for backtest_config in backtest_requests:
            symbol = backtest_config['symbol']
            backtest_id = str(uuid4())
            backtest_config['backtest_id'] = backtest_id
            
            try:
                # Create isolated project
                isolated_path = await self.create_isolated_project(symbol, backtest_id)
                isolated_paths.append(isolated_path)
                
                # Run backtest in detached mode
                result = await self.run_detached_backtest(isolated_path, backtest_config)
                
                if result.get('success'):
                    running_backtests.append(result)
                else:
                    results[symbol] = result
                    
            except Exception as e:
                logger.error(f"Failed to start backtest for {symbol}: {e}")
                if not continue_on_error:
                    raise
                results[symbol] = {
                    'symbol': symbol,
                    'error': str(e),
                    'success': False
                }
        
        # Wait for all detached backtests to complete
        logger.info(f"All {len(running_backtests)} backtests started. Waiting for completion...")
        completed_results = await self.wait_for_completion(running_backtests, timeout_per_backtest)
        results.update(completed_results)
        
        # Cleanup if requested
        if self.cleanup_after_run:
            cleanup_tasks = [self.cleanup_isolated_project(path) for path in isolated_paths]
            await asyncio.gather(*cleanup_tasks, return_exceptions=True)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Completed batch of {len(backtest_requests)} backtests in {elapsed_time:.2f}s")
        logger.info(f"Success rate: {sum(1 for r in results.values() if r.get('success'))}/{len(results)}")
        
        return results


import os  # Add this import at the top of the file