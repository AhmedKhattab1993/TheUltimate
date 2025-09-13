#!/usr/bin/env python3
"""Analyze why parameter sweep with same session ID causes linkage issues."""

import asyncio
import asyncpg

async def analyze_issue():
    # Direct connection
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='stock_screener'
    )
    
    # Check the problematic session
    session_id = 'd345fd13-ca50-4e11-9c35-62cf443fc869'
    
    print(f"Analyzing session: {session_id}")
    print("="*80)
    
    # Check screener results for this session
    screener_info = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total_symbols,
            COUNT(DISTINCT created_at) as distinct_timestamps,
            MIN(created_at) as first_created,
            MAX(created_at) as last_created,
            MAX(created_at) - MIN(created_at) as time_span
        FROM screener_results
        WHERE session_id = $1
    ''', session_id)
    
    print("Screener Results:")
    print(f"  Total symbols: {screener_info['total_symbols']}")
    print(f"  Distinct timestamps: {screener_info['distinct_timestamps']}")
    print(f"  First created: {screener_info['first_created']}")
    print(f"  Last created: {screener_info['last_created']}")
    print(f"  Time span: {screener_info['time_span']}")
    
    # Check backtest links for this session
    links_info = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total_links,
            COUNT(DISTINCT symbol) as distinct_symbols,
            MIN(created_at) as first_created,
            MAX(created_at) as last_created
        FROM screener_backtest_links
        WHERE screener_session_id = $1
    ''', session_id)
    
    print("\nBacktest Links:")
    print(f"  Total links: {links_info['total_links']}")
    print(f"  Distinct symbols: {links_info['distinct_symbols']}")
    print(f"  First created: {links_info['first_created']}")
    print(f"  Last created: {links_info['last_created']}")
    
    # Check if screener results were created multiple times
    print("\n\nChecking screener result creation patterns...")
    print("-"*80)
    
    creation_patterns = await conn.fetch('''
        SELECT 
            DATE_TRUNC('second', created_at) as creation_second,
            COUNT(*) as symbols_created
        FROM screener_results
        WHERE session_id = $1
        GROUP BY DATE_TRUNC('second', created_at)
        ORDER BY creation_second
        LIMIT 10
    ''', session_id)
    
    print("Symbols created per second:")
    for row in creation_patterns:
        print(f"  {row['creation_second']}: {row['symbols_created']} symbols")
    
    # Check backtest results
    backtest_info = await conn.fetchrow('''
        SELECT 
            COUNT(*) as total_backtests,
            COUNT(DISTINCT br.symbol) as distinct_symbols
        FROM backtest_results br
        JOIN screener_backtest_links sbl ON br.backtest_id = sbl.backtest_id
        WHERE sbl.screener_session_id = $1
    ''', session_id)
    
    print(f"\nBacktest Results:")
    print(f"  Total backtests: {backtest_info['total_backtests']}")
    print(f"  Distinct symbols: {backtest_info['distinct_symbols']}")
    
    # Check cache service usage
    print("\n\nChecking cache patterns...")
    print("-"*80)
    
    cache_info = await conn.fetch('''
        SELECT 
            service,
            COUNT(*) as cache_entries,
            MIN(created_at) as first_cached,
            MAX(created_at) as last_cached
        FROM cache_service
        WHERE cache_key LIKE '%' || $1 || '%'
        GROUP BY service
    ''', str(session_id))
    
    for row in cache_info:
        print(f"{row['service']:10} | Entries: {row['cache_entries']} | "
              f"First: {row['first_cached']} | Last: {row['last_cached']}")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_issue())