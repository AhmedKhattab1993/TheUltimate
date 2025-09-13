"""
Simplified request models for the 3 basic trading filters.
"""

from pydantic import BaseModel, Field, validator
from datetime import date
from typing import List, Optional, Literal, Dict, Any
from enum import Enum


class SimplePriceRangeParams(BaseModel):
    """Parameters for simple price range filter using OPEN price."""
    min_price: float = Field(1.0, ge=0, description="Minimum OPEN price")
    max_price: float = Field(100.0, ge=0, description="Maximum OPEN price")
    
    @validator('max_price')
    def validate_max_greater_than_min(cls, v, values):
        if 'min_price' in values and v < values['min_price']:
            raise ValueError('max_price must be greater than or equal to min_price')
        return v


class MAPeriod(int, Enum):
    """Common moving average periods."""
    MA_20 = 20
    MA_50 = 50
    MA_200 = 200


class PriceVsMAParams(BaseModel):
    """Parameters for price vs moving average filter."""
    ma_period: int = Field(MAPeriod.MA_20, ge=2, le=200, description="Moving average period in days")
    condition: Literal["above", "below"] = Field("above", description="Price position relative to MA")


class RSIParams(BaseModel):
    """Parameters for RSI filter."""
    rsi_period: int = Field(14, ge=2, le=50, description="RSI calculation period")
    condition: Literal["above", "below"] = Field("below", description="RSI condition")
    threshold: float = Field(30.0, ge=0, le=100, description="RSI threshold (e.g., 30 for oversold, 70 for overbought)")
    
    @validator('threshold')
    def validate_threshold_makes_sense(cls, v, values):
        """Warn if threshold doesn't match typical usage."""
        if 'condition' in values:
            if values['condition'] == 'below' and v > 50:
                # Usually looking for oversold when below threshold
                pass  # Allow but could log warning
            elif values['condition'] == 'above' and v < 50:
                # Usually looking for overbought when above threshold
                pass  # Allow but could log warning
        return v


class MinAverageVolumeParams(BaseModel):
    """Parameters for minimum average volume filter."""
    lookback_days: int = Field(20, ge=1, le=200, description="Number of days to calculate average volume")
    min_avg_volume: float = Field(1000000, ge=0, description="Minimum average volume in shares")


class MinAverageDollarVolumeParams(BaseModel):
    """Parameters for minimum average dollar volume filter."""
    lookback_days: int = Field(20, ge=1, le=200, description="Number of days to calculate average dollar volume")
    min_avg_dollar_volume: float = Field(10000000, ge=0, description="Minimum average dollar volume")


class GapDirection(str, Enum):
    """Gap direction options."""
    UP = "up"
    DOWN = "down"
    BOTH = "both"


class GapParams(BaseModel):
    """Parameters for gap filter."""
    gap_threshold: float = Field(2.0, ge=0, le=50, description="Minimum gap percentage to qualify")
    direction: GapDirection = Field(GapDirection.BOTH, description="Gap direction - up, down, or both")


class PreviousDayDollarVolumeParams(BaseModel):
    """Parameters for previous day dollar volume filter."""
    min_dollar_volume: float = Field(10000000, ge=0, description="Minimum dollar volume for previous day")


class RelativeVolumeParams(BaseModel):
    """Parameters for relative volume filter."""
    recent_days: int = Field(2, ge=1, le=10, description="Number of recent days for average")
    lookback_days: int = Field(20, ge=5, le=200, description="Number of historical days for average")
    min_ratio: float = Field(1.5, ge=0.1, le=10, description="Minimum ratio of recent/historical volume")
    
    @validator('lookback_days')
    def validate_lookback_greater_than_recent(cls, v, values):
        if 'recent_days' in values and v <= values['recent_days']:
            raise ValueError('lookback_days must be greater than recent_days')
        return v


class SimpleFilters(BaseModel):
    """Container for the 8 simple filters."""
    price_range: Optional[SimplePriceRangeParams] = Field(None, description="Filter by OPEN price range")
    price_vs_ma: Optional[PriceVsMAParams] = Field(None, description="Filter by price vs moving average")
    rsi: Optional[RSIParams] = Field(None, description="Filter by RSI conditions")
    min_avg_volume: Optional[MinAverageVolumeParams] = Field(None, description="Filter by minimum average volume")
    min_avg_dollar_volume: Optional[MinAverageDollarVolumeParams] = Field(None, description="Filter by minimum average dollar volume")
    gap: Optional[GapParams] = Field(None, description="Filter by gap between open and previous close")
    prev_day_dollar_volume: Optional[PreviousDayDollarVolumeParams] = Field(None, description="Filter by previous day's dollar volume")
    relative_volume: Optional[RelativeVolumeParams] = Field(None, description="Filter by relative volume ratio")


class SimpleScreenRequest(BaseModel):
    """Simplified screening request with 8 basic filters."""
    start_date: date = Field(..., description="Start date for screening")
    end_date: date = Field(..., description="End date for screening")
    use_all_us_stocks: bool = Field(True, description="Screen all US common stocks")
    filters: SimpleFilters = Field(..., description="Simple filter parameters")
    
    # Performance options
    enable_db_prefiltering: bool = Field(True, description="Use database pre-filtering where possible")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be on or after start_date')
        # Limit date range for performance
        if 'start_date' in values:
            days = (v - values['start_date']).days
            if days > 365:
                raise ValueError('Date range cannot exceed 365 days')
        return v
    
    
    @validator('filters')
    def validate_at_least_one_filter(cls, v):
        if not any([v.price_range, v.price_vs_ma, v.rsi, v.min_avg_volume, v.min_avg_dollar_volume, v.gap, v.prev_day_dollar_volume, v.relative_volume]):
            raise ValueError('At least one filter must be specified')
        return v


class SimpleScreenResult(BaseModel):
    """Result for a single symbol from simplified screening."""
    symbol: str
    qualifying_dates: List[date]
    total_days_analyzed: int
    qualifying_days_count: int
    metrics: dict  # Filter-specific metrics
    
    @property
    def qualifying_percentage(self) -> float:
        """Calculate percentage of days that qualified."""
        if self.total_days_analyzed == 0:
            return 0.0
        return (self.qualifying_days_count / self.total_days_analyzed) * 100
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class TimingBreakdown(BaseModel):
    """Detailed timing breakdown for screening operations."""
    symbol_fetch_ms: float = Field(description="Time to fetch active symbols from database")
    data_loading_ms: float = Field(description="Time to load historical data")
    filter_timings: Dict[str, Dict[str, float]] = Field(
        default_factory=dict,
        description="Timing for each filter (total_ms and symbols_processed)"
    )
    result_saving_ms: float = Field(description="Time to save results")


class SimpleScreenResponse(BaseModel):
    """Response from simplified screening endpoint."""
    request: SimpleScreenRequest
    execution_time_ms: float
    total_symbols_screened: int
    total_qualifying_stocks: int
    results: List[SimpleScreenResult]
    
    # Performance metrics
    db_prefiltering_used: bool = Field(False, description="Whether database pre-filtering was used")
    symbols_filtered_by_db: int = Field(0, description="Number of symbols eliminated by DB pre-filtering")
    
    # Timing breakdown (optional - only included when available)
    timing_breakdown: Optional[Dict[str, TimingBreakdown]] = Field(
        None,
        description="Detailed timing breakdown by date (date -> timing details)"
    )
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }