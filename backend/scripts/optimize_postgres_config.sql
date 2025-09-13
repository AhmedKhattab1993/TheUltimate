-- PostgreSQL Configuration Optimizations for Stock Screener
-- Run these commands as superuser or adjust postgresql.conf

-- 1. Increase work_mem for better sorting performance
-- Current: 4MB, Recommended: 256MB
ALTER SYSTEM SET work_mem = '256MB';

-- 2. Increase shared_buffers for better caching
-- Current: 128MB, Recommended: 2GB (25% of RAM)
-- Note: This requires restart
ALTER SYSTEM SET shared_buffers = '2GB';

-- 3. Adjust effective_cache_size
-- Current: 4GB, Recommended: 8GB (75% of RAM)
ALTER SYSTEM SET effective_cache_size = '8GB';

-- 4. Optimize for SSDs
-- Lower random_page_cost for SSD storage
ALTER SYSTEM SET random_page_cost = 1.1;

-- 5. Increase maintenance_work_mem for better index creation
ALTER SYSTEM SET maintenance_work_mem = '512MB';

-- 6. Enable parallel queries
ALTER SYSTEM SET max_parallel_workers_per_gather = 4;
ALTER SYSTEM SET max_parallel_workers = 8;

-- 7. Optimize checkpoint settings
ALTER SYSTEM SET checkpoint_completion_target = 0.9;
ALTER SYSTEM SET wal_buffers = '16MB';

-- 8. Enable JIT compilation for complex queries
ALTER SYSTEM SET jit = on;

-- Apply changes (some require restart)
SELECT pg_reload_conf();

-- Show current settings
SELECT name, setting, unit, short_desc
FROM pg_settings
WHERE name IN (
    'work_mem',
    'shared_buffers',
    'effective_cache_size',
    'random_page_cost',
    'maintenance_work_mem',
    'max_parallel_workers_per_gather',
    'jit'
)
ORDER BY name;