#!/usr/bin/env python3
"""
Comprehensive test for real-world screening scenarios with performance optimizations.
"""

import httpx
import asyncio
import time
import json
from datetime import date, timedelta


async def test_comprehensive_screening():
    """Test various screening scenarios to verify optimizations"""
    
    base_url = "http://localhost:8080/api/v1"
    
    # Test configuration
    end_date = date.today()
    start_date = end_date - timedelta(days=30)
    
    # Different screening scenarios
    test_scenarios = [
        {
            "name": "High Volume Gainers",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filters": {
                    "volume": {
                        "min_average": 5000000,
                        "lookback_days": 20
                    },
                    "price_change": {
                        "min_change": 5.0,
                        "max_change": 50.0,
                        "period_days": 1
                    }
                }
            }
        },
        {
            "name": "Above 50-day MA with Strong Volume",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filters": {
                    "volume": {
                        "min_average": 3000000,
                        "lookback_days": 20
                    },
                    "moving_average": {
                        "period": 50,
                        "condition": "above"
                    }
                }
            }
        },
        {
            "name": "Day Trading Setup - Gap and Go",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filters": {
                    "gap": {
                        "min_gap_percent": 4.0,
                        "max_gap_percent": 20.0
                    },
                    "price_range": {
                        "min_price": 2.0,
                        "max_price": 50.0
                    },
                    "relative_volume": {
                        "min_relative_volume": 2.0,
                        "lookback_days": 20
                    }
                }
            }
        },
        {
            "name": "Small Cap Movers",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "filters": {
                    "market_cap": {
                        "max_market_cap": 300000000,
                        "min_market_cap": 50000000
                    },
                    "price_change": {
                        "min_change": 3.0,
                        "period_days": 1
                    },
                    "volume": {
                        "min_average": 1000000
                    }
                }
            }
        },
        {
            "name": "Multiple Filters Combined",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM"],
                "filters": {
                    "volume": {
                        "min_average": 1000000,
                        "lookback_days": 20
                    },
                    "price_change": {
                        "min_change": -10.0,
                        "max_change": 10.0,
                        "period_days": 5
                    },
                    "moving_average": {
                        "period": 20,
                        "condition": "above"
                    }
                }
            }
        }
    ]
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        print("=" * 80)
        print("COMPREHENSIVE SCREENING TEST")
        print("=" * 80)
        
        # Run each scenario
        for i, scenario in enumerate(test_scenarios, 1):
            print(f"\n{i}. {scenario['name']}")
            print("-" * 60)
            
            # First run (cold cache)
            print("First run (cold cache):")
            start_time = time.time()
            
            try:
                response1 = await client.post(
                    f"{base_url}/screen",
                    json=scenario['request']
                )
                
                time1 = time.time() - start_time
                
                if response1.status_code == 200:
                    result1 = response1.json()
                    print(f"  ✓ Success in {time1:.2f} seconds")
                    print(f"  Total symbols screened: {result1['total_symbols_screened']}")
                    print(f"  Qualifying stocks: {result1['total_qualifying_stocks']}")
                    print(f"  API execution time: {result1['execution_time_ms']:.2f}ms")
                    
                    # Show some results
                    if result1['results']:
                        symbols = [r['symbol'] for r in result1['results'][:5]]
                        print(f"  Sample results: {symbols}")
                else:
                    print(f"  ✗ Failed with status {response1.status_code}")
                    print(f"  Error: {response1.text}")
                    continue
                    
                # Second run (warm cache)
                print("\nSecond run (warm cache):")
                start_time = time.time()
                
                response2 = await client.post(
                    f"{base_url}/screen",
                    json=scenario['request']
                )
                
                time2 = time.time() - start_time
                
                if response2.status_code == 200:
                    result2 = response2.json()
                    print(f"  ✓ Success in {time2:.2f} seconds")
                    print(f"  API execution time: {result2['execution_time_ms']:.2f}ms")
                    if time2 > 0:
                        print(f"  Cache speedup: {(time1/time2):.2f}x faster")
                    
                    # Verify results are consistent
                    if result1['total_qualifying_stocks'] == result2['total_qualifying_stocks']:
                        print("  ✓ Results are consistent between runs")
                    else:
                        print("  ✗ WARNING: Different results between runs!")
                        
            except httpx.TimeoutException:
                elapsed = time.time() - start_time
                print(f"  ✗ Request timed out after {elapsed:.2f} seconds")
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
        
        # Test with large dataset (if desired)
        print("\n" + "=" * 80)
        print("STRESS TEST: Large Dataset Performance")
        print("-" * 60)
        
        # Test with 100 symbols
        large_symbols = [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
            "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
            "PFE", "CVX", "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO",
            "VZ", "ADBE", "CMCSA", "NFLX", "INTC", "T", "ORCL", "IBM", "AMD",
            "QCOM", "TXN", "AVGO", "CRM", "PYPL", "NOW", "UBER", "SQ", "SHOP",
            "ROKU", "SNAP", "PINS", "ZM", "DOCU", "OKTA", "TWLO", "NET",
            "DDOG", "SNOW", "ABNB", "DASH", "COIN", "HOOD", "RIVN", "LCID",
            "F", "GM", "COST", "TGT", "LOW", "CVS", "WBA", "CI", "ANTM",
            "UPS", "FDX", "CAT", "DE", "BA", "LMT", "RTX", "GD", "NOC",
            "GE", "HON", "MMM", "EMR", "ITW", "ETN", "PH", "ROK", "AME",
            "GNRC", "XYL", "IR", "FAST", "GWW", "CDNS", "SNPS", "ANSS",
            "ADSK", "INTU", "WDAY", "VEEV", "TEAM", "HUBS"
        ][:50]  # Limit to 50 for reasonable test time
        
        large_request = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": large_symbols,
            "filters": {
                "volume": {
                    "min_average": 1000000
                },
                "price_change": {
                    "min_change": -5.0,
                    "max_change": 10.0,
                    "period_days": 1
                }
            }
        }
        
        print(f"Testing with {len(large_symbols)} symbols...")
        start_time = time.time()
        
        try:
            response = await client.post(
                f"{base_url}/screen",
                json=large_request
            )
            
            elapsed_time = time.time() - start_time
            
            if response.status_code == 200:
                result = response.json()
                print(f"✓ Success in {elapsed_time:.2f} seconds")
                print(f"  Total symbols screened: {result['total_symbols_screened']}")
                print(f"  Qualifying stocks: {result['total_qualifying_stocks']}")
                print(f"  API execution time: {result['execution_time_ms']:.2f}ms")
                print(f"  Average time per symbol: {result['execution_time_ms']/len(large_symbols):.2f}ms")
                
                # Calculate throughput
                symbols_per_second = len(large_symbols) / (result['execution_time_ms'] / 1000)
                print(f"  Throughput: {symbols_per_second:.1f} symbols/second")
                
        except Exception as e:
            print(f"✗ Error: {str(e)}")


if __name__ == "__main__":
    print("Stock Screener Comprehensive Testing")
    print("Make sure the API is running on http://localhost:8080")
    print("\nStarting tests...\n")
    
    asyncio.run(test_comprehensive_screening())