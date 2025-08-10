"""
Models for backtesting functionality.
"""

from pydantic import BaseModel, Field, validator
from datetime import date, datetime
from typing import List, Optional, Dict, Any, Literal
from enum import Enum


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
    initial_cash: float = Field(100000.0, gt=0, description="Initial cash amount")
    parameters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Strategy parameters")
    symbols: List[str] = Field(default_factory=list, description="Symbols to trade")
    resolution: Literal["Tick", "Second", "Minute", "Hour", "Daily"] = Field("Minute", description="Data resolution")
    use_screener_results: bool = Field(False, description="Use latest screener results for symbols")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if 'start_date' in values and v < values['start_date']:
            raise ValueError('end_date must be on or after start_date')
        return v


class BacktestRunInfo(BaseModel):
    """Information about a running or queued backtest."""
    backtest_id: str = Field(..., description="Unique backtest identifier")
    status: BacktestStatus = Field(..., description="Current status")
    request: BacktestRequest = Field(..., description="Original request")
    created_at: datetime = Field(..., description="When the backtest was created")
    started_at: Optional[datetime] = Field(None, description="When execution started")
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    container_id: Optional[str] = Field(None, description="Docker container ID")
    result_path: Optional[str] = Field(None, description="Path to results if completed")


class BacktestProgress(BaseModel):
    """Real-time progress update for a running backtest."""
    backtest_id: str
    status: BacktestStatus
    progress_percentage: Optional[float] = Field(None, ge=0, le=100)
    current_date: Optional[date] = None
    log_entries: List[str] = Field(default_factory=list)
    statistics: Optional[Dict[str, Any]] = None


class BacktestStatistics(BaseModel):
    """Key statistics from a backtest result."""
    # Core Performance Metrics
    total_return: float = Field(..., description="Total return percentage")
    net_profit: float = Field(..., description="Net profit percentage")
    net_profit_currency: float = Field(..., description="Net profit in currency")
    compounding_annual_return: float = Field(..., description="Compounding annual return percentage")
    
    # Risk Metrics
    sharpe_ratio: float = Field(..., description="Sharpe ratio")
    sortino_ratio: float = Field(..., description="Sortino ratio")
    max_drawdown: float = Field(..., description="Maximum drawdown percentage")
    probabilistic_sharpe_ratio: float = Field(..., description="Probabilistic Sharpe ratio percentage")
    
    # Trading Statistics
    total_orders: int = Field(..., description="Total number of orders")
    total_trades: int = Field(..., description="Total number of completed trades")
    win_rate: float = Field(..., description="Win rate percentage")
    loss_rate: float = Field(..., description="Loss rate percentage")
    average_win: float = Field(..., description="Average winning trade percentage")
    average_loss: float = Field(..., description="Average losing trade percentage")
    average_win_currency: float = Field(..., description="Average winning trade in currency")
    average_loss_currency: float = Field(..., description="Average losing trade in currency")
    
    # Advanced Metrics
    profit_factor: float = Field(..., description="Profit factor")
    profit_loss_ratio: float = Field(..., description="Profit-Loss ratio")
    expectancy: float = Field(..., description="Expectancy")
    alpha: float = Field(..., description="Alpha")
    beta: float = Field(..., description="Beta")
    annual_standard_deviation: float = Field(..., description="Annual standard deviation")
    annual_variance: float = Field(..., description="Annual variance")
    information_ratio: float = Field(..., description="Information ratio")
    tracking_error: float = Field(..., description="Tracking error")
    treynor_ratio: float = Field(..., description="Treynor ratio")
    
    # Portfolio Information
    start_equity: float = Field(..., description="Starting equity")
    end_equity: float = Field(..., description="Ending equity")
    total_fees: float = Field(..., description="Total fees paid")
    estimated_strategy_capacity: float = Field(..., description="Estimated strategy capacity")
    lowest_capacity_asset: str = Field(..., description="Lowest capacity asset")
    portfolio_turnover: float = Field(..., description="Portfolio turnover percentage")
    
    class Config:
        alias_generator = to_camel
        populate_by_name = True
        schema_extra = {
            "example": {
                "totalReturn": -20.401,
                "netProfit": -20.401,
                "netProfitCurrency": -20401.03,
                "compoundingAnnualReturn": -13.256,
                "sharpeRatio": -0.591,
                "sortinoRatio": -0.764,
                "maxDrawdown": 35.800,
                "probabilisticSharpeRatio": 2.023,
                "totalOrders": 797,
                "totalTrades": 797,
                "winRate": 33.0,
                "lossRate": 67.0,
                "averageWin": 1.62,
                "averageLoss": -0.87,
                "averageWinCurrency": 125.50,
                "averageLossCurrency": -85.25,
                "profitFactor": 1.85,
                "profitLossRatio": 1.85,
                "expectancy": -0.061,
                "alpha": 0,
                "beta": 0,
                "annualStandardDeviation": 0.215,
                "annualVariance": 0.046,
                "informationRatio": -0.336,
                "trackingError": 0.215,
                "treynorRatio": 0,
                "startEquity": 100000,
                "endEquity": 79598.97,
                "totalFees": 1692.39,
                "estimatedStrategyCapacity": 1000000.00,
                "lowestCapacityAsset": "AAPL R735QTJ8XC9X",
                "portfolioTurnover": 129.06
            }
        }


class BacktestResult(BaseModel):
    """Complete backtest result."""
    backtest_id: str = Field(..., description="Unique backtest identifier")
    strategy_name: str = Field(..., description="Strategy that was tested")
    start_date: date = Field(..., description="Backtest start date")
    end_date: date = Field(..., description="Backtest end date")
    initial_cash: float = Field(..., description="Initial cash amount")
    final_value: float = Field(..., description="Final portfolio value")
    statistics: BacktestStatistics = Field(..., description="Performance statistics")
    orders: Optional[List[Dict[str, Any]]] = Field(None, description="List of orders/trades")
    equity_curve: Optional[List[Dict[str, Any]]] = Field(None, description="Equity curve data")
    created_at: datetime = Field(..., description="When the backtest was run")
    result_path: str = Field(..., description="Path to full result files")
    
    class Config:
        alias_generator = to_camel
        populate_by_name = True
        json_encoders = {
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