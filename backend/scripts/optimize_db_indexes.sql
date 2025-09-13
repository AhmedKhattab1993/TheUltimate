-- Optimization Script for Stock Screener Database Indexes
-- This script adds composite indexes to significantly improve query performance
-- Expected improvement: 50-70% reduction in data loading time

-- Drop existing indexes if they exist (to avoid conflicts)
DROP INDEX IF EXISTS idx_daily_bars_symbol_time;
DROP INDEX IF EXISTS idx_daily_bars_symbol_time_covering;
DROP INDEX IF EXISTS idx_symbols_active_type;

-- 1. Primary composite index on (symbol, time) with covering columns
-- This index is optimized for the main screening query pattern
-- The INCLUDE clause creates a covering index that contains all needed columns
-- This eliminates the need for heap lookups, dramatically improving performance
CREATE INDEX CONCURRENTLY idx_daily_bars_symbol_time_covering 
ON daily_bars (symbol, time) 
INCLUDE (open, high, low, close, volume);

-- 2. Partial index for active symbols query
-- This speeds up the get_all_active_symbols query
CREATE INDEX CONCURRENTLY idx_symbols_active_type 
ON symbols (type, symbol) 
WHERE active = true;

-- 3. Index for date range queries (if not using the composite index)
-- This is a fallback index for queries that filter by date first
CREATE INDEX CONCURRENTLY idx_daily_bars_time 
ON daily_bars (time);

-- 4. Analyze the tables to update statistics
-- This helps the query planner make better decisions
ANALYZE daily_bars;
ANALYZE symbols;

-- Verify indexes were created successfully
SELECT 
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE tablename IN ('daily_bars', 'symbols')
ORDER BY tablename, indexname;

-- Check index sizes
SELECT 
    pg_size_pretty(pg_relation_size(indexrelid)) AS index_size,
    indexrelname AS index_name
FROM pg_stat_user_indexes
WHERE schemaname = 'public' 
    AND tablename IN ('daily_bars', 'symbols')
ORDER BY pg_relation_size(indexrelid) DESC;