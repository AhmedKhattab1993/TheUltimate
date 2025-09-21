"""
Simple and efficient filters for stock screening.

This module provides filters that replace the complex filter system:
1. SimplePriceRangeFilter - Filter by OPEN price range
2. PriceVsMAFilter - Compare OPEN price to moving average
3. RSIFilter - Standard RSI calculation with threshold
4. MinAverageVolumeFilter - Filter by minimum average volume
5. MinAverageDollarVolumeFilter - Filter by minimum average dollar volume
6. GapFilter - Filter by gap between open and previous close
7. PreviousDayDollarVolumeFilter - Filter by previous day's dollar volume
8. RelativeVolumeFilter - Filter by relative volume ratio

All filters are fully vectorized using NumPy and support database pre-filtering where applicable.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import numpy as np
import logging

from app.models.simple_requests import NumericRange

@dataclass
class FilterResult:
    """Result from applying a filter."""
    symbol: str
    qualifying_mask: np.ndarray
    dates: np.ndarray
    metrics: Dict[str, Any]
    metadata: Optional[Dict[str, Any]] = None
    
    @property
    def num_qualifying_days(self) -> int:
        """Number of days that passed the filter."""
        return int(np.sum(self.qualifying_mask))
    
    @property
    def qualifying_dates(self) -> np.ndarray:
        """Get dates that passed the filter."""
        return self.dates[self.qualifying_mask]
    
    def combine_with(self, other: 'FilterResult') -> 'FilterResult':
        """Combine this result with another using AND logic."""
        if self.symbol != other.symbol:
            raise ValueError(f"Cannot combine results for different symbols: {self.symbol} vs {other.symbol}")
        
        # Combine masks using AND
        combined_mask = self.qualifying_mask & other.qualifying_mask
        
        # Merge metrics
        combined_metrics = {**self.metrics, **other.metrics}
        
        return FilterResult(
            symbol=self.symbol,
            qualifying_mask=combined_mask,
            dates=self.dates,
            metrics=combined_metrics,
            metadata={**(self.metadata or {}), **(other.metadata or {})}
        )
    
class EnhancedBaseFilter:
    """Base class for enhanced filters."""
    
    def get_required_lookback_days(self) -> int:
        """Get number of lookback days required."""
        return 252  # Default to 1 year
    
    def get_required_fields(self) -> List[str]:
        """Get required data fields."""
        return ['open', 'high', 'low', 'close', 'volume']
    
    def _validate_data(self, data: np.ndarray, min_length: int = 1) -> None:
        """Validate input data."""
        if data is None or len(data) < min_length:
            raise ValueError(f"Insufficient data: need at least {min_length} days")
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply the filter to data."""
        raise NotImplementedError

@dataclass
class DatabasePreFilter:
    """Lightweight descriptor for database pre-filtering clauses."""

    where_conditions: List[str]

logger = logging.getLogger(__name__)


def _range_mask(values: np.ndarray, numeric_range: NumericRange) -> np.ndarray:
    """Create a boolean mask selecting entries that fall inside ``numeric_range``."""

    mask = ~np.isnan(values)
    if numeric_range.min is not None:
        mask &= values >= numeric_range.min
    if numeric_range.max is not None:
        mask &= values <= numeric_range.max
    return mask


