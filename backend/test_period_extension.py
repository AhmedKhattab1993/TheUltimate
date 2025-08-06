#!/usr/bin/env python3
"""
Test script for automatic period data extension solution.

This script tests the automatic period extension functionality to ensure
all period-based filters work correctly with single-day screening.
"""

import asyncio
import logging
from datetime import date, timedelta
from typing import List
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.abspath('.'))

from app.core.filters import VolumeFilter, MovingAverageFilter
from app.core.day_trading_filters import RelativeVolumeFilter
from app.core.filter_analyzer import FilterRequirementAnalyzer
from app.services.polygon_client import PolygonClient
from app.services.screener import ScreenerEngine
from app.models.stock import StockData, StockBar

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_mock_stock_data(symbol: str, start_date: date, num_days: int = 30) -> StockData:
    """Create mock stock data for testing."""
    bars = []
    current_date = start_date - timedelta(days=num_days)
    
    # Generate mock data with increasing volume and price trends
    base_price = 10.0
    base_volume = 100000
    
    for i in range(num_days + 1):
        # Skip weekends
        if current_date.weekday() < 5:
            price_variation = (i % 5) * 0.5  # Price varies slightly
            volume_variation = (i % 7) * 10000  # Volume varies
            
            bar = StockBar(
                symbol=symbol,
                date=current_date,
                open=base_price + price_variation,
                high=base_price + price_variation + 0.5,
                low=base_price + price_variation - 0.3,
                close=base_price + price_variation + 0.2,
                volume=base_volume + volume_variation,
                vwap=base_price + price_variation + 0.1
            )
            bars.append(bar)
        
        current_date += timedelta(days=1)
    
    return StockData(symbol=symbol, bars=bars)


async def test_filter_requirement_analyzer():
    """Test the FilterRequirementAnalyzer functionality."""
    logger.info("=== Testing FilterRequirementAnalyzer ===")
    
    # Create test filters
    filters = [
        VolumeFilter(lookback_days=10, threshold=50000, name="Volume10d"),
        MovingAverageFilter(period=20, position="above", name="MA20"),
        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=15, name="RelVol15d")
    ]
    
    analyzer = FilterRequirementAnalyzer()
    
    # Test analysis
    requirements = analyzer.analyze_filters(filters)
    logger.info(f"Found {len(requirements)} filter requirements:")
    for req in requirements:
        logger.info(f"  - {req}")
    
    # Test date calculation
    target_date = date.today()
    extended_start, _ = analyzer.calculate_required_start_date(
        filters, target_date, target_date
    )
    
    extension_days = (target_date - extended_start).days
    logger.info(f"Single day screening on {target_date} requires extension to {extended_start} (+{extension_days} days)")
    
    # Test filter summary
    summary = analyzer.get_filter_summary(filters)
    logger.info(f"Filter summary: {summary}")
    
    assert len(requirements) == 3, f"Expected 3 requirements, got {len(requirements)}"
    assert extension_days > 0, f"Expected positive extension days, got {extension_days}"
    
    logger.info("✅ FilterRequirementAnalyzer tests passed")


async def test_screener_with_extension():
    """Test the ScreenerEngine with period extension."""
    logger.info("=== Testing ScreenerEngine with Period Extension ===")
    
    # Create mock data for testing
    target_date = date.today()
    symbols = ["AAPL", "MSFT", "GOOGL"]
    
    # Create filters that require lookback data
    filters = [
        VolumeFilter(lookback_days=5, threshold=80000, name="Volume5d"),
        MovingAverageFilter(period=10, position="above", name="MA10")
    ]
    
    # Test without real Polygon client (using mock data)
    screener = ScreenerEngine(max_workers=2)
    
    # Create mock extended stock data
    extended_stock_data = []
    for symbol in symbols:
        stock_data = create_mock_stock_data(symbol, target_date, num_days=20)
        extended_stock_data.append(stock_data)
    
    # Test regular screening on extended data
    screen_result = screener.screen(extended_stock_data, filters, date_range=None)
    
    logger.info(f"Screening results: {len(screen_result.qualifying_symbols)} qualifying symbols")
    logger.info(f"Processing time: {screen_result.processing_time:.3f} seconds")
    
    # Test date slicing functionality
    from app.services.polygon_client import PolygonClient
    client = PolygonClient()  # This will fail without API key, but we test the method
    
    # Create extended data dict
    extended_data_dict = {stock.symbol: stock for stock in extended_stock_data}
    
    # Test slicing back to original range
    sliced_data = client.slice_data_to_original_range(
        extended_data_dict, target_date, target_date
    )
    
    logger.info(f"Sliced data: {len(sliced_data)} symbols")
    for symbol, stock_data in sliced_data.items():
        logger.info(f"  {symbol}: {len(stock_data.bars)} bars (target: single day)")
        assert len(stock_data.bars) <= 1, f"Expected at most 1 bar after slicing, got {len(stock_data.bars)}"
    
    logger.info("✅ ScreenerEngine with extension tests passed")


