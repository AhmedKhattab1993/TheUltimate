"""
Service for fetching previous trading day data to support gap calculations.

This service handles the complexity of finding previous trading day data for gap calculations,
including handling weekends, holidays, and implementing efficient caching strategies.
"""

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Set, Any
import time
from collections import defaultdict

from .polygon_client import PolygonClient, PolygonAPIError
from app.models.stock import StockData, StockBar
from app.config import settings


logger = logging.getLogger(__name__)


class PreviousTradingDayService:
    """
    Service to fetch previous trading day closes for gap percentage calculations.
    
    This service provides both single and bulk operations for fetching previous trading day data,
    with intelligent caching and fallback mechanisms to handle weekends, holidays, and missing data.
    """
    
    def __init__(self, polygon_client: Optional[PolygonClient] = None):
        """
        Initialize the previous trading day service.
        
        Args:
            polygon_client: Optional PolygonClient instance. If not provided, creates one.
        """
        self.polygon_client = polygon_client
        self._should_close_client = polygon_client is None
        
        # Cache for previous trading day data
        # Structure: {date: {symbol: close_price}}
        self._previous_day_cache: Dict[date, Dict[str, float]] = {}
        self._cache_timestamps: Dict[date, float] = {}
        self.cache_ttl = settings.previous_day_cache_ttl
        
        # Cache for trading day mapping (date -> previous_trading_date)
        self._trading_day_cache: Dict[date, Optional[date]] = {}
        self.max_lookback_days = settings.max_previous_day_lookback
        
    async def __aenter__(self):
        """Async context manager entry"""
        if self.polygon_client is None:
            self.polygon_client = PolygonClient()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self._should_close_client and self.polygon_client:
            await self.polygon_client.close()
    
    def _is_cache_valid(self, target_date: date) -> bool:
        """Check if cached data for a date is still valid"""
        if target_date not in self._cache_timestamps:
            return False
        
        cache_timestamp = self._cache_timestamps[target_date]
        return time.time() - cache_timestamp < self.cache_ttl
    
    def _find_previous_trading_day(self, target_date: date, max_lookback_days: Optional[int] = None) -> Optional[date]:
        """
        Find the most likely previous trading day for a given date.
        
        This method uses heuristics to find the previous trading day:
        - Monday: looks back to Friday (3 days)
        - Tuesday-Friday: looks back 1 day
        - Weekend days: looks back to Friday
        
        Args:
            target_date: The date to find previous trading day for
            max_lookback_days: Maximum days to look back (uses config setting if None)
            
        Returns:
            Previous trading day date or None if not found
        """
        if max_lookback_days is None:
            max_lookback_days = self.max_lookback_days
        # Check cache first
        if target_date in self._trading_day_cache:
            return self._trading_day_cache[target_date]
        
        # Common US market holidays (basic set - in production would use a more comprehensive calendar)
        common_holidays = {
            # New Year's Day
            date(target_date.year, 1, 1),
            # Independence Day
            date(target_date.year, 7, 4),
            # Christmas Day
            date(target_date.year, 12, 25),
        }
        
        # Look back from the day before target_date
        current_date = target_date - timedelta(days=1)
        days_checked = 0
        
        while days_checked < max_lookback_days:
            # Skip weekends (Saturday = 5, Sunday = 6)
            if current_date.weekday() < 5 and current_date not in common_holidays:
                # This is likely a trading day
                self._trading_day_cache[target_date] = current_date
                return current_date
            
            current_date -= timedelta(days=1)
            days_checked += 1
        
        # If we couldn't find a reasonable previous trading day, cache None
        self._trading_day_cache[target_date] = None
        logger.warning(f"Could not find previous trading day for {target_date} within {max_lookback_days} days")
        return None
    
    async def get_previous_day_close(self, symbol: str, target_date: date) -> Optional[float]:
        """
        Get the previous trading day close price for a single symbol.
        
        Args:
            symbol: Stock symbol
            target_date: Date to get previous trading day close for
            
        Returns:
            Previous day close price or None if not available
        """
        # Check if we have cached data for this date
        if self._is_cache_valid(target_date) and target_date in self._previous_day_cache:
            return self._previous_day_cache[target_date].get(symbol)
        
        # Find the previous trading day
        previous_date = self._find_previous_trading_day(target_date)
        if not previous_date:
            return None
        
        try:
            # Fetch data for the previous trading day
            stock_data = await self.polygon_client.fetch_historical_data(
                symbol=symbol,
                start_date=previous_date,
                end_date=previous_date,
                adjusted=True
            )
            
            if stock_data.bars:
                close_price = stock_data.bars[0].close
                
                # Cache the result
                if target_date not in self._previous_day_cache:
                    self._previous_day_cache[target_date] = {}
                
                self._previous_day_cache[target_date][symbol] = close_price
                self._cache_timestamps[target_date] = time.time()
                
                return close_price
            
        except PolygonAPIError as e:
            logger.warning(f"Failed to fetch previous day close for {symbol} on {target_date}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error fetching previous day close for {symbol} on {target_date}: {e}")
        
        return None
    
    async def get_previous_day_closes_bulk(
        self, 
        symbols: List[str], 
        target_date: date,
        use_bulk_endpoint: bool = True
    ) -> Dict[str, Optional[float]]:
        """
        Get previous trading day close prices for multiple symbols efficiently.
        
        Args:
            symbols: List of stock symbols
            target_date: Date to get previous trading day closes for
            use_bulk_endpoint: Whether to use bulk endpoint for efficiency (default: True)
            
        Returns:
            Dictionary mapping symbol to previous day close price (None if not available)
        """
        results = {}
        
        # Check cache for any symbols we already have
        cached_symbols = set()
        if self._is_cache_valid(target_date) and target_date in self._previous_day_cache:
            for symbol in symbols:
                if symbol in self._previous_day_cache[target_date]:
                    results[symbol] = self._previous_day_cache[target_date][symbol]
                    cached_symbols.add(symbol)
        
        # Get symbols that need to be fetched
        symbols_to_fetch = [s for s in symbols if s not in cached_symbols]
        
        if not symbols_to_fetch:
            # All symbols were cached
            return results
        
        # Find the previous trading day
        previous_date = self._find_previous_trading_day(target_date)
        if not previous_date:
            # Return None for all symbols if we can't find previous trading day
            for symbol in symbols_to_fetch:
                results[symbol] = None
            return results
        
        try:
            if use_bulk_endpoint:
                # Try using bulk endpoint first (more efficient)
                logger.debug(f"Using bulk endpoint to fetch previous day data for {len(symbols_to_fetch)} symbols on {previous_date}")
                
                bulk_data = await self.polygon_client.fetch_bulk_historical_data_with_fallback(
                    symbols=symbols_to_fetch,
                    start_date=previous_date,
                    end_date=previous_date,
                    adjusted=True,
                    prefer_bulk=True
                )
                
                # Process bulk results
                fetched_symbols = set()
                for symbol, stock_data in bulk_data.items():
                    if stock_data.bars:
                        close_price = stock_data.bars[0].close
                        results[symbol] = close_price
                        fetched_symbols.add(symbol)
                        
                        # Cache the result
                        if target_date not in self._previous_day_cache:
                            self._previous_day_cache[target_date] = {}
                        self._previous_day_cache[target_date][symbol] = close_price
                
                # Handle symbols that weren't found in bulk data
                missing_symbols = set(symbols_to_fetch) - fetched_symbols
                for symbol in missing_symbols:
                    results[symbol] = None
                
            else:
                # Fallback to individual requests
                logger.debug(f"Using individual requests to fetch previous day data for {len(symbols_to_fetch)} symbols")
                
                tasks = []
                for symbol in symbols_to_fetch:
                    task = self.get_previous_day_close(symbol, target_date)
                    tasks.append((symbol, task))
                
                # Execute all tasks concurrently
                for symbol, task in tasks:
                    try:
                        close_price = await task
                        results[symbol] = close_price
                    except Exception as e:
                        logger.warning(f"Failed to fetch previous day close for {symbol}: {e}")
                        results[symbol] = None
            
            # Update cache timestamp
            self._cache_timestamps[target_date] = time.time()
            
        except Exception as e:
            logger.error(f"Error in bulk fetch for previous day closes: {e}")
            # Return None for all unfetched symbols
            for symbol in symbols_to_fetch:
                if symbol not in results:
                    results[symbol] = None
        
        return results
    
    async def get_multiple_previous_day_closes(
        self, 
        symbol_dates: List[tuple[str, date]]
    ) -> Dict[tuple[str, date], Optional[float]]:
        """
        Get previous day closes for multiple symbol-date combinations efficiently.
        
        This method is optimized for scenarios where you need previous day data
        for different symbols on different dates.
        
        Args:
            symbol_dates: List of (symbol, date) tuples
            
        Returns:
            Dictionary mapping (symbol, date) tuple to previous day close price
        """
        results = {}
        
        # Group by date for efficient batch processing
        date_to_symbols = defaultdict(list)
        for symbol, target_date in symbol_dates:
            date_to_symbols[target_date].append(symbol)
        
        # Process each date group
        for target_date, symbols in date_to_symbols.items():
            try:
                date_results = await self.get_previous_day_closes_bulk(symbols, target_date)
                
                # Map results back to the original (symbol, date) keys
                for symbol in symbols:
                    results[(symbol, target_date)] = date_results.get(symbol)
                    
            except Exception as e:
                logger.error(f"Error fetching previous day closes for date {target_date}: {e}")
                # Set None for all symbols on this date
                for symbol in symbols:
                    results[(symbol, target_date)] = None
        
        return results
    
    def clear_cache(self):
        """Clear all cached data"""
        self._previous_day_cache.clear()
        self._cache_timestamps.clear()
        self._trading_day_cache.clear()
        logger.info("Previous trading day service cache cleared")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics for monitoring"""
        return {
            'cached_dates': len(self._previous_day_cache),
            'cached_trading_day_mappings': len(self._trading_day_cache),
            'total_cached_symbols': sum(len(symbols) for symbols in self._previous_day_cache.values()),
            'cache_ttl_seconds': self.cache_ttl
        }


# Example usage and testing
async def example_usage():
    """Example of how to use the PreviousTradingDayService"""
    
    async with PreviousTradingDayService() as service:
        target_date = date(2024, 1, 2)  # A Tuesday
        
        # Single symbol
        aapl_prev_close = await service.get_previous_day_close("AAPL", target_date)
        print(f"AAPL previous close for {target_date}: {aapl_prev_close}")
        
        # Multiple symbols
        symbols = ["AAPL", "MSFT", "GOOGL"]
        bulk_results = await service.get_previous_day_closes_bulk(symbols, target_date)
        print(f"Bulk results for {target_date}: {bulk_results}")
        
        # Multiple symbol-date combinations
        symbol_dates = [
            ("AAPL", date(2024, 1, 2)),
            ("MSFT", date(2024, 1, 3)),
            ("GOOGL", date(2024, 1, 2))
        ]
        multi_results = await service.get_multiple_previous_day_closes(symbol_dates)
        print(f"Multi results: {multi_results}")
        
        # Cache stats
        stats = service.get_cache_stats()
        print(f"Cache stats: {stats}")


if __name__ == "__main__":
    # For testing purposes
    asyncio.run(example_usage())