#!/usr/bin/env python3
"""
Direct test for August 1, 2025 issue
"""
import httpx
import asyncio

async def test():
    async with httpx.AsyncClient(timeout=300.0) as client:
        # Test 1: Specific stocks for August 2025
        print("Test 1: Testing 5 stocks for August 1, 2025...")
        response = await client.post(
            "http://localhost:8000/api/v1/screen",
            json={
                "start_date": "2025-08-01",
                "end_date": "2025-08-01",
                "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMD"],
                "filters": {}
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Screened: {data.get('total_symbols_screened')} stocks")
            print(f"✅ Results: {len(data.get('results', []))} stocks")
            results = data.get('results', [])
            if results:
                print("Stocks found:", [r['symbol'] for r in results])
        else:
            print(f"❌ Error: {response.status_code}")
            
        # Test 2: Same stocks with your filters
        print("\nTest 2: Same stocks with your filters...")
        response = await client.post(
            "http://localhost:8000/api/v1/screen",
            json={
                "start_date": "2025-08-01",
                "end_date": "2025-08-01",
                "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMD", "F", "GE", "BAC", "T", "INTC"],
                "filters": {
                    "gap": {"min_gap_percent": 4.0},
                    "price_range": {"min_price": 2.0, "max_price": 10.0},
                    "relative_volume": {"min_relative_volume": 2.0}
                }
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ With filters - Results: {len(data.get('results', []))}")
            
        # Test 3: Check if it's a future date issue
        print("\nTest 3: Testing past date (Jan 10, 2024)...")
        response = await client.post(
            "http://localhost:8000/api/v1/screen",
            json={
                "start_date": "2024-01-10",
                "end_date": "2024-01-10",
                "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMD"],
                "filters": {}
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Past date - Results: {len(data.get('results', []))}")
            
        # Test 4: All US stocks but with timeout handling
        print("\nTest 4: Testing ALL US stocks for August 1, 2025 (this may take time)...")
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/screen",
                json={
                    "start_date": "2025-08-01", 
                    "end_date": "2025-08-01",
                    "use_all_us_stocks": True,
                    "filters": {
                        "price_range": {"min_price": 2.0, "max_price": 10.0}
                    }
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                total = data.get('total_symbols_screened', 0)
                print(f"✅ ALL US STOCKS:")
                print(f"   - Total screened: {total}")
                print(f"   - In $2-$10 range: {len(results)} stocks")
                if results:
                    print(f"   - Examples: {[r['symbol'] for r in results[:20]]}")
                else:
                    print("   ❌ No stocks found in $2-$10 range for August 2025")
                    
        except Exception as e:
            print(f"❌ Error with all stocks: {e}")

asyncio.run(test())