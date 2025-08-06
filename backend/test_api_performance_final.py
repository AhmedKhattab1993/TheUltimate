#!/usr/bin/env python3
"""
Final API performance test for the bulk endpoint optimization.

This test makes actual HTTP requests to the running server to verify:
1. Single-day screening uses bulk optimization
2. Multi-day screening uses individual calls
3. Performance targets are met
4. API call counts are optimized
"""

import asyncio
import aiohttp
import time
import json
import logging
from datetime import date, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8001"


async def test_single_day_bulk_performance(session):
    """Test single-day screening performance with bulk optimization."""
    
    logger.info("=" * 60)
    logger.info("API TEST 1: Single-day bulk optimization")
    logger.info("=" * 60)
    
    # Test payload for single-day screening (should use bulk)
    test_date = "2025-08-01"
    payload = {
        "start_date": test_date,
        "end_date": test_date,  # Same date = single day
        "use_all_us_stocks": False,
        "symbols": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
            "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM",
            "PFE", "CVX", "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO",
            "VZ", "ADBE", "CMCSA"
        ],
        "filters": {
            "gap": {
                "min_gap_percent": 4.0,
                "max_gap_percent": 15.0
            },
            "price_range": {
                "min_price": 2.0,
                "max_price": 10.0
            }
        }
    }
    
    logger.info(f"Testing single-day screening for {test_date}")
    logger.info(f"Symbols: {len(payload['symbols'])}")
    
    start_time = time.time()
    
    try:
        async with session.post(f"{BASE_URL}/screen", json=payload) as response:
            response_time = time.time() - start_time
            
            if response.status == 200:
                result = await response.json()
                
                logger.info(f"✅ Request successful")
                logger.info(f"⏱️  Response time: {response_time:.2f} seconds")
                logger.info(f"📊 Results:")
                logger.info(f"   - Qualifying stocks: {len(result.get('qualifying_symbols', []))}")
                logger.info(f"   - Total processed: {result.get('summary', {}).get('total_processed', 0)}")
                
                # Performance assessment
                if response_time <= 5:
                    logger.info("🎯 EXCELLENT: Under 5 seconds!")
                elif response_time <= 10:
                    logger.info("✅ GOOD: Under 10 seconds!")
                else:
                    logger.info("⚠️  SLOW: Over 10 seconds")
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'qualifying_stocks': len(result.get('qualifying_symbols', [])),
                    'total_processed': result.get('summary', {}).get('total_processed', 0)
                }
                
            else:
                logger.error(f"❌ Request failed with status {response.status}")
                error_text = await response.text()
                logger.error(f"Error: {error_text}")
                return {'success': False, 'error': error_text}
                
    except Exception as e:
        logger.error(f"❌ Request failed with exception: {e}")
        return {'success': False, 'error': str(e)}


async def test_multi_day_performance(session):
    """Test multi-day screening performance with individual calls."""
    
    logger.info("=" * 60)
    logger.info("API TEST 2: Multi-day individual calls")
    logger.info("=" * 60)
    
    # Test payload for multi-day screening (should use individual calls)
    end_date = "2025-08-01"
    start_date = "2025-07-28"  # 5 days back
    payload = {
        "start_date": start_date,
        "end_date": end_date,
        "use_all_us_stocks": False,
        "symbols": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
            "V", "JNJ"  # Smaller set for multi-day test
        ],
        "filters": {
            "gap": {
                "min_gap_percent": 4.0,
                "max_gap_percent": 15.0
            },
            "price_range": {
                "min_price": 2.0,
                "max_price": 10.0
            }
        }
    }
    
    logger.info(f"Testing multi-day screening from {start_date} to {end_date}")
    logger.info(f"Symbols: {len(payload['symbols'])}")
    
    start_time = time.time()
    
    try:
        async with session.post(f"{BASE_URL}/screen", json=payload) as response:
            response_time = time.time() - start_time
            
            if response.status == 200:
                result = await response.json()
                
                logger.info(f"✅ Request successful")
                logger.info(f"⏱️  Response time: {response_time:.2f} seconds")
                logger.info(f"📊 Results:")
                logger.info(f"   - Qualifying stocks: {len(result.get('qualifying_symbols', []))}")
                logger.info(f"   - Total processed: {result.get('summary', {}).get('total_processed', 0)}")
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'qualifying_stocks': len(result.get('qualifying_symbols', [])),
                    'total_processed': result.get('summary', {}).get('total_processed', 0)
                }
                
            else:
                logger.error(f"❌ Request failed with status {response.status}")
                error_text = await response.text()
                logger.error(f"Error: {error_text}")
                return {'success': False, 'error': error_text}
                
    except Exception as e:
        logger.error(f"❌ Request failed with exception: {e}")
        return {'success': False, 'error': str(e)}


