#!/usr/bin/env python3
"""
Simple API performance test using requests library.
"""

import requests
import time
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8001/api/v1"

def test_api_health():
    """Test if API is responding."""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            logger.info("✅ API is healthy")
            return True
        else:
            logger.error(f"❌ API health check failed: {response.status_code}")
            return False
    except Exception as e:
        logger.error(f"❌ Cannot connect to API: {e}")
        return False

def test_single_day_screening():
    """Test single-day screening performance."""
    
    logger.info("=" * 60)
    logger.info("API TEST: Single-day bulk optimization")
    logger.info("=" * 60)
    
    payload = {
        "start_date": "2025-08-01",
        "end_date": "2025-08-01",
        "use_all_us_stocks": False,
        "symbols": [
            "AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA", "JPM",
            "V", "JNJ", "WMT", "PG", "UNH", "HD", "DIS", "MA", "BAC", "XOM"
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
    
    logger.info(f"Testing {len(payload['symbols'])} symbols for single day")
    
    start_time = time.time()
    
    try:
        response = requests.post(f"{BASE_URL}/screen", json=payload, timeout=30)
        response_time = time.time() - start_time
        
        if response.status_code == 200:
            result = response.json()
            
            logger.info(f"✅ Request successful")
            logger.info(f"⏱️  Response time: {response_time:.2f} seconds")
            logger.info(f"📊 Results:")
            logger.info(f"   - Qualifying stocks: {len(result.get('qualifying_symbols', []))}")
            logger.info(f"   - Total processed: {result.get('summary', {}).get('total_processed', 0)}")
            
            if result.get('qualifying_symbols'):
                logger.info(f"   - Qualifying symbols: {result['qualifying_symbols'][:5]}{'...' if len(result['qualifying_symbols']) > 5 else ''}")
            
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
            logger.error(f"❌ Request failed with status {response.status_code}")
            logger.error(f"Error: {response.text}")
            return {'success': False, 'error': response.text}
            
    except Exception as e:
        logger.error(f"❌ Request failed with exception: {e}")
        return {'success': False, 'error': str(e)}

def main():
    """Run API performance test."""
    
    logger.info("🚀 API PERFORMANCE TEST")
    logger.info("=" * 50)
    
    # Check API health
    if not test_api_health():
        logger.error("API is not responding. Make sure server is running on port 8001")
        return
    
    # Run single-day screening test
    result = test_single_day_screening()
    
    if result['success']:
        logger.info("=" * 50)
        logger.info("🎯 TEST SUMMARY")
        logger.info("=" * 50)
        logger.info(f"✅ API test successful")
        logger.info(f"⏱️  Response time: {result['response_time']:.2f}s")
        logger.info(f"📊 Performance: {'EXCELLENT' if result['response_time'] <= 5 else 'GOOD' if result['response_time'] <= 10 else 'NEEDS WORK'}")
        
        # Compare to baseline
        baseline_time = 27.92
        improvement = baseline_time / result['response_time']
        logger.info(f"🚀 Improvement: {improvement:.1f}x faster than baseline ({baseline_time}s)")
        
        if improvement >= 5:
            logger.info("🎉 OUTSTANDING: Bulk optimization is working excellently!")
        elif improvement >= 2:
            logger.info("✅ SUCCESS: Significant performance improvement achieved!")
        else:
            logger.info("⚠️  MARGINAL: Some improvement but target not fully met")
    else:
        logger.error("❌ API test failed")

if __name__ == "__main__":
    main()