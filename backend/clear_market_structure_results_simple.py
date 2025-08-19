#!/usr/bin/env python3
"""
Simple script to clear the market_structure_results table using asyncpg.
"""

import asyncio
import asyncpg
import os
from datetime import datetime


async def clear_table():
    """Clear all data from market_structure_results table."""
    
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
        
        # First, check how many records exist
        print("Checking current records in market_structure_results table...")
        count = await conn.fetchval("SELECT COUNT(*) FROM market_structure_results")
        
        if count == 0:
            print("Table is already empty. Nothing to clear.")
            await conn.close()
            return
        
        print(f"\nFound {count} records in market_structure_results table.")
        
        # Show sample of records that will be deleted
        print("\nSample of records to be deleted (showing first 5):")
        rows = await conn.fetch("""
            SELECT id, backtest_id, symbol, strategy_name, start_date, end_date, created_at 
            FROM market_structure_results 
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        for row in rows:
            print(f"  - ID: {row['id']}, Symbol: {row['symbol']}, "
                  f"Strategy: {row['strategy_name']}, "
                  f"Period: {row['start_date']} to {row['end_date']}")
        
        # Ask for confirmation
        print(f"\n⚠️  WARNING: This will permanently delete ALL {count} records!")
        print("Type 'yes' to confirm or anything else to cancel.")
        confirm = input("Proceed? ").strip().lower()
        
        if confirm != 'yes':
            print("Operation cancelled.")
            await conn.close()
            return
        
        # Clear the table using TRUNCATE
        print("\nClearing market_structure_results table...")
        await conn.execute("TRUNCATE TABLE market_structure_results CASCADE")
        
        # Verify the table is empty
        new_count = await conn.fetchval("SELECT COUNT(*) FROM market_structure_results")
        
        if new_count == 0:
            print("✅ Table cleared successfully!")
        else:
            print(f"⚠️  Warning: Table still contains {new_count} records")
        
        # Also check cache tables
        try:
            cache_count = await conn.fetchval("SELECT COUNT(*) FROM cache_backtest_results")
            if cache_count > 0:
                print(f"\nFound {cache_count} cached backtest results.")
                clear_cache = input("Clear cache tables as well? (yes/no): ").strip().lower()
                if clear_cache == 'yes':
                    await conn.execute("TRUNCATE TABLE cache_backtest_results CASCADE")
                    print("✅ Cache tables cleared!")
        except:
            # Cache tables might not exist
            pass
        
        await conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("CLEAR MARKET STRUCTURE RESULTS TABLE")
    print("=" * 60)
    
    asyncio.run(clear_table())