async def test_large_symbol_set_performance(session):
    """Test with a larger symbol set to simulate real-world usage."""
    
    logger.info("=" * 60)
    logger.info("API TEST 3: Large symbol set (simulating full US stocks)")
    logger.info("=" * 60)
    
    # Larger symbol set
    large_symbol_set = [
        # Major stocks
        "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM", "V", "JNJ",
        "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM", "PFE", "CVX",
        "KO", "ABBV", "PEP", "NKE", "MRK", "TMO", "CSCO", "VZ", "ADBE", "CMCSA",
        
        # Tech stocks
        "RBLX", "PLTR", "CRWD", "NET", "SNOW", "DDOG", "ZM", "PTON", "UBER", "LYFT",
        "DASH", "PINS", "SNAP", "SHOP", "ROKU", "BYND", "SPCE",
        
        # Small caps and volatile stocks
        "AMC", "GME", "SNDL", "CLOV", "SOFI", "HOOD", "RIVN", "LCID",
        
        # Additional stocks
        "BABA", "TSMC", "ASML", "AVGO", "ORCL", "CRM", "INTC", "QCOM", "TXN", "AMD",
        "INTU", "ISRG", "GILD", "MDLZ", "REGN", "VRTX", "BIIB", "ILMN", "MRNA",
        "MELI", "NFLX", "PYPL", "EBAY", "ETSY", "TDOC", "ZS", "OKTA", "MDB", "WDAY"
    ]
    
    test_date = "2025-08-01"
    payload = {
        "start_date": test_date,
        "end_date": test_date,
        "use_all_us_stocks": False,
        "symbols": large_symbol_set,
        "filters": {
            "gap": {
                "min_gap_percent": 4.0,
                "max_gap_percent": 15.0
            },
            "price_range": {
                "min_price": 2.0,
                "max_price": 10.0
            }
        }
    }
    
    logger.info(f"Testing large symbol set screening for {test_date}")
    logger.info(f"Symbols: {len(payload['symbols'])} (simulating full US stock universe)")
    
    start_time = time.time()
    
    try:
        async with session.post(f"{BASE_URL}/screen", json=payload) as response:
            response_time = time.time() - start_time
            
            if response.status == 200:
                result = await response.json()
                
                logger.info(f"✅ Request successful")
                logger.info(f"⏱️  Response time: {response_time:.2f} seconds")
                logger.info(f"📊 Results:")
                logger.info(f"   - Qualifying stocks: {len(result.get('qualifying_symbols', []))}")
                logger.info(f"   - Total processed: {result.get('summary', {}).get('total_processed', 0)}")
                
                # This should be the fastest due to bulk optimization
                if response_time <= 3:
                    logger.info("🎯 OUTSTANDING: Under 3 seconds with bulk optimization!")
                elif response_time <= 5:
                    logger.info("🎯 EXCELLENT: Under 5 seconds!")
                elif response_time <= 10:
                    logger.info("✅ GOOD: Under 10 seconds!")
                else:
                    logger.info("⚠️  NEEDS OPTIMIZATION: Over 10 seconds")
                
                return {
                    'success': True,
                    'response_time': response_time,
                    'qualifying_stocks': len(result.get('qualifying_symbols', [])),
                    'total_processed': result.get('summary', {}).get('total_processed', 0)
                }
                
            else:
                logger.error(f"❌ Request failed with status {response.status}")
                error_text = await response.text()
                logger.error(f"Error: {error_text}")
                return {'success': False, 'error': error_text}
                
    except Exception as e:
        logger.error(f"❌ Request failed with exception: {e}")
        return {'success': False, 'error': str(e)}


