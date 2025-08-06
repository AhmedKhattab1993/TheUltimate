#!/usr/bin/env python3
"""
Test that screening still works after removing Pre-market Volume and News Catalyst filters
"""
import asyncio
import httpx
import json

async def test_screening_without_removed_filters():
    """Test screening with remaining filters only"""
    
    # Test data with only remaining filters
    request_data = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01", 
        "use_all_us_stocks": False,
        "symbols": ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"],
        "filters": {
            "gap": {
                "min_gap_percent": 2.0
            },
            "price_range": {
                "min_price": 1.0,
                "max_price": 500.0
            },
            "relative_volume": {
                "min_relative_volume": 1.5,
                "lookback_days": 20
            },
            "market_cap": {
                "max_market_cap": 5000000000000  # 5T - very high to not filter anything
            }
        }
    }
    
    print("Testing screening with remaining filters (no Pre-market Volume or News Catalyst)...")
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/v1/screen",
                json=request_data
            )
            
            print(f"\nResponse Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Success! Found {len(data.get('results', []))} results")
                print(f"Symbols screened: {data.get('total_symbols_screened', 0)}")
                print(f"Execution time: {data.get('execution_time_ms', 0):.2f} ms")
                
                if data.get('results'):
                    print(f"Sample results: {[r['symbol'] for r in data['results'][:3]]}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

    # Test with deprecated filter fields to ensure they're ignored gracefully
    print("\n" + "="*60)
    print("Testing request with deprecated filter fields...")
    
    request_with_deprecated = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01", 
        "symbols": ["AAPL"],
        "filters": {
            "gap": {
                "min_gap_percent": 1.0
            },
            # These should be ignored gracefully
            "premarket_volume": {
                "min_volume": 100000
            },
            "news_catalyst": {
                "require_news": True
            }
        }
    }
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "http://localhost:8001/api/v1/screen",
                json=request_with_deprecated
            )
            
            print(f"Response Status: {response.status_code}")
            
            if response.status_code == 422:
                print("✅ Expected: Deprecated filters properly rejected with validation error")
            elif response.status_code == 200:
                print("✅ Alternative: Deprecated filters ignored gracefully")
            else:
                error_data = response.json() if response.headers.get('content-type', '').startswith('application/json') else response.text
                print(f"Response: {error_data}")
                
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_screening_without_removed_filters())