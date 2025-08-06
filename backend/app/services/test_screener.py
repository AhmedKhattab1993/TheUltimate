"""
Test script for the high-performance screener engine.

This script demonstrates how to use the screener engine with various filters
and verifies the vectorized operations work correctly.
"""

import numpy as np
from datetime import date, timedelta
from typing import List

from ..models.stock import StockData, StockBar
from ..core.filters import VolumeFilter, PriceChangeFilter, MovingAverageFilter, CompositeFilter
from .screener import ScreenerEngine


def generate_test_data(symbol: str, num_days: int = 100) -> StockData:
    """Generate synthetic stock data for testing."""
    bars = []
    base_price = 100.0
    base_volume = 1000000
    start_date = date.today() - timedelta(days=num_days)
    
    for i in range(num_days):
        # Add some randomness but keep it realistic
        price_change = np.random.normal(0, 0.02)  # 2% daily volatility
        volume_change = np.random.normal(0, 0.1)   # 10% volume volatility
        
        current_price = base_price * (1 + price_change)
        current_volume = int(base_volume * (1 + volume_change))
        
        # Ensure positive values
        current_price = max(current_price, 1.0)
        current_volume = max(current_volume, 100)
        
        bar = StockBar(
            symbol=symbol,
            date=start_date + timedelta(days=i),
            open=current_price * 0.99,
            high=current_price * 1.01,
            low=current_price * 0.98,
            close=current_price,
            volume=current_volume,
            vwap=current_price
        )
        bars.append(bar)
        
        # Update base values for next iteration
        base_price = current_price
        base_volume = current_volume * 0.9 + base_volume * 0.1  # Smooth volume changes
    
    return StockData(symbol=symbol, bars=bars)


def test_individual_filters():
    """Test individual filter functionality."""
    print("Testing Individual Filters")
    print("=" * 50)
    
    # Generate test data
    stock = generate_test_data("TEST", 50)
    data = stock.to_numpy()
    
    # Test Volume Filter
    print("\n1. Volume Filter Test:")
    volume_filter = VolumeFilter(lookback_days=5, threshold=900000)
    result = volume_filter.apply(data, "TEST")
    print(f"   - Qualifying days: {result.num_qualifying_days}")
    print(f"   - Metrics: {result.metrics}")
    
    # Test Price Change Filter
    print("\n2. Price Change Filter Test:")
    price_filter = PriceChangeFilter(min_change=-2.0, max_change=2.0)
    result = price_filter.apply(data, "TEST")
    print(f"   - Qualifying days: {result.num_qualifying_days}")
    print(f"   - Metrics: {result.metrics}")
    
    # Test Moving Average Filter
    print("\n3. Moving Average Filter Test:")
    ma_filter = MovingAverageFilter(period=10, position="above")
    result = ma_filter.apply(data, "TEST")
    print(f"   - Qualifying days: {result.num_qualifying_days}")
    print(f"   - Metrics: {result.metrics}")


def test_composite_filter():
    """Test composite filter functionality."""
    print("\n\nTesting Composite Filter")
    print("=" * 50)
    
    # Generate test data
    stock = generate_test_data("TEST", 50)
    data = stock.to_numpy()
    
    # Create individual filters
    filters = [
        VolumeFilter(lookback_days=5, threshold=900000),
        PriceChangeFilter(min_change=-2.0, max_change=2.0),
        MovingAverageFilter(period=10, position="above")
    ]
    
    # Create and apply composite filter
    composite = CompositeFilter(filters)
    result = composite.apply(data, "TEST")
    
    print(f"Composite Filter Results:")
    print(f"   - Qualifying days: {result.num_qualifying_days}")
    print(f"   - Date range: {result.qualifying_dates[0] if result.num_qualifying_days > 0 else 'None'} to {result.qualifying_dates[-1] if result.num_qualifying_days > 0 else 'None'}")
    print(f"   - Combined metrics: {result.metrics}")


