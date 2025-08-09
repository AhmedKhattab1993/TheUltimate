#!/usr/bin/env python3
"""Test gap filter directly to debug why it returns no results."""

import asyncio
import asyncpg
from datetime import date, timedelta
import numpy as np
from backend.app.core.simple_filters import GapFilter

async def test_gap_filter():
    # Connect to database
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/stock_screener')
    
    try:
        # Get a sample of stocks to test
        symbols = await conn.fetch("""
            SELECT DISTINCT symbol 
            FROM daily_bars 
            WHERE time >= '2025-07-01' 
            LIMIT 10
        """)
        
        print(f"Testing {len(symbols)} symbols...")
        
        for row in symbols:
            symbol = row['symbol']
            
            # Get data for this symbol
            data = await conn.fetch("""
                SELECT time::date as date, open, close, high, low, volume
                FROM daily_bars
                WHERE symbol = $1 
                AND time >= '2025-07-01' 
                AND time <= '2025-08-09'
                ORDER BY time
            """, symbol)
            
            if len(data) < 2:
                continue
            
            # Convert to numpy array
            dtype = [('date', 'U10'), ('open', 'f8'), ('close', 'f8'), 
                     ('high', 'f8'), ('low', 'f8'), ('volume', 'f8')]
            
            np_data = np.array([
                (str(r['date']), float(r['open']), float(r['close']), 
                 float(r['high']), float(r['low']), float(r['volume']))
                for r in data
            ], dtype=dtype)
            
            # Apply gap filter with 2% threshold
            gap_filter = GapFilter(gap_threshold=2.0, direction="both")
            result = gap_filter.apply(np_data, symbol)
            
            # Check for gaps manually
            gaps = []
            for i in range(1, len(data)):
                prev_close = float(data[i-1]['close'])
                curr_open = float(data[i]['open'])
                if prev_close > 0:
                    gap_pct = ((curr_open - prev_close) / prev_close) * 100
                    if abs(gap_pct) >= 2.0:
                        gaps.append((data[i]['date'], gap_pct))
            
            print(f"\n{symbol}:")
            print(f"  Days analyzed: {len(data)}")
            print(f"  Qualifying days (filter): {result.num_qualifying_days}")
            print(f"  Manual gap count: {len(gaps)}")
            
            if gaps:
                print("  Manual gaps found:")
                for date, gap_pct in gaps[:5]:  # Show first 5
                    print(f"    {date}: {gap_pct:.2f}%")
            
            if result.num_qualifying_days > 0:
                print(f"  Filter metrics: {result.metrics}")
    
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_gap_filter())