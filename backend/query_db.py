#!/usr/bin/env python3
"""
Quick database query tool
Usage: ./query_db.py "SELECT * FROM screener_results LIMIT 5"
"""
import asyncio
import sys
from app.services.database import db_pool
import json
from tabulate import tabulate

async def run_query(query):
    async with db_pool.acquire() as conn:
        try:
            results = await conn.fetch(query)
            if results:
                # Convert to list of dicts for tabulate
                data = []
                for row in results:
                    row_dict = dict(row)
                    # Convert JSON fields to strings for display
                    for key, value in row_dict.items():
                        if isinstance(value, dict) or isinstance(value, list):
                            row_dict[key] = json.dumps(value)[:50] + "..."
                        elif isinstance(value, (int, float)) and value is not None:
                            if 'return' in key or 'ratio' in key or 'drawdown' in key:
                                row_dict[key] = f"{value:.2f}"
                    data.append(row_dict)
                
                print(tabulate(data, headers="keys", tablefmt="grid"))
                print(f"\nRows returned: {len(results)}")
            else:
                print("No results found")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        print("Usage: ./query_db.py 'YOUR SQL QUERY'")
        print("\nExample queries:")
        print("  ./query_db.py 'SELECT * FROM screener_results LIMIT 5'")
        print("  ./query_db.py 'SELECT symbol, total_return FROM market_structure_results ORDER BY total_return DESC LIMIT 10'")
        print("  ./query_db.py 'SELECT COUNT(*) FROM daily_bars'")
        sys.exit(1)
    
    asyncio.run(run_query(query))