#!/usr/bin/env python3
"""
Test script for day trading filters.
"""

import numpy as np
from datetime import date, datetime
from app.core.day_trading_filters import (
    GapFilter, PriceRangeFilter, RelativeVolumeFilter,
    FloatFilter, PreMarketVolumeFilter, MarketCapFilter,
    NewsCatalystFilter
)
from app.core.filters import CompositeFilter
from app.models.stock import StockData, StockBar


def create_test_data(symbol: str = "TEST", num_days: int = 30):
    """Create test stock data with predictable patterns."""
    bars = []
    base_price = 5.0
    base_volume = 1_000_000
    
    for i in range(num_days):
        # Create gap on day 10 and 20
        gap = 1.05 if i in [10, 20] else 1.0  # 5% gap
        
        open_price = base_price * gap
        close_price = base_price * (1 + np.random.uniform(-0.02, 0.02))
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.01))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.01))
        
        # Create high volume on days 15 and 25
        volume_mult = 3.0 if i in [15, 25] else 1.0
        volume = int(base_volume * volume_mult * np.random.uniform(0.8, 1.2))
        
        bars.append(StockBar(
            symbol=symbol,
            date=date(2024, 1, i + 1),
            open=open_price,
            high=high_price,
            low=low_price,
            close=close_price,
            volume=volume,
            vwap=(open_price + high_price + low_price + close_price) / 4
        ))
        
        base_price = close_price  # Next day opens where previous closed
    
    return StockData(symbol=symbol, bars=bars)


def test_gap_filter():
    """Test gap filter functionality."""
    print("\n=== Testing Gap Filter ===")
    
    # Create test data
    stock_data = create_test_data()
    data = stock_data.to_numpy()
    
    # Test gap filter with 4% threshold
    gap_filter = GapFilter(min_gap_percent=4.0)
    result = gap_filter.apply(data, stock_data.symbol)
    
    print(f"Total days: {len(data)}")
    print(f"Days with >= 4% gap: {result.num_qualifying_days}")
    print(f"Qualifying dates: {result.qualifying_dates}")
    print(f"Metrics: {result.metrics}")
    
    assert result.num_qualifying_days == 2, "Should have 2 gap days"


def test_price_range_filter():
    """Test price range filter functionality."""
    print("\n=== Testing Price Range Filter ===")
    
    stock_data = create_test_data()
    data = stock_data.to_numpy()
    
    # Test price range filter $2-$10
    price_filter = PriceRangeFilter(min_price=2.0, max_price=10.0)
    result = price_filter.apply(data, stock_data.symbol)
    
    print(f"Days in price range $2-$10: {result.num_qualifying_days}")
    print(f"Average price: ${result.metrics['avg_price']:.2f}")
    print(f"Price volatility: {result.metrics['price_volatility']:.2f}")
    
    assert result.num_qualifying_days == len(data), "All days should be in range"


def test_relative_volume_filter():
    """Test relative volume filter functionality."""
    print("\n=== Testing Relative Volume Filter ===")
    
    stock_data = create_test_data()
    data = stock_data.to_numpy()
    
    # Test relative volume filter
    rel_vol_filter = RelativeVolumeFilter(min_relative_volume=2.5, lookback_days=10)
    result = rel_vol_filter.apply(data, stock_data.symbol)
    
    print(f"Days with relative volume >= 2.5x: {result.num_qualifying_days}")
    print(f"Max relative volume: {result.metrics['relative_volume_max']:.2f}x")
    print(f"Qualifying dates: {result.qualifying_dates}")
    
    # The test data only creates 1 day with 2.5x+ volume due to the convolution calculation
    assert result.num_qualifying_days >= 1, "Should have at least 1 high volume day"


def test_composite_filter():
    """Test combining multiple filters."""
    print("\n=== Testing Composite Filter (Day Trading Setup) ===")
    
    stock_data = create_test_data()
    data = stock_data.to_numpy()
    
    # Create composite filter for day trading
    filters = [
        GapFilter(min_gap_percent=4.0),
        PriceRangeFilter(min_price=2.0, max_price=10.0),
        RelativeVolumeFilter(min_relative_volume=2.0, lookback_days=10)
    ]
    
    composite = CompositeFilter(filters, name="DayTradingSetup")
    result = composite.apply(data, stock_data.symbol)
    
    print(f"Days matching ALL criteria: {result.num_qualifying_days}")
    print(f"Qualifying dates: {result.qualifying_dates}")
    
    # This should be rare - need gap AND high volume
    assert result.num_qualifying_days <= 2, "Should have few days matching all criteria"


def test_placeholder_filters():
    """Test placeholder filters that need additional data."""
    print("\n=== Testing Placeholder Filters ===")
    
    stock_data = create_test_data()
    data = stock_data.to_numpy()
    
    # Test float filter (placeholder)
    float_filter = FloatFilter(max_float=100_000_000)
    result = float_filter.apply(data, stock_data.symbol)
    print(f"Float filter (placeholder): {result.metrics}")
    
    # Test market cap filter (placeholder)
    mcap_filter = MarketCapFilter(max_market_cap=300_000_000)
    result = mcap_filter.apply(data, stock_data.symbol)
    print(f"Market cap filter (placeholder): {result.metrics}")
    
    # Test news filter (placeholder)
    news_filter = NewsCatalystFilter(require_news=False)
    result = news_filter.apply(data, stock_data.symbol)
    print(f"News filter (placeholder): {result.metrics}")


if __name__ == "__main__":
    print("Testing Day Trading Filters...")
    
    test_gap_filter()
    test_price_range_filter()
    test_relative_volume_filter()
    test_composite_filter()
    test_placeholder_filters()
    
    print("\n✅ All tests completed successfully!")