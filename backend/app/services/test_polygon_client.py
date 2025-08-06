"""
Test file for PolygonClient
This demonstrates how to use the client and can be used for manual testing.
"""

import asyncio
from datetime import date, timedelta
import os
from app.services.polygon_client import PolygonClient, PolygonAPIError
import logging

# Configure logging to see debug messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)


async def test_polygon_client():
    """Test various PolygonClient methods"""
    
    # Check if API key is set
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("WARNING: POLYGON_API_KEY environment variable not set!")
        print("Set it in .env file or export it to test the client")
        return
    
    print(f"Using API key: {api_key[:8]}...")
    
    async with PolygonClient() as client:
        print("\n1. Testing market status check...")
        try:
            market_status = await client.check_market_status()
            print(f"Market status: {market_status.get('market', 'unknown')}")
        except PolygonAPIError as e:
            print(f"Error checking market status: {e}")
        
        print("\n2. Testing single symbol fetch...")
        end_date = date.today()
        start_date = end_date - timedelta(days=7)  # Last 7 days
        
        try:
            stock_data = await client.fetch_historical_data(
                symbol="AAPL",
                start_date=start_date,
                end_date=end_date
            )
            
            print(f"Fetched {len(stock_data.bars)} bars for {stock_data.symbol}")
            if stock_data.bars:
                latest_bar = stock_data.bars[-1]
                print(f"Latest bar: Date={latest_bar.date}, Close=${latest_bar.close:.2f}, Volume={latest_bar.volume:,}")
                
                # Test numpy conversion
                np_data = stock_data.to_numpy()
                print(f"Numpy array shape: {np_data.shape}, dtype fields: {np_data.dtype.names}")
        
        except PolygonAPIError as e:
            print(f"Error fetching AAPL data: {e}")
        
        print("\n3. Testing batch fetch with rate limiting...")
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA"]  # 6 symbols to test rate limiting
        
        try:
            import time
            start_time = time.time()
            
            batch_data = await client.fetch_batch_historical_data(
                symbols=symbols,
                start_date=start_date,
                end_date=end_date
            )
            
            elapsed_time = time.time() - start_time
            print(f"Batch fetch completed in {elapsed_time:.2f} seconds")
            print(f"Successfully fetched data for {len(batch_data)} symbols:")
            
            for symbol, data in batch_data.items():
                if data.bars:
                    latest = data.bars[-1]
                    print(f"  {symbol}: {len(data.bars)} bars, latest close=${latest.close:.2f}")
                else:
                    print(f"  {symbol}: No data")
        
        except PolygonAPIError as e:
            print(f"Error in batch fetch: {e}")
        
        print("\n4. Testing symbol details...")
        try:
            details = await client.get_symbol_details("AAPL")
            if details:
                print(f"AAPL details:")
                print(f"  Name: {details.get('name', 'N/A')}")
                print(f"  Market Cap: {details.get('market_cap', 'N/A')}")
                print(f"  Currency: {details.get('currency_name', 'N/A')}")
        except PolygonAPIError as e:
            print(f"Error fetching symbol details: {e}")
        
        print("\n5. Testing error handling with invalid symbol...")
        try:
            invalid_data = await client.fetch_historical_data(
                symbol="INVALID123",
                start_date=start_date,
                end_date=end_date
            )
            print(f"Unexpected success for invalid symbol: {len(invalid_data.bars)} bars")
        except PolygonAPIError as e:
            print(f"Expected error for invalid symbol: {e}")


async def test_rate_limiting():
    """Test that rate limiting works correctly"""
    print("\nTesting rate limiting (this will take about 1 minute)...")
    
    api_key = os.getenv("POLYGON_API_KEY")
    if not api_key:
        print("Skipping rate limit test - no API key")
        return
    
    async with PolygonClient() as client:
        # Try to make more requests than allowed
        symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM"]
        end_date = date.today()
        start_date = end_date - timedelta(days=1)
        
        import time
        start_time = time.time()
        request_times = []
        
        for symbol in symbols:
            try:
                req_start = time.time()
                await client.fetch_historical_data(symbol, start_date, end_date)
                req_end = time.time()
                request_times.append(req_end - req_start)
                print(f"Request {len(request_times)}: {symbol} completed in {req_end - req_start:.2f}s")
            except Exception as e:
                print(f"Error fetching {symbol}: {e}")
        
        total_time = time.time() - start_time
        print(f"\nTotal time for {len(symbols)} requests: {total_time:.2f}s")
        print(f"Average request time: {sum(request_times)/len(request_times):.2f}s")
        
        # With 5 req/min limit, 8 requests should take > 60 seconds
        if total_time > 60:
            print("Rate limiting is working correctly!")
        else:
            print("WARNING: Rate limiting might not be working as expected")


if __name__ == "__main__":
    print("Polygon API Client Test Suite")
    print("=" * 50)
    
    # Run basic tests
    asyncio.run(test_polygon_client())
    
    # Uncomment to test rate limiting (takes about 1 minute)
    # asyncio.run(test_rate_limiting())