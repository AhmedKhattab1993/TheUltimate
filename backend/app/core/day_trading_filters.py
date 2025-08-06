"""
Day trading specific filters for stock screening using numpy vectorization.

This module provides high-performance filter implementations specifically designed
for day trading strategies, focusing on gap moves, volume patterns, and price action.
"""

from typing import Dict, Any, Optional, List, Tuple, Callable, Awaitable
import numpy as np
from datetime import date, datetime, time
import logging
import asyncio

from .filters import BaseFilter, FilterResult


logger = logging.getLogger(__name__)


class GapFilter(BaseFilter):
    """
    Filter stocks based on gap percentage from previous day's close.
    
    A gap occurs when a stock opens significantly higher or lower than the
    previous day's close. This filter identifies stocks with gaps exceeding
    a specified threshold.
    
    Enhanced version supports fetching missing previous day data for single-date requests.
    """
    
    def __init__(self, min_gap_percent: float, max_gap_percent: Optional[float] = None, 
                 name: str = "GapFilter", 
                 previous_day_fetcher: Optional[Callable[[str, date], Awaitable[Optional[float]]]] = None,
                 enable_async_fetch: bool = False):
        """
        Initialize gap filter.
        
        Args:
            min_gap_percent: Minimum gap percentage (e.g., 4.0 for 4%)
            max_gap_percent: Optional maximum gap percentage
            name: Optional name for the filter
            previous_day_fetcher: Optional async function to fetch previous day close prices
            enable_async_fetch: Whether to enable async fetching of missing previous day data
        """
        super().__init__(name)
        if min_gap_percent < 0:
            raise ValueError(f"min_gap_percent must be >= 0, got {min_gap_percent}")
        if max_gap_percent is not None and max_gap_percent < min_gap_percent:
            raise ValueError(f"max_gap_percent must be >= min_gap_percent")
        
        self.min_gap_percent = min_gap_percent
        self.max_gap_percent = max_gap_percent
        self.previous_day_fetcher = previous_day_fetcher
        self.enable_async_fetch = enable_async_fetch
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply gap filter using vectorized operations."""
        self._validate_data(data, min_length=1)  # Reduced minimum length for single-day support
        
        opens = data['open'].astype(np.float64)
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate gap percentage using available data
        gap_percents = np.full_like(opens, np.nan)
        
        if len(data) >= 2:
            # Multi-day data: use vectorized operations as before
            gap_percents[1:] = ((opens[1:] - closes[:-1]) / closes[:-1]) * 100
        elif len(data) == 1 and self.enable_async_fetch and self.previous_day_fetcher:
            # Single-day data: mark for async processing
            # We'll handle this in apply_async method
            pass
        
        # Create mask for qualifying dates
        qualifying_mask = ~np.isnan(gap_percents) & (gap_percents >= self.min_gap_percent)
        if self.max_gap_percent is not None:
            qualifying_mask &= (gap_percents <= self.max_gap_percent)
        
        # Calculate metrics
        valid_gaps = gap_percents[~np.isnan(gap_percents)]
        metrics = {
            'gap_percent_mean': float(np.mean(valid_gaps)) if len(valid_gaps) > 0 else 0.0,
            'gap_percent_max': float(np.max(valid_gaps)) if len(valid_gaps) > 0 else 0.0,
            'gap_percent_min': float(np.min(valid_gaps)) if len(valid_gaps) > 0 else 0.0,
            'gap_days_count': int(np.sum(qualifying_mask)),
            'requires_async_processing': len(data) == 1 and self.enable_async_fetch and self.previous_day_fetcher is not None,
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    async def apply_async(self, data: np.ndarray, symbol: str) -> FilterResult:
        """
        Apply gap filter with async support for fetching missing previous day data.
        
        This method is used when we have single-day data and need to fetch
        the previous trading day close price to calculate the gap.
        """
        self._validate_data(data, min_length=1)
        
        opens = data['open'].astype(np.float64)
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        gap_percents = np.full_like(opens, np.nan)
        
        if len(data) >= 2:
            # Multi-day data: use vectorized operations
            gap_percents[1:] = ((opens[1:] - closes[:-1]) / closes[:-1]) * 100
        elif len(data) == 1 and self.previous_day_fetcher:
            # Single-day data: fetch previous day close
            try:
                # Convert numpy date to Python date for API call
                target_date = dates[0].astype('datetime64[D]').astype(date)
                previous_close = await self.previous_day_fetcher(symbol, target_date)
                
                if previous_close is not None:
                    # Calculate gap for the single day
                    gap_percent = ((opens[0] - previous_close) / previous_close) * 100
                    gap_percents[0] = gap_percent
                    logger.debug(f"Calculated gap for {symbol} on {target_date}: {gap_percent:.2f}%")
                else:
                    logger.warning(f"Could not fetch previous day close for {symbol} on {target_date}")
                    
            except Exception as e:
                logger.error(f"Error fetching previous day data for {symbol}: {e}")
        
        # Create mask for qualifying dates
        qualifying_mask = ~np.isnan(gap_percents) & (gap_percents >= self.min_gap_percent)
        if self.max_gap_percent is not None:
            qualifying_mask &= (gap_percents <= self.max_gap_percent)
        
        # Calculate metrics
        valid_gaps = gap_percents[~np.isnan(gap_percents)]
        metrics = {
            'gap_percent_mean': float(np.mean(valid_gaps)) if len(valid_gaps) > 0 else 0.0,
            'gap_percent_max': float(np.max(valid_gaps)) if len(valid_gaps) > 0 else 0.0,
            'gap_percent_min': float(np.min(valid_gaps)) if len(valid_gaps) > 0 else 0.0,
            'gap_days_count': int(np.sum(qualifying_mask)),
            'async_processing_used': True,
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


class PriceRangeFilter(BaseFilter):
    """
    Filter stocks within a specific price range.
    
    Day traders often prefer stocks within certain price ranges for
    better risk/reward ratios and liquidity.
    """
    
    def __init__(self, min_price: float, max_price: float, name: str = "PriceRangeFilter"):
        """
        Initialize price range filter.
        
        Args:
            min_price: Minimum stock price
            max_price: Maximum stock price
            name: Optional name for the filter
        """
        super().__init__(name)
        if min_price < 0:
            raise ValueError(f"min_price must be >= 0, got {min_price}")
        if max_price < min_price:
            raise ValueError(f"max_price must be >= min_price")
        
        self.min_price = min_price
        self.max_price = max_price
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply price range filter using vectorized operations."""
        self._validate_data(data)
        
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Create mask for qualifying dates
        qualifying_mask = (closes >= self.min_price) & (closes <= self.max_price)
        
        # Calculate metrics
        metrics = {
            'avg_price': float(np.mean(closes)),
            'price_volatility': float(np.std(closes)),
            'days_in_range': int(np.sum(qualifying_mask)),
            'percent_days_in_range': float((np.sum(qualifying_mask) / len(closes)) * 100),
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


class RelativeVolumeFilter(BaseFilter):
    """
    Filter stocks based on relative volume compared to average.
    
    High relative volume indicates increased interest and liquidity,
    which is crucial for day trading.
    """
    
    def __init__(self, min_relative_volume: float, lookback_days: int = 20,
                 name: str = "RelativeVolumeFilter"):
        """
        Initialize relative volume filter.
        
        Args:
            min_relative_volume: Minimum relative volume ratio (e.g., 2.0 for 2x average)
            lookback_days: Number of days to calculate average volume
            name: Optional name for the filter
        """
        super().__init__(name)
        if min_relative_volume < 1.0:
            raise ValueError(f"min_relative_volume must be >= 1.0, got {min_relative_volume}")
        if lookback_days < 5:
            raise ValueError(f"lookback_days must be >= 5, got {lookback_days}")
        
        self.min_relative_volume = min_relative_volume
        self.lookback_days = lookback_days
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply relative volume filter using vectorized operations."""
        self._validate_data(data, min_length=self.lookback_days + 1)
        
        volumes = data['volume'].astype(np.float64)
        dates = data['date']
        
        # Calculate rolling average volume
        kernel = np.ones(self.lookback_days) / self.lookback_days
        avg_volumes_valid = np.convolve(volumes, kernel, mode='valid')
        
        # Align arrays - pad beginning with NaN
        avg_volumes = np.full_like(volumes, np.nan)
        avg_volumes[self.lookback_days - 1:] = avg_volumes_valid
        
        # Calculate relative volume
        relative_volumes = np.full_like(volumes, np.nan)
        mask = avg_volumes > 0  # Avoid division by zero
        relative_volumes[mask] = volumes[mask] / avg_volumes[mask]
        
        # Create mask for qualifying dates
        qualifying_mask = (~np.isnan(relative_volumes) & 
                          (relative_volumes >= self.min_relative_volume))
        
        # Calculate metrics
        valid_rel_vols = relative_volumes[~np.isnan(relative_volumes)]
        metrics = {
            'relative_volume_mean': float(np.mean(valid_rel_vols)) if len(valid_rel_vols) > 0 else 0.0,
            'relative_volume_max': float(np.max(valid_rel_vols)) if len(valid_rel_vols) > 0 else 0.0,
            'high_relative_volume_days': int(np.sum(qualifying_mask)),
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


class FloatFilter(BaseFilter):
    """
    Filter stocks based on share float (shares available for trading).
    
    Lower float stocks tend to have more volatile price movements,
    which can be beneficial for day trading.
    """
    
    def __init__(self, max_float: float, name: str = "FloatFilter"):
        """
        Initialize float filter.
        
        Args:
            max_float: Maximum acceptable float
            name: Optional name for the filter
        """
        super().__init__(name)
        if max_float <= 0:
            raise ValueError(f"max_float must be > 0, got {max_float}")
        
        self.max_float = max_float
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """
        Apply float filter.
        
        Note: This filter requires float data to be available in the data structure.
        For now, it returns a placeholder implementation that should be updated
        when float data is integrated.
        """
        self._validate_data(data)
        
        dates = data['date']
        
        # TODO: Implement actual float filtering when float data is available
        # For now, return all True to not filter anything
        qualifying_mask = np.ones(len(dates), dtype=bool)
        
        logger.warning(f"FloatFilter not fully implemented for {symbol} - float data not available")
        
        metrics = {
            'float_filter_applied': False,
            'max_float_threshold': self.max_float
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


# NOTE: PreMarketVolumeFilter is commented out as it requires intraday data which is not currently available
# class PreMarketVolumeFilter(BaseFilter):
#     """
#     Filter stocks based on pre-market trading volume.
#     
#     High pre-market volume indicates early interest and potential
#     momentum for the trading day.
#     """
#     
#     def __init__(self, min_volume: int, cutoff_time: str = "09:00",
#                  name: str = "PreMarketVolumeFilter"):
#         """
#         Initialize pre-market volume filter.
#         
#         Args:
#             min_volume: Minimum pre-market volume
#             cutoff_time: Time cutoff for pre-market volume (HH:MM format)
#             name: Optional name for the filter
#         """
#         super().__init__(name)
#         if min_volume < 0:
#             raise ValueError(f"min_volume must be >= 0, got {min_volume}")
#         
#         self.min_volume = min_volume
#         self.cutoff_time = cutoff_time
#     
#     def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
#         """
#         Apply pre-market volume filter.
#         
#         Note: This filter requires intraday data to properly calculate
#         pre-market volume. Current implementation is a placeholder.
#         """
#         self._validate_data(data)
#         
#         dates = data['date']
#         
#         # TODO: Implement actual pre-market volume filtering when intraday data is available
#         # For now, return all True to not filter anything
#         qualifying_mask = np.ones(len(dates), dtype=bool)
#         
#         logger.warning(f"PreMarketVolumeFilter not fully implemented for {symbol} - intraday data not available")
#         
#         metrics = {
#             'premarket_filter_applied': False,
#             'min_volume_threshold': self.min_volume,
#             'cutoff_time': self.cutoff_time,
#         }
#         
#         return FilterResult(
#             symbol=symbol,
#             qualifying_mask=qualifying_mask,
#             dates=dates,
#             metrics=metrics
#         )


class MarketCapFilter(BaseFilter):
    """
    Filter stocks based on market capitalization.
    
    Small-cap stocks often provide better day trading opportunities
    due to higher volatility and momentum potential.
    """
    
    def __init__(self, max_market_cap: float, min_market_cap: Optional[float] = None,
                 name: str = "MarketCapFilter"):
        """
        Initialize market cap filter.
        
        Args:
            max_market_cap: Maximum market capitalization
            min_market_cap: Optional minimum market capitalization
            name: Optional name for the filter
        """
        super().__init__(name)
        if max_market_cap <= 0:
            raise ValueError(f"max_market_cap must be > 0, got {max_market_cap}")
        if min_market_cap is not None:
            if min_market_cap < 0:
                raise ValueError(f"min_market_cap must be >= 0, got {min_market_cap}")
            if min_market_cap >= max_market_cap:
                raise ValueError("min_market_cap must be < max_market_cap")
        
        self.max_market_cap = max_market_cap
        self.min_market_cap = min_market_cap
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """
        Apply market cap filter.
        
        Note: This filter requires market cap data or shares outstanding data
        to be available. Current implementation is a placeholder.
        """
        self._validate_data(data)
        
        dates = data['date']
        
        # TODO: Implement actual market cap filtering when market cap data is available
        # For now, return all True to not filter anything
        qualifying_mask = np.ones(len(dates), dtype=bool)
        
        logger.warning(f"MarketCapFilter not fully implemented for {symbol} - market cap data not available")
        
        metrics = {
            'market_cap_filter_applied': False,
            'max_market_cap_threshold': self.max_market_cap,
            'min_market_cap_threshold': self.min_market_cap,
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


# NOTE: NewsCatalystFilter is commented out as it requires news data integration which is not currently available
# class NewsCatalystFilter(BaseFilter):
#     """
#     Filter stocks based on recent news catalyst.
#     
#     Fresh news can drive significant price movements and volume,
#     making stocks ideal for day trading.
#     """
#     
#     def __init__(self, hours_lookback: int = 24, require_news: bool = True,
#                  name: str = "NewsCatalystFilter"):
#         """
#         Initialize news catalyst filter.
#         
#         Args:
#             hours_lookback: Hours to look back for news
#             require_news: Whether to require news for qualification
#             name: Optional name for the filter
#         """
#         super().__init__(name)
#         if hours_lookback < 1:
#             raise ValueError(f"hours_lookback must be >= 1, got {hours_lookback}")
#         
#         self.hours_lookback = hours_lookback
#         self.require_news = require_news
#     
#     def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
#         """
#         Apply news catalyst filter.
#         
#         Note: This filter requires news data integration. Current implementation
#         is a placeholder.
#         """
#         self._validate_data(data)
#         
#         dates = data['date']
#         
#         # TODO: Implement actual news filtering when news data is available
#         # For now, return all True if not requiring news, all False if requiring
#         if self.require_news:
#             qualifying_mask = np.zeros(len(dates), dtype=bool)
#             logger.warning(f"NewsCatalystFilter blocking all dates for {symbol} - news data not available")
#         else:
#             qualifying_mask = np.ones(len(dates), dtype=bool)
#         
#         metrics = {
#             'news_filter_applied': False,
#             'hours_lookback': self.hours_lookback,
#             'require_news': self.require_news,
#         }
#         
#         return FilterResult(
#             symbol=symbol,
#             qualifying_mask=qualifying_mask,
#             dates=dates,
#             metrics=metrics
#         )


class DayTradingCompositeFilter(BaseFilter):
    """
    Specialized composite filter for day trading that combines multiple filters
    with optimized logic for day trading scenarios.
    """
    
    def __init__(self, filters: List[BaseFilter], name: str = "DayTradingComposite"):
        """
        Initialize day trading composite filter.
        
        Args:
            filters: List of filters to combine
            name: Optional name for the filter
        """
        super().__init__(name)
        self.filters = filters
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply all filters with day trading optimizations."""
        if not self.filters:
            return FilterResult(
                symbol=symbol,
                qualifying_mask=np.ones(len(data), dtype=bool),
                dates=data['date'],
                metrics={}
            )
        
        # Apply first filter
        result = self.filters[0].apply(data, symbol)
        
        # Combine with remaining filters
        for filter in self.filters[1:]:
            filter_result = filter.apply(data, symbol)
            result = result.combine_with(filter_result)
        
        # Add composite metrics
        result.metrics['total_filters_applied'] = len(self.filters)
        result.metrics['filter_names'] = [f.name for f in self.filters]
        
        return result