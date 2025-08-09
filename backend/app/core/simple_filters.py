"""
Simple and efficient filters for stock screening.

This module provides three basic filters that replace the complex filter system:
1. SimplePriceRangeFilter - Filter by OPEN price range
2. PriceVsMAFilter - Compare OPEN price to moving average
3. RSIFilter - Standard RSI calculation with threshold

All filters are fully vectorized using NumPy and support database pre-filtering.
"""

from typing import Optional, Dict, Any, List
from dataclasses import dataclass
import numpy as np
import logging

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

class DatabasePreFilter:
    """Interface for database pre-filtering."""
    pass

logger = logging.getLogger(__name__)


class SimplePriceRangeFilter(EnhancedBaseFilter):
    """
    Filter stocks based on OPEN price within a specific range.
    
    This filter uses the OPEN price of each day to determine if a stock
    qualifies, making it suitable for day trading strategies that focus
    on entry opportunities at market open.
    
    Supports database pre-filtering for efficient data loading.
    """
    
    def __init__(self, min_price: float, max_price: float, name: str = "SimplePriceRangeFilter"):
        """
        Initialize price range filter.
        
        Args:
            min_price: Minimum acceptable OPEN price
            max_price: Maximum acceptable OPEN price
            name: Optional name for the filter
        """
        self.name = name
        if min_price < 0:
            raise ValueError(f"min_price must be >= 0, got {min_price}")
        if max_price < min_price:
            raise ValueError(f"max_price must be >= min_price")
        
        self.min_price = min_price
        self.max_price = max_price
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply price range filter using OPEN prices."""
        self._validate_data(data)
        
        opens = data['open'].astype(np.float64)
        dates = data['date']
        
        # Create mask for qualifying dates based on OPEN price
        qualifying_mask = (opens >= self.min_price) & (opens <= self.max_price)
        
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
        return DatabasePreFilter(
            where_conditions=[
                f"open >= {self.min_price}",
                f"open <= {self.max_price}"
            ]
        )


class PriceVsMAFilter(EnhancedBaseFilter):
    """
    Filter stocks based on OPEN price position relative to moving average.
    
    The moving average is calculated from CLOSE prices of previous days
    (excluding the current day), then compared to the current day's OPEN price.
    This approach identifies stocks that open above or below their recent trend.
    
    Supports periods: 20, 50, 200 days
    Conditions: "above" or "below"
    """
    
    def __init__(self, period: int, condition: str = "above", name: str = "PriceVsMAFilter"):
        """
        Initialize price vs MA filter.
        
        Args:
            period: Moving average period (20, 50, or 200)
            condition: "above" or "below" - filter for OPEN prices above or below MA
            name: Optional name for the filter
        """
        self.name = name
        if period not in [20, 50, 200]:
            raise ValueError(f"period must be 20, 50, or 200, got {period}")
        if condition not in ["above", "below"]:
            raise ValueError(f"condition must be 'above' or 'below', got '{condition}'")
        
        self.period = period
        self.condition = condition
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply price vs MA filter using vectorized operations."""
        # Don't enforce strict validation - work with the data we have
        self._validate_data(data, min_length=1)
        
        # If we don't have enough data for the MA, return empty result
        if len(data) < self.period:
            return FilterResult(
                symbol=symbol,
                qualifying_mask=np.zeros(len(data), dtype=bool),
                dates=data['date'],
                metrics={'error': f'Insufficient data for {self.period}-day MA'}
            )
        
        opens = data['open'].astype(np.float64)
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate MA from previous closes (excluding current day)
        # For each day, we calculate MA from the previous N closes
        ma_values = np.full_like(closes, np.nan)
        
        # We need at least 'period' previous days to calculate MA
        for i in range(self.period, len(closes)):
            # Calculate MA from previous closes (not including current day)
            ma_values[i] = np.mean(closes[i-self.period:i])
        
        # Compare OPEN price to MA
        if self.condition == "above":
            qualifying_mask = ~np.isnan(ma_values) & (opens > ma_values)
        else:  # below
            qualifying_mask = ~np.isnan(ma_values) & (opens < ma_values)
        
        # Calculate metrics
        valid_mas = ma_values[~np.isnan(ma_values)]
        valid_opens = opens[~np.isnan(ma_values)]
        
        if len(valid_mas) > 0:
            distance_from_ma = ((valid_opens - valid_mas) / valid_mas) * 100
            metrics = {
                f'ma_{self.period}_mean': float(np.mean(valid_mas)),
                f'distance_from_ma_{self.period}_mean': float(np.mean(distance_from_ma)),
                f'distance_from_ma_{self.period}_std': float(np.std(distance_from_ma)),
                'qualifying_days': int(np.sum(qualifying_mask)),
                'total_days_with_ma': int(len(valid_mas))
            }
        else:
            metrics = {
                f'ma_{self.period}_mean': 0.0,
                f'distance_from_ma_{self.period}_mean': 0.0,
                f'distance_from_ma_{self.period}_std': 0.0,
                'qualifying_days': 0,
                'total_days_with_ma': 0
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
    """
    Filter stocks based on Relative Strength Index (RSI).
    
    Uses Wilder's method for RSI calculation:
    - First average gain/loss uses simple average
    - Subsequent values use smoothed average: (prev_avg * (n-1) + current) / n
    
    RSI = 100 - (100 / (1 + RS))
    where RS = average gain / average loss
    """
    
    def __init__(self, period: int = 14, threshold: float = 30.0, 
                 condition: str = "below", name: str = "RSIFilter"):
        """
        Initialize RSI filter.
        
        Args:
            period: RSI calculation period (default: 14)
            threshold: RSI threshold value (e.g., 30 for oversold, 70 for overbought)
            condition: "above" or "below" - filter condition relative to threshold
            name: Optional name for the filter
        """
        self.name = name
        if period < 2:
            raise ValueError(f"period must be >= 2, got {period}")
        if threshold < 0 or threshold > 100:
            raise ValueError(f"threshold must be between 0 and 100, got {threshold}")
        if condition not in ["above", "below"]:
            raise ValueError(f"condition must be 'above' or 'below', got '{condition}'")
        
        self.period = period
        self.threshold = threshold
        self.condition = condition
    
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
        
        # Create qualifying mask based on condition
        if self.condition == "above":
            qualifying_mask = ~np.isnan(rsi_values) & (rsi_values > self.threshold)
        else:  # below
            qualifying_mask = ~np.isnan(rsi_values) & (rsi_values < self.threshold)
        
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
    """
    Filter stocks based on minimum average trading volume in shares.
    
    This filter calculates the average volume over a specified lookback period
    and filters stocks that meet the minimum volume requirement.
    
    Supports database pre-filtering for efficient data loading.
    """
    
    def __init__(self, lookback_days: int = 20, min_avg_volume: float = 1000000, 
                 name: str = "MinAverageVolumeFilter"):
        """
        Initialize minimum average volume filter.
        
        Args:
            lookback_days: Number of days to calculate average volume (default: 20)
            min_avg_volume: Minimum average volume in shares (default: 1M)
            name: Optional name for the filter
        """
        self.name = name
        if lookback_days < 1:
            raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")
        if min_avg_volume < 0:
            raise ValueError(f"min_avg_volume must be >= 0, got {min_avg_volume}")
        
        self.lookback_days = lookback_days
        self.min_avg_volume = min_avg_volume
    
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
        qualifying_mask = ~np.isnan(avg_volumes) & (avg_volumes >= self.min_avg_volume)
        
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
        # Pre-filter for stocks that have at least some days with high volume
        # This is an approximation - we check if volume ever exceeds the threshold
        return DatabasePreFilter(
            where_conditions=[
                f"volume >= {self.min_avg_volume}"
            ]
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for average calculation."""
        return self.lookback_days


class MinAverageDollarVolumeFilter(EnhancedBaseFilter):
    """
    Filter stocks based on minimum average dollar volume (price * volume).
    
    This filter calculates the average dollar volume over a specified lookback period
    and filters stocks that meet the minimum dollar volume requirement.
    Uses VWAP (Volume Weighted Average Price) when available, otherwise uses close price.
    
    Supports database pre-filtering for efficient data loading.
    """
    
    def __init__(self, lookback_days: int = 20, min_avg_dollar_volume: float = 10000000, 
                 name: str = "MinAverageDollarVolumeFilter"):
        """
        Initialize minimum average dollar volume filter.
        
        Args:
            lookback_days: Number of days to calculate average dollar volume (default: 20)
            min_avg_dollar_volume: Minimum average dollar volume (default: $10M)
            name: Optional name for the filter
        """
        self.name = name
        if lookback_days < 1:
            raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")
        if min_avg_dollar_volume < 0:
            raise ValueError(f"min_avg_dollar_volume must be >= 0, got {min_avg_dollar_volume}")
        
        self.lookback_days = lookback_days
        self.min_avg_dollar_volume = min_avg_dollar_volume
    
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
        qualifying_mask = ~np.isnan(avg_dollar_volumes) & (avg_dollar_volumes >= self.min_avg_dollar_volume)
        
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
        # Pre-filter using a conservative estimate: volume * close >= threshold
        # This assumes average price is at least $1
        min_volume_estimate = self.min_avg_dollar_volume / 100  # Assuming avg price of $100
        return DatabasePreFilter(
            where_conditions=[
                f"volume >= {min_volume_estimate}"
            ]
        )
    
    def get_required_lookback_days(self) -> int:
        """Return number of historical days needed for average calculation."""
        return self.lookback_days


class GapFilter(EnhancedBaseFilter):
    """
    Filter stocks based on gap between today's open and yesterday's close.
    
    A gap occurs when today's opening price is significantly different from
    yesterday's closing price. This filter calculates the gap percentage and
    filters based on the specified threshold and direction.
    
    Gap percentage = ((today_open - yesterday_close) / yesterday_close) * 100
    """
    
    def __init__(self, gap_threshold: float = 2.0, direction: str = "both", 
                 name: str = "GapFilter"):
        """
        Initialize gap filter.
        
        Args:
            gap_threshold: Minimum gap percentage to qualify (default: 2%)
            direction: Gap direction - "up", "down", or "both" (default: "both")
            name: Optional name for the filter
        """
        self.name = name
        if gap_threshold < 0:
            raise ValueError(f"gap_threshold must be >= 0, got {gap_threshold}")
        if direction not in ["up", "down", "both"]:
            raise ValueError(f"direction must be 'up', 'down', or 'both', got '{direction}'")
        
        self.gap_threshold = gap_threshold
        self.direction = direction
    
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
        
        # Create qualifying mask based on direction and threshold
        if self.direction == "up":
            # Gap up: today's open > yesterday's close by threshold%
            qualifying_mask = ~np.isnan(gap_percentages) & (gap_percentages >= self.gap_threshold)
        elif self.direction == "down":
            # Gap down: today's open < yesterday's close by threshold%
            qualifying_mask = ~np.isnan(gap_percentages) & (gap_percentages <= -self.gap_threshold)
        else:  # both
            # Either gap up or gap down by threshold%
            qualifying_mask = ~np.isnan(gap_percentages) & (np.abs(gap_percentages) >= self.gap_threshold)
        
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