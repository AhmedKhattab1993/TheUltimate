"""
Enhanced filters that can optionally return daily calculated values.

These are modified versions of simple_filters that include daily values in metrics
when return_daily_values=True is specified.
"""

from typing import Optional, Dict, Any, List
import numpy as np
import logging
from .simple_filters import (
    EnhancedBaseFilter, FilterResult,
    SimplePriceRangeFilter as BaseSimplePriceRangeFilter,
    PriceVsMAFilter as BasePriceVsMAFilter,
    RSIFilter as BaseRSIFilter,
    GapFilter as BaseGapFilter,
    PreviousDayDollarVolumeFilter as BasePreviousDayDollarVolumeFilter,
    RelativeVolumeFilter as BaseRelativeVolumeFilter
)

logger = logging.getLogger(__name__)


class EnhancedPriceVsMAFilter(BasePriceVsMAFilter):
    """Enhanced version that can return daily MA values."""
    
    def __init__(self, period: int, condition: str = "above", 
                 name: Optional[str] = None, return_daily_values: bool = False):
        super().__init__(period, condition, name)
        self.return_daily_values = return_daily_values
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply filter and optionally include daily values in metrics."""
        # Get base result
        result = super().apply(data, symbol)
        
        if self.return_daily_values:
            # Recalculate MA values to include in metrics
            closes = data['close']
            ma_values = np.full_like(closes, np.nan)
            
            for i in range(self.period, len(closes)):
                ma_values[i] = np.mean(closes[i-self.period:i])
            
            # Add daily values to metrics
            result.metrics['ma_values'] = ma_values.tolist()
            result.metrics['dates'] = data['date'].astype(str).tolist()
        
        return result


class EnhancedRSIFilter(BaseRSIFilter):
    """Enhanced version that can return daily RSI values."""
    
    def __init__(self, period: int = 14, threshold: float = 30.0, 
                 condition: str = "below", name: Optional[str] = None,
                 return_daily_values: bool = False):
        super().__init__(period, threshold, condition, name)
        self.return_daily_values = return_daily_values
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply filter and optionally include daily values in metrics."""
        # Get base result 
        result = super().apply(data, symbol)
        
        if self.return_daily_values:
            # Recalculate RSI values to include in metrics
            closes = data['close']
            rsi_values = np.full_like(closes, np.nan)
            
            # Calculate price changes
            price_changes = np.diff(closes)
            
            # Need at least period + 1 prices to calculate RSI
            if len(closes) > self.period:
                # Calculate initial RSI
                gains = np.where(price_changes[:self.period] > 0, price_changes[:self.period], 0)
                losses = np.where(price_changes[:self.period] < 0, -price_changes[:self.period], 0)
                
                avg_gain = np.mean(gains)
                avg_loss = np.mean(losses)
                
                if avg_loss != 0:
                    rs = avg_gain / avg_loss
                    rsi_values[self.period] = 100 - (100 / (1 + rs))
                else:
                    rsi_values[self.period] = 100
                
                # Calculate subsequent RSI values using Wilder's smoothing
                for i in range(self.period + 1, len(closes)):
                    gain = max(price_changes[i-1], 0)
                    loss = max(-price_changes[i-1], 0)
                    
                    avg_gain = (avg_gain * (self.period - 1) + gain) / self.period
                    avg_loss = (avg_loss * (self.period - 1) + loss) / self.period
                    
                    if avg_loss != 0:
                        rs = avg_gain / avg_loss
                        rsi_values[i] = 100 - (100 / (1 + rs))
                    else:
                        rsi_values[i] = 100
            
            # Add daily values to metrics
            result.metrics['rsi_values'] = rsi_values.tolist()
            result.metrics['dates'] = data['date'].astype(str).tolist()
        
        return result


