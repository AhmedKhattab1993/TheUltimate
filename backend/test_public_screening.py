#!/usr/bin/env python3
"""
Test screening on the public server
"""
import asyncio
import httpx
import json

async def test_public_screening():
    """Test screening on the public server"""
    
    request_data = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "symbols": ["AAPL", "MSFT"],
        "filters": {
            "price_range": {
                "min_price": 50.0,
                "max_price": 500.0
            }
        }
    }
    
    print("Testing public server screening...")
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(
                "http://34.125.88.131:8000/api/v1/screen",
                json=request_data
            )
            
            print(f"\nResponse Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Public server screening successful!")
                print(f"Symbols screened: {data.get('total_symbols_screened', 0)}")
                print(f"Results found: {len(data.get('results', []))}")
                print(f"Execution time: {data.get('execution_time_ms', 0):.2f} ms")
                
                # Show some results
                if data.get('results'):
                    print(f"Sample symbols: {[r['symbol'] for r in data['results'][:5]]}")
                
                # Check performance metrics
                if 'performance_metrics' in data:
                    metrics = data['performance_metrics']
                    print(f"\nPerformance Metrics:")
                    print(f"- Used bulk endpoint: {metrics.get('used_bulk_endpoint', False)}")
                    print(f"- Data fetch time: {metrics.get('data_fetch_time_ms', 0):.2f} ms")
                    print(f"- Symbols fetched: {metrics.get('symbols_fetched', 0)}")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_public_screening())