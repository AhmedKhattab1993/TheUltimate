#!/usr/bin/env python3
"""Analyze what happens when multiple parameter combinations use same session ID."""

import asyncio
import asyncpg

async def analyze_linkage_scenario():
    # Direct connection
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='stock_screener'
    )
    
    print("Analyzing linkage scenario for shared session IDs...")
    print("="*80)
    
    # Check unique constraint on screener_backtest_links
    constraint_info = await conn.fetch('''
        SELECT 
            tc.constraint_name,
            tc.constraint_type,
            kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = 'screener_backtest_links'
        AND tc.constraint_type IN ('PRIMARY KEY', 'UNIQUE')
        ORDER BY tc.constraint_name, kcu.ordinal_position
    ''')
    
    print("Constraints on screener_backtest_links:")
    current_constraint = None
    for row in constraint_info:
        if row['constraint_name'] != current_constraint:
            current_constraint = row['constraint_name']
            print(f"\n{row['constraint_type']}: {row['constraint_name']}")
            print("  Columns: ", end="")
        print(f"{row['column_name']}, ", end="")
    print("\n")
    
    # Simulate what happens with shared session ID
    print("\nScenario: Multiple parameter combinations with same session ID")
    print("-"*80)
    print("1. First combination (price 1-20, no RSI):")
    print("   - Screener finds: AAL, AMC, ARLO (3 symbols)")
    print("   - Backtests run for all 3")
    print("   - Links created: (session1, backtest_aal, AAL, 2025-08-05)")
    print("                   (session1, backtest_amc, AMC, 2025-08-05)")
    print("                   (session1, backtest_arlo, ARLO, 2025-08-05)")
    print()
    print("2. Second combination (price 1-20, RSI > 70):")
    print("   - Screener finds: AAL, BTU, CAG (3 symbols, AAL overlaps)")
    print("   - Backtest for AAL: CACHED (uses same backtest_aal)")
    print("   - Backtest for BTU: NEW")
    print("   - Backtest for CAG: NEW")
    print("   - Links created: (session1, backtest_aal, AAL, 2025-08-05) <- CONFLICT, DO NOTHING")
    print("                   (session1, backtest_btu, BTU, 2025-08-05)")
    print("                   (session1, backtest_cag, CAG, 2025-08-05)")
    print()
    print("Result: Links table has all 5 unique symbol links for session1")
    print()
    
    # Check actual data
    print("\nChecking actual data patterns...")
    print("-"*80)
    
    # Find sessions with multiple parameter combinations
    multi_param_sessions = await conn.fetch('''
        WITH param_groups AS (
            SELECT 
                session_id,
                data_date,
                COUNT(DISTINCT (
                    COALESCE(filter_min_price::text, 'null') || '-' ||
                    COALESCE(filter_max_price::text, 'null') || '-' ||
                    COALESCE(filter_rsi_enabled::text, 'null') || '-' ||
                    COALESCE(filter_rsi_threshold::text, 'null')
                )) as param_combinations,
                COUNT(DISTINCT symbol) as unique_symbols,
                COUNT(*) as total_rows
            FROM screener_results
            WHERE source = 'pipeline'
            GROUP BY session_id, data_date
            HAVING COUNT(DISTINCT (
                COALESCE(filter_min_price::text, 'null') || '-' ||
                COALESCE(filter_max_price::text, 'null') || '-' ||
                COALESCE(filter_rsi_enabled::text, 'null') || '-' ||
                COALESCE(filter_rsi_threshold::text, 'null')
            )) > 1
        )
        SELECT * FROM param_groups
        ORDER BY param_combinations DESC
        LIMIT 5
    ''')
    
    if multi_param_sessions:
        print("Sessions with multiple parameter combinations:")
        for row in multi_param_sessions:
            print(f"Session: {row['session_id']}")
            print(f"  Date: {row['data_date']}")
            print(f"  Parameter combinations: {row['param_combinations']}")
            print(f"  Unique symbols: {row['unique_symbols']}")
            print(f"  Total rows: {row['total_rows']}")
            
            # Check backtest links for this session
            link_count = await conn.fetchval('''
                SELECT COUNT(DISTINCT symbol)
                FROM screener_backtest_links
                WHERE screener_session_id = $1
                AND data_date = $2
            ''', row['session_id'], row['data_date'])
            
            print(f"  Backtest links: {link_count}")
            print(f"  Missing links: {row['unique_symbols'] - link_count}")
            print()
    else:
        print("No sessions found with multiple parameter combinations")
    
    await conn.close()

if __name__ == "__main__":
    asyncio.run(analyze_linkage_scenario())