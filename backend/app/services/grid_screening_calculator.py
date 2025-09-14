"""
Grid Screening Calculator Service

Calculates screening filter values for all symbols on a given date and stores
them in the grid_screening table.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import Dict, Any, List, Optional, Set
import numpy as np
import asyncpg
from uuid import uuid4
import time

from ..core.enhanced_filters import (
    EnhancedPriceVsMAFilter,
    EnhancedRSIFilter,
    EnhancedGapFilter,
    EnhancedPreviousDayDollarVolumeFilter,
    EnhancedRelativeVolumeFilter
)
from ..services.fast_data_converter import rows_to_numpy
from ..config import settings

logger = logging.getLogger(__name__)


class GridScreeningCalculator:
    """Calculates screening values for grid analysis."""
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        
        # Initialize filters that we'll reuse
        self.filters = {
            'ma_20': EnhancedPriceVsMAFilter(period=20, return_daily_values=True),
            'ma_50': EnhancedPriceVsMAFilter(period=50, return_daily_values=True),
            'ma_200': EnhancedPriceVsMAFilter(period=200, return_daily_values=True),
            'rsi_14': EnhancedRSIFilter(period=14, return_daily_values=True),
            'gap': EnhancedGapFilter(return_daily_values=True),
            'prev_dollar_vol': EnhancedPreviousDayDollarVolumeFilter(return_daily_values=True),
            'rel_vol': EnhancedRelativeVolumeFilter(return_daily_values=True)
        }
    
    async def calculate_for_date(self, process_date: date, 
                                limit: Optional[int] = None,
                                use_bulk_loading: bool = True) -> Dict[str, Any]:
        """
        Calculate screening values for all symbols on a given date.
        
        Args:
            process_date: Date to calculate values for
            limit: Optional limit on number of symbols (for testing)
            
        Returns:
            Dictionary with processing statistics
        """
        start_time = time.time()
        
        # Get symbols with data for this date
        symbols = await self._get_symbols_for_date(process_date, limit)
        
        if not symbols:
            logger.info(f"No symbols found for {process_date}")
            return {
                'date': process_date,
                'total_symbols': 0,
                'processed': 0,
                'errors': 0,
                'duration_seconds': time.time() - start_time
            }
        
        logger.info(f"Processing {len(symbols)} symbols for {process_date}")
        
        # Get existing symbols to avoid duplicates
        existing_symbols = await self._get_existing_symbols(process_date)
        symbols_to_process = [s for s in symbols if s not in existing_symbols]
        
        if not symbols_to_process:
            logger.info(f"All {len(symbols)} symbols already processed for {process_date}")
            return {
                'date': process_date,
                'total_symbols': len(symbols),
                'already_processed': len(symbols),
                'processed': 0,
                'errors': 0,
                'duration_seconds': time.time() - start_time
            }
        
        logger.info(f"Need to process {len(symbols_to_process)} new symbols")
        
        if use_bulk_loading and len(symbols_to_process) > 20:
            # Use bulk loading for better performance with many symbols
            logger.info("Using bulk loading strategy")
            result = await self._process_bulk(symbols_to_process, process_date)
            processed_count = result['processed']
            error_count = result['errors']
        else:
            # Use batch processing for smaller datasets
            logger.info("Using batch processing strategy")
            
            # Process in batches
            batch_size = 5  # Optimal based on performance testing
            processed_count = 0
            error_count = 0
            all_results = []
            
            for i in range(0, len(symbols_to_process), batch_size):
                batch = symbols_to_process[i:i + batch_size]
                batch_results = await self._process_batch(batch, process_date)
                
                # Collect results
                for result in batch_results:
                    if result['success']:
                        all_results.append(result['data'])
                        processed_count += 1
                    else:
                        error_count += 1
                        logger.error(f"Failed to process {result['symbol']}: {result.get('error')}")
                
                # Save batch to database
                if all_results:
                    await self._save_results_to_db(all_results)
                    all_results = []  # Clear for next batch
                
                # Log progress
                total_done = i + len(batch)
                progress = (total_done / len(symbols_to_process)) * 100
                logger.info(f"Progress: {total_done}/{len(symbols_to_process)} ({progress:.1f}%)")
        
        # Final statistics
        duration = time.time() - start_time
        logger.info(f"Completed processing {process_date} in {duration:.2f} seconds")
        logger.info(f"Processed: {processed_count}, Errors: {error_count}")
        
        return {
            'date': process_date,
            'total_symbols': len(symbols),
            'already_processed': len(existing_symbols),
            'processed': processed_count,
            'errors': error_count,
            'duration_seconds': duration
        }
    
    async def _get_symbols_for_date(self, process_date: date, 
                                   limit: Optional[int] = None) -> List[str]:
        """Get all symbols that have data for the given date."""
        async with self.db_pool.acquire() as conn:
            # Check if testing mode is enabled
            if settings.TESTING_MODE:
                # Use only testing symbols
                query = """
                SELECT DISTINCT symbol 
                FROM daily_bars 
                WHERE time::date = $1 
                    AND symbol = ANY($2::text[])
                ORDER BY symbol
                """
                rows = await conn.fetch(query, process_date, settings.TESTING_SYMBOLS)
                symbols = [row['symbol'] for row in rows]
                logger.info(f"Testing mode: Found {len(symbols)} symbols from testing list")
                return symbols
            
            # Normal mode - get all symbols
            query = """
            SELECT DISTINCT symbol 
            FROM daily_bars 
            WHERE time::date = $1 
            ORDER BY symbol
            """
            
            if limit:
                query += f" LIMIT {limit}"
            
            rows = await conn.fetch(query, process_date)
            return [row['symbol'] for row in rows]
    
    async def _get_existing_symbols(self, process_date: date) -> Set[str]:
        """Get symbols already processed for this date."""
        async with self.db_pool.acquire() as conn:
            query = """
            SELECT symbol 
            FROM grid_screening 
            WHERE date = $1
            """
            rows = await conn.fetch(query, process_date)
            return set(row['symbol'] for row in rows)
    
    async def _process_batch(self, symbols: List[str], 
                           process_date: date) -> List[Dict[str, Any]]:
        """Process a batch of symbols concurrently."""
        tasks = []
        for symbol in symbols:
            task = asyncio.create_task(self._calculate_symbol_metrics(symbol, process_date))
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        processed_results = []
        for symbol, result in zip(symbols, results):
            if isinstance(result, Exception):
                processed_results.append({
                    'symbol': symbol,
                    'success': False,
                    'error': str(result)
                })
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def _calculate_symbol_metrics(self, symbol: str, 
                                      process_date: date) -> Dict[str, Any]:
        """Calculate all screening metrics for a single symbol."""
        try:
            # Load data with sufficient lookback for MA200
            lookback_days = 252  # 1 year for MA200 + buffer
            start_date = process_date - timedelta(days=lookback_days)
            
            # Load data directly from database
            async with self.db_pool.acquire() as conn:
                query = """
                SELECT 
                    time::date as date,
                    open, high, low, close, volume
                FROM daily_bars
                WHERE symbol = $1
                    AND time::date >= $2
                    AND time::date <= $3
                ORDER BY time ASC
                """
                rows = await conn.fetch(query, symbol, start_date, process_date)
            
            if not rows or len(rows) == 0:
                return {
                    'symbol': symbol,
                    'success': False,
                    'error': 'No data available'
                }
            
            # Convert to numpy array
            np_data = rows_to_numpy(rows)
            
            # Get the latest values
            latest_close = float(np_data['close'][-1])
            
            # Calculate all metrics
            metrics = {
                'symbol': symbol,
                'date': process_date,
                'price': latest_close
            }
            
            # MA values
            for period in [20, 50, 200]:
                filter_key = f'ma_{period}'
                result = self.filters[filter_key].apply(np_data, symbol)
                
                if 'ma_values' in result.metrics:
                    ma_values = result.metrics['ma_values']
                    if len(ma_values) > 0 and not np.isnan(ma_values[-1]):
                        metrics[filter_key] = float(ma_values[-1])
                    else:
                        metrics[filter_key] = None
                else:
                    metrics[filter_key] = None
            
            # RSI
            result = self.filters['rsi_14'].apply(np_data, symbol)
            if 'rsi_values' in result.metrics:
                rsi_values = result.metrics['rsi_values']
                if len(rsi_values) > 0 and not np.isnan(rsi_values[-1]):
                    metrics['rsi_14'] = float(rsi_values[-1])
                else:
                    metrics['rsi_14'] = None
            else:
                metrics['rsi_14'] = None
            
            # Gap percentage
            result = self.filters['gap'].apply(np_data, symbol)
            if 'gap_percentages' in result.metrics:
                gap_values = result.metrics['gap_percentages']
                if len(gap_values) > 0 and not np.isnan(gap_values[-1]):
                    metrics['gap_percent'] = float(gap_values[-1])
                else:
                    metrics['gap_percent'] = None
            else:
                metrics['gap_percent'] = None
            
            # Previous day dollar volume
            result = self.filters['prev_dollar_vol'].apply(np_data, symbol)
            if 'prev_day_dollar_volumes' in result.metrics:
                prev_vols = result.metrics['prev_day_dollar_volumes']
                if len(prev_vols) > 0 and not np.isnan(prev_vols[-1]):
                    metrics['prev_day_dollar_volume'] = float(prev_vols[-1])
                else:
                    metrics['prev_day_dollar_volume'] = None
            else:
                metrics['prev_day_dollar_volume'] = None
            
            # Relative volume
            result = self.filters['rel_vol'].apply(np_data, symbol)
            if 'relative_volume_ratios' in result.metrics:
                rel_ratios = result.metrics['relative_volume_ratios']
                if len(rel_ratios) > 0 and not np.isnan(rel_ratios[-1]):
                    metrics['relative_volume'] = float(rel_ratios[-1])
                else:
                    metrics['relative_volume'] = None
            else:
                metrics['relative_volume'] = None
            
            return {
                'symbol': symbol,
                'success': True,
                'data': metrics
            }
            
        except Exception as e:
            logger.error(f"Error calculating metrics for {symbol}: {str(e)}")
            return {
                'symbol': symbol,
                'success': False,
                'error': str(e)
            }
    
    async def _process_bulk(self, symbols: List[str], process_date: date) -> Dict[str, int]:
        """
        Process symbols using bulk loading for better performance.
        """
        # Load all data in one query
        lookback_days = 252  # 1 year for MA200 + buffer
        start_date = process_date - timedelta(days=lookback_days)
        
        logger.info(f"Bulk loading data for {len(symbols)} symbols")
        
        async with self.db_pool.acquire() as conn:
            query = """
            SELECT 
                symbol,
                time::date as date,
                open, high, low, close, volume
            FROM daily_bars
            WHERE symbol = ANY($1::text[])
                AND time::date >= $2
                AND time::date <= $3
            ORDER BY symbol, time ASC
            """
            rows = await conn.fetch(query, symbols, start_date, process_date)
        
        logger.info(f"Loaded {len(rows)} total bars")
        
        # Group by symbol
        from collections import defaultdict
        data_by_symbol = defaultdict(list)
        for row in rows:
            data_by_symbol[row['symbol']].append(row)
        
        logger.info(f"Processing {len(data_by_symbol)} symbols with data")
        
        # Process all symbols
        all_results = []
        processed_count = 0
        error_count = 0
        
        for symbol, symbol_rows in data_by_symbol.items():
            try:
                # Convert to numpy array
                np_data = rows_to_numpy(symbol_rows)
                
                if len(np_data) < 21:  # Minimum for most calculations
                    error_count += 1
                    continue
                
                # Calculate metrics using the same logic
                metrics = self._calculate_metrics_from_data(symbol, process_date, np_data)
                all_results.append(metrics)
                processed_count += 1
                
                # Save in batches of 100
                if len(all_results) >= 100:
                    await self._save_results_to_db(all_results)
                    all_results = []
                    logger.info(f"Progress: {processed_count}/{len(symbols)} processed")
                    
            except Exception as e:
                logger.error(f"Error processing {symbol}: {str(e)}")
                error_count += 1
        
        # Save remaining results
        if all_results:
            await self._save_results_to_db(all_results)
        
        return {
            'processed': processed_count,
            'errors': error_count
        }
    
    def _calculate_metrics_from_data(self, symbol: str, process_date: date, 
                                    np_data: np.ndarray) -> Dict[str, Any]:
        """
        Calculate all metrics from numpy data.
        """
        # Get the latest values
        latest_close = float(np_data['close'][-1])
        
        # Calculate all metrics
        metrics = {
            'symbol': symbol,
            'date': process_date,
            'price': latest_close
        }
        
        # MA values
        for period in [20, 50, 200]:
            filter_key = f'ma_{period}'
            result = self.filters[filter_key].apply(np_data, symbol)
            
            if 'ma_values' in result.metrics:
                ma_values = result.metrics['ma_values']
                if len(ma_values) > 0 and not np.isnan(ma_values[-1]):
                    metrics[filter_key] = float(ma_values[-1])
                else:
                    metrics[filter_key] = None
            else:
                metrics[filter_key] = None
        
        # RSI
        result = self.filters['rsi_14'].apply(np_data, symbol)
        if 'rsi_values' in result.metrics:
            rsi_values = result.metrics['rsi_values']
            if len(rsi_values) > 0 and not np.isnan(rsi_values[-1]):
                metrics['rsi_14'] = float(rsi_values[-1])
            else:
                metrics['rsi_14'] = None
        else:
            metrics['rsi_14'] = None
        
        # Gap percentage
        result = self.filters['gap'].apply(np_data, symbol)
        if 'gap_percentages' in result.metrics:
            gap_values = result.metrics['gap_percentages']
            if len(gap_values) > 0 and not np.isnan(gap_values[-1]):
                metrics['gap_percent'] = float(gap_values[-1])
            else:
                metrics['gap_percent'] = None
        else:
            metrics['gap_percent'] = None
        
        # Previous day dollar volume
        result = self.filters['prev_dollar_vol'].apply(np_data, symbol)
        if 'prev_day_dollar_volumes' in result.metrics:
            prev_vols = result.metrics['prev_day_dollar_volumes']
            if len(prev_vols) > 0 and not np.isnan(prev_vols[-1]):
                metrics['prev_day_dollar_volume'] = float(prev_vols[-1])
            else:
                metrics['prev_day_dollar_volume'] = None
        else:
            metrics['prev_day_dollar_volume'] = None
        
        # Relative volume
        result = self.filters['rel_vol'].apply(np_data, symbol)
        if 'relative_volume_ratios' in result.metrics:
            rel_ratios = result.metrics['relative_volume_ratios']
            if len(rel_ratios) > 0 and not np.isnan(rel_ratios[-1]):
                metrics['relative_volume'] = float(rel_ratios[-1])
            else:
                metrics['relative_volume'] = None
        else:
            metrics['relative_volume'] = None
        
        return metrics
    
    async def _save_results_to_db(self, results: List[Dict[str, Any]]) -> None:
        """Save batch of results to database."""
        if not results:
            return
        
        async with self.db_pool.acquire() as conn:
            # Prepare data for bulk insert
            insert_data = []
            for result in results:
                insert_data.append((
                    result['symbol'],
                    result['date'],
                    result.get('price'),
                    result.get('ma_20'),
                    result.get('ma_50'),
                    result.get('ma_200'),
                    result.get('rsi_14'),
                    result.get('gap_percent'),
                    result.get('prev_day_dollar_volume'),
                    result.get('relative_volume')
                ))
            
            # Bulk insert
            await conn.executemany("""
                INSERT INTO grid_screening (
                    symbol, date, price, ma_20, ma_50, ma_200,
                    rsi_14, gap_percent, prev_day_dollar_volume, relative_volume
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (symbol, date) DO NOTHING
            """, insert_data)
            
            logger.info(f"Saved {len(results)} screening results to database")