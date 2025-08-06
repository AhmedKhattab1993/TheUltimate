#!/usr/bin/env python3
"""
Integration test for stock screener with all US stocks capability.
Tests the API endpoints and request/response formats.
"""
import requests
import json
from datetime import datetime, timedelta

# API base URL
API_URL = "http://localhost:8000/api/v1"

def test_health_check():
    """Test health check endpoint."""
    print("Testing health check...")
    response = requests.get(f"{API_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["healthy", "degraded"]
    print("✓ Health check passed")
    return True

def test_get_us_stocks_endpoint():
    """Test fetching all US stocks endpoint."""
    print("\nTesting US stocks endpoint...")
    response = requests.get(f"{API_URL}/symbols/us-stocks")
    assert response.status_code == 200
    stocks = response.json()
    assert isinstance(stocks, list)
    print(f"✓ US stocks endpoint returned {len(stocks)} symbols")
    return True

def test_screen_with_specific_symbols():
    """Test screening with specific symbols."""
    print("\nTesting screening with specific symbols...")
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)
    
    request_data = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "use_all_us_stocks": False,
        "filters": {
            "volume": {
                "min_average": 1000000
            }
        }
    }
    
    print(f"Request payload: {json.dumps(request_data, indent=2)}")
    
    response = requests.post(f"{API_URL}/screen", json=request_data)
    assert response.status_code == 200
    data = response.json()
    
    assert "total_symbols_screened" in data
    assert data["total_symbols_screened"] == 3
    assert "results" in data
    print(f"✓ Screening with specific symbols passed. Found {data['total_qualifying_stocks']} qualifying stocks")
    return True

def test_screen_with_all_us_stocks():
    """Test screening with all US stocks."""
    print("\nTesting screening with all US stocks...")
    
    # Use a very short date range to avoid timeout in test
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    request_data = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "use_all_us_stocks": True,
        "filters": {
            "volume": {
                "min_average": 10000000  # High volume filter to reduce results
            },
            "price_change": {
                "min_change": 5.0  # Significant price change to further filter
            }
        }
    }
    
    print(f"Request payload: {json.dumps(request_data, indent=2)}")
    print("Note: This test uses strict filters to avoid long processing time")
    
    response = requests.post(f"{API_URL}/screen", json=request_data, timeout=120)
    assert response.status_code == 200
    data = response.json()
    
    assert "total_symbols_screened" in data
    assert data["total_symbols_screened"] > 1000  # Should be screening many symbols
    assert "results" in data
    assert "execution_time_ms" in data
    print(f"✓ Screening with all US stocks passed")
    print(f"  - Screened {data['total_symbols_screened']} symbols")
    print(f"  - Found {data['total_qualifying_stocks']} qualifying stocks")
    print(f"  - Execution time: {data['execution_time_ms']/1000:.2f} seconds")
    return True

def test_validation_error():
    """Test that API properly validates conflicting parameters."""
    print("\nTesting validation error handling...")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    # Try to send both symbols and use_all_us_stocks=True
    request_data = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "symbols": ["AAPL", "MSFT"],
        "use_all_us_stocks": True,
        "filters": {
            "volume": {
                "min_average": 1000000
            }
        }
    }
    
    response = requests.post(f"{API_URL}/screen", json=request_data)
    assert response.status_code == 422  # Validation error
    print("✓ Validation error properly handled")
    return True

def main():
    """Run all integration tests."""
    print("=" * 60)
    print("Stock Screener Integration Tests")
    print("=" * 60)
    
    tests = [
        test_health_check,
        test_get_us_stocks_endpoint,
        test_screen_with_specific_symbols,
        test_screen_with_all_us_stocks,
        test_validation_error
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ {test.__name__} failed: {str(e)}")
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"Tests completed: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0

if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)