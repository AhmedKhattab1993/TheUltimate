#!/usr/bin/env python3
"""
Clear Grid Analysis Tables

This script clears data from the grid_screening and grid_market_structure tables.

Usage:
    python scripts/clear_grid_tables.py                    # Clear all data
    python scripts/clear_grid_tables.py --date 2025-09-10  # Clear specific date
    python scripts/clear_grid_tables.py --symbol AAPL      # Clear specific symbol
"""

import asyncio
import argparse
import logging
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.config import settings
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def clear_grid_tables(date: str = None, symbol: str = None):
    """Clear data from grid analysis tables."""
    
    conn = await asyncpg.connect(settings.database_url)
    
    try:
        # Build WHERE clauses
        where_conditions = []
        params = []
        param_count = 0
        
        if date:
            param_count += 1
            where_conditions.append(f"date = ${param_count}")
            params.append(datetime.strptime(date, "%Y-%m-%d").date())
            
        if symbol:
            param_count += 1
            where_conditions.append(f"symbol = ${param_count}")
            params.append(symbol)
        
        where_clause = " AND ".join(where_conditions) if where_conditions else "1=1"
        
        # Check grid_screening table
        count_query = f"SELECT COUNT(*) FROM grid_screening WHERE {where_clause}"
        screening_count = await conn.fetchval(count_query, *params)
        logger.info(f"\nGrid Screening Table:")
        logger.info(f"  Records to delete: {screening_count:,}")
        
        if screening_count > 0:
            # Show sample records
            sample_query = f"""
            SELECT symbol, date, price, ma_20, rsi_14, gap_percent 
            FROM grid_screening 
            WHERE {where_clause}
            ORDER BY date DESC, symbol 
            LIMIT 5
            """
            samples = await conn.fetch(sample_query, *params)
            logger.info("  Sample records:")
            for row in samples:
                logger.info(f"    {row['symbol']} on {row['date']}: Price=${row['price']}, MA20=${row['ma_20']}, RSI={row['rsi_14']}")
        
        # Check grid_market_structure table
        # Adjust WHERE clause for this table (backtest_date instead of date)
        ms_where = where_clause.replace("date =", "backtest_date =")
        count_query = f"SELECT COUNT(*) FROM grid_market_structure WHERE {ms_where}"
        ms_count = await conn.fetchval(count_query, *params)
        logger.info(f"\nGrid Market Structure Table:")
        logger.info(f"  Records to delete: {ms_count:,}")
        
        if ms_count > 0:
            # Show sample records
            sample_query = f"""
            SELECT symbol, backtest_date, pivot_bars, total_return, sharpe_ratio, total_trades 
            FROM grid_market_structure 
            WHERE {ms_where}
            ORDER BY backtest_date DESC, symbol, pivot_bars 
            LIMIT 5
            """
            samples = await conn.fetch(sample_query, *params)
            logger.info("  Sample records:")
            for row in samples:
                logger.info(f"    {row['symbol']} on {row['backtest_date']} (pivot={row['pivot_bars']}): Return={row['total_return']}%, Sharpe={row['sharpe_ratio']}")
        
        total_records = screening_count + ms_count
        logger.info(f"\nTotal records to delete: {total_records:,}")
        
        if total_records == 0:
            logger.info("No records to delete.")
            return
        
        logger.info("\nDeleting records...")
        
        # Delete from grid_screening
        if screening_count > 0:
            delete_query = f"DELETE FROM grid_screening WHERE {where_clause}"
            result = await conn.execute(delete_query, *params)
            logger.info(f"  Deleted {screening_count:,} records from grid_screening")
        
        # Delete from grid_market_structure
        if ms_count > 0:
            delete_query = f"DELETE FROM grid_market_structure WHERE {ms_where}"
            result = await conn.execute(delete_query, *params)
            logger.info(f"  Deleted {ms_count:,} records from grid_market_structure")
        
        logger.info("\n✓ Tables cleared successfully!")
    
    finally:
        await conn.close()


def main():
    parser = argparse.ArgumentParser(description="Clear grid analysis tables")
    parser.add_argument("--date", type=str, help="Clear only records for specific date (YYYY-MM-DD)")
    parser.add_argument("--symbol", type=str, help="Clear only records for specific symbol")
    
    args = parser.parse_args()
    
    # Run the clear operation
    asyncio.run(clear_grid_tables(
        date=args.date,
        symbol=args.symbol
    ))


if __name__ == "__main__":
    main()