#!/usr/bin/env python3
"""
Test with the simplest possible screening request
"""
import asyncio
import httpx
import json

async def test_simple_screening():
    """Test with minimal request"""
    
    # Most basic request possible
    request_data = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "symbols": ["AAPL"],
        "filters": {}  # No filters
    }
    
    print("Testing simplest possible screening...")
    print(f"Request: {json.dumps(request_data, indent=2)}")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            response = await client.post(
                "http://34.125.88.131:8000/api/v1/screen",
                json=request_data
            )
            
            print(f"\nResponse Status: {response.status_code}")
            print(f"Response: {response.text[:1000]}")
                
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_simple_screening())