"""
Models for backtesting functionality.
"""

from datetime import date, datetime
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
from decimal import Decimal
from uuid import UUID
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FieldValidationInfo,
    field_validator,
    model_serializer,
)


def to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    components = string.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])


def _convert_for_json(value: Any) -> Any:
    """Recursively convert dataclasses to JSON-friendly primitives."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, list):
        return [_convert_for_json(item) for item in value]
    if isinstance(value, dict):
        return {key: _convert_for_json(val) for key, val in value.items()}
    return value


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
    lower_timeframe: str = Field("1min", description="Lower timeframe for analysis")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional strategy parameters")
    symbols: List[str] = Field(default_factory=list, description="Symbols to trade")
    use_screener_results: bool = Field(False, description="Use latest screener results for symbols")
    
    @field_validator('end_date')
    @classmethod
    def validate_date_range(cls, v: date, info: FieldValidationInfo) -> date:
        start_date = info.data.get('start_date')
        if start_date and v < start_date:
            raise ValueError('end_date must be on or after start_date')
        return v

    @field_validator('pivot_bars')
    @classmethod
    def validate_pivot_bars(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('pivot_bars must be greater than 0')
        return v

    @field_validator('initial_cash')
    @classmethod
    def validate_initial_cash(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('initial_cash must be greater than 0')
        return v

    @field_validator('lower_timeframe')
    @classmethod
    def validate_lower_timeframe(cls, v: str) -> str:
        valid_timeframes = ['1min', '5min', '10min']
        lowered = v.lower()
        if lowered not in valid_timeframes:
            raise ValueError(f'lower_timeframe must be one of: {", ".join(valid_timeframes)}')
        return lowered


class ScreenerBacktestRequest(BaseModel):
    """Request to run backtests for screener results."""
    strategy_name: str = Field(..., description="Name of the strategy to backtest")
    initial_cash: Decimal = Field(100000.0, gt=0, description="Initial cash amount")
    resolution: Literal["Tick", "Second", "Minute", "Hour", "Daily"] = Field("Minute", description="Data resolution")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Strategy parameters including pivot_bars")
    use_latest_ui_session: bool = Field(True, description="Use latest UI screener session")
    start_date: Optional[date] = Field(None, description="Start date for screener results (if not using latest session)")
    end_date: Optional[date] = Field(None, description="End date for screener results (if not using latest session)")
    
    @field_validator('initial_cash')
    @classmethod
    def validate_initial_cash(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError('initial_cash must be greater than 0')
        return v


class GridBacktestSweepRequest(BaseModel):
    """Parameter sweep definition for grid runs backed by the strategy registry."""

    base_request: BacktestRequest = Field(..., description="Seed request shared across sweeps")
    parameter_sweeps: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Parameter overrides merged onto the base request per job",
    )

    @field_validator("parameter_sweeps")
    @classmethod
    def validate_parameter_sweeps(
        cls, value: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        if not value:
            raise ValueError("parameter_sweeps must contain at least one entry")
        return value


class OptimizationParameterRange(BaseModel):
    """Value range for an optimization sweep parameter."""

    name: str = Field(..., description="Parameter name")
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")
    step: float = Field(..., gt=0, description="Increment between values")

    @field_validator("max")
    @classmethod
    def validate_range(cls, value: float, info: FieldValidationInfo) -> float:
        minimum = info.data.get("min")
        if minimum is not None and value < minimum:
            raise ValueError("max must be greater than or equal to min")
        return value


class OptimizationRequest(BaseModel):
    """Request payload for Lean optimization jobs."""

    base_request: BacktestRequest = Field(..., description="Seed request shared across optimization runs")
    target_metric: str = Field(..., description="Optimization target metric (e.g., SharpeRatio)")
    target_direction: Literal["maximize", "minimize"] = Field(
        "maximize", description="Optimization extremum"
    )
    parameters: List[OptimizationParameterRange] = Field(
        ..., description="Parameter ranges to explore"
    )
    max_concurrent_backtests: Optional[int] = Field(
        None,
        gt=0,
        description="Maximum number of parallel backtests to run during optimization",
    )

    @field_validator("parameters")
    @classmethod
    def ensure_parameters(cls, value: List[OptimizationParameterRange]) -> List[OptimizationParameterRange]:
        if not value:
            raise ValueError("parameters must contain at least one range")
        return value


class BacktestRunInfo(BaseModel):
    """Information about a running or queued backtest with enhanced metadata."""
    backtest_id: str = Field(..., description="Unique backtest identifier")
    status: BacktestStatus = Field(..., description="Current status")
    request: BacktestRequest = Field(..., description="Original request")
    job_type: str = Field("backtest", description="Type of Lean job (backtest/grid/optimize/data)")
    created_at: datetime = Field(..., description="When the backtest was created")
    started_at: Optional[datetime] = Field(None, description="When execution started")
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    container_id: Optional[str] = Field(None, description="Docker container ID")
    result_path: Optional[str] = Field(None, description="Path to results if completed")
    cache_hit: Optional[bool] = Field(None, description="Whether result was retrieved from cache")
    metrics: Optional[Dict[str, Decimal]] = Field(
        None, description="Numeric metrics captured for this run"
    )
    targets: Optional[List[str]] = Field(
        None, description="Symbol targets that were part of this run"
    )
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
    
    @field_validator(
        'win_rate',
        'loss_rate',
    )
    @classmethod
    def validate_rate_percentages(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Rate percentages must be between 0 and 100')
        return v

    @field_validator(
        'total_orders',
        'total_trades',
        'winning_trades',
        'losing_trades',
        'pivot_highs_detected',
        'pivot_lows_detected',
        'bos_signals_generated',
        'position_flips',
        'liquidation_events',
    )
    @classmethod
    def validate_counts(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError('Count values cannot be negative')
        return v

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra='ignore',  # Ignore unknown fields from historical data
        json_schema_extra={
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
        },
    )

    @model_serializer(mode='wrap')
    def serialize_model(self, handler):
        data = handler(self)
        return _convert_for_json(data)


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
    
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )

    @model_serializer(mode='wrap')
    def serialize_model(self, handler):
        data = handler(self)
        return _convert_for_json(data)


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
    
    @field_validator('win_rate', 'loss_rate')
    @classmethod
    def validate_rate_percentages(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Rate percentages must be between 0 and 100')
        return v

    @field_validator(
        'total_trades',
        'winning_trades',
        'losing_trades',
        'total_orders',
        'pivot_highs_detected',
        'pivot_lows_detected',
        'bos_signals_generated',
        'position_flips',
        'liquidation_events',
        'execution_time_ms',
    )
    @classmethod
    def validate_counts(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v < 0:
            raise ValueError('Count and time values cannot be negative')
        return v

    @field_validator('pivot_bars')
    @classmethod
    def validate_pivot_bars(cls, v: int) -> int:
        if v <= 0:
            raise ValueError('pivot_bars must be greater than 0')
        return v

    @field_validator('initial_cash', 'final_value', 'start_equity', 'end_equity')
    @classmethod
    def validate_monetary_values(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        if v is not None and v < 0:
            raise ValueError('Monetary values cannot be negative')
        return v

    @model_serializer(mode='wrap')
    def serialize_model(self, handler):
        data = handler(self)
        return _convert_for_json(data)


class BacktestListResponse(BaseModel):
    """Paginated response for recent backtest runs."""
    runs: List[BacktestRunInfo] = Field(..., description="Recent backtest runs")
    total_count: int = Field(..., description="Total number of results")
    page: int = Field(1, description="Current page")
    page_size: int = Field(20, description="Results per page")

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


class JobTypeSummary(BaseModel):
    """Aggregated counts per job type."""

    job_type: str
    total_runs: int
    completed_runs: int
    failed_runs: int
    last_run_id: Optional[str] = None
    last_run_at: Optional[datetime] = None


class MetricSummary(BaseModel):
    """Best metric per job type."""

    job_type: str
    metric_key: str
    metric_value: Decimal
    run_id: str
    strategy_name: str
    created_at: datetime


class TargetSummary(BaseModel):
    """Aggregated target counts per job type."""

    job_type: str
    target_count: int


class RunSummaryResponse(BaseModel):
    """Summary combining counts, metrics, and targets."""

    job_types: List[JobTypeSummary] = Field(default_factory=list)
    metrics: List[MetricSummary] = Field(default_factory=list)
    targets: List[TargetSummary] = Field(default_factory=list)
