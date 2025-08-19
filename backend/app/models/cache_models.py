"""
Pydantic models for caching system.

These models represent the structure of cache data for storing screener and backtest results
to avoid redundant computations. Updated to work with the new denormalized database schema.
"""

import hashlib
import json
from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, validator


class CachedScreenerRequest(BaseModel):
    """Model for screener request parameters used for cache key generation."""
    
    # Date range parameters
    start_date: date
    end_date: date
    
    # Price filters
    min_price: Optional[Decimal] = None
    max_price: Optional[Decimal] = None
    
    # Price vs MA filter (replaces above_sma20)
    price_vs_ma_enabled: bool = False
    price_vs_ma_period: Optional[int] = None
    price_vs_ma_condition: Optional[str] = None  # 'above' or 'below'
    
    # RSI filter
    rsi_enabled: bool = False
    rsi_period: Optional[int] = None
    rsi_threshold: Optional[Decimal] = None
    rsi_condition: Optional[str] = None  # 'above' or 'below'
    
    # Gap filter (enhanced with direction)
    gap_enabled: bool = False
    gap_threshold: Optional[Decimal] = None  # renamed from min_gap
    gap_direction: Optional[str] = None  # 'up', 'down', or 'any'
    
    # Previous day dollar volume filter (replaces min_volume)
    prev_day_dollar_volume_enabled: bool = False
    prev_day_dollar_volume: Optional[Decimal] = None
    
    # Relative volume filter
    relative_volume_enabled: bool = False
    relative_volume_recent_days: Optional[int] = None
    relative_volume_lookback_days: Optional[int] = None
    relative_volume_min_ratio: Optional[Decimal] = None
    
    def calculate_hash(self) -> str:
        """
        Calculate hash for screener parameters.
        
        Returns:
            SHA256 hash of the parameters
        """
        # Create a consistent dictionary representation
        data = {
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat()
            },
            'filters': {
                'min_price': float(self.min_price) if self.min_price is not None else None,
                'max_price': float(self.max_price) if self.max_price is not None else None,
                'price_vs_ma': {
                    'enabled': self.price_vs_ma_enabled,
                    'period': self.price_vs_ma_period,
                    'condition': self.price_vs_ma_condition
                },
                'rsi': {
                    'enabled': self.rsi_enabled,
                    'period': self.rsi_period,
                    'threshold': float(self.rsi_threshold) if self.rsi_threshold is not None else None,
                    'condition': self.rsi_condition
                },
                'gap': {
                    'enabled': self.gap_enabled,
                    'threshold': float(self.gap_threshold) if self.gap_threshold is not None else None,
                    'direction': self.gap_direction
                },
                'prev_day_dollar_volume': {
                    'enabled': self.prev_day_dollar_volume_enabled,
                    'value': float(self.prev_day_dollar_volume) if self.prev_day_dollar_volume is not None else None
                },
                'relative_volume': {
                    'enabled': self.relative_volume_enabled,
                    'recent_days': self.relative_volume_recent_days,
                    'lookback_days': self.relative_volume_lookback_days,
                    'min_ratio': float(self.relative_volume_min_ratio) if self.relative_volume_min_ratio is not None else None
                }
            }
        }
        # Sort keys to ensure consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()


class CachedScreenerResult(BaseModel):
    """Model for individual screener result stored in the database."""
    
    # Primary identification
    id: UUID = Field(default_factory=uuid4)
    
    # Stock identification
    symbol: str
    company_name: Optional[str] = None
    
    # Timestamps
    screened_at: datetime = Field(default_factory=datetime.utcnow)
    data_date: date
    
    # Filter parameters (denormalized for query performance)
    # Price filters
    filter_min_price: Optional[Decimal] = None
    filter_max_price: Optional[Decimal] = None
    
    # Price vs MA filter
    filter_price_vs_ma_enabled: bool = False
    filter_price_vs_ma_period: Optional[int] = None
    filter_price_vs_ma_condition: Optional[str] = None
    
    # RSI filter
    filter_rsi_enabled: bool = False
    filter_rsi_period: Optional[int] = None
    filter_rsi_threshold: Optional[Decimal] = None
    filter_rsi_condition: Optional[str] = None
    
    # Gap filter
    filter_gap_enabled: bool = False
    filter_gap_threshold: Optional[Decimal] = None
    filter_gap_direction: Optional[str] = None
    
    # Previous day dollar volume filter
    filter_prev_day_dollar_volume_enabled: bool = False
    filter_prev_day_dollar_volume: Optional[Decimal] = None
    
    # Relative volume filter
    filter_relative_volume_enabled: bool = False
    filter_relative_volume_recent_days: Optional[int] = None
    filter_relative_volume_lookback_days: Optional[int] = None
    filter_relative_volume_min_ratio: Optional[Decimal] = None
    
    # Session identification
    session_id: Optional[UUID] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class CachedBacktestRequest(BaseModel):
    """Model for backtest request parameters used for cache key generation."""
    
    # Symbol
    symbol: str
    
    # Strategy configuration
    strategy_name: str = Field(default="MarketStructure")
    
    # Date range
    start_date: date
    end_date: date
    
    # Algorithm parameters (new cache key parameters)
    initial_cash: Decimal = Field(gt=0)
    pivot_bars: int = Field(gt=0)
    lower_timeframe: str
    
    # Legacy parameters - kept for backward compatibility during transition
    holding_period: Optional[int] = None
    gap_threshold: Optional[Decimal] = None
    stop_loss: Optional[Decimal] = None
    take_profit: Optional[Decimal] = None
    
    def calculate_hash(self) -> str:
        """
        Calculate hash for backtest parameters using new cache key structure.
        
        Returns:
            SHA256 hash of the parameters
        """
        # Create a consistent dictionary representation using the 7 cache key parameters
        data = {
            'symbol': self.symbol,
            'strategy_name': self.strategy_name,
            'date_range': {
                'start': self.start_date.isoformat(),
                'end': self.end_date.isoformat()
            },
            'parameters': {
                'initial_cash': float(self.initial_cash),
                'pivot_bars': self.pivot_bars,
                'lower_timeframe': self.lower_timeframe
            }
        }
        # Sort keys to ensure consistent hashing
        json_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(json_str.encode()).hexdigest()
    
    def get_cache_hash(self) -> str:
        """Get the cache hash to use as backtest identifier."""
        return self.calculate_hash()


