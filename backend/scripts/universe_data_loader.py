#!/usr/bin/env python
"""
Enhanced Data Loader for US Equities Universe

This script provides production-ready functionality to:
1. Discover the full universe of US common stocks and ETFs from Polygon.io
2. Load daily bars efficiently using bulk endpoints
3. Load minute bars with intelligent chunking and priority-based loading
4. Track progress with resume capability
5. Handle failures gracefully with retry logic
6. Support both initial historical load and daily updates for both daily and minute data
"""

import asyncio
import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Set, Any, Tuple
import signal
import time
import pytz
from collections import defaultdict
import heapq

# Add parent directory to path to import app modules
sys.path.append(str(Path(__file__).parent.parent))

from app.services.polygon_client import PolygonClient, PolygonAPIError
from app.services.ticker_discovery import TickerDiscoveryService
from app.services.data_collector import DataCollector
from app.services.database import db_pool, DatabaseTransaction
from app.config import settings
from app.models.stock import StockBar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Eastern timezone for market data
ET = pytz.timezone('US/Eastern')

# Progress checkpoint file
CHECKPOINT_FILE = Path(__file__).parent / "universe_loader_checkpoint.json"

# Constants for minute data loading
MAX_BARS_PER_REQUEST = 50000  # Polygon API limit
DEFAULT_CHUNK_DAYS = 30  # Default chunk size for minute data
MIN_CHUNK_DAYS = 7  # Minimum chunk size
MAX_CONCURRENT_SYMBOLS = 200  # Maximum symbols to process concurrently


