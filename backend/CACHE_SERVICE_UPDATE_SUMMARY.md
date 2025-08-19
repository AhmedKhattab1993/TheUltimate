# Cache Service Update Summary

## Overview
This document summarizes the updates made to the cache service to work with the new screener_results schema.

## Files Modified

### 1. `/backend/app/models/cache_models.py`

#### CachedScreenerRequest Model Updates:
- **Removed old filter fields:**
  - `min_volume`, `min_market_cap`, `max_market_cap`
  - `min_change`, `max_change`
  - `min_atr`
  - `min_gap` (replaced with `gap_threshold`)
  - `above_vwap`, `above_sma20`

- **Added new filter fields:**
  - Price vs MA: `price_vs_ma_enabled`, `price_vs_ma_period`, `price_vs_ma_condition`
  - RSI: `rsi_enabled`, `rsi_period`, `rsi_threshold`, `rsi_condition`
  - Gap: `gap_enabled`, `gap_threshold`, `gap_direction`
  - Previous day dollar volume: `prev_day_dollar_volume_enabled`, `prev_day_dollar_volume`
  - Relative volume: `relative_volume_enabled`, `relative_volume_recent_days`, `relative_volume_lookback_days`, `relative_volume_min_ratio`

- **Updated `calculate_hash()` method:** Now includes all new filter parameters in a structured format

#### CachedScreenerResult Model Updates:
- **Removed columns:**
  - `price`, `volume`, `market_cap`
  - All old filter columns matching the request model
  - Performance metrics columns

- **Added columns:** Same new filter columns as in the request model

### 2. `/backend/app/services/cache_service.py`

#### get_screener_results() Updates:
- **Updated SQL query:**
  - Removed references to dropped columns
  - Added all new filter columns to SELECT clause
  - Updated WHERE clause to match on new filter columns (20 parameters total)
  - Maintained NULL-safe comparisons for optional filters

- **Updated parameter passing:** Now passes 20 parameters to match new filter columns

- **Updated result mapping:** Maps database rows to new CachedScreenerResult model fields

#### save_screener_results() Updates:
- **Updated INSERT query:** Includes all new filter columns (25 columns total)
- **Updated batch data preparation:** Maps request parameters to new columns

#### Legacy Method Updates:
- **get_screener_results_legacy():**
  - Maps old filter format to new schema
  - `above_sma20` → `price_vs_ma_enabled=True, period=20, condition='above'`
  - `min_gap` → `gap_enabled=True, gap_threshold, direction='up'`
  - `min_volume` → `prev_day_dollar_volume` (rough conversion × 100)

- **save_screener_results_legacy():** Same mapping as get method

## Key Changes

### 1. Filter Mapping Strategy
- Old boolean filters expanded to detailed configurations
- Volume filter converted from share count to dollar volume
- Gap filter enhanced with direction support
- SMA20 filter generalized to configurable MA period

### 2. Backward Compatibility
- Legacy methods provide translation layer
- Old filter formats automatically mapped to new schema
- Rough conversions where exact mapping not possible (e.g., volume → dollar volume)

### 3. Cache Matching Logic
- Maintains exact column matching for cache hits
- NULL-safe comparisons for all optional parameters
- Enabled flags distinguish between "not configured" and "configured with NULL"

## Testing

A test script has been created at `/backend/test_cache_service_new_schema.py` that:
1. Tests basic price filters
2. Tests complex filters with all new fields
3. Tests legacy compatibility methods
4. Verifies cache statistics
5. Tests cache cleanup

## Migration Considerations

### Before Running Migration:
1. Cache will have misses for existing data (different schema)
2. Old cached results won't match new queries
3. Consider clearing cache table before migration

### After Running Migration:
1. All new cache entries will use new schema
2. Legacy methods provide transition support
3. Monitor cache hit rates initially

## Next Steps

1. Run the database migration script (004_align_screener_results_schema.sql)
2. Test cache service with test script
3. Update pipeline code to use new filter parameters
4. Update API endpoints to handle new schema
5. Monitor cache performance during transition