class SimplePriceRangeFilter(EnhancedBaseFilter):
    """Filter stocks based on OPEN price within a numeric range."""

    def __init__(
        self,
        price_range: NumericRange,
        name: str = "SimplePriceRangeFilter",
    ) -> None:
        if price_range.min is not None and price_range.min < 0:
            raise ValueError(f"open_price.min must be >= 0, got {price_range.min}")
        if price_range.max is not None and price_range.max < 0:
            raise ValueError(f"open_price.max must be >= 0, got {price_range.max}")

        self.name = name
        self.price_range = price_range
    
    def get_required_lookback_days(self) -> int:
        """Price range filter only needs current day data."""
        return 0  # No historical data needed
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply price range filter using OPEN prices."""
        self._validate_data(data)
        
        opens = data['open'].astype(np.float64)
        dates = data['date']
        
        # Create mask for qualifying dates based on OPEN price
        qualifying_mask = _range_mask(opens, self.price_range)
        
        # Calculate metrics
        metrics = {
            'avg_open_price': float(np.mean(opens)),
            'open_price_std': float(np.std(opens)),
            'days_in_range': int(np.sum(qualifying_mask)),
            'percent_days_in_range': float((np.sum(qualifying_mask) / len(opens)) * 100),
            'min_open_seen': float(np.min(opens)),
            'max_open_seen': float(np.max(opens))
        }

        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )

    def get_database_prefilter(self) -> Optional[DatabasePreFilter]:
        """Generate database WHERE clause for pre-filtering."""
        conditions: List[str] = []
        if self.price_range.min is not None:
            conditions.append(f"open >= {self.price_range.min}")
        if self.price_range.max is not None:
            conditions.append(f"open <= {self.price_range.max}")

        return DatabasePreFilter(where_conditions=conditions) if conditions else None


class PriceVsMAFilter(EnhancedBaseFilter):
    """Filter stocks whose OPEN/MA ratio falls inside a target range."""

    def __init__(
        self,
        period: int,
        ratio_range: NumericRange,
        name: str = "PriceVsMAFilter",
    ) -> None:
        self.name = name
        if period not in [20, 50, 200]:
            raise ValueError(f"period must be 20, 50, or 200, got {period}")

        self.period = period
        self.ratio_range = ratio_range
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply price vs MA filter using vectorized operations."""
        # Don't enforce strict validation - work with the data we have
        self._validate_data(data, min_length=1)
        
        opens = data['open'].astype(np.float64)
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate MA from previous closes (excluding current day)
        # Uses as much history as is available, up to the desired period.
        ma_values = np.full_like(closes, np.nan)
        window_lengths = np.zeros(len(closes), dtype=np.int32)

        for i in range(1, len(closes)):
            window_start = max(0, i - self.period)
            window = closes[window_start:i]
            if window.size == 0:
                continue
            ma_values[i] = float(np.mean(window))
            window_lengths[i] = window.size
        
        ratios = np.full_like(opens, np.nan)
        valid_ma_mask = (~np.isnan(ma_values)) & (ma_values != 0)
        ratios[valid_ma_mask] = opens[valid_ma_mask] / ma_values[valid_ma_mask]

        qualifying_mask = _range_mask(ratios, self.ratio_range)

        # Calculate metrics
        valid_mas = ma_values[~np.isnan(ma_values)]
        valid_ratios = ratios[~np.isnan(ratios)]

        if len(valid_mas) > 0:
            distance_from_ma = ((opens[~np.isnan(ma_values)] - valid_mas) / valid_mas) * 100
            valid_lengths = window_lengths[window_lengths > 0]
            metrics = {
                f'ma_{self.period}_mean': float(np.mean(valid_mas)),
                f'distance_from_ma_{self.period}_mean': float(np.mean(distance_from_ma)),
                f'distance_from_ma_{self.period}_std': float(np.std(distance_from_ma)),
                'open_over_ma_mean': float(np.mean(valid_ratios)) if len(valid_ratios) > 0 else 0.0,
                'open_over_ma_std': float(np.std(valid_ratios)) if len(valid_ratios) > 0 else 0.0,
                'qualifying_days': int(np.sum(qualifying_mask)),
                'total_days_with_ma': int(len(valid_mas)),
                'ma_effective_window_min': int(valid_lengths.min()) if len(valid_lengths) > 0 else 0,
                'ma_effective_window_max': int(valid_lengths.max()) if len(valid_lengths) > 0 else 0,
            }
        else:
            metrics = {
                f'ma_{self.period}_mean': 0.0,
                f'distance_from_ma_{self.period}_mean': 0.0,
                f'distance_from_ma_{self.period}_std': 0.0,
                'open_over_ma_mean': 0.0,
                'open_over_ma_std': 0.0,
                'qualifying_days': 0,
                'total_days_with_ma': 0,
                'ma_effective_window_min': 0,
                'ma_effective_window_max': 0,
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for MA calculation."""
        return self.period


class RSIFilter(EnhancedBaseFilter):
    """Filter stocks whose RSI falls inside a numeric range."""

    def __init__(
        self,
        period: int = 14,
        rsi_range: NumericRange | None = None,
        name: str = "RSIFilter",
    ) -> None:
        self.name = name
        if period < 2:
            raise ValueError(f"period must be >= 2, got {period}")

        self.period = period
        self.rsi_range = rsi_range or NumericRange(max=30.0)
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply RSI filter using Wilder's method."""
        # Don't enforce strict validation - work with the data we have
        self._validate_data(data, min_length=1)
        
        # If we don't have enough data for RSI, return empty result
        if len(data) <= self.period:
            return FilterResult(
                symbol=symbol,
                qualifying_mask=np.zeros(len(data), dtype=bool),
                dates=data['date'],
                metrics={'error': f'Insufficient data for {self.period}-period RSI'}
            )
        
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate price changes
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)
        
        # Calculate RSI using Wilder's method
        rsi_values = np.full_like(closes, np.nan)
        
        # Need at least period + 1 prices to calculate RSI
        if len(closes) > self.period:
            # Initial averages (simple moving average)
            avg_gain = np.mean(gains[:self.period])
            avg_loss = np.mean(losses[:self.period])
            
            # Calculate initial RSI
            if avg_loss != 0:
                rs = avg_gain / avg_loss
                rsi_values[self.period] = 100 - (100 / (1 + rs))
            else:
                rsi_values[self.period] = 100
            
            # Calculate subsequent RSI values using Wilder's smoothing
            for i in range(self.period + 1, len(closes)):
                # Wilder's smoothing method
                avg_gain = (avg_gain * (self.period - 1) + gains[i-1]) / self.period
                avg_loss = (avg_loss * (self.period - 1) + losses[i-1]) / self.period
                
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    rsi_values[i] = 100 - (100 / (1 + rs))
                else:
                    rsi_values[i] = 100
        
        qualifying_mask = _range_mask(rsi_values, self.rsi_range)
        
        # Calculate metrics
        valid_rsi = rsi_values[~np.isnan(rsi_values)]
        metrics = {
            'rsi_mean': float(np.mean(valid_rsi)) if len(valid_rsi) > 0 else 0.0,
            'rsi_std': float(np.std(valid_rsi)) if len(valid_rsi) > 0 else 0.0,
            'rsi_min': float(np.min(valid_rsi)) if len(valid_rsi) > 0 else 0.0,
            'rsi_max': float(np.max(valid_rsi)) if len(valid_rsi) > 0 else 0.0,
            'days_qualifying': int(np.sum(qualifying_mask)),
            'percent_days_qualifying': float((np.sum(qualifying_mask) / len(closes)) * 100)
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for RSI calculation."""
        # Need extra days for price change calculation
        return self.period + 1


class MinAverageVolumeFilter(EnhancedBaseFilter):
    """Filter stocks based on rolling average trading volume."""

    def __init__(
        self,
        lookback_days: int = 20,
        volume_range: NumericRange | None = None,
        name: str = "MinAverageVolumeFilter",
    ) -> None:
        self.name = name
        if lookback_days < 1:
            raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")

        self.lookback_days = lookback_days
        self.volume_range = volume_range or NumericRange(min=1_000_000)
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply minimum average volume filter using vectorized operations."""
        self._validate_data(data)
        
        volumes = data['volume'].astype(np.float64)
        dates = data['date']
        
        # Calculate rolling average volume
        avg_volumes = np.full_like(volumes, np.nan)
        
        # Need at least lookback_days of data to calculate average
        for i in range(self.lookback_days - 1, len(volumes)):
            # Calculate average volume for the past lookback_days including current day
            avg_volumes[i] = np.mean(volumes[i-self.lookback_days+1:i+1])
        
        # Create mask for days where average volume meets minimum
        qualifying_mask = _range_mask(avg_volumes, self.volume_range)
        
        # Calculate metrics
        valid_avg_volumes = avg_volumes[~np.isnan(avg_volumes)]
        
        if len(valid_avg_volumes) > 0:
            metrics = {
                'avg_volume_mean': float(np.mean(valid_avg_volumes)),
                'avg_volume_std': float(np.std(valid_avg_volumes)),
                'avg_volume_min': float(np.min(valid_avg_volumes)),
                'avg_volume_max': float(np.max(valid_avg_volumes)),
                'days_above_threshold': int(np.sum(qualifying_mask)),
                'percent_days_above_threshold': float((np.sum(qualifying_mask) / len(volumes)) * 100)
            }
        else:
            metrics = {
                'avg_volume_mean': 0.0,
                'avg_volume_std': 0.0,
                'avg_volume_min': 0.0,
                'avg_volume_max': 0.0,
                'days_above_threshold': 0,
                'percent_days_above_threshold': 0.0
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_database_prefilter(self) -> Optional[DatabasePreFilter]:
        """Generate database WHERE clause for pre-filtering."""
        if self.volume_range.min is None:
            return None

        return DatabasePreFilter(
            where_conditions=[
                f"volume >= {self.volume_range.min}"
            ]
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for average calculation."""
        return self.lookback_days


class MinAverageDollarVolumeFilter(EnhancedBaseFilter):
    """Filter stocks based on rolling average dollar volume (price * volume)."""

    def __init__(
        self,
        lookback_days: int = 20,
        dollar_volume_range: NumericRange | None = None,
        name: str = "MinAverageDollarVolumeFilter",
    ) -> None:
        self.name = name
        if lookback_days < 1:
            raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")

        self.lookback_days = lookback_days
        self.dollar_volume_range = dollar_volume_range or NumericRange(min=10_000_000)
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply minimum average dollar volume filter using vectorized operations."""
        self._validate_data(data)
        
        volumes = data['volume'].astype(np.float64)
        dates = data['date']
        
        # Use VWAP if available, otherwise use close price
        if 'vwap' in data.dtype.names:
            prices = data['vwap'].astype(np.float64)
            # Handle cases where VWAP might be 0 or NaN
            close_prices = data['close'].astype(np.float64)
            prices = np.where((prices > 0) & ~np.isnan(prices), prices, close_prices)
        else:
            prices = data['close'].astype(np.float64)
        
        # Calculate dollar volume for each day
        dollar_volumes = volumes * prices
        
        # Calculate rolling average dollar volume
        avg_dollar_volumes = np.full_like(dollar_volumes, np.nan)
        
        # Need at least lookback_days of data to calculate average
        for i in range(self.lookback_days - 1, len(dollar_volumes)):
            # Calculate average dollar volume for the past lookback_days including current day
            avg_dollar_volumes[i] = np.mean(dollar_volumes[i-self.lookback_days+1:i+1])
        
        # Create mask for days where average dollar volume meets minimum
        qualifying_mask = _range_mask(avg_dollar_volumes, self.dollar_volume_range)
        
        # Calculate metrics
        valid_avg_dollar_volumes = avg_dollar_volumes[~np.isnan(avg_dollar_volumes)]
        
        if len(valid_avg_dollar_volumes) > 0:
            metrics = {
                'avg_dollar_volume_mean': float(np.mean(valid_avg_dollar_volumes)),
                'avg_dollar_volume_std': float(np.std(valid_avg_dollar_volumes)),
                'avg_dollar_volume_min': float(np.min(valid_avg_dollar_volumes)),
                'avg_dollar_volume_max': float(np.max(valid_avg_dollar_volumes)),
                'days_above_threshold': int(np.sum(qualifying_mask)),
                'percent_days_above_threshold': float((np.sum(qualifying_mask) / len(dollar_volumes)) * 100)
            }
        else:
            metrics = {
                'avg_dollar_volume_mean': 0.0,
                'avg_dollar_volume_std': 0.0,
                'avg_dollar_volume_min': 0.0,
                'avg_dollar_volume_max': 0.0,
                'days_above_threshold': 0,
                'percent_days_above_threshold': 0.0
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_database_prefilter(self) -> Optional[DatabasePreFilter]:
        """Generate database WHERE clause for pre-filtering."""
        if self.dollar_volume_range.min is None:
            return None

        min_volume_estimate = self.dollar_volume_range.min / 100  # Assuming avg price of $100
        return DatabasePreFilter(where_conditions=[f"volume >= {min_volume_estimate}"])
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for average calculation."""
        return self.lookback_days


class GapFilter(EnhancedBaseFilter):
    """Filter stocks based on the opening gap percentage."""

    def __init__(
        self,
        gap_range: NumericRange,
        direction: str = "both",
        name: str = "GapFilter",
    ) -> None:
        self.name = name
        if direction not in {"up", "down", "both"}:
            raise ValueError("direction must be 'up', 'down', or 'both'")
        self.direction = direction
        self.gap_range = gap_range
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply gap filter using vectorized operations."""
        self._validate_data(data, min_length=2)  # Need at least 2 days for gap calculation
        
        opens = data['open'].astype(np.float64)
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate gap percentages
        # Gap for day i is: (open[i] - close[i-1]) / close[i-1] * 100
        gap_percentages = np.full_like(opens, np.nan)
        
        # Calculate gaps starting from the second day
        for i in range(1, len(opens)):
            if closes[i-1] > 0:  # Avoid division by zero
                gap_percentages[i] = ((opens[i] - closes[i-1]) / closes[i-1]) * 100
        
        abs_gaps = np.abs(gap_percentages)
        qualifying_mask = _range_mask(abs_gaps, self.gap_range)

        if self.direction == "up":
            qualifying_mask &= gap_percentages >= 0
        elif self.direction == "down":
            qualifying_mask &= gap_percentages <= 0
        
        # Calculate metrics
        valid_gaps = gap_percentages[~np.isnan(gap_percentages)]
        
        if len(valid_gaps) > 0:
            gap_up_count = int(np.sum(valid_gaps > 0))
            gap_down_count = int(np.sum(valid_gaps < 0))
            
            metrics = {
                'avg_gap_percentage': float(np.mean(np.abs(valid_gaps))),
                'max_gap_up_percentage': float(np.max(valid_gaps)) if gap_up_count > 0 else 0.0,
                'max_gap_down_percentage': float(np.min(valid_gaps)) if gap_down_count > 0 else 0.0,
                'gap_up_days': gap_up_count,
                'gap_down_days': gap_down_count,
                'qualifying_gap_days': int(np.sum(qualifying_mask)),
                'percent_days_with_gap': float((np.sum(qualifying_mask) / (len(opens) - 1)) * 100)  # -1 because first day has no gap
            }
        else:
            metrics = {
                'avg_gap_percentage': 0.0,
                'max_gap_up_percentage': 0.0,
                'max_gap_down_percentage': 0.0,
                'gap_up_days': 0,
                'gap_down_days': 0,
                'qualifying_gap_days': 0,
                'percent_days_with_gap': 0.0
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for gap calculation."""
        # Need previous day's close to calculate today's gap
        return 1


class PreviousDayDollarVolumeFilter(EnhancedBaseFilter):
    """Filter stocks using the previous day's dollar volume range."""

    def __init__(
        self,
        dollar_volume_range: NumericRange | None = None,
        name: str = "PreviousDayDollarVolumeFilter",
    ) -> None:
        self.name = name
        self.dollar_volume_range = dollar_volume_range or NumericRange(min=10_000_000)
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply previous day dollar volume filter."""
        self._validate_data(data, min_length=2)  # Need at least 2 days
        
        volumes = data['volume'].astype(np.float64)
        dates = data['date']
        
        # Use VWAP if available, otherwise use close price
        if 'vwap' in data.dtype.names:
            prices = data['vwap'].astype(np.float64)
            # Handle cases where VWAP might be 0 or NaN
            close_prices = data['close'].astype(np.float64)
            prices = np.where((prices > 0) & ~np.isnan(prices), prices, close_prices)
        else:
            prices = data['close'].astype(np.float64)
        
        # Calculate dollar volume for each day
        dollar_volumes = volumes * prices
        
        # Create qualifying mask using vectorized operations
        # Day i qualifies if day i-1 (yesterday) had sufficient dollar volume
        qualifying_mask = np.zeros(len(dollar_volumes), dtype=bool)
        if len(dollar_volumes) > 1:
            prev_values = dollar_volumes[:-1].astype(np.float64)
            qualifying_mask[1:] = _range_mask(prev_values, self.dollar_volume_range)
        
        # Calculate metrics
        # Get dollar volumes for days that had a previous day
        prev_day_dollar_volumes = dollar_volumes[:-1]  # All but last day
        
        if len(prev_day_dollar_volumes) > 0:
            metrics = {
                'avg_dollar_volume': float(np.mean(dollar_volumes)),
                'prev_day_avg_dollar_volume': float(np.mean(prev_day_dollar_volumes)),
                'prev_day_min_dollar_volume': float(np.min(prev_day_dollar_volumes)),
                'prev_day_max_dollar_volume': float(np.max(prev_day_dollar_volumes)),
                'days_qualifying': int(np.sum(qualifying_mask)),
                'prev_days_in_range': int(np.sum(_range_mask(prev_day_dollar_volumes, self.dollar_volume_range))),
                'percent_days_qualifying': float((np.sum(qualifying_mask) / len(dollar_volumes)) * 100)
            }
        else:
            metrics = {
                'avg_dollar_volume': 0.0,
                'prev_day_avg_dollar_volume': 0.0,
                'prev_day_min_dollar_volume': 0.0,
                'prev_day_max_dollar_volume': 0.0,
                'days_qualifying': 0,
                'prev_days_above_threshold': 0,
                'percent_days_qualifying': 0.0
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed."""
        # Need at least 1 previous day
        return 1


class RelativeVolumeFilter(EnhancedBaseFilter):
    """Filter stocks based on relative volume ratio."""

    def __init__(
        self,
        recent_days: int = 2,
        lookback_days: int = 20,
        ratio_range: NumericRange | None = None,
        name: str = "RelativeVolumeFilter",
    ) -> None:
        self.name = name

        if recent_days < 1:
            raise ValueError(f"recent_days must be >= 1, got {recent_days}")
        if lookback_days < recent_days:
            raise ValueError(
                f"lookback_days must be >= recent_days, got {lookback_days} < {recent_days}"
            )

        self.recent_days = recent_days
        self.lookback_days = lookback_days
        self.ratio_range = ratio_range or NumericRange(min=1.5)
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply relative volume filter."""
        # Need at least lookback_days + 1 to exclude current day
        required_days = self.lookback_days + 1
        if len(data) < required_days:
            logger.debug(f"RelativeVolumeFilter for {symbol}: Have {len(data)} days, need {required_days}")
        self._validate_data(data, min_length=required_days)
        
        volumes = data['volume'].astype(np.float64)
        dates = data['date']
        
        # Initialize arrays for ratios
        relative_volume_ratios = np.full(len(volumes), np.nan)
        
        # Vectorized calculation of relative volume ratios
        # We can calculate for all valid days at once
        if len(volumes) >= self.lookback_days + 1:
            # Create arrays to hold recent and historical averages
            recent_avgs = np.zeros(len(volumes) - self.lookback_days)
            historical_avgs = np.zeros(len(volumes) - self.lookback_days)
            
            # Calculate moving averages using vectorized operations
            for idx, i in enumerate(range(self.lookback_days, len(volumes))):
                # Recent average: last N days EXCLUDING current day
                recent_avgs[idx] = np.mean(volumes[i-self.recent_days:i])
                
                # Historical average: last M days EXCLUDING current day
                historical_avgs[idx] = np.mean(volumes[i-self.lookback_days:i])
            
            # Calculate ratios with division by zero handling
            # Where historical_avg is 0, set ratio to 0
            valid_mask = historical_avgs > 0
            ratios = np.zeros_like(recent_avgs)
            ratios[valid_mask] = recent_avgs[valid_mask] / historical_avgs[valid_mask]
            
            # Assign to the appropriate positions in the result array
            relative_volume_ratios[self.lookback_days:] = ratios
        
        # Create qualifying mask
        qualifying_mask = _range_mask(relative_volume_ratios, self.ratio_range)
        
        # Calculate metrics
        valid_ratios = relative_volume_ratios[~np.isnan(relative_volume_ratios)]
        
        if len(valid_ratios) > 0:
            metrics = {
                'avg_relative_volume_ratio': float(np.mean(valid_ratios)),
                'max_relative_volume_ratio': float(np.max(valid_ratios)),
                'min_relative_volume_ratio': float(np.min(valid_ratios)),
                'std_relative_volume_ratio': float(np.std(valid_ratios)),
                'days_qualifying': int(np.sum(qualifying_mask)),
                'days_in_range': int(np.sum(qualifying_mask)),
                'percent_days_qualifying': float((np.sum(qualifying_mask) / len(volumes)) * 100)
            }
        else:
            metrics = {
                'avg_relative_volume_ratio': 0.0,
                'max_relative_volume_ratio': 0.0,
                'min_relative_volume_ratio': 0.0,
                'std_relative_volume_ratio': 0.0,
                'days_qualifying': 0,
                'days_in_range': 0,
                'percent_days_qualifying': 0.0
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed."""
        # Need lookback_days + 1 because we exclude the current day
        return self.lookback_days + 1
