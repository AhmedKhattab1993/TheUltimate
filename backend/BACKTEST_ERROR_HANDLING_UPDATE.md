# Backtest API Error Handling Update

## Summary
Modified the backtest API endpoints to handle validation errors gracefully by skipping problematic historical results instead of crashing.

## Changes Made

### 1. `/api/v2/backtest/db/results` endpoint (lines 687-764)
- Wrapped the result parsing in a try-except block
- If a result fails validation, it's skipped and logged as a warning
- The endpoint continues processing other results
- Added a counter to track skipped results
- Frontend receives valid results only, preventing crashes

### 2. `/api/v2/backtest/db/results/{result_id}` endpoint (lines 875-960)
- Added try-except wrapper around result parsing
- Returns a 404 error with a user-friendly message if parsing fails
- Logs the specific error for debugging

### 3. `/api/v2/backtest/db/cache-lookup` endpoint (lines 1095-1169)
- Added try-except wrapper around cached result parsing
- Returns appropriate error message if cached result is invalid
- Prevents frontend crashes when retrieving cached results

### 4. `/api/v2/backtest/results` endpoint (lines 198-207)
- Added error handling for strategy result loading
- If one strategy's results fail to load, others are still processed
- Logs warnings but continues operation

## Benefits
1. **Frontend Stability**: The backtesting tab will load successfully even if some historical results have validation errors
2. **Graceful Degradation**: Users see valid results while problematic ones are skipped
3. **Better Debugging**: Errors are logged with specific row IDs for investigation
4. **No Data Loss**: Invalid results remain in the database and can be fixed later

## Note
The BacktestStatistics model already has `extra = "ignore"` in its Config, which helps handle unknown fields from historical data. The main validation errors come from field type mismatches or constraint violations (e.g., negative counts, percentages > 100).

## Testing
After applying these changes and restarting the backend:
- The `/api/v2/backtest/db/results` endpoint returns data successfully
- No errors in the frontend logs
- The backtesting tab should load without issues