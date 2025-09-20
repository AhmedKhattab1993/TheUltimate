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
from asyncio import subprocess as async_subprocess
import argparse
import json
import logging
import os
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import signal
import statistics
import time

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
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
DOWNLOAD_TIMEOUT = 1800  # 30 minutes per batch - increased for batch downloads
DEFAULT_BATCH_SIZE = int(os.getenv("MINUTE_BATCH_SIZE", "80"))
DEFAULT_MAX_PARALLEL_BATCHES = int(os.getenv("MINUTE_MAX_PARALLEL", "1"))
DEFAULT_BATCH_COOLDOWN = float(os.getenv("MINUTE_BATCH_COOLDOWN", "0.1"))
DEFAULT_MAX_SYMBOLS_PER_DATE = int(os.getenv("MINUTE_MAX_SYMBOLS_PER_DATE", "0"))
DEFAULT_MAX_CHECKPOINT_JOBS = int(os.getenv("MINUTE_MAX_CHECKPOINT_JOBS", "8"))

class ProgressTracker:
    """Tracks download progress and handles checkpointing"""
    
    def __init__(self, checkpoint_file: Path = CHECKPOINT_FILE, max_jobs_to_keep: int = 10):
        self.checkpoint_file = checkpoint_file
        self.max_jobs_to_keep = max_jobs_to_keep
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
                backup_name = f"{self.checkpoint_file.name}.corrupt.{int(time.time())}"
                backup_path = self.checkpoint_file.with_name(backup_name)
                try:
                    self.checkpoint_file.rename(backup_path)
                    logger.warning(
                        f"Corrupted checkpoint moved to {backup_path}. Starting with a fresh state."
                    )
                except Exception as rename_error:
                    logger.warning(
                        f"Failed to move corrupted checkpoint: {rename_error}. Continuing without checkpoint."
                    )
                return {}
        return {}
    
    def _compact_jobs(self):
        """Keep only the most recent jobs to prevent file bloat"""
        if self.max_jobs_to_keep <= 0:
            return

        job_items = sorted(
            self.checkpoint_data.items(),
            key=lambda item: item[1].get("last_updated", item[1].get("created_at", "")),
            reverse=True
        )
        if len(job_items) <= self.max_jobs_to_keep:
            return

        # Keep the newest N jobs
        keep = dict(job_items[:self.max_jobs_to_keep])
        removed = set(job_id for job_id, _ in job_items[self.max_jobs_to_keep:])
        if removed:
            logger.info(
                f"Pruning {len(removed)} old jobs from checkpoint: {sorted(list(removed))[:5]}"
            )
        self.checkpoint_data = keep

    def save_checkpoint(self):
        """Save current checkpoint to file"""
        try:
            self._compact_jobs()
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


class MetricsRecorder:
    """Capture runtime metrics for post-run analysis"""

    def __init__(self) -> None:
        self._metrics: Dict[str, List[float]] = defaultdict(list)

    def track(self, label: str, duration: float) -> None:
        self._metrics[label].append(duration)

    def summary(self) -> Dict[str, Dict[str, float]]:
        summary: Dict[str, Dict[str, float]] = {}
        for label, samples in self._metrics.items():
            if not samples:
                continue
            summary[label] = {
                "count": len(samples),
                "total": sum(samples),
                "mean": statistics.fmean(samples),
                "p95": sorted(samples)[int(len(samples) * 0.95) - 1] if len(samples) > 1 else samples[0]
            }
        return summary

    def log_summary(self) -> None:
        for label, stats_dict in self.summary().items():
            logger.info(
                f"[METRICS] {label}: runs={stats_dict['count']}, total={stats_dict['total']:.2f}s, "
                f"mean={stats_dict['mean']:.2f}s, p95={stats_dict['p95']:.2f}s"
            )


class TimedStep:
    """Context manager to time critical sections and record duration"""

    def __init__(self, recorder: MetricsRecorder, label: str, log: bool = True) -> None:
        self.recorder = recorder
        self.label = label
        self.log = log
        self._start: Optional[float] = None
        self.duration: Optional[float] = None

    def __enter__(self):
        self._start = time.perf_counter()
        self.duration = None
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._start is None:
            return
        duration = time.perf_counter() - self._start
        self.duration = duration
        self.recorder.track(self.label, duration)
        if self.log:
            logger.info(f"[TIMER] {self.label} completed in {duration:.2f}s")


