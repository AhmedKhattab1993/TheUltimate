#!/usr/bin/env python3
"""
Script to clear the market_structure_results table.
This will delete all backtest results from the database.
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime


def get_db_connection():
    """Get database connection using environment variables."""
    return psycopg2.connect(
        host=os.getenv('DB_HOST', 'localhost'),
        port=os.getenv('DB_PORT', '5432'),
        database=os.getenv('DB_NAME', 'trading_system'),
        user=os.getenv('DB_USER', 'postgres'),
        password=os.getenv('DB_PASSWORD', 'postgres')
    )


def clear_market_structure_results():
    """Clear all data from market_structure_results table."""
    conn = None
    cur = None
    
    try:
        # Connect to database
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        
        # First, check how many records exist
        print("Checking current records in market_structure_results table...")
        cur.execute("SELECT COUNT(*) as total_records FROM market_structure_results")
        result = cur.fetchone()
        total_records = result['total_records']
        
        if total_records == 0:
            print("Table is already empty. Nothing to clear.")
            return
        
        print(f"\nFound {total_records} records in market_structure_results table.")
        
        # Show sample of records that will be deleted
        print("\nSample of records to be deleted:")
        cur.execute("""
            SELECT id, backtest_id, symbol, strategy_name, start_date, end_date, created_at 
            FROM market_structure_results 
            ORDER BY created_at DESC
            LIMIT 5
        """)
        
        for row in cur.fetchall():
            print(f"  - ID: {row['id']}, Symbol: {row['symbol']}, "
                  f"Strategy: {row['strategy_name']}, "
                  f"Period: {row['start_date']} to {row['end_date']}")
        
        # Ask for confirmation
        print(f"\n⚠️  WARNING: This will permanently delete ALL {total_records} records!")
        confirm = input("Are you sure you want to proceed? (yes/no): ").strip().lower()
        
        if confirm != 'yes':
            print("Operation cancelled.")
            return
        
        # Create backup timestamp
        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Optional: Export data before deletion
        print(f"\nExporting data to backup file before deletion...")
        cur.execute("""
            COPY (SELECT * FROM market_structure_results) 
            TO STDOUT WITH CSV HEADER
        """)
        
        backup_file = f"market_structure_results_backup_{backup_timestamp}.csv"
        with open(backup_file, 'w') as f:
            for line in cur:
                f.write(line)
        
        print(f"Backup saved to: {backup_file}")
        
        # Clear the table using TRUNCATE
        print("\nClearing market_structure_results table...")
        cur.execute("TRUNCATE TABLE market_structure_results CASCADE")
        
        # Commit the transaction
        conn.commit()
        
        # Verify the table is empty
        cur.execute("SELECT COUNT(*) as total_records FROM market_structure_results")
        result = cur.fetchone()
        
        if result['total_records'] == 0:
            print("✅ Table cleared successfully!")
        else:
            print(f"⚠️  Warning: Table still contains {result['total_records']} records")
        
        # Also clear any cached results if cache tables exist
        try:
            cur.execute("SELECT COUNT(*) FROM cache_backtest_results")
            cache_count = cur.fetchone()['count']
            if cache_count > 0:
                print(f"\nFound {cache_count} cached backtest results.")
                clear_cache = input("Clear cache tables as well? (yes/no): ").strip().lower()
                if clear_cache == 'yes':
                    cur.execute("TRUNCATE TABLE cache_backtest_results CASCADE")
                    conn.commit()
                    print("✅ Cache tables cleared!")
        except:
            # Cache tables might not exist
            pass
            
    except Exception as e:
        print(f"❌ Error: {e}")
        if conn:
            conn.rollback()
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


if __name__ == "__main__":
    print("=" * 60)
    print("CLEAR MARKET STRUCTURE RESULTS TABLE")
    print("=" * 60)
    
    clear_market_structure_results()