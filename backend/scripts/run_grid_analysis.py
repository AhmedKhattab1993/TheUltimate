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
import asyncpg

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GridAnalysisOrchestrator:
    """Main orchestrator for grid analysis."""
    
    def __init__(self):
        self.conn = None
        
    async def __aenter__(self):
        self.conn = await asyncpg.connect(settings.database_url)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.conn.close()
    
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
            # For now, just check what symbols we have data for
            query = """
            SELECT DISTINCT symbol 
            FROM daily_bars 
            WHERE time::date = $1 
            ORDER BY symbol
            """
            symbols = await self.conn.fetch(query, process_date)
            logger.info(f"Found {len(symbols)} symbols with data for {process_date}")
            
            if symbols:
                logger.info(f"First 10 symbols: {[s['symbol'] for s in symbols[:10]]}")
                logger.info(f"Last 10 symbols: {[s['symbol'] for s in symbols[-10:]]}")
                
                # Log all symbols to a file if needed
                symbols_file = Path(f"symbols_{process_date}.txt")
                with open(symbols_file, 'w') as f:
                    for sym in symbols:
                        f.write(f"{sym['symbol']}\n")
                logger.info(f"All symbols written to {symbols_file}")
            
            results["screening"] = {
                "symbols_count": len(symbols),
                "status": "completed" if symbols else "no_data"
            }
            
        except Exception as e:
            logger.error(f"Error in screening phase: {e}")
            results["screening"] = {"status": "error", "error": str(e)}
        
        # Phase 2: Backtesting
        logger.info("\nPhase 2: Running backtests...")
        try:
            # For now, just show what we would do
            if symbols:
                pivot_bars_values = [1, 2, 3, 5, 10, 20]
                total_backtests = len(symbols) * len(pivot_bars_values)
                logger.info(f"Would run {total_backtests} backtests:")
                logger.info(f"  - {len(symbols)} symbols")
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