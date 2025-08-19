# Statistics Parsing Fix Summary

## Issue
The backtest pipeline was showing all statistics as 0.0 even though the backtests were running successfully and producing real results.

## Root Cause
The statistics parser in `app/services/statistics_aggregator.py` was only looking at the `statistics` section of LEAN's summary.json file, which often contains "0%" values. The actual values are stored in other sections like `runtimeStatistics`, `totalPerformance.portfolioStatistics`, and `totalPerformance.tradeStatistics`.

## Fix Applied
Updated the `_parse_lean_results` method in `statistics_aggregator.py` to:

1. **Look at multiple sections** of the LEAN output:
   - `runtimeStatistics` for actual return percentages and net profit
   - `totalPerformance.portfolioStatistics` for portfolio-level metrics
   - `totalPerformance.tradeStatistics` for trade-level statistics

2. **Calculate values when needed**:
   - If total return is 0%, calculate it from (end_equity - start_equity) / start_equity
   - Convert win rate from decimal to percentage
   - Extract actual dollar values for profits and equity

3. **Enhanced reporting**:
   - Added net profit, total trades to HTML and CSV reports
   - Updated console output to show more detailed statistics
   - Improved formatting for currency values

## Test Results
After the fix, a test backtest for ALGN showed:
- Total Return: 1.26% (previously showed 0.0%)
- Net Profit: $1,255.52 (previously not shown)
- Win Rate: 100% (previously showed 0.0%)
- Total Trades: 1 (previously showed 0)

## Timeout Configuration
The pipeline uses a 300-second (5-minute) timeout per backtest, configured in `pipeline_config.yaml`. If backtests are timing out, increase the `timeout_per_backtest` value.

## Files Modified
- `/home/ahmed/TheUltimate/backend/app/services/statistics_aggregator.py` - Updated parsing logic and report generation
- `/home/ahmed/TheUltimate/backend/pipeline_config.yaml` - Added comment about timeout configuration