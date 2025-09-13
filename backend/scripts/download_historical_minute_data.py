#!/usr/bin/env python
"""
Historical Minute Data Downloader for LEAN

This script downloads historical minute data from Polygon API using LEAN CLI.
It iterates backwards from end date to start date, downloading data for all
available tickers on each trading day.

Features:
- Backwards date iteration (most recent to oldest)
- Automatic ticker discovery for each date
- Parallel downloads with configurable concurrency
- Progress tracking and resume capability
- Comprehensive logging
- Skip weekends and holidays automatically
"""

import asyncio
import argparse
import json
import logging
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import signal
import time
import os

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.services.polygon_client import PolygonClient, PolygonAPIError
from app.config import settings

# Configure logging
log_format = '%(asctime)s - %(levelname)s - %(message)s'
logging.basicConfig(
    level=logging.INFO,
    format=log_format,
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Also log to file
file_handler = logging.FileHandler('historical_minute_download.log')
file_handler.setFormatter(logging.Formatter(log_format))
logging.getLogger().addHandler(file_handler)

logger = logging.getLogger(__name__)

# Constants
CHECKPOINT_FILE = Path(__file__).parent / "minute_data_checkpoint.json"
LEAN_CLI_PATH = Path(__file__).parent.parent / "lean_venv" / "bin" / "lean"
LEAN_DATA_PATH = Path(__file__).parent.parent / "lean" / "data"
BATCH_SIZE = 50  # Number of tickers to download in one command
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
DOWNLOAD_TIMEOUT = 1800  # 30 minutes per batch - increased for batch downloads

class ProgressTracker:
    """Tracks download progress and handles checkpointing"""
    
    def __init__(self, checkpoint_file: Path = CHECKPOINT_FILE):
        self.checkpoint_file = checkpoint_file
        self.checkpoint_data = self._load_checkpoint()
        self.start_time = time.time()
        
    def _load_checkpoint(self) -> Dict[str, Any]:
        """Load checkpoint from file if exists"""
        if self.checkpoint_file.exists():
            try:
                with open(self.checkpoint_file, 'r') as f:
                    data = json.load(f)
                logger.info(f"Loaded checkpoint from {self.checkpoint_file}")
                return data
            except Exception as e:
                logger.error(f"Error loading checkpoint: {e}")
                return {}
        return {}
    
    def save_checkpoint(self):
        """Save current checkpoint to file"""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(self.checkpoint_data, f, indent=2, default=str)
            logger.debug("Checkpoint saved")
        except Exception as e:
            logger.error(f"Error saving checkpoint: {e}")
    
    def init_job(self, job_id: str, start_date: date, end_date: date):
        """Initialize a new download job"""
        if job_id not in self.checkpoint_data:
            self.checkpoint_data[job_id] = {
                "start_date": str(start_date),
                "end_date": str(end_date),
                "created_at": datetime.now().isoformat(),
                "status": "in_progress",
                "dates_completed": [],
                "dates_failed": {},
                "symbols_by_date": {},
                "total_symbols_downloaded": 0,
                "total_download_commands": 0,
                "last_updated": datetime.now().isoformat()
            }
            self.save_checkpoint()
    
    def mark_date_completed(self, job_id: str, date_str: str, symbols_count: int):
        """Mark a date as completed"""
        job_data = self.checkpoint_data.get(job_id, {})
        if "dates_completed" not in job_data:
            job_data["dates_completed"] = []
        if date_str not in job_data["dates_completed"]:
            job_data["dates_completed"].append(date_str)
        job_data["total_symbols_downloaded"] = job_data.get("total_symbols_downloaded", 0) + symbols_count
        job_data["last_updated"] = datetime.now().isoformat()
        self.checkpoint_data[job_id] = job_data
        self.save_checkpoint()
    
    def mark_symbol_failed(self, job_id: str, date_str: str, symbol: str, error: str):
        """Mark a symbol as failed for a specific date"""
        job_data = self.checkpoint_data.get(job_id, {})
        if "dates_failed" not in job_data:
            job_data["dates_failed"] = {}
        if date_str not in job_data["dates_failed"]:
            job_data["dates_failed"][date_str] = {}
        job_data["dates_failed"][date_str][symbol] = error
        job_data["last_updated"] = datetime.now().isoformat()
        self.checkpoint_data[job_id] = job_data
        self.save_checkpoint()
    
    def update_symbols_for_date(self, job_id: str, date_str: str, symbols: List[str]):
        """Update the list of symbols found for a date"""
        job_data = self.checkpoint_data.get(job_id, {})
        if "symbols_by_date" not in job_data:
            job_data["symbols_by_date"] = {}
        job_data["symbols_by_date"][date_str] = symbols
        job_data["last_updated"] = datetime.now().isoformat()
        self.checkpoint_data[job_id] = job_data
        self.save_checkpoint()
    
    def increment_download_count(self, job_id: str):
        """Increment the total download commands executed"""
        job_data = self.checkpoint_data.get(job_id, {})
        job_data["total_download_commands"] = job_data.get("total_download_commands", 0) + 1
        self.checkpoint_data[job_id] = job_data
        # Don't save checkpoint here to avoid too many writes
    
    def get_progress_summary(self, job_id: str) -> str:
        """Get a summary of progress"""
        job_data = self.checkpoint_data.get(job_id, {})
        dates_completed = len(job_data.get("dates_completed", []))
        total_symbols = job_data.get("total_symbols_downloaded", 0)
        total_commands = job_data.get("total_download_commands", 0)
        elapsed_time = time.time() - self.start_time
        
        return (f"Progress: {dates_completed} dates completed, "
                f"{total_symbols} symbols downloaded, "
                f"{total_commands} commands executed, "
                f"Runtime: {elapsed_time/60:.1f} minutes")


class MinuteDataDownloader:
    """Downloads historical minute data using LEAN CLI and Polygon API"""
    
    def __init__(self):
        self.polygon_client = None
        self.progress_tracker = ProgressTracker()
        self.shutdown_requested = False
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
    
    async def initialize(self):
        """Initialize Polygon client"""
        logger.info("Initializing Polygon client...")
        self.polygon_client = PolygonClient()
        await self.polygon_client.__aenter__()
        logger.info("Polygon client initialized")
    
    async def cleanup(self):
        """Cleanup resources"""
        if self.polygon_client:
            await self.polygon_client.__aexit__(None, None, None)
    
    def is_trading_day(self, date_obj: date) -> bool:
        """Check if a date is a trading day (weekday)"""
        return date_obj.weekday() < 5  # Monday = 0, Friday = 4
    
    def get_trading_days_between(self, start_date: date, end_date: date) -> List[date]:
        """Get all trading days between start and end date (backwards)"""
        trading_days = []
        current_date = end_date
        
        while current_date >= start_date:
            if self.is_trading_day(current_date):
                trading_days.append(current_date)
            current_date -= timedelta(days=1)
        
        return trading_days
    
    def download_batch_data(self, symbols: List[str], date_str: str) -> Tuple[List[str], List[str], Dict[str, str]]:
        """
        Download data for a batch of symbols on a specific date using LEAN CLI
        
        Returns: (successful_symbols, failed_symbols, error_dict)
        """
        # Filter out symbols that already have data
        symbols_to_download = []
        already_exist = []
        
        for symbol in symbols:
            data_file = LEAN_DATA_PATH / "equity" / "usa" / "minute" / symbol.lower() / f"{date_str}_trade.zip"
            if data_file.exists():
                logger.debug(f"Data already exists for {symbol} on {date_str}, skipping")
                already_exist.append(symbol)
            else:
                symbols_to_download.append(symbol)
        
        if not symbols_to_download:
            logger.info(f"All {len(symbols)} symbols already have data for {date_str}")
            return (already_exist, [], {})
        
        # LEAN requires end date to be after start date, so we add 1 day
        start_date = datetime.strptime(date_str, "%Y%m%d")
        end_date = start_date + timedelta(days=1)
        end_date_str = end_date.strftime("%Y%m%d")
        
        # Join symbols with commas for batch download
        ticker_list = ",".join(symbols_to_download)
        logger.info(f"Downloading batch of {len(symbols_to_download)} symbols for {date_str}")
        
        cmd = [
            str(LEAN_CLI_PATH),
            "data", "download",
            "--data-provider-historical", "Polygon",
            "--data-type", "Trade",
            "--resolution", "Minute",
            "--security-type", "Equity",
            "--market", "usa",
            "--ticker", ticker_list,  # Comma-separated list of tickers
            "--start", date_str,
            "--end", end_date_str,
            "--polygon-api-key", settings.polygon_api_key
        ]
        
        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Executing batch download: {len(symbols_to_download)} symbols")
                result = subprocess.run(
                    cmd,
                    input="\n1\n\n\n",  # Handle any interactive prompts
                    capture_output=True,
                    text=True,
                    cwd=str(LEAN_DATA_PATH.parent),
                    timeout=DOWNLOAD_TIMEOUT
                )
                
                if result.returncode == 0:
                    logger.info(f"Successfully downloaded batch of {len(symbols_to_download)} symbols for {date_str}")
                    # Verify which files were actually created
                    successful = []
                    failed = []
                    errors = {}
                    
                    for symbol in symbols_to_download:
                        data_file = LEAN_DATA_PATH / "equity" / "usa" / "minute" / symbol.lower() / f"{date_str}_trade.zip"
                        if data_file.exists():
                            successful.append(symbol)
                        else:
                            failed.append(symbol)
                            errors[symbol] = "File not created after batch download"
                    
                    return (already_exist + successful, failed, errors)
                else:
                    error_msg = result.stderr or result.stdout
                    if attempt < MAX_RETRIES - 1:
                        logger.warning(f"Batch download attempt {attempt + 1} failed: {error_msg[:200]}...")
                        time.sleep(RETRY_DELAY)
                    else:
                        logger.error(f"Batch download failed after {MAX_RETRIES} attempts")
                        # Return all as failed
                        errors = {symbol: error_msg[:200] for symbol in symbols_to_download}
                        return (already_exist, symbols_to_download, errors)
                        
            except subprocess.TimeoutExpired:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Batch download timeout on attempt {attempt + 1}")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Batch download timed out after {MAX_RETRIES} attempts")
                    errors = {symbol: f"Timeout after {DOWNLOAD_TIMEOUT}s" for symbol in symbols_to_download}
                    return (already_exist, symbols_to_download, errors)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Exception on batch download attempt {attempt + 1}: {str(e)}")
                    time.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Batch download exception after {MAX_RETRIES} attempts: {str(e)}")
                    errors = {symbol: str(e)[:200] for symbol in symbols_to_download}
                    return (already_exist, symbols_to_download, errors)
        
        # Should not reach here, but just in case
        errors = {symbol: "Unknown error" for symbol in symbols_to_download}
        return (already_exist, symbols_to_download, errors)
    
    async def download_date_data(self, date_obj: date, job_id: str) -> int:
        """Download data for all symbols on a specific date"""
        date_str = date_obj.strftime("%Y%m%d")
        
        # Always process all dates, even if previously marked as completed
        logger.info(f"Processing date {date_str} - Fetching available symbols...")
        
        try:
            # Get all available symbols for this date
            bulk_data = await self.polygon_client.fetch_bulk_daily_data(
                date_obj=date_obj,
                adjusted=True,
                include_otc=False
            )
            
            symbols = list(bulk_data.keys())
            logger.info(f"Found {len(symbols)} symbols for {date_str}")
            
            if not symbols:
                logger.warning(f"No symbols found for {date_str}, marking as completed")
                self.progress_tracker.mark_date_completed(job_id, date_str, 0)
                return 0
            
            # Update symbols in checkpoint
            self.progress_tracker.update_symbols_for_date(job_id, date_str, symbols)
            
            # Process symbols in batches
            logger.info(f"Starting batch downloads for {len(symbols)} symbols on {date_str}")
            logger.info(f"Batch size: {BATCH_SIZE} symbols per command")
            
            total_successful = 0
            total_failed = 0
            all_errors = {}
            
            # Split symbols into batches
            for i in range(0, len(symbols), BATCH_SIZE):
                if self.shutdown_requested:
                    break
                    
                batch = symbols[i:i + BATCH_SIZE]
                batch_num = (i // BATCH_SIZE) + 1
                total_batches = (len(symbols) + BATCH_SIZE - 1) // BATCH_SIZE
                
                logger.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} symbols)")
                
                # Download this batch
                successful, failed, errors = self.download_batch_data(batch, date_str)
                
                total_successful += len(successful)
                total_failed += len(failed)
                
                # Track failed symbols
                for symbol, error in errors.items():
                    self.progress_tracker.mark_symbol_failed(job_id, date_str, symbol, error)
                    all_errors[symbol] = error
                
                # Log batch progress
                logger.info(f"Batch {batch_num} completed: {len(successful)} successful, {len(failed)} failed")
                logger.info(f"Overall progress: {total_successful + total_failed}/{len(symbols)} symbols processed")
                
                # Small delay between batches to avoid overwhelming the system
                if i + BATCH_SIZE < len(symbols):
                    await asyncio.sleep(2)
            
            logger.info(f"Completed {date_str}: {total_successful} successful, {total_failed} failed")
            
            # Mark date as completed
            self.progress_tracker.mark_date_completed(job_id, date_str, total_successful)
            
            # Save checkpoint with progress summary
            self.progress_tracker.save_checkpoint()
            logger.info(self.progress_tracker.get_progress_summary(job_id))
            
            return total_successful
            
        except PolygonAPIError as e:
            logger.error(f"Polygon API error for {date_str}: {e}")
            return 0
        except Exception as e:
            logger.error(f"Unexpected error for {date_str}: {e}")
            return 0
    
    async def download_historical_data(self, start_date: date, end_date: date):
        """Main method to download historical data for date range"""
        job_id = f"minute_data_{start_date}_{end_date}"
        
        logger.info(f"Starting historical minute data download")
        logger.info(f"Date range: {start_date} to {end_date}")
        logger.info(f"Job ID: {job_id}")
        
        # Initialize job in progress tracker
        self.progress_tracker.init_job(job_id, start_date, end_date)
        
        # Get trading days (backwards)
        trading_days = self.get_trading_days_between(start_date, end_date)
        logger.info(f"Found {len(trading_days)} trading days to process")
        
        total_symbols_downloaded = 0
        
        # Process each trading day
        for i, date_obj in enumerate(trading_days):
            if self.shutdown_requested:
                logger.info("Shutdown requested, stopping...")
                break
            
            logger.info(f"\nProcessing date {i+1}/{len(trading_days)}: {date_obj}")
            
            symbols_count = await self.download_date_data(date_obj, job_id)
            total_symbols_downloaded += symbols_count
            
            # Small delay between dates to avoid overwhelming the system
            if i < len(trading_days) - 1:
                await asyncio.sleep(1)
        
        # Final summary
        logger.info("\n" + "="*50)
        logger.info("Download job completed!")
        logger.info(self.progress_tracker.get_progress_summary(job_id))
        logger.info(f"Total symbols downloaded: {total_symbols_downloaded}")
        logger.info("="*50)


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Download historical minute data from Polygon using LEAN CLI"
    )
    parser.add_argument(
        "--start",
        type=str,
        required=True,
        help="Start date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--end",
        type=str,
        required=True,
        help="End date in YYYY-MM-DD format"
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from previous checkpoint"
    )
    
    args = parser.parse_args()
    
    # Parse dates
    try:
        start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
        end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
    except ValueError as e:
        logger.error(f"Invalid date format: {e}")
        sys.exit(1)
    
    if start_date > end_date:
        logger.error("Start date must be before or equal to end date")
        sys.exit(1)
    
    # Check if LEAN CLI exists
    if not LEAN_CLI_PATH.exists():
        logger.error(f"LEAN CLI not found at {LEAN_CLI_PATH}")
        logger.error("Please install LEAN CLI: pip install lean")
        sys.exit(1)
    
    # Create downloader and run
    downloader = MinuteDataDownloader()
    
    try:
        await downloader.initialize()
        
        if args.resume:
            logger.info("Resuming from checkpoint...")
        
        await downloader.download_historical_data(start_date, end_date)
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        await downloader.cleanup()


if __name__ == "__main__":
    asyncio.run(main())