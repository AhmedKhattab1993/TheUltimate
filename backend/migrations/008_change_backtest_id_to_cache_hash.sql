-- Migration: 008_change_backtest_id_to_cache_hash.sql
-- Purpose: Change backtest_id from UUID to cache_hash VARCHAR to eliminate ID mismatch issues
-- Note: This is a major schema change that affects multiple tables

-- ============================================================================
-- FORWARD MIGRATION
-- ============================================================================

BEGIN;

-- Step 1: Add new cache_hash columns to affected tables
ALTER TABLE market_structure_results 
ADD COLUMN cache_hash VARCHAR(64);

ALTER TABLE backtest_trades 
ADD COLUMN cache_hash VARCHAR(64);

-- Step 2: Create function to convert UUID to cache hash format
-- Since we're using deterministic UUIDs based on cache hash, we can extract the original hash
CREATE OR REPLACE FUNCTION uuid_to_cache_hash(uuid_val UUID) RETURNS VARCHAR AS $$
BEGIN
    -- Extract the hex string from UUID and remove hyphens
    RETURN REPLACE(uuid_val::text, '-', '');
END;
$$ LANGUAGE plpgsql;

-- Step 3: Populate cache_hash columns with converted values
UPDATE market_structure_results 
SET cache_hash = uuid_to_cache_hash(backtest_id);

UPDATE backtest_trades 
SET cache_hash = uuid_to_cache_hash(backtest_id);

-- Step 4: Drop foreign key constraint on backtest_trades
ALTER TABLE backtest_trades 
DROP CONSTRAINT IF EXISTS fk_backtest_result;

-- Step 5: Drop the old backtest_id columns
ALTER TABLE market_structure_results 
DROP COLUMN backtest_id;

ALTER TABLE backtest_trades 
DROP COLUMN backtest_id;

-- Step 6: Rename cache_hash to backtest_id (but now it's VARCHAR)
ALTER TABLE market_structure_results 
RENAME COLUMN cache_hash TO backtest_id;

ALTER TABLE backtest_trades 
RENAME COLUMN cache_hash TO backtest_id;

-- Step 7: Set NOT NULL constraints
ALTER TABLE market_structure_results 
ALTER COLUMN backtest_id SET NOT NULL;

ALTER TABLE backtest_trades 
ALTER COLUMN backtest_id SET NOT NULL;

-- Step 8: Create new primary key and indexes on market_structure_results
-- First drop existing primary key on id
ALTER TABLE market_structure_results 
DROP CONSTRAINT market_structure_results_pkey;

-- Add new primary key on backtest_id (cache hash)
ALTER TABLE market_structure_results 
ADD CONSTRAINT market_structure_results_pkey PRIMARY KEY (backtest_id);

-- Keep the id column but make it unique instead of primary key
ALTER TABLE market_structure_results 
ADD CONSTRAINT market_structure_results_id_unique UNIQUE (id);

-- Step 9: Re-create foreign key constraint with new data type
ALTER TABLE backtest_trades 
ADD CONSTRAINT fk_backtest_result 
    FOREIGN KEY (backtest_id) 
    REFERENCES market_structure_results(backtest_id)
    ON DELETE CASCADE;

-- Step 10: Re-create indexes with new column type
DROP INDEX IF EXISTS idx_market_structure_backtest_id;
CREATE INDEX idx_market_structure_backtest_id ON market_structure_results(backtest_id);

DROP INDEX IF EXISTS idx_backtest_trades_backtest_id;
CREATE INDEX idx_backtest_trades_backtest_id ON backtest_trades(backtest_id);

-- Step 11: Update column comments
COMMENT ON COLUMN market_structure_results.backtest_id IS 'Cache hash used as unique identifier for the backtest (deterministic based on parameters)';
COMMENT ON COLUMN backtest_trades.backtest_id IS 'Cache hash linking to parent backtest result in market_structure_results table';

-- Step 12: Clean up temporary function
DROP FUNCTION IF EXISTS uuid_to_cache_hash(UUID);

-- Record migration
INSERT INTO schema_migrations (version, filename) 
VALUES (8, '008_change_backtest_id_to_cache_hash.sql')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- ============================================================================
-- ROLLBACK MIGRATION (if needed)
-- ============================================================================
-- BEGIN;
-- 
-- -- Step 1: Add UUID columns back
-- ALTER TABLE market_structure_results ADD COLUMN backtest_id_uuid UUID;
-- ALTER TABLE backtest_trades ADD COLUMN backtest_id_uuid UUID;
-- 
-- -- Step 2: Generate new UUIDs from cache hash
-- UPDATE market_structure_results 
-- SET backtest_id_uuid = (
--     SUBSTRING(backtest_id, 1, 8) || '-' ||
--     SUBSTRING(backtest_id, 9, 4) || '-' ||
--     SUBSTRING(backtest_id, 13, 4) || '-' ||
--     SUBSTRING(backtest_id, 17, 4) || '-' ||
--     SUBSTRING(backtest_id, 21, 12)
-- )::UUID;
-- 
-- UPDATE backtest_trades 
-- SET backtest_id_uuid = (
--     SELECT m.backtest_id_uuid 
--     FROM market_structure_results m 
--     WHERE m.backtest_id = backtest_trades.backtest_id
-- );
-- 
-- -- Step 3: Drop foreign key
-- ALTER TABLE backtest_trades DROP CONSTRAINT IF EXISTS fk_backtest_result;
-- 
-- -- Step 4: Drop VARCHAR columns
-- ALTER TABLE market_structure_results DROP COLUMN backtest_id;
-- ALTER TABLE backtest_trades DROP COLUMN backtest_id;
-- 
-- -- Step 5: Rename UUID columns
-- ALTER TABLE market_structure_results RENAME COLUMN backtest_id_uuid TO backtest_id;
-- ALTER TABLE backtest_trades RENAME COLUMN backtest_id_uuid TO backtest_id;
-- 
-- -- Step 6: Restore constraints and indexes
-- ALTER TABLE market_structure_results 
--     DROP CONSTRAINT market_structure_results_pkey,
--     ADD CONSTRAINT market_structure_results_pkey PRIMARY KEY (id),
--     DROP CONSTRAINT market_structure_results_id_unique;
-- 
-- ALTER TABLE backtest_trades 
--     ADD CONSTRAINT fk_backtest_result 
--     FOREIGN KEY (backtest_id) 
--     REFERENCES market_structure_results(backtest_id)
--     ON DELETE CASCADE;
-- 
-- CREATE INDEX idx_market_structure_backtest_id ON market_structure_results(backtest_id);
-- CREATE INDEX idx_backtest_trades_backtest_id ON backtest_trades(backtest_id);
-- 
-- DELETE FROM schema_migrations WHERE version = 8;
-- 
-- COMMIT;