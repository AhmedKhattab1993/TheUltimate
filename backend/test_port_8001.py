#!/usr/bin/env python3
"""
Test screening on port 8001 which might have the latest code
"""
import asyncio
import httpx
import json

async def test_port_8001():
    """Test screening on port 8001"""
    
    request_data = {
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
    
    print("Testing port 8001 screening...")
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
                print(f"✅ Port 8001 screening successful!")
                print(f"Symbols screened: {data.get('total_symbols_screened', 0)}")
                print(f"Results found: {len(data.get('results', []))}")
                print(f"Execution time: {data.get('execution_time_ms', 0):.2f} ms")
                
                # Check for period extension features
                if 'performance_metrics' in data:
                    metrics = data['performance_metrics']
                    print(f"Performance metrics available: True")
                    print(f"- Used bulk endpoint: {metrics.get('used_bulk_endpoint', False)}")
                
                return True
            else:
                print(f"❌ Error: {response.status_code}")
                print(f"Response: {response.text[:500]}")
                return False
                
        except Exception as e:
            print(f"❌ Request failed: {e}")
            return False

if __name__ == "__main__":
    asyncio.run(test_port_8001())