"""
Pydantic models for grid analysis results API.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import date, datetime


class GridScreeningResult(BaseModel):
    """Individual screening result for a symbol."""
    symbol: str
    price: float
    ma_20: float
    ma_50: float
    ma_200: float
    rsi_14: float
    gap_percent: float
    prev_day_dollar_volume: float
    relative_volume: float


class GridMarketStructureResult(BaseModel):
    """Individual market structure backtest result."""
    symbol: str
    pivot_bars: int
    status: str
    total_return: float = Field(description="Total net profit from backtest")
    sharpe_ratio: float
    max_drawdown: float
    win_rate: float
    total_trades: int
    backtest_id: Optional[str] = None


class GridResultSummary(BaseModel):
    """Summary of grid results for a date."""
    date: date
    screening_symbols: int = Field(description="Number of symbols screened")
    backtest_count: int = Field(description="Total number of backtests")
    backtest_completed: int = Field(description="Number of completed backtests")
    backtest_failed: int = Field(description="Number of failed backtests")
    screening_time_ms: Optional[float] = Field(None, description="Time to complete screening in ms")
    backtest_time_ms: Optional[float] = Field(None, description="Time to complete all backtests in ms")


class GridResultDetail(BaseModel):
    """Detailed grid results for a specific date."""
    date: date
    screening_results: List[GridScreeningResult]
    backtest_results: List[GridMarketStructureResult]
    total_screening_symbols: int
    total_backtests: int


class GridResultsListResponse(BaseModel):
    """Paginated list of grid result summaries."""
    results: List[GridResultSummary]
    total_count: int
    page: int
    page_size: int