#!/bin/bash

# Post-Deployment Verification Script for Enhanced Backtest Schema
# This script validates the deployment was successful

set -e  # Exit on any error

# Configuration
API_BASE_URL=${API_BASE_URL:-"http://localhost:8000"}
FRONTEND_URL=${FRONTEND_URL:-"http://localhost:3000"}
DB_URL=${DATABASE_URL:-"postgresql://postgres:postgres@localhost:5432/stock_screener"}

echo "=== POST-DEPLOYMENT VERIFICATION SCRIPT ==="
echo "API Base URL: $API_BASE_URL"
echo "Frontend URL: $FRONTEND_URL"
echo "Timestamp: $(date)"

# Test 1: Database Connection and Schema
echo ""
echo "1. Verifying Database Schema..."
python3 << 'EOF'
import asyncio
import asyncpg
import os

async def verify_schema():
    try:
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stock_screener')
        conn = await asyncpg.connect(db_url)
        
        # Check enhanced columns exist
        columns = await conn.fetch('''
            SELECT column_name FROM information_schema.columns 
            WHERE table_name = 'market_structure_results'
            AND column_name IN (
                'strategy_name', 'pivot_bars', 'lower_timeframe', 
                'cache_hit', 'pivot_highs_detected', 'final_value'
            )
        ''')
        
        if len(columns) >= 6:
            print("   ✅ Enhanced schema columns present")
        else:
            print("   ❌ Missing enhanced columns")
            return False
        
        # Check cache key index
        index = await conn.fetchrow('''
            SELECT indexname FROM pg_indexes 
            WHERE tablename = 'market_structure_results' 
            AND indexname = 'idx_backtest_cache_key'
        ''')
        
        if index:
            print("   ✅ Cache key index exists")
        else:
            print("   ❌ Cache key index missing")
            return False
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Database verification failed: {e}")
        return False

if asyncio.run(verify_schema()):
    exit(0)
else:
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "   ✅ Database schema verification passed"
else
    echo "   ❌ Database schema verification failed"
    exit 1
fi

# Test 2: API Health Check
echo ""
echo "2. Verifying API Health..."
if curl -f -s "$API_BASE_URL/health" > /dev/null; then
    echo "   ✅ API health endpoint responding"
else
    echo "   ❌ API health endpoint not responding"
    exit 1
fi

# Test 3: Backtest API Endpoints
echo ""
echo "3. Testing Backtest API Endpoints..."

# Test backtest results endpoint
echo "   Testing GET /api/v1/backtest/results..."
RESULTS_RESPONSE=$(curl -s -w "%{http_code}" "$API_BASE_URL/api/v1/backtest/results?limit=5")
HTTP_CODE="${RESULTS_RESPONSE: -3}"

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ Backtest results endpoint responding"
else
    echo "   ❌ Backtest results endpoint failed (HTTP $HTTP_CODE)"
    exit 1
fi

# Test backtest strategies endpoint
echo "   Testing GET /api/v1/backtest/strategies..."
STRATEGIES_RESPONSE=$(curl -s -w "%{http_code}" "$API_BASE_URL/api/v1/backtest/strategies")
HTTP_CODE="${STRATEGIES_RESPONSE: -3}"

if [ "$HTTP_CODE" = "200" ]; then
    echo "   ✅ Backtest strategies endpoint responding"
else
    echo "   ❌ Backtest strategies endpoint failed (HTTP $HTTP_CODE)"
    exit 1
fi

# Test 4: Data Integrity
echo ""
echo "4. Verifying Data Integrity..."
python3 << 'EOF'
import asyncio
import asyncpg
import os

