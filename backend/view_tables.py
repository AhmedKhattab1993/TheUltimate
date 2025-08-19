#!/usr/bin/env python3
"""
Simple script to view database tables
"""
import asyncio
import sys
from datetime import datetime
from app.services.database import db_pool
import json

async def view_tables():
    async with db_pool.acquire() as conn:
        print("\n=== DATABASE TABLES ===\n")
        
        # List all tables
        tables = await conn.fetch("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public' 
            ORDER BY tablename
        """)
        
        print("Available tables:")
        for table in tables:
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table['tablename']}")
            print(f"  - {table['tablename']}: {count} rows")
        
        print("\n=== SCREENER RESULTS (Last 5) ===")
        screener_results = await conn.fetch("""
            SELECT request_hash, date_range, symbol_count, 
                   created_at, access_count
            FROM screener_results 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        for row in screener_results:
            date_range = json.loads(row['date_range'])
            print(f"\nHash: {row['request_hash'][:16]}...")
            print(f"Date Range: {date_range['start']} to {date_range['end']}")
            print(f"Symbols Found: {row['symbol_count']}")
            print(f"Created: {row['created_at']}")
            print(f"Accessed: {row['access_count']} times")
        
        print("\n=== MARKET STRUCTURE RESULTS (Last 5) ===")
        backtest_results = await conn.fetch("""
            SELECT symbol, total_return, sharpe_ratio, max_drawdown,
                   created_at, status
            FROM market_structure_results 
            ORDER BY created_at DESC 
            LIMIT 5
        """)
        
        for row in backtest_results:
            print(f"\nSymbol: {row['symbol']}")
            print(f"Total Return: {row['total_return']:.2f}%" if row['total_return'] else "Total Return: N/A")
            print(f"Sharpe Ratio: {row['sharpe_ratio']:.2f}" if row['sharpe_ratio'] else "Sharpe Ratio: N/A")
            print(f"Max Drawdown: {row['max_drawdown']:.2f}%" if row['max_drawdown'] else "Max Drawdown: N/A")
            print(f"Status: {row['status']}")
            print(f"Created: {row['created_at']}")
        
        print("\n=== DAILY BARS (Last 5 entries) ===")
        daily_bars = await conn.fetch("""
            SELECT symbol, timestamp, open, high, low, close, volume
            FROM daily_bars 
            ORDER BY timestamp DESC 
            LIMIT 5
        """)
        
        for row in daily_bars:
            print(f"\n{row['symbol']} - {row['timestamp'].date()}")
            print(f"  Open: ${row['open']:.2f}, High: ${row['high']:.2f}")
            print(f"  Low: ${row['low']:.2f}, Close: ${row['close']:.2f}")
            print(f"  Volume: {row['volume']:,}")

if __name__ == "__main__":
    asyncio.run(view_tables())