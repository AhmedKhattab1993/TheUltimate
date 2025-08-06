from pydantic import BaseModel, Field, validator
from datetime import date
from typing import Dict, List, Optional, Any
from enum import Enum


class ComparisonOperator(str, Enum):
    ABOVE = "above"
    BELOW = "below"
    CROSSES_ABOVE = "crosses_above"
    CROSSES_BELOW = "crosses_below"


class VolumeFilterParams(BaseModel):
    min_average: Optional[float] = Field(None, ge=0, description="Minimum average volume")
    max_average: Optional[float] = Field(None, ge=0, description="Maximum average volume")
    lookback_days: int = Field(20, ge=1, le=252, description="Days to calculate average")
    
    @validator('max_average')
    def validate_max_greater_than_min(cls, v, values):
        if v is not None and 'min_average' in values and values['min_average'] is not None:
            if v < values['min_average']:
                raise ValueError('max_average must be greater than min_average')
        return v


class PriceChangeFilterParams(BaseModel):
    min_change: Optional[float] = Field(None, description="Minimum price change %")
    max_change: Optional[float] = Field(None, description="Maximum price change %")
    period_days: int = Field(1, ge=1, le=252, description="Period for calculating change")
    
    @validator('max_change')
    def validate_max_greater_than_min(cls, v, values):
        if v is not None and 'min_change' in values and values['min_change'] is not None:
            if v < values['min_change']:
                raise ValueError('max_change must be greater than min_change')
        return v


class MovingAverageFilterParams(BaseModel):
    period: int = Field(50, ge=2, le=200, description="Moving average period")
    condition: ComparisonOperator = Field(ComparisonOperator.ABOVE, description="Price condition relative to MA")


class GapFilterParams(BaseModel):
    min_gap_percent: float = Field(4.0, ge=0, description="Minimum gap percentage from previous close")
    max_gap_percent: Optional[float] = Field(None, ge=0, description="Maximum gap percentage from previous close")
    
    @validator('max_gap_percent')
    def validate_max_greater_than_min(cls, v, values):
        if v is not None and 'min_gap_percent' in values and values['min_gap_percent'] is not None:
            if v < values['min_gap_percent']:
                raise ValueError('max_gap_percent must be greater than min_gap_percent')
        return v


class PriceRangeFilterParams(BaseModel):
    min_price: float = Field(2.0, ge=0, description="Minimum stock price")
    max_price: float = Field(10.0, ge=0, description="Maximum stock price")
    
    @validator('max_price')
    def validate_max_greater_than_min(cls, v, values):
        if 'min_price' in values and v < values['min_price']:
            raise ValueError('max_price must be greater than min_price')
        return v


class FloatFilterParams(BaseModel):
    max_float: float = Field(100_000_000, gt=0, description="Maximum share float (shares outstanding)")


class RelativeVolumeFilterParams(BaseModel):
    min_relative_volume: float = Field(2.0, ge=1.0, description="Minimum relative volume vs average")
    lookback_days: int = Field(20, ge=5, le=60, description="Days to calculate average volume")


class MarketCapFilterParams(BaseModel):
    max_market_cap: float = Field(300_000_000, gt=0, description="Maximum market capitalization")
    min_market_cap: Optional[float] = Field(None, ge=0, description="Minimum market capitalization")
    
    @validator('max_market_cap')
    def validate_max_greater_than_min(cls, v, values):
        if 'min_market_cap' in values and values['min_market_cap'] is not None:
            if v < values['min_market_cap']:
                raise ValueError('max_market_cap must be greater than min_market_cap')
        return v


class PreMarketVolumeFilterParams(BaseModel):
    min_volume: int = Field(100_000, ge=0, description="Minimum pre-market volume")
    cutoff_time: str = Field("09:00", description="Time cutoff for pre-market volume (EST)")


class NewsCatalystFilterParams(BaseModel):
    hours_lookback: int = Field(24, ge=1, le=72, description="Hours to look back for news")
    require_news: bool = Field(True, description="Require news catalyst for qualification")


class Filters(BaseModel):
    volume: Optional[VolumeFilterParams] = None
    price_change: Optional[PriceChangeFilterParams] = None
    moving_average: Optional[MovingAverageFilterParams] = None
    gap: Optional[GapFilterParams] = None
    price_range: Optional[PriceRangeFilterParams] = None
    float: Optional[FloatFilterParams] = None
    relative_volume: Optional[RelativeVolumeFilterParams] = None
    market_cap: Optional[MarketCapFilterParams] = None
    premarket_volume: Optional[PreMarketVolumeFilterParams] = None
    news_catalyst: Optional[NewsCatalystFilterParams] = None


class ScreenRequest(BaseModel):
    start_date: date
    end_date: date
    symbols: Optional[List[str]] = Field(None, description="Symbols to screen (defaults to preset list)")
    use_all_us_stocks: bool = Field(False, description="Screen all US common stocks instead of specific symbols")
    filters: Filters
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be after start_date')
        return v
    
    @validator('symbols')
    def validate_symbols(cls, v, values):
        # If use_all_us_stocks is True, symbols should be None or empty
        if 'use_all_us_stocks' in values and values['use_all_us_stocks'] and v:
            raise ValueError('Cannot specify both symbols and use_all_us_stocks=True')
        
        if v:
            # Convert to uppercase and remove duplicates
            return list(set(symbol.upper() for symbol in v))
        return v


class ScreenResult(BaseModel):
    symbol: str
    qualifying_dates: List[date]
    metrics: Dict[str, Any]  # Additional metrics like avg volume, price change, etc.
    
    class Config:
        json_encoders = {
            date: lambda v: v.isoformat()
        }


class PerformanceMetrics(BaseModel):
    """Performance metrics for bulk endpoint optimization tracking."""
    data_fetch_time_ms: float
    screening_time_ms: float
    total_execution_time_ms: float
    used_bulk_endpoint: bool
    symbols_fetched: int
    symbols_failed: int


class ScreenResponse(BaseModel):
    request_date: date
    total_symbols_screened: int
    total_qualifying_stocks: int
    results: List[ScreenResult]
    execution_time_ms: float
    performance_metrics: Optional[PerformanceMetrics] = None