class CachedBacktestResult(BaseModel):
    """Model for backtest result stored in the database."""
    
    # Primary identification
    id: UUID = Field(default_factory=uuid4)
    
    # Backtest identification (now using cache hash)
    backtest_id: str
    symbol: str
    strategy_name: str
    
    # Algorithm parameters (new cache key parameters)
    initial_cash: Decimal
    pivot_bars: int
    lower_timeframe: str
    
    # Date range
    start_date: date
    end_date: date
    
    # Core performance metrics
    total_return: Decimal
    net_profit: Optional[Decimal] = None
    net_profit_currency: Optional[Decimal] = None
    compounding_annual_return: Optional[Decimal] = None
    final_value: Optional[Decimal] = None
    start_equity: Optional[Decimal] = None
    end_equity: Optional[Decimal] = None
    
    # Risk metrics
    sharpe_ratio: Optional[Decimal] = None
    sortino_ratio: Optional[Decimal] = None
    max_drawdown: Optional[Decimal] = None
    probabilistic_sharpe_ratio: Optional[Decimal] = None
    annual_standard_deviation: Optional[Decimal] = None
    annual_variance: Optional[Decimal] = None
    beta: Optional[Decimal] = None
    alpha: Optional[Decimal] = None
    
    # Trading statistics
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: Decimal
    loss_rate: Optional[Decimal] = None
    average_win: Optional[Decimal] = None
    average_loss: Optional[Decimal] = None
    profit_factor: Optional[Decimal] = None
    profit_loss_ratio: Optional[Decimal] = None
    expectancy: Optional[Decimal] = None
    total_orders: Optional[int] = None
    
    # Advanced metrics
    information_ratio: Optional[Decimal] = None
    tracking_error: Optional[Decimal] = None
    treynor_ratio: Optional[Decimal] = None
    total_fees: Optional[Decimal] = None
    estimated_strategy_capacity: Optional[Decimal] = None
    lowest_capacity_asset: Optional[str] = None
    portfolio_turnover: Optional[Decimal] = None
    
    # Strategy-specific metrics
    pivot_highs_detected: Optional[int] = None
    pivot_lows_detected: Optional[int] = None
    bos_signals_generated: Optional[int] = None
    position_flips: Optional[int] = None
    liquidation_events: Optional[int] = None
    
    # Execution metadata
    execution_time_ms: Optional[int] = None
    result_path: Optional[str] = None
    status: str = 'completed'
    error_message: Optional[str] = None
    cache_hit: Optional[bool] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @validator('win_rate', 'loss_rate')
    def validate_rate_percentages(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Rate percentages must be between 0 and 100')
        return v
    
    @validator('total_trades', 'winning_trades', 'losing_trades', 'total_orders', 
               'pivot_highs_detected', 'pivot_lows_detected', 'bos_signals_generated',
               'position_flips', 'liquidation_events')
    def validate_counts(cls, v):
        if v is not None and v < 0:
            raise ValueError('Count values cannot be negative')
        return v
    
    @validator('pivot_bars')
    def validate_pivot_bars(cls, v):
        if v <= 0:
            raise ValueError('pivot_bars must be greater than 0')
        return v
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat(),
            date: lambda v: v.isoformat()
        }


class CacheMetadata(BaseModel):
    """Model for tracking cache statistics."""
    
    id: UUID = Field(default_factory=uuid4)
    cache_type: str
    last_cleanup: Optional[datetime] = None
    total_hits: int = 0
    total_misses: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {
            UUID: lambda v: str(v),
            datetime: lambda v: v.isoformat()
        }


# Legacy model names for backwards compatibility
ScreenerResults = CachedScreenerResult
MarketStructureResults = CachedBacktestResult