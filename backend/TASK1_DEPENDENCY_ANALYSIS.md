# Task 1: Dependency Analysis Report

## Overview
This document analyzes all code dependencies on the `screener_results` table to understand the impact of schema changes.

## Files That Interact with screener_results Table

### 1. API Layer
- **`/backend/app/api/screener_results.py`**
  - Lists screener results with pagination
  - Gets detailed results by ID
  - Deletes results
  - **Columns Used**:
    - All columns are selected and used in queries
    - Filters are reconstructed from filter_* columns
    - Symbol data uses: symbol, company_name, price, volume
    - Metadata uses: screened_at, data_date, created_at, session_id

### 2. Cache Service
- **`/backend/app/services/cache_service.py`**
  - Critical for performance - matches cached results based on filter parameters
  - **Columns Used for Cache Matching** (WHERE clause):
    - `data_date` (range matching)
    - `filter_min_price`, `filter_max_price`
    - `filter_min_volume`
    - `filter_min_market_cap`, `filter_max_market_cap`
    - `filter_min_change`, `filter_max_change`
    - `filter_min_atr`
    - `filter_min_gap`
    - `filter_above_vwap`
    - `filter_above_sma20`
    - `screened_at` (for TTL check)
  - **Columns Retrieved**: All columns in the table
  - **Columns Saved**: All columns when saving new results

### 3. Pipeline Script
- **`/backend/run_screener_backtest_pipeline.py`**
  - Saves screener results to cache/database
  - **Columns Populated**:
    - Basic: symbol, company_name, data_date, price, volume, market_cap
    - Filters: filter_min_price, filter_max_price, filter_min_volume, filter_min_gap, filter_above_vwap, filter_above_sma20
    - Metrics: daily_change_percent, gap_percent
    - Missing columns for: RSI filters, relative_volume filters, price_vs_ma details

### 4. Other References
- **`/backend/app/services/screener_results.py`**: File-based storage (not using DB)
- **`/backend/clean_screener_results.py`**: Utility script for cleaning
- **Various migration/test scripts**: Database operations

## Current vs Pipeline Configuration Mismatch

### Columns in DB but NOT in Pipeline Config:
- `market_cap`, `filter_min_market_cap`, `filter_max_market_cap`
- `filter_min_change`, `filter_max_change`, `daily_change_percent`
- `filter_min_atr`, `atr_value`
- `filter_above_vwap`, `distance_from_vwap_percent`
- `distance_from_sma20_percent`

### Pipeline Filters WITHOUT Corresponding DB Columns:
- **RSI Filter**:
  - Need: `filter_rsi_enabled`, `filter_rsi_period`, `filter_rsi_threshold`, `filter_rsi_condition`
- **Relative Volume Filter**:
  - Need: `filter_relative_volume_enabled`, `filter_relative_volume_ratio`, `filter_relative_volume_recent_days`, `filter_relative_volume_lookback_days`
- **Price vs MA Details**:
  - Need: `filter_price_vs_ma_period`, `filter_price_vs_ma_condition`
- **Gap Direction**:
  - Need: `filter_gap_direction` (currently only has min_gap)
- **Previous Day Dollar Volume**:
  - Need: `filter_prev_day_dollar_volume`

## Critical Dependencies

### 1. Cache Service Matching Logic
The cache service uses exact column matching in WHERE clauses. Any schema change must:
- Preserve columns used in WHERE clauses OR
- Update the matching logic simultaneously
- Handle NULL values correctly (current logic uses `OR (col IS NULL AND $n IS NULL)`)

### 2. API Response Format
The API reconstructs filter objects from individual columns. Changes require:
- Updating the filter reconstruction logic
- Ensuring backward compatibility for frontend

### 3. Pipeline Data Population
The pipeline currently tries to map some filters to existing columns (e.g., dollar volume → volume). Changes need:
- Proper mapping of all pipeline filters to new columns
- Removal of hacky conversions

## Recommendations

1. **Preserve Cache-Critical Columns**: Keep columns used in cache WHERE clauses
2. **Add Missing Pipeline Columns**: Add columns for RSI, relative volume, etc.
3. **Remove Truly Unused Columns**: market_cap, change, ATR (if not used by cache)
4. **Update Code in Order**:
   - Migration script first
   - Cache service updates
   - Pipeline save logic
   - API response construction
   - Frontend display

## Next Steps
Proceed to Task 2: Design New Table Schema based on this analysis.