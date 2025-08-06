#!/usr/bin/env python3
"""
Simple test script for the stock screener using urllib.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, Any


def make_request(url: str, method: str = "GET", data: Dict = None, headers: Dict = None) -> tuple:
    """Make HTTP request and return (status, headers, body)."""
    if headers is None:
        headers = {}
    
    request = urllib.request.Request(url, method=method)
    
    # Add headers
    for key, value in headers.items():
        request.add_header(key, value)
    
    # Add data if POST
    if data and method == "POST":
        request.data = json.dumps(data).encode('utf-8')
        request.add_header('Content-Type', 'application/json')
    
    try:
        response = urllib.request.urlopen(request)
        return response.status, dict(response.headers), response.read().decode('utf-8')
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read().decode('utf-8')
    except Exception as e:
        return None, None, str(e)


def test_server_health():
    """Test if server is running."""
    print("\n1. Testing Server Health...")
    status, headers, body = make_request("http://localhost:8000/")
    
    if status == 200:
        data = json.loads(body)
        print("✓ Server is healthy")
        print(f"  - Name: {data.get('name')}")
        print(f"  - Version: {data.get('version')}")
        print(f"  - Status: {data.get('status')}")
        return True
    else:
        print(f"✗ Server health check failed: {status}")
        return False


def test_cors_headers():
    """Test CORS configuration."""
    print("\n2. Testing CORS Headers...")
    
    test_origins = [
        "http://localhost:5173",
        "http://34.125.88.131",
        "https://example.com"
    ]
    
    all_passed = True
    
    for origin in test_origins:
        headers = {"Origin": origin}
        status, response_headers, body = make_request(
            "http://localhost:8000/api/v1/screen",
            method="OPTIONS",
            headers=headers
        )
        
        cors_origin = response_headers.get('access-control-allow-origin', 'NOT SET')
        cors_methods = response_headers.get('access-control-allow-methods', 'NOT SET')
        cors_headers = response_headers.get('access-control-allow-headers', 'NOT SET')
        
        allowed = cors_origin in ['*', origin]
        
        print(f"\n  Origin: {origin}")
        print(f"    - Status: {status}")
        print(f"    - Allow-Origin: {cors_origin} {'✓' if allowed else '✗'}")
        print(f"    - Allow-Methods: {cors_methods}")
        print(f"    - Allow-Headers: {cors_headers}")
        
        if not allowed:
            all_passed = False
    
    return all_passed


def test_valid_request():
    """Test valid screen request."""
    print("\n3. Testing Valid Screen Request...")
    
    request_data = {
        "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "symbols": ["AAPL", "MSFT", "GOOGL"],
        "filters": {
            "volume": {"min_average": 1000000},
            "price_change": {"min_change": -5, "max_change": 10},
            "moving_average": {"period": 20, "condition": "above"}
        }
    }
    
    status, headers, body = make_request(
        "http://localhost:8000/api/v1/screen",
        method="POST",
        data=request_data
    )
    
    if status == 200:
        data = json.loads(body)
        print("✓ Valid request processed successfully")
        print(f"  - Total results: {data.get('total_results', 0)}")
        print(f"  - Response has 'results': {'results' in data}")
        print(f"  - Response has 'filters_applied': {'filters_applied' in data}")
        print(f"  - Response has 'date_range': {'date_range' in data}")
        
        if data.get('results'):
            first_result = data['results'][0]
            print(f"\n  First result structure:")
            print(f"    - Has 'symbol': {'symbol' in first_result}")
            print(f"    - Has 'qualifying_dates': {'qualifying_dates' in first_result}")
            print(f"    - Has 'metrics': {'metrics' in first_result}")
            
            if 'metrics' in first_result:
                metrics = first_result['metrics']
                print(f"    - Metrics has 'average_price': {'average_price' in metrics}")
                print(f"    - Metrics has 'average_volume': {'average_volume' in metrics}")
        
        return True
    else:
        print(f"✗ Valid request failed with status: {status}")
        print(f"  - Response: {body[:200]}...")
        return False


def test_invalid_requests():
    """Test invalid request handling."""
    print("\n4. Testing Invalid Request Handling...")
    
    test_cases = [
        {
            "name": "Missing required fields",
            "data": {"filters": {"volume": {"min_average": 1000000}}}
        },
        {
            "name": "Invalid filter field",
            "data": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "filters": {"price_range": {"minimum": 50}}
            }
        },
        {
            "name": "Invalid date format",
            "data": {
                "start_date": "2024/01/01",
                "end_date": "2024/01/31",
                "filters": {}
            }
        }
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        status, headers, body = make_request(
            "http://localhost:8000/api/v1/screen",
            method="POST",
            data=test_case["data"]
        )
        
        # We expect 400 or 422 for validation errors
        handled_correctly = status in [400, 422]
        
        print(f"\n  Test: {test_case['name']}")
        print(f"    - Status: {status} {'✓' if handled_correctly else '✗'}")
        if not handled_correctly:
            print(f"    - Expected 400 or 422, got {status}")
            all_passed = False
    
    return all_passed


def test_public_ip_simulation():
    """Test public IP access simulation."""
    print("\n5. Testing Public IP Access Simulation...")
    
    headers = {
        "Origin": "http://34.125.88.131",
        "X-Forwarded-For": "34.125.88.131"
    }
    
    status, response_headers, body = make_request(
        "http://localhost:8000/",
        headers=headers
    )
    
    cors_origin = response_headers.get('access-control-allow-origin', 'NOT SET')
    allows_public = cors_origin in ['*', 'http://34.125.88.131']
    
    print(f"  - Status: {status}")
    print(f"  - CORS Allow-Origin: {cors_origin}")
    print(f"  - Allows public IP: {'✓' if allows_public else '✗'}")
    
    return status == 200 and allows_public


def test_minimal_request():
    """Test minimal valid request."""
    print("\n6. Testing Minimal Request (With minimal filters)...")
    
    request_data = {
        "start_date": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "filters": {
            "volume": {"min_average": 0}  # At least one filter is required
        }
    }
    
    status, headers, body = make_request(
        "http://localhost:8000/api/v1/screen",
        method="POST",
        data=request_data
    )
    
    if status == 200:
        data = json.loads(body)
        print("✓ Minimal request processed successfully")
        print(f"  - Total results: {data.get('total_results', 0)}")
        print(f"  - Uses default symbols: {len(data.get('results', [])) > 0}")
        return True
    else:
        print(f"✗ Minimal request failed with status: {status}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("STOCK SCREENER API TEST SUITE")
    print("="*60)
    print(f"Testing server at: http://localhost:8000")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run tests
    tests = [
        ("Server Health", test_server_health),
        ("CORS Headers", test_cors_headers),
        ("Valid Request", test_valid_request),
        ("Invalid Requests", test_invalid_requests),
        ("Public IP Access", test_public_ip_simulation),
        ("Minimal Request", test_minimal_request)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            passed = test_func()
            results.append((test_name, passed))
        except Exception as e:
            print(f"\n✗ {test_name} failed with exception: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    total = len(results)
    passed = sum(1 for _, p in results if p)
    
    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")
    
    if passed < total:
        print("\nFailed Tests:")
        for name, passed in results:
            if not passed:
                print(f"  - {name}")
    
    print("="*60)
    
    return passed == total


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)