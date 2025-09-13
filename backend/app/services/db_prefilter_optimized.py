"""
Optimized database pre-filtering with bulk processing.
"""

from typing import List, Dict, Any, Optional, Set
from datetime import date
import asyncpg
import logging
from dataclasses import dataclass
from collections import defaultdict
import time

from ..models.simple_requests import SimpleFilters, SimplePriceRangeParams

logger = logging.getLogger(__name__)


@dataclass
class PreFilterResult:
    """Result from database pre-filtering."""
    symbols_to_process: Set[str]
    symbols_filtered_out: Set[str]
    total_symbols: int
    
    @property
    def filter_efficiency(self) -> float:
        """Calculate how many symbols were filtered out."""
        if self.total_symbols == 0:
            return 0.0
        return len(self.symbols_filtered_out) / self.total_symbols


class OptimizedDataLoader:
    """
    Optimized data loader with bulk processing and minimal overhead.
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
        self.prefilter = DatabasePreFilter(db_pool)
    
    async def load_data_for_screening(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        filters: SimpleFilters,
        enable_prefiltering: bool = True
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Load stock data optimized for the active filters.
        
        Returns:
            Dictionary mapping symbol to list of daily bars
        """
        # Determine if pre-filtering would help
        date_range_days = (end_date - start_date).days + 1
        
        if enable_prefiltering and await self.prefilter.should_use_prefiltering(
            len(symbols), date_range_days
        ):
            # Apply pre-filtering
            prefilter_result = await self.prefilter.prefilter_symbols(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date,
                filters=filters
            )
            symbols_to_load = list(prefilter_result.symbols_to_process)
            
            logger.info(
                f"Pre-filtering reduced symbols from {prefilter_result.total_symbols} "
                f"to {len(symbols_to_load)} ({prefilter_result.filter_efficiency*100:.1f}% filtered)"
            )
        else:
            symbols_to_load = symbols
        
        # Load data for remaining symbols
        if not symbols_to_load:
            return {}
        
        # Use optimized bulk loading
        return await self._bulk_load_optimized(symbols_to_load, start_date, end_date)
    
    async def _bulk_load_optimized(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Optimized bulk loading with minimal overhead.
        Uses column-based processing to avoid dict conversion overhead.
        """
        query = """
        SELECT symbol, time::date as date, open, high, low, close, volume
        FROM daily_bars
        WHERE symbol = ANY($1::text[])
          AND time::date BETWEEN $2 AND $3
        ORDER BY symbol, time
        """
        
        start_time = time.time()
        
        async with self.db_pool.acquire() as conn:
            # Use prepared statement for better performance
            stmt = await conn.prepare(query)
            rows = await stmt.fetch(symbols, start_date, end_date)
        
        fetch_time = time.time() - start_time
        
        # Process in bulk using defaultdict for O(1) append
        data_by_symbol = defaultdict(list)
        
        # Direct processing without dict conversion
        for row in rows:
            # Keep row as asyncpg Record (dict-like but more efficient)
            data_by_symbol[row['symbol']].append(row)
        
        process_time = time.time() - start_time - fetch_time
        
        logger.info(
            f"Bulk loaded {len(rows)} bars for {len(data_by_symbol)} symbols "
            f"(fetch: {fetch_time:.3f}s, process: {process_time:.3f}s)"
        )
        
        return dict(data_by_symbol)
    
    async def get_all_active_symbols(
        self,
        start_date: date,
        end_date: date,
        symbol_types: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get all active symbols that have data in the specified date range.
        """
        if symbol_types is None:
            symbol_types = ['CS', 'ETF']
        
        query = """
        SELECT DISTINCT s.symbol
        FROM symbols s
        INNER JOIN daily_bars db ON s.symbol = db.symbol
        WHERE s.active = true
          AND s.type = ANY($1::text[])
          AND db.time::date BETWEEN $2 AND $3
          AND db.volume > 0
        ORDER BY s.symbol
        """
        
        try:
            async with self.db_pool.acquire() as conn:
                rows = await conn.fetch(
                    query,
                    symbol_types,
                    start_date,
                    end_date
                )
            
            symbols = [row['symbol'] for row in rows]
            logger.info(
                f"Found {len(symbols)} active symbols with data between {start_date} and {end_date}"
            )
            
            return symbols
        except Exception as e:
            logger.error(f"Error fetching all active symbols: {e}")
            raise


class DatabasePreFilter:
    """
    Handles database-level pre-filtering to reduce data loading.
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db_pool = db_pool
    
    async def prefilter_symbols(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        filters: SimpleFilters
    ) -> PreFilterResult:
        """
        Pre-filter symbols based on filters that can be evaluated at DB level.
        """
        total_symbols = len(symbols)
        qualifying_symbols = set(symbols)
        
        # Apply price range pre-filter if present
        if filters.price_range:
            price_qualifying = await self._prefilter_by_price_range(
                symbols=list(qualifying_symbols),
                start_date=start_date,
                end_date=end_date,
                price_range=filters.price_range
            )
            qualifying_symbols &= price_qualifying
        
        # Apply volume pre-filter if present
        if filters.min_avg_volume:
            volume_qualifying = await self._prefilter_by_volume(
                symbols=list(qualifying_symbols),
                start_date=start_date,
                end_date=end_date,
                min_volume=filters.min_avg_volume.min_avg_volume
            )
            qualifying_symbols &= volume_qualifying
        
        # Apply dollar volume pre-filter if present (conservative)
        if filters.min_avg_dollar_volume:
            min_volume_estimate = filters.min_avg_dollar_volume.min_avg_dollar_volume / 100
            dollar_vol_qualifying = await self._prefilter_by_volume(
                symbols=list(qualifying_symbols),
                start_date=start_date,
                end_date=end_date,
                min_volume=min_volume_estimate
            )
            qualifying_symbols &= dollar_vol_qualifying
        
        symbols_set = set(symbols)
        filtered_out = symbols_set - qualifying_symbols
        
        logger.info(
            f"Pre-filter results: {len(qualifying_symbols)}/{total_symbols} symbols passed, "
            f"{len(filtered_out)} filtered out"
        )
        
        return PreFilterResult(
            symbols_to_process=qualifying_symbols,
            symbols_filtered_out=filtered_out,
            total_symbols=total_symbols
        )
    
    async def _prefilter_by_price_range(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        price_range: SimplePriceRangeParams
    ) -> Set[str]:
        """Pre-filter symbols by price range."""
        query = """
        SELECT DISTINCT symbol
        FROM daily_bars
        WHERE symbol = ANY($1::text[])
          AND time::date BETWEEN $2 AND $3
          AND open >= $4
          AND open <= $5
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                symbols,
                start_date,
                end_date,
                price_range.min_price,
                price_range.max_price
            )
        
        return {row['symbol'] for row in rows}
    
    async def _prefilter_by_volume(
        self,
        symbols: List[str],
        start_date: date,
        end_date: date,
        min_volume: float
    ) -> Set[str]:
        """Pre-filter symbols by volume."""
        query = """
        SELECT DISTINCT symbol
        FROM daily_bars
        WHERE symbol = ANY($1::text[])
          AND time::date BETWEEN $2 AND $3
          AND volume >= $4
        """
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                symbols,
                start_date,
                end_date,
                min_volume
            )
        
        return {row['symbol'] for row in rows}
    
    async def should_use_prefiltering(
        self,
        num_symbols: int,
        date_range_days: int
    ) -> bool:
        """Determine if pre-filtering would be beneficial."""
        estimated_data_points = num_symbols * date_range_days
        return estimated_data_points > 10000