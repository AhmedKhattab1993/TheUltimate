#!/usr/bin/env python3
"""Test script for the new Results API endpoints."""

import requests
import json
from datetime import datetime, date

BASE_URL = "http://localhost:8000"

def test_screener_results_endpoints():
    """Test screener results API endpoints."""
    print("Testing Screener Results API...")
    
    # Test listing screener results
    print("\n1. Testing GET /api/v2/screener/results")
    response = requests.get(f"{BASE_URL}/api/v2/screener/results")
    print(f"Status: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Total results: {data.get('total_count', 0)}")
        print(f"Page: {data.get('page', 1)}/{data.get('total_pages', 1)}")
        if data.get('results'):
            print(f"First result ID: {data['results'][0]['id']}")
            # Test getting details of first result
            result_id = data['results'][0]['id']
            print(f"\n2. Testing GET /api/v2/screener/results/{result_id}")
            detail_response = requests.get(f"{BASE_URL}/api/v2/screener/results/{result_id}")
            print(f"Status: {detail_response.status_code}")
            if detail_response.ok:
                detail_data = detail_response.json()
                print(f"Symbol count: {detail_data.get('symbol_count', 0)}")
                print(f"Filters: {list(detail_data.get('filters', {}).keys())}")
    else:
        print(f"Error: {response.text}")
    
    # Test with pagination
    print("\n3. Testing pagination")
    response = requests.get(f"{BASE_URL}/api/v2/screener/results?page=1&page_size=5")
    print(f"Status: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Results on page: {len(data.get('results', []))}")
    
    # Test with date filter
    print("\n4. Testing date filter")
    today = date.today().isoformat()
    response = requests.get(f"{BASE_URL}/api/v2/screener/results?start_date={today}")
    print(f"Status: {response.status_code}")
    if response.ok:
        data = response.json()
        print(f"Results after {today}: {data.get('total_count', 0)}")


def test_backtest_results_pagination():
    """Test backtest results pagination."""
    print("\n\nTesting Backtest Results Pagination...")
    
    # Test with different page sizes
    for page_size in [5, 10, 20]:
        print(f"\n- Testing page_size={page_size}")
        response = requests.get(f"{BASE_URL}/api/v2/backtest/results?page=1&page_size={page_size}")
        print(f"  Status: {response.status_code}")
        if response.ok:
            data = response.json()
            print(f"  Results returned: {len(data.get('results', []))}")
            print(f"  Total count: {data.get('total_count', 0)}")


if __name__ == "__main__":
    print("="*50)
    print("Testing Results API Endpoints")
    print("="*50)
    
    test_screener_results_endpoints()
    test_backtest_results_pagination()
    
    print("\n" + "="*50)
    print("Test completed!")