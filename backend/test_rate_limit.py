#!/usr/bin/env python3
"""
Test script to verify rate limiting has been removed/increased for paid API tier
"""

import asyncio
import time
import httpx
from datetime import datetime

API_URL = "http://localhost:8000/api/v1"

async def test_screening_speed():
    """Test the screening endpoint to measure performance"""
    
    # Test with 30 stocks
    symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", 
        "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
        "PFE", "CVX", "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO",
        "VZ", "ADBE", "CMCSA"
    ]
    
    request_payload = {
        "symbols": symbols,
        "filters": {
            "volume": {
                "enabled": True,
                "min_volume": 1000000
            }
        },
        "date_range": {
            "days_back": 30
        }
    }
    
    print(f"Testing screening performance with {len(symbols)} stocks...")
    print(f"Started at: {datetime.now()}")
    
    start_time = time.time()
    
    try:
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(
                f"{API_URL}/screen",
                json=request_payload
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                print(f"\nScreening completed successfully!")
                print(f"Time taken: {elapsed_time:.2f} seconds")
                print(f"Requests per second: {len(symbols) / elapsed_time:.2f}")
                print(f"Average time per stock: {elapsed_time / len(symbols):.2f} seconds")
                print(f"\nResults summary:")
                print(f"- Total stocks processed: {data['summary']['total_stocks_processed']}")
                print(f"- Qualifying stocks: {data['summary']['total_qualifying_stocks']}")
                print(f"- Processing time (server): {data['summary']['processing_time_ms']:.2f}ms")
                
                # Check if we're hitting rate limits
                if elapsed_time > 60:
                    print("\n⚠️  WARNING: Screening took more than 1 minute!")
                    print("This suggests rate limiting is still active.")
                else:
                    print("\n✅ SUCCESS: Screening completed quickly!")
                    print("Rate limiting appears to be disabled or set to a high limit.")
                    
            else:
                print(f"\n❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
    except Exception as e:
        print(f"\n❌ Error during test: {e}")

async def test_individual_requests():
    """Test making rapid individual requests to check rate limiting"""
    
    print("\n\nTesting rapid individual requests...")
    symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META"]
    
    request_times = []
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for symbol in symbols:
            start = time.time()
            
            try:
                response = await client.post(
                    f"{API_URL}/screen",
                    json={
                        "symbols": [symbol],
                        "filters": {
                            "volume": {
                                "enabled": True,
                                "min_volume": 1000000
                            }
                        },
                        "date_range": {
                            "days_back": 30
                        }
                    }
                )
                
                end = time.time()
                request_time = end - start
                request_times.append(request_time)
                
                if response.status_code == 200:
                    print(f"✓ {symbol}: {request_time:.2f}s")
                else:
                    print(f"✗ {symbol}: Error {response.status_code}")
                    
            except Exception as e:
                print(f"✗ {symbol}: Error - {e}")
    
    if request_times:
        avg_time = sum(request_times) / len(request_times)
        print(f"\nAverage request time: {avg_time:.2f}s")
        
        if avg_time > 12:  # If average is > 12s, we're likely hitting 5 req/min limit
            print("⚠️  Rate limiting detected - requests are being delayed")
        else:
            print("✅ No significant rate limiting detected")

async def main():
    """Run all tests"""
    print("=" * 60)
    print("Testing Polygon API Rate Limiting")
    print("=" * 60)
    
    # Test 1: Full screening performance
    await test_screening_speed()
    
    # Test 2: Individual rapid requests
    await test_individual_requests()
    
    print("\n" + "=" * 60)
    print("Test completed!")

if __name__ == "__main__":
    asyncio.run(main())