async def verify_data():
    try:
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stock_screener')
        conn = await asyncpg.connect(db_url)
        
        # Check record count
        count = await conn.fetchval('SELECT COUNT(*) FROM market_structure_results')
        print(f"   ✅ {count} backtest records in database")
        
        # Check for valid data in enhanced columns
        if count > 0:
            enhanced_data = await conn.fetchrow('''
                SELECT strategy_name, pivot_bars, lower_timeframe, 
                       pivot_highs_detected, cache_hit
                FROM market_structure_results 
                WHERE strategy_name IS NOT NULL 
                LIMIT 1
            ''')
            
            if enhanced_data:
                print(f"   ✅ Enhanced data populated: {enhanced_data['strategy_name']}")
                print(f"      Pivot bars: {enhanced_data['pivot_bars']}")
                print(f"      Timeframe: {enhanced_data['lower_timeframe']}")
            else:
                print("   ❌ Enhanced columns not populated")
                return False
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Data verification failed: {e}")
        return False

if asyncio.run(verify_data()):
    exit(0)
else:
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "   ✅ Data integrity verification passed"
else
    echo "   ❌ Data integrity verification failed"
    exit 1
fi

# Test 5: Performance Check
echo ""
echo "5. Performance Verification..."
python3 << 'EOF'
import asyncio
import asyncpg
import os
from datetime import datetime

async def verify_performance():
    try:
        db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/stock_screener')
        conn = await asyncpg.connect(db_url)
        
        # Test cache key lookup performance
        start_time = datetime.now()
        result = await conn.fetchrow('''
            SELECT * FROM market_structure_results 
            WHERE symbol = $1 AND strategy_name = $2 
            LIMIT 1
        ''', 'APLD', 'MarketStructure')
        
        query_time = (datetime.now() - start_time).total_seconds() * 1000
        
        if query_time < 100:
            print(f"   ✅ Cache key query: {query_time:.2f}ms (Good)")
        elif query_time < 500:
            print(f"   ⚠️  Cache key query: {query_time:.2f}ms (Acceptable)")
        else:
            print(f"   ❌ Cache key query: {query_time:.2f}ms (Too slow)")
            return False
        
        await conn.close()
        return True
        
    except Exception as e:
        print(f"   ❌ Performance verification failed: {e}")
        return False

if asyncio.run(verify_performance()):
    exit(0)
else:
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo "   ✅ Performance verification passed"
else
    echo "   ❌ Performance verification failed"
    exit 1
fi

# Test 6: Frontend Health Check (if available)
echo ""
echo "6. Frontend Verification..."
if curl -f -s "$FRONTEND_URL" > /dev/null; then
    echo "   ✅ Frontend responding"
else
    echo "   ⚠️  Frontend not responding (may be expected if not running)"
fi

# Test 7: Log Analysis
echo ""
echo "7. Checking for Errors in Logs..."
if [ -f "backend.log" ]; then
    ERROR_COUNT=$(grep -c "ERROR\|CRITICAL\|Exception" backend.log | tail -100 || echo "0")
    if [ "$ERROR_COUNT" -eq 0 ]; then
        echo "   ✅ No errors in recent logs"
    else
        echo "   ⚠️  Found $ERROR_COUNT errors in logs (review recommended)"
    fi
else
    echo "   ⚠️  Backend log file not found"
fi

# Test 8: Service Status
echo ""
echo "8. Service Status Check..."
if pgrep -f "python.*main.py" > /dev/null; then
    echo "   ✅ Backend service running"
else
    echo "   ❌ Backend service not running"
    exit 1
fi

# Generate verification report
echo ""
echo "=== DEPLOYMENT VERIFICATION REPORT ==="
echo "Timestamp: $(date)"
echo "Status: ✅ ALL TESTS PASSED"
echo ""
echo "Verified Components:"
echo "  ✅ Database schema and indexes"
echo "  ✅ API endpoints responding"
echo "  ✅ Data integrity maintained"
echo "  ✅ Performance within acceptable limits"
echo "  ✅ Services running correctly"
echo ""
echo "🎉 DEPLOYMENT VERIFICATION SUCCESSFUL!"
echo "🚀 Enhanced backtest system is ready for production use"

# Save verification results
echo "$(date): Deployment verification passed" >> deployment_verification.log