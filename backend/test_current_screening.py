#!/usr/bin/env python3
"""
Test current screening functionality to verify the server is working
"""
import asyncio
import httpx
import json

async def test_current_screening():
    """Test the current screening with a simple request"""
    
    request_data = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "filters": {
            "price_range": {
                "min_price": 1.0,
                "max_price": 1000.0
            }
        }
    }
    
    print("Testing current screening functionality...")
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/screen",
                json=request_data
            )
            
            print(f"\nResponse Status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"✅ Screening successful!")
                print(f"Symbols screened: {data.get('total_symbols_screened', 0)}")
                print(f"Results found: {len(data.get('results', []))}")
                print(f"Execution time: {data.get('execution_time_ms', 0):.2f} ms")
                
                # Check if period extension is working
                if 'performance_metrics' in data:
                    metrics = data['performance_metrics']
                    print(f"Used bulk endpoint: {metrics.get('used_bulk_endpoint', False)}")
                    print(f"Data fetch time: {metrics.get('data_fetch_time_ms', 0):.2f} ms")
                
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_current_screening())