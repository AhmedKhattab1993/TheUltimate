#!/usr/bin/env python3
"""
Test API structure without making actual Polygon API calls.
"""

import json
import urllib.request
import urllib.error
from datetime import datetime, timedelta


def make_request(url: str, method: str = "GET", data: dict = None, headers: dict = None) -> tuple:
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


def main():
    """Run API structure tests."""
    print("="*60)
    print("STOCK SCREENER API STRUCTURE TEST")
    print("="*60)
    print(f"Testing server at: http://localhost:8000")
    print(f"Test started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test 1: Server Health
    print("\n1. Server Health Check...")
    status, headers, body = make_request("http://localhost:8000/")
    if status == 200:
        data = json.loads(body)
        print("✓ Server is healthy")
        print(f"  - Name: {data.get('name')}")
        print(f"  - Version: {data.get('version')}")
        print(f"  - Available endpoints: {', '.join(data.get('endpoints', {}).keys())}")
    else:
        print(f"✗ Server health check failed: {status}")
    
    # Test 2: CORS Headers from different origins
    print("\n2. CORS Configuration Test...")
    test_origins = ["http://localhost:5173", "http://34.125.88.131", "https://example.com"]
    
    for origin in test_origins:
        headers = {"Origin": origin}
        status, response_headers, _ = make_request(
            "http://localhost:8000/api/v1/screen",
            method="OPTIONS",
            headers=headers
        )
        
        cors_origin = response_headers.get('access-control-allow-origin', 'NOT SET')
        print(f"  Origin {origin}: {cors_origin} {'✓' if cors_origin in ['*', origin] else '✗'}")
    
    # Test 3: Get available filters
    print("\n3. Available Filters...")
    status, _, body = make_request("http://localhost:8000/api/v1/filters")
    if status == 200:
        filters = json.loads(body)
        print("✓ Retrieved filter definitions")
        for filter_name, filter_info in filters.items():
            print(f"  - {filter_name}: {filter_info.get('description', 'No description')}")
    else:
        print(f"✗ Failed to get filters: {status}")
    
    # Test 4: Get available symbols
    print("\n4. Available Symbols...")
    status, _, body = make_request("http://localhost:8000/api/v1/symbols")
    if status == 200:
        symbols = json.loads(body)
        print(f"✓ Retrieved {len(symbols)} symbols")
        print(f"  - First 5: {', '.join(symbols[:5])}")
    else:
        print(f"✗ Failed to get symbols: {status}")
    
    # Test 5: Request validation (without actual API call)
    print("\n5. Request Format Validation...")
    
    # Valid structure but would trigger API call
    valid_request = {
        "start_date": (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        "end_date": datetime.now().strftime("%Y-%m-%d"),
        "symbols": ["AAPL"],
        "filters": {
            "volume": {"min_average": 1000000}
        }
    }
    
    # Invalid structure tests
    invalid_requests = [
        {
            "name": "Missing dates",
            "data": {"filters": {"volume": {"min_average": 1000000}}}
        },
        {
            "name": "Wrong date format",
            "data": {
                "start_date": "2024/01/01",
                "end_date": "2024/01/31",
                "filters": {"volume": {"min_average": 1000000}}
            }
        },
        {
            "name": "Invalid filter",
            "data": {
                "start_date": "2024-01-01",
                "end_date": "2024-01-31",
                "filters": {"invalid_filter": {"value": 100}}
            }
        }
    ]
    
    print("  Testing invalid request handling:")
    for test_case in invalid_requests:
        status, _, body = make_request(
            "http://localhost:8000/api/v1/screen",
            method="POST",
            data=test_case["data"]
        )
        expected = status in [400, 422]
        print(f"    - {test_case['name']}: Status {status} {'✓' if expected else '✗'}")
    
    # Test 6: API documentation
    print("\n6. API Documentation...")
    status, _, _ = make_request("http://localhost:8000/docs")
    print(f"  - Swagger UI: {'✓ Available' if status == 200 else '✗ Not available'}")
    
    status, _, _ = make_request("http://localhost:8000/redoc")
    print(f"  - ReDoc: {'✓ Available' if status == 200 else '✗ Not available'}")
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print("All API structure tests completed.")
    print("Note: Actual screening tests skipped to avoid rate limits.")
    print("="*60)


if __name__ == "__main__":
    main()