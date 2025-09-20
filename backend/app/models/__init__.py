"""Models package for the application."""

from .stock import StockData, StockBar
from .backtest import (
    BacktestRequest, BacktestResult, BacktestStatus, 
    BacktestStatistics, BacktestRunInfo, BacktestProgress,
    DatabaseBacktestResult, BacktestListResponse, StrategyInfo,
    GridBacktestSweepRequest, OptimizationParameterRange, OptimizationRequest,
    JobTypeSummary, MetricSummary, TargetSummary, RunSummaryResponse,
)
from .ingestion import DataIngestionRequest
from .simple_requests import (
    RegistryFilterState,
    RegistryScreenRequest,
    SimpleScreenRequest,
    SimplePriceRangeParams,
    GapParams,
    PreviousDayDollarVolumeParams,
    RelativeVolumeParams,
    SimpleFilters
)
from .cache_models import (
    ScreenerResults, MarketStructureResults, CacheMetadata,
    CachedScreenerRequest, CachedScreenerResult,
    CachedBacktestRequest, CachedBacktestResult
)

__all__ = [
    # Stock models
    'StockData',
    'StockBar',
    
    # Backtest models
    'BacktestRequest',
    'BacktestResult',
    'BacktestStatus',
    'BacktestStatistics',
    'BacktestRunInfo',
    'BacktestProgress',
    'DatabaseBacktestResult',
    'BacktestListResponse',
    'StrategyInfo',
    'GridBacktestSweepRequest',
    'OptimizationParameterRange',
    'OptimizationRequest',
    'JobTypeSummary',
    'MetricSummary',
    'TargetSummary',
    'RunSummaryResponse',
    'DataIngestionRequest',
    
    # Simple request models
    'RegistryFilterState',
    'RegistryScreenRequest',
    'SimpleScreenRequest',
    'SimplePriceRangeParams',
    'GapParams',
    'PreviousDayDollarVolumeParams',
    'RelativeVolumeParams',
    'SimpleFilters',
    
    # Cache models
    'ScreenerResults',
    'MarketStructureResults',
    'CacheMetadata',
    'CachedScreenerRequest',
    'CachedScreenerResult',
    'CachedBacktestRequest',
    'CachedBacktestResult'
]
