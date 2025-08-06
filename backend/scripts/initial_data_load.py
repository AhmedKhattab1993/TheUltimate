#!/usr/bin/env python3
"""
Initial data load script for TimescaleDB stock screener

This script performs the initial historical data load from Polygon.io
into the TimescaleDB database.
"""
import asyncio
import logging
import sys
from pathlib import Path
from datetime import date, datetime, timedelta
import argparse
from typing import List, Optional

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from app.services.data_collector import DataCollector
from app.services.database import db_pool, check_database_connection
from app.services.polygon_client import PolygonClient
from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class InitialDataLoader:
    """Handles initial data loading with progress tracking"""
    
    def __init__(self, start_date: date, end_date: date, symbols: Optional[List[str]] = None):
        self.start_date = start_date
        self.end_date = end_date
        self.symbols = symbols
        self.progress_file = Path("data_load_progress.json")
        
    async def load_progress(self) -> dict:
        """Load progress from file"""
        if self.progress_file.exists():
            import json
            with open(self.progress_file, 'r') as f:
                return json.load(f)
        return {}
        
    async def save_progress(self, progress: dict):
        """Save progress to file"""
        import json
        with open(self.progress_file, 'w') as f:
            json.dump(progress, f, indent=2, default=str)
            
    async def run(self):
        """Run the initial data load"""
        start_time = datetime.now()
        
        # Check database connection
        if not await check_database_connection():
            logger.error("Database connection failed. Please check your configuration.")
            return 1
            
        logger.info("Starting initial data load")
        logger.info(f"Date range: {self.start_date} to {self.end_date}")
        
        # Load progress
        progress = await self.load_progress()
        
        try:
            async with PolygonClient() as polygon_client:
                collector = DataCollector(polygon_client)
                
                # Step 1: Update symbols table
                if not progress.get("symbols_updated"):
                    logger.info("Step 1: Updating symbols table...")
                    symbol_count = await collector.update_symbols_table()
                    logger.info(f"Updated {symbol_count} symbols")
                    progress["symbols_updated"] = True
                    await self.save_progress(progress)
                else:
                    logger.info("Step 1: Symbols table already updated (skipping)")
                    
                # Step 2: Get symbols to load
                if self.symbols:
                    symbols_to_load = self.symbols
                else:
                    # Get all active symbols from database
                    rows = await db_pool.fetch('''
                        SELECT symbol FROM symbols 
                        WHERE active = true 
                        AND type IN ('CS', 'ADRC', 'ETF')  -- Common stock, ADR, ETF
                        ORDER BY symbol
                    ''')
                    symbols_to_load = [row['symbol'] for row in rows]
                    
                logger.info(f"Found {len(symbols_to_load)} symbols to load")
                
                # Step 3: Load data day by day (for bulk endpoint efficiency)
                current_date = self.start_date
                days_processed = progress.get("days_processed", [])
                
                while current_date <= self.end_date:
                    # Skip weekends
                    if current_date.weekday() >= 5:
                        current_date += timedelta(days=1)
                        continue
                        
                    # Check if already processed
                    date_str = current_date.isoformat()
                    if date_str in days_processed:
                        logger.info(f"Skipping {date_str} (already processed)")
                        current_date += timedelta(days=1)
                        continue
                        
                    logger.info(f"\nLoading data for {current_date}...")
                    
                    try:
                        # Use bulk endpoint for daily data
                        stats = await collector.collect_daily_data_for_date(
                            target_date=current_date,
                            symbols=symbols_to_load if self.symbols else None,
                            use_bulk_endpoint=True
                        )
                        
                        logger.info(
                            f"Loaded {stats['bars_stored']} bars for {current_date} "
                            f"({stats['total_symbols']} symbols, {stats['errors']} errors)"
                        )
                        
                        # Update progress
                        days_processed.append(date_str)
                        progress["days_processed"] = days_processed
                        progress["last_processed_date"] = date_str
                        progress["total_bars_loaded"] = progress.get("total_bars_loaded", 0) + stats['bars_stored']
                        await self.save_progress(progress)
                        
                    except Exception as e:
                        logger.error(f"Error loading data for {current_date}: {e}")
                        # Continue with next day
                        
                    current_date += timedelta(days=1)
                    
                # Step 4: Fill any gaps
                if not self.symbols:  # Only for full load
                    logger.info("\nStep 4: Checking for data gaps...")
                    
                    # Get symbols with potential gaps
                    gap_check_symbols = await db_pool.fetch('''
                        SELECT DISTINCT symbol 
                        FROM daily_bars 
                        WHERE time >= $1 AND time <= $2
                        GROUP BY symbol
                        HAVING COUNT(DISTINCT DATE(time)) < $3
                    ''', 
                        self.start_date, 
                        self.end_date,
                        (self.end_date - self.start_date).days * 0.7  # 70% threshold
                    )
                    
                    if gap_check_symbols:
                        gap_symbols = [row['symbol'] for row in gap_check_symbols]
                        logger.info(f"Found {len(gap_symbols)} symbols with potential gaps")
                        
                        gap_stats = await collector.fill_missing_data(
                            symbols=gap_symbols,
                            start_date=self.start_date,
                            end_date=self.end_date
                        )
                        
                        logger.info(f"Gap filling complete: {gap_stats}")
                        
        except Exception as e:
            logger.error(f"Fatal error during data load: {e}")
            return 1
            
        finally:
            await db_pool.close()
            
        # Summary
        duration = datetime.now() - start_time
        logger.info("\n" + "="*50)
        logger.info("Initial data load complete!")
        logger.info(f"Total duration: {duration}")
        logger.info(f"Total bars loaded: {progress.get('total_bars_loaded', 0)}")
        logger.info(f"Days processed: {len(progress.get('days_processed', []))}")
        logger.info("="*50)
        
        # Clean up progress file
        if self.progress_file.exists():
            self.progress_file.unlink()
            
        return 0


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Load historical stock data into TimescaleDB")
    parser.add_argument(
        "--start-date",
        type=str,
        required=True,
        help="Start date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--end-date",
        type=str,
        required=True,
        help="End date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--symbols",
        type=str,
        nargs="+",
        help="Specific symbols to load (optional, loads all if not specified)"
    )
    parser.add_argument(
        "--skip-migration",
        action="store_true",
        help="Skip database migration check"
    )
    
    args = parser.parse_args()
    
    # Parse dates
    try:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").date()
    except ValueError:
        logger.error("Invalid date format. Use YYYY-MM-DD")
        return 1
        
    # Validate dates
    if end_date < start_date:
        logger.error("End date must be after start date")
        return 1
        
    if end_date > date.today():
        logger.error("End date cannot be in the future")
        return 1
        
    # Run migrations first (unless skipped)
    if not args.skip_migration:
        logger.info("Running database migrations...")
        from migrations.run_migrations import MigrationRunner
        
        runner = MigrationRunner(settings.database_url)
        try:
            await runner.run_migrations()
        except Exception as e:
            logger.error(f"Migration failed: {e}")
            return 1
            
    # Run data loader
    loader = InitialDataLoader(
        start_date=start_date,
        end_date=end_date,
        symbols=args.symbols
    )
    
    return await loader.run()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))