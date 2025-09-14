#!/usr/bin/env python3
"""
Analyze why UI screener results are not showing backtest data in Results tab.
"""

import asyncio
import asyncpg
from datetime import datetime, timedelta


async def analyze_join_issue():
    """Analyze the join issue between screener results and backtest data."""
    # Database connection
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='stock_screener'
    )
    
    try:
        print("=== ANALYZING UI SCREENER BACKTEST JOIN ISSUE ===\n")
        
        # 1. Check the structure of key tables
        print("1. Checking table structures...")
        
        # Check screener_results columns
        screener_columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'screener_results'
            AND column_name IN ('session_id', 'symbol', 'data_date', 'source')
            ORDER BY column_name
        """)
        
        print("screener_results key columns:")
        for col in screener_columns:
            print(f"  {col['column_name']}: {col['data_type']}")
        
        # Check screener_backtest_links columns
        links_columns = await conn.fetch("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'screener_backtest_links'
            ORDER BY column_name
        """)
        
        print("\nscreener_backtest_links columns:")
        for col in links_columns:
            print(f"  {col['column_name']}: {col['data_type']}")
        
        # 2. Check recent UI screener sessions
        print("\n2. Checking recent UI screener sessions...")
        ui_sessions = await conn.fetch("""
            SELECT DISTINCT session_id, source, data_date, COUNT(*) as symbol_count
            FROM screener_results
            WHERE source = 'ui'
            AND created_at > NOW() - INTERVAL '7 days'
            GROUP BY session_id, source, data_date
            ORDER BY data_date DESC, symbol_count DESC
            LIMIT 10
        """)
        
        print("Recent UI sessions:")
        for session in ui_sessions:
            print(f"  {session['session_id']} | {session['source']} | {session['data_date']} | {session['symbol_count']} symbols")
        
        # 3. Check recent pipeline sessions for comparison
        print("\n3. Checking recent pipeline sessions for comparison...")
        pipeline_sessions = await conn.fetch("""
            SELECT DISTINCT session_id, source, data_date, COUNT(*) as symbol_count
            FROM screener_results
            WHERE source = 'pipeline'
            AND created_at > NOW() - INTERVAL '7 days'
            GROUP BY session_id, source, data_date
            ORDER BY data_date DESC, symbol_count DESC
            LIMIT 5
        """)
        
        print("Recent pipeline sessions:")
        for session in pipeline_sessions:
            print(f"  {session['session_id']} | {session['source']} | {session['data_date']} | {session['symbol_count']} symbols")
        
        # 4. Check if there are any backtest links for UI sessions
        print("\n4. Checking backtest links for UI vs Pipeline...")
        
        ui_links_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT sbl.backtest_id)
            FROM screener_results sr
            LEFT JOIN screener_backtest_links sbl ON 
                sr.session_id = sbl.screener_session_id 
                AND sr.symbol = sbl.symbol 
                AND sr.data_date = sbl.data_date
            WHERE sr.source = 'ui'
            AND sr.created_at > NOW() - INTERVAL '7 days'
            AND sbl.backtest_id IS NOT NULL
        """)
        
        pipeline_links_count = await conn.fetchval("""
            SELECT COUNT(DISTINCT sbl.backtest_id)
            FROM screener_results sr
            LEFT JOIN screener_backtest_links sbl ON 
                sr.session_id = sbl.screener_session_id 
                AND sr.symbol = sbl.symbol 
                AND sr.data_date = sbl.data_date
            WHERE sr.source = 'pipeline'
            AND sr.created_at > NOW() - INTERVAL '7 days'
            AND sbl.backtest_id IS NOT NULL
        """)
        
        print(f"UI screener results with backtest links: {ui_links_count}")
        print(f"Pipeline screener results with backtest links: {pipeline_links_count}")
        
        # 5. Deep dive into a specific UI session
        if ui_sessions:
            test_session = ui_sessions[0]['session_id']
            test_date = ui_sessions[0]['data_date']
            
            print(f"\n5. Deep dive into UI session: {test_session}")
            print(f"   Date: {test_date}")
            
            # Get some sample symbols from this session
            sample_symbols = await conn.fetch("""
                SELECT symbol, session_id, data_date, created_at
                FROM screener_results
                WHERE session_id = $1
                ORDER BY symbol
                LIMIT 5
            """, test_session)
            
            print(f"   Sample symbols ({len(sample_symbols)}):")
            for sym in sample_symbols:
                print(f"     {sym['symbol']} | {sym['data_date']} | {sym['created_at']}")
            
            # Check if any of these symbols have backtest links
            if sample_symbols:
                test_symbol = sample_symbols[0]['symbol']
                test_symbol_date = sample_symbols[0]['data_date']
                
                print(f"\n   Checking links for {test_symbol} on {test_symbol_date}:")
                
                # Direct check in links table
                direct_links = await conn.fetch("""
                    SELECT screener_session_id, symbol, data_date, backtest_id, bulk_id, created_at
                    FROM screener_backtest_links
                    WHERE symbol = $1
                    AND data_date = $2
                    ORDER BY created_at DESC
                """, test_symbol, test_symbol_date)
                
                print(f"     Found {len(direct_links)} direct links for this symbol/date:")
                for link in direct_links:
                    print(f"       Session: {link['screener_session_id']}")
                    print(f"       Symbol: {link['symbol']}")
                    print(f"       Date: {link['data_date']}")
                    print(f"       Backtest: {link['backtest_id']}")
                    print(f"       Bulk ID: {link['bulk_id']}")
                    print(f"       Created: {link['created_at']}")
                    print()
                
                # Check if session IDs match
                matching_links = await conn.fetch("""
                    SELECT screener_session_id, symbol, data_date, backtest_id, bulk_id
                    FROM screener_backtest_links
                    WHERE screener_session_id = $1
                    AND symbol = $2
                    AND data_date = $3
                """, test_session, test_symbol, test_symbol_date)
                
                print(f"     Links matching exact session/symbol/date: {len(matching_links)}")
                
        # 6. Check data types and potential mismatches
        print("\n6. Checking for data type mismatches...")
        
        session_id_type_screener = await conn.fetchval("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'screener_results'
            AND column_name = 'session_id'
        """)
        
        session_id_type_links = await conn.fetchval("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'screener_backtest_links'
            AND column_name = 'screener_session_id'
        """)
        
        print(f"screener_results.session_id type: {session_id_type_screener}")
        print(f"screener_backtest_links.screener_session_id type: {session_id_type_links}")
        
        date_type_screener = await conn.fetchval("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'screener_results'
            AND column_name = 'data_date'
        """)
        
        date_type_links = await conn.fetchval("""
            SELECT data_type
            FROM information_schema.columns
            WHERE table_name = 'screener_backtest_links'
            AND column_name = 'data_date'
        """)
        
        print(f"screener_results.data_date type: {date_type_screener}")
        print(f"screener_backtest_links.data_date type: {date_type_links}")
        
        # 7. Test the actual join used in the view
        print("\n7. Testing the actual join from combined view...")
        
        combined_test = await conn.fetch("""
            SELECT 
                sr.session_id,
                sr.source,
                sr.symbol,
                sr.data_date,
                sbl.screener_session_id,
                sbl.backtest_id,
                sbl.bulk_id,
                CASE 
                    WHEN sbl.backtest_id IS NOT NULL THEN 'HAS_BACKTEST'
                    ELSE 'NO_BACKTEST'
                END as backtest_status
            FROM screener_results sr
            LEFT JOIN screener_backtest_links sbl ON 
                sr.session_id = sbl.screener_session_id 
                AND sr.symbol = sbl.symbol 
                AND sr.data_date = sbl.data_date
            WHERE sr.source = 'ui'
            AND sr.created_at > NOW() - INTERVAL '7 days'
            ORDER BY sr.created_at DESC
            LIMIT 20
        """)
        
        print(f"Sample combined results for UI source ({len(combined_test)} records):")
        ui_with_backtest = 0
        ui_without_backtest = 0
        
        for row in combined_test:
            if row['backtest_status'] == 'HAS_BACKTEST':
                ui_with_backtest += 1
            else:
                ui_without_backtest += 1
                
            print(f"  {row['symbol']} | {row['data_date']} | {row['backtest_status']} | Bulk: {row['bulk_id']}")
        
        print(f"\nSummary for UI results:")
        print(f"  With backtest data: {ui_with_backtest}")
        print(f"  Without backtest data: {ui_without_backtest}")
        
        # 8. Same test for pipeline for comparison
        print("\n8. Testing pipeline results for comparison...")
        
        pipeline_combined_test = await conn.fetch("""
            SELECT 
                sr.session_id,
                sr.source,
                sr.symbol,
                sr.data_date,
                sbl.screener_session_id,
                sbl.backtest_id,
                sbl.bulk_id,
                CASE 
                    WHEN sbl.backtest_id IS NOT NULL THEN 'HAS_BACKTEST'
                    ELSE 'NO_BACKTEST'
                END as backtest_status
            FROM screener_results sr
            LEFT JOIN screener_backtest_links sbl ON 
                sr.session_id = sbl.screener_session_id 
                AND sr.symbol = sbl.symbol 
                AND sr.data_date = sbl.data_date
            WHERE sr.source = 'pipeline'
            AND sr.created_at > NOW() - INTERVAL '7 days'
            ORDER BY sr.created_at DESC
            LIMIT 10
        """)
        
        print(f"Sample combined results for pipeline source ({len(pipeline_combined_test)} records):")
        pipeline_with_backtest = 0
        pipeline_without_backtest = 0
        
        for row in pipeline_combined_test:
            if row['backtest_status'] == 'HAS_BACKTEST':
                pipeline_with_backtest += 1
            else:
                pipeline_without_backtest += 1
                
            print(f"  {row['symbol']} | {row['data_date']} | {row['backtest_status']} | Bulk: {row['bulk_id']}")
        
        print(f"\nSummary for pipeline results:")
        print(f"  With backtest data: {pipeline_with_backtest}")
        print(f"  Without backtest data: {pipeline_without_backtest}")
        
        # 9. Check for any orphaned links
        print("\n9. Checking for orphaned backtest links...")
        
        orphaned_links = await conn.fetch("""
            SELECT sbl.screener_session_id, sbl.symbol, sbl.data_date, sbl.backtest_id, sbl.bulk_id
            FROM screener_backtest_links sbl
            LEFT JOIN screener_results sr ON 
                sbl.screener_session_id = sr.session_id
                AND sbl.symbol = sr.symbol
                AND sbl.data_date = sr.data_date
            WHERE sr.session_id IS NULL
            AND sbl.created_at > NOW() - INTERVAL '7 days'
            LIMIT 10
        """)
        
        print(f"Orphaned backtest links (links without corresponding screener results): {len(orphaned_links)}")
        for link in orphaned_links:
            print(f"  Session: {link['screener_session_id']} | Symbol: {link['symbol']} | Date: {link['data_date']}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(analyze_join_issue())