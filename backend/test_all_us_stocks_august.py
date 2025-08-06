#!/usr/bin/env python3
"""
Test with ALL US stocks for August 1, 2025 to diagnose why no results are showing
"""
import asyncio
import httpx
import json

async def test_all_us_stocks_august_2025():
    """Test various filter combinations with ALL US stocks for August 1, 2025"""
    
    # The date you're using
    test_date = "2025-08-01"
    
    print(f"🔍 Testing ALL US STOCKS for {test_date}")
    print("="*80)
    
    # Start with NO filters, then add one at a time
    test_configs = [
        {
            "name": "1. NO FILTERS (Should return ALL stocks)",
            "filters": {}
        },
        {
            "name": "2. ONLY PRICE FILTER (Very Wide: $1-$1000)",
            "filters": {
                "price_range": {"min_price": 1.0, "max_price": 1000.0}
            }
        },
        {
            "name": "3. ONLY PRICE FILTER (Your Range: $2-$10)",
            "filters": {
                "price_range": {"min_price": 2.0, "max_price": 10.0}
            }
        },
        {
            "name": "4. ONLY GAP FILTER (1%)",
            "filters": {
                "gap": {"min_gap_percent": 1.0}
            }
        },
        {
            "name": "5. ONLY GAP FILTER (Your 4%)",
            "filters": {
                "gap": {"min_gap_percent": 4.0}
            }
        },
        {
            "name": "6. ONLY VOLUME FILTER (Low threshold)",
            "filters": {
                "volume": {"min_average": 100000, "lookback_days": 20}
            }
        },
        {
            "name": "7. ONLY RELATIVE VOLUME (1.1x)",
            "filters": {
                "relative_volume": {"min_relative_volume": 1.1, "lookback_days": 20}
            }
        },
        {
            "name": "8. YOUR EXACT FILTERS",
            "filters": {
                "gap": {"min_gap_percent": 4.0},
                "price_range": {"min_price": 2.0, "max_price": 10.0},
                "relative_volume": {"min_relative_volume": 2.0, "lookback_days": 20}
            }
        },
        {
            "name": "9. VERY LENIENT COMBO",
            "filters": {
                "gap": {"min_gap_percent": 0.5},
                "price_range": {"min_price": 1.0, "max_price": 50.0},
                "relative_volume": {"min_relative_volume": 1.1, "lookback_days": 20}
            }
        }
    ]
    
    # First, start the server
    print("Starting server...")
    server_process = await asyncio.create_subprocess_exec(
        "python3", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL
    )
    
    # Wait for server to start
    await asyncio.sleep(5)
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            # First check server health
            health = await client.get("http://localhost:8000/api/v1/health")
            print(f"Server health: {health.status_code}")
            
            for config in test_configs:
                print(f"\n{config['name']}")
                print("-"*80)
                
                request_data = {
                    "start_date": test_date,
                    "end_date": test_date,
                    "use_all_us_stocks": True,  # KEY: Using ALL US stocks
                    "filters": config['filters']
                }
                
                try:
                    response = await client.post(
                        "http://localhost:8000/api/v1/screen",
                        json=request_data
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        results = data.get('results', [])
                        total_screened = data.get('total_symbols_screened', 0)
                        execution_time = data.get('execution_time_ms', 0)
                        
                        print(f"✅ Status: SUCCESS")
                        print(f"📊 Screened: {total_screened} stocks in {execution_time:.0f}ms")
                        print(f"🎯 Results: {len(results)} stocks passed ({len(results)/total_screened*100:.2f}% pass rate)")
                        
                        if results:
                            # Show first 10 stocks
                            symbols = [r['symbol'] for r in results[:10]]
                            print(f"📈 Sample stocks: {symbols}")
                            if len(results) > 10:
                                print(f"   ... and {len(results) - 10} more stocks")
                            
                            # Show some metrics from first stock
                            if results[0].get('metrics'):
                                print(f"\n   Sample metrics for {results[0]['symbol']}:")
                                for key, value in list(results[0]['metrics'].items())[:5]:
                                    if isinstance(value, (int, float)):
                                        print(f"     - {key}: {value:.2f}")
                        else:
                            print("❌ No stocks passed these filters")
                            
                        # Check performance metrics
                        if 'performance_metrics' in data:
                            pm = data['performance_metrics']
                            print(f"\n   Performance:")
                            print(f"     - Used bulk endpoint: {pm.get('used_bulk_endpoint', False)}")
                            print(f"     - Data fetch time: {pm.get('data_fetch_time_ms', 0):.0f}ms")
                            
                    else:
                        print(f"❌ Error: {response.status_code}")
                        error_text = response.text[:500]
                        print(f"   Response: {error_text}")
                        
                except Exception as e:
                    print(f"❌ Request failed: {e}")
            
            # Special test: Check if we have data for August 2025
            print("\n" + "="*80)
            print("SPECIAL TEST: Checking data availability for August 2025")
            print("="*80)
            
            # Test a few specific stocks to see if we get data
            test_symbols = ["AAPL", "MSFT", "GOOGL"]
            request_data = {
                "start_date": test_date,
                "end_date": test_date,
                "symbols": test_symbols,
                "filters": {}  # No filters
            }
            
            response = await client.post(
                "http://localhost:8000/api/v1/screen",
                json=request_data
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get('total_symbols_screened', 0)
                print(f"✅ Data check: {total} stocks had data for {test_date}")
                
                # Check with period extension
                print("\nChecking with period-based filter (should trigger extension)...")
                request_data['filters'] = {
                    "relative_volume": {"min_relative_volume": 1.0, "lookback_days": 20}
                }
                
                response = await client.post(
                    "http://localhost:8000/api/v1/screen",
                    json=request_data
                )
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ Period extension working: {data.get('total_symbols_screened', 0)} stocks processed")
                
    finally:
        # Kill the server
        server_process.terminate()
        await server_process.wait()
    
    print("\n" + "="*80)
    print("ANALYSIS COMPLETE")
    print("="*80)

if __name__ == "__main__":
    print("🚀 Testing ALL US Stocks Screening for August 1, 2025\n")
    asyncio.run(test_all_us_stocks_august_2025())