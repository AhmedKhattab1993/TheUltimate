"""
Simplified request models for the 3 basic trading filters.
"""

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FieldValidationInfo,
    field_validator,
    model_validator,
)
from datetime import date
from typing import Any, Dict, List, Optional
from enum import Enum


class NumericRange(BaseModel):
    """Generic numeric range shared by all filters."""

    min: float | None = Field(None, description="Inclusive lower bound")
    max: float | None = Field(None, description="Inclusive upper bound")
    step: float | None = Field(None, gt=0, description="Suggested increment when sweeping")

    @model_validator(mode="after")
    def ensure_bounds(cls, values: "NumericRange") -> "NumericRange":  # noqa: N805
        min_value = values.min
        max_value = values.max

        if min_value is None and max_value is None:
            raise ValueError("at least one of min or max must be provided")
        if min_value is not None and max_value is not None and min_value > max_value:
            raise ValueError("min cannot be greater than max")
        return values


class SimplePriceRangeParams(BaseModel):
    """Parameters for simple price range filter using OPEN price."""

    open_price: NumericRange = Field(
        default_factory=lambda: NumericRange(min=1.0, max=100.0),
        description="Range of acceptable opening prices",
    )


class MAPeriod(int, Enum):
    """Common moving average periods."""
    MA_20 = 20
    MA_50 = 50
    MA_200 = 200


class PriceVsMAParams(BaseModel):
    """Parameters for price vs moving average filter."""

    ma_period: int = Field(
        MAPeriod.MA_20,
        ge=2,
        le=200,
        description="Moving average period in days",
    )
    open_over_ma: NumericRange = Field(
        default_factory=lambda: NumericRange(min=1.0),
        description="Range for the open/MA ratio",
    )


class RSIParams(BaseModel):
    """Parameters for RSI filter."""
    rsi_period: int = Field(14, ge=2, le=50, description="RSI calculation period")
    rsi_value: NumericRange = Field(
        default_factory=lambda: NumericRange(max=30.0),
        description="Range of acceptable RSI values",
    )


class MinAverageVolumeParams(BaseModel):
    """Parameters for minimum average volume filter."""
    lookback_days: int = Field(20, ge=1, le=200, description="Number of days to calculate average volume")
    avg_volume: NumericRange = Field(
        default_factory=lambda: NumericRange(min=1_000_000),
        description="Allowed range for the rolling average volume",
    )


class MinAverageDollarVolumeParams(BaseModel):
    """Parameters for minimum average dollar volume filter."""
    lookback_days: int = Field(20, ge=1, le=200, description="Number of days to calculate average dollar volume")
    avg_dollar_volume: NumericRange = Field(
        default_factory=lambda: NumericRange(min=10_000_000),
        description="Allowed range for the rolling average dollar volume",
    )


class GapDirection(str, Enum):
    """Gap direction options."""

    UP = "up"
    DOWN = "down"
    BOTH = "both"


class GapParams(BaseModel):
    """Parameters for gap filter."""

    gap_percent: NumericRange = Field(
        default_factory=lambda: NumericRange(min=2.0),
        description="Allowed range for the absolute open gap percentage",
    )
    direction: GapDirection = Field(
        GapDirection.BOTH,
        description="Preferred gap direction when evaluating the range",
    )


class PreviousDayDollarVolumeParams(BaseModel):
    """Parameters for previous day dollar volume filter."""
    dollar_volume: NumericRange = Field(
        default_factory=lambda: NumericRange(min=10_000_000),
        description="Allowed range for yesterday's dollar volume",
    )


class RelativeVolumeParams(BaseModel):
    """Parameters for relative volume filter."""
    recent_days: int = Field(2, ge=1, le=10, description="Number of recent days for average")
    lookback_days: int = Field(20, ge=5, le=200, description="Number of historical days for average")
    ratio: NumericRange = Field(
        default_factory=lambda: NumericRange(min=1.5),
        description="Allowed range for the recent/long-term volume ratio",
    )
    
    @field_validator('lookback_days')
    @classmethod
    def validate_lookback_greater_than_recent(cls, v: int, info: FieldValidationInfo) -> int:
        recent_days = info.data.get('recent_days')
        if recent_days is not None and v <= recent_days:
            raise ValueError('lookback_days must be greater than recent_days')
        return v


