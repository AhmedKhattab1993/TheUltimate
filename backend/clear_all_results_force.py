#!/usr/bin/env python3
"""
Script to clear all data from screener results, backtest results, and linkage tables.
Non-interactive version - use with caution!
"""

import asyncio
import asyncpg
import logging
from pathlib import Path
import sys

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from app.services.database import db_pool
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def clear_all_results():
    """Clear all results from the database tables."""
    try:
        # Connect to database
        await db_pool.initialize()
        
        logger.info("Starting to clear all results data...")
        
        # List of tables to clear in order (respecting foreign key constraints)
        tables_to_clear = [
            ('screener_backtest_links', 'screener-backtest linkage'),
            ('market_structure_results', 'backtest results'),
            ('backtest_trades', 'backtest trades'),
            ('screener_results', 'screener results'),
        ]
        
        # Clear each table
        for table_name, description in tables_to_clear:
            try:
                # Get count before deletion
                count_query = f"SELECT COUNT(*) FROM {table_name}"
                count = await db_pool.fetchval(count_query)
                
                if count > 0:
                    # Delete all records
                    delete_query = f"DELETE FROM {table_name}"
                    await db_pool.execute(delete_query)
                    logger.info(f"Deleted {count:,} records from {table_name} ({description})")
                else:
                    logger.info(f"No records to delete from {table_name} ({description})")
                    
            except Exception as e:
                logger.error(f"Error clearing {table_name}: {e}")
                raise
        
        # Verify all tables are empty
        logger.info("\nVerifying all tables are empty:")
        for table_name, description in tables_to_clear:
            count = await db_pool.fetchval(f"SELECT COUNT(*) FROM {table_name}")
            logger.info(f"  {table_name}: {count} records")
        
        # Check the view
        view_count = await db_pool.fetchval("SELECT COUNT(*) FROM combined_screener_backtest_results")
        logger.info(f"  combined_screener_backtest_results (view): {view_count} records")
        
        logger.info("\n✅ All results data has been cleared successfully!")
        
        # Show a warning about cache
        logger.warning("\n⚠️  Note: This script does NOT clear the cache tables.")
        logger.warning("    If you also want to clear cached results, run:")
        logger.warning("    python clear_cache.py")
        
    except Exception as e:
        logger.error(f"Error clearing results: {e}")
        raise
    finally:
        # Close database connection
        if db_pool._pool:
            await db_pool.close()


async def main():
    """Main entry point."""
    logger.warning("\n" + "="*60)
    logger.warning("CLEARING ALL RESULTS DATA")
    logger.warning("="*60)
    
    await clear_all_results()


if __name__ == "__main__":
    asyncio.run(main())