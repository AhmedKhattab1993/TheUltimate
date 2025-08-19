# Pipeline Schema Update Summary

## Overview
Updated the screener-backtest pipeline to save data to the new screener_results schema columns, properly mapping all filter parameters from the pipeline configuration.

## Changes Made

### 1. Updated `run_screener_backtest_pipeline.py`

#### Cache Request Creation (Line 166-193)
- Removed the hacky conversion of dollar volume to volume
- Added proper mapping for all filter types:
  - **Price Range**: `min_price`, `max_price`
  - **Price vs MA**: `price_vs_ma_enabled`, `price_vs_ma_period`, `price_vs_ma_condition`
  - **RSI**: `rsi_enabled`, `rsi_period`, `rsi_threshold`, `rsi_condition`
  - **Gap**: `gap_enabled`, `gap_threshold`, `gap_direction` (with "both" → "any" mapping)
  - **Previous Day Dollar Volume**: `prev_day_dollar_volume_enabled`, `prev_day_dollar_volume`
  - **Relative Volume**: `relative_volume_enabled`, `relative_volume_recent_days`, `relative_volume_lookback_days`, `relative_volume_min_ratio`

#### Cache Result Storage (Line 221-250)
- Removed attempts to save `price`, `volume`, `market_cap` (columns removed from schema)
- Removed metrics like `daily_change_percent`, `gap_percent` (not in new schema)
- Added complete filter parameter mapping matching the cache request structure
- Each result now stores all filter parameters used in the screening run

### 2. Key Improvements

1. **Proper NULL Handling**: Uses conditional checks to set `None` for disabled filters
2. **Enabled Flags**: Correctly sets boolean flags based on filter presence
3. **Direction Mapping**: Handles API's "both" → database's "any" for gap direction
4. **No Data Loss**: All pipeline filter parameters are now preserved in the database

### 3. Testing

Created `test_pipeline_schema_update.py` to verify:
- All filter parameters map correctly
- Partial filter configurations work properly
- NULL values are handled appropriately
- Direction mapping works as expected

### 4. Compatibility

The changes are fully compatible with:
- The new cache models in `app/models/cache_models.py`
- The new schema design in `TASK2_NEW_SCHEMA_DESIGN.md`
- The existing pipeline configuration structure
- The cache service's filter matching logic

## Usage

The pipeline now correctly saves all filter information when caching is enabled:

```bash
# Run with test configuration
python3 run_screener_backtest_pipeline.py pipeline_config_test_new_schema.yaml

# Run with standard configuration
python3 run_screener_backtest_pipeline.py pipeline_config.yaml
```

## Next Steps

1. Run the database migration to update the schema (Task 3)
2. Update the cache service to use the new columns for matching (Task 4)
3. Test end-to-end with the new schema in place