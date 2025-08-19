# Task 2: New Schema Design

## Overview
This document outlines the new schema design for the `screener_results` table that aligns with the pipeline configuration while maintaining cache functionality.

## Design Principles
1. **Keep cache-critical columns** for efficient cache matching
2. **Add pipeline-specific columns** for all filters in pipeline_config.yaml
3. **Remove unused columns** that aren't in pipeline config or used for caching
4. **Maintain one-row-per-symbol design** for cache compatibility

## New Schema Design

```sql
CREATE TABLE screener_results (
    -- ===== Primary Identification =====
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_id UUID NOT NULL,  -- Groups results from same screening run
    
    -- ===== Stock Identification =====
    symbol VARCHAR(10) NOT NULL,
    company_name VARCHAR(255),  -- Keep for display purposes
    
    -- ===== Timestamps =====
    screened_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    data_date DATE NOT NULL,  -- Date of stock data used
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    
    -- ===== FILTER COLUMNS (Used by Cache) =====
    -- Price Range Filter
    filter_min_price DECIMAL(10, 2),
    filter_max_price DECIMAL(10, 2),
    
    -- Price vs MA Filter (NEW)
    filter_price_vs_ma_enabled BOOLEAN DEFAULT false,
    filter_price_vs_ma_period INTEGER,  -- e.g., 20 for SMA20
    filter_price_vs_ma_condition VARCHAR(10),  -- 'above' or 'below'
    
    -- RSI Filter (NEW)
    filter_rsi_enabled BOOLEAN DEFAULT false,
    filter_rsi_period INTEGER,  -- e.g., 14
    filter_rsi_threshold DECIMAL(5, 2),  -- e.g., 30.0
    filter_rsi_condition VARCHAR(10),  -- 'above' or 'below'
    
    -- Gap Filter (ENHANCED)
    filter_gap_enabled BOOLEAN DEFAULT false,
    filter_gap_threshold DECIMAL(5, 2),  -- Renamed from filter_min_gap
    filter_gap_direction VARCHAR(10),  -- 'up', 'down', or 'any' (NEW)
    
    -- Previous Day Dollar Volume Filter (NEW)
    filter_prev_day_dollar_volume_enabled BOOLEAN DEFAULT false,
    filter_prev_day_dollar_volume DECIMAL(15, 2),
    
    -- Relative Volume Filter (NEW)
    filter_relative_volume_enabled BOOLEAN DEFAULT false,
    filter_relative_volume_recent_days INTEGER,
    filter_relative_volume_lookback_days INTEGER,
    filter_relative_volume_min_ratio DECIMAL(5, 2),
    
    -- ===== REMOVE THESE COLUMNS =====
    -- price DECIMAL(10, 2),  -- REMOVE - not needed
    -- volume BIGINT,  -- REMOVE - not needed
    -- market_cap BIGINT,  -- REMOVE - not in pipeline
    -- filter_min_volume BIGINT,  -- REMOVE - replaced by dollar volume
    -- filter_min_market_cap BIGINT,  -- REMOVE - not in pipeline
    -- filter_max_market_cap BIGINT,  -- REMOVE - not in pipeline
    -- filter_min_change DECIMAL(5, 2),  -- REMOVE - not in pipeline
    -- filter_max_change DECIMAL(5, 2),  -- REMOVE - not in pipeline
    -- filter_min_atr DECIMAL(10, 2),  -- REMOVE - not in pipeline
    -- filter_above_vwap BOOLEAN,  -- REMOVE - not in pipeline
    -- filter_above_sma20 BOOLEAN,  -- REMOVE - replaced by price_vs_ma
    -- daily_change_percent DECIMAL(5, 2),  -- REMOVE - not needed
    -- atr_value DECIMAL(10, 2),  -- REMOVE - not in pipeline
    -- gap_percent DECIMAL(5, 2),  -- REMOVE - not needed
    -- distance_from_vwap_percent DECIMAL(5, 2),  -- REMOVE - not in pipeline
    -- distance_from_sma20_percent DECIMAL(5, 2),  -- REMOVE - not needed
    
    -- ===== Constraints =====
    CONSTRAINT chk_price_range CHECK (
        (filter_min_price IS NULL OR filter_max_price IS NULL) OR 
        (filter_min_price <= filter_max_price)
    ),
    CONSTRAINT chk_price_vs_ma_condition CHECK (
        filter_price_vs_ma_condition IN ('above', 'below') OR filter_price_vs_ma_condition IS NULL
    ),
    CONSTRAINT chk_rsi_condition CHECK (
        filter_rsi_condition IN ('above', 'below') OR filter_rsi_condition IS NULL
    ),
    CONSTRAINT chk_gap_direction CHECK (
        filter_gap_direction IN ('up', 'down', 'any') OR filter_gap_direction IS NULL
    ),
    CONSTRAINT chk_positive_values CHECK (
        (filter_min_price IS NULL OR filter_min_price >= 0) AND
        (filter_max_price IS NULL OR filter_max_price >= 0) AND
        (filter_gap_threshold IS NULL OR filter_gap_threshold >= 0) AND
        (filter_prev_day_dollar_volume IS NULL OR filter_prev_day_dollar_volume >= 0) AND
        (filter_relative_volume_min_ratio IS NULL OR filter_relative_volume_min_ratio >= 0)
    )
);

-- ===== Indexes =====
-- Time-based queries
CREATE INDEX idx_screener_results_screened_at ON screener_results(screened_at DESC);
CREATE INDEX idx_screener_results_data_date ON screener_results(data_date DESC);

-- Symbol lookups
CREATE INDEX idx_screener_results_symbol ON screener_results(symbol);

-- Session grouping
CREATE INDEX idx_screener_results_session_id ON screener_results(session_id);

-- Composite for common patterns
CREATE INDEX idx_screener_results_symbol_date ON screener_results(symbol, data_date DESC);

-- Cache matching optimization (covers all filter columns used in WHERE clause)
CREATE INDEX idx_screener_results_cache_match ON screener_results(
    data_date,
    filter_min_price,
    filter_max_price,
    filter_price_vs_ma_enabled,
    filter_price_vs_ma_period,
    filter_price_vs_ma_condition,
    filter_rsi_enabled,
    filter_gap_enabled,
    filter_prev_day_dollar_volume_enabled,
    filter_relative_volume_enabled
);
```

