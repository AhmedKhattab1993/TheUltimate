# Frontend Column Update Summary

## Changes Implemented

### Columns Removed
1. **Profit ($)** - Was displaying `netProfitCurrency`
2. **Sortino Ratio** - Was displaying `sortinoRatio`

### Columns Added
1. **Pivots** - Displays `pivotBars` (number of pivot bars used in the strategy)
2. **Lower TF** - Displays `lowerTimeframe` (lower timeframe used for entry/exit)

## Files Modified
- `/home/ahmed/TheUltimate/frontend/src/components/results/BacktestResultsView.tsx`

## Current Table Structure
The backtest results table now shows these columns in order:
1. Date
2. Strategy
3. Symbol
4. Period
5. Return
6. Sharpe
7. Max DD
8. Win Rate
9. Trades
10. **Pivots** (NEW)
11. **Lower TF** (NEW)
12. Final Value
13. Actions

## Testing Results
✅ All changes verified using Playwright automated testing:
- Profit column successfully removed
- Sortino column successfully removed
- Pivots column successfully added
- Lower TF column successfully added
- Screenshot captured at: `/home/ahmed/TheUltimate/.playwright-mcp/backtest-results-table.png`

## Notes
- The new columns currently show "N/A" for existing data that doesn't have these fields populated
- The Lower TF column uses a styled badge with outline variant for better visibility
- Both new columns are center-aligned to match the table design