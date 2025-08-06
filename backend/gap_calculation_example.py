#!/usr/bin/env python3
"""
Example demonstrating how to use the enhanced gap calculation functionality.

This example shows how the gap percentage calculation fix handles both multi-day
and single-day screening scenarios.
"""

import asyncio
import sys
import os
from datetime import date, timedelta

# Add the project root to Python path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.services.screener import ScreenerEngine
from app.services.polygon_client import PolygonClient
from app.core.day_trading_filters import GapFilter
from app.config import settings


async def gap_calculation_example():
    """
    Example usage of the enhanced gap calculation functionality.
    """
    
    print("=== Gap Calculation Enhancement Example ===\n")
    
    # Configuration check
    print("Configuration:")
    print(f"  Async gap calculation enabled: {settings.enable_async_gap_calculation}")
    print(f"  Cache TTL: {settings.previous_day_cache_ttl} seconds")
    print(f"  Max lookback days: {settings.max_previous_day_lookback}")
    print()
    
    if not settings.polygon_api_key:
        print("⚠️  No Polygon API key found.")
        print("   Set POLYGON_API_KEY environment variable to run live examples.")
        print("   The implementation will work with API key provided.\n")
        
        # Show how to configure for production use
        print("Production Usage Example:")
        print("```python")
        print("# For multi-day data (existing behavior - no changes needed)")
        print("screener = ScreenerEngine()")
        print("gap_filter = GapFilter(min_gap_percent=4.0)")
        print("results = screener.screen(multi_day_stock_data, [gap_filter])")
        print()
        print("# For single-day data (new async capability)")
        print("async with PolygonClient() as client:")
        print("    screener = ScreenerEngine(")
        print("        polygon_client=client,")
        print("        enable_async_gap_calculation=True")
        print("    )")
        print("    gap_filter = GapFilter(min_gap_percent=4.0)")
        print("    results = await screener.screen_async(single_day_stock_data, [gap_filter])")
        print("```")
        return
    
    try:
        # Example with real API data
        print("Fetching real market data example...")
        
        async with PolygonClient() as polygon_client:
            # Example 1: Traditional multi-day screening (backward compatible)
            print("\n1. Multi-day screening (traditional approach):")
            print("-" * 50)
            
            # Fetch 5 days of data for a few symbols
            end_date = date.today() - timedelta(days=1)  # Yesterday
            start_date = end_date - timedelta(days=4)    # 5 days ago
            
            symbols = ["AAPL", "MSFT"]
            multi_day_data = await polygon_client.fetch_batch_historical_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date
            )
            
            # Traditional screening (synchronous)
            screener = ScreenerEngine()
            gap_filter = GapFilter(min_gap_percent=2.0)  # 2% minimum gap
            
            multi_day_results = screener.screen(list(multi_day_data.values()), [gap_filter])
            
            print(f"  Processed: {multi_day_results.num_processed} symbols")
            print(f"  Qualifying: {len(multi_day_results.qualifying_symbols)} symbols")
            print(f"  Processing time: {multi_day_results.processing_time:.3f}s")
            
            # Example 2: Single-day screening with async enhancement
            print("\n2. Single-day screening (new async approach):")
            print("-" * 50)
            
            # Fetch only yesterday's data
            single_day_data = await polygon_client.fetch_batch_historical_data(
                symbols=symbols,
                start_date=end_date,
                end_date=end_date
            )
            
            # Enhanced screening with async gap calculation
            async_screener = ScreenerEngine(
                polygon_client=polygon_client,
                enable_async_gap_calculation=True
            )
            
            single_day_results = await async_screener.screen_async(
                list(single_day_data.values()), 
                [gap_filter]
            )
            
            print(f"  Processed: {single_day_results.num_processed} symbols")
            print(f"  Qualifying: {len(single_day_results.qualifying_symbols)} symbols")
            print(f"  Processing time: {single_day_results.processing_time:.3f}s")
            
            # Show detailed results for qualifying symbols
            if single_day_results.qualifying_symbols:
                print("\n  Qualifying symbols with gap details:")
                for symbol in single_day_results.qualifying_symbols:
                    result = single_day_results.results[symbol]
                    print(f"    {symbol}: {result.metrics.get('gap_percent_mean', 0):.2f}% gap")
            
            print("\n3. Performance comparison:")
            print("-" * 50)
            print(f"  Multi-day processing:  {multi_day_results.processing_time:.3f}s")
            print(f"  Single-day processing: {single_day_results.processing_time:.3f}s")
            print(f"  Async overhead:        {abs(single_day_results.processing_time - multi_day_results.processing_time):.3f}s")
            
            # Example 3: Bulk single-day screening
            print("\n4. Bulk single-day screening:")
            print("-" * 50)
            
            # Fetch single-day data for more symbols
            bulk_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]
            bulk_single_day = await polygon_client.fetch_batch_historical_data(
                symbols=bulk_symbols,
                start_date=end_date,
                end_date=end_date
            )
            
            bulk_results = await async_screener.screen_async(
                list(bulk_single_day.values()),
                [GapFilter(min_gap_percent=1.0)]  # Lower threshold for demo
            )
            
            print(f"  Bulk processed: {bulk_results.num_processed} symbols")
            print(f"  Bulk qualifying: {len(bulk_results.qualifying_symbols)} symbols")
            print(f"  Bulk time: {bulk_results.processing_time:.3f}s")
            
    except Exception as e:
        print(f"❌ Error in example: {e}")
        print("This could be due to API limits, network issues, or market hours.")
    
    print("\n=== Key Benefits of the Enhancement ===")
    print("✓ Backward compatible: Existing code continues to work unchanged")
    print("✓ Automatic optimization: Multi-day data uses fast vectorized operations")
    print("✓ Single-day support: Missing previous day data is fetched automatically")
    print("✓ Intelligent caching: Reduces API calls with 24-hour cache")
    print("✓ Graceful fallback: Handles API failures and missing data")
    print("✓ Configurable: Enable/disable via environment variables")


if __name__ == "__main__":
    asyncio.run(gap_calculation_example())