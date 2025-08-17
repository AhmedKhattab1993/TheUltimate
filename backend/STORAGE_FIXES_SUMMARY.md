# Storage Fixes Summary

## Issues Fixed

### 1. Cache Service - Column Mismatch Error
**Error**: `column "time_in_market" of relation "market_structure_results" does not exist`

**Fix**: Updated `cache_service.py` save_backtest_results method:
- Removed `time_in_market` column (doesn't exist in schema)
- Added missing columns: `total_fees`, `estimated_strategy_capacity`, `lowest_capacity_asset`, `portfolio_turnover`, `result_path`, `resolution`
- Updated INSERT statement to match actual schema
- Fixed parameter count from 39 to 51 to match all columns

### 2. Backtest Storage - Percentage Parsing Error
**Error**: `could not convert string to float: '0%'`

**Fix**: Updated `backtest_storage.py` _parse_percentage method:
- Added try-except block for safer parsing
- Handle empty strings after removing '%' sign
- Added logging for parse failures
- Return 0.0 for unparseable values instead of crashing

## Files Modified
1. `/app/services/cache_service.py` - Fixed INSERT query to match schema
2. `/app/services/backtest_storage.py` - Fixed percentage parsing

## Impact
These fixes ensure:
- Backtest results can be saved to the database without column mismatch errors
- Percentage values like "0%" are properly parsed to 0.0
- Both file storage and database storage work correctly
- Pipeline can save results without failures