"""
Example usage of the high-performance screener engine with real market data.

This example demonstrates how to:
1. Fetch real stock data using PolygonClient
2. Apply various filters using the screener engine
3. Analyze results and extract insights
"""

import asyncio
from datetime import date, timedelta
from typing import List
import os

from ..services.polygon_client import PolygonClient
from ..services.screener import ScreenerEngine
from ..core.filters import VolumeFilter, PriceChangeFilter, MovingAverageFilter
from ..models.stock import StockData


async def fetch_stock_data(symbols: List[str], days_back: int = 60) -> List[StockData]:
    """Fetch historical stock data for given symbols."""
    # Initialize Polygon client
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        raise ValueError("POLYGON_API_KEY environment variable not set")
    
    client = PolygonClient(api_key)
    
    # Calculate date range
    end_date = date.today()
    start_date = end_date - timedelta(days=days_back)
    
    # Fetch data for all symbols
    stock_data_list = []
    
    for symbol in symbols:
        print(f"Fetching data for {symbol}...")
        try:
            data = await client.get_stock_bars(
                symbol=symbol,
                from_date=start_date.isoformat(),
                to_date=end_date.isoformat(),
                timespan="day"
            )
            stock_data_list.append(data)
        except Exception as e:
            print(f"Error fetching {symbol}: {e}")
    
    return stock_data_list


def run_volume_breakout_screen(stock_data_list: List[StockData]):
    """Screen for stocks with volume breakouts."""
    print("\n" + "=" * 60)
    print("VOLUME BREAKOUT SCREENER")
    print("=" * 60)
    
    # Define filters for volume breakout pattern
    filters = [
        # High volume (50% above 20-day average)
        VolumeFilter(lookback_days=20, threshold=1.5e6, name="HighVolume"),
        
        # Positive price movement
        PriceChangeFilter(min_change=2.0, max_change=10.0, name="PositiveMomentum"),
        
        # Price above 20-day moving average
        MovingAverageFilter(period=20, position="above", name="AboveMA20")
    ]
    
    # Run screener
    screener = ScreenerEngine(max_workers=4)
    results = screener.screen_with_metrics(
        stock_data_list,
        filters,
        metric_aggregations={
            'avg_volume_*_mean': 'mean',
            'price_change_mean': 'mean',
            'distance_from_sma_*_mean': 'mean'
        }
    )
    
    # Display results
    print(f"\nScreening Summary:")
    print(f"  - Total stocks screened: {results['summary']['total_processed']}")
    print(f"  - Qualifying stocks: {results['summary']['qualifying_symbols']}")
    print(f"  - Processing time: {results['summary']['processing_time_ms']:.1f}ms")
    
    print(f"\nTop Volume Breakout Candidates:")
    # Sort by number of qualifying days
    sorted_symbols = sorted(
        results['qualifying_symbols'],
        key=lambda x: x['qualifying_days'],
        reverse=True
    )
    
    for i, symbol_info in enumerate(sorted_symbols[:5], 1):
        print(f"\n{i}. {symbol_info['symbol']}:")
        print(f"   - Qualifying days: {symbol_info['qualifying_days']}")
        print(f"   - Date range: {symbol_info['first_qualifying_date']} to {symbol_info['last_qualifying_date']}")
        print(f"   - Avg volume: {symbol_info['metrics'].get('avg_volume_20d_mean', 0):,.0f}")
        print(f"   - Avg price change: {symbol_info['metrics'].get('price_change_mean', 0):.2f}%")
        print(f"   - Distance from MA20: {symbol_info['metrics'].get('distance_from_sma_20_mean', 0):.2f}%")


def run_momentum_screen(stock_data_list: List[StockData]):
    """Screen for stocks with strong momentum characteristics."""
    print("\n" + "=" * 60)
    print("MOMENTUM SCREENER")
    print("=" * 60)
    
    # Define filters for momentum pattern
    filters = [
        # Moderate to high volume
        VolumeFilter(lookback_days=10, threshold=1e6, name="ModerateVolume"),
        
        # Consistent positive price movement
        PriceChangeFilter(min_change=0.5, max_change=5.0, name="SteadyGains"),
        
        # Price above both 10 and 20 day moving averages
        MovingAverageFilter(period=10, position="above", name="AboveMA10"),
        MovingAverageFilter(period=20, position="above", name="AboveMA20")
    ]
    
    # Run screener
    screener = ScreenerEngine(max_workers=4)
    results = screener.screen_with_metrics(stock_data_list, filters)
    
    # Display results
    print(f"\nScreening Summary:")
    print(f"  - Total stocks screened: {results['summary']['total_processed']}")
    print(f"  - Qualifying stocks: {results['summary']['qualifying_symbols']}")
    
    print(f"\nTop Momentum Stocks:")
    for i, symbol_info in enumerate(results['qualifying_symbols'][:5], 1):
        print(f"\n{i}. {symbol_info['symbol']}:")
        print(f"   - Momentum score (qualifying days): {symbol_info['qualifying_days']}")
        print(f"   - Consistency period: {symbol_info['first_qualifying_date']} to {symbol_info['last_qualifying_date']}")


def run_volatility_screen(stock_data_list: List[StockData]):
    """Screen for stocks with specific volatility characteristics."""
    print("\n" + "=" * 60)
    print("LOW VOLATILITY SCREENER")
    print("=" * 60)
    
    # Define filters for low volatility pattern
    filters = [
        # Decent volume to ensure liquidity
        VolumeFilter(lookback_days=20, threshold=500000, name="LiquidityFilter"),
        
        # Low daily price changes (low volatility)
        PriceChangeFilter(min_change=-1.5, max_change=1.5, name="LowVolatility"),
        
        # Close to moving average (stable trend)
        MovingAverageFilter(period=50, position="above", name="StableTrend")
    ]
    
    # Run screener with date range (last 30 days)
    screener = ScreenerEngine(max_workers=4)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    results = screener.screen(
        stock_data_list,
        filters,
        date_range=(start_date, end_date)
    )
    
    # Display results
    print(f"\nScreening Summary (Last 30 Days):")
    print(f"  - Total stocks screened: {results.num_processed}")
    print(f"  - Low volatility stocks: {len(results.qualifying_symbols)}")
    
    print(f"\nLow Volatility Stocks:")
    for symbol in results.qualifying_symbols[:10]:
        result = results.results[symbol]
        print(f"  - {symbol}: {result.num_qualifying_days} stable days")


async def main():
    """Main function to run all screeners."""
    # Define universe of stocks to screen
    # In practice, this could be S&P 500, sector-specific, or custom watchlist
    symbols = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META",
        "TSLA", "NVDA", "AMD", "INTC", "QCOM",
        "JPM", "BAC", "WFC", "GS", "MS",
        "JNJ", "PFE", "UNH", "CVS", "ABBV",
        "XOM", "CVX", "COP", "SLB", "EOG"
    ]
    
    print("Fetching stock data...")
    stock_data_list = await fetch_stock_data(symbols, days_back=60)
    print(f"Successfully fetched data for {len(stock_data_list)} stocks")
    
    # Run different screening strategies
    run_volume_breakout_screen(stock_data_list)
    run_momentum_screen(stock_data_list)
    run_volatility_screen(stock_data_list)
    
    print("\n" + "=" * 60)
    print("Screening completed!")
    print("=" * 60)


if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())