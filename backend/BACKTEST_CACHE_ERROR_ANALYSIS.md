# Backtest Cache Error Analysis

## Summary of Errors Found

When running the screener backtest pipeline, two critical errors were identified related to saving backtest results to cache:

### 1. Column Mismatch Error in Cache Service
**Error:** `INSERT has more target columns than expressions`

**Root Cause:** The INSERT statement in `cache_service.py` has a mismatch between columns and values:
- **Columns specified:** 53 columns
- **Placeholders provided:** 51 values ($1 through $51)
- **Missing value:** The query is missing a placeholder for `profit_loss_ratio` column

**Location:** `/home/ahmed/TheUltimate/backend/app/services/cache_service.py` lines 405-431

**Details:**
- The INSERT statement includes both `profit_factor` and `profit_loss_ratio` columns (line 416)
- However, only one value is provided for both columns (line 467)
- The value at line 467 is assigned to `profit_factor`, leaving `profit_loss_ratio` without a corresponding value

### 2. String to Float Conversion Error in Backtest Storage
**Error:** `could not convert string to float: '0%'`

**Root Cause:** The backtest storage service is attempting to convert percentage strings directly to float without proper parsing.

**Location:** `/home/ahmed/TheUltimate/backend/app/services/backtest_storage.py`

**Details:**
- The error occurs when saving backtest results to file storage
- The `_parse_percentage` method exists but may not be called for all percentage values
- Some values from LEAN results come as strings with '%' suffix (e.g., "0%") that need to be cleaned before conversion

## Impact

1. **Cache Storage Fails:** Backtest results cannot be cached in the database, forcing re-execution of backtests on subsequent runs
2. **File Storage Fails:** Backtest results cannot be saved to file storage as backup
3. **Performance Degradation:** Without caching, the pipeline must re-run all backtests each time

## Recommended Fixes

### Fix 1: Correct the INSERT Statement in cache_service.py
Add the missing placeholder for `profit_loss_ratio`:
- Change line 429 from: `$33, $34, $35, $36, $37, $38, $39, $40, $41, $42,`
- To: `$33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43,`
- Adjust all subsequent placeholders by incrementing by 1
- Add the profit_loss_ratio value after profit_factor in the execute call

### Fix 2: Ensure Proper Percentage Parsing
- Review all percentage value extractions in backtest_storage.py
- Ensure `_parse_percentage` method is called for all percentage fields
- Add defensive parsing to handle various formats ("0%", "0.00%", 0.0, etc.)

## Verification Steps

After applying fixes:
1. Run the pipeline again: `./venv/bin/python run_screener_backtest_pipeline.py`
2. Check for successful cache hits on subsequent runs
3. Verify no conversion errors in the logs
4. Confirm backtest results are properly stored in both cache and file storage