class EnhancedGapFilter(BaseGapFilter):
    """Enhanced version that can return daily gap percentages."""
    
    def __init__(self, gap_threshold: float = 2.0, direction: str = "up",
                 name: Optional[str] = None, return_daily_values: bool = False):
        super().__init__(gap_threshold, direction, name)
        self.return_daily_values = return_daily_values
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply filter and optionally include daily values in metrics."""
        # Get base result
        result = super().apply(data, symbol)
        
        if self.return_daily_values:
            # Recalculate gap percentages to include in metrics
            opens = data['open']
            closes = data['close']
            gap_percentages = np.full_like(opens, np.nan)
            
            # Calculate gaps starting from the second day
            for i in range(1, len(opens)):
                if closes[i-1] > 0:  # Avoid division by zero
                    gap_percentages[i] = ((opens[i] - closes[i-1]) / closes[i-1]) * 100
            
            # Add daily values to metrics
            result.metrics['gap_percentages'] = gap_percentages.tolist()
            result.metrics['dates'] = data['date'].astype(str).tolist()
        
        return result


class EnhancedPreviousDayDollarVolumeFilter(BasePreviousDayDollarVolumeFilter):
    """Enhanced version that can return daily dollar volumes."""
    
    def __init__(self, min_dollar_volume: float = 1_000_000, 
                 name: Optional[str] = None, return_daily_values: bool = False):
        super().__init__(min_dollar_volume, name)
        self.return_daily_values = return_daily_values
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply filter and optionally include daily values in metrics."""
        # Get base result
        result = super().apply(data, symbol)
        
        if self.return_daily_values:
            # Calculate dollar volumes
            volumes = data['volume']
            prices = data['close']
            dollar_volumes = volumes * prices
            
            # Previous day dollar volumes (shift by 1)
            prev_day_dollar_volumes = np.full_like(dollar_volumes, np.nan)
            if len(dollar_volumes) > 1:
                prev_day_dollar_volumes[1:] = dollar_volumes[:-1]
            
            # Add daily values to metrics
            result.metrics['dollar_volumes'] = dollar_volumes.tolist()
            result.metrics['prev_day_dollar_volumes'] = prev_day_dollar_volumes.tolist()
            result.metrics['dates'] = data['date'].astype(str).tolist()
        
        return result


class EnhancedRelativeVolumeFilter(BaseRelativeVolumeFilter):
    """Enhanced version that can return daily relative volume ratios."""
    
    def __init__(self, recent_days: int = 2, lookback_days: int = 20,
                 min_ratio: float = 1.5, name: Optional[str] = None,
                 return_daily_values: bool = False):
        super().__init__(recent_days, lookback_days, min_ratio, name)
        self.return_daily_values = return_daily_values
    
    def apply(self, data: np.ndarray, symbol: str) -> FilterResult:
        """Apply filter and optionally include daily values in metrics."""
        # Get base result
        result = super().apply(data, symbol)
        
        if self.return_daily_values:
            # Recalculate relative volume ratios
            volumes = data['volume']
            relative_volume_ratios = np.full(len(volumes), np.nan)
            
            # Vectorized calculation of relative volume ratios
            if len(volumes) >= self.lookback_days:
                # For each position starting from lookback_days
                for i in range(self.lookback_days, len(volumes)):
                    # Calculate recent average (including current day)
                    recent_start = max(0, i - self.recent_days + 1)
                    recent_avg = np.mean(volumes[recent_start:i + 1])
                    
                    # Calculate lookback average (excluding recent days)
                    lookback_start = i - self.lookback_days + 1
                    lookback_end = recent_start
                    
                    if lookback_end > lookback_start:
                        lookback_avg = np.mean(volumes[lookback_start:lookback_end])
                        
                        if lookback_avg > 0:
                            relative_volume_ratios[i] = recent_avg / lookback_avg
            
            # Add daily values to metrics
            result.metrics['relative_volume_ratios'] = relative_volume_ratios.tolist()
            result.metrics['dates'] = data['date'].astype(str).tolist()
        
        return result