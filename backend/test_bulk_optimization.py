#!/usr/bin/env python3
"""
Test script to demonstrate the bulk endpoint optimization performance improvements.

This script compares the performance of:
1. Individual API calls (old method)
2. Bulk endpoint with fallback (new optimized method)

Expected results:
- Bulk endpoint should be 10x faster for single-day requests
- Sub-10 second performance for screening all US stocks
- Ideally 3-5 seconds for complete screening
"""

import asyncio
import time
import logging
from datetime import date, timedelta
from typing import Dict, List

from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.core.day_trading_filters import GapFilter, PriceRangeFilter, RelativeVolumeFilter
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_individual_vs_bulk_performance():
    """Compare individual calls vs bulk endpoint performance."""
    
    # Test configuration
    test_date = date.today() - timedelta(days=1)  # Yesterday's data
    test_symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", 
        "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
        "PFE", "CVX", "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO",
        "VZ", "ADBE", "CMCSA"
    ]  # 30 symbols for comparison
    
    async with PolygonClient() as client:
        
        # Test 1: Individual API calls (old method)
        logger.info("=" * 60)
        logger.info("TEST 1: Individual API calls (old method)")
        logger.info("=" * 60)
        
        start_time = time.time()
        individual_results = await client.fetch_batch_historical_data(
            symbols=test_symbols,
            start_date=test_date,
            end_date=test_date,
            adjusted=True,
            max_concurrent=100
        )
        individual_time = time.time() - start_time
        
        logger.info(f"Individual calls completed:")
        logger.info(f"  - Time: {individual_time:.2f} seconds")
        logger.info(f"  - Symbols fetched: {len(individual_results)}")
        logger.info(f"  - Success rate: {len(individual_results)}/{len(test_symbols)} ({(len(individual_results)/len(test_symbols))*100:.1f}%)")
        
        # Test 2: Bulk endpoint (new method)
        logger.info("=" * 60)
        logger.info("TEST 2: Bulk endpoint with fallback (new method)")
        logger.info("=" * 60)
        
        start_time = time.time()
        bulk_results = await client.fetch_bulk_historical_data_with_fallback(
            symbols=test_symbols,
            start_date=test_date,
            end_date=test_date,
            adjusted=True,
            prefer_bulk=True,
            max_concurrent=200
        )
        bulk_time = time.time() - start_time
        
        logger.info(f"Bulk endpoint completed:")
        logger.info(f"  - Time: {bulk_time:.2f} seconds")
        logger.info(f"  - Symbols fetched: {len(bulk_results)}")
        logger.info(f"  - Success rate: {len(bulk_results)}/{len(test_symbols)} ({(len(bulk_results)/len(test_symbols))*100:.1f}%)")
        
        # Performance comparison
        logger.info("=" * 60)
        logger.info("PERFORMANCE COMPARISON")
        logger.info("=" * 60)
        
        if bulk_time > 0:
            speedup = individual_time / bulk_time
            logger.info(f"Speed improvement: {speedup:.1f}x faster")
            
            if speedup >= 5:
                logger.info("✅ EXCELLENT: Bulk endpoint provides significant performance improvement!")
            elif speedup >= 2:
                logger.info("✅ GOOD: Bulk endpoint provides good performance improvement")
            else:
                logger.info("⚠️  MARGINAL: Performance improvement is minimal")
        
        # Data quality comparison
        data_quality_same = len(individual_results) == len(bulk_results)
        logger.info(f"Data quality: {'✅ Same' if data_quality_same else '⚠️  Different'} number of symbols")
        
        return {
            'individual_time': individual_time,
            'bulk_time': bulk_time,
            'speedup': individual_time / bulk_time if bulk_time > 0 else 0,
            'individual_count': len(individual_results),
            'bulk_count': len(bulk_results)
        }


