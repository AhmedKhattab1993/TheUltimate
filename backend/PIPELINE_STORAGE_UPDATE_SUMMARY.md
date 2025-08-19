# Pipeline Storage Update Summary

## Overview
Updated the pipeline storage logic to work with the new column-based database schema, moving away from JSON storage to individual columns for better query performance and data integrity.

## Changes Made

### 1. BacktestQueueManager Updates (`app/services/backtest_queue_manager.py`)

#### Imports Added:
- Added `CachedBacktestResult` model import
- Added `Decimal` import for proper numeric handling

#### Updated `_parse_and_store_results` method:
- Now creates a `CachedBacktestResult` model instance instead of passing raw dictionaries
- Maps all LEAN statistics to individual model fields:
  - Core metrics: `total_return`, `win_rate`, `total_trades`, `winning_trades`, `losing_trades`
  - Risk metrics: `sharpe_ratio`, `sortino_ratio`, `max_drawdown`
  - Profit metrics: `profit_factor`, `total_profit`
  - Additional metrics: `avg_winning_return`, `avg_losing_return`
  - Execution metadata: `execution_time_ms`
- Properly extracts backtest parameters from request data
- Calls the updated cache service method with the model instance

#### Updated cache checking logic:
- Creates `CachedBacktestRequest` model for cache lookups
- Converts cached results back to expected format for compatibility

#### Enhanced `_extract_statistics_from_result` method:
- Extracts more fields from LEAN results including:
  - Trade statistics: `average_win`, `average_loss`, `largest_win`, `largest_loss`
  - Duration metrics: `average_trade_duration`
  - Portfolio statistics: `average_daily_return`, `standard_deviation`, `market_exposure`
  - Separate winning/losing trade counts

### 2. Pipeline Script Updates (`run_screener_backtest_pipeline.py`)

#### Imports Added:
- Added `CachedScreenerRequest` and `CachedScreenerResult` model imports
- Added `date` import for proper date handling

#### Updated screener cache logic:
- Creates `CachedScreenerRequest` model with all filter parameters
- Maps frontend filters to cache model fields:
  - Price range filters → `min_price`, `max_price`
  - Dollar volume filter → estimated `min_volume`
  - Gap filter → `min_gap` (for upward gaps)
  - Technical indicators → `above_vwap`, `above_sma20`
- Extracts symbols from cached `CachedScreenerResult` objects

#### Updated screener result storage:
- Creates `CachedScreenerResult` models for each screened stock
- Captures all filter parameters used in the query
- Stores performance metrics: `daily_change_percent`, `gap_percent`
- Calls cache service with model instances

#### Updated backtest cache logic:
- Creates `CachedBacktestRequest` model for cache lookups
- Properly converts cached results to expected format
- Maintains backward compatibility with existing pipeline flow

## Benefits

1. **Better Performance**: Individual columns allow for indexed queries and better query optimization
2. **Data Integrity**: Strong typing with Pydantic models ensures data consistency
3. **Maintainability**: Clear model definitions make it easier to understand data structure
4. **Extensibility**: Easy to add new fields without breaking existing queries
5. **Cache Efficiency**: More granular cache lookups based on exact parameter matches

## Testing

Created and ran a test script that verified:
- All imports work correctly
- Models can be instantiated properly
- Hash calculation functions work as expected

## Next Steps

1. Monitor pipeline execution to ensure proper data storage
2. Verify cache hit rates improve with the new structure
3. Consider adding indexes on frequently queried columns
4. Add migration scripts if needed for existing JSON data