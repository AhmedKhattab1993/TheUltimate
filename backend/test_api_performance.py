#!/usr/bin/env python3
"""
Test the screener API performance with parallel fetching optimizations.
"""

import httpx
import asyncio
import time
import json
from datetime import date, timedelta


async def test_api_performance():
    """Test the API performance improvements"""
    
    base_url = "http://localhost:8080/api/v1"
    
    # Test configuration
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # Different test sizes
    test_configs = [
        {
            "name": "Small set (10 symbols)",
            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", "V", "JNJ"]
        },
        {
            "name": "Medium set (30 symbols)",
            "symbols": None  # Will use default symbols
        },
        {
            "name": "Large set (all US stocks)",
            "use_all_us_stocks": True
        }
    ]
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        # First, check health
        print("Checking API health...")
        health_resp = await client.get(f"{base_url}/health")
        if health_resp.status_code == 200:
            print("API is healthy")
        else:
            print(f"API health check failed: {health_resp.status_code}")
            return
        
        print("\n" + "=" * 60)
        
        # Clear cache before tests
        print("Clearing cache...")
        cache_resp = await client.post(f"{base_url}/cache/clear")
        if cache_resp.status_code == 200:
            print("Cache cleared successfully")
        
        # Run performance tests
        for config in test_configs:
            print(f"\n{config['name']}:")
            print("-" * 40)
            
            # Prepare request
            request_data = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filters": {
                    "volume": {
                        "min_average": 1000000,
                        "lookback_days": 20
                    },
                    "price_change": {
                        "min_change": -5.0,
                        "max_change": 10.0,
                        "period_days": 1
                    }
                }
            }
            
            # Add symbols or use_all_us_stocks based on config
            if "symbols" in config and config["symbols"]:
                request_data["symbols"] = config["symbols"]
            elif "use_all_us_stocks" in config:
                request_data["use_all_us_stocks"] = config["use_all_us_stocks"]
                # Skip this test if it's too large
                print("Note: This test may take several minutes...")
                # Actually skip for now
                print("Skipping large test for quick verification")
                continue
            
            # Make request
            start_time = time.time()
            
            try:
                response = await client.post(
                    f"{base_url}/screen",
                    json=request_data
                )
                
                elapsed_time = time.time() - start_time
                
                if response.status_code == 200:
                    result = response.json()
                    print(f"✓ Success in {elapsed_time:.2f} seconds")
                    print(f"  Total symbols screened: {result['total_symbols_screened']}")
                    print(f"  Qualifying stocks: {result['total_qualifying_stocks']}")
                    print(f"  API execution time: {result['execution_time_ms']:.2f}ms")
                    
                    # Show some results
                    if result['results']:
                        print(f"  Sample results: {[r['symbol'] for r in result['results'][:5]]}")
                else:
                    print(f"✗ Failed with status {response.status_code}")
                    print(f"  Error: {response.text}")
                    
            except httpx.TimeoutException:
                print(f"✗ Request timed out after {elapsed_time:.2f} seconds")
            except Exception as e:
                print(f"✗ Error: {str(e)}")
        
        # Test cache effectiveness
        print("\n" + "=" * 60)
        print("Testing cache effectiveness...")
        print("-" * 40)
        
        # First request (no cache)
        print("\nFirst request (no cache):")
        start_time = time.time()
        response1 = await client.post(
            f"{base_url}/screen",
            json={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                "filters": {
                    "volume": {"min_average": 1000000}
                }
            }
        )
        time1 = time.time() - start_time
        print(f"  Time: {time1:.2f} seconds")
        
        # Second request (with cache)
        print("\nSecond request (same data, with cache):")
        start_time = time.time()
        response2 = await client.post(
            f"{base_url}/screen",
            json={
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
                "filters": {
                    "volume": {"min_average": 1000000}
                }
            }
        )
        time2 = time.time() - start_time
        print(f"  Time: {time2:.2f} seconds")
        print(f"  Speed improvement: {(time1/time2):.2f}x faster")


if __name__ == "__main__":
    print("Stock Screener API Performance Test")
    print("=" * 60)
    print("\nMake sure the API is running on http://localhost:8080")
    print("Starting tests in 3 seconds...\n")
    
    time.sleep(3)
    
    asyncio.run(test_api_performance())