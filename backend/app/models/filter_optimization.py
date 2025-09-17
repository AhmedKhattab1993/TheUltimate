"""
Models for filter optimization analysis.
"""

from pydantic import BaseModel
from typing import List, Dict, Optional, Union, Literal, Any
from datetime import date
from enum import Enum


class OptimizationTarget(str, Enum):
    """Target metrics for optimization"""
    SHARPE_RATIO = "sharpe_ratio"
    TOTAL_RETURN = "total_return"
    WIN_RATE = "win_rate"
    PROFIT_FACTOR = "profit_factor"
    MIN_DRAWDOWN = "min_drawdown"
    CUSTOM = "custom"


class FilterRange(BaseModel):
    """Range configuration for a filter parameter"""
    min_value: float
    max_value: float
    step: float
    

class FilterSearchSpace(BaseModel):
    """Search space for all filter parameters"""
    # Price range filter (sliding window approach)
    price_range: Optional[FilterRange] = None
    
    # RSI filter (sliding window approach)
    rsi_range: Optional[FilterRange] = None
    
    # Gap filter (sliding window approach)
    gap_range: Optional[FilterRange] = None
    
    # Volume filters (sliding window approach)
    volume_range: Optional[FilterRange] = None
    rel_volume_range: Optional[FilterRange] = None
    
    # Pivot bars (sliding window approach)
    pivot_bars_range: Optional[FilterRange] = None
    
    # MA filters (discrete choices)
    ma_periods: Optional[List[int]] = None
    ma_conditions: Optional[List[str]] = None
    

class OptimizationRequest(BaseModel):
    """Request for filter optimization"""
    start_date: date
    end_date: date
    target: OptimizationTarget
    custom_formula: Optional[str] = None  # For custom target
    search_space: FilterSearchSpace
    max_results: int = 50
    min_symbols_required: int = 10  # Minimum symbols that must pass filter
    pivot_bars: Optional[int] = None  # Specific pivot_bars to analyze
    

class FilterCombination(BaseModel):
    """A specific combination of filter values"""
    price_range: Optional[Dict[str, float]] = None
    rsi_range: Optional[Dict[str, float]] = None
    gap_range: Optional[Dict[str, float]] = None
    volume_min: Optional[float] = None
    rel_volume_min: Optional[float] = None
    ma_condition: Optional[Dict[str, Union[int, str]]] = None
    

class OptimizationResult(BaseModel):
    """Result for a single filter combination"""
    rank: int
    filter_combination: FilterCombination
    
    # Performance metrics
    avg_sharpe_ratio: float
    avg_total_return: float
    avg_win_rate: float
    avg_profit_factor: float
    avg_max_drawdown: float
    
    # Additional statistics
    total_symbols_matched: int
    total_backtests: int
    target_score: float  # Score based on optimization target
    
    # Sample stocks that passed this filter
    sample_symbols: List[str]
    

class OptimizationResponse(BaseModel):
    """Response containing optimization results"""
    request_summary: Dict[str, Any]
    results: List[OptimizationResult]
    total_combinations_tested: int
    execution_time_ms: int
    
    # Analysis metadata
    date_range_analyzed: Dict[str, str]
    optimization_target: str
    
    # Best performing combination
    best_combination: Optional[OptimizationResult] = None