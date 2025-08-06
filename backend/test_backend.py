#!/usr/bin/env python3
"""
Backend Testing Script
Tests the backend components without requiring all dependencies
"""

import sys
import os
import json
import importlib.util

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test which modules can be imported"""
    print("=== Testing Module Imports ===")
    
    modules_to_test = [
        ("fastapi", "FastAPI"),
        ("uvicorn", "Uvicorn"),
        ("pydantic", "Pydantic"),
        ("pydantic_settings", "Pydantic Settings"),
        ("numpy", "NumPy"),
        ("pandas", "Pandas"),
        ("httpx", "HTTPX"),
        ("dotenv", "Python-dotenv"),
        ("pytest", "Pytest"),
    ]
    
    results = {}
    for module_name, display_name in modules_to_test:
        try:
            importlib.import_module(module_name)
            results[display_name] = "✓ Installed"
        except ImportError as e:
            results[display_name] = f"✗ Missing: {str(e)}"
    
    for name, status in results.items():
        print(f"{name}: {status}")
    
    return results

def test_config():
    """Test if configuration can be loaded"""
    print("\n=== Testing Configuration ===")
    
    try:
        # Check if .env file exists
        env_path = os.path.join(os.path.dirname(__file__), '.env')
        if os.path.exists(env_path):
            print(f"✓ .env file found at {env_path}")
            with open(env_path, 'r') as f:
                lines = f.readlines()
                for line in lines:
                    if 'POLYGON_API_KEY' in line:
                        key = line.split('=')[1].strip()
                        print(f"✓ POLYGON_API_KEY configured (length: {len(key)})")
        else:
            print("✗ .env file not found")
            
        # Try to load settings without pydantic_settings
        try:
            from dotenv import load_dotenv
            load_dotenv()
            
            api_key = os.getenv("POLYGON_API_KEY", "")
            if api_key:
                print(f"✓ Environment variable POLYGON_API_KEY loaded (length: {len(api_key)})")
            else:
                print("✗ POLYGON_API_KEY not found in environment")
        except ImportError:
            print("✗ python-dotenv not installed, checking .env file manually")
            
    except Exception as e:
        print(f"✗ Error loading configuration: {str(e)}")

def test_file_structure():
    """Test if all required files exist"""
    print("\n=== Testing File Structure ===")
    
    required_files = [
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/api/__init__.py",
        "app/api/screener.py",
        "app/services/__init__.py",
        "app/services/polygon_client.py",
        "app/services/screener.py",
        "app/models/__init__.py",
        "app/models/stock.py",
        "app/models/requests.py",
        "app/core/__init__.py",
        "app/core/filters.py",
    ]
    
    for file_path in required_files:
        full_path = os.path.join(os.path.dirname(__file__), file_path)
        if os.path.exists(full_path):
            print(f"✓ {file_path}")
        else:
            print(f"✗ {file_path} - NOT FOUND")

def test_polygon_api():
    """Test Polygon API connection"""
    print("\n=== Testing Polygon API Connection ===")
    
    try:
        import httpx
        from dotenv import load_dotenv
        load_dotenv()
        
        api_key = os.getenv("POLYGON_API_KEY", "")
        if not api_key:
            print("✗ No API key found")
            return
            
        # Test API connection
        url = f"https://api.polygon.io/v2/aggs/ticker/AAPL/prev?apiKey={api_key}"
        
        with httpx.Client() as client:
            response = client.get(url)
            if response.status_code == 200:
                print("✓ Successfully connected to Polygon API")
                data = response.json()
                if 'results' in data:
                    print(f"✓ Got data for AAPL: {data['results'][0]['c']} (close price)")
            else:
                print(f"✗ API request failed: {response.status_code}")
                print(f"  Response: {response.text}")
                
    except Exception as e:
        print(f"✗ Error testing Polygon API: {str(e)}")

def test_basic_imports():
    """Test importing our own modules"""
    print("\n=== Testing Backend Module Imports ===")
    
    modules = [
        "app",
        "app.models.stock",
        "app.models.requests",
        "app.core.filters",
    ]
    
    for module in modules:
        try:
            imported = importlib.import_module(module)
            print(f"✓ {module}")
        except Exception as e:
            print(f"✗ {module}: {str(e)}")

def main():
    print("Stock Screener Backend Test Suite")
    print("=" * 50)
    
    # Run all tests
    test_imports()
    test_config()
    test_file_structure()
    test_basic_imports()
    test_polygon_api()
    
    print("\n" + "=" * 50)
    print("Testing complete!")

if __name__ == "__main__":
    main()