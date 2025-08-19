#!/usr/bin/env python3
"""Fix the database save issue by updating the INSERT query to match actual table columns."""

import os

# Read the current file
with open('/home/ahmed/TheUltimate/backend/app/services/backtest_queue_manager.py', 'r') as f:
    content = f.read()

# Find and replace the INSERT query section
old_insert = '''            # Insert into market_structure_results table
            query = """
                INSERT INTO market_structure_results (
                    id, backtest_id, symbol, strategy_name,
                    initial_cash, pivot_bars, lower_timeframe,
                    start_date, end_date,
                    total_return, net_profit, net_profit_currency,
                    compounding_annual_return, final_value, start_equity, end_equity,
                    sharpe_ratio, sortino_ratio, max_drawdown,
                    probabilistic_sharpe_ratio, annual_standard_deviation, annual_variance,
                    beta, alpha,
                    total_trades, winning_trades, losing_trades, win_rate, loss_rate,
                    average_win_percentage, average_loss_percentage, profit_factor,
                    profit_loss_ratio, expectancy, total_orders,
                    information_ratio, tracking_error, treynor_ratio,
                    total_fees, estimated_strategy_capacity, lowest_capacity_asset,
                    portfolio_turnover,
                    pivot_highs_detected, pivot_lows_detected, bos_signals_generated,
                    position_flips, liquidation_events,
                    execution_time_ms, result_path, status, error_message,
                    cache_hit, created_at, resolution
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                    $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                    $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43, $44,
                    $45, $46, $47, $48, $49, $50, $51, $52, $53, $54, $55
                )
            """'''

new_insert = '''            # Insert into market_structure_results table (using only necessary columns)
            query = """
                INSERT INTO market_structure_results (
                    id, backtest_id, symbol, strategy_name,
                    initial_cash, pivot_bars, lower_timeframe,
                    start_date, end_date,
                    total_return, net_profit, net_profit_currency,
                    compounding_annual_return, final_value, start_equity, end_equity,
                    sharpe_ratio, sortino_ratio, max_drawdown,
                    probabilistic_sharpe_ratio, annual_standard_deviation, annual_variance,
                    beta, alpha,
                    total_trades, winning_trades, losing_trades, win_rate, loss_rate,
                    average_win, average_loss, profit_factor,
                    profit_loss_ratio, expectancy, total_orders,
                    information_ratio, tracking_error, treynor_ratio,
                    total_fees, estimated_strategy_capacity, lowest_capacity_asset,
                    portfolio_turnover,
                    pivot_highs_detected, pivot_lows_detected, bos_signals_generated,
                    position_flips, liquidation_events,
                    execution_time_ms, result_path, status, error_message,
                    cache_hit, created_at, resolution
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16,
                    $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28, $29, $30,
                    $31, $32, $33, $34, $35, $36, $37, $38, $39, $40, $41, $42, $43, $44,
                    $45, $46, $47, $48, $49, $50, $51, $52, $53, NOW()
                )
            """'''

# Also fix the column names in execute (average_win_percentage -> average_win, etc.)
old_execute_params = '''                Decimal(str(statistics.get('average_win', 0))),  # average_win_percentage
                Decimal(str(statistics.get('average_loss', 0))),  # average_loss_percentage'''

new_execute_params = '''                Decimal(str(statistics.get('average_win', 0))),  # average_win
                Decimal(str(statistics.get('average_loss', 0))),  # average_loss'''

# Replace the content
content = content.replace(old_insert, new_insert)
content = content.replace(old_execute_params, new_execute_params)

# Also remove the extra created_at parameter since we're using NOW()
content = content.replace(
    "                datetime.now(),  # created_at\n                statistics.get('resolution', task.request_data.get('resolution', 'Daily'))  # resolution",
    "                statistics.get('resolution', task.request_data.get('resolution', 'Daily'))  # resolution"
)

# Write the updated file
with open('/home/ahmed/TheUltimate/backend/app/services/backtest_queue_manager.py', 'w') as f:
    f.write(content)

print("Fixed the database save issue in backtest_queue_manager.py")
print("Changes made:")
print("1. Updated column names (average_win_percentage -> average_win, average_loss_percentage -> average_loss)")
print("2. Used NOW() for created_at instead of passing it as parameter")
print("3. Adjusted parameter count from 55 to 54")