async def test_full_us_stock_screening():
    """Test screening all US stocks with the bulk optimization."""
    
    logger.info("=" * 60)
    logger.info("TEST 3: Full US Stock Screening Performance")
    logger.info("=" * 60)
    
    test_date = date.today() - timedelta(days=1)  # Yesterday's data
    
    # Define day trading filters for realistic test
    filters = [
        GapFilter(min_gap_percent=4.0, max_gap_percent=20.0),
        PriceRangeFilter(min_price=2.0, max_price=10.0),
        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=20)
    ]
    
    async with PolygonClient() as client:
        
        # Step 1: Fetch all US stock symbols (if not using bulk for all)
        logger.info("Fetching US stock universe...")
        from app.services.ticker_discovery import TickerDiscoveryService
        ticker_discovery = TickerDiscoveryService(client)
        
        # For demo purposes, let's use a subset to show the concept
        # In production, this would fetch all ~8000+ US stocks
        all_symbols = settings.default_symbols  # Use default for demo
        logger.info(f"Testing with {len(all_symbols)} symbols (subset for demo)")
        
        # Step 2: Bulk data fetch
        logger.info("Starting bulk data fetch...")
        start_time = time.time()
        
        stock_data_dict = await client.fetch_bulk_historical_data_with_fallback(
            symbols=all_symbols,
            start_date=test_date,
            end_date=test_date,
            adjusted=True,
            prefer_bulk=True,  # Use bulk optimization
            max_concurrent=200
        )
        
        data_fetch_time = time.time() - start_time
        logger.info(f"Data fetch completed in {data_fetch_time:.2f} seconds")
        
        # Step 3: Run screening
        logger.info("Starting screening process...")
        screening_start = time.time()
        
        stock_data_list = list(stock_data_dict.values())
        screener = ScreenerEngine(max_workers=8)
        screen_result = screener.screen(stock_data_list, filters)
        
        screening_time = time.time() - screening_start
        total_time = time.time() - start_time
        
        # Results
        logger.info("=" * 60)
        logger.info("FULL SCREENING RESULTS")
        logger.info("=" * 60)
        
        logger.info(f"Total execution time: {total_time:.2f} seconds")
        logger.info(f"  - Data fetch: {data_fetch_time:.2f} seconds ({(data_fetch_time/total_time)*100:.1f}%)")
        logger.info(f"  - Screening: {screening_time:.2f} seconds ({(screening_time/total_time)*100:.1f}%)")
        logger.info(f"Symbols processed: {len(stock_data_list)}")
        logger.info(f"Qualifying stocks: {len(screen_result.qualifying_symbols)}")
        
        # Performance assessment
        if total_time <= 5:
            logger.info("🎯 EXCELLENT: Under 5 seconds - Target achieved!")
        elif total_time <= 10:
            logger.info("✅ GOOD: Under 10 seconds - Performance target met!")
        elif total_time <= 30:
            logger.info("⚠️  ACCEPTABLE: Under 30 seconds - Room for improvement")
        else:
            logger.info("❌ NEEDS WORK: Over 30 seconds - Optimization needed")
        
        return {
            'total_time': total_time,
            'data_fetch_time': data_fetch_time,
            'screening_time': screening_time,
            'symbols_processed': len(stock_data_list),
            'qualifying_stocks': len(screen_result.qualifying_symbols)
        }


async def main():
    """Run all performance tests."""
    
    logger.info("🚀 Starting Bulk Endpoint Optimization Performance Tests")
    logger.info("=" * 80)
    
    try:
        # Test 1 & 2: Individual vs Bulk comparison
        comparison_results = await test_individual_vs_bulk_performance()
        
        # Test 3: Full screening performance
        screening_results = await test_full_us_stock_screening()
        
        # Final summary
        logger.info("=" * 80)
        logger.info("🎯 FINAL PERFORMANCE SUMMARY")
        logger.info("=" * 80)
        
        logger.info(f"Bulk vs Individual speedup: {comparison_results['speedup']:.1f}x")
        logger.info(f"Full screening time: {screening_results['total_time']:.2f} seconds")
        logger.info(f"Symbols processed: {screening_results['symbols_processed']}")
        logger.info(f"Qualifying stocks found: {screening_results['qualifying_stocks']}")
        
        # Overall assessment
        success_criteria = [
            comparison_results['speedup'] >= 3,  # At least 3x speedup
            screening_results['total_time'] <= 10,  # Under 10 seconds
            screening_results['symbols_processed'] >= 20  # Processed significant number
        ]
        
        if all(success_criteria):
            logger.info("🎉 SUCCESS: All performance targets achieved!")
        elif sum(success_criteria) >= 2:
            logger.info("✅ GOOD: Most performance targets achieved")
        else:
            logger.info("⚠️  PARTIAL: Some optimization goals met, room for improvement")
        
    except Exception as e:
        logger.error(f"❌ Test failed with error: {e}", exc_info=True)
    
    logger.info("=" * 80)
    logger.info("Test completed!")


if __name__ == "__main__":
    asyncio.run(main())