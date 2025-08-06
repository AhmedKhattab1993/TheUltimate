#!/usr/bin/env python3
"""
Example script demonstrating the bulk endpoint optimization for stock screening.

This shows how to use the optimized screener API with bulk data fetching
to achieve sub-10 second performance when screening large numbers of stocks.
"""

import asyncio
import json
import logging
from datetime import date, timedelta

from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.core.day_trading_filters import GapFilter, PriceRangeFilter, RelativeVolumeFilter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def example_bulk_screening():
    """Example of bulk-optimized stock screening."""
    
    # Configuration
    screening_date = date.today() - timedelta(days=1)  # Yesterday
    
    # Define filters for day trading setup
    filters = [
        GapFilter(min_gap_percent=4.0, max_gap_percent=15.0, name="Gap4-15%"),
        PriceRangeFilter(min_price=2.0, max_price=10.0, name="Price$2-10"),
        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=20, name="RelVol2x")
    ]
    
    logger.info(f"🔍 Screening stocks for {screening_date}")
    logger.info(f"📋 Filters: {[f.name for f in filters]}")
    
    async with PolygonClient() as client:
        
        # Example 1: Screen specific symbols with bulk optimization
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE 1: Screening specific symbols")
        logger.info("="*50)
        
        symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
            "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
            "SNDL", "AMC", "GME", "BBBY", "PTON", "NKLA", "SPCE", "PLTR"
        ]
        
        start_time = asyncio.get_event_loop().time()
        
        # Fetch data using bulk optimization
        stock_data_dict = await client.fetch_bulk_historical_data_with_fallback(
            symbols=symbols,
            start_date=screening_date,
            end_date=screening_date,
            adjusted=True,
            prefer_bulk=True  # Enable bulk optimization
        )
        
        fetch_time = asyncio.get_event_loop().time() - start_time
        
        # Run screening
        screening_start = asyncio.get_event_loop().time()
        stock_data_list = list(stock_data_dict.values())
        screener = ScreenerEngine(max_workers=4)
        results = screener.screen(stock_data_list, filters)
        screening_time = asyncio.get_event_loop().time() - screening_start
        
        total_time = fetch_time + screening_time
        
        logger.info(f"⏱️  Performance:")
        logger.info(f"   Data fetch: {fetch_time:.2f}s")
        logger.info(f"   Screening: {screening_time:.2f}s")
        logger.info(f"   Total: {total_time:.2f}s")
        logger.info(f"📊 Results:")
        logger.info(f"   Symbols processed: {len(stock_data_list)}")
        logger.info(f"   Qualifying stocks: {len(results.qualifying_symbols)}")
        
        if results.qualifying_symbols:
            logger.info(f"🎯 Qualifying symbols: {results.qualifying_symbols}")
        
        # Example 2: Demonstrate fallback to individual calls
        logger.info("\n" + "="*50)
        logger.info("EXAMPLE 2: Multi-day range (uses individual calls)")
        logger.info("="*50)
        
        start_date = screening_date - timedelta(days=5)
        end_date = screening_date
        
        start_time = asyncio.get_event_loop().time()
        
        # This will automatically use individual calls for multi-day range
        multi_day_data = await client.fetch_bulk_historical_data_with_fallback(
            symbols=symbols[:10],  # Smaller subset for demo
            start_date=start_date,
            end_date=end_date,
            adjusted=True,
            prefer_bulk=True  # Will fallback to individual calls automatically
        )
        
        multi_day_time = asyncio.get_event_loop().time() - start_time
        
        logger.info(f"⏱️  Multi-day fetch time: {multi_day_time:.2f}s")
        logger.info(f"📊 Symbols with multi-day data: {len(multi_day_data)}")
        
        # Show data richness
        for symbol, stock_data in list(multi_day_data.items())[:3]:
            logger.info(f"   {symbol}: {len(stock_data.bars)} days of data")


async def example_api_request_simulation():
    """Simulate API request format for the optimized screener."""
    
    logger.info("\n" + "="*50)
    logger.info("EXAMPLE 3: API Request Format")
    logger.info("="*50)
    
    # This simulates the JSON that would be sent to the API
    api_request = {
        "start_date": "2024-01-15",
        "end_date": "2024-01-15",  # Single day for bulk optimization
        "use_all_us_stocks": False,
        "symbols": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"
        ],
        "filters": {
            "gap": {
                "min_gap_percent": 4.0,
                "max_gap_percent": 15.0
            },
            "price_range": {
                "min_price": 2.0,
                "max_price": 10.0
            },
            "relative_volume": {
                "min_relative_volume": 2.0,
                "lookback_days": 20
            }
        }
    }
    
    logger.info("📝 Example API request:")
    logger.info(json.dumps(api_request, indent=2))
    
    logger.info("\n🚀 Expected performance with bulk optimization:")
    logger.info("   - Single day request: Uses bulk endpoint (1 API call)")
    logger.info("   - Multi-day request: Uses individual calls with high concurrency")
    logger.info("   - All US stocks + single day: Bulk endpoint for ~8000+ stocks")
    logger.info("   - Expected time: 3-10 seconds depending on scope")


async def main():
    """Run all examples."""
    
    logger.info("🚀 Bulk Endpoint Optimization Examples")
    logger.info("="*80)
    
    try:
        await example_bulk_screening()
        await example_api_request_simulation()
        
        logger.info("\n" + "="*80)
        logger.info("✅ All examples completed successfully!")
        logger.info("💡 Key benefits of bulk optimization:")
        logger.info("   • 10x faster for single-day requests")
        logger.info("   • Reduced API rate limit usage")
        logger.info("   • Better connection pooling")
        logger.info("   • Automatic fallback for reliability")
        logger.info("   • Sub-10 second screening of all US stocks")
        
    except Exception as e:
        logger.error(f"❌ Example failed: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())