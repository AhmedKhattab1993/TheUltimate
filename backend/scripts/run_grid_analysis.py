#!/usr/bin/env python3
"""
Grid Analysis Script - Comprehensive screening and backtesting for all symbols.

Usage:
    python scripts/run_grid_analysis.py --date 2024-03-01
    python scripts/run_grid_analysis.py --start-date 2024-01-01 --end-date 2024-03-01
"""

import asyncio
import argparse
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Any
import sys
import os
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.services.date_utils import get_trading_days_between
from app.services.grid_screening_calculator import GridScreeningCalculator
from app.services.database import DatabasePool
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GridAnalysisOrchestrator:
    """Main orchestrator for grid analysis."""
    
    def __init__(self):
        self.db_pool = None
        self.screening_calculator = None
        
    async def __aenter__(self):
        # Create database pool
        self.db_pool = await asyncpg.create_pool(
            settings.database_url,
            min_size=5,
            max_size=20
        )
        
        # Initialize calculator
        self.screening_calculator = GridScreeningCalculator(self.db_pool)
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.db_pool:
            await self.db_pool.close()
    
    async def process_date(self, process_date: date) -> Dict[str, Any]:
        """Process a single date - run screening and backtests."""
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing date: {process_date}")
        logger.info(f"{'='*60}")
        
        results = {
            "date": process_date,
            "screening": None,
            "backtesting": None
        }
        
        # Phase 1: Screening
        logger.info("\nPhase 1: Calculating screening values...")
        try:
            # Use the screening calculator to process all symbols
            screening_result = await self.screening_calculator.calculate_for_date(
                process_date,
                limit=None  # Process all symbols
            )
            
            logger.info(f"Screening results:")
            logger.info(f"  Total symbols: {screening_result['total_symbols']}")
            logger.info(f"  Already processed: {screening_result.get('already_processed', 0)}")
            logger.info(f"  Newly processed: {screening_result['processed']}")
            logger.info(f"  Errors: {screening_result['errors']}")
            logger.info(f"  Duration: {screening_result['duration_seconds']:.2f} seconds")
            
            results["screening"] = {
                "symbols_count": screening_result['total_symbols'],
                "processed": screening_result['processed'],
                "errors": screening_result['errors'],
                "status": "completed" if screening_result['processed'] > 0 or screening_result.get('already_processed', 0) > 0 else "no_data"
            }
            
            # Store symbols count for backtest phase
            self._symbols_count = screening_result['total_symbols']
            
        except Exception as e:
            logger.error(f"Error in screening phase: {e}")
            results["screening"] = {"status": "error", "error": str(e)}
            self._symbols_count = 0
        
        # Phase 2: Backtesting
        logger.info("\nPhase 2: Running backtests...")
        try:
            # For now, just show what we would do
            if self._symbols_count > 0:
                pivot_bars_values = [1, 2, 3, 5, 10, 20]
                total_backtests = self._symbols_count * len(pivot_bars_values)
                logger.info(f"Would run {total_backtests} backtests:")
                logger.info(f"  - {self._symbols_count} symbols")
                logger.info(f"  - {len(pivot_bars_values)} pivot_bars values: {pivot_bars_values}")
                logger.info(f"  - Lower timeframe: 1 minute")
                
                results["backtesting"] = {
                    "total_backtests": total_backtests,
                    "status": "planned"
                }
            else:
                results["backtesting"] = {"status": "skipped", "reason": "no_symbols"}
                
        except Exception as e:
            logger.error(f"Error in backtesting phase: {e}")
            results["backtesting"] = {"status": "error", "error": str(e)}
        
        return results
    
    async def run(self, start_date: date, end_date: date):
        """Run grid analysis for date range."""
        # Get trading days between dates
        trading_days = get_trading_days_between(start_date, end_date)
        
        # Process in reverse order (most recent first)
        trading_days.reverse()
        
        logger.info(f"\nProcessing {len(trading_days)} trading days")
        logger.info(f"From: {end_date} (most recent)")
        logger.info(f"To: {start_date} (oldest)")
        
        all_results = []
        
        for i, trading_day in enumerate(trading_days, 1):
            logger.info(f"\nProcessing day {i}/{len(trading_days)}")
            
            try:
                result = await self.process_date(trading_day)
                all_results.append(result)
                
                # Show summary
                screening = result.get("screening", {})
                backtesting = result.get("backtesting", {})
                
                logger.info(f"\nSummary for {trading_day}:")
                logger.info(f"  Screening: {screening.get('status')} - {screening.get('symbols_count', 0)} symbols")
                logger.info(f"  Backtesting: {backtesting.get('status')} - {backtesting.get('total_backtests', 0)} planned")
                
            except Exception as e:
                logger.error(f"Failed to process {trading_day}: {e}")
                all_results.append({
                    "date": trading_day,
                    "error": str(e)
                })
        
        # Final summary
        logger.info(f"\n{'='*60}")
        logger.info("Grid Analysis Complete")
        logger.info(f"{'='*60}")
        logger.info(f"Processed {len(all_results)} days")
        
        successful = sum(1 for r in all_results if r.get("screening", {}).get("status") == "completed")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {len(all_results) - successful}")


def parse_date(date_str: str) -> date:
    """Parse date string to date object."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def main():
    parser = argparse.ArgumentParser(description="Run grid analysis for symbols")
    
    # Date arguments
    parser.add_argument("--date", type=str, help="Single date to process (YYYY-MM-DD)")
    parser.add_argument("--start-date", type=str, help="Start date for range (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, help="End date for range (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.date:
        # Single date mode
        start_date = end_date = parse_date(args.date)
    elif args.start_date and args.end_date:
        # Date range mode
        start_date = parse_date(args.start_date)
        end_date = parse_date(args.end_date)
        
        if start_date > end_date:
            logger.error("Start date must be before or equal to end date")
            sys.exit(1)
    else:
        logger.error("Must specify either --date or both --start-date and --end-date")
        sys.exit(1)
    
    # Run the analysis
    async def run():
        async with GridAnalysisOrchestrator() as orchestrator:
            await orchestrator.run(start_date, end_date)
    
    asyncio.run(run())


if __name__ == "__main__":
    main()