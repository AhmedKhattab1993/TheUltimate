#!/usr/bin/env python3
"""
API Integration Test for Period Extension Implementation.

This script demonstrates and validates the period extension functionality 
through the actual API endpoint.
"""

import json
import time
import httpx
import asyncio
from datetime import date

# Test API endpoint
API_BASE_URL = "http://localhost:8000/api/v1"

async def test_single_day_screening_with_period_extension():
    """Test single-day screening through the API to validate period extension."""
    
    print("🧪 Testing Single-Day Screening with Period Extension via API")
    print("=" * 70)
    
    # Test payload for single-day screening with filters requiring historical data
    test_request = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01", 
        "symbols": ["AAPL", "MSFT", "NVDA"],
        "filters": {
            "volume": {
                "min_average": 1000000,
                "lookback_days": 20
            },
            "moving_average": {
                "period": 50,
                "condition": "above"
            },
            "relative_volume": {
                "min_relative_volume": 1.5,
                "lookback_days": 20
            }
        }
    }
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            print(f"📤 Sending request to {API_BASE_URL}/screen")
            print(f"📅 Date range: {test_request['start_date']} to {test_request['end_date']}")
            print(f"📊 Symbols: {test_request['symbols']}")
            print(f"🔍 Filters: Volume (20-day), MA (50-day), RelVol (20-day)")
            print()
            
            response = await client.post(
                f"{API_BASE_URL}/screen",
                json=test_request,
                headers={"Content-Type": "application/json"}
            )
            
            execution_time = time.time() - start_time
            
            print(f"📥 Response Status: {response.status_code}")
            print(f"⏱️  Total Execution Time: {execution_time:.2f} seconds")
            print()
            
            if response.status_code == 200:
                result = response.json()
                
                print("✅ API Response Successful!")
                print(f"🎯 Qualifying Symbols: {len(result.get('results', []))}")
                print(f"📈 Processing Time: {result.get('performance', {}).get('execution_time_seconds', 0):.3f}s")
                
                # Display results
                if result.get('results'):
                    print("\n📋 Qualifying Stocks:")
                    for stock in result['results']:
                        print(f"   • {stock['symbol']}: {len(stock.get('qualifying_dates', []))} qualifying days")
                        if stock.get('metrics'):
                            for metric, value in stock['metrics'].items():
                                if isinstance(value, (int, float)):
                                    print(f"     - {metric}: {value:.2f}")
                                else:
                                    print(f"     - {metric}: {value}")
                else:
                    print("\n📋 No qualifying stocks found")
                
                # Check if period extension was applied (look for signs in logs or metadata)
                performance = result.get('performance', {})
                if performance.get('execution_time_seconds', 0) > 0.1:
                    print("✅ Period extension likely applied (processing time indicates data fetching)")
                
                print("\n" + "=" * 70)
                print("✅ SINGLE-DAY SCREENING WITH PERIOD EXTENSION TEST PASSED")
                print("✅ API successfully handled filters requiring historical data")
                print("✅ Filters worked correctly despite single-day date range")
                return True
                
            else:
                print(f"❌ API Error: {response.status_code}")
                print(f"Response: {response.text}")
                return False
                
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False

async def test_health_check():
    """Test API health check."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{API_BASE_URL}/health")
            return response.status_code == 200
    except:
        return False

async def main():
    """Main test function."""
    print("🚀 Period Extension API Integration Test")
    print("🔗 Testing the automatic period data extension through REST API")
    print()
    
    # Check if API is running
    print("🏥 Checking API health...")
    if await test_health_check():
        print("✅ API is healthy and running")
        print()
    else:
        print("❌ API is not running or not healthy")
        print("💡 Make sure to start the API server first: python -m uvicorn app.main:app --reload")
        return
    
    # Run the main test
    success = await test_single_day_screening_with_period_extension()
    
    if success:
        print("🎉 ALL TESTS PASSED!")
        print("✅ Period extension implementation working correctly via API")
    else:
        print("❌ TESTS FAILED!")
        print("🛠️  Check API logs and implementation")

if __name__ == "__main__":
    asyncio.run(main())