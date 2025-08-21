"""
Models for combined screener and backtest results.
"""

from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID


class CombinedScreenerBacktestRow(BaseModel):
    """Single row representing combined screener and backtest data."""
    
    # Screener columns
    screener_session_id: Optional[UUID]
    screening_date: Optional[str]  # Data date
    source: Optional[str]
    symbol: str
    company_name: Optional[str]
    screened_at: Optional[str]  # Created date/timestamp
    
    # All screener filter parameters
    filter_min_price: Optional[float]
    filter_max_price: Optional[float]
    filter_price_vs_ma_enabled: bool = False
    filter_price_vs_ma_period: Optional[int]
    filter_price_vs_ma_condition: Optional[str]
    filter_rsi_enabled: bool = False
    filter_rsi_period: Optional[int]
    filter_rsi_threshold: Optional[float]
    filter_rsi_condition: Optional[str]
    filter_gap_enabled: bool = False
    filter_gap_threshold: Optional[float]
    filter_gap_direction: Optional[str]
    filter_prev_day_dollar_volume_enabled: bool = False
    filter_prev_day_dollar_volume: Optional[float]
    filter_relative_volume_enabled: bool = False
    filter_relative_volume_recent_days: Optional[int]
    filter_relative_volume_lookback_days: Optional[int]
    filter_relative_volume_min_ratio: Optional[float]
    
    # Backtest columns
    backtest_id: Optional[str]
    backtest_created_at: Optional[str]  # Created date
    strategy_name: Optional[str]  # Strategy name
    cache_hit: Optional[bool]
    backtest_start_date: Optional[str]
    backtest_end_date: Optional[str]
    
    # All backtest performance metrics
    total_return: Optional[float]
    net_profit: Optional[float]
    net_profit_currency: Optional[float]
    compounding_annual_return: Optional[float]
    final_value: Optional[float]
    start_equity: Optional[float]
    end_equity: Optional[float]
    
    # Risk metrics
    sharpe_ratio: Optional[float]
    sortino_ratio: Optional[float]
    max_drawdown: Optional[float]
    probabilistic_sharpe_ratio: Optional[float]
    annual_standard_deviation: Optional[float]
    annual_variance: Optional[float]
    beta: Optional[float]
    alpha: Optional[float]
    
    # Trading statistics
    total_trades: Optional[int]
    winning_trades: Optional[int]
    losing_trades: Optional[int]
    win_rate: Optional[float]
    loss_rate: Optional[float]
    average_win: Optional[float]
    average_loss: Optional[float]
    profit_factor: Optional[float]
    profit_loss_ratio: Optional[float]
    expectancy: Optional[float]
    total_orders: Optional[int]
    
    # Advanced metrics
    information_ratio: Optional[float]
    tracking_error: Optional[float]
    treynor_ratio: Optional[float]
    total_fees: Optional[float]
    estimated_strategy_capacity: Optional[float]
    lowest_capacity_asset: Optional[str]
    portfolio_turnover: Optional[float]
    
    # Strategy-specific metrics
    pivot_highs_detected: Optional[int]
    pivot_lows_detected: Optional[int]
    bos_signals_generated: Optional[int]
    position_flips: Optional[int]
    liquidation_events: Optional[int]
    
    # Algorithm parameters
    initial_cash: Optional[float]
    pivot_bars: Optional[int]
    lower_timeframe: Optional[str]
    
    class Config:
        from_attributes = True


class CombinedScreenerBacktestResponse(BaseModel):
    """Response model for combined screener and backtest results."""
    
    results: List[CombinedScreenerBacktestRow]
    total_count: int
    limit: int
    offset: int
    
    class Config:
        from_attributes = True