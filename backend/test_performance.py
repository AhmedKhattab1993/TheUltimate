#!/usr/bin/env python3
"""
Performance test for day trading filters with numpy vectorization.
"""

import numpy as np
import time
from datetime import date, timedelta
from app.core.day_trading_filters import (
    GapFilter, PriceRangeFilter, RelativeVolumeFilter
)
from app.core.filters import CompositeFilter
from app.models.stock import StockData, StockBar


def create_large_dataset(num_days: int = 1000) -> StockData:
    """Create a large dataset for performance testing."""
    bars = []
    base_price = 100.0
    base_volume = 1_000_000
    
    for i in range(num_days):
        # Add some randomness
        open_price = base_price * (1 + np.random.uniform(-0.05, 0.05))
        close_price = open_price * (1 + np.random.uniform(-0.02, 0.02))
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.01))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.01))
        volume = int(base_volume * np.random.uniform(0.5, 2.0))
        
        bars.append(StockBar(
            symbol="TEST",
            date=date.today() - timedelta(days=num_days-i),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            vwap=(open_price + high_price + low_price + close_price) / 4
        ))
        
        base_price = close_price
    
    return StockData(symbol="TEST", bars=bars)


def test_individual_filter_performance():
    """Test performance of individual filters."""
    print("\n=== Individual Filter Performance Test ===")
    
    # Create datasets of different sizes
    sizes = [100, 500, 1000, 5000]
    
    for size in sizes:
        print(f"\nDataset size: {size} days")
        stock_data = create_large_dataset(size)
        data = stock_data.to_numpy()
        
        # Test Gap Filter
        gap_filter = GapFilter(min_gap_percent=2.0)
        start_time = time.time()
        result = gap_filter.apply(data, stock_data.symbol)
        gap_time = (time.time() - start_time) * 1000
        print(f"  Gap Filter: {gap_time:.2f}ms")
        
        # Test Price Range Filter
        price_filter = PriceRangeFilter(min_price=50.0, max_price=150.0)
        start_time = time.time()
        result = price_filter.apply(data, stock_data.symbol)
        price_time = (time.time() - start_time) * 1000
        print(f"  Price Range Filter: {price_time:.2f}ms")
        
        # Test Relative Volume Filter
        rel_vol_filter = RelativeVolumeFilter(min_relative_volume=1.5)
        start_time = time.time()
        result = rel_vol_filter.apply(data, stock_data.symbol)
        rel_vol_time = (time.time() - start_time) * 1000
        print(f"  Relative Volume Filter: {rel_vol_time:.2f}ms")


def test_composite_filter_performance():
    """Test performance of composite filters."""
    print("\n=== Composite Filter Performance Test ===")
    
    stock_data = create_large_dataset(1000)
    data = stock_data.to_numpy()
    
    # Create composite filter with all day trading filters
    filters = [
        GapFilter(min_gap_percent=2.0),
        PriceRangeFilter(min_price=50.0, max_price=150.0),
        RelativeVolumeFilter(min_relative_volume=1.5, lookback_days=20)
    ]
    
    composite = CompositeFilter(filters, name="DayTradingComposite")
    
    # Test multiple runs
    times = []
    for i in range(10):
        start_time = time.time()
        result = composite.apply(data, stock_data.symbol)
        execution_time = (time.time() - start_time) * 1000
        times.append(execution_time)
    
    print(f"\nComposite filter on 1000 days:")
    print(f"  Average time: {np.mean(times):.2f}ms")
    print(f"  Min time: {np.min(times):.2f}ms")
    print(f"  Max time: {np.max(times):.2f}ms")
    print(f"  Std dev: {np.std(times):.2f}ms")


def test_vectorization_efficiency():
    """Compare vectorized vs non-vectorized operations."""
    print("\n=== Vectorization Efficiency Test ===")
    
    # Create large array
    size = 10000
    prices = np.random.uniform(50, 150, size)
    volumes = np.random.uniform(500000, 2000000, size)
    
    # Test vectorized operation
    start_time = time.time()
    mask = (prices > 75) & (prices < 125) & (volumes > 1000000)
    qualifying = np.sum(mask)
    vectorized_time = (time.time() - start_time) * 1000
    
    # Test loop-based operation
    start_time = time.time()
    count = 0
    for i in range(size):
        if prices[i] > 75 and prices[i] < 125 and volumes[i] > 1000000:
            count += 1
    loop_time = (time.time() - start_time) * 1000
    
    print(f"\nProcessing {size} data points:")
    print(f"  Vectorized: {vectorized_time:.2f}ms")
    print(f"  Loop-based: {loop_time:.2f}ms")
    print(f"  Speedup: {loop_time/vectorized_time:.1f}x")
    print(f"  Results match: {qualifying == count}")


def test_memory_efficiency():
    """Test memory usage of filters."""
    print("\n=== Memory Efficiency Test ===")
    
    import psutil
    import os
    
    process = psutil.Process(os.getpid())
    
    # Baseline memory
    baseline_memory = process.memory_info().rss / 1024 / 1024  # MB
    print(f"Baseline memory: {baseline_memory:.1f} MB")
    
    # Create large dataset
    stock_data = create_large_dataset(10000)
    data = stock_data.to_numpy()
    after_data_memory = process.memory_info().rss / 1024 / 1024
    print(f"After creating 10k days dataset: {after_data_memory:.1f} MB")
    print(f"Dataset memory usage: {after_data_memory - baseline_memory:.1f} MB")
    
    # Apply filters
    filters = [
        GapFilter(min_gap_percent=2.0),
        PriceRangeFilter(min_price=50.0, max_price=150.0),
        RelativeVolumeFilter(min_relative_volume=1.5)
    ]
    
    results = []
    for filter in filters:
        result = filter.apply(data, stock_data.symbol)
        results.append(result)
    
    after_filter_memory = process.memory_info().rss / 1024 / 1024
    print(f"After applying filters: {after_filter_memory:.1f} MB")
    print(f"Filter memory overhead: {after_filter_memory - after_data_memory:.1f} MB")


def main():
    """Run all performance tests."""
    print("=" * 60)
    print("Performance Tests for Day Trading Filters")
    print("=" * 60)
    
    test_individual_filter_performance()
    test_composite_filter_performance()
    test_vectorization_efficiency()
    # test_memory_efficiency()  # Skipped - requires psutil
    
    print("\n" + "=" * 60)
    print("✅ Performance tests completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()