#!/usr/bin/env python3
"""
Example: Screen all US common stocks using the ticker discovery feature.

This example shows how to use the new use_all_us_stocks parameter to screen
the entire universe of US common stocks instead of a predefined list.
"""

import asyncio
import httpx
from datetime import date, timedelta
import json


async def screen_all_us_stocks():
    """Example of screening all US stocks with volume filter."""
    
    # API endpoint
    base_url = "http://localhost:8000"
    endpoint = f"{base_url}/api/screener/screen"
    
    # Define screening parameters
    end_date = date.today()
    start_date = end_date - timedelta(days=30)  # Last 30 days
    
    # Screen request with use_all_us_stocks flag
    screen_request = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "use_all_us_stocks": True,  # This is the key flag!
        "filters": {
            "volume": {
                "min_average": 1000000,  # At least 1M average volume
                "lookback_days": 20
            },
            "price_change": {
                "min_change": 5.0,  # At least 5% gain
                "period_days": 5    # Over last 5 days
            }
        }
    }
    
    print("Universe Screening Example")
    print("=" * 50)
    print(f"Screening ALL US common stocks from {start_date} to {end_date}")
    print(f"Filters:")
    print(f"  - Average volume > 1M shares (20-day average)")
    print(f"  - Price change > 5% (5-day period)")
    print("\nThis may take several minutes due to the large number of stocks...")
    
    async with httpx.AsyncClient(timeout=300.0) as client:  # 5 minute timeout
        try:
            response = await client.post(endpoint, json=screen_request)
            
            if response.status_code == 200:
                result = response.json()
                
                print(f"\n✅ Screening completed successfully!")
                print(f"   - Total stocks screened: {result['total_symbols_screened']}")
                print(f"   - Qualifying stocks: {result['total_qualifying_stocks']}")
                print(f"   - Execution time: {result['execution_time_ms']:.2f}ms")
                
                # Show top 10 results
                if result['results']:
                    print("\nTop 10 qualifying stocks:")
                    for i, stock in enumerate(result['results'][:10], 1):
                        metrics = stock['metrics']
                        print(f"\n{i}. {stock['symbol']}:")
                        print(f"   - Average Volume: {metrics.get('average_volume', 'N/A'):,.0f}")
                        print(f"   - Price Change: {metrics.get('price_change_percent', 'N/A'):.2f}%")
                        
            else:
                print(f"\n❌ Error: {response.status_code}")
                print(f"   {response.text}")
                
        except httpx.TimeoutException:
            print("\n❌ Request timed out. Screening large universe can take time.")
        except Exception as e:
            print(f"\n❌ Error: {e}")


async def compare_universe_sizes():
    """Compare default universe vs all US stocks."""
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        try:
            # Get default symbols
            response = await client.get(f"{base_url}/api/screener/symbols")
            default_symbols = response.json() if response.status_code == 200 else []
            
            # Get all US stocks
            print("\nFetching all US common stocks (this may take 10-30 seconds)...")
            response = await client.get(f"{base_url}/api/screener/symbols/us-stocks")
            all_us_stocks = response.json() if response.status_code == 200 else []
            
            print("\nUniverse Comparison:")
            print(f"  - Default universe: {len(default_symbols)} stocks")
            print(f"  - All US common stocks: {len(all_us_stocks)} stocks")
            print(f"  - Difference: {len(all_us_stocks) - len(default_symbols)} additional stocks")
            
        except Exception as e:
            print(f"Error comparing universes: {e}")


if __name__ == "__main__":
    print("Make sure the backend API is running (cd backend && uvicorn app.main:app)")
    print()
    
    # First, compare universe sizes
    asyncio.run(compare_universe_sizes())
    
    # Then run the screening example
    print("\n" + "=" * 50)
    input("Press Enter to run universe screening example...")
    asyncio.run(screen_all_us_stocks())