#!/usr/bin/env python3
"""
Simple test script to run 5 backtests in parallel without delay or caching.
"""

import asyncio
import logging
from pathlib import Path
import sys

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from app.services.backtest_queue_manager import BacktestQueueManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_parallel_backtests():
    """Run 20 backtests in parallel without delay or caching."""
    
    # Create queue manager with no startup delay and no caching
    queue_manager = BacktestQueueManager(
        max_parallel=20,  # Set to 20 to match the number of backtests
        startup_delay=0.0,  # No delay
        cache_service=None,  # No caching
        enable_storage=True,
        enable_cleanup=False
    )
    
    # Define 20 backtest requests with diverse symbols
    symbols = [
        'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'META',
        'NVDA', 'TSLA', 'BRK.B', 'JPM', 'JNJ',
        'V', 'PG', 'UNH', 'HD', 'DIS',
        'MA', 'PYPL', 'BAC', 'NFLX', 'ADBE'
    ]
    
    backtest_requests = []
    for symbol in symbols:
        backtest_requests.append({
            'symbol': symbol,
            'strategy': 'MarketStructure',
            'start_date': '2025-01-01',
            'end_date': '2025-01-31',
            'initial_cash': 100000,
            'resolution': 'Daily',
            'parameters': {
                'pivot_bars': 20,
                'lower_timeframe': '5min'
            }
        })
    
    logger.info(f"Starting {len(backtest_requests)} backtests in parallel...")
    
    # Run all backtests
    results = await queue_manager.run_batch(
        backtest_requests,
        timeout_per_backtest=300,  # 5 minutes timeout
        retry_attempts=1,
        continue_on_error=True
    )
    
    logger.info(f"\nCompleted {len(results)} backtests:")
    
    # Print summary of results
    for symbol, result in results.items():
        if 'error' in result:
            logger.error(f"{symbol}: ERROR - {result['error']}")
        else:
            stats = result.get('statistics', {})
            logger.info(f"{symbol}: Total Return: {stats.get('total_return', 0):.2%}, "
                       f"Win Rate: {stats.get('win_rate', 0):.2%}, "
                       f"Total Trades: {stats.get('total_trades', 0)}")
    
    logger.info("\nAll backtests completed!")


async def main():
    """Main entry point."""
    await run_parallel_backtests()


if __name__ == "__main__":
    asyncio.run(main())