#!/usr/bin/env python3
"""
Test script to verify performance improvements with parallel fetching.
"""

import asyncio
import time
from datetime import date, timedelta
import os
import sys

# Add the app directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.polygon_client import PolygonClient
from app.config import settings


async def test_parallel_performance():
    """Test the performance of parallel vs sequential fetching"""
    
    # Test symbols - using more symbols to see the difference
    test_symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
        "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
        "PFE", "CVX", "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO",
        "VZ", "ADBE", "CMCSA", "NFLX", "INTC", "T", "ORCL", "IBM", "AMD",
        "QCOM", "TXN", "AVGO", "CRM", "PYPL", "NOW", "UBER", "SQ", "SHOP",
        "ROKU", "SNAP", "PINS", "TWTR", "ZM"
    ][:30]  # Limit to 30 symbols for reasonable test time
    
    # Date range
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    print(f"Testing performance with {len(test_symbols)} symbols")
    print(f"Date range: {start_date} to {end_date}")
    print("-" * 60)
    
    async with PolygonClient() as client:
        # Clear cache before testing
        client.clear_cache()
        
        # Test 1: Parallel fetching with different concurrency limits
        for max_concurrent in [1, 10, 50, 100]:
            print(f"\nTesting with max_concurrent={max_concurrent}")
            start_time = time.time()
            
            results = await client.fetch_batch_historical_data(
                symbols=test_symbols,
                start_date=start_date,
                end_date=end_date,
                adjusted=True,
                continue_on_error=True,
                max_concurrent=max_concurrent
            )
            
            elapsed_time = time.time() - start_time
            success_count = len(results)
            
            print(f"  Time taken: {elapsed_time:.2f} seconds")
            print(f"  Successful fetches: {success_count}/{len(test_symbols)}")
            print(f"  Average time per symbol: {elapsed_time/len(test_symbols):.2f} seconds")
            
            # Clear cache between tests
            client.clear_cache()
            
            # Small delay between tests
            await asyncio.sleep(2)
        
        # Test 2: Cache performance
        print("\n" + "-" * 60)
        print("Testing cache performance...")
        
        # First run - no cache
        print("\nFirst run (no cache):")
        start_time = time.time()
        results1 = await client.fetch_batch_historical_data(
            symbols=test_symbols[:10],  # Just 10 symbols for cache test
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            continue_on_error=True,
            max_concurrent=50
        )
        time_no_cache = time.time() - start_time
        print(f"  Time taken: {time_no_cache:.2f} seconds")
        
        # Second run - with cache
        print("\nSecond run (with cache):")
        start_time = time.time()
        results2 = await client.fetch_batch_historical_data(
            symbols=test_symbols[:10],  # Same symbols
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            continue_on_error=True,
            max_concurrent=50
        )
        time_with_cache = time.time() - start_time
        print(f"  Time taken: {time_with_cache:.2f} seconds")
        print(f"  Speed improvement: {(time_no_cache/time_with_cache):.2f}x faster")


if __name__ == "__main__":
    # Check if API key is set
    if not settings.polygon_api_key:
        print("Error: POLYGON_API_KEY environment variable not set")
        sys.exit(1)
    
    print("Stock Screener Parallel Performance Test")
    print("=" * 60)
    
    asyncio.run(test_parallel_performance())