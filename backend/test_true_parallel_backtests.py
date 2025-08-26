#!/usr/bin/env python3
"""
Test script to run 5 backtests in TRUE parallel using isolated directories.
This bypasses the config.json bottleneck by giving each backtest its own project directory.
"""

import asyncio
import logging
from pathlib import Path
import sys
import time

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from app.services.parallel_backtest_queue_manager import ParallelBacktestQueueManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_true_parallel_backtests():
    """Run 5 backtests in true parallel using isolated directories."""
    
    logger.info("=" * 80)
    logger.info("TRUE PARALLEL BACKTEST TEST - Using Isolated Directories")
    logger.info("=" * 80)
    
    # Create parallel queue manager
    queue_manager = ParallelBacktestQueueManager(
        max_parallel=5,
        template_project_path="/home/ahmed/TheUltimate/backend/lean/MarketStructure",
        temp_dir_base=None,  # Use default: lean/isolated_backtests
        cleanup_after_run=False,  # Keep directories for inspection
        cache_service=None,  # No caching
        enable_storage=True
    )
    
    # Define 5 backtest requests - same date range for simplicity
    backtest_requests = [
        {
            'symbol': 'AAPL',
            'strategy': 'MarketStructure',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'initial_cash': 100000,
            'resolution': 'Daily',
            'parameters': {
                'pivot_bars': 20,
                'lower_timeframe': '5min'
            }
        },
        {
            'symbol': 'GOOGL',
            'strategy': 'MarketStructure',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'initial_cash': 100000,
            'resolution': 'Daily',
            'parameters': {
                'pivot_bars': 20,
                'lower_timeframe': '5min'
            }
        },
        {
            'symbol': 'MSFT',
            'strategy': 'MarketStructure',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'initial_cash': 100000,
            'resolution': 'Daily',
            'parameters': {
                'pivot_bars': 20,
                'lower_timeframe': '5min'
            }
        },
        {
            'symbol': 'AMZN',
            'strategy': 'MarketStructure',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'initial_cash': 100000,
            'resolution': 'Daily',
            'parameters': {
                'pivot_bars': 20,
                'lower_timeframe': '5min'
            }
        },
        {
            'symbol': 'META',
            'strategy': 'MarketStructure',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'initial_cash': 100000,
            'resolution': 'Daily',
            'parameters': {
                'pivot_bars': 20,
                'lower_timeframe': '5min'
            }
        }
    ]
    
    logger.info(f"Starting {len(backtest_requests)} backtests in TRUE parallel...")
    logger.info("Each backtest will have its own isolated project directory")
    logger.info("No config file locking or contention!")
    
    start_time = time.time()
    
    # Run all backtests in parallel
    results = await queue_manager.run_batch(
        backtest_requests,
        timeout_per_backtest=300,  # 5 minutes timeout
        retry_attempts=1,
        continue_on_error=True
    )
    
    elapsed_time = time.time() - start_time
    
    logger.info("\n" + "=" * 80)
    logger.info(f"RESULTS - Completed in {elapsed_time:.2f} seconds")
    logger.info("=" * 80)
    
    # Print summary of results
    success_count = 0
    for symbol, result in results.items():
        if 'error' in result:
            logger.error(f"{symbol}: ❌ ERROR - {result['error']}")
        else:
            success_count += 1
            stats = result.get('statistics', {})
            logger.info(f"{symbol}: ✅ SUCCESS - "
                       f"Total Return: {stats.get('total_return', 0):.2%}, "
                       f"Win Rate: {stats.get('win_rate', 0):.2%}, "
                       f"Total Trades: {stats.get('total_trades', 0)}")
    
    logger.info("\n" + "=" * 80)
    logger.info(f"SUMMARY: {success_count}/{len(results)} backtests completed successfully")
    logger.info(f"True parallel execution time: {elapsed_time:.2f} seconds")
    logger.info(f"Average time per backtest: {elapsed_time/len(results):.2f} seconds")
    logger.info("=" * 80)
    
    # Show where isolated directories are located
    logger.info("\nIsolated project directories kept at: /home/ahmed/TheUltimate/backend/lean/isolated_backtests/")
    logger.info("You can inspect them to verify each had its own config.json")
    
    return results


async def main():
    """Main entry point."""
    try:
        results = await run_true_parallel_backtests()
        
        # Optional: Clean up manually
        logger.info("\nTo clean up isolated directories, run:")
        logger.info("rm -rf /home/ahmed/TheUltimate/backend/lean/isolated_backtests/")
        
    except Exception as e:
        logger.error(f"Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(main())