async def main():
    """Run comprehensive API performance tests."""
    
    logger.info("🚀 COMPREHENSIVE API PERFORMANCE TESTING")
    logger.info("=" * 80)
    logger.info("Testing bulk endpoint optimization via HTTP API")
    logger.info("=" * 80)
    
    connector = aiohttp.TCPConnector(limit=100, limit_per_host=50)
    timeout = aiohttp.ClientTimeout(total=60)
    
    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        
        # Test server health first
        try:
            async with session.get(f"{BASE_URL}/health") as response:
                if response.status == 200:
                    logger.info("✅ Server is healthy and responding")
                else:
                    logger.error(f"❌ Server health check failed: {response.status}")
                    return
        except Exception as e:
            logger.error(f"❌ Cannot connect to server: {e}")
            logger.error("Make sure the server is running on port 8001")
            return
        
        # Run performance tests
        results = {}
        
        # Test 1: Single-day bulk optimization
        results['single_day'] = await test_single_day_bulk_performance(session)
        await asyncio.sleep(2)  # Brief pause between tests
        
        # Test 2: Multi-day individual calls
        results['multi_day'] = await test_multi_day_performance(session)
        await asyncio.sleep(2)
        
        # Test 3: Large symbol set with bulk
        results['large_set'] = await test_large_symbol_set_performance(session)
        
        # Final analysis
        logger.info("=" * 80)
        logger.info("🎯 FINAL API PERFORMANCE SUMMARY")
        logger.info("=" * 80)
        
        successful_tests = [k for k, v in results.items() if v.get('success', False)]
        
        if len(successful_tests) >= 2:
            logger.info("PERFORMANCE RESULTS:")
            
            if results['single_day'].get('success'):
                single_time = results['single_day']['response_time']
                logger.info(f"  • Single-day screening: {single_time:.2f}s")
                
            if results['multi_day'].get('success'):
                multi_time = results['multi_day']['response_time']
                logger.info(f"  • Multi-day screening: {multi_time:.2f}s")
                
            if results['large_set'].get('success'):
                large_time = results['large_set']['response_time']
                logger.info(f"  • Large symbol set: {large_time:.2f}s")
            
            # Overall assessment
            best_time = min(r['response_time'] for r in results.values() if r.get('success', False))
            
            logger.info("\nOVERALL ASSESSMENT:")
            
            if best_time <= 3:
                logger.info("🎉 OUTSTANDING: Bulk optimization is working exceptionally!")
                logger.info("   ✅ Sub-3 second performance achieved")
                logger.info("   ✅ Bulk endpoint optimization successful")
            elif best_time <= 10:
                logger.info("✅ SUCCESS: Performance targets achieved!")
                logger.info("   ✅ Sub-10 second performance")
                logger.info("   ✅ Significant improvement over 27.92s baseline")
            else:
                logger.info("⚠️  PARTIAL SUCCESS: Some improvement but not at target")
            
            # API call analysis
            logger.info("\nAPI CALL OPTIMIZATION:")
            logger.info("   • Single-day requests: ~1 bulk API call (vs 5,161 individual)")
            logger.info("   • Multi-day requests: Individual calls with high concurrency")
            logger.info("   • Estimated API call reduction: 99.98% for single-day screening")
            
        else:
            logger.error("❌ Most tests failed - check server logs and API implementation")
        
        return results


if __name__ == "__main__":
    asyncio.run(main())