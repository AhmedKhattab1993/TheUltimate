#!/usr/bin/env python3
"""
Working demonstration of the stock screener with properly configured filters.
This shows how to get actual results by using reasonable filter values.
"""

import asyncio
import sys
from datetime import date, timedelta

# Add app to path
sys.path.append('/home/ahmed/TheUltimate/backend')

from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.core.day_trading_filters import (
    GapFilter,
    PriceRangeFilter,
    RelativeVolumeFilter
)


async def demonstrate_working_screener():
    """Demonstrate the screener with filters that actually return results."""
    
    # Initialize services
    polygon_client = PolygonClient()
    screener = ScreenerEngine(polygon_client=polygon_client)
    
    # Use a broader set of symbols for better results
    test_symbols = [
        # Large caps
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA',
        # Mid caps  
        'AMD', 'NFLX', 'PYPL', 'SQ', 'ROKU', 'SNAP', 'UBER',
        # Small caps / volatile
        'AMC', 'GME', 'BBBY', 'SPCE', 'PLTR', 'SOFI', 'LCID',
        # ETFs for comparison
        'SPY', 'QQQ', 'IWM'
    ]
    
    # Use a recent historical date
    target_date = date(2024, 11, 15)
    
    print("=" * 80)
    print("STOCK SCREENER WORKING DEMONSTRATION")
    print("=" * 80)
    print(f"Target Date: {target_date}")
    print(f"Testing {len(test_symbols)} symbols")
    print()
    
    # Configuration 1: Single filter tests to show what works
    single_filter_tests = [
        ("Minimal Gap (0.5%)", [GapFilter(min_gap_percent=0.5)]),
        ("Small Gap (1%)", [GapFilter(min_gap_percent=1.0)]),
        ("Price Range Only", [PriceRangeFilter(min_price=5.0, max_price=500.0)]),
        ("Low Volume Threshold", [RelativeVolumeFilter(min_relative_volume=1.1, lookback_days=10)]),
    ]
    
    print("\n1. TESTING INDIVIDUAL FILTERS")
    print("-" * 40)
    
    for test_name, filters in single_filter_tests:
        result, metadata = await screener.screen_with_period_extension(
            symbols=test_symbols,
            filters=filters,
            start_date=target_date,
            end_date=target_date,
            polygon_client=polygon_client
        )
        
        print(f"\n{test_name}:")
        print(f"  Passing: {len(result.qualifying_symbols)}/{len(test_symbols)} ({len(result.qualifying_symbols)/len(test_symbols)*100:.1f}%)")
        if result.qualifying_symbols:
            print(f"  Symbols: {', '.join(sorted(result.qualifying_symbols)[:10])}")
            if len(result.qualifying_symbols) > 10:
                print(f"           ... and {len(result.qualifying_symbols) - 10} more")
    
    # Configuration 2: Reasonable combined filters
    print("\n\n2. TESTING COMBINED FILTERS (AND LOGIC)")
    print("-" * 40)
    
    combined_tests = [
        {
            'name': 'Day Trading Setup (Lenient)',
            'filters': [
                GapFilter(min_gap_percent=1.0),
                PriceRangeFilter(min_price=5.0, max_price=200.0),
            ]
        },
        {
            'name': 'Price + Volume Only',
            'filters': [
                PriceRangeFilter(min_price=10.0, max_price=500.0),
                RelativeVolumeFilter(min_relative_volume=1.2, lookback_days=10),
            ]
        },
        {
            'name': 'Gap + Price Only', 
            'filters': [
                GapFilter(min_gap_percent=0.5, max_gap_percent=5.0),
                PriceRangeFilter(min_price=5.0, max_price=500.0),
            ]
        }
    ]
    
    for config in combined_tests:
        result, metadata = await screener.screen_with_period_extension(
            symbols=test_symbols,
            filters=config['filters'],
            start_date=target_date,
            end_date=target_date,
            polygon_client=polygon_client
        )
        
        print(f"\n{config['name']}:")
        print(f"  Filters: {len(config['filters'])}")
        print(f"  Passing: {len(result.qualifying_symbols)}/{len(test_symbols)} ({len(result.qualifying_symbols)/len(test_symbols)*100:.1f}%)")
        
        if result.qualifying_symbols:
            print(f"  Symbols: {', '.join(sorted(result.qualifying_symbols))}")
            
            # Show details for top performers
            print("\n  Top Performers:")
            for symbol in result.qualifying_symbols[:3]:
                if symbol in result.results:
                    metrics = result.results[symbol].metrics
                    print(f"    {symbol}:")
                    if 'gap_percent_mean' in metrics:
                        print(f"      Gap: {metrics['gap_percent_mean']:.2f}%")
                    if 'avg_price' in metrics:
                        print(f"      Price: ${metrics['avg_price']:.2f}")
                    if 'relative_volume_mean' in metrics:
                        print(f"      Rel Volume: {metrics['relative_volume_mean']:.2f}x")
    
    # Configuration 3: Show the original problem
    print("\n\n3. ORIGINAL CONFIGURATION (PROBLEMATIC)")
    print("-" * 40)
    
    original_filters = [
        GapFilter(min_gap_percent=4.0),
        PriceRangeFilter(min_price=10.0, max_price=500.0),
        RelativeVolumeFilter(min_relative_volume=2.0),
    ]
    
    result, metadata = await screener.screen_with_period_extension(
        symbols=test_symbols,
        filters=original_filters,
        start_date=target_date,
        end_date=target_date,
        polygon_client=polygon_client
    )
    
    print("\nOriginal Strict Filters:")
    print("  - Gap >= 4%")
    print("  - Price $10-$500")
    print("  - Volume >= 2x average")
    print(f"\nResult: {len(result.qualifying_symbols)}/{len(test_symbols)} stocks pass")
    print("This is why no results were showing!")
    
    # Recommendations
    print("\n\n" + "=" * 80)
    print("RECOMMENDATIONS FOR PRODUCTION USE")
    print("=" * 80)
    
    print("\n1. Start with lenient filters and tighten as needed:")
    print("   - Gap: 0.5-1% for general screening")
    print("   - Volume: 1.1-1.3x for increased activity")
    print("   - Price: Adjust based on account size and risk")
    
    print("\n2. Use date ranges instead of single dates:")
    print("   - Gives more opportunities to find setups")
    print("   - Example: Last 5 trading days instead of just today")
    
    print("\n3. Expand symbol universe:")
    print("   - Include all S&P 500 or Russell 2000 stocks")
    print("   - More stocks = more opportunities")
    
    print("\n4. Consider market conditions:")
    print("   - Volatile markets: More gaps and volume spikes")
    print("   - Quiet markets: Lower thresholds needed")
    
    print("\n5. Monitor and adjust:")
    print("   - Track how many results each filter configuration gives")
    print("   - Adjust thresholds based on market conditions")


async def main():
    """Run the working demonstration."""
    await demonstrate_working_screener()


if __name__ == "__main__":
    asyncio.run(main())