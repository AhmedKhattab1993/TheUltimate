#!/usr/bin/env python3
"""
Test with lenient filters to demonstrate stocks passing through
"""
import asyncio
import httpx
import json
from datetime import date, timedelta

async def test_with_lenient_filters():
    """Test with progressively more lenient filters to show results"""
    
    # Use a recent date instead of future date
    end_date = date.today() - timedelta(days=5)  # 5 days ago
    start_date = end_date
    
    print(f"Testing with date: {end_date}")
    print("="*80)
    
    # Test configurations from strict to lenient
    test_configs = [
        {
            "name": "1. ORIGINAL STRICT FILTERS (Your Current Settings)",
            "filters": {
                "gap": {"min_gap_percent": 4.0},
                "price_range": {"min_price": 2.0, "max_price": 10.0},
                "relative_volume": {"min_relative_volume": 2.0, "lookback_days": 20}
            }
        },
        {
            "name": "2. MODERATE FILTERS (Gap 2%, Price $5-$50, Volume 1.5x)",
            "filters": {
                "gap": {"min_gap_percent": 2.0},
                "price_range": {"min_price": 5.0, "max_price": 50.0},
                "relative_volume": {"min_relative_volume": 1.5, "lookback_days": 20}
            }
        },
        {
            "name": "3. LENIENT FILTERS (Gap 1%, Price $10-$200, Volume 1.2x)",
            "filters": {
                "gap": {"min_gap_percent": 1.0},
                "price_range": {"min_price": 10.0, "max_price": 200.0},
                "relative_volume": {"min_relative_volume": 1.2, "lookback_days": 20}
            }
        },
        {
            "name": "4. VERY LENIENT (Gap 0.5%, Price $20-$500, Volume 1.1x)",
            "filters": {
                "gap": {"min_gap_percent": 0.5},
                "price_range": {"min_price": 20.0, "max_price": 500.0},
                "relative_volume": {"min_relative_volume": 1.1, "lookback_days": 20}
            }
        },
        {
            "name": "5. PRICE AND VOLUME ONLY (No Gap Filter)",
            "filters": {
                "price_range": {"min_price": 50.0, "max_price": 500.0},
                "relative_volume": {"min_relative_volume": 1.2, "lookback_days": 20}
            }
        }
    ]
    
    # Test with popular stocks
    test_symbols = ["AAPL", "MSFT", "GOOGL", "TSLA", "NVDA", "AMD", "META", "AMZN", "SPY", "QQQ",
                    "BAC", "F", "GE", "INTC", "T", "WMT", "DIS", "NFLX", "PYPL", "SQ"]
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        for config in test_configs:
            print(f"\n{config['name']}")
            print("-"*80)
            
            request_data = {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": test_symbols,
                "filters": config['filters']
            }
            
            try:
                # Start your server first with: python3 start.py
                response = await client.post(
                    "http://localhost:8000/api/v1/screen",
                    json=request_data
                )
                
                if response.status_code == 200:
                    data = response.json()
                    results = data.get('results', [])
                    total_screened = data.get('total_symbols_screened', 0)
                    
                    print(f"✅ Screened: {total_screened} stocks")
                    print(f"📊 Results: {len(results)} stocks passed all filters ({len(results)/total_screened*100:.1f}%)")
                    
                    if results:
                        print(f"🎯 Stocks that passed: {[r['symbol'] for r in results]}")
                        
                        # Show details for first few stocks
                        for result in results[:3]:
                            print(f"\n   {result['symbol']}:")
                            metrics = result.get('metrics', {})
                            if 'gap_percent' in metrics:
                                print(f"     - Gap: {metrics.get('gap_percent', 0):.2f}%")
                            if 'current_price' in metrics:
                                print(f"     - Price: ${metrics.get('current_price', 0):.2f}")
                            if 'relative_volume' in metrics:
                                print(f"     - Rel Volume: {metrics.get('relative_volume', 0):.2f}x")
                    else:
                        print("❌ No stocks passed these filters")
                        
                else:
                    print(f"❌ Error: {response.status_code}")
                    
            except Exception as e:
                print(f"❌ Request failed: {e}")
                print("⚠️  Make sure to start the server first with: python3 start.py")
    
    print("\n" + "="*80)
    print("SUMMARY:")
    print("- Strict filters (Gap 4%, Price $2-$10): Usually 0 results")
    print("- Moderate filters: Some results for active stocks")
    print("- Lenient filters: More results, better for finding opportunities")
    print("- Price/Volume only: Most results, good for general screening")
    print("\n💡 TIP: Adjust filters based on market conditions and your trading style")

if __name__ == "__main__":
    print("🔍 Testing Stock Screener with Different Filter Settings\n")
    asyncio.run(test_with_lenient_filters())