## Mapping: Pipeline Config → Database Columns

| Pipeline Filter | Database Columns |
|----------------|-----------------|
| `price_range.min_price` | `filter_min_price` |
| `price_range.max_price` | `filter_max_price` |
| `price_vs_ma.enabled` | `filter_price_vs_ma_enabled` |
| `price_vs_ma.ma_period` | `filter_price_vs_ma_period` |
| `price_vs_ma.condition` | `filter_price_vs_ma_condition` |
| `rsi.enabled` | `filter_rsi_enabled` |
| `rsi.rsi_period` | `filter_rsi_period` |
| `rsi.threshold` | `filter_rsi_threshold` |
| `rsi.condition` | `filter_rsi_condition` |
| `gap.enabled` | `filter_gap_enabled` |
| `gap.gap_threshold` | `filter_gap_threshold` |
| `gap.direction` | `filter_gap_direction` |
| `prev_day_dollar_volume.enabled` | `filter_prev_day_dollar_volume_enabled` |
| `prev_day_dollar_volume.min_dollar_volume` | `filter_prev_day_dollar_volume` |
| `relative_volume.enabled` | `filter_relative_volume_enabled` |
| `relative_volume.recent_days` | `filter_relative_volume_recent_days` |
| `relative_volume.lookback_days` | `filter_relative_volume_lookback_days` |
| `relative_volume.min_ratio` | `filter_relative_volume_min_ratio` |

## Key Changes from Current Schema

### Added Columns:
1. **Price vs MA details**: Replaces generic `filter_above_sma20` with configurable period and condition
2. **RSI filter columns**: Complete RSI filter support
3. **Gap direction**: Enhanced gap filter with direction
4. **Previous day dollar volume**: Replaces simple volume filter
5. **Relative volume filter**: Complete relative volume support
6. **Enabled flags**: For each filter type to distinguish between "not configured" and "configured with NULL values"

### Removed Columns:
1. **Market data columns**: `price`, `volume`, `market_cap` (not needed for output)
2. **Unused filters**: `market_cap`, `change`, `ATR`, `VWAP` filters
3. **Metric columns**: `daily_change_percent`, `atr_value`, `gap_percent`, distance metrics

### Modified Columns:
1. `filter_min_gap` → `filter_gap_threshold` (clearer naming)
2. `filter_above_sma20` → replaced by `filter_price_vs_ma_*` columns

## Cache Service Impact

The cache service will need updates to:
1. Match on new filter columns in WHERE clause
2. Handle enabled flags properly (NULL vs false)
3. Update hash calculation to include all new parameters

## Benefits of This Design

1. **Aligned with Pipeline**: Every pipeline filter has corresponding columns
2. **Cache Efficient**: Maintains column-based matching for fast cache lookups
3. **Cleaner**: Removes unused columns reducing storage and complexity
4. **Extensible**: Easy to add new filters by following the pattern
5. **Clear Intent**: Enabled flags make it clear when a filter is intentionally used

## Next Steps
Proceed to Task 3: Create the migration script to transform the current schema to this new design.