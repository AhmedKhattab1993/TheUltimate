#!/usr/bin/env python3
"""
Extensive test to verify rate limiting has been removed
"""
import asyncio
import httpx
from datetime import date, timedelta
import json
import time

API_BASE_URL = "http://localhost:8000/api/v1"

async def test_extensive_rate_limiting():
    async with httpx.AsyncClient() as client:
        # Test with 20 stocks to ensure no rate limiting
        print("Extensive Rate Limiting Test\n" + "="*50 + "\n")
        
        # Use recent dates
        end_date = date.today() - timedelta(days=5)
        start_date = end_date - timedelta(days=30)
        
        # Test with 20 stocks
        symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", 
            "TSLA", "NVDA", "JPM", "V", "JNJ",
            "WMT", "PG", "UNH", "MA", "HD",
            "DIS", "BAC", "CVX", "ABBV", "PFE"
        ]
        
        screen_request = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": symbols,
            "filters": {
                "volume": {
                    "min_average": 500000,  # 500K shares
                    "lookback_days": 20
                }
            }
        }
        
        print(f"Screening {len(symbols)} stocks")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Filters: Average volume > 500K shares\n")
        
        # Start timing
        start_time = time.time()
        print("Starting request at:", time.strftime("%H:%M:%S"))
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/screen",
                json=screen_request,
                timeout=300.0  # 5 minute timeout
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                print(f"Completed at: {time.strftime('%H:%M:%S')}")
                print(f"\n✅ Screen completed successfully!")
                
                print(f"\nPerformance Metrics:")
                print(f"  - Total elapsed time: {elapsed_time:.2f} seconds")
                print(f"  - Server execution time: {result['execution_time_ms']/1000:.2f} seconds")
                print(f"  - Average time per stock: {elapsed_time/len(symbols):.2f} seconds")
                
                # Analysis
                print(f"\nRate Limiting Analysis:")
                if elapsed_time < 5:
                    print(f"  ✅ EXCELLENT: All {len(symbols)} stocks fetched in under 5 seconds!")
                    print(f"     This confirms rate limiting has been completely removed.")
                elif elapsed_time < 30:
                    print(f"  ✅ GOOD: All {len(symbols)} stocks fetched in under 30 seconds.")
                    print(f"     Rate limiting appears to be removed.")
                elif elapsed_time < 60:
                    print(f"  ⚠️  WARNING: Request took {elapsed_time:.0f} seconds.")
                    print(f"     This is slower than expected but no rate limiting detected.")
                else:
                    print(f"  ❌ FAIL: Request took {elapsed_time:.0f} seconds!")
                    print(f"     Rate limiting may still be active.")
                    print(f"     With rate limiting, this would take ~{(len(symbols)-1)*60} seconds")
                
                print(f"\nResults Summary:")
                print(f"  - Symbols screened: {result['total_symbols_screened']}")
                print(f"  - Qualifying stocks: {result['total_qualifying_stocks']}")
                
            else:
                print(f"\n❌ Error: {response.status_code}")
                print(f"Response: {response.text}")
                
        except httpx.TimeoutException:
            elapsed_time = time.time() - start_time
            print(f"\n❌ Request timed out after {elapsed_time:.2f} seconds!")
            
        except Exception as e:
            elapsed_time = time.time() - start_time
            print(f"\n❌ Error after {elapsed_time:.2f} seconds: {e}")

if __name__ == "__main__":
    print("Extensive Rate Limiting Test for Stock Screener\n")
    asyncio.run(test_extensive_rate_limiting())