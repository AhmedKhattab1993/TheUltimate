"""
Pydantic models for grid analysis results API.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
from datetime import datetime


class GridRunSummary(BaseModel):
    """Summary of a grid job execution."""

    run_id: str = Field(..., description="Unique identifier of the grid job")
    strategy_name: str = Field(..., description="Lean strategy that executed")
    status: str = Field(..., description="Final status of the job")
    job_type: str = Field(..., description="Job type emitted by the scheduler")
    created_at: datetime = Field(..., description="When the job was queued")
    started_at: Optional[datetime] = Field(None, description="When execution started")
    completed_at: Optional[datetime] = Field(None, description="When execution completed")
    duration_ms: Optional[float] = Field(None, description="Execution duration in milliseconds")
    target_count: int = Field(..., description="Number of symbol targets processed")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Numeric metrics tracked for the run")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata captured during the run")


class GridRunResult(BaseModel):
    """Per-symbol (or aggregate) result for a grid run."""

    symbol: Optional[str] = Field(None, description="Target symbol for the run")
    status: str = Field(..., description="Result status for the target")
    created_at: datetime = Field(..., description="When the result was recorded")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Parameters used for the backtest")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="Metrics returned by Lean")


class GridRunDetail(GridRunSummary):
    """Detailed view of a grid run including per-target metrics."""

    results: List[GridRunResult] = Field(default_factory=list, description="Per-target results")


class GridResultsListResponse(BaseModel):
    """Paginated list of grid result summaries."""
    results: List[GridRunSummary]
    total_count: int
    page: int
    page_size: int
