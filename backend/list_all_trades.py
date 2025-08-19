#!/usr/bin/env python3
"""
List all trades in the database with summary statistics.
"""

import asyncio
import asyncpg
import os
from collections import defaultdict


async def list_trades():
    """List all trades with detailed information."""
    
    # Database connection parameters
    db_config = {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', '5432')),
        'database': os.getenv('DB_NAME', 'stock_screener'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', 'postgres')
    }
    
    try:
        # Connect to database
        conn = await asyncpg.connect(**db_config)
        
        print("=" * 100)
        print("ALL TRADES IN DATABASE")
        print("=" * 100)
        
        # Get all trades
        trades = await conn.fetch("""
            SELECT 
                bt.symbol_value,
                bt.trade_time AT TIME ZONE 'America/New_York' as trade_time_et,
                bt.direction,
                bt.quantity,
                bt.fill_price,
                bt.order_fee_amount,
                bt.backtest_id,
                msr.symbol as backtest_symbol,
                msr.strategy_name
            FROM backtest_trades bt
            JOIN market_structure_results msr ON bt.backtest_id = msr.backtest_id
            ORDER BY bt.trade_time
        """)
        
        if not trades:
            print("No trades found in database!")
            await conn.close()
            return
        
        # Print header
        print(f"\n{'#':<4} {'Symbol':<8} {'Time (ET)':<20} {'Dir':<5} {'Quantity':>10} {'Price':>10} {'Fee':>8} {'Strategy':<15}")
        print("-" * 100)
        
        # Print all trades
        for i, trade in enumerate(trades, 1):
            print(f"{i:<4} {trade['symbol_value']:<8} "
                  f"{trade['trade_time_et'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{trade['direction']:<5} {abs(trade['quantity']):>10.0f} "
                  f"{trade['fill_price']:>10.2f} {trade['order_fee_amount']:>8.2f} "
                  f"{trade['strategy_name']:<15}")
        
        # Summary statistics
        print("\n" + "=" * 100)
        print("SUMMARY STATISTICS")
        print("=" * 100)
        
        # Group by symbol
        symbol_stats = defaultdict(lambda: {
            'buy_count': 0, 'sell_count': 0, 'total_fees': 0,
            'buy_volume': 0, 'sell_volume': 0
        })
        
        for trade in trades:
            symbol = trade['symbol_value']
            if trade['direction'] == 'buy':
                symbol_stats[symbol]['buy_count'] += 1
                symbol_stats[symbol]['buy_volume'] += abs(trade['quantity']) * trade['fill_price']
            else:
                symbol_stats[symbol]['sell_count'] += 1
                symbol_stats[symbol]['sell_volume'] += abs(trade['quantity']) * trade['fill_price']
            symbol_stats[symbol]['total_fees'] += trade['order_fee_amount']
        
        print(f"\n{'Symbol':<10} {'Buy Trades':>12} {'Sell Trades':>12} {'Total Trades':>12} {'Buy Volume':>15} {'Sell Volume':>15} {'Total Fees':>12}")
        print("-" * 100)
        
        for symbol, stats in symbol_stats.items():
            total_trades = stats['buy_count'] + stats['sell_count']
            print(f"{symbol:<10} {stats['buy_count']:>12} {stats['sell_count']:>12} "
                  f"{total_trades:>12} ${stats['buy_volume']:>14,.2f} "
                  f"${stats['sell_volume']:>14,.2f} ${stats['total_fees']:>11,.2f}")
        
        # Overall summary
        total_trades = len(trades)
        total_buy_trades = sum(1 for t in trades if t['direction'] == 'buy')
        total_sell_trades = sum(1 for t in trades if t['direction'] == 'sell')
        total_fees = sum(t['order_fee_amount'] for t in trades)
        
        print("\n" + "-" * 100)
        print(f"{'TOTAL':<10} {total_buy_trades:>12} {total_sell_trades:>12} {total_trades:>12} "
              f"{' ':>15} {' ':>15} ${total_fees:>11,.2f}")
        
        # Time range
        first_trade = min(trades, key=lambda t: t['trade_time_et'])
        last_trade = max(trades, key=lambda t: t['trade_time_et'])
        
        print(f"\nTrade Period: {first_trade['trade_time_et'].strftime('%Y-%m-%d %H:%M:%S')} ET "
              f"to {last_trade['trade_time_et'].strftime('%Y-%m-%d %H:%M:%S')} ET")
        
        # Backtests represented
        unique_backtests = set(t['backtest_id'] for t in trades)
        print(f"Backtests: {len(unique_backtests)}")
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(list_trades())