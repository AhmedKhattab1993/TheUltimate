-- Script to clear market_structure_results table
-- This will delete all data but preserve the table structure

-- First, let's check how many records we're about to delete
SELECT COUNT(*) as total_records FROM market_structure_results;

-- Show a sample of records that will be deleted (first 5)
SELECT id, backtest_id, symbol, strategy_name, start_date, end_date, created_at 
FROM market_structure_results 
LIMIT 5;

-- Clear the table data
-- Using TRUNCATE for better performance and to reset any sequences
-- CASCADE will also delete related records in tables with foreign keys
TRUNCATE TABLE market_structure_results CASCADE;

-- Verify the table is empty
SELECT COUNT(*) as records_after_truncate FROM market_structure_results;

-- Note: If you need to delete specific records instead of all records, use:
-- DELETE FROM market_structure_results WHERE <condition>;