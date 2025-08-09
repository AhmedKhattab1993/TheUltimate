"""
Database pre-filtering strategies for the simplified filters.

This module provides efficient database queries to pre-filter stocks
before loading all data into memory for vectorized operations.
"""

from typing import List, Dict, Any, Optional, Set
from datetime import date
import asyncpg
import logging
from dataclasses import dataclass

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


class DatabasePreFilter:
    """
    Handles database-level pre-filtering to reduce data loading.
    
    Only the price range filter can be efficiently pre-filtered at the
    database level. MA and RSI require historical calculations.
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
        
        Args:
            symbols: List of symbols to check
            start_date: Start date for filtering
            end_date: End date for filtering
            filters: Simple filters to apply
            
        Returns:
            PreFilterResult with symbols that need full processing
        """
        total_symbols = len(symbols)
        
        # Check which filters can be pre-filtered
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
            # Use a conservative estimate for pre-filtering
            # Assume minimum price of $1 for safety
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
        """
        Pre-filter symbols that have at least one day with OPEN price in range.
        
        This query finds symbols that have ANY day in the date range where
        the open price is within the specified range.
        """
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
        """
        Pre-filter symbols that have at least one day with volume above threshold.
        
        This is a conservative pre-filter that finds symbols with ANY day
        where volume exceeds the threshold. The actual filter will check
        the average volume.
        """
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
    
    async def get_precomputed_indicators(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch pre-computed indicators if available in the database.
        
        This can include pre-calculated MA values and RSI values
        for common periods.
        """
        query = """
        SELECT 
            time::date as date,
            open,
            close,
            ma_20,
            ma_50,
            ma_200,
            rsi_14
        FROM daily_bars
        WHERE symbol = $1
          AND time::date BETWEEN $2 AND $3
        ORDER BY time
        """
        
        # This is a placeholder - actual implementation would depend
        # on whether we store pre-computed indicators
        logger.debug(f"Pre-computed indicators not yet implemented for {symbol}")
        return None
    
    async def should_use_prefiltering(
        self,
        num_symbols: int,
        date_range_days: int
    ) -> bool:
        """
        Determine if pre-filtering would be beneficial based on data size.
        
        Pre-filtering has overhead, so it's only worth it for larger datasets.
        """
        # Estimate total data points
        estimated_data_points = num_symbols * date_range_days
        
        # Pre-filtering is beneficial for larger datasets
        # These thresholds can be tuned based on performance testing
        if estimated_data_points > 10000:  # e.g., 100 symbols * 100 days
            return True
        
        # For small datasets, loading everything might be faster
        return False


class OptimizedDataLoader:
    """
    Loads stock data with optimizations based on active filters.
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
        
        # Optimize query based on active filters
        query = self._build_optimized_query(filters)
        
        async with self.db_pool.acquire() as conn:
            rows = await conn.fetch(
                query,
                symbols_to_load,
                start_date,
                end_date
            )
        
        # Group by symbol
        data_by_symbol = {}
        for row in rows:
            symbol = row['symbol']
            if symbol not in data_by_symbol:
                data_by_symbol[symbol] = []
            data_by_symbol[symbol].append(dict(row))
        
        return data_by_symbol
    
    def _build_optimized_query(self, filters: SimpleFilters) -> str:
        """
        Build optimized query based on active filters.
        
        Only select columns needed for the active filters.
        """
        # Always need these columns
        select_cols = ['symbol', 'time::date as date', 'open', 'high', 'low', 'close', 'volume']
        
        # Add columns based on active filters
        if filters.price_vs_ma or filters.rsi:
            # These filters need close prices
            pass  # close already included
        
        # Price range only needs open (already included)
        
        # Could add pre-computed indicators if available
        # if filters.price_vs_ma and ma_period in [20, 50, 200]:
        #     select_cols.append(f'ma_{ma_period}')
        
        query = f"""
        SELECT {', '.join(select_cols)}
        FROM daily_bars
        WHERE symbol = ANY($1::text[])
          AND time::date BETWEEN $2 AND $3
        ORDER BY symbol, time
        """
        
        return query
    
    async def get_all_active_symbols(
        self,
        start_date: date,
        end_date: date,
        symbol_types: Optional[List[str]] = None
    ) -> List[str]:
        """
        Get all active symbols that have data in the specified date range.
        
        Args:
            start_date: Start date for data availability check
            end_date: End date for data availability check
            symbol_types: Optional list of symbol types to include (e.g., ['CS', 'ETF'])
                         Defaults to common stock and ETFs
        
        Returns:
            List of symbol strings that have data in the date range
        """
        if symbol_types is None:
            # Default to common stocks and ETFs, excluding ADRs and other types
            symbol_types = ['CS', 'ETF']
        
        query = """
        SELECT DISTINCT s.symbol
        FROM symbols s
        INNER JOIN daily_bars db ON s.symbol = db.symbol
        WHERE s.active = true
          AND s.type = ANY($1::text[])
          AND db.time::date BETWEEN $2 AND $3
          AND db.volume > 0  -- Ensure the stock actually traded
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