class ProgressTracker:
    """Tracks and persists data loading progress"""
    
    def __init__(self, checkpoint_file: Path = CHECKPOINT_FILE):
        self.checkpoint_file = checkpoint_file
        self.checkpoint_data = self._load_checkpoint()
        
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
            
    def get_resume_state(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get resume state for a specific job"""
        return self.checkpoint_data.get(job_id)
        
    def update_progress(self, job_id: str, state: Dict[str, Any]):
        """Update progress for a job"""
        self.checkpoint_data[job_id] = {
            **state,
            "last_updated": datetime.now().isoformat()
        }
        self.save_checkpoint()
        
    def mark_complete(self, job_id: str):
        """Mark a job as complete"""
        if job_id in self.checkpoint_data:
            self.checkpoint_data[job_id]["status"] = "completed"
            self.checkpoint_data[job_id]["completed_at"] = datetime.now().isoformat()
            self.save_checkpoint()
            
    def clear_job(self, job_id: str):
        """Clear a job from checkpoint"""
        if job_id in self.checkpoint_data:
            del self.checkpoint_data[job_id]
            self.save_checkpoint()


class UniverseDataLoader:
    """Main data loader for US stocks universe"""
    
    def __init__(self):
        self.polygon_client = None
        self.ticker_discovery = None
        self.data_collector = None
        self.progress_tracker = ProgressTracker()
        self.shutdown_requested = False
        self.minute_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYMBOLS)
        
        # Register signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.shutdown_requested = True
        
    async def initialize(self):
        """Initialize services"""
        logger.info("Initializing services...")
        
        # Initialize database pool
        await db_pool.initialize()
        
        # Initialize Polygon client
        self.polygon_client = PolygonClient()
        await self.polygon_client.__aenter__()
        
        # Initialize services
        self.ticker_discovery = TickerDiscoveryService(self.polygon_client)
        self.data_collector = DataCollector(self.polygon_client)
        
        logger.info("Services initialized successfully")
        
    async def cleanup(self):
        """Cleanup services"""
        logger.info("Cleaning up services...")
        
        if self.polygon_client:
            await self.polygon_client.__aexit__(None, None, None)
            
        await db_pool.close()
        
        logger.info("Cleanup complete")
        
    async def discover_universe(self, force_refresh: bool = False) -> List[str]:
        """
        Discover the full universe of US common stocks
        
        Args:
            force_refresh: Force refresh even if we have cached universe
            
        Returns:
            List of ticker symbols
        """
        # Check if we have a recent universe cached
        cache_key = "universe_discovery"
        cached_state = self.progress_tracker.get_resume_state(cache_key)
        
        if not force_refresh and cached_state and cached_state.get("symbols"):
            # Check if cache is less than 24 hours old
            last_updated = datetime.fromisoformat(cached_state["last_updated"])
            if datetime.now() - last_updated < timedelta(hours=24):
                logger.info(f"Using cached universe of {len(cached_state['symbols'])} symbols")
                return cached_state["symbols"]
                
        # Discover fresh universe
        logger.info("Discovering US equities universe (CS + ETF)...")
        start_time = time.time()
        
        try:
            # Fetch both common stocks and ETFs
            symbols = await self.ticker_discovery.fetch_us_equities(include_types=['CS', 'ETF'])
            
            # Cache the universe
            self.progress_tracker.update_progress(cache_key, {
                "symbols": symbols,
                "count": len(symbols),
                "discovered_at": datetime.now().isoformat()
            })
            
            elapsed = time.time() - start_time
            logger.info(f"Discovered {len(symbols)} US equities (CS + ETF) in {elapsed:.2f} seconds")
            
            return symbols
            
        except Exception as e:
            logger.error(f"Error discovering universe: {e}")
            raise
            
    async def load_historical_data_by_date(
        self,
        start_date: date,
        end_date: date,
        symbols: Optional[List[str]] = None,
        batch_size: int = 1000
    ) -> Dict[str, Any]:
        """
        Load historical data by date using bulk endpoint
        
        This is the most efficient method as it fetches all symbols for each date
        in a single API call.
        
        Args:
            start_date: Start date for historical data
            end_date: End date for historical data
            symbols: Optional list of symbols to filter (None = all)
            batch_size: Batch size for database inserts
            
        Returns:
            Load statistics
        """
        job_id = f"historical_load_{start_date}_{end_date}"
        
        # Check for existing progress
        resume_state = self.progress_tracker.get_resume_state(job_id)
        if resume_state and resume_state.get("status") != "completed":
            logger.info(f"Resuming historical load from checkpoint: {resume_state}")
            processed_dates = set(resume_state.get("processed_dates", []))
        else:
            processed_dates = set()
            
        # Initialize statistics
        stats = {
            "total_dates": 0,
            "processed_dates": 0,
            "total_bars": 0,
            "total_symbols": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat(),
            "status": "in_progress"
        }
        
        # Generate list of trading days
        current_date = start_date
        trading_days = []
        
        while current_date <= end_date:
            # Skip weekends
            if current_date.weekday() < 5:  # Monday = 0, Friday = 4
                trading_days.append(current_date)
            current_date += timedelta(days=1)
            
        stats["total_dates"] = len(trading_days)
        logger.info(f"Loading data for {len(trading_days)} trading days from {start_date} to {end_date}")
        
        # Process each trading day
        for trading_day in trading_days:
            if self.shutdown_requested:
                logger.info("Shutdown requested, saving progress...")
                break
                
            # Skip if already processed
            if str(trading_day) in processed_dates:
                logger.debug(f"Skipping already processed date: {trading_day}")
                stats["processed_dates"] += 1
                continue
                
            try:
                logger.info(f"Loading data for {trading_day} ({stats['processed_dates'] + 1}/{stats['total_dates']})")
                
                # Use bulk endpoint to get all stocks for this date
                day_start = time.time()
                bars_buffer = []
                symbols_seen = set()
                
                # Define streaming callback to process data as it arrives
                async def process_stock_data(symbol: str, stock_data):
                    nonlocal bars_buffer, symbols_seen
                    
                    # Filter by symbols if specified
                    if symbols and symbol not in symbols:
                        return
                        
                    symbols_seen.add(symbol)
                    bars_buffer.extend(stock_data.bars)
                    
                    # Store in batches for efficiency
                    if len(bars_buffer) >= batch_size:
                        await self._store_bars_batch(bars_buffer)
                        stats["total_bars"] += len(bars_buffer)
                        bars_buffer = []
                
                # Fetch data with streaming
                await self.polygon_client.fetch_bulk_daily_data(
                    date_obj=trading_day,
                    adjusted=True,
                    include_otc=False,
                    streaming_callback=process_stock_data
                )
                
                # Store any remaining bars
                if bars_buffer:
                    await self._store_bars_batch(bars_buffer)
                    stats["total_bars"] += len(bars_buffer)
                    
                # Update coverage tracking
                if symbols_seen:
                    await self._update_bulk_coverage(symbols_seen, trading_day)
                    
                day_elapsed = time.time() - day_start
                logger.info(f"Processed {len(symbols_seen)} symbols for {trading_day} in {day_elapsed:.2f} seconds")
                
                # Update progress
                stats["processed_dates"] += 1
                stats["total_symbols"] = len(symbols_seen)
                processed_dates.add(str(trading_day))
                
                # Save checkpoint
                self.progress_tracker.update_progress(job_id, {
                    **stats,
                    "processed_dates": list(processed_dates),
                    "last_processed_date": str(trading_day)
                })
                
            except Exception as e:
                logger.error(f"Error processing {trading_day}: {e}")
                stats["errors"] += 1
                
                # Save error to database
                await self._log_bulk_error(trading_day, str(e))
                
                # Continue with next date
                continue
                
        # Mark job as complete
        if stats["processed_dates"] == stats["total_dates"]:
            stats["status"] = "completed"
            stats["completed_at"] = datetime.now().isoformat()
            self.progress_tracker.mark_complete(job_id)
        else:
            stats["status"] = "interrupted" if self.shutdown_requested else "partial"
            
        stats["end_time"] = datetime.now().isoformat()
        
        return stats
        
    async def load_daily_update(self, target_date: Optional[date] = None) -> Dict[str, Any]:
        """
        Load daily update for the most recent trading day
        
        Args:
            target_date: Specific date to update (None = most recent trading day)
            
        Returns:
            Update statistics
        """
        if target_date is None:
            # Determine most recent trading day
            target_date = self._get_last_trading_day()
            
        logger.info(f"Running daily update for {target_date}")
        
        # Use the same logic as historical load but for single day
        stats = await self.load_historical_data_by_date(
            start_date=target_date,
            end_date=target_date
        )
        
        # Update symbols table with latest ticker info
        logger.info("Updating symbols table...")
        symbols_updated = await self.data_collector.update_symbols_table()
        stats["symbols_updated"] = symbols_updated
        
        return stats
        
    async def _store_bars_batch(self, bars: List[Any]):
        """Store a batch of bars efficiently"""
        if not bars:
            return
            
        try:
            async with DatabaseTransaction() as conn:
                await self.data_collector._store_daily_bars(bars, conn)
        except Exception as e:
            logger.error(f"Error storing batch of {len(bars)} bars: {e}")
            raise
            
    async def _update_bulk_coverage(self, symbols: Set[str], date_obj: date):
        """Update coverage tracking for bulk load"""
        try:
            # Batch update coverage for all symbols
            records = [
                (symbol, 'daily', date_obj, date_obj, datetime.now(pytz.UTC))
                for symbol in symbols
            ]
            
            async with DatabaseTransaction() as conn:
                await conn.executemany('''
                    INSERT INTO data_coverage (symbol, data_type, start_date, end_date, last_updated)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (symbol, data_type)
                    DO UPDATE SET
                        start_date = LEAST(data_coverage.start_date, EXCLUDED.start_date),
                        end_date = GREATEST(data_coverage.end_date, EXCLUDED.end_date),
                        last_updated = EXCLUDED.last_updated
                ''', records)
                
        except Exception as e:
            logger.error(f"Error updating coverage: {e}")
            
    async def _log_bulk_error(self, date_obj: date, error_message: str):
        """Log error for bulk load"""
        try:
            await db_pool.execute('''
                INSERT INTO data_fetch_errors (symbol, error_type, error_message, start_date, end_date)
                VALUES ($1, $2, $3, $4, $5)
            ''', 'BULK_LOAD', 'bulk_load_error', error_message, date_obj, date_obj)
        except Exception as e:
            logger.error(f"Failed to log error: {e}")
            
    def _get_last_trading_day(self) -> date:
        """Get the most recent trading day"""
        today = date.today()
        
        # If it's a weekend, go back to Friday
        if today.weekday() == 5:  # Saturday
            return today - timedelta(days=1)
        elif today.weekday() == 6:  # Sunday
            return today - timedelta(days=2)
            
        # If it's after market close (4 PM ET), use today
        # Otherwise use previous trading day
        now_et = datetime.now(ET)
        market_close = now_et.replace(hour=16, minute=0, second=0)
        
        if now_et >= market_close:
            return today
        else:
            # Use previous trading day
            if today.weekday() == 0:  # Monday
                return today - timedelta(days=3)  # Friday
            else:
                return today - timedelta(days=1)
                
    async def verify_data_integrity(self, sample_size: int = 100) -> Dict[str, Any]:
        """
        Verify data integrity by checking a sample of loaded data
        
        Args:
            sample_size: Number of random symbols to check
            
        Returns:
            Verification results
        """
        logger.info(f"Verifying data integrity with sample size {sample_size}")
        
        results = {
            "symbols_checked": 0,
            "missing_data": [],
            "data_gaps": [],
            "invalid_ohlc": [],
            "verification_time": datetime.now().isoformat()
        }
        
        try:
            # Get random sample of symbols
            symbols = await db_pool.fetch('''
                SELECT DISTINCT symbol 
                FROM daily_bars 
                ORDER BY RANDOM() 
                LIMIT $1
            ''', sample_size)
            
            for record in symbols:
                symbol = record['symbol']
                results["symbols_checked"] += 1
                
                # Check for data gaps
                gaps = await db_pool.fetch('''
                    WITH trading_days AS (
                        SELECT generate_series(
                            (SELECT MIN(time)::date FROM daily_bars WHERE symbol = $1),
                            (SELECT MAX(time)::date FROM daily_bars WHERE symbol = $1),
                            '1 day'::interval
                        )::date AS date
                    ),
                    existing_days AS (
                        SELECT DISTINCT time::date AS date
                        FROM daily_bars
                        WHERE symbol = $1
                    )
                    SELECT td.date
                    FROM trading_days td
                    LEFT JOIN existing_days ed ON td.date = ed.date
                    WHERE ed.date IS NULL
                    AND EXTRACT(DOW FROM td.date) NOT IN (0, 6)
                    ORDER BY td.date
                ''', symbol)
                
                if gaps:
                    results["data_gaps"].append({
                        "symbol": symbol,
                        "missing_dates": [str(g['date']) for g in gaps]
                    })
                    
                # Check for invalid OHLC relationships
                invalid = await db_pool.fetch('''
                    SELECT time, open, high, low, close
                    FROM daily_bars
                    WHERE symbol = $1
                    AND (
                        high < low OR
                        high < open OR
                        high < close OR
                        low > open OR
                        low > close
                    )
                    ORDER BY time
                ''', symbol)
                
                if invalid:
                    results["invalid_ohlc"].append({
                        "symbol": symbol,
                        "count": len(invalid),
                        "examples": [dict(r) for r in invalid[:5]]
                    })
                    
            logger.info(f"Data integrity check complete: {results['symbols_checked']} symbols checked")
            
        except Exception as e:
            logger.error(f"Error during data integrity check: {e}")
            results["error"] = str(e)
            
        return results
        
    async def _get_stock_volumes(self, symbols: List[str], lookback_days: int = 30) -> Dict[str, float]:
        """
        Get average daily volumes for stocks to prioritize high-volume stocks
        
        Args:
            symbols: List of symbols to check
            lookback_days: Number of days to calculate average volume
            
        Returns:
            Dictionary of symbol -> average volume
        """
        volumes = {}
        end_date = date.today()
        start_date = end_date - timedelta(days=lookback_days)
        
        try:
            # Query database for recent volume data
            records = await db_pool.fetch('''
                SELECT symbol, AVG(volume) as avg_volume
                FROM daily_bars
                WHERE symbol = ANY($1::text[])
                AND time >= $2 AND time <= $3
                GROUP BY symbol
            ''', symbols, start_date, end_date)
            
            for record in records:
                volumes[record['symbol']] = float(record['avg_volume'] or 0)
                
            # For symbols without data, assign 0 volume
            for symbol in symbols:
                if symbol not in volumes:
                    volumes[symbol] = 0
                    
        except Exception as e:
            logger.error(f"Error fetching volume data: {e}")
            # Return empty volumes on error
            return {symbol: 0 for symbol in symbols}
            
        return volumes
        
    def _create_priority_queue(self, symbols: List[str], volumes: Dict[str, float]) -> List[Tuple[float, str]]:
        """
        Create a priority queue of symbols based on volume (highest volume first)
        
        Args:
            symbols: List of symbols
            volumes: Dictionary of symbol -> volume
            
        Returns:
            Priority queue as list of (negative_volume, symbol) tuples
        """
        # Use negative volume for max heap behavior
        priority_queue = []
        for symbol in symbols:
            volume = volumes.get(symbol, 0)
            heapq.heappush(priority_queue, (-volume, symbol))
            
        return priority_queue
        
    async def _fetch_minute_bars(
        self, 
        symbol: str, 
        start_date: date, 
        end_date: date,
        max_attempts: int = 3
    ) -> Optional[List[StockBar]]:
        """
        Fetch minute bars for a single symbol with automatic chunking
        
        Args:
            symbol: Stock symbol
            start_date: Start date
            end_date: End date
            max_attempts: Maximum retry attempts
            
        Returns:
            List of StockBar objects or None on failure
        """
        all_bars = []
        current_start = start_date
        
        while current_start <= end_date:
            # Calculate chunk end date
            chunk_end = min(
                current_start + timedelta(days=DEFAULT_CHUNK_DAYS - 1),
                end_date
            )
            
            # Try to fetch this chunk
            for attempt in range(max_attempts):
                try:
                    # Build API endpoint for minute aggregates
                    endpoint = f"/v2/aggs/ticker/{symbol}/range/1/minute/{self._format_date(current_start)}/{self._format_date(chunk_end)}"
                    
                    params = {
                        "adjusted": "true",
                        "sort": "asc",
                        "limit": str(MAX_BARS_PER_REQUEST)
                    }
                    
                    response = await self.polygon_client._make_request(endpoint, params)
                    
                    if response.get("status") == "OK" and "results" in response:
                        # Parse bars
                        for bar_data in response["results"]:
                            # Convert timestamp to datetime
                            timestamp = datetime.fromtimestamp(bar_data["t"] / 1000, tz=pytz.UTC)
                            
                            bar = StockBar(
                                symbol=symbol,
                                date=timestamp.date(),
                                timestamp=timestamp,
                                open=bar_data["o"],
                                high=bar_data["h"],
                                low=bar_data["l"],
                                close=bar_data["c"],
                                volume=round(bar_data["v"]),  # Round fractional volumes to nearest integer
                                vwap=bar_data.get("vw"),
                                transactions=bar_data.get("n")
                            )
                            all_bars.append(bar)
                        
                        # Check if we got the max number of bars (might need smaller chunks)
                        if len(response["results"]) >= MAX_BARS_PER_REQUEST:
                            logger.warning(f"Hit bar limit for {symbol} chunk {current_start} to {chunk_end}")
                            # Reduce chunk size for next iteration
                            chunk_days = max(MIN_CHUNK_DAYS, (chunk_end - current_start).days // 2)
                            chunk_end = current_start + timedelta(days=chunk_days - 1)
                            continue
                            
                    break  # Success, exit retry loop
                    
                except PolygonAPIError as e:
                    if e.status_code == 404:
                        # No data for this symbol/period
                        logger.debug(f"No minute data for {symbol} from {current_start} to {chunk_end}")
                        break
                    elif attempt < max_attempts - 1:
                        logger.warning(f"API error for {symbol}, attempt {attempt + 1}: {e}")
                        # Removed sleep delay for faster loading
                    else:
                        logger.error(f"Failed to fetch minute data for {symbol} after {max_attempts} attempts: {e}")
                        return None
                        
                except Exception as e:
                    logger.error(f"Unexpected error fetching minute data for {symbol}: {e}")
                    return None
                    
            # Move to next chunk
            current_start = chunk_end + timedelta(days=1)
            
        return all_bars if all_bars else None
        
    def _format_date(self, date_obj: date) -> str:
        """Format date for Polygon API (YYYY-MM-DD)"""
        return date_obj.strftime("%Y-%m-%d")
        
    async def _store_minute_bars_batch(self, bars: List[StockBar]):
        """Store a batch of minute bars efficiently"""
        if not bars:
            return
            
        try:
            # Prepare records for bulk insert
            records = []
            for bar in bars:
                records.append((
                    bar.timestamp,
                    bar.symbol,
                    float(bar.open),
                    float(bar.high),
                    float(bar.low),
                    float(bar.close),
                    bar.volume,
                    float(bar.vwap) if bar.vwap else None,
                    bar.transactions
                ))
                
            async with DatabaseTransaction() as conn:
                # Use COPY for efficient bulk insert
                await conn.copy_records_to_table(
                    'minute_bars',
                    records=records,
                    columns=['time', 'symbol', 'open', 'high', 'low', 'close', 'volume', 'vwap', 'transactions']
                )
                
        except Exception as e:
            logger.error(f"Error storing batch of {len(bars)} minute bars: {e}")
            raise
            
    async def load_minute_data_by_symbol(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        priority_load: bool = True,
        batch_size: int = 5000
    ) -> Dict[str, Any]:
        """
        Load minute data for specified symbols
        
        Args:
            symbols: List of symbols to load
            start_date: Start date
            end_date: End date
            priority_load: If True, load high-volume stocks first
            batch_size: Batch size for database inserts
            
        Returns:
            Load statistics
        """
        job_id = f"minute_load_{start_date}_{end_date}"
        
        # Check for existing progress
        resume_state = self.progress_tracker.get_resume_state(job_id)
        if resume_state and resume_state.get("status") != "completed":
            logger.info(f"Resuming minute load from checkpoint: {resume_state}")
            processed_symbols = set(resume_state.get("processed_symbols", []))
            failed_symbols = set(resume_state.get("failed_symbols", []))
        else:
            processed_symbols = set()
            failed_symbols = set()
            
        # Initialize statistics
        stats = {
            "total_symbols": len(symbols),
            "processed_symbols": len(processed_symbols),
            "failed_symbols": len(failed_symbols),
            "total_bars": 0,
            "errors": 0,
            "start_time": datetime.now().isoformat(),
            "status": "in_progress"
        }
        
        # Get volume data for prioritization if requested
        if priority_load:
            logger.info("Fetching volume data for prioritization...")
            volumes = await self._get_stock_volumes(symbols)
            priority_queue = self._create_priority_queue(symbols, volumes)
            
            # Convert to ordered list
            symbols_to_process = []
            while priority_queue:
                _, symbol = heapq.heappop(priority_queue)
                if symbol not in processed_symbols:
                    symbols_to_process.append(symbol)
        else:
            symbols_to_process = [s for s in symbols if s not in processed_symbols]
            
        logger.info(f"Loading minute data for {len(symbols_to_process)} symbols from {start_date} to {end_date}")
        
        # Process symbols with controlled concurrency
        async def process_symbol(symbol: str) -> Tuple[str, bool, int]:
            """Process a single symbol and return (symbol, success, bar_count)"""
            async with self.minute_semaphore:
                if self.shutdown_requested:
                    return symbol, False, 0
                    
                try:
                    logger.info(f"Loading minute data for {symbol} ({stats['processed_symbols'] + 1}/{stats['total_symbols']})")
                    
                    # Fetch minute bars
                    bars = await self._fetch_minute_bars(symbol, start_date, end_date)
                    
                    if bars:
                        # Store in batches
                        for i in range(0, len(bars), batch_size):
                            batch = bars[i:i + batch_size]
                            await self._store_minute_bars_batch(batch)
                            
                        # Update coverage
                        await self._update_minute_coverage(symbol, start_date, end_date)
                        
                        return symbol, True, len(bars)
                    else:
                        return symbol, False, 0
                        
                except Exception as e:
                    logger.error(f"Error processing {symbol}: {e}")
                    await self._log_minute_error(symbol, start_date, end_date, str(e))
                    return symbol, False, 0
                    
        # Create tasks for concurrent processing
        tasks = []
        for symbol in symbols_to_process:
            if self.shutdown_requested:
                break
            tasks.append(process_symbol(symbol))
            
        # Process in chunks to avoid overwhelming the system
        chunk_size = MAX_CONCURRENT_SYMBOLS
        for i in range(0, len(tasks), chunk_size):
            if self.shutdown_requested:
                break
                
            chunk_tasks = tasks[i:i + chunk_size]
            results = await asyncio.gather(*chunk_tasks, return_exceptions=True)
            
            # Process results
            for result in results:
                if isinstance(result, Exception):
                    logger.error(f"Task failed with exception: {result}")
                    stats["errors"] += 1
                else:
                    symbol, success, bar_count = result
                    processed_symbols.add(symbol)
                    stats["processed_symbols"] += 1
                    
                    if success:
                        stats["total_bars"] += bar_count
                        logger.debug(f"Successfully loaded {bar_count} bars for {symbol}")
                    else:
                        failed_symbols.add(symbol)
                        stats["failed_symbols"] = len(failed_symbols)
                        stats["errors"] += 1
                        
            # Save checkpoint after each chunk
            self.progress_tracker.update_progress(job_id, {
                **stats,
                "processed_symbols": list(processed_symbols),
                "failed_symbols": list(failed_symbols),
                "last_updated": datetime.now().isoformat()
            })
            
        # Mark job as complete
        if stats["processed_symbols"] == stats["total_symbols"]:
            stats["status"] = "completed"
            stats["completed_at"] = datetime.now().isoformat()
            self.progress_tracker.mark_complete(job_id)
        else:
            stats["status"] = "interrupted" if self.shutdown_requested else "partial"
            
        stats["end_time"] = datetime.now().isoformat()
        
        return stats
        
    async def _update_minute_coverage(self, symbol: str, start_date: date, end_date: date):
        """Update coverage tracking for minute data"""
        try:
            async with DatabaseTransaction() as conn:
                await conn.execute('''
                    INSERT INTO data_coverage (symbol, data_type, start_date, end_date, last_updated)
                    VALUES ($1, $2, $3, $4, $5)
                    ON CONFLICT (symbol, data_type)
                    DO UPDATE SET
                        start_date = LEAST(data_coverage.start_date, EXCLUDED.start_date),
                        end_date = GREATEST(data_coverage.end_date, EXCLUDED.end_date),
                        last_updated = EXCLUDED.last_updated
                ''', symbol, 'minute', start_date, end_date, datetime.now(pytz.UTC))
                
        except Exception as e:
            logger.error(f"Error updating minute coverage for {symbol}: {e}")
            
    async def _log_minute_error(self, symbol: str, start_date: date, end_date: date, error_message: str):
        """Log error for minute data load"""
        try:
            await db_pool.execute('''
                INSERT INTO data_fetch_errors (symbol, error_type, error_message, start_date, end_date)
                VALUES ($1, $2, $3, $4, $5)
            ''', symbol, 'minute_load_error', error_message, start_date, end_date)
        except Exception as e:
            logger.error(f"Failed to log minute error: {e}")
            
    async def load_daily_minute_update(
        self,
        target_date: Optional[date] = None,
        symbols: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Load minute data for the most recent trading day
        
        Args:
            target_date: Specific date to update (None = most recent trading day)
            symbols: Optional list of symbols (None = all universe)
            
        Returns:
            Update statistics
        """
        if target_date is None:
            target_date = self._get_last_trading_day()
            
        # If no symbols specified, use the full universe
        if symbols is None:
            symbols = await self.discover_universe()
            
        logger.info(f"Running minute data update for {target_date} with {len(symbols)} symbols")
        
        # Load minute data for single day
        stats = await self.load_minute_data_by_symbol(
            symbols=symbols,
            start_date=target_date,
            end_date=target_date,
            priority_load=True  # Always prioritize for daily updates
        )
        
        return stats


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Enhanced Data Loader for US Equities Universe (Common Stocks + ETFs)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Discover universe of stocks
  python universe_data_loader.py --discover
  
  # Load historical daily data for date range
  python universe_data_loader.py --historical --start 2024-01-01 --end 2024-12-31
  
  # Load historical minute data for date range
  python universe_data_loader.py --historical --minute --start 2024-01-01 --end 2024-01-31
  
  # Run daily update for daily bars
  python universe_data_loader.py --daily
  
  # Run daily update for minute bars
  python universe_data_loader.py --daily --minute
  
  # Load minute data for specific symbols
  python universe_data_loader.py --historical --minute --symbols AAPL,MSFT,GOOGL --start 2024-01-01 --end 2024-01-31
  
  # Verify data integrity
  python universe_data_loader.py --verify --sample-size 200
  
  # Resume interrupted job
  python universe_data_loader.py --resume
  
  # Clear checkpoint for fresh start
  python universe_data_loader.py --clear-checkpoint historical_load_2024-01-01_2024-12-31
        """
    )
    
    parser.add_argument("--discover", action="store_true", help="Discover universe of US common stocks and ETFs")
    parser.add_argument("--historical", action="store_true", help="Load historical data")
    parser.add_argument("--daily", action="store_true", help="Run daily update")
    parser.add_argument("--minute", action="store_true", help="Load minute data instead of daily")
    parser.add_argument("--verify", action="store_true", help="Verify data integrity")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--clear-checkpoint", type=str, help="Clear specific checkpoint")
    
    parser.add_argument("--start", type=str, help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, help="End date (YYYY-MM-DD)")
    parser.add_argument("--date", type=str, help="Specific date for daily update (YYYY-MM-DD)")
    
    parser.add_argument("--symbols", type=str, help="Comma-separated list of symbols to filter")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for database inserts (default: 1000 for daily, 5000 for minute)")
    parser.add_argument("--sample-size", type=int, default=100, help="Sample size for verification")
    parser.add_argument("--no-priority", action="store_true", help="Disable priority-based loading for minute data")
    
    parser.add_argument("--force-refresh", action="store_true", help="Force refresh universe discovery")
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.historical and (not args.start or not args.end):
        parser.error("--historical requires --start and --end dates")
        
    # Initialize loader
    loader = UniverseDataLoader()
    
    try:
        await loader.initialize()
        
        # Handle checkpoint operations
        if args.clear_checkpoint:
            loader.progress_tracker.clear_job(args.clear_checkpoint)
            logger.info(f"Cleared checkpoint: {args.clear_checkpoint}")
            return
            
        # Parse symbols if provided
        symbols = None
        if args.symbols:
            symbols = [s.strip().upper() for s in args.symbols.split(",")]
            logger.info(f"Filtering for {len(symbols)} symbols")
            
        # Adjust batch size for minute data
        if args.minute and args.batch_size == 1000:  # Default value
            args.batch_size = 5000
            
        # Execute requested operations
        if args.discover:
            universe = await loader.discover_universe(force_refresh=args.force_refresh)
            print(f"\nDiscovered {len(universe)} US equities (common stocks + ETFs)")
            print(f"First 10 symbols: {universe[:10]}")
            
            # Update symbols table
            logger.info("Updating symbols table with discovered universe...")
            symbols_updated = await loader.data_collector.update_symbols_table()
            print(f"Updated {symbols_updated} symbols in database")
            
        elif args.historical:
            start_date = datetime.strptime(args.start, "%Y-%m-%d").date()
            end_date = datetime.strptime(args.end, "%Y-%m-%d").date()
            
            if args.minute:
                # Load minute data
                if not symbols:
                    universe = await loader.discover_universe()
                    symbols = universe
                    logger.info(f"Loading minute data for {len(symbols)} symbols")
                    
                stats = await loader.load_minute_data_by_symbol(
                    symbols=symbols,
                    start_date=start_date,
                    end_date=end_date,
                    priority_load=not args.no_priority,
                    batch_size=args.batch_size
                )
                
                print(f"\nMinute Data Load Results:")
                print(f"  Status: {stats['status']}")
                print(f"  Symbols Processed: {stats['processed_symbols']}/{stats['total_symbols']}")
                print(f"  Failed Symbols: {stats['failed_symbols']}")
                print(f"  Total Bars: {stats['total_bars']:,}")
                print(f"  Errors: {stats['errors']}")
                
                if stats.get('failed_symbols', 0) > 0:
                    print(f"\n  Note: {stats['failed_symbols']} symbols had no minute data or errors")
            else:
                # Load daily data
                if not symbols:
                    universe = await loader.discover_universe()
                    logger.info(f"Loading daily data for {len(universe)} symbols")
                    
                    # Update symbols table before loading data
                    logger.info("Updating symbols table...")
                    symbols_updated = await loader.data_collector.update_symbols_table()
                    logger.info(f"Updated {symbols_updated} symbols in database")
                    
                stats = await loader.load_historical_data_by_date(
                    start_date=start_date,
                    end_date=end_date,
                    symbols=symbols,
                    batch_size=args.batch_size
                )
                
                print(f"\nHistorical Load Results:")
                print(f"  Status: {stats['status']}")
                print(f"  Dates Processed: {stats['processed_dates']}/{stats['total_dates']}")
                print(f"  Total Bars: {stats['total_bars']:,}")
                print(f"  Errors: {stats['errors']}")
            
        elif args.daily:
            target_date = None
            if args.date:
                target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
                
            if args.minute:
                # Load minute data for daily update
                stats = await loader.load_daily_minute_update(
                    target_date=target_date,
                    symbols=symbols
                )
                
                print(f"\nMinute Data Daily Update Results:")
                print(f"  Status: {stats['status']}")
                print(f"  Symbols Processed: {stats['processed_symbols']}/{stats['total_symbols']}")
                print(f"  Total Bars: {stats['total_bars']:,}")
                print(f"  Errors: {stats['errors']}")
            else:
                # Load daily data update
                stats = await loader.load_daily_update(target_date)
                
                print(f"\nDaily Update Results:")
                print(f"  Status: {stats['status']}")
                print(f"  Bars Loaded: {stats['total_bars']:,}")
                print(f"  Symbols Updated: {stats.get('symbols_updated', 0)}")
            
        elif args.verify:
            results = await loader.verify_data_integrity(sample_size=args.sample_size)
            
            print(f"\nData Integrity Check:")
            print(f"  Symbols Checked: {results['symbols_checked']}")
            print(f"  Symbols with Gaps: {len(results['data_gaps'])}")
            print(f"  Invalid OHLC Found: {len(results['invalid_ohlc'])}")
            
            if results['data_gaps']:
                print(f"\nFirst 5 symbols with gaps:")
                for gap in results['data_gaps'][:5]:
                    print(f"  {gap['symbol']}: {len(gap['missing_dates'])} missing dates")
                    
        else:
            parser.print_help()
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        raise
    finally:
        await loader.cleanup()


if __name__ == "__main__":
    asyncio.run(main())