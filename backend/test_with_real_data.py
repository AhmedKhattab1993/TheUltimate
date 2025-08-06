#!/usr/bin/env python3
"""
Test with real historical data from a known active trading day
"""
import asyncio
import httpx
import json

async def test_with_real_historical_data():
    """Test with actual historical data"""
    
    # Use a known active trading day (recent past)
    test_date = "2024-01-10"  # A real trading day in the past
    
    print(f"Testing with historical date: {test_date}")
    print("="*80)
    
    # Test with increasingly lenient filters
    test_configs = [
        {
            "name": "1. VERY LENIENT FILTERS (To ensure we see some results)",
            "filters": {
                "price_range": {"min_price": 1.0, "max_price": 10000.0}
            }
        },
        {
            "name": "2. ADD VOLUME FILTER",
            "filters": {
                "price_range": {"min_price": 1.0, "max_price": 10000.0},
                "volume": {"min_average": 100000, "lookback_days": 20}
            }
        },
        {
            "name": "3. ADD SMALL GAP FILTER",
            "filters": {
                "price_range": {"min_price": 1.0, "max_price": 10000.0},
                "volume": {"min_average": 100000, "lookback_days": 20},
                "gap": {"min_gap_percent": 0.1}  # Very small gap
            }
        },
        {
            "name": "4. YOUR ORIGINAL FILTERS (for comparison)",
            "filters": {
                "gap": {"min_gap_percent": 4.0},
                "price_range": {"min_price": 2.0, "max_price": 10.0},
                "relative_volume": {"min_relative_volume": 2.0, "lookback_days": 20}
            }
        }
    ]
    
    # Test with well-known liquid stocks
    test_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "NVDA", "AMD", "SPY", "QQQ"]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for config in test_configs:
            print(f"\n{config['name']}")
            print("-"*80)
            
            request_data = {
                "start_date": test_date,
                "end_date": test_date,
                "symbols": test_symbols,
                "filters": config['filters']
            }
            
            try:
                response = await client.post(
                    "http://localhost:8000/api/v1/screen",
                    json=request_data
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])
                    total_screened = data.get('total_symbols_screened', 0)
                    
                    print(f"✅ Screened: {total_screened} stocks")
                    print(f"📊 Results: {len(results)} stocks passed ({len(results)/total_screened*100:.1f}%)")
                    
                    if results:
                        print(f"🎯 Stocks that passed: {[r['symbol'] for r in results]}")
                        
                        # Show some metrics
                        for result in results[:3]:
                            print(f"\n   {result['symbol']}:")
                            metrics = result.get('metrics', {})
                            print(f"     Qualifying dates: {result.get('qualifying_dates', [])}")
                            if metrics:
                                for key, value in list(metrics.items())[:5]:
                                    if isinstance(value, (int, float)):
                                        print(f"     - {key}: {value:.2f}")
                    else:
                        print("❌ No stocks passed these filters")
                        
                else:
                    print(f"❌ Error: {response.status_code} - {response.text[:200]}")
                    
            except Exception as e:
                print(f"❌ Request failed: {e}")
    
    # Now test with the full US stock universe for better results
    print("\n" + "="*80)
    print("TESTING WITH ALL US STOCKS (Better chance of finding matches)")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=180.0) as client:
        # Test with lenient filters on all US stocks
        request_data = {
            "start_date": test_date,
            "end_date": test_date,
            "use_all_us_stocks": True,
            "filters": {
                "price_range": {"min_price": 5.0, "max_price": 50.0},
                "volume": {"min_average": 1000000, "lookback_days": 20}
            }
        }
        
        print("\nTesting all US stocks with Price $5-$50 and Volume > 1M...")
        
        try:
            response = await client.post(
                "http://localhost:8000/api/v1/screen",
                json=request_data
            )
            
            if response.status_code == 200:
                data = response.json()
                results = data.get('results', [])
                total_screened = data.get('total_symbols_screened', 0)
                
                print(f"✅ Screened: {total_screened} stocks")
                print(f"📊 Results: {len(results)} stocks passed ({len(results)/total_screened*100:.1f}%)")
                
                if results:
                    # Show first 10 results
                    print(f"🎯 Sample stocks that passed: {[r['symbol'] for r in results[:10]]}")
                    print(f"   ... and {len(results) - 10} more stocks")
                    
        except Exception as e:
            print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    print("🔍 Testing Stock Screener with Real Historical Data\n")
    asyncio.run(test_with_real_historical_data())