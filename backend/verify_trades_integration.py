#!/usr/bin/env python3
"""
Verify that trades are being stored correctly in the database.
"""

import asyncio
import asyncpg
import os
from datetime import datetime
from zoneinfo import ZoneInfo


async def verify_trades():
    """Check trades storage integration."""
    
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
        
        print("=" * 80)
        print("TRADES STORAGE VERIFICATION")
        print("=" * 80)
        
        # 1. Check backtest results
        print("\n1. Latest Backtest Results:")
        print("-" * 80)
        
        backtests = await conn.fetch("""
            SELECT backtest_id, symbol, strategy_name, start_date, end_date,
                   total_trades, win_rate, sharpe_ratio, created_at
            FROM market_structure_results
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        if not backtests:
            print("No backtest results found!")
            await conn.close()
            return
        
        for bt in backtests:
            print(f"Backtest ID: {bt['backtest_id']}")
            print(f"  Symbol: {bt['symbol']}, Strategy: {bt['strategy_name']}")
            print(f"  Period: {bt['start_date']} to {bt['end_date']}")
            print(f"  Trades: {bt['total_trades']}, Win Rate: {bt['win_rate']}%")
            print(f"  Sharpe: {bt['sharpe_ratio']:.4f}")
            print(f"  Created: {bt['created_at']}")
            print()
        
        # 2. Check trades for latest backtest
        latest_backtest_id = backtests[0]['backtest_id']
        print(f"\n2. Trades for Latest Backtest ({latest_backtest_id}):")
        print("-" * 80)
        
        trade_count = await conn.fetchval("""
            SELECT COUNT(*) FROM backtest_trades
            WHERE backtest_id = $1
        """, latest_backtest_id)
        
        print(f"Total trades stored: {trade_count}")
        
        # 3. Sample trades with Eastern Time
        print("\n3. Sample Trades (First 10):")
        print("-" * 80)
        
        trades = await conn.fetch("""
            SELECT symbol, trade_time AT TIME ZONE 'America/New_York' as trade_time_et,
                   direction, quantity, fill_price, order_fee_amount
            FROM backtest_trades
            WHERE backtest_id = $1
            ORDER BY trade_time
            LIMIT 10
        """, latest_backtest_id)
        
        print(f"{'Symbol':<10} {'Time (ET)':<20} {'Dir':<5} {'Qty':>10} {'Price':>10} {'Fee':>8}")
        print("-" * 73)
        
        for trade in trades:
            print(f"{trade['symbol']:<10} {trade['trade_time_et'].strftime('%Y-%m-%d %H:%M:%S'):<20} "
                  f"{trade['direction']:<5} {trade['quantity']:>10.0f} "
                  f"{trade['fill_price']:>10.2f} {trade['order_fee_amount']:>8.2f}")
        
        # 4. Trade statistics
        print("\n4. Trade Statistics:")
        print("-" * 80)
        
        stats = await conn.fetchrow("""
            SELECT 
                COUNT(*) as total_trades,
                COUNT(CASE WHEN direction = 'buy' THEN 1 END) as buy_trades,
                COUNT(CASE WHEN direction = 'sell' THEN 1 END) as sell_trades,
                AVG(fill_price) as avg_price,
                SUM(order_fee_amount) as total_fees,
                MIN(trade_time AT TIME ZONE 'America/New_York') as first_trade,
                MAX(trade_time AT TIME ZONE 'America/New_York') as last_trade
            FROM backtest_trades
            WHERE backtest_id = $1
        """, latest_backtest_id)
        
        print(f"Total Trades: {stats['total_trades']}")
        print(f"Buy Trades: {stats['buy_trades']}")
        print(f"Sell Trades: {stats['sell_trades']}")
        print(f"Average Price: ${stats['avg_price']:.2f}")
        print(f"Total Fees: ${stats['total_fees']:.2f}")
        print(f"First Trade: {stats['first_trade'].strftime('%Y-%m-%d %H:%M:%S')} ET")
        print(f"Last Trade: {stats['last_trade'].strftime('%Y-%m-%d %H:%M:%S')} ET")
        
        # 5. Check all unique symbols
        print("\n5. All Traded Symbols:")
        print("-" * 80)
        
        symbols = await conn.fetch("""
            SELECT DISTINCT symbol_value, COUNT(*) as trade_count
            FROM backtest_trades
            GROUP BY symbol_value
            ORDER BY trade_count DESC
        """)
        
        for sym in symbols:
            print(f"{sym['symbol_value']}: {sym['trade_count']} trades")
        
        await conn.close()
        print("\n✅ Trade storage integration verified successfully!")
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    asyncio.run(verify_trades())