#!/usr/bin/env python3
"""
Test screening performance without caching for August 1, 2025
"""
import asyncio
import time
import logging
from datetime import date
import httpx

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

API_URL = "http://localhost:8000"

async def test_screening_performance():
    """Test full screening performance without caching"""
    
    # First clear the cache
    async with httpx.AsyncClient() as client:
        logger.info("Clearing cache...")
        response = await client.post(f"{API_URL}/api/v1/cache/clear")
        if response.status_code == 200:
            logger.info("Cache cleared successfully")
    
    # Prepare screening request with default day trading filters
    request_data = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "use_all_us_stocks": True,
        "filters": {
            "gap": {
                "min_gap_percent": 4.0
            },
            "price_range": {
                "min_price": 2.0,
                "max_price": 10.0
            },
            "float": {
                "max_float": 100000000,
                "preferred_max_float": 20000000
            },
            "relative_volume": {
                "min_relative_volume": 2.0,
                "lookback_days": 20
            },
            "premarket_volume": {
                "min_volume": 100000,
                "cutoff_time": "09:00"
            },
            "market_cap": {
                "max_market_cap": 300000000
            }
        }
    }
    
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        # Run the screening
        logger.info("Starting screening run (no cache)...")
        logger.info("Date: August 1, 2025")
        logger.info("Symbols: All US common stocks (~5,161)")
        logger.info("Filters: Default day trading filters")
        
        start_time = time.time()
        
        try:
            response = await client.post(
                f"{API_URL}/api/v1/screen",
                json=request_data
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if response.status_code == 200:
                data = response.json()
                
                logger.info("\n" + "="*60)
                logger.info("SCREENING RESULTS (NO CACHE)")
                logger.info("="*60)
                logger.info(f"Total symbols screened: {data.get('total_symbols_screened', 0)}")
                logger.info(f"Results found: {len(data.get('results', []))}")
                logger.info(f"Execution time (server): {data.get('execution_time_ms', 0):.2f} ms")
                logger.info(f"Total request time: {elapsed_time:.2f} seconds")
                logger.info(f"Throughput: {data.get('total_symbols_screened', 0) / elapsed_time:.1f} symbols/second")
                
                # Show sample results
                if data.get('results'):
                    logger.info(f"\nTop 5 results: {[r['symbol'] for r in data['results'][:5]]}")
                
                # Calculate API call estimates
                total_symbols = data.get('total_symbols_screened', 5161)
                logger.info(f"\nAPI calls made: ~{total_symbols} (one per symbol)")
                logger.info(f"Average time per symbol: {elapsed_time / total_symbols * 1000:.2f} ms")
                
            else:
                logger.error(f"Screening failed: {response.status_code}")
                logger.error(f"Error: {response.text}")
                
        except httpx.TimeoutException:
            logger.error("Request timed out after 600 seconds")
        except Exception as e:
            logger.error(f"Error: {e}")
            
        # Run a second time to show cache impact (for comparison)
        logger.info("\n" + "="*60)
        logger.info("Running second screening (WITH CACHE) for comparison...")
        
        start_time2 = time.time()
        
        try:
            response2 = await client.post(
                f"{API_URL}/api/v1/screen",
                json=request_data
            )
            
            end_time2 = time.time()
            elapsed_time2 = end_time2 - start_time2
            
            if response2.status_code == 200:
                data2 = response2.json()
                logger.info(f"Cached execution time: {elapsed_time2:.2f} seconds")
                logger.info(f"Cache speedup: {elapsed_time / elapsed_time2:.1f}x faster")
                
        except Exception as e:
            logger.error(f"Error on cached run: {e}")

if __name__ == "__main__":
    asyncio.run(test_screening_performance())