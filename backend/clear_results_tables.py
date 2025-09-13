#!/usr/bin/env python3
"""Clear all results data from the database tables."""

import asyncio
import asyncpg

async def clear_results():
    # Direct connection
    conn = await asyncpg.connect(
        host='localhost',
        port=5432,
        user='postgres',
        password='postgres',
        database='stock_screener'
    )
    
    try:
        print("Clearing results tables...")
        print("="*80)
        
        # Clear tables in correct order due to foreign key constraints
        tables = [
            ('screener_backtest_links', 'Screener-Backtest Links'),
            ('market_structure_results', 'Market Structure Results'),
            ('screener_results', 'Screener Results'),
            ('cache_service', 'Cache Service Entries')
        ]
        
        for table_name, display_name in tables:
            # Get count before deletion
            count = await conn.fetchval(f"SELECT COUNT(*) FROM {table_name}")
            
            if count > 0:
                # Delete all records
                await conn.execute(f"DELETE FROM {table_name}")
                print(f"✓ Cleared {count:,} records from {display_name}")
            else:
                print(f"- {display_name} was already empty")
        
        print("\nAll results tables have been cleared successfully!")
        
    except Exception as e:
        print(f"Error clearing tables: {e}")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(clear_results())