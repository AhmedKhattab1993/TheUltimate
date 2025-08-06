#!/usr/bin/env python3
"""
Quick test script to verify the stock screener is working properly
"""
import asyncio
import httpx
from datetime import date, timedelta
import json

API_BASE_URL = "http://localhost:8000/api/v1"

async def test_screener():
    async with httpx.AsyncClient() as client:
        # Test 1: Health check
        print("1. Testing health endpoint...")
        response = await client.get(f"{API_BASE_URL}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {json.dumps(response.json(), indent=2)}\n")
        
        # Test 2: Get available symbols
        print("2. Testing symbols endpoint...")
        response = await client.get(f"{API_BASE_URL}/symbols")
        symbols = response.json()
        print(f"   Status: {response.status_code}")
        print(f"   Available symbols: {len(symbols)}")
        print(f"   First 5 symbols: {symbols[:5]}\n")
        
        # Test 3: Get available filters
        print("3. Testing filters endpoint...")
        response = await client.get(f"{API_BASE_URL}/filters")
        print(f"   Status: {response.status_code}")
        print(f"   Available filters: {list(response.json().keys())}\n")
        
        # Test 4: Run a screen with filters
        print("4. Testing screen endpoint...")
        
        # Use recent dates to ensure data availability
        end_date = date.today() - timedelta(days=5)  # 5 days ago to ensure market data
        start_date = end_date - timedelta(days=30)   # 30 day window
        
        screen_request = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],  # Test with 5 stocks
            "filters": {
                "volume": {
                    "min_average": 10000000,  # 10M shares
                    "lookback_days": 20
                },
                "price_change": {
                    "min_change": -5.0,
                    "max_change": 5.0,
                    "period_days": 1
                },
                "moving_average": {
                    "period": 20,
                    "condition": "above"
                }
            }
        }
        
        print(f"   Screening {len(screen_request['symbols'])} stocks from {start_date} to {end_date}")
        print(f"   Filters: volume > 10M, price change -5% to 5%, price above 20-day MA")
        
        try:
            response = await client.post(
                f"{API_BASE_URL}/screen",
                json=screen_request,
                timeout=60.0  # Longer timeout for data fetching
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"\n   ✅ Screen completed successfully!")
                print(f"   Total symbols screened: {result['total_symbols_screened']}")
                print(f"   Qualifying stocks: {result['total_qualifying_stocks']}")
                print(f"   Execution time: {result['execution_time_ms']:.2f}ms")
                
                if result['results']:
                    print("\n   Sample results:")
                    for stock in result['results'][:3]:  # Show first 3
                        print(f"   - {stock['symbol']}: {len(stock['qualifying_dates'])} qualifying days")
                        if stock['metrics']:
                            print(f"     Avg Volume: {stock['metrics'].get('avg_volume', 'N/A'):,.0f}")
                            print(f"     Avg Price Change: {stock['metrics'].get('avg_price_change', 'N/A'):.2f}%")
            else:
                print(f"   ❌ Error: {response.status_code}")
                print(f"   Response: {response.text}")
        except Exception as e:
            print(f"   ❌ Error during screen: {e}")

if __name__ == "__main__":
    print("Stock Screener API Test\n" + "="*50 + "\n")
    
    print("Make sure the backend is running on http://localhost:8000")
    print("Start it with: cd backend && python3 run.py\n")
    
    asyncio.run(test_screener())