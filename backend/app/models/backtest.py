"""
Models for backtesting functionality.
"""

from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from decimal import Decimal
from uuid import UUID


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


class BacktestStatus(str, Enum):
    """Status of a backtest run."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StrategyInfo(BaseModel):
    """Information about a LEAN strategy."""
    name: str = Field(..., description="Strategy name")
    file_path: str = Field(..., description="Path to strategy file")
    description: Optional[str] = Field(None, description="Strategy description")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Available strategy parameters")
    last_modified: Optional[datetime] = Field(None, description="Last modification time")


class BacktestRequest(BaseModel):
    """Request to run a backtest."""
    strategy_name: str = Field(..., description="Name of the strategy to backtest")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    initial_cash: Decimal = Field(100000.0, gt=0, description="Initial cash amount")
    resolution: Literal["Tick", "Second", "Minute", "Hour", "Daily"] = Field("Minute", description="Data resolution")
    pivot_bars: int = Field(5, gt=0, description="Number of bars for pivot detection")
    lower_timeframe: str = Field("5min", description="Lower timeframe for analysis")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional strategy parameters")
    symbols: List[str] = Field(default_factory=list, description="Symbols to trade")
    use_screener_results: bool = Field(False, description="Use latest screener results for symbols")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be on or after start_date')
        return v
    
    @validator('pivot_bars')
    def validate_pivot_bars(cls, v):
        if v <= 0:
            raise ValueError('pivot_bars must be greater than 0')
        return v
    
    @validator('initial_cash')
    def validate_initial_cash(cls, v):
        if v <= 0:
            raise ValueError('initial_cash must be greater than 0')
        return v
    
    @validator('lower_timeframe')
    def validate_lower_timeframe(cls, v):
        valid_timeframes = ['1min', '5min', '15min', '30min', '1hour', '4hour', 'daily']
        if v.lower() not in valid_timeframes:
            raise ValueError(f'lower_timeframe must be one of: {", ".join(valid_timeframes)}')
        return v.lower()


class ScreenerBacktestRequest(BaseModel):
    """Request to run backtests for screener results."""
    strategy_name: str = Field(..., description="Name of the strategy to backtest")
    initial_cash: Decimal = Field(100000.0, gt=0, description="Initial cash amount")
    resolution: Literal["Tick", "Second", "Minute", "Hour", "Daily"] = Field("Minute", description="Data resolution")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Strategy parameters including pivot_bars")
    use_latest_ui_session: bool = Field(True, description="Use latest UI screener session")
    start_date: Optional[date] = Field(None, description="Start date for screener results (if not using latest session)")
    end_date: Optional[date] = Field(None, description="End date for screener results (if not using latest session)")
    
    @validator('initial_cash')
    def validate_initial_cash(cls, v):
        if v <= 0:
            raise ValueError('initial_cash must be greater than 0')
        return v


class BacktestRunInfo(BaseModel):
    """Information about a running or queued backtest with enhanced metadata."""
    backtest_id: str = Field(..., description="Unique backtest identifier")
    status: BacktestStatus = Field(..., description="Current status")
    request: BacktestRequest = Field(..., description="Original request")
    created_at: datetime = Field(..., description="When the backtest was created")
    started_at: Optional[datetime] = Field(None, description="When execution started")
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    container_id: Optional[str] = Field(None, description="Docker container ID")
    result_path: Optional[str] = Field(None, description="Path to results if completed")
    cache_hit: Optional[bool] = Field(None, description="Whether result was retrieved from cache")
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")


class BacktestProgress(BaseModel):
    """Real-time progress update for a running backtest."""
    backtest_id: str
    status: BacktestStatus
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    current_date: Optional[date] = None
    log_entries: List[str] = Field(default_factory=list)
    statistics: Optional[Dict[str, Any]] = None


class BacktestStatistics(BaseModel):
    """Comprehensive statistics from a backtest result."""
    # Core Performance Metrics - REQUIRED fields (only the most essential)
    total_return: Decimal = Field(..., description="Total return percentage")
    net_profit: Decimal = Field(..., description="Net profit percentage")
    net_profit_currency: Decimal = Field(..., description="Net profit in currency")
    final_value: Decimal = Field(..., description="Final portfolio value")
    
    # Core Performance Metrics - OPTIONAL fields with defaults
    compounding_annual_return: Decimal = Field(default=0.0, description="Compounding annual return percentage")
    start_equity: Decimal = Field(default=100000.0, description="Starting equity")
    end_equity: Decimal = Field(default=0.0, description="Ending equity")
    
    # Risk Metrics - All OPTIONAL with defaults
    sharpe_ratio: Decimal = Field(default=0.0, description="Sharpe ratio")
    sortino_ratio: Decimal = Field(default=0.0, description="Sortino ratio")
    max_drawdown: Decimal = Field(default=0.0, description="Maximum drawdown percentage")
    probabilistic_sharpe_ratio: Decimal = Field(default=0.0, description="Probabilistic Sharpe ratio percentage")
    annual_standard_deviation: Decimal = Field(default=0.0, description="Annual standard deviation")
    annual_variance: Decimal = Field(default=0.0, description="Annual variance")
    beta: Decimal = Field(default=0.0, description="Beta coefficient")
    alpha: Decimal = Field(default=0.0, description="Alpha coefficient")
    
    # Trading Statistics - All OPTIONAL with defaults
    total_orders: int = Field(default=0, description="Total number of orders")
    total_trades: int = Field(default=0, description="Total number of completed trades")
    winning_trades: int = Field(default=0, description="Number of winning trades")
    losing_trades: int = Field(default=0, description="Number of losing trades")
    win_rate: Decimal = Field(default=0.0, description="Win rate percentage")
    loss_rate: Decimal = Field(default=0.0, description="Loss rate percentage")
    average_win: Decimal = Field(default=0.0, description="Average winning trade percentage")
    average_loss: Decimal = Field(default=0.0, description="Average losing trade percentage")
    average_win_currency: Optional[Decimal] = Field(default=None, description="Average winning trade in currency")
    average_loss_currency: Optional[Decimal] = Field(default=None, description="Average losing trade in currency")
    profit_factor: Decimal = Field(default=0.0, description="Profit factor")
    profit_loss_ratio: Decimal = Field(default=0.0, description="Profit-Loss ratio")
    expectancy: Decimal = Field(default=0.0, description="Expected value of a trade")
    expectancy_currency: Optional[Decimal] = Field(default=None, description="Expected value of a trade in currency")
    
    # Advanced Metrics - All OPTIONAL with defaults
    information_ratio: Decimal = Field(default=0.0, description="Information ratio")
    tracking_error: Decimal = Field(default=0.0, description="Tracking error")
    treynor_ratio: Decimal = Field(default=0.0, description="Treynor ratio")
    total_fees: Decimal = Field(default=0.0, description="Total fees paid")
    estimated_strategy_capacity: Decimal = Field(default=0.0, description="Estimated strategy capacity")
    lowest_capacity_asset: str = Field(default="", description="Lowest capacity asset")
    portfolio_turnover: Decimal = Field(default=0.0, description="Portfolio turnover percentage")
    
    # Strategy-Specific Metrics
    pivot_highs_detected: Optional[int] = Field(None, description="Number of pivot highs detected")
    pivot_lows_detected: Optional[int] = Field(None, description="Number of pivot lows detected")
    bos_signals_generated: Optional[int] = Field(None, description="Number of break of structure signals generated")
    position_flips: Optional[int] = Field(None, description="Number of position flips")
    liquidation_events: Optional[int] = Field(None, description="Number of liquidation events")
    
    @validator('win_rate', 'loss_rate')
    def validate_rate_percentages(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Rate percentages must be between 0 and 100')
        return v
    
    @validator('total_orders', 'total_trades', 'winning_trades', 'losing_trades',
               'pivot_highs_detected', 'pivot_lows_detected', 'bos_signals_generated',
               'position_flips', 'liquidation_events')
    def validate_counts(cls, v):
        if v is not None and v < 0:
            raise ValueError('Count values cannot be negative')
        return v
    
    class Config:
        alias_generator = to_camel
        populate_by_name = True
        extra = "ignore"  # Ignore unknown fields from historical data
        json_encoders = {
            Decimal: lambda v: float(v)
        }
        json_schema_extra = {
            "example": {
                "totalReturn": -20.401,
                "netProfit": -20.401,
                "netProfitCurrency": -20401.03,
                "compoundingAnnualReturn": -13.256,
                "finalValue": 79598.97,
                "startEquity": 100000,
                "endEquity": 79598.97,
                "sharpeRatio": -0.591,
                "sortinoRatio": -0.764,
                "maxDrawdown": 35.800,
                "probabilisticSharpeRatio": 2.023,
                "annualStandardDeviation": 0.215,
                "annualVariance": 0.046,
                "beta": 0,
                "alpha": 0,
                "totalOrders": 797,
                "totalTrades": 797,
                "winningTrades": 263,
                "losingTrades": 534,
                "winRate": 33.0,
                "lossRate": 67.0,
                "averageWin": 1.62,
                "averageLoss": -0.87,
                "profitFactor": 1.85,
                "profitLossRatio": 1.85,
                "expectancy": -0.061,
                "informationRatio": -0.336,
                "trackingError": 0.215,
                "treynorRatio": 0,
                "totalFees": 1692.39,
                "estimatedStrategyCapacity": 1000000.00,
                "lowestCapacityAsset": "AAPL R735QTJ8XC9X",
                "portfolioTurnover": 129.06,
                "pivotHighsDetected": 45,
                "pivotLowsDetected": 42,
                "bosSignalsGenerated": 87,
                "positionFlips": 15,
                "liquidationEvents": 0
            }
        }


class BacktestResult(BaseModel):
    """Complete backtest result with enhanced metadata."""
    # Core Identifiers
    backtest_id: str = Field(..., description="Unique backtest identifier")
    symbol: str = Field(..., description="Symbol that was backtested")
    strategy_name: str = Field(..., description="Strategy that was tested")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    
    # Algorithm Parameters
    initial_cash: Decimal = Field(..., description="Initial cash amount")
    resolution: str = Field(..., description="Data resolution used")
    pivot_bars: int = Field(..., description="Number of bars for pivot detection")
    lower_timeframe: str = Field(..., description="Lower timeframe used for analysis")
    
    # Core Results
    final_value: Decimal = Field(..., description="Final portfolio value")
    statistics: BacktestStatistics = Field(..., description="Comprehensive performance statistics")
    
    # Execution Metadata
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    result_path: Optional[str] = Field(None, description="Path to full result files")
    status: str = Field("completed", description="Backtest execution status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    cache_hit: Optional[bool] = Field(None, description="Whether result was retrieved from cache")
    
    # Optional detailed data
    orders: Optional[List[Dict[str, Any]]] = Field(None, description="List of orders/trades")
    equity_curve: Optional[List[Dict[str, Any]]] = Field(None, description="Equity curve data")
    
    # Timestamps
    created_at: datetime = Field(..., description="When the backtest was run")
    
    class Config:
        alias_generator = to_camel
        populate_by_name = True
        json_encoders = {
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }


class DatabaseBacktestResult(BaseModel):
    """Database model for backtest results matching the market_structure_results table schema."""
    # Core Identifiers
    id: Optional[UUID] = Field(None, description="Primary key")
    backtest_id: UUID = Field(..., description="Unique backtest identifier")
    symbol: str = Field(..., description="Stock symbol")
    strategy_name: str = Field(..., description="Strategy name")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    
    # Algorithm Parameters
    initial_cash: Decimal = Field(..., description="Starting capital")
    resolution: str = Field(..., description="Data resolution")
    pivot_bars: int = Field(..., description="Bars for pivot detection")
    lower_timeframe: str = Field(..., description="Analysis timeframe")
    
    # Core Performance Results
    total_return: Decimal = Field(..., description="Total return percentage")
    net_profit: Decimal = Field(..., description="Net profit percentage")
    net_profit_currency: Decimal = Field(..., description="Net profit in currency")
    compounding_annual_return: Decimal = Field(..., description="Compounding annual return")
    final_value: Decimal = Field(..., description="Final portfolio value")
    start_equity: Decimal = Field(..., description="Starting equity")
    end_equity: Decimal = Field(..., description="Ending equity")
    
    # Risk Metrics
    sharpe_ratio: Decimal = Field(..., description="Sharpe ratio")
    sortino_ratio: Decimal = Field(..., description="Sortino ratio")
    max_drawdown: Decimal = Field(..., description="Maximum drawdown percentage")
    probabilistic_sharpe_ratio: Optional[Decimal] = Field(None, description="Probabilistic Sharpe ratio")
    annual_standard_deviation: Optional[Decimal] = Field(None, description="Annual standard deviation")
    annual_variance: Optional[Decimal] = Field(None, description="Annual variance")
    beta: Optional[Decimal] = Field(None, description="Beta coefficient")
    alpha: Optional[Decimal] = Field(None, description="Alpha coefficient")
    
    # Trading Statistics
    total_trades: int = Field(..., description="Total number of trades")
    winning_trades: int = Field(..., description="Number of winning trades")
    losing_trades: int = Field(..., description="Number of losing trades")
    win_rate: Decimal = Field(..., description="Win rate percentage")
    loss_rate: Optional[Decimal] = Field(None, description="Loss rate percentage")
    average_win: Optional[Decimal] = Field(None, description="Average winning trade")
    average_loss: Optional[Decimal] = Field(None, description="Average losing trade")
    profit_factor: Decimal = Field(..., description="Profit factor")
    profit_loss_ratio: Optional[Decimal] = Field(None, description="Profit-Loss ratio")
    expectancy: Optional[Decimal] = Field(None, description="Expected value per trade")
    total_orders: Optional[int] = Field(None, description="Total number of orders")
    
    # Advanced Metrics
    information_ratio: Optional[Decimal] = Field(None, description="Information ratio")
    tracking_error: Optional[Decimal] = Field(None, description="Tracking error")
    treynor_ratio: Optional[Decimal] = Field(None, description="Treynor ratio")
    total_fees: Optional[Decimal] = Field(None, description="Total fees paid")
    estimated_strategy_capacity: Optional[Decimal] = Field(None, description="Estimated strategy capacity")
    lowest_capacity_asset: Optional[str] = Field(None, description="Lowest capacity asset")
    portfolio_turnover: Optional[Decimal] = Field(None, description="Portfolio turnover")
    
    # Strategy-Specific Metrics
    pivot_highs_detected: Optional[int] = Field(None, description="Pivot highs detected")
    pivot_lows_detected: Optional[int] = Field(None, description="Pivot lows detected")
    bos_signals_generated: Optional[int] = Field(None, description="Break of structure signals")
    position_flips: Optional[int] = Field(None, description="Position flips")
    liquidation_events: Optional[int] = Field(None, description="Liquidation events")
    
    # Execution Metadata
    execution_time_ms: Optional[int] = Field(None, description="Execution time in milliseconds")
    result_path: Optional[str] = Field(None, description="Path to result files")
    status: str = Field("completed", description="Execution status")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    cache_hit: Optional[bool] = Field(None, description="Whether result was from cache")
    created_at: Optional[datetime] = Field(None, description="When the result was created")
    
    @validator('win_rate', 'loss_rate')
    def validate_rate_percentages(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Rate percentages must be between 0 and 100')
        return v
    
    @validator('total_trades', 'winning_trades', 'losing_trades', 'total_orders',
               'pivot_highs_detected', 'pivot_lows_detected', 'bos_signals_generated',
               'position_flips', 'liquidation_events', 'execution_time_ms')
    def validate_counts(cls, v):
        if v is not None and v < 0:
            raise ValueError('Count and time values cannot be negative')
        return v
    
    @validator('pivot_bars')
    def validate_pivot_bars(cls, v):
        if v <= 0:
            raise ValueError('pivot_bars must be greater than 0')
        return v
    
    @validator('initial_cash', 'final_value', 'start_equity', 'end_equity')
    def validate_monetary_values(cls, v):
        if v is not None and v < 0:
            raise ValueError('Monetary values cannot be negative')
        return v
    
    class Config:
        json_encoders = {
            Decimal: lambda v: float(v),
            UUID: lambda v: str(v),
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat()
        }


class BacktestListResponse(BaseModel):
    """Response containing list of backtest results."""
    results: List[BacktestResult] = Field(..., description="List of backtest results")
    total_count: int = Field(..., description="Total number of results")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Results per page")
    
    class Config:
        alias_generator = to_camel
        populate_by_name = True