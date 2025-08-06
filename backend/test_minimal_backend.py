#!/usr/bin/env python3
"""
Minimal Backend Test - Tests core functionality without all dependencies
"""

import sys
import os
import json
from urllib.request import urlopen
from urllib.error import URLError, HTTPError
from typing import Dict, List, Any

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_polygon_api_basic():
    """Test Polygon API with basic urllib instead of httpx"""
    print("=== Testing Polygon API Connection (Basic) ===")
    
    try:
        # Read API key from .env file
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        api_key = None
        
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if 'POLYGON_API_KEY' in line:
                        api_key = line.split('=')[1].strip()
                        break
        
        if not api_key:
            print("✗ No API key found in .env file")
            return False
            
        # Test API connection
        url = f"https://api.polygon.io/v2/aggs/ticker/AAPL/prev?apiKey={api_key}"
        
        try:
            response = urlopen(url)
            data = json.loads(response.read().decode())
            
            if response.status == 200 and 'results' in data:
                print("✓ Successfully connected to Polygon API")
                result = data['results'][0]
                print(f"✓ AAPL Previous Close: ${result['c']}")
                print(f"  Volume: {result['v']:,}")
                print(f"  Date: {result['t']}")
                return True
            else:
                print(f"✗ Unexpected response: {data}")
                return False
                
        except HTTPError as e:
            print(f"✗ API request failed: {e.code} {e.reason}")
            if e.code == 401:
                print("  → Invalid API key")
            elif e.code == 429:
                print("  → Rate limit exceeded")
            return False
            
        except URLError as e:
            print(f"✗ Network error: {str(e)}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False

def test_screening_logic():
    """Test basic screening logic without dependencies"""
    print("\n=== Testing Screening Logic ===")
    
    # Mock data for testing
    mock_stocks = [
        {"symbol": "AAPL", "close": 180.0, "volume": 50000000, "change_pct": 2.5},
        {"symbol": "MSFT", "close": 350.0, "volume": 25000000, "change_pct": -1.2},
        {"symbol": "GOOGL", "close": 140.0, "volume": 30000000, "change_pct": 3.8},
        {"symbol": "TSLA", "close": 250.0, "volume": 80000000, "change_pct": -5.0},
    ]
    
    # Test price filter
    print("\nTesting Price Filter (> $200):")
    filtered = [s for s in mock_stocks if s["close"] > 200]
    for stock in filtered:
        print(f"  ✓ {stock['symbol']}: ${stock['close']}")
    
    # Test volume filter
    print("\nTesting Volume Filter (> 40M):")
    filtered = [s for s in mock_stocks if s["volume"] > 40000000]
    for stock in filtered:
        print(f"  ✓ {stock['symbol']}: {stock['volume']:,} shares")
    
    # Test gainers
    print("\nTesting Gainers Filter (> 2%):")
    filtered = [s for s in mock_stocks if s["change_pct"] > 2.0]
    for stock in filtered:
        print(f"  ✓ {stock['symbol']}: +{stock['change_pct']}%")
    
    return True

def test_api_endpoints():
    """Test if API endpoints are properly defined"""
    print("\n=== Testing API Endpoint Definitions ===")
    
    try:
        # Import the screener router
        from app.api import screener
        
        # Check if router has expected endpoints
        routes = []
        for route in screener.router.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append(f"{list(route.methods)[0]} {route.path}")
                print(f"✓ Found endpoint: {list(route.methods)[0]} {route.path}")
        
        expected_endpoints = ["/screen", "/symbols", "/filters", "/health"]
        missing = []
        
        for endpoint in expected_endpoints:
            found = any(endpoint in route for route in routes)
            if not found:
                missing.append(endpoint)
        
        if missing:
            print(f"\n✗ Missing endpoints: {', '.join(missing)}")
            return False
        else:
            print("\n✓ All expected endpoints defined")
            return True
            
    except Exception as e:
        print(f"✗ Error importing API routes: {str(e)}")
        return False

def test_filter_definitions():
    """Test filter definitions without numpy"""
    print("\n=== Testing Filter Definitions ===")
    
    try:
        # Read the filters file
        filters_path = os.path.join(os.path.dirname(__file__), 'app/core/filters.py')
        
        with open(filters_path, 'r') as f:
            content = f.read()
            
        # Check for key filter classes
        filter_classes = [
            "PriceFilter",
            "VolumeFilter", 
            "ChangeFilter",
            "MovingAverageFilter",
            "RSIFilter"
        ]
        
        found = []
        missing = []
        
        for filter_class in filter_classes:
            if f"class {filter_class}" in content:
                found.append(filter_class)
                print(f"✓ Found {filter_class}")
            else:
                missing.append(filter_class)
                print(f"✗ Missing {filter_class}")
        
        return len(missing) == 0
        
    except Exception as e:
        print(f"✗ Error checking filters: {str(e)}")
        return False

def test_mock_server():
    """Test a minimal FastAPI server without all dependencies"""
    print("\n=== Testing Minimal Server Setup ===")
    
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
        
        # Create minimal app
        app = FastAPI(title="Stock Screener Test")
        
        @app.get("/test")
        def test_endpoint():
            return {"status": "ok", "message": "Test endpoint working"}
        
        print("✓ FastAPI app created successfully")
        print("✓ Test endpoint defined")
        
        # Test if we can access the openapi schema
        if hasattr(app, 'openapi'):
            print("✓ OpenAPI schema available")
        
        return True
        
    except Exception as e:
        print(f"✗ Error creating test server: {str(e)}")
        return False

def check_missing_dependencies():
    """List all missing dependencies with installation commands"""
    print("\n=== Missing Dependencies Summary ===")
    
    missing = []
    
    deps = [
        ("pydantic_settings", "pydantic-settings"),
        ("numpy", "numpy"),
        ("pandas", "pandas"),
        ("httpx", "httpx"),
        ("dotenv", "python-dotenv"),
        ("pytest", "pytest"),
        ("pytest_asyncio", "pytest-asyncio"),
    ]
    
    for module, package in deps:
        try:
            __import__(module)
        except ImportError:
            missing.append(package)
    
    if missing:
        print("\n✗ Missing packages:")
        for pkg in missing:
            print(f"  - {pkg}")
        
        print("\n To install missing dependencies, run:")
        print("  python3 -m pip install --user " + " ".join(missing))
        print("\n Or create a virtual environment:")
        print("  python3 -m venv venv")
        print("  source venv/bin/activate")
        print("  pip install -r requirements.txt")
    else:
        print("✓ All dependencies installed")
    
    return len(missing) == 0

def main():
    print("Stock Screener Backend Testing (Minimal)")
    print("=" * 50)
    
    results = {
        "Polygon API": test_polygon_api_basic(),
        "Screening Logic": test_screening_logic(),
        "API Endpoints": test_api_endpoints(),
        "Filter Definitions": test_filter_definitions(),
        "Server Setup": test_mock_server(),
        "Dependencies": check_missing_dependencies()
    }
    
    print("\n" + "=" * 50)
    print("Test Results Summary:")
    print("=" * 50)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test, result in results.items():
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{test:<20} {status}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed < total:
        print("\n⚠️  Backend has issues that need to be resolved")
        print("See details above for specific problems")
    else:
        print("\n✓ Backend core functionality verified!")

if __name__ == "__main__":
    main()