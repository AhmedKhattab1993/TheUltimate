# Backtest Results Schema Alignment Plan

## Overview
Redesign the `market_structure_results` table to properly align with actual algorithm parameters and results, ensuring each metric is stored in a separate column for optimal querying and display.

## Current Issues
- Schema contains irrelevant parameters (`param_holding_period`, `param_stop_loss`, `param_take_profit`)
- Missing many actual algorithm parameters and performance metrics
- Cannot efficiently query or display comprehensive backtest results

## Target Schema Design

### Core Identifiers (Keep/Modify)
- `id` (UUID, Primary Key) - Keep
- `backtest_id` (UUID) - Keep 
- `symbol` (VARCHAR) - Keep
- `strategy_name` (VARCHAR) - Add
- `start_date` (DATE) - Keep
- `end_date` (DATE) - Keep
- `created_at` (TIMESTAMP) - Keep

### Algorithm Parameters (New)
- `initial_cash` (DECIMAL) - Starting capital
- `resolution` (VARCHAR) - Data resolution (Daily, Minute, etc.)
- `pivot_bars` (INTEGER) - Bars for pivot detection
- `lower_timeframe` (VARCHAR) - Analysis timeframe

### Core Performance Results (Keep/Enhance)
- `total_return` (DECIMAL) - Keep
- `net_profit` (DECIMAL) - Add
- `net_profit_currency` (DECIMAL) - Add
- `compounding_annual_return` (DECIMAL) - Add
- `final_value` (DECIMAL) - Add
- `start_equity` (DECIMAL) - Add
- `end_equity` (DECIMAL) - Add

### Risk Metrics (Keep/Enhance)
- `sharpe_ratio` (DECIMAL) - Keep
- `sortino_ratio` (DECIMAL) - Keep
- `max_drawdown` (DECIMAL) - Keep
- `probabilistic_sharpe_ratio` (DECIMAL) - Add
- `annual_standard_deviation` (DECIMAL) - Add
- `annual_variance` (DECIMAL) - Add
- `beta` (DECIMAL) - Add
- `alpha` (DECIMAL) - Add

### Trading Statistics (Keep/Enhance)
- `total_trades` (INTEGER) - Keep
- `winning_trades` (INTEGER) - Keep
- `losing_trades` (INTEGER) - Keep
- `win_rate` (DECIMAL) - Keep
- `loss_rate` (DECIMAL) - Add
- `average_win` (DECIMAL) - Add (rename from avg_winning_return)
- `average_loss` (DECIMAL) - Add (rename from avg_losing_return)
- `profit_factor` (DECIMAL) - Keep
- `profit_loss_ratio` (DECIMAL) - Add
- `expectancy` (DECIMAL) - Add
- `total_orders` (INTEGER) - Add

### Advanced Metrics (New)
- `information_ratio` (DECIMAL) - Add
- `tracking_error` (DECIMAL) - Add
- `treynor_ratio` (DECIMAL) - Add
- `total_fees` (DECIMAL) - Add
- `estimated_strategy_capacity` (DECIMAL) - Add
- `lowest_capacity_asset` (VARCHAR) - Add
- `portfolio_turnover` (DECIMAL) - Add

### Strategy-Specific Metrics (New)
- `pivot_highs_detected` (INTEGER) - Add
- `pivot_lows_detected` (INTEGER) - Add
- `bos_signals_generated` (INTEGER) - Add
- `position_flips` (INTEGER) - Add
- `liquidation_events` (INTEGER) - Add

### Execution Metadata (Keep/Enhance)
- `execution_time_ms` (INTEGER) - Keep
- `result_path` (VARCHAR) - Add
- `status` (VARCHAR) - Keep
- `error_message` (TEXT) - Keep
- `cache_hit` (BOOLEAN) - Add

### Remove Columns
- `param_holding_period`, `param_stop_loss`, `param_take_profit`
- `avg_return`, `median_return`, `std_dev`, `min_return`, `max_return`
- `avg_holding_days`, `best_trade`, `worst_trade`
- `total_profit`, `total_loss`, `time_in_market`

## Cache Key Parameters
The backtest caching system will use these key parameters to determine cache hits/misses:
- `symbol` - Stock symbol
- `strategy_name` - Strategy used (e.g., "MarketStructure") 
- `start_date` - Backtest start date
- `end_date` - Backtest end date
- `initial_cash` - Starting capital amount
- `pivot_bars` - Number of bars for pivot detection
- `lower_timeframe` - Analysis timeframe (e.g., "5min")

## Implementation Tasks

