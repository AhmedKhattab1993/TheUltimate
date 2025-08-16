#!/usr/bin/env python3
"""
Diagnostic script to test pipeline components individually.
"""

import asyncio
import sys
from pathlib import Path
import logging
import time

# Add backend to path
sys.path.append(str(Path(__file__).parent))

from app.services.api_client import APIClient
from app.models.simple_requests import (
    SimpleScreenRequest, 
    SimplePriceRangeParams,
    GapParams,
    PreviousDayDollarVolumeParams,
    RelativeVolumeParams,
    SimpleFilters
)
from app.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_screener_api():
    """Test the screener API directly."""
    logger.info("Testing screener API...")
    
    # Build simple test request
    filters = SimpleFilters(
        price_range=SimplePriceRangeParams(min_price=5, max_price=1000),
        gap=GapParams(gap_threshold=2.0, direction="up"),
        prev_day_dollar_volume=PreviousDayDollarVolumeParams(min_dollar_volume=10000000),
        relative_volume=RelativeVolumeParams(recent_days=2, lookback_days=20, min_ratio=1.5)
    )
    
    request = SimpleScreenRequest(
        start_date="2025-08-04",
        end_date="2025-08-04",
        filters=filters,
        enable_db_prefiltering=True
    )
    
    # Test API client
    client = APIClient(base_url="http://localhost:8000")
    
    try:
        start_time = time.time()
        response = await client.screen_stocks(request)
        elapsed = time.time() - start_time
        
        logger.info(f"✓ Screener API test successful!")
        logger.info(f"  - Found {response.total_qualifying_stocks} stocks")
        logger.info(f"  - Response time: {elapsed:.2f}s")
        logger.info(f"  - First 5 symbols: {[r.symbol for r in response.results[:5]]}")
        
        return True, response.results
        
    except Exception as e:
        logger.error(f"✗ Screener API test failed: {e}")
        return False, []
    finally:
        await client.close()


async def test_lean_connection():
    """Test LEAN Docker connection."""
    logger.info("Testing LEAN Docker connection...")
    
    try:
        import docker
        client = docker.from_env()
        
        # Check if Docker is running
        client.ping()
        logger.info("✓ Docker is running")
        
        # Check if LEAN image exists
        images = client.images.list(name="quantconnect/lean")
        if images:
            logger.info("✓ LEAN Docker image found")
        else:
            logger.warning("✗ LEAN Docker image not found - may need to pull")
        
        # Check running containers
        containers = client.containers.list(all=True, filters={"ancestor": "quantconnect/lean:latest"})
        logger.info(f"  - LEAN containers: {len(containers)} found")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Docker/LEAN test failed: {e}")
        return False


async def test_backtest_manager():
    """Test the backtest manager with a single symbol."""
    logger.info("Testing backtest manager...")
    
    from app.services.backtest_manager import BacktestManager
    from app.models.backtest import BacktestRequest
    
    manager = BacktestManager()
    
    # Create simple backtest request
    request = BacktestRequest(
        strategy_name="MarketStructure",
        symbols=["AAPL"],  # Single test symbol
        start_date="2025-08-04",
        end_date="2025-08-04",
        initial_cash=100000,
        resolution="Daily",
        parameters={
            "pivot_bars": 2,
            "lower_timeframe": "5min"
        }
    )
    
    try:
        start_time = time.time()
        run_info = await manager.start_backtest(request)
        backtest_id = run_info.backtest_id
        logger.info(f"  - Created backtest ID: {backtest_id}")
        
        # Wait a bit for it to start
        await asyncio.sleep(5)
        
        # Check status
        status = await manager.get_backtest_status(backtest_id)
        elapsed = time.time() - start_time
        
        logger.info(f"✓ Backtest manager test successful!")
        logger.info(f"  - Status: {status.status if status else 'Unknown'}")
        logger.info(f"  - Time elapsed: {elapsed:.2f}s")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Backtest manager test failed: {e}")
        return False


async def test_database_connection():
    """Test database connection."""
    logger.info("Testing database connection...")
    
    try:
        from app.services.database import db_pool
        
        # Initialize the pool if needed
        await db_pool.initialize()
        
        async with db_pool.acquire() as conn:
            # Simple query
            result = await conn.fetchval("SELECT 1")
            if result == 1:
                logger.info("✓ Database connection successful")
                
                # Check tables
                tables = await conn.fetch("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                logger.info(f"  - Found {len(tables)} tables")
                
                return True
            
    except Exception as e:
        logger.error(f"✗ Database test failed: {e}")
        return False


async def main():
    """Run all diagnostic tests."""
    logger.info("=" * 60)
    logger.info("PIPELINE DIAGNOSTICS")
    logger.info("=" * 60)
    
    results = {}
    
    # Test 1: Database
    results['database'] = await test_database_connection()
    logger.info("")
    
    # Test 2: Screener API
    screener_ok, symbols = await test_screener_api()
    results['screener'] = screener_ok
    logger.info("")
    
    # Test 3: Docker/LEAN
    results['docker_lean'] = await test_lean_connection()
    logger.info("")
    
    # Test 4: Backtest Manager (only if other tests pass)
    if all([results['database'], results['screener'], results['docker_lean']]):
        results['backtest_manager'] = await test_backtest_manager()
    else:
        logger.warning("Skipping backtest manager test due to failed dependencies")
        results['backtest_manager'] = False
    
    # Summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    
    all_passed = all(results.values())
    
    for component, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        logger.info(f"{component:20} : {status}")
    
    logger.info("")
    if all_passed:
        logger.info("All tests passed! Pipeline should work correctly.")
    else:
        logger.info("Some tests failed. Please fix the issues above.")
    
    return all_passed


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)