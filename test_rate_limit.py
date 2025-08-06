#!/usr/bin/env python3
"""
Test script to verify rate limiting has been removed
"""
import asyncio
import httpx
from datetime import date, timedelta
import json
import time

API_BASE_URL = "http://localhost:8000/api/v1"

async def test_rate_limiting():
    async with httpx.AsyncClient() as client:
        # Test with 10 stocks to check for rate limiting
        print("Testing Rate Limiting Removal\n" + "="*50 + "\n")
        
        # Use recent dates to ensure data availability
        end_date = date.today() - timedelta(days=5)
        start_date = end_date - timedelta(days=30)
        
        # Test with 10 popular stocks
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", 
                   "TSLA", "NVDA", "JPM", "V", "JNJ"]
        
        screen_request = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": symbols,
            "filters": {
                "volume": {
                    "min_average": 1000000,  # 1M shares
                    "lookback_days": 20
                }
            }
        }
        
        print(f"Screening {len(symbols)} stocks: {', '.join(symbols)}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Filters: Average volume > 1M shares\n")
        
        # Start timing
        start_time = time.time()
        print("Starting request...")
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/screen",
                json=screen_request,
                timeout=120.0  # 2 minute timeout
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n✅ Screen completed successfully!")
                print(f"\nTiming Results:")
                print(f"  - Total elapsed time: {elapsed_time:.2f} seconds")
                print(f"  - Execution time (server): {result['execution_time_ms']:.2f}ms ({result['execution_time_ms']/1000:.2f}s)")
                print(f"  - Average time per stock: {elapsed_time/len(symbols):.2f} seconds")
                
                print(f"\nScreen Results:")
                print(f"  - Total symbols screened: {result['total_symbols_screened']}")
                print(f"  - Qualifying stocks: {result['total_qualifying_stocks']}")
                
                # Check if rate limiting would have been applied
                if elapsed_time > 60:
                    print(f"\n⚠️  WARNING: Request took over 60 seconds!")
                    print(f"    This suggests rate limiting may still be active.")
                else:
                    print(f"\n✅ PASS: Request completed in under 60 seconds!")
                    print(f"    Rate limiting appears to be successfully removed.")
                
                # Show individual stock results
                if result['results']:
                    print(f"\nIndividual Stock Results:")
                    for stock in result['results']:
                        days = len(stock['qualifying_dates'])
                        print(f"  - {stock['symbol']}: {days} qualifying days")
                        
            else:
                print(f"\n❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except httpx.TimeoutException:
            elapsed_time = time.time() - start_time
            print(f"\n❌ Request timed out after {elapsed_time:.2f} seconds!")
            print("This suggests the request is taking too long, possibly due to rate limiting.")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"\n❌ Error during screen after {elapsed_time:.2f} seconds: {e}")
        
        # Now let's check the server logs
        print("\n" + "="*50)
        print("Server Log Analysis")
        print("="*50)
        print("\nTo check server logs for rate limiting messages:")
        print("1. Look for messages like: 'Rate limit reached. Sleeping for X seconds'")
        print("2. Check the backend terminal where the server is running")
        print("3. The logs should show API calls being made without delays")

if __name__ == "__main__":
    print("Rate Limiting Test for Stock Screener\n")
    print("Make sure the backend is running on http://localhost:8000")
    print("Start it with: cd backend && python3 run.py\n")
    
    asyncio.run(test_rate_limiting())