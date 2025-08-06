#!/usr/bin/env python3
"""
Test current screening issue - why frontend is taking longer
"""
import asyncio
import time
import httpx
import json

async def test_screening_request():
    """Test the current screening request that's taking longer"""
    
    # Test data similar to what frontend sends
    request_data = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01", 
        "use_all_us_stocks": True,
        "filters": {
            "gap": {
                "min_gap_percent": 4.0
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
    
    print("Testing screening request...")
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    start_time = time.time()
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            print("\nSending request to http://localhost:8001/api/v1/screen...")
            response = await client.post(
                "http://localhost:8001/api/v1/screen",
                json=request_data
            )
            
            end_time = time.time()
            elapsed = end_time - start_time
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response Time: {elapsed:.2f} seconds")
            
            if response.status_code == 200:
                data = response.json()
                print(f"Results: {len(data.get('results', []))} stocks found")
                print(f"Symbols screened: {data.get('total_symbols_screened', 0)}")
                print(f"Server execution time: {data.get('execution_time_ms', 0):.2f} ms")
                
                # Check performance metrics if available
                if 'performance_metrics' in data:
                    metrics = data['performance_metrics']
                    print(f"\nPerformance Metrics:")
                    print(f"- Data fetch time: {metrics.get('data_fetch_time_ms', 0):.2f} ms")
                    print(f"- Filter time: {metrics.get('filter_time_ms', 0):.2f} ms")
                    print(f"- API calls made: {metrics.get('api_calls_made', 0)}")
                    print(f"- Used bulk endpoint: {metrics.get('used_bulk_endpoint', False)}")
                
            else:
                print(f"Error: {response.text}")
                
        except Exception as e:
            print(f"Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_screening_request())