def test_screener_engine():
    """Test the screener engine with multiple stocks."""
    print("\n\nTesting Screener Engine")
    print("=" * 50)
    
    # Generate test data for multiple stocks
    symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA"]
    stock_data_list = []
    
    for i, symbol in enumerate(symbols):
        # Add variety to the data
        stock = generate_test_data(symbol, 100)
        # Modify some stocks to have different characteristics
        if i % 2 == 0:
            # Increase volume for even-indexed stocks
            for bar in stock.bars:
                bar.volume = int(bar.volume * 1.5)
        stock_data_list.append(stock)
    
    # Create filters
    filters = [
        VolumeFilter(lookback_days=20, threshold=1200000),
        PriceChangeFilter(min_change=-3.0, max_change=3.0),
        MovingAverageFilter(period=20, position="above")
    ]
    
    # Create and run screener
    screener = ScreenerEngine(max_workers=2)
    
    # Basic screening
    print("\nBasic Screening:")
    result = screener.screen(stock_data_list, filters)
    print(f"   - Summary: {result.get_summary()}")
    print(f"   - Qualifying symbols: {result.qualifying_symbols}")
    
    # Screening with metrics
    print("\nScreening with Metrics:")
    metrics_result = screener.screen_with_metrics(
        stock_data_list,
        filters,
        metric_aggregations={
            'avg_volume_*_mean': 'mean',
            'price_change_mean': 'mean',
            'distance_from_sma_*_mean': 'mean'
        }
    )
    
    print(f"   - Summary: {metrics_result['summary']}")
    print(f"   - Aggregated metrics: {metrics_result['aggregated_metrics']}")
    
    # Show details for qualifying symbols
    print("\n   - Qualifying symbol details:")
    for symbol_info in metrics_result['qualifying_symbols'][:3]:  # Show first 3
        print(f"     * {symbol_info['symbol']}: {symbol_info['qualifying_days']} days")


def test_performance():
    """Test performance with large dataset."""
    print("\n\nTesting Performance")
    print("=" * 50)
    
    import time
    
    # Generate large dataset
    num_stocks = 100
    num_days = 252  # One year of trading days
    
    print(f"Generating {num_stocks} stocks with {num_days} days each...")
    start_time = time.time()
    
    stock_data_list = []
    for i in range(num_stocks):
        stock = generate_test_data(f"STOCK{i:03d}", num_days)
        stock_data_list.append(stock)
    
    generation_time = time.time() - start_time
    print(f"   - Data generation time: {generation_time:.2f}s")
    
    # Create filters
    filters = [
        VolumeFilter(lookback_days=20, threshold=1000000),
        PriceChangeFilter(min_change=-2.5, max_change=2.5),
        MovingAverageFilter(period=50, position="above")
    ]
    
    # Run screening
    screener = ScreenerEngine(max_workers=4)
    
    print(f"\nScreening {num_stocks} stocks...")
    start_time = time.time()
    result = screener.screen(stock_data_list, filters)
    screening_time = time.time() - start_time
    
    summary = result.get_summary()
    print(f"   - Screening time: {screening_time:.2f}s")
    print(f"   - Processing rate: {num_stocks / screening_time:.1f} stocks/second")
    print(f"   - Total data points processed: {num_stocks * num_days:,}")
    print(f"   - Qualifying symbols: {summary['qualifying_symbols']}")


def test_edge_cases():
    """Test edge cases and error handling."""
    print("\n\nTesting Edge Cases")
    print("=" * 50)
    
    # Test with minimal data
    print("\n1. Minimal data test:")
    stock = StockData(
        symbol="MIN",
        bars=[
            StockBar(
                symbol="MIN",
                date=date.today(),
                open=100, high=101, low=99, close=100,
                volume=1000000
            )
        ]
    )
    
    screener = ScreenerEngine()
    filters = [VolumeFilter(lookback_days=1, threshold=500000)]
    result = screener.screen([stock], filters)
    print(f"   - Result: {result.get_summary()}")
    
    # Test with insufficient data for moving average
    print("\n2. Insufficient data for MA test:")
    stock = generate_test_data("INSUFF", 5)
    filters = [MovingAverageFilter(period=10, position="above")]
    result = screener.screen([stock], filters)
    print(f"   - Result: {result.get_summary()}")
    print(f"   - Errors: {result.processing_errors}")
    
    # Test with empty stock list
    print("\n3. Empty stock list test:")
    result = screener.screen([], filters)
    print(f"   - Result: {result.get_summary()}")
    
    # Test with date range filtering
    print("\n4. Date range filtering test:")
    stock = generate_test_data("RANGE", 30)
    end_date = date.today()
    start_date = end_date - timedelta(days=10)
    
    filters = [VolumeFilter(lookback_days=5, threshold=500000)]
    result = screener.screen([stock], filters, date_range=(start_date, end_date))
    print(f"   - Date range: {start_date} to {end_date}")
    print(f"   - Result: {result.get_summary()}")


if __name__ == "__main__":
    # Run all tests
    test_individual_filters()
    test_composite_filter()
    test_screener_engine()
    test_performance()
    test_edge_cases()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("=" * 50)