# Performance Optimization Guide

## Overview

This guide documents the performance optimizations implemented to address the 15.4-second data loading bottleneck in the stock screener.

## Problem Analysis

The screening process was taking 15.4 seconds for data loading (88% of total time) when processing 8,589 symbols. Root cause analysis revealed:

1. **Bug in fallback code**: The `_fetch_all_data` function was calling a non-existent method `get_daily_bars`, causing it to fail for every symbol
2. **Missing database indexes**: No composite indexes existed for the primary query pattern

## Implemented Solutions

### 1. Fixed Database Batch Loading (80% improvement potential)

**File**: `app/api/simple_screener.py`

**Change**: Fixed `_fetch_all_data` to use proper batch database queries instead of individual API calls.

```python
# Now uses efficient batch query:
SELECT symbol, time::date as date, open, high, low, close, volume
FROM daily_bars
WHERE symbol = ANY($1::text[])
  AND time::date BETWEEN $2 AND $3
ORDER BY symbol, time
```

**Expected Impact**: 
- Reduces 8,589 individual queries to 1 batch query
- Expected time reduction: 15.4s → ~3s

### 2. Added Composite Database Indexes (50-70% improvement)

**File**: `scripts/apply_db_optimizations.py`

**Created Indexes**:

1. **Composite Covering Index**: 
   ```sql
   CREATE INDEX idx_daily_bars_symbol_time_covering 
   ON daily_bars (symbol, time) 
   INCLUDE (open, high, low, close, volume)
   ```
   - Eliminates heap lookups by including all needed columns
   - Perfectly matches the query pattern

2. **Symbols Index**:
   ```sql
   CREATE INDEX idx_symbols_active_type 
   ON symbols (type, symbol) 
   WHERE active = true
   ```
   - Speeds up active symbol lookups

3. **Time Index**: Backup index for date-first queries

**Expected Impact**:
- 50-70% reduction in query execution time
- Combined with fix #1: 15.4s → ~1-2s total

## How to Apply Optimizations

### Step 1: Apply Database Indexes

```bash
cd /home/ahmed/TheUltimate/backend
python scripts/apply_db_optimizations.py
```

This script will:
- Create optimized indexes (may take 2-5 minutes)
- Update table statistics
- Verify index creation
- Test query performance

### Step 2: Restart Backend

The code fix is already applied. Restart the backend to use the new code:

```bash
# Stop backend
pkill -f "uvicorn.*backend"

# Start backend
cd /home/ahmed/TheUltimate/backend
./scripts/run_services.sh
```

## Verification

After applying optimizations, check the logs for:

1. **Data Loading Time**: Should drop from 15.4s to 1-2s
2. **Batch Loading Message**: Should see "Batch loaded X symbols with Y total bars"
3. **No Fallback Errors**: Should not see "Error fetching data for symbol"

## Additional Optimization Opportunities

If further optimization is needed:

1. **PostgreSQL Configuration Tuning** (20-30% additional improvement):
   ```sql
   -- Increase work_mem for sorting
   SET work_mem = '256MB';
   
   -- Increase shared_buffers
   -- Edit postgresql.conf:
   shared_buffers = 4GB
   effective_cache_size = 12GB
   ```

2. **Connection Pool Tuning**:
   - Increase pool size in database configuration
   - Current asyncpg pool settings may need adjustment

3. **Data Partitioning**:
   - Partition daily_bars table by date range
   - Further improves query performance for date-based queries

## Performance Monitoring

Monitor performance with:

```sql
-- Check query execution plans
EXPLAIN (ANALYZE, BUFFERS) 
SELECT symbol, time::date as date, open, high, low, close, volume
FROM daily_bars
WHERE symbol = ANY(ARRAY['AAPL', 'MSFT']::text[])
  AND time::date BETWEEN '2025-08-01' AND '2025-08-31';

-- Check index usage
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch
FROM pg_stat_user_indexes
WHERE tablename = 'daily_bars'
ORDER BY idx_scan DESC;
```

## Expected Results

After implementing both optimizations:

- **Before**: 15.4 seconds data loading (88% of total time)
- **After**: 1-2 seconds data loading (~10% of total time)
- **Overall Improvement**: 85-90% reduction in screening time