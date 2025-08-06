#!/usr/bin/env python3
"""
Simple test with ALL US stocks for August 1, 2025
"""
import asyncio
import httpx
import json
import time

async def test_august_2025():
    """Test why no results for August 1, 2025"""
    
    # Wait for server
    await asyncio.sleep(3)
    
    test_date = "2025-08-01"
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        print(f"Testing ALL US stocks for {test_date}")
        print("="*60)
        
        # Test 1: No filters - should return everything
        print("\n1. NO FILTERS - Should return ALL stocks")
        request = {
            "start_date": test_date,
            "end_date": test_date,
            "use_all_us_stocks": True,
            "filters": {}
        }
        
        start = time.time()
        response = await client.post("http://localhost:8000/api/v1/screen", json=request)
        elapsed = time.time() - start
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Screened: {data.get('total_symbols_screened', 0)} stocks in {elapsed:.1f}s")
            print(f"✅ Results: {len(data.get('results', []))} stocks")
            if data.get('results'):
                print(f"   First 5: {[r['symbol'] for r in data['results'][:5]]}")
        else:
            print(f"❌ Error: {response.status_code}")
            
        # Test 2: Just price filter
        print("\n2. PRICE FILTER ONLY ($2-$10)")
        request['filters'] = {
            "price_range": {"min_price": 2.0, "max_price": 10.0}
        }
        
        response = await client.post("http://localhost:8000/api/v1/screen", json=request)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"✅ Results: {len(results)} stocks in $2-$10 range")
            if results:
                print(f"   Examples: {[r['symbol'] for r in results[:10]]}")
        
        # Test 3: Just gap filter
        print("\n3. GAP FILTER ONLY (4%)")
        request['filters'] = {
            "gap": {"min_gap_percent": 4.0}
        }
        
        response = await client.post("http://localhost:8000/api/v1/screen", json=request)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"✅ Results: {len(results)} stocks with gap >= 4%")
            if results:
                for r in results[:5]:
                    gap = r.get('metrics', {}).get('gap_percent', 0)
                    print(f"   {r['symbol']}: {gap:.1f}% gap")
        
        # Test 4: Your exact filters
        print("\n4. YOUR EXACT FILTERS")
        request['filters'] = {
            "gap": {"min_gap_percent": 4.0},
            "price_range": {"min_price": 2.0, "max_price": 10.0},
            "relative_volume": {"min_relative_volume": 2.0, "lookback_days": 20}
        }
        
        response = await client.post("http://localhost:8000/api/v1/screen", json=request)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            total = data.get('total_symbols_screened', 0)
            print(f"✅ Screened: {total} stocks")
            print(f"✅ Results: {len(results)} stocks passed ALL filters")
            print(f"   Pass rate: {len(results)/total*100:.2f}%")
            
            if results:
                print(f"\n🎯 STOCKS THAT PASSED YOUR FILTERS:")
                for r in results[:10]:
                    print(f"   - {r['symbol']}")
                    metrics = r.get('metrics', {})
                    if metrics:
                        print(f"     Gap: {metrics.get('gap_percent', 0):.1f}%")
                        print(f"     Price: ${metrics.get('current_price', 0):.2f}")
                        print(f"     Rel Vol: {metrics.get('relative_volume', 0):.1f}x")
            else:
                print("\n❌ No stocks passed all your filters")
                print("\nDIAGNOSIS:")
                print("- 4% gap is very strict")
                print("- $2-$10 range eliminates most stocks")
                print("- 2x relative volume is rare")
                print("- August 2025 is a future date - might have limited data")
                
        # Test with past date for comparison
        print("\n" + "="*60)
        print("COMPARISON: Testing with January 10, 2024 (past date)")
        print("="*60)
        
        request['start_date'] = "2024-01-10"
        request['end_date'] = "2024-01-10"
        
        response = await client.post("http://localhost:8000/api/v1/screen", json=request)
        
        if response.status_code == 200:
            data = response.json()
            results = data.get('results', [])
            print(f"✅ Results with past date: {len(results)} stocks")

if __name__ == "__main__":
    asyncio.run(test_august_2025())