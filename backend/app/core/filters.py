"""
High-performance filter classes for stock screening using numpy vectorization.

This module provides abstract base classes and concrete implementations for
filtering stocks based on various criteria. All filters use vectorized numpy
operations for maximum performance.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple, Optional
import numpy as np
from datetime import date, datetime


class FilterResult:
    """Container for filter results including qualifying dates and metrics."""
    
    def __init__(self, 
                 symbol: str,
                 qualifying_mask: np.ndarray,
                 dates: np.ndarray,
                 metrics: Optional[Dict[str, Any]] = None):
        self.symbol = symbol
        self.qualifying_mask = qualifying_mask
        self.dates = dates
        self.metrics = metrics or {}
        
    @property
    def qualifying_dates(self) -> np.ndarray:
        """Get array of dates where the filter criteria was met."""
        return self.dates[self.qualifying_mask]
    
    @property
    def num_qualifying_days(self) -> int:
        """Get count of days that qualified."""
        return np.sum(self.qualifying_mask)
    
    def combine_with(self, other: 'FilterResult') -> 'FilterResult':
        """Combine this result with another using AND logic."""
        if self.symbol != other.symbol:
            raise ValueError(f"Cannot combine results for different symbols: {self.symbol} vs {other.symbol}")
        
        # Ensure date arrays match
        if not np.array_equal(self.dates, other.dates):
            raise ValueError("Cannot combine results with different date arrays")
        
        # Combine masks with AND logic
        combined_mask = self.qualifying_mask & other.qualifying_mask
        
        # Merge metrics
        combined_metrics = {**self.metrics, **other.metrics}
        
        return FilterResult(
            symbol=self.symbol,
            qualifying_mask=combined_mask,
            dates=self.dates,
            metrics=combined_metrics
        )


class BaseFilter(ABC):
    """
    Abstract base class for all stock filters.
    
    All filters must implement the apply method which performs vectorized
    operations on numpy arrays for maximum performance.
    """
    
    def __init__(self, name: str):
        self.name = name
    
    @abstractmethod
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """
        Apply the filter to stock data.
        
        Args:
            data: Structured numpy array with fields: date, open, high, low, close, volume, vwap
            symbol: Stock symbol being filtered
            
        Returns:
            FilterResult containing qualifying dates and calculated metrics
        """
        pass
    
    def _validate_data(self, data: np.ndarray, min_length: int = 1) -> None:
        """Validate input data array."""
        if len(data) < min_length:
            raise ValueError(f"Insufficient data: need at least {min_length} days, got {len(data)}")
        
        # Check for required fields
        required_fields = ['date', 'open', 'high', 'low', 'close', 'volume']
        for field in required_fields:
            if field not in data.dtype.names:
                raise ValueError(f"Missing required field: {field}")


class VolumeFilter(BaseFilter):
    """
    Filter stocks based on average volume over N days exceeding a threshold.
    
    Uses vectorized rolling mean calculation for efficiency.
    """
    
    def __init__(self, lookback_days: int, threshold: float, name: str = "VolumeFilter"):
        """
        Initialize volume filter.
        
        Args:
            lookback_days: Number of days to calculate average volume
            threshold: Minimum average volume threshold
            name: Optional name for the filter
        """
        super().__init__(name)
        if lookback_days < 1:
            raise ValueError(f"lookback_days must be >= 1, got {lookback_days}")
        if threshold < 0:
            raise ValueError(f"threshold must be >= 0, got {threshold}")
        
        self.lookback_days = lookback_days
        self.threshold = threshold
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply volume filter using vectorized operations."""
        self._validate_data(data, min_length=self.lookback_days)
        
        volumes = data['volume'].astype(np.float64)
        dates = data['date']
        
        # Calculate rolling average using vectorized convolution
        # This is much faster than loops for large arrays
        if self.lookback_days == 1:
            avg_volumes = volumes
        else:
            # Use uniform filter for rolling mean
            kernel = np.ones(self.lookback_days) / self.lookback_days
            # Mode 'valid' returns output only where full convolution is possible
            avg_volumes_valid = np.convolve(volumes, kernel, mode='valid')
            
            # Pad the beginning with NaN to maintain array alignment
            avg_volumes = np.full_like(volumes, np.nan)
            avg_volumes[self.lookback_days - 1:] = avg_volumes_valid
        
        # Create mask for qualifying dates (ignore NaN values)
        qualifying_mask = ~np.isnan(avg_volumes) & (avg_volumes >= self.threshold)
        
        # Calculate metrics
        valid_avg_volumes = avg_volumes[~np.isnan(avg_volumes)]
        metrics = {
            f'avg_volume_{self.lookback_days}d_mean': float(np.mean(valid_avg_volumes)) if len(valid_avg_volumes) > 0 else 0.0,
            f'avg_volume_{self.lookback_days}d_max': float(np.max(valid_avg_volumes)) if len(valid_avg_volumes) > 0 else 0.0,
            f'avg_volume_{self.lookback_days}d_min': float(np.min(valid_avg_volumes)) if len(valid_avg_volumes) > 0 else 0.0,
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


class PriceChangeFilter(BaseFilter):
    """
    Filter stocks based on price change percentage within a specified range.
    
    Calculates daily price change % and filters based on min/max thresholds.
    """
    
    def __init__(self, min_change: float, max_change: float, name: str = "PriceChangeFilter"):
        """
        Initialize price change filter.
        
        Args:
            min_change: Minimum price change % (can be negative)
            max_change: Maximum price change %
            name: Optional name for the filter
        """
        super().__init__(name)
        if min_change >= max_change:
            raise ValueError(f"min_change ({min_change}) must be less than max_change ({max_change})")
        
        self.min_change = min_change
        self.max_change = max_change
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply price change filter using vectorized operations."""
        self._validate_data(data, min_length=2)
        
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate daily price change percentage
        # Using vectorized operations for efficiency
        price_changes = np.full_like(closes, np.nan)
        price_changes[1:] = ((closes[1:] - closes[:-1]) / closes[:-1]) * 100
        
        # Create mask for qualifying dates
        qualifying_mask = (~np.isnan(price_changes) & 
                          (price_changes >= self.min_change) & 
                          (price_changes <= self.max_change))
        
        # Calculate metrics
        valid_changes = price_changes[~np.isnan(price_changes)]
        metrics = {
            'price_change_mean': np.mean(valid_changes) if len(valid_changes) > 0 else 0,
            'price_change_std': np.std(valid_changes) if len(valid_changes) > 0 else 0,
            'price_change_max': np.max(valid_changes) if len(valid_changes) > 0 else 0,
            'price_change_min': np.min(valid_changes) if len(valid_changes) > 0 else 0,
        }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


class MovingAverageFilter(BaseFilter):
    """
    Filter stocks based on price position relative to Simple Moving Average (SMA).
    
    Can filter for prices above or below the SMA.
    """
    
    def __init__(self, period: int, position: str = "above", name: str = "MovingAverageFilter"):
        """
        Initialize moving average filter.
        
        Args:
            period: Number of days for SMA calculation
            position: "above" or "below" - filter for prices above or below SMA
            name: Optional name for the filter
        """
        super().__init__(name)
        if period < 1:
            raise ValueError(f"period must be >= 1, got {period}")
        if position not in ["above", "below"]:
            raise ValueError(f"position must be 'above' or 'below', got '{position}'")
        
        self.period = period
        self.position = position
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply moving average filter using vectorized operations."""
        self._validate_data(data, min_length=self.period)
        
        closes = data['close'].astype(np.float64)
        dates = data['date']
        
        # Calculate Simple Moving Average using vectorized convolution
        if self.period == 1:
            sma = closes
        else:
            kernel = np.ones(self.period) / self.period
            sma_valid = np.convolve(closes, kernel, mode='valid')
            
            # Pad the beginning with NaN to maintain array alignment
            sma = np.full_like(closes, np.nan)
            sma[self.period - 1:] = sma_valid
        
        # Create mask based on position
        if self.position == "above":
            qualifying_mask = ~np.isnan(sma) & (closes > sma)
        else:  # below
            qualifying_mask = ~np.isnan(sma) & (closes < sma)
        
        # Calculate metrics
        valid_sma = sma[~np.isnan(sma)]
        valid_closes = closes[~np.isnan(sma)]
        
        if len(valid_sma) > 0:
            distance_from_sma = ((valid_closes - valid_sma) / valid_sma) * 100
            metrics = {
                f'sma_{self.period}_value_mean': np.mean(valid_sma),
                f'distance_from_sma_{self.period}_mean': np.mean(distance_from_sma),
                f'distance_from_sma_{self.period}_std': np.std(distance_from_sma),
            }
        else:
            metrics = {
                f'sma_{self.period}_value_mean': 0,
                f'distance_from_sma_{self.period}_mean': 0,
                f'distance_from_sma_{self.period}_std': 0,
            }
        
        return FilterResult(
            symbol=symbol,
            qualifying_mask=qualifying_mask,
            dates=dates,
            metrics=metrics
        )


class CompositeFilter(BaseFilter):
    """
    Combines multiple filters using AND logic.
    
    All filters must pass for a date to qualify.
    """
    
    def __init__(self, filters: list, name: str = "CompositeFilter"):
        """
        Initialize composite filter.
        
        Args:
            filters: List of BaseFilter instances to combine
            name: Optional name for the filter
        """
        super().__init__(name)
        if not filters:
            raise ValueError("At least one filter must be provided")
        
        self.filters = filters
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply all filters and combine results with AND logic."""
        if not self.filters:
            # Return all True if no filters
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
        
        return result