class MinuteDataDownloader:
    """Downloads historical minute data using LEAN CLI and Polygon API"""
    
    def __init__(
        self,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_parallel_batches: int = DEFAULT_MAX_PARALLEL_BATCHES,
        batch_cooldown: float = DEFAULT_BATCH_COOLDOWN,
        max_symbols_per_date: Optional[int] = None,
        dry_run: bool = False,
        max_checkpoint_jobs: int = DEFAULT_MAX_CHECKPOINT_JOBS
    ):
        self.polygon_client = None
        self.progress_tracker = ProgressTracker(max_jobs_to_keep=max_checkpoint_jobs)
        self.shutdown_requested = False
        self.metrics = MetricsRecorder()
        self.batch_size = max(1, batch_size)
        self.max_parallel_batches = max(1, max_parallel_batches)
        self.batch_cooldown = max(0.0, batch_cooldown)
        self._batch_semaphore = asyncio.Semaphore(self.max_parallel_batches)
        self.max_symbols_per_date = (
            max_symbols_per_date if max_symbols_per_date and max_symbols_per_date > 0 else None
        )
        self.dry_run = dry_run
        
        # Register signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
    
    async def initialize(self):
        """Initialize Polygon client"""
        if self.dry_run:
            logger.info("Dry-run mode enabled: skipping Polygon client initialization")
            return

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

    def _mock_symbols_for_date(self, date_str: str) -> List[str]:
        """Generate a synthetic symbol universe for dry-run benchmarking"""
        baseline = self.batch_size * max(2, self.max_parallel_batches)
        target = self.max_symbols_per_date or baseline
        target = max(self.batch_size, target)
        target = min(target, 2000)  # Keep mocks bounded to avoid runaway lists
        return [f"SIM_{date_str}_{i:04d}" for i in range(target)]
    
    async def download_batch_data(
        self,
        job_id: str,
        symbols: List[str],
        date_str: str
    ) -> Tuple[List[str], List[str], Dict[str, str], Optional[float]]:
        """
        Download data for a batch of symbols on a specific date using LEAN CLI.

        Returns: (successful_symbols, failed_symbols, error_dict, duration_seconds)
        """
        symbols_to_download: List[str] = []
        already_exist: List[str] = []

        for symbol in symbols:
            data_file = LEAN_DATA_PATH / "equity" / "usa" / "minute" / symbol.lower() / f"{date_str}_trade.zip"
            if data_file.exists():
                logger.debug(f"Data already exists for {symbol} on {date_str}, skipping")
                already_exist.append(symbol)
            else:
                symbols_to_download.append(symbol)

        if not symbols_to_download:
            logger.info(f"All {len(symbols)} symbols already have data for {date_str}")
            return (already_exist, [], {}, 0.0)

        if self.dry_run:
            with TimedStep(self.metrics, f"lean.batch[dry:{len(symbols_to_download)}]", log=False) as timer:
                await asyncio.sleep(min(0.05, self.batch_cooldown or 0.05))
            logger.info(
                f"Dry-run: skipping LEAN download for {len(symbols_to_download)} symbols on {date_str}"
            )
            self.progress_tracker.increment_download_count(job_id)
            duration = timer.duration or 0.0
            return (already_exist + symbols_to_download, [], {}, duration)

        start_date = datetime.strptime(date_str, "%Y%m%d")
        end_date = start_date + timedelta(days=1)
        end_date_str = end_date.strftime("%Y%m%d")

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
            "--ticker", ticker_list,
            "--start", date_str,
            "--end", end_date_str,
            "--polygon-api-key", settings.polygon_api_key
        ]

        input_payload = "\n1\n\n\n".encode()
        batch_duration: Optional[float] = None

        for attempt in range(MAX_RETRIES):
            try:
                logger.debug(f"Executing batch download: {len(symbols_to_download)} symbols")
                with TimedStep(self.metrics, f"lean.batch[{len(symbols_to_download)}]") as timer:
                    process = await asyncio.create_subprocess_exec(
                        *cmd,
                        stdin=async_subprocess.PIPE,
                        stdout=async_subprocess.PIPE,
                        stderr=async_subprocess.PIPE,
                        cwd=str(LEAN_DATA_PATH.parent)
                    )
                    try:
                        stdout, stderr = await asyncio.wait_for(
                            process.communicate(input_payload),
                            timeout=DOWNLOAD_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        process.kill()
                        await process.communicate()
                        raise

                batch_duration = timer.duration
                self.progress_tracker.increment_download_count(job_id)

                stdout_text = stdout.decode() if isinstance(stdout, bytes) else stdout
                stderr_text = stderr.decode() if isinstance(stderr, bytes) else stderr

                if process.returncode == 0:
                    logger.info(
                        f"Successfully downloaded batch of {len(symbols_to_download)} symbols for {date_str}"
                    )
                    successful: List[str] = []
                    failed: List[str] = []
                    errors: Dict[str, str] = {}

                    for symbol in symbols_to_download:
                        data_file = LEAN_DATA_PATH / "equity" / "usa" / "minute" / symbol.lower() / f"{date_str}_trade.zip"
                        if data_file.exists():
                            successful.append(symbol)
                        else:
                            failed.append(symbol)
                            errors[symbol] = "File not created after batch download"

                    return (already_exist + successful, failed, errors, batch_duration)

                error_output = stderr_text or stdout_text or ""
                error_msg = error_output or "Unknown error"
                if attempt < MAX_RETRIES - 1:
                    logger.warning(
                        f"Batch download attempt {attempt + 1} failed: {error_msg[:200]}..."
                    )
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Batch download failed after {MAX_RETRIES} attempts")
                    errors = {symbol: error_msg[:200] for symbol in symbols_to_download}
                    return (already_exist, symbols_to_download, errors, batch_duration)

            except asyncio.TimeoutError:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Batch download timeout on attempt {attempt + 1}")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Batch download timed out after {MAX_RETRIES} attempts")
                    errors = {symbol: f"Timeout after {DOWNLOAD_TIMEOUT}s" for symbol in symbols_to_download}
                    return (already_exist, symbols_to_download, errors, batch_duration)
            except Exception as e:
                if attempt < MAX_RETRIES - 1:
                    logger.warning(f"Exception on batch download attempt {attempt + 1}: {str(e)}")
                    await asyncio.sleep(RETRY_DELAY)
                else:
                    logger.error(f"Batch download exception after {MAX_RETRIES} attempts: {str(e)}")
                    errors = {symbol: str(e)[:200] for symbol in symbols_to_download}
                    return (already_exist, symbols_to_download, errors, batch_duration)

        errors = {symbol: "Unknown error" for symbol in symbols_to_download}
        return (already_exist, symbols_to_download, errors, batch_duration)

    async def _process_batch(
        self,
        job_id: str,
        date_str: str,
        batch: List[str],
        batch_index: int,
        total_batches: int
    ) -> Optional[Tuple[int, List[str], List[str], Dict[str, str], Optional[float]]]:
        """Execute a single batch with concurrency control"""
        if self.shutdown_requested:
            logger.info(f"Shutdown requested - skipping batch {batch_index + 1}/{total_batches}")
            errors = {symbol: "Shutdown requested" for symbol in batch}
            return (batch_index, [], batch, errors, None)

        if self.batch_cooldown > 0 and batch_index > 0:
            await asyncio.sleep(self.batch_cooldown)

        async with self._batch_semaphore:
            logger.info(
                f"Processing batch {batch_index + 1}/{total_batches} ({len(batch)} symbols)"
            )
            with TimedStep(self.metrics, f"batch.lifecycle[{len(batch)}]") as lifecycle_timer:
                successful, failed, errors, duration = await self.download_batch_data(
                    job_id=job_id,
                    symbols=batch,
                    date_str=date_str
                )

            batch_duration = duration or lifecycle_timer.duration

        if self.batch_cooldown > 0:
            await asyncio.sleep(self.batch_cooldown)

        return (batch_index, successful, failed, errors, batch_duration)

    async def download_date_data(self, date_obj: date, job_id: str) -> int:
        """Download data for all symbols on a specific date"""
        date_str = date_obj.strftime("%Y%m%d")
        
        # Always process all dates, even if previously marked as completed
        logger.info(f"Processing date {date_str} - Fetching available symbols...")
        
        try:
            if self.dry_run:
                symbols = self._mock_symbols_for_date(date_str)
                logger.info(
                    f"Dry-run: generated {len(symbols)} synthetic symbols for {date_str}"
                )
            else:
                # Get all available symbols for this date
                with TimedStep(self.metrics, "polygon.bulk_fetch"):
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

            if self.max_symbols_per_date and len(symbols) > self.max_symbols_per_date:
                original_len = len(symbols)
                symbols = symbols[:self.max_symbols_per_date]
                logger.info(
                    f"Limiting symbols for {date_str} from {original_len} to {len(symbols)} "
                    f"(max per date configured)"
                )

            # Update symbols in checkpoint
            self.progress_tracker.update_symbols_for_date(job_id, date_str, symbols)
            
            # Process symbols in batches
            logger.info(f"Starting batch downloads for {len(symbols)} symbols on {date_str}")
            logger.info(
                f"Batch size: {self.batch_size} symbols, max parallel: {self.max_parallel_batches}, "
                f"cooldown: {self.batch_cooldown:.2f}s"
            )

            total_successful = 0
            total_failed = 0
            all_errors = {}

            batches: List[List[str]] = [
                symbols[i:i + self.batch_size]
                for i in range(0, len(symbols), self.batch_size)
            ]
            total_batches = len(batches)

            tasks = [
                asyncio.create_task(
                    self._process_batch(
                        job_id=job_id,
                        date_str=date_str,
                        batch=batch,
                        batch_index=index,
                        total_batches=total_batches
                    )
                )
                for index, batch in enumerate(batches)
            ]

            for task in asyncio.as_completed(tasks):
                batch_result = await task
                if batch_result is None:
                    continue

                batch_index, successful, failed, errors, duration = batch_result

                total_successful += len(successful)
                total_failed += len(failed)

                for symbol, error in errors.items():
                    self.progress_tracker.mark_symbol_failed(job_id, date_str, symbol, error)
                    all_errors[symbol] = error

                throughput = 0.0
                if duration and len(successful) > 0:
                    throughput = len(successful) / duration
                logger.info(
                    f"Batch {batch_index + 1}/{total_batches} completed: {len(successful)} successful, "
                    f"{len(failed)} failed, throughput={throughput:.1f} symbols/s"
                )
                logger.info(
                    f"Overall progress: {total_successful + total_failed}/{len(symbols)} symbols processed"
                )
            
            logger.info(f"Completed {date_str}: {total_successful} successful, {total_failed} failed")
            if all_errors:
                sample = list(all_errors.items())[:5]
                logger.warning(
                    f"Failures for {date_str}: {len(all_errors)} symbols (sample: {sample})"
                )
            
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
            
            with TimedStep(self.metrics, "date.total") as date_timer:
                symbols_count = await self.download_date_data(date_obj, job_id)
            total_symbols_downloaded += symbols_count

            if date_timer.duration:
                logger.info(
                    f"Date {date_obj} completed in {date_timer.duration:.2f}s "
                    f"({symbols_count} symbols, {symbols_count/date_timer.duration if date_timer.duration else 0:.1f} symbols/s)"
                )
            
            # Small delay between dates to avoid overwhelming the system
            if i < len(trading_days) - 1:
                await asyncio.sleep(1)
        
        # Final summary
        logger.info("\n" + "="*50)
        logger.info("Download job completed!")
        logger.info(self.progress_tracker.get_progress_summary(job_id))
        logger.info(f"Total symbols downloaded: {total_symbols_downloaded}")
        logger.info("Aggregated performance metrics:")
        self.metrics.log_summary()
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
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help="Number of symbols per LEAN download command (default from MINUTE_BATCH_SIZE env or 75)"
    )
    parser.add_argument(
        "--max-parallel-batches",
        type=int,
        default=DEFAULT_MAX_PARALLEL_BATCHES,
        help="Maximum concurrent LEAN download commands (default from MINUTE_MAX_PARALLEL env or 3)"
    )
    parser.add_argument(
        "--batch-cooldown",
        type=float,
        default=DEFAULT_BATCH_COOLDOWN,
        help="Delay in seconds between batch launches (default from MINUTE_BATCH_COOLDOWN env or 0.25)"
    )
    parser.add_argument(
        "--max-symbols-per-date",
        type=int,
        default=DEFAULT_MAX_SYMBOLS_PER_DATE,
        help="Cap the number of symbols processed per date (0 means no cap)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip external API/LEAN calls and simulate downloads for benchmarking"
    )
    parser.add_argument(
        "--max-checkpoint-jobs",
        type=int,
        default=DEFAULT_MAX_CHECKPOINT_JOBS,
        help="Maximum number of recent jobs to retain in the checkpoint file"
    )
    parser.add_argument(
        "--reset-checkpoint",
        action="store_true",
        help="Delete existing checkpoint before starting"
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
    
    # Reset checkpoint if requested
    if args.reset_checkpoint and CHECKPOINT_FILE.exists():
        backup_path = CHECKPOINT_FILE.with_name(
            f"{CHECKPOINT_FILE.name}.backup.{int(time.time())}"
        )
        CHECKPOINT_FILE.rename(backup_path)
        logger.info(
            f"Checkpoint reset requested. Existing file moved to {backup_path}"
        )

    # Check if LEAN CLI exists
    if not args.dry_run and not LEAN_CLI_PATH.exists():
        logger.error(f"LEAN CLI not found at {LEAN_CLI_PATH}")
        logger.error("Please install LEAN CLI: pip install lean")
        sys.exit(1)

    # Create downloader and run
    downloader = MinuteDataDownloader(
        batch_size=args.batch_size,
        max_parallel_batches=args.max_parallel_batches,
        batch_cooldown=args.batch_cooldown,
        max_symbols_per_date=args.max_symbols_per_date,
        dry_run=args.dry_run,
        max_checkpoint_jobs=args.max_checkpoint_jobs
    )
    
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