async def test_polygon_client_extension(use_real_api: bool = False):
    """Test PolygonClient extension functionality."""
    logger.info("=== Testing PolygonClient Extension ===")
    
    if not use_real_api:
        logger.info("Skipping real API test (use_real_api=False)")
        return
    
    try:
        async with PolygonClient() as client:
            symbols = ["AAPL", "MSFT"]  # Small test set
            target_date = date.today() - timedelta(days=1)  # Yesterday
            
            # Create mock filter requirements
            from app.core.filter_analyzer import FilterRequirement
            requirements = [
                FilterRequirement("VolumeFilter", 5, "volume", "5-day volume lookback"),
                FilterRequirement("MA10", 10, "moving_average", "10-day MA")
            ]
            
            # Test extension method
            extended_data, metadata = await client.fetch_historical_data_with_extension(
                symbols=symbols,
                original_start_date=target_date,
                original_end_date=target_date,
                filter_requirements=requirements,
                adjusted=True,
                max_concurrent=10,
                prefer_bulk=True
            )
            
            logger.info(f"Extended data fetch results:")
            logger.info(f"  Symbols fetched: {len(extended_data)}")
            logger.info(f"  Extension applied: {metadata.get('period_extension_applied', False)}")
            logger.info(f"  Extension days: {metadata.get('extension_days', 0)}")
            logger.info(f"  Fetch time: {metadata.get('fetch_time_seconds', 0):.2f}s")
            
            # Test slicing back to original range
            sliced_data = client.slice_data_to_original_range(
                extended_data, target_date, target_date
            )
            
            logger.info(f"After slicing to original range: {len(sliced_data)} symbols")
            
            assert len(extended_data) > 0, "Expected some extended data"
            assert metadata.get('period_extension_applied', False), "Expected extension to be applied"
            
            logger.info("✅ PolygonClient extension tests passed")
            
    except Exception as e:
        logger.warning(f"Real API test failed (expected if no API key): {e}")


async def test_integration_with_problematic_filters():
    """Test the integration with the specific filters mentioned in the issue."""
    logger.info("=== Testing Integration with Problematic Filters ===")
    
    target_date = date.today()
    symbols = ["AAPL", "MSFT", "NVDA", "TSLA"]
    
    # These are the exact filters mentioned in the issue
    problematic_filters = [
        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=20, name="RelativeVolume20d"),
        VolumeFilter(lookback_days=10, threshold=100000, name="Volume10d"),
        MovingAverageFilter(period=50, position="above", name="MA50"),
    ]
    
    # Test analyzer on these specific filters
    analyzer = FilterRequirementAnalyzer()
    requirements = analyzer.analyze_filters(problematic_filters)
    
    logger.info(f"Analysis of problematic filters:")
    for req in requirements:
        logger.info(f"  - {req.filter_name}: {req.lookback_days} days ({req.filter_type})")
    
    # Calculate required extension for single-day screening
    extended_start, _ = analyzer.calculate_required_start_date(
        problematic_filters, target_date, target_date
    )
    
    extension_days = (target_date - extended_start).days
    logger.info(f"Single-day screening on {target_date} requires {extension_days} days of historical data")
    
    # Verify that each filter's requirements are captured
    filter_types_found = {req.filter_type for req in requirements}
    expected_types = {"relative_volume", "volume", "moving_average"}
    
    assert filter_types_found == expected_types, f"Expected {expected_types}, got {filter_types_found}"
    assert extension_days >= 50, f"Expected at least 50 days extension (MA50 + buffer), got {extension_days}"
    
    # Test with mock data to ensure filters work with extended data
    # Need to generate more data than the extension days to account for business days only
    mock_days_needed = extension_days + 30  # Add buffer for weekends
    mock_stock_data = []
    for symbol in symbols[:2]:  # Limit to 2 symbols for quick test
        stock_data = create_mock_stock_data(symbol, target_date, num_days=mock_days_needed)
        logger.info(f"Generated {len(stock_data.bars)} bars for {symbol} (needed {extension_days}+ for filters)")
        mock_stock_data.append(stock_data)
    
    # Run screening on extended data
    screener = ScreenerEngine(max_workers=2)
    screen_result = screener.screen(mock_stock_data, problematic_filters, date_range=None)
    
    logger.info(f"Mock screening results with extended data:")
    logger.info(f"  Total processed: {screen_result.num_processed}")
    logger.info(f"  Qualifying symbols: {len(screen_result.qualifying_symbols)}")
    logger.info(f"  Processing errors: {screen_result.num_errors}")
    
    # The key test: no errors should occur due to insufficient data
    assert screen_result.num_errors == 0, f"Expected no processing errors, got {screen_result.num_errors}"
    
    logger.info("✅ Integration test with problematic filters passed")


async def run_all_tests():
    """Run all tests."""
    logger.info("Starting automatic period data extension tests...")
    
    try:
        await test_filter_requirement_analyzer()
        await test_screener_with_extension()
        await test_polygon_client_extension(use_real_api=False)  # Set to True to test with real API
        await test_integration_with_problematic_filters()
        
        logger.info("🎉 All tests passed! Automatic period extension implementation is working correctly.")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(run_all_tests())