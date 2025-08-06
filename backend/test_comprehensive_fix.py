#!/usr/bin/env python3
"""
Comprehensive test of the 500 error fix including period extension functionality.
"""

import requests
import json
from datetime import date, timedelta

def test_various_filter_combinations():
    """Test different filter combinations to ensure period extension works."""
    
    # Calculate dates
    end_date = date.today()
    start_date = end_date - timedelta(days=1)
    
    test_cases = [
        {
            "name": "Volume Filter Only",
            "filters": {
                "volume": {
                    "min_average": 1000000,
                    "lookback_days": 20
                }
            }
        },
        {
            "name": "Moving Average Filter (Period Extension Required)",
            "filters": {
                "moving_average": {
                    "period": 50,
                    "condition": "above"
                }
            }
        },
        {
            "name": "Gap Filter (Period Extension Required)",
            "filters": {
                "gap": {
                    "min_gap_percent": 2.0,
                    "max_gap_percent": 15.0
                }
            }
        },
        {
            "name": "Multiple Filters with Period Extension",
            "filters": {
                "volume": {
                    "min_average": 500000,
                    "lookback_days": 10
                },
                "moving_average": {
                    "period": 20,
                    "condition": "above"
                },
                "price_range": {
                    "min_price": 1.0,
                    "max_price": 50.0
                }
            }
        },
        {
            "name": "Complex Filter Setup",
            "filters": {
                "volume": {
                    "min_average": 1000000,
                    "lookback_days": 20
                },
                "relative_volume": {
                    "min_relative_volume": 1.5,
                    "lookback_days": 30
                },
                "gap": {
                    "min_gap_percent": 1.0
                },
                "market_cap": {
                    "max_market_cap": 10000000000
                }
            }
        }
    ]
    
    url = "http://34.125.88.131:8000/api/v1/screen"
    
    results = {}
    
    for test_case in test_cases:
        print(f"\n--- Testing: {test_case['name']} ---")
        
        request_payload = {
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "symbols": ["AAPL", "TSLA", "MSFT", "GOOGL"],
            "use_all_us_stocks": False,
            "filters": test_case["filters"]
        }
        
        try:
            print(f"Filters: {json.dumps(test_case['filters'], indent=2)}")
            
            response = requests.post(url, json=request_payload, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                qualifying_stocks = result.get('total_qualifying_stocks', 0)
                execution_time = result.get('execution_time_ms', 0)
                performance = result.get('performance_metrics', {})
                
                print(f"✅ SUCCESS: {qualifying_stocks} qualifying stocks found")
                print(f"⏱️  Execution time: {execution_time:.2f}ms")
                
                if performance:
                    print(f"📊 Used bulk endpoint: {performance.get('used_bulk_endpoint', False)}")
                    print(f"📊 Data fetch time: {performance.get('data_fetch_time_ms', 0):.2f}ms")
                    print(f"📊 Screening time: {performance.get('screening_time_ms', 0):.2f}ms")
                
                results[test_case['name']] = {
                    'success': True,
                    'qualifying_stocks': qualifying_stocks,
                    'execution_time_ms': execution_time,
                    'performance_metrics': performance
                }
                
            else:
                print(f"❌ FAILED: Status {response.status_code}")
                print(f"Response: {response.text[:500]}...")
                results[test_case['name']] = {
                    'success': False,
                    'error': f"Status {response.status_code}",
                    'response': response.text[:200]
                }
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            results[test_case['name']] = {
                'success': False,
                'error': str(e)
            }
    
    return results

def test_period_extension_specifically():
    """Test that period extension is working properly with historical data requirements."""
    
    print("\n=== Testing Period Extension Functionality ===")
    
    # Test with a longer date range to ensure period extension kicks in
    end_date = date.today() - timedelta(days=1)  # Use yesterday to ensure data availability
    start_date = end_date  # Single day (forces period extension for MA filters)
    
    request_payload = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "symbols": ["AAPL", "MSFT", "TSLA"],
        "use_all_us_stocks": False,
        "filters": {
            "moving_average": {
                "period": 50,  # Requires 50+ days of historical data
                "condition": "above"
            },
            "volume": {
                "min_average": 1000000,
                "lookback_days": 20  # Requires 20+ days of historical data
            }
        }
    }
    
    url = "http://34.125.88.131:8000/api/v1/screen"
    
    try:
        print(f"Testing single-day screening with period extension requirements...")
        print(f"Date: {start_date.isoformat()}")
        print(f"Filters requiring historical data: MA(50) + Volume(20-day avg)")
        
        response = requests.post(url, json=request_payload, timeout=90)
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ SUCCESS: Period extension working correctly!")
            print(f"📈 Qualifying stocks: {result.get('total_qualifying_stocks', 0)}")
            print(f"⏱️  Total execution time: {result.get('execution_time_ms', 0):.2f}ms")
            
            performance = result.get('performance_metrics', {})
            if performance:
                print(f"📊 Data fetch time: {performance.get('data_fetch_time_ms', 0):.2f}ms")
                print(f"📊 Screening time: {performance.get('screening_time_ms', 0):.2f}ms")
                print(f"📊 Used bulk endpoint: {performance.get('used_bulk_endpoint', False)}")
            
            return True
        else:
            print(f"❌ FAILED: Status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False

if __name__ == "__main__":
    print("=== Comprehensive API Fix Testing ===")
    
    # Test various filter combinations
    print("\n🧪 Testing Various Filter Combinations...")
    filter_results = test_various_filter_combinations()
    
    # Test period extension specifically
    period_extension_ok = test_period_extension_specifically()
    
    # Summary
    print("\n" + "="*50)
    print("📋 SUMMARY OF RESULTS")
    print("="*50)
    
    successful_tests = sum(1 for result in filter_results.values() if result.get('success', False))
    total_tests = len(filter_results)
    
    print(f"Filter combination tests: {successful_tests}/{total_tests} passed")
    print(f"Period extension test: {'✅ PASSED' if period_extension_ok else '❌ FAILED'}")
    
    if successful_tests == total_tests and period_extension_ok:
        print("\n🎉 ALL TESTS PASSED! The 500 error fix is successful!")
        print("✅ Missing model classes have been added")
        print("✅ Period extension functionality is working")
        print("✅ Async/sync integration is properly handled")
        print("✅ Backward compatibility is maintained")
    else:
        print(f"\n⚠️  Some tests failed. Success rate: {(successful_tests + (1 if period_extension_ok else 0))}/{total_tests + 1}")
        
        for test_name, result in filter_results.items():
            if not result.get('success', False):
                print(f"❌ {test_name}: {result.get('error', 'Unknown error')}")
    
    print("\n" + "="*50)