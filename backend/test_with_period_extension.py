#!/usr/bin/env python3
"""
Test stock screener with period extension to solve the "insufficient data" issue.
This test uses the screen_with_period_extension method which automatically fetches
the necessary historical data for filters.
"""

import asyncio
import sys
from datetime import date, timedelta
from typing import List, Dict, Any

# Add app to path
sys.path.append('/home/ahmed/TheUltimate/backend')

from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.core.day_trading_filters import (
    GapFilter,
    PriceRangeFilter,
    RelativeVolumeFilter,
    MarketCapFilter
)


async def test_with_period_extension():
    """Test screening with period extension to fix insufficient data issues."""
    
    # Initialize services
    polygon_client = PolygonClient()
    screener = ScreenerEngine(polygon_client=polygon_client)
    
    # Test parameters
    test_symbols = ['AAPL', 'MSFT', 'GOOGL', 'TSLA', 'NVDA', 'AMC', 'GME', 'SPY', 'QQQ', 'META']
    
    # Use a historical date instead of future date
    target_date = date(2024, 12, 31)  # Last trading day of 2024
    
    print(f"Testing stock screener with period extension for {target_date}")
    print("=" * 80)
    
    # Test different filter configurations
    filter_configs = [
        {
            'name': 'Lenient Filters',
            'filters': [
                GapFilter(min_gap_percent=1.0),  # 1% gap instead of 4%
                PriceRangeFilter(min_price=1.0, max_price=1000.0),  # Wider range
                RelativeVolumeFilter(min_relative_volume=1.2),  # 1.2x instead of 2x
            ]
        },
        {
            'name': 'Moderate Filters',
            'filters': [
                GapFilter(min_gap_percent=2.0),  # 2% gap
                PriceRangeFilter(min_price=5.0, max_price=500.0),
                RelativeVolumeFilter(min_relative_volume=1.5),  # 1.5x volume
            ]
        },
        {
            'name': 'Original Strict Filters',
            'filters': [
                GapFilter(min_gap_percent=4.0),  # Original 4% gap
                PriceRangeFilter(min_price=10.0, max_price=500.0),
                RelativeVolumeFilter(min_relative_volume=2.0),  # Original 2x volume
            ]
        },
        {
            'name': 'Gap Only (1%)',
            'filters': [GapFilter(min_gap_percent=1.0)]
        },
        {
            'name': 'Volume Only (1.2x)',
            'filters': [RelativeVolumeFilter(min_relative_volume=1.2)]
        }
    ]
    
    # Run tests for each configuration
    for config in filter_configs:
        print(f"\n\nTesting: {config['name']}")
        print("-" * 40)
        
        try:
            # Use screen_with_period_extension which automatically handles historical data requirements
            result, metadata = await screener.screen_with_period_extension(
                symbols=test_symbols,
                filters=config['filters'],
                start_date=target_date,
                end_date=target_date,
                polygon_client=polygon_client,
                auto_slice_results=True,  # Slice results back to target date
                adjusted=True,
                max_concurrent=10,
                prefer_bulk=True
            )
            
            # Display results
            print(f"Period Extension Applied: {metadata.get('period_extension_applied', False)}")
            if metadata.get('period_extension_applied'):
                print(f"Extended Start Date: {metadata.get('extended_start_date', 'N/A')}")
                print(f"Original Start Date: {metadata.get('original_start_date', 'N/A')}")
            
            print(f"\nResults Summary:")
            print(f"Total Symbols Processed: {len(test_symbols)}")
            print(f"Qualifying Symbols: {len(result.qualifying_symbols)}")
            print(f"Pass Rate: {(len(result.qualifying_symbols) / len(test_symbols) * 100):.1f}%")
            print(f"Processing Time: {result.processing_time:.2f} seconds")
            
            if result.qualifying_symbols:
                print(f"\nQualifying Symbols: {', '.join(result.qualifying_symbols)}")
                
                # Show details for first few qualifying symbols
                print("\nDetailed Results (first 3):")
                for symbol in result.qualifying_symbols[:3]:
                    if symbol in result.results:
                        filter_result = result.results[symbol]
                        print(f"\n  {symbol}:")
                        print(f"    Qualifying Days: {filter_result.num_qualifying_days}")
                        
                        # Show key metrics
                        metrics = filter_result.metrics
                        if 'gap_percent_mean' in metrics:
                            print(f"    Avg Gap %: {metrics['gap_percent_mean']:.2f}%")
                        if 'relative_volume_mean' in metrics:
                            print(f"    Avg Relative Volume: {metrics['relative_volume_mean']:.2f}x")
            else:
                print("\nNo qualifying symbols found.")
                
                # Analyze why stocks failed
                print("\nAnalyzing failures (first 3 symbols):")
                for symbol in test_symbols[:3]:
                    if symbol in result.results:
                        filter_result = result.results[symbol]
                        metrics = filter_result.metrics
                        
                        print(f"\n  {symbol}:")
                        if 'gap_percent_mean' in metrics:
                            print(f"    Gap % (avg): {metrics.get('gap_percent_mean', 0):.2f}%")
                            print(f"    Gap % (max): {metrics.get('gap_percent_max', 0):.2f}%")
                        if 'relative_volume_mean' in metrics:
                            print(f"    Relative Volume (avg): {metrics.get('relative_volume_mean', 0):.2f}x")
                            print(f"    Relative Volume (max): {metrics.get('relative_volume_max', 0):.2f}x")
                        if 'avg_price' in metrics:
                            print(f"    Avg Price: ${metrics.get('avg_price', 0):.2f}")
                    
        except Exception as e:
            print(f"Error running test: {e}")
            import traceback
            traceback.print_exc()
    
    # Test with OR logic (custom implementation)
    print("\n\n" + "="*80)
    print("TESTING WITH OR LOGIC (Any filter passes)")
    print("="*80)
    
    # Fetch data once for OR logic test
    print(f"\nFetching data for OR logic test...")
    extended_start = target_date - timedelta(days=30)
    
    stock_data_dict = await polygon_client.fetch_bulk_historical_data_with_fallback(
        symbols=test_symbols,
        start_date=extended_start,
        end_date=target_date,
        adjusted=True,
        prefer_bulk=True,
        max_concurrent=10
    )
    
    stock_data_list = list(stock_data_dict.values())
    
    # Test each filter individually
    individual_filters = [
        ('Gap >= 1%', GapFilter(min_gap_percent=1.0)),
        ('Price $5-$500', PriceRangeFilter(min_price=5.0, max_price=500.0)),
        ('Volume >= 1.2x', RelativeVolumeFilter(min_relative_volume=1.2)),
    ]
    
    qualifying_symbols_union = set()
    
    for filter_name, filter_obj in individual_filters:
        result = screener.screen(
            stock_data_list=stock_data_list,
            filters=[filter_obj],
            date_range=(target_date, target_date)
        )
        
        print(f"\n{filter_name}: {len(result.qualifying_symbols)} symbols pass")
        print(f"  Symbols: {', '.join(result.qualifying_symbols)}")
        
        qualifying_symbols_union.update(result.qualifying_symbols)
    
    print(f"\n\nOR Logic Results:")
    print(f"Total symbols that pass at least one filter: {len(qualifying_symbols_union)}")
    print(f"Pass rate: {(len(qualifying_symbols_union) / len(test_symbols) * 100):.1f}%")
    print(f"Symbols: {', '.join(sorted(qualifying_symbols_union))}")
    
    # Recommendations
    print("\n\n" + "="*80)
    print("RECOMMENDATIONS BASED ON TEST RESULTS")
    print("="*80)
    
    print("\n1. Use Period Extension:")
    print("   - The screen_with_period_extension method automatically fetches required historical data")
    print("   - This solves the 'insufficient data' error for filters that need lookback periods")
    
    print("\n2. Adjust Filter Thresholds:")
    print("   - Gap: Use 1-2% instead of 4% for more results")
    print("   - Volume: Use 1.2-1.5x instead of 2x")
    print("   - Price: Consider wider ranges based on your strategy")
    
    print("\n3. Consider OR Logic:")
    print("   - Current system uses AND logic (all filters must pass)")
    print("   - OR logic (any filter passes) gives more results")
    print("   - Could implement a scoring system instead of binary pass/fail")
    
    print("\n4. Use Historical Dates:")
    print("   - Future dates like August 1, 2025 have no real data")
    print("   - Always use historical or current dates for real results")


async def main():
    """Run the test with period extension."""
    await test_with_period_extension()


if __name__ == "__main__":
    asyncio.run(main())