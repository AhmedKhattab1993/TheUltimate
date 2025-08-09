#!/usr/bin/env python3
"""Test gap filter API with specific stocks."""

import requests
import json

# Test with specific stocks first
url = "http://localhost:8000/api/v2/simple-screener/screen"

# Test 1: Gap filter only
payload1 = {
    "start_date": "2025-07-10",
    "end_date": "2025-08-09",
    "use_all_us_stocks": True,
    "filters": {
        "gap": {
            "gap_threshold": 2.0,
            "direction": "both"
        }
    }
}

print("Test 1: Gap filter (2%) only...")
try:
    response = requests.post(url, json=payload1, timeout=120)
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"Total stocks screened: {data.get('total_symbols_screened', 0)}")
    print(f"Qualifying stocks: {data.get('total_qualifying_stocks', 0)}")
    print(f"Execution time: {data.get('execution_time_ms', 0)}ms")
    
    if data.get('results'):
        print("\nFirst 5 results:")
        for i, result in enumerate(data['results'][:5]):
            print(f"  {result['symbol']}: {len(result['qualifying_dates'])} qualifying days")
except Exception as e:
    print(f"Error: {e}")

# Test 2: Gap filter with looser threshold
print("\n\nTest 2: Gap filter (1%) - looser threshold...")
payload2 = {
    "start_date": "2025-07-10", 
    "end_date": "2025-08-09",
    "use_all_us_stocks": True,
    "filters": {
        "gap": {
            "gap_threshold": 1.0,
            "direction": "both"
        }
    }
}

try:
    response = requests.post(url, json=payload2, timeout=120)
    data = response.json()
    print(f"Status: {response.status_code}")
    print(f"Total stocks screened: {data.get('total_symbols_screened', 0)}")
    print(f"Qualifying stocks: {data.get('total_qualifying_stocks', 0)}")
    print(f"Execution time: {data.get('execution_time_ms', 0)}ms")
    
    if data.get('results'):
        print("\nFirst 5 results:")
        for i, result in enumerate(data['results'][:5]):
            print(f"  {result['symbol']}: {len(result['qualifying_dates'])} qualifying days")
except Exception as e:
    print(f"Error: {e}")