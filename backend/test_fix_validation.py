#!/usr/bin/env python3
"""
Test script to validate the 500 error fix for missing model classes.
"""

import requests
import json
from datetime import date, timedelta

def test_api_endpoint(port=8000):
    """Test the screening endpoint with a simple request."""
    
    # Calculate dates
    end_date = date.today()
    start_date = end_date - timedelta(days=1)
    
    # Simple test request with minimal filters
    test_request = {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "symbols": ["AAPL", "TSLA"],
        "use_all_us_stocks": False,
        "filters": {
            "volume": {
                "min_average": 1000000,
                "lookback_days": 20
            }
        }
    }
    
    url = f"http://34.125.88.131:{port}/api/v1/screen"
    
    try:
        print(f"Testing endpoint: {url}")
        print(f"Request payload: {json.dumps(test_request, indent=2)}")
        
        response = requests.post(url, json=test_request, timeout=30)
        
        print(f"Response status: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Endpoint responded with 200 OK")
            result = response.json()
            print(f"Found {result.get('total_qualifying_stocks', 0)} qualifying stocks")
            return True
        else:
            print(f"ERROR: Got status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except Exception as e:
        print(f"ERROR: Request failed: {e}")
        return False

def test_health_endpoint(port=8000):
    """Test the health endpoint to ensure server is responsive."""
    
    url = f"http://34.125.88.131:{port}/api/v1/health"
    
    try:
        print(f"Testing health endpoint: {url}")
        response = requests.get(url, timeout=10)
        
        print(f"Health status: {response.status_code}")
        
        if response.status_code == 200:
            print("SUCCESS: Health endpoint OK")
            return True
        else:
            print(f"ERROR: Health endpoint returned {response.status_code}")
            return False
            
    except Exception as e:
        print(f"ERROR: Health check failed: {e}")
        return False

if __name__ == "__main__":
    print("=== Testing API Fix Validation ===")
    
    # Test port 8000 (the problematic one)
    print("\n--- Testing Port 8000 (Main Server) ---")
    health_ok = test_health_endpoint(8000)
    if health_ok:
        screen_ok = test_api_endpoint(8000)
        if screen_ok:
            print("\n✅ SUCCESS: Port 8000 is working correctly!")
        else:
            print("\n❌ FAILED: Port 8000 health OK but screening failed")
    else:
        print("\n❌ FAILED: Port 8000 health check failed")
    
    # Also test port 8001 for comparison
    print("\n--- Testing Port 8001 (Comparison) ---")
    health_ok_8001 = test_health_endpoint(8001)
    if health_ok_8001:
        screen_ok_8001 = test_api_endpoint(8001)
        if screen_ok_8001:
            print("\n✅ Port 8001 is working correctly!")
        else:
            print("\n❌ Port 8001 health OK but screening failed")
    else:
        print("\n⚠️  Port 8001 not responding (expected if not running)")