#!/usr/bin/env python3
"""
Integration test for day trading filters.
"""

import asyncio
import httpx
from datetime import date, timedelta
import json
import time


async def test_health_check():
    """Test API health endpoint."""
    print("\n=== Testing Health Check ===")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/api/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        print("✓ Health check passed")
        return data


async def test_filters_endpoint():
    """Test filters endpoint."""
    print("\n=== Testing Filters Endpoint ===")
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/api/v1/filters")
        assert response.status_code == 200
        data = response.json()
        
        # Check new day trading filters exist
        required_filters = [
            "gap", "price_range", "relative_volume", "float",
            "premarket_volume", "market_cap", "news_catalyst"
        ]
        
        for filter_name in required_filters:
            assert filter_name in data, f"Missing filter: {filter_name}"
            print(f"✓ Found filter: {filter_name}")
        
        return data


async def test_screening_with_day_trading_filters():
    """Test screening with various day trading filter combinations."""
    print("\n=== Testing Screening with Day Trading Filters ===")
    
    # Test data
    end_date = date.today() - timedelta(days=5)  # Use recent historical data
    start_date = end_date - timedelta(days=60)  # 60 days of data
    
    test_cases = [
        {
            "name": "Gap Filter Only",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": ["AAPL", "TSLA", "NVDA", "AMD", "MSFT"],
                "filters": {
                    "gap": {
                        "min_gap_percent": 2.0,
                        "max_gap_percent": 10.0
                    }
                }
            }
        },
        {
            "name": "Price Range + Relative Volume",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": ["AAPL", "TSLA", "NVDA", "AMD", "MSFT"],
                "filters": {
                    "price_range": {
                        "min_price": 50.0,
                        "max_price": 500.0
                    },
                    "relative_volume": {
                        "min_relative_volume": 1.5,
                        "lookback_days": 20
                    }
                }
            }
        },
        {
            "name": "Complete Day Trading Setup",
            "request": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "symbols": ["AAPL", "TSLA", "NVDA", "AMD", "MSFT", "META", "GOOGL"],
                "filters": {
                    "gap": {
                        "min_gap_percent": 2.0
                    },
                    "price_range": {
                        "min_price": 20.0,
                        "max_price": 1000.0
                    },
                    "relative_volume": {
                        "min_relative_volume": 1.2,
                        "lookback_days": 10
                    },
                    "float": {
                        "max_float": 500000000
                    },
                    "market_cap": {
                        "max_market_cap": 5000000000
                    }
                }
            }
        }
    ]
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        for test_case in test_cases:
            print(f"\n--- {test_case['name']} ---")
            start_time = time.time()
            
            response = await client.post(
                "http://localhost:8080/api/v1/screen",
                json=test_case["request"]
            )
            
            assert response.status_code == 200, f"Failed with status {response.status_code}: {response.text}"
            data = response.json()
            
            execution_time = time.time() - start_time
            
            print(f"Total symbols screened: {data['total_symbols_screened']}")
            print(f"Qualifying stocks: {data['total_qualifying_stocks']}")
            print(f"API execution time: {data['execution_time_ms']:.2f}ms")
            print(f"Total request time: {execution_time*1000:.2f}ms")
            
            if data['results']:
                print("\nQualifying Stocks:")
                for result in data['results'][:5]:  # Show first 5
                    print(f"  - {result['symbol']}:")
                    if 'gap_days_count' in result['metrics']:
                        print(f"    Gap days: {result['metrics']['gap_days_count']}")
                    if 'relative_volume_max' in result['metrics']:
                        print(f"    Max rel volume: {result['metrics']['relative_volume_max']:.2f}x")
            
            print(f"✓ {test_case['name']} passed")


async def test_performance():
    """Test performance with larger datasets."""
    print("\n=== Testing Performance ===")
    
    end_date = date.today() - timedelta(days=5)
    start_date = end_date - timedelta(days=90)  # 90 days of data
    
    # Test with more symbols
    large_symbol_set = [
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "AMD",
        "INTC", "NFLX", "DIS", "BA", "GS", "JPM", "BAC", "WMT",
        "HD", "MCD", "KO", "PEP", "NKE", "SBUX", "F", "GM"
    ]
    
    request = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "symbols": large_symbol_set,
        "filters": {
            "gap": {"min_gap_percent": 1.5},
            "relative_volume": {"min_relative_volume": 1.5}
        }
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        start_time = time.time()
        response = await client.post(
            "http://localhost:8080/api/v1/screen",
            json=request
        )
        total_time = time.time() - start_time
        
        assert response.status_code == 200
        data = response.json()
        
        print(f"Symbols: {len(large_symbol_set)}")
        print(f"Date range: {(end_date - start_date).days} days")
        print(f"Total data points: ~{len(large_symbol_set) * (end_date - start_date).days}")
        print(f"API execution time: {data['execution_time_ms']:.2f}ms")
        print(f"Total request time: {total_time*1000:.2f}ms")
        print(f"✓ Performance test passed")


async def test_validation():
    """Test input validation for new filters."""
    print("\n=== Testing Input Validation ===")
    
    invalid_requests = [
        {
            "name": "Invalid gap percentage",
            "request": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "symbols": ["AAPL"],
                "filters": {
                    "gap": {"min_gap_percent": -5.0}  # Negative gap
                }
            }
        },
        {
            "name": "Invalid price range",
            "request": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "symbols": ["AAPL"],
                "filters": {
                    "price_range": {
                        "min_price": 100.0,
                        "max_price": 50.0  # Max < Min
                    }
                }
            }
        },
        {
            "name": "Invalid relative volume",
            "request": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "symbols": ["AAPL"],
                "filters": {
                    "relative_volume": {
                        "min_relative_volume": 0.5  # Less than 1.0
                    }
                }
            }
        }
    ]
    
    async with httpx.AsyncClient() as client:
        for test_case in invalid_requests:
            print(f"\n--- {test_case['name']} ---")
            response = await client.post(
                "http://localhost:8080/api/v1/screen",
                json=test_case["request"]
            )
            
            # Should return 400 or 422 for validation errors
            assert response.status_code in [400, 422], f"Expected validation error, got {response.status_code}"
            print(f"✓ Validation correctly rejected: {test_case['name']}")


async def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Starting Integration Tests for Day Trading Filters")
    print("=" * 60)
    
    try:
        # Test endpoints
        await test_health_check()
        await test_filters_endpoint()
        
        # Test screening functionality
        await test_screening_with_day_trading_filters()
        
        # Test performance
        await test_performance()
        
        # Test validation
        await test_validation()
        
        print("\n" + "=" * 60)
        print("✅ ALL INTEGRATION TESTS PASSED!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())