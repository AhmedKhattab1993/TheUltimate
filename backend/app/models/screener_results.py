"""
Models for screener results API endpoints.
"""

from pydantic import BaseModel, Field
from datetime import datetime
from typing import List, Dict, Any, Optional


class ScreenerResultSummary(BaseModel):
    """Summary of a screener result for list views."""
    id: str = Field(..., description="Unique identifier for the result")
    timestamp: str = Field(..., description="ISO format timestamp when screening was performed")
    symbol_count: int = Field(..., description="Number of symbols that passed the filters")
    filters: Dict[str, Any] = Field(..., description="Filters used in the screening")
    execution_time_ms: float = Field(0, description="Execution time in milliseconds")
    total_symbols_screened: int = Field(0, description="Total number of symbols screened")


class SymbolMetrics(BaseModel):
    """Metrics for a single symbol in screener results."""
    symbol: str = Field(..., description="Stock symbol")
    latest_price: Optional[float] = Field(None, description="Latest closing price")
    latest_volume: Optional[int] = Field(None, description="Latest trading volume")
    # Can be extended with more metrics as needed


class ScreenerResultDetail(BaseModel):
    """Detailed screener result including all symbols."""
    id: str = Field(..., description="Unique identifier for the result")
    timestamp: str = Field(..., description="ISO format timestamp when screening was performed")
    symbol_count: int = Field(..., description="Number of symbols that passed the filters")
    filters: Dict[str, Any] = Field(..., description="Filters used in the screening")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    symbols: List[SymbolMetrics] = Field(..., description="List of symbols with their metrics")


class ScreenerResultsListResponse(BaseModel):
    """Paginated response for screener results list."""
    results: List[ScreenerResultSummary] = Field(..., description="List of screener result summaries")
    total_count: int = Field(..., description="Total number of results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of results per page")