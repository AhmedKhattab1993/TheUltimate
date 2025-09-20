"""
Models for combined screener and backtest results.
"""

from pydantic import BaseModel, ConfigDict
from typing import Dict, List, Optional
from uuid import UUID


class CombinedRow(BaseModel):
    """Row describing screener output paired with the latest backtest data."""

    screener_result_id: UUID
    screener_run_id: UUID
    symbol: str
    screener_created_at: str
    screener_metrics: Dict[str, object]
    filters: Dict[str, object]
    screener_metadata: Dict[str, object]
    run_id: Optional[UUID]
    run_created_at: Optional[str]
    run_status: Optional[str]
    strategy_name: Optional[str]
    backtest_parameters: Dict[str, object]
    backtest_metrics: Dict[str, object]

    model_config = ConfigDict(from_attributes=True)


class CombinedResponse(BaseModel):
    """Paginated response of combined screener/backtest records."""

    results: List[CombinedRow]
    total_count: int
    limit: int
    offset: int

    model_config = ConfigDict(from_attributes=True)
