#!/usr/bin/env python3
"""
Example script demonstrating how to use the Stock Screener API.

This script shows various API calls and how to work with the responses.
"""

import asyncio
import httpx
from datetime import date, timedelta
import json
from typing import Dict, Any


API_BASE_URL = "http://localhost:8000/api/v1"


async def check_health():
    """Check API health status."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/health")
        
        if response.status_code == 200:
            data = response.json()
            print("Health Check:")
            print(f"  Status: {data['status']}")
            print(f"  Timestamp: {data['timestamp']}")
            print(f"  Polygon API: {data['checks']['polygon_api']['status']}")
            print(f"  Response Time: {data['response_time_ms']:.2f}ms")
        else:
            print(f"Health check failed: {response.status_code}")
        
        print()


async def get_available_symbols():
    """Get list of available symbols."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/symbols")
        
        if response.status_code == 200:
            symbols = response.json()
            print(f"Available Symbols ({len(symbols)} total):")
            print(f"  {', '.join(symbols[:10])}...")
        else:
            print(f"Failed to get symbols: {response.status_code}")
        
        print()


async def get_available_filters():
    """Get information about available filters."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{API_BASE_URL}/filters")
        
        if response.status_code == 200:
            filters = response.json()
            print("Available Filters:")
            for filter_name, filter_info in filters.items():
                print(f"  {filter_name}: {filter_info['description']}")
                print(f"    Parameters:")
                for param_name, param_info in filter_info['parameters'].items():
                    print(f"      - {param_name}: {param_info['description']}")
        else:
            print(f"Failed to get filters: {response.status_code}")
        
        print()


async def screen_volume_filter():
    """Example: Screen for high volume stocks."""
    print("Example 1: High Volume Stocks")
    print("-" * 40)
    
    # Set date range (last 30 days)
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    request_data = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"],  # Limited symbols for faster demo
        "filters": {
            "volume": {
                "min_average": 10000000,  # 10M minimum average volume
                "lookback_days": 20
            }
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/screen",
            json=request_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total symbols screened: {data['total_symbols_screened']}")
            print(f"Qualifying stocks: {data['total_qualifying_stocks']}")
            print(f"Execution time: {data['execution_time_ms']:.2f}ms")
            
            if data['results']:
                print("\nQualifying Stocks:")
                for result in data['results']:
                    print(f"  {result['symbol']}:")
                    print(f"    Qualifying dates: {len(result['qualifying_dates'])}")
                    print(f"    Average volume (20d): {result['metrics'].get('avg_volume_20d_mean', 0):,.0f}")
        else:
            print(f"Screening failed: {response.status_code}")
            print(response.json())
    
    print()


async def screen_price_change_filter():
    """Example: Screen for stocks with significant price changes."""
    print("Example 2: Price Change Filter")
    print("-" * 40)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    request_data = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "symbols": ["AAPL", "MSFT", "GOOGL", "NVDA", "TSLA"],
        "filters": {
            "price_change": {
                "min_change": 2.0,  # Minimum 2% daily gain
                "max_change": 10.0,  # Maximum 10% daily gain
                "period_days": 1
            }
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/screen",
            json=request_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total symbols screened: {data['total_symbols_screened']}")
            print(f"Qualifying stocks: {data['total_qualifying_stocks']}")
            
            if data['results']:
                print("\nStocks with 2-10% daily gains:")
                for result in data['results']:
                    print(f"  {result['symbol']}:")
                    print(f"    Days with qualifying gains: {len(result['qualifying_dates'])}")
                    print(f"    Average price change: {result['metrics'].get('price_change_mean', 0):.2f}%")
                    print(f"    Max price change: {result['metrics'].get('price_change_max', 0):.2f}%")
        else:
            print(f"Screening failed: {response.status_code}")
            print(response.json())
    
    print()


async def screen_moving_average_filter():
    """Example: Screen for stocks above their 50-day moving average."""
    print("Example 3: Moving Average Filter")
    print("-" * 40)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=90)  # Need more data for 50-day MA
    
    request_data = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN"],
        "filters": {
            "moving_average": {
                "period": 50,
                "condition": "above"
            }
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/screen",
            json=request_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total symbols screened: {data['total_symbols_screened']}")
            print(f"Qualifying stocks: {data['total_qualifying_stocks']}")
            
            if data['results']:
                print("\nStocks above 50-day MA:")
                for result in data['results']:
                    print(f"  {result['symbol']}:")
                    print(f"    Days above MA: {len(result['qualifying_dates'])}")
                    print(f"    Avg distance from MA: {result['metrics'].get('distance_from_sma_50_mean', 0):.2f}%")
        else:
            print(f"Screening failed: {response.status_code}")
            print(response.json())
    
    print()


async def screen_combined_filters():
    """Example: Screen with multiple filters combined."""
    print("Example 4: Combined Filters")
    print("-" * 40)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=60)
    
    request_data = {
        "start_date": str(start_date),
        "end_date": str(end_date),
        "symbols": None,  # Use default symbol universe
        "filters": {
            "volume": {
                "min_average": 5000000,
                "lookback_days": 20
            },
            "price_change": {
                "min_change": -2.0,
                "max_change": 5.0,
                "period_days": 1
            },
            "moving_average": {
                "period": 20,
                "condition": "above"
            }
        }
    }
    
    print("Screening with:")
    print("  - Volume > 5M (20-day average)")
    print("  - Daily price change between -2% and 5%")
    print("  - Price above 20-day moving average")
    print()
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(
            f"{API_BASE_URL}/screen",
            json=request_data
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Total symbols screened: {data['total_symbols_screened']}")
            print(f"Qualifying stocks: {data['total_qualifying_stocks']}")
            print(f"Execution time: {data['execution_time_ms']:.2f}ms")
            
            if data['results']:
                print("\nTop qualifying stocks:")
                # Sort by number of qualifying days
                sorted_results = sorted(
                    data['results'], 
                    key=lambda x: len(x['qualifying_dates']), 
                    reverse=True
                )[:5]
                
                for result in sorted_results:
                    print(f"  {result['symbol']}:")
                    print(f"    Qualifying days: {len(result['qualifying_dates'])}")
                    print(f"    Avg volume: {result['metrics'].get('avg_volume_20d_mean', 0):,.0f}")
                    print(f"    Avg price change: {result['metrics'].get('price_change_mean', 0):.2f}%")
                    print(f"    Distance from MA20: {result['metrics'].get('distance_from_sma_20_mean', 0):.2f}%")
        else:
            print(f"Screening failed: {response.status_code}")
            print(response.json())
    
    print()


async def main():
    """Run all examples."""
    print("Stock Screener API Usage Examples")
    print("=" * 50)
    print()
    
    # Check health first
    await check_health()
    
    # Get available resources
    await get_available_symbols()
    await get_available_filters()
    
    # Run screening examples
    await screen_volume_filter()
    await screen_price_change_filter()
    await screen_moving_average_filter()
    await screen_combined_filters()
    
    print("\nAll examples completed!")


if __name__ == "__main__":
    # Note: Make sure the API server is running before executing this script
    print("Note: This script requires the API server to be running on http://localhost:8000")
    print("Start the server with: python run.py")
    print()
    
    asyncio.run(main())