### Task 1: Database Schema Migration (Agent: implementation-engineer)
**Objective**: Create and execute database migration script
**Requirements**:
- Create migration script `005_redesign_backtest_results_schema.sql`
- Add all new columns with proper data types and constraints
- Remove obsolete columns
- Migrate existing data where applicable
- Create appropriate indexes for performance
- Test migration on development database

### Task 2: Update Cache Service (Agent: implementation-engineer)
**Objective**: Update cache service to use new cache key parameters
**Requirements**:
- Update `backend/app/models/cache_models.py` CachedBacktestRequest model
- Modify cache key generation to use: symbol, strategy_name, start_date, end_date, initial_cash, pivot_bars, lower_timeframe
- Update `backend/app/services/cache_service.py` cache lookup logic
- Remove old parameters (holding_period, gap_threshold, stop_loss, take_profit) from cache logic
- Test cache hit/miss detection with new parameters

### Task 3: Update Pipeline Code (Agent: implementation-engineer) 
**Objective**: Modify pipeline to save comprehensive results
**Requirements**:
- Update `run_screener_backtest_pipeline.py` to extract all new metrics from LEAN results
- Map LEAN output JSON to new database columns
- Ensure all algorithm parameters are captured (especially the 7 cache key parameters)
- Add strategy-specific metrics extraction
- Test with sample backtest runs

### Task 4: Update Backend Models (Agent: implementation-engineer)
**Objective**: Modify Pydantic models and database schemas
**Requirements**:
- Update `backend/app/models/backtest.py` with new column structure
- Add new fields to response models
- Update database table definitions
- Ensure proper validation and typing

### Task 5: Update API Endpoints (Agent: implementation-engineer)
**Objective**: Enhance API to return comprehensive backtest data
**Requirements**:
- Update `backend/app/api/backtest.py` endpoints
- Return all new performance metrics in API responses
- Add filtering capabilities for new columns
- Update pagination and sorting logic
- Test API responses with new schema

### Task 6: Update Frontend Display (Agent: implementation-engineer)
**Objective**: Enhance UI to display comprehensive backtest results
**Requirements**:
- Update `frontend/src/components/results/BacktestResultsView.tsx`
- Create detailed metrics display components
- Add performance charts for new metrics
- Organize metrics by categories (Core, Risk, Trading, Advanced)
- Implement responsive design for all metrics

### Task 7: Data Migration and Cleanup (Agent: system-tester)
**Objective**: Apply migration and verify data integrity
**Requirements**:
- Execute migration script on production database
- Verify all existing data is preserved where applicable
- Test new columns accept expected data types
- Validate constraints and indexes work correctly

### Task 8: Integration Testing (Agent: system-tester)
**Objective**: Test complete pipeline with new schema
**Requirements**:
- Run end-to-end backtest pipeline
- Verify all metrics are captured correctly
- Test API responses contain all expected fields
- Verify frontend displays all metrics properly
- Test edge cases and error scenarios

### Task 9: Performance Optimization (Agent: system-tester)
**Objective**: Ensure optimal query performance
**Requirements**:
- Test query performance with new schema
- Optimize indexes if needed
- Verify API response times are acceptable
- Test with large result sets

### Task 10: Documentation Update (Agent: general-purpose)
**Objective**: Update documentation for new schema
**Requirements**:
- Document new database schema
- Update API documentation
- Create mapping guide from LEAN results to database columns
- Document frontend component structure

### Task 11: Production Deployment (Agent: system-tester)
**Objective**: Deploy changes to production safely
**Requirements**:
- Create deployment checklist
- Execute migration in production
- Monitor for any issues
- Verify all systems working correctly

## Success Criteria
- ✅ All algorithm parameters and results stored in separate columns
- ✅ Pipeline saves comprehensive backtest metrics
- ✅ API returns all performance data
- ✅ Frontend displays organized, comprehensive results
- ✅ No data loss during migration
- ✅ Query performance maintained or improved

## Dependencies
- Existing backtest pipeline functionality
- LEAN algorithm output format
- Frontend results display components
- Database migration capabilities

## Cache Key Composite Index
The migration should create a composite index on the cache key parameters for optimal cache lookup performance:
```sql
CREATE INDEX idx_backtest_cache_key ON market_structure_results 
(symbol, strategy_name, start_date, end_date, initial_cash, pivot_bars, lower_timeframe);
```

## Timeline Estimate
- Tasks 1-2: Database migration and cache updates (2-3 hours)
- Tasks 3-4: Pipeline and backend model changes (2-3 hours)
- Tasks 5-6: API and frontend updates (2-3 hours) 
- Tasks 7-9: Testing and optimization (1-2 hours)
- Tasks 10-11: Documentation and deployment (1 hour)

**Total: 8-12 hours**