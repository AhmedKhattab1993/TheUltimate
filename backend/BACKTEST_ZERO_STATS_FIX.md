# Backtest Zero Statistics Fix

## Issue
Backtest 2025-08-17_16-49-59_88ff03ee showed mostly zero statistics despite having actual trading activity.

## Root Cause
LEAN outputs statistics in multiple sections:
1. `statistics` - Portfolio-level metrics (mostly zeros for short backtests)
2. `portfolioStatistics` - Also portfolio-level (zeros for short backtests)
3. `tradeStatistics` - Trade-level metrics (has actual values)

For single-day backtests, LEAN cannot calculate annualized metrics like Sharpe ratio, so it outputs zeros for portfolio statistics. However, the trade statistics contain valid calculated values.

## Solution
Modified both `backtest_storage.py` AND `backtest_queue_manager.py` (used by the pipeline) to fallback to `tradeStatistics` when portfolio statistics are zero:

1. **Sharpe Ratio**: Use `tradeStatistics.sharpeRatio` when portfolio stat is 0
2. **Sortino Ratio**: Use `tradeStatistics.sortinoRatio` when portfolio stat is 0
3. **Win Rate**: Use `tradeStatistics.winRate` (multiply by 100 for percentage)
4. **Loss Rate**: Use `tradeStatistics.lossRate` (multiply by 100 for percentage)
5. **Profit Factor**: Use `tradeStatistics.profitFactor` when portfolio stat is 0
6. **Profit-Loss Ratio**: Use `tradeStatistics.profitLossRatio` when portfolio stat is 0
7. **Max Drawdown**: Calculate from `tradeStatistics.maximumClosedTradeDrawdown`

## Example Values from 88ff03ee
- Total Trades: 21
- Win Rate: 33.33% (7 winning trades)
- Loss Rate: 66.67% (14 losing trades)
- Sharpe Ratio: -0.4284
- Sortino Ratio: -0.6499
- Profit Factor: 0.3555
- Max Drawdown: -6.998% (from $6,998.37 drawdown on $100k initial)

## Files Modified
1. `/app/services/backtest_storage.py` - Used by the backtest storage service for file-based storage
2. `/app/services/backtest_queue_manager.py` - Used by the pipeline for database storage

## Impact
This fix ensures that even short-duration backtests (1-day or less) will show meaningful statistics extracted from trade-level data when portfolio-level calculations are not available. The fix applies to both:
- Direct backtest API calls (via backtest_storage.py)
- Pipeline-based backtests (via backtest_queue_manager.py)