class SimpleFilters(BaseModel):
    """Container for the 8 simple filters."""

    price_range: Optional[SimplePriceRangeParams] = Field(None, description="Filter by OPEN price range")
    price_vs_ma: Optional[List[PriceVsMAParams]] = Field(
        None, description="Filter by price vs moving average"
    )
    rsi: Optional[List[RSIParams]] = Field(None, description="Filter by RSI conditions")
    min_avg_volume: Optional[MinAverageVolumeParams] = Field(None, description="Filter by minimum average volume")
    min_avg_dollar_volume: Optional[MinAverageDollarVolumeParams] = Field(None, description="Filter by minimum average dollar volume")
    gap: Optional[GapParams] = Field(None, description="Filter by gap between open and previous close")
    prev_day_dollar_volume: Optional[PreviousDayDollarVolumeParams] = Field(
        None, description="Filter by previous day's dollar volume"
    )
    relative_volume: Optional[RelativeVolumeParams] = Field(
        None, description="Filter by relative volume ratio"
    )

    @field_validator("price_vs_ma", mode="before")
    @classmethod
    def _coerce_price_vs_ma(
        cls, value: Optional[Any]
    ) -> Optional[List[PriceVsMAParams]]:
        if value in (None, [], {}):
            return None
        if isinstance(value, list):
            return value
        return [value]

    @field_validator("rsi", mode="before")
    @classmethod
    def _coerce_rsi(
        cls, value: Optional[Any]
    ) -> Optional[List[RSIParams]]:
        if value in (None, [], {}):
            return None
        if isinstance(value, list):
            return value
        return [value]

    @model_validator(mode="after")
    def _normalize_lists(self) -> "SimpleFilters":  # noqa: N805
        if self.price_vs_ma and len(self.price_vs_ma) == 0:
            self.price_vs_ma = None
        if self.rsi and len(self.rsi) == 0:
            self.rsi = None
        return self


class RegistryFilterState(BaseModel):
    """Generic filter payload sent from the frontend registry."""

    enabled: bool = Field(False, description="Whether filter should be applied")
    values: Dict[str, Any] = Field(default_factory=dict, description="Raw control values")


class RegistryScreenRequest(BaseModel):
    """Wire model accepted by the API before hydration via the filter registry."""

    start_date: date
    end_date: date
    filters: Dict[str, RegistryFilterState]
    use_all_us_stocks: bool = Field(True, description="Whether to hydrate the full universe")
    enable_db_prefiltering: bool = Field(True, description="Use database-side pre-filtering when available")

    def build_simple_request(self, filters: SimpleFilters) -> "SimpleScreenRequest":
        """Convert hydrated filters into the legacy request type."""

        return SimpleScreenRequest(
            start_date=self.start_date,
            end_date=self.end_date,
            use_all_us_stocks=self.use_all_us_stocks,
            filters=filters,
            enable_db_prefiltering=self.enable_db_prefiltering,
        )

class SimpleScreenRequest(BaseModel):
    """Simplified screening request with 8 basic filters."""
    start_date: date = Field(..., description="Start date for screening")
    end_date: date = Field(..., description="End date for screening")
    use_all_us_stocks: bool = Field(True, description="Screen all US common stocks")
    filters: SimpleFilters = Field(..., description="Simple filter parameters")
    
    # Performance options
    enable_db_prefiltering: bool = Field(True, description="Use database pre-filtering where possible")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v, info: FieldValidationInfo):
        start_date = info.data.get('start_date')
        if start_date and v < start_date:
            raise ValueError('end_date must be on or after start_date')
        # Limit date range for performance
        if start_date:
            days = (v - start_date).days
            if days > 365:
                raise ValueError('Date range cannot exceed 365 days')
        return v
    
    @field_validator('filters')
    @classmethod
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
    
    model_config = ConfigDict()
