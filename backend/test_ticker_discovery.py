#!/usr/bin/env python3
"""
Test script for ticker discovery functionality.

This script tests the new ticker discovery service to ensure it's working correctly.
"""

import asyncio
import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app.services.polygon_client import PolygonClient
from backend.app.services.ticker_discovery import TickerDiscoveryService
from backend.app.config import settings


async def test_ticker_discovery():
    """Test the ticker discovery service."""
    print("Testing Ticker Discovery Service")
    print("=" * 50)
    
    # Create Polygon client
    async with PolygonClient() as polygon_client:
        # Create ticker discovery service
        ticker_service = TickerDiscoveryService(polygon_client)
        
        try:
            # Test fetching a single page of tickers first
            print("\n1. Testing single page fetch...")
            start_time = datetime.now()
            
            # Fetch just one page to test
            single_page = await polygon_client.fetch_tickers(
                market="stocks",
                ticker_type="CS",
                active=True,
                limit=10  # Small limit for testing
            )
            
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   - Fetched {len(single_page.get('results', []))} tickers in {elapsed:.2f} seconds")
            
            if single_page.get('results'):
                print("   - Sample tickers:", [t['ticker'] for t in single_page['results'][:5]])
            
            # Test full discovery (this might take a while)
            print("\n2. Testing full US common stock discovery...")
            print("   (This may take 10-30 seconds due to pagination...)")
            
            start_time = datetime.now()
            all_tickers = await ticker_service.fetch_all_us_common_stocks()
            elapsed = (datetime.now() - start_time).total_seconds()
            
            print(f"\n   - Found {len(all_tickers)} US common stocks")
            print(f"   - Time taken: {elapsed:.2f} seconds")
            print(f"   - Sample tickers: {all_tickers[:10]}")
            
            # Show some statistics
            print("\n3. Ticker Statistics:")
            print(f"   - Total US common stocks: {len(all_tickers)}")
            print(f"   - Single letter tickers: {len([t for t in all_tickers if len(t) == 1])}")
            print(f"   - Two letter tickers: {len([t for t in all_tickers if len(t) == 2])}")
            print(f"   - Three letter tickers: {len([t for t in all_tickers if len(t) == 3])}")
            print(f"   - Four+ letter tickers: {len([t for t in all_tickers if len(t) >= 4])}")
            
            print("\n✅ Ticker discovery test completed successfully!")
            
        except Exception as e:
            print(f"\n❌ Error during testing: {e}")
            import traceback
            traceback.print_exc()


async def test_api_endpoint():
    """Test the API endpoint for ticker discovery."""
    print("\n\nTesting API Endpoint")
    print("=" * 50)
    
    try:
        import httpx
        
        # Assuming the API is running on default port
        base_url = "http://localhost:8000"
        
        async with httpx.AsyncClient() as client:
            # Test the new endpoint
            print("\n1. Testing /api/screener/symbols/us-stocks endpoint...")
            
            response = await client.get(f"{base_url}/api/screener/symbols/us-stocks")
            
            if response.status_code == 200:
                tickers = response.json()
                print(f"   - Successfully fetched {len(tickers)} US stocks via API")
                print(f"   - Sample: {tickers[:5]}")
            else:
                print(f"   - Failed with status {response.status_code}: {response.text}")
                
    except httpx.ConnectError:
        print("   - Could not connect to API. Make sure the backend is running.")
    except Exception as e:
        print(f"   - Error testing API: {e}")


if __name__ == "__main__":
    print("Starting Ticker Discovery Tests...")
    
    # Test ticker discovery service directly
    asyncio.run(test_ticker_discovery())
    
    # Optionally test API endpoint
    # asyncio.run(test_api_endpoint())