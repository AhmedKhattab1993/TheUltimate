#!/usr/bin/env python3
"""
Test the final screening functionality with all our implementations
"""
import asyncio
import httpx
import json
import time

async def test_comprehensive_screening():
    """Test comprehensive screening with different filter types"""
    
    tests = [
        {
            "name": "Simple Price Range Filter",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-01",
                "symbols": ["AAPL"],
                "filters": {
                    "price_range": {
                        "min_price": 100.0,
                        "max_price": 300.0
                    }
                }
            }
        },
        {
            "name": "Gap Filter (requires previous day)",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-01",
                "symbols": ["AAPL", "MSFT"],
                "filters": {
                    "gap": {
                        "min_gap_percent": 1.0
                    }
                }
            }
        },
        {
            "name": "Relative Volume Filter (20-day lookback)",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-01",
                "symbols": ["AAPL", "MSFT", "GOOGL"],
                "filters": {
                    "relative_volume": {
                        "min_relative_volume": 1.5,
                        "lookback_days": 20
                    }
                }
            }
        },
        {
            "name": "All US Stocks with Day Trading Filters",
            "request": {
                "start_date": "2025-08-01",
                "end_date": "2025-08-01",
                "use_all_us_stocks": True,
                "filters": {
                    "gap": {
                        "min_gap_percent": 3.0
                    },
                    "price_range": {
                        "min_price": 2.0,
                        "max_price": 10.0
                    },
                    "relative_volume": {
                        "min_relative_volume": 2.0,
                        "lookback_days": 20
                    }
                }
            }
        }
    ]
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        for i, test in enumerate(tests, 1):
            print(f"\n{'='*60}")
            print(f"Test {i}: {test['name']}")
            print(f"{'='*60}")
            
            start_time = time.time()
            
            try:
                response = await client.post(
                    "http://34.125.88.131:8000/api/v1/screen",
                    json=test['request']
                )
                
                end_time = time.time()
                
                print(f"Response Status: {response.status_code}")
                print(f"Request Time: {end_time - start_time:.2f} seconds")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"✅ SUCCESS!")
                    print(f"   Symbols screened: {data.get('total_symbols_screened', 0)}")
                    print(f"   Results found: {len(data.get('results', []))}")
                    print(f"   Server execution time: {data.get('execution_time_ms', 0):.2f} ms")
                    
                    # Check for period extension and performance features
                    if 'performance_metrics' in data:
                        metrics = data['performance_metrics']
                        print(f"   Performance Metrics:")
                        print(f"     - Used bulk endpoint: {metrics.get('used_bulk_endpoint', False)}")
                        print(f"     - Data fetch time: {metrics.get('data_fetch_time_ms', 0):.2f} ms")
                        print(f"     - Symbols fetched: {metrics.get('symbols_fetched', 0)}")
                        print(f"     - Symbols failed: {metrics.get('symbols_failed', 0)}")
                    
                    # Show sample results
                    if data.get('results'):
                        symbols = [r['symbol'] for r in data['results'][:5]]
                        print(f"   Sample results: {symbols}")
                        
                else:
                    print(f"❌ FAILED: {response.status_code}")
                    print(f"   Response: {response.text[:300]}")
                    
            except Exception as e:
                print(f"❌ REQUEST FAILED: {e}")
                
            print(f"\n{'-'*60}")

if __name__ == "__main__":
    print("🧪 Testing comprehensive screening functionality...")
    print("🌐 Testing on public server: http://34.125.88.131:8000")
    asyncio.run(test_comprehensive_screening())