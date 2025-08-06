#!/usr/bin/env python
"""
Example usage of the Universe Data Loader

This script demonstrates how to use the UniverseDataLoader programmatically
in other applications or scheduled jobs.
"""

import asyncio
from datetime import date, timedelta
import logging
from pathlib import Path
import sys

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from scripts.universe_data_loader import UniverseDataLoader

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def example_daily_update():
    """Example: Run daily update after market close"""
    loader = UniverseDataLoader()
    
    try:
        await loader.initialize()
        
        # Run daily update
        logger.info("Running daily update...")
        stats = await loader.load_daily_update()
        
        logger.info(f"Daily update complete:")
        logger.info(f"  - Bars loaded: {stats['total_bars']:,}")
        logger.info(f"  - Symbols updated: {stats.get('symbols_updated', 0)}")
        
        # Verify a sample of data
        logger.info("Verifying data integrity...")
        verification = await loader.verify_data_integrity(sample_size=50)
        
        if verification['data_gaps']:
            logger.warning(f"Found {len(verification['data_gaps'])} symbols with gaps")
            
    finally:
        await loader.cleanup()


async def example_historical_backfill():
    """Example: Backfill historical data for the last month"""
    loader = UniverseDataLoader()
    
    try:
        await loader.initialize()
        
        # Calculate date range (last 30 days)
        end_date = date.today() - timedelta(days=1)  # Yesterday
        start_date = end_date - timedelta(days=30)
        
        logger.info(f"Loading historical data from {start_date} to {end_date}")
        
        # First discover universe
        universe = await loader.discover_universe()
        logger.info(f"Found {len(universe)} stocks in universe")
        
        # Load historical data
        stats = await loader.load_historical_data_by_date(
            start_date=start_date,
            end_date=end_date,
            batch_size=2000  # Larger batch for faster loading
        )
        
        logger.info(f"Historical load complete:")
        logger.info(f"  - Status: {stats['status']}")
        logger.info(f"  - Dates processed: {stats['processed_dates']}/{stats['total_dates']}")
        logger.info(f"  - Total bars: {stats['total_bars']:,}")
        
    finally:
        await loader.cleanup()


async def example_specific_symbols():
    """Example: Load data for specific symbols only"""
    loader = UniverseDataLoader()
    
    # Tech giants
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "NVDA", "TSLA"]
    
    try:
        await loader.initialize()
        
        # Load last 5 days of data
        end_date = date.today() - timedelta(days=1)
        start_date = end_date - timedelta(days=5)
        
        logger.info(f"Loading data for {len(symbols)} symbols")
        
        stats = await loader.load_historical_data_by_date(
            start_date=start_date,
            end_date=end_date,
            symbols=symbols
        )
        
        logger.info(f"Load complete: {stats['total_bars']} bars loaded")
        
    finally:
        await loader.cleanup()


async def example_error_recovery():
    """Example: Check and recover from errors"""
    loader = UniverseDataLoader()
    
    try:
        await loader.initialize()
        
        # Check for recent errors
        from app.services.database import db_pool
        
        errors = await db_pool.fetch('''
            SELECT DISTINCT symbol, error_type, COUNT(*) as error_count
            FROM data_fetch_errors
            WHERE created_at > NOW() - INTERVAL '24 hours'
            AND resolved = false
            GROUP BY symbol, error_type
            ORDER BY error_count DESC
            LIMIT 10
        ''')
        
        if errors:
            logger.info(f"Found {len(errors)} symbols with recent errors")
            
            # Retry failed symbols
            failed_symbols = [e['symbol'] for e in errors]
            
            stats = await loader.load_historical_data_by_date(
                start_date=date.today() - timedelta(days=1),
                end_date=date.today() - timedelta(days=1),
                symbols=failed_symbols
            )
            
            logger.info(f"Retry complete: {stats['total_bars']} bars recovered")
            
    finally:
        await loader.cleanup()


async def main():
    """Run examples"""
    print("Universe Data Loader Examples\n")
    print("1. Daily Update")
    print("2. Historical Backfill (last 30 days)")
    print("3. Load Specific Symbols")
    print("4. Error Recovery")
    
    choice = input("\nSelect example (1-4): ")
    
    if choice == "1":
        await example_daily_update()
    elif choice == "2":
        await example_historical_backfill()
    elif choice == "3":
        await example_specific_symbols()
    elif choice == "4":
        await example_error_recovery()
    else:
        print("Invalid choice")


if __name__ == "__main__":
    asyncio.run(main())