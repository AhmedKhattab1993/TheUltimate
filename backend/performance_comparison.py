#!/usr/bin/env python3
"""
Performance comparison analysis for stock screener optimizations.
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


async def compare_sequential_vs_parallel():
    """Compare sequential vs parallel fetching performance"""
    
    # Test symbols
    test_symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
        "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
        "PFE", "CVX"
    ]
    
    # Date range
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    print("PERFORMANCE COMPARISON: Sequential vs Parallel Fetching")
    print("=" * 70)
    print(f"Testing with {len(test_symbols)} symbols")
    print(f"Date range: {start_date} to {end_date}")
    print()
    
    async with PolygonClient() as client:
        # Clear cache before testing
        client.clear_cache()
        
        # Test 1: Sequential fetching (simulated with max_concurrent=1)
        print("1. SEQUENTIAL FETCHING (max_concurrent=1)")
        print("-" * 50)
        start_time = time.time()
        
        sequential_results = await client.fetch_batch_historical_data(
            symbols=test_symbols,
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            continue_on_error=True,
            max_concurrent=1
        )
        
        sequential_time = time.time() - start_time
        print(f"  Time taken: {sequential_time:.2f} seconds")
        print(f"  Successful fetches: {len(sequential_results)}/{len(test_symbols)}")
        print(f"  Average time per symbol: {sequential_time/len(test_symbols):.2f} seconds")
        
        # Clear cache
        client.clear_cache()
        await asyncio.sleep(1)
        
        # Test 2: Parallel fetching with optimal concurrency
        print("\n2. PARALLEL FETCHING (max_concurrent=50)")
        print("-" * 50)
        start_time = time.time()
        
        parallel_results = await client.fetch_batch_historical_data(
            symbols=test_symbols,
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            continue_on_error=True,
            max_concurrent=50
        )
        
        parallel_time = time.time() - start_time
        print(f"  Time taken: {parallel_time:.2f} seconds")
        print(f"  Successful fetches: {len(parallel_results)}/{len(test_symbols)}")
        print(f"  Average time per symbol: {parallel_time/len(test_symbols):.2f} seconds")
        
        # Performance improvement
        print("\n3. PERFORMANCE IMPROVEMENT")
        print("-" * 50)
        speedup = sequential_time / parallel_time
        print(f"  Speedup: {speedup:.2f}x faster")
        print(f"  Time saved: {sequential_time - parallel_time:.2f} seconds")
        print(f"  Efficiency gain: {((speedup - 1) / speedup * 100):.1f}%")
        
        # Test 3: Cache performance
        print("\n4. CACHE PERFORMANCE")
        print("-" * 50)
        
        # First request (data already in cache from parallel test)
        print("  Testing cache hit performance...")
        start_time = time.time()
        
        cache_results = await client.fetch_batch_historical_data(
            symbols=test_symbols[:5],  # Just 5 symbols for cache test
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            continue_on_error=True,
            max_concurrent=50
        )
        
        cache_time = time.time() - start_time
        print(f"  Cache hit time: {cache_time:.4f} seconds")
        print(f"  Average per symbol: {cache_time/5:.4f} seconds")
        
        # Clear cache and fetch again
        client.clear_cache()
        await asyncio.sleep(1)
        
        print("\n  Testing cache miss performance...")
        start_time = time.time()
        
        no_cache_results = await client.fetch_batch_historical_data(
            symbols=test_symbols[:5],
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            continue_on_error=True,
            max_concurrent=50
        )
        
        no_cache_time = time.time() - start_time
        print(f"  Cache miss time: {no_cache_time:.4f} seconds")
        print(f"  Average per symbol: {no_cache_time/5:.4f} seconds")
        
        if cache_time > 0:
            cache_speedup = no_cache_time / cache_time
            print(f"\n  Cache speedup: {cache_speedup:.1f}x faster")
            print(f"  Cache efficiency: {((cache_speedup - 1) / cache_speedup * 100):.1f}%")
        
        # Test different concurrency levels
        print("\n5. CONCURRENCY LEVEL ANALYSIS")
        print("-" * 50)
        print("  Testing different max_concurrent values...")
        
        concurrency_levels = [1, 5, 10, 25, 50, 100]
        for level in concurrency_levels:
            client.clear_cache()
            await asyncio.sleep(0.5)
            
            start_time = time.time()
            results = await client.fetch_batch_historical_data(
                symbols=test_symbols[:10],  # 10 symbols for quick test
                start_date=start_date,
                end_date=end_date,
                adjusted=True,
                continue_on_error=True,
                max_concurrent=level
            )
            elapsed = time.time() - start_time
            
            throughput = len(results) / elapsed
            print(f"  max_concurrent={level:3d}: {elapsed:.2f}s ({throughput:.1f} symbols/sec)")


if __name__ == "__main__":
    # Check if API key is set
    if not settings.polygon_api_key:
        print("Error: POLYGON_API_KEY environment variable not set")
        sys.exit(1)
    
    print("Stock Screener Performance Comparison")
    print("=" * 70)
    print()
    
    asyncio.run(compare_sequential_vs_parallel())