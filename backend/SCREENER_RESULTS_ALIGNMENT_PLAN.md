# Screener Results Table Alignment Plan

## Overview
This plan outlines the tasks needed to align the screener_results table schema with the actual pipeline configuration, removing unused columns and adding pipeline-specific filter columns while maintaining cache functionality.

## Current Issues
1. Database schema has columns for filters not used in pipeline (market_cap, change, ATR)
2. Pipeline has filters (RSI, relative_volume) without corresponding database columns
3. Frontend expects certain data that may not align with new structure
4. Cache service relies on specific columns for matching results

## End Goal
- Screener results table only stores filters actually used in pipeline
- Cache functionality remains intact
- Frontend displays appropriate columns for screener results
- Clean migration from current to new schema

---

## Task Breakdown

### Task 1: Analyze Current Dependencies
**Agent**: General-purpose
**Objectives**:
1. Identify all code that reads from screener_results table
2. Document which columns are actually used by:
   - Cache service (already identified: uses filter columns for matching)
   - API endpoints for listing screener results
   - API endpoints for screener result details
   - Any other services
3. Create a dependency map showing what needs to be updated

**Key files to check**:
- `/backend/app/api/screener_results.py`
- `/backend/app/services/cache_service.py`
- `/backend/app/services/screener_results.py`
- Any other files that query screener_results table

---

### Task 2: Design New Table Schema
**Agent**: Software-architect
**Objectives**:
1. Design the new screener_results table schema that:
   - Keeps columns required for cache matching
   - Adds columns for pipeline-specific filters (RSI, relative_volume details)
   - Removes unused columns (market data, unused filters)
   - Maintains compatibility with existing foreign keys/relationships

2. Consider whether to:
   - Keep one row per symbol (current design) for cache compatibility
   - Or switch to one row per screening session with JSONB array of symbols

3. Document the mapping between:
   - Pipeline config parameters → Database columns
   - Old schema → New schema

**New Schema Structure**:
```sql
-- Core identification
id, session_id, screened_at, created_at, data_date

-- Symbol data (one row per symbol for cache)
symbol, company_name (nullable)

-- Existing filter columns used by cache
filter_min_price, filter_max_price
filter_min_volume
filter_min_gap
filter_above_sma20

-- New pipeline-specific columns
filter_price_vs_ma_period
filter_price_vs_ma_condition
filter_rsi_enabled
filter_rsi_period
filter_rsi_threshold
filter_rsi_condition
filter_gap_direction
filter_relative_volume_enabled
filter_relative_volume_ratio
filter_prev_day_dollar_volume

-- Remove: price, volume, market_cap, all unused filter columns, metric columns
```

---

### Task 3: Create Database Migration
**Agent**: Implementation-engineer
**Objectives**:
1. Create migration script `004_align_screener_results_schema.sql` that:
   - Backs up existing data to a temporary table
   - Adds new columns for pipeline-specific filters
   - Drops unused columns
   - Migrates any necessary data
   - Updates indexes for performance

2. Include rollback capability in case of issues

3. Test migration on a copy of the database first

**Migration Steps**:
```sql
-- 1. Create backup
CREATE TABLE screener_results_backup AS SELECT * FROM screener_results;

-- 2. Add new columns
ALTER TABLE screener_results ADD COLUMN filter_price_vs_ma_period INTEGER;
-- ... etc

-- 3. Drop unused columns
ALTER TABLE screener_results DROP COLUMN price;
-- ... etc

-- 4. Update indexes
```

---

### Task 4: Update Cache Service
**Agent**: Implementation-engineer
**Objectives**:
1. Update `CachedScreenerRequest` model to include new filter parameters
2. Update `CachedScreenerResult` model to remove unused fields
3. Modify cache matching logic to handle new filter columns
4. Update the hash calculation to include new parameters
5. Test cache hit/miss logic with new schema

**Key changes**:
- Add RSI and relative volume parameters to cache request
- Update SQL queries to use new column names
- Ensure backward compatibility during transition

---

### Task 5: Update Pipeline Code
**Agent**: Implementation-engineer
**Objectives**:
1. Update `run_screener_backtest_pipeline.py` to:
   - Save all filter parameters to appropriate columns
   - Map pipeline config to new database columns correctly
   - Remove code that saves unused data (price, volume, metrics)

2. Ensure the pipeline correctly populates:
   - RSI filter details when enabled
   - Relative volume filter details when enabled
   - Price vs MA period and condition
   - Gap direction
   - Previous day dollar volume

---

### Task 6: Update API Endpoints
**Agent**: Implementation-engineer
**Objectives**:
1. Update `/api/v2/screener/results` endpoint to:
   - Return data in format expected by frontend
   - Include new filter information
   - Remove references to dropped columns

2. Update the screener results detail endpoint to:
   - Show complete filter information
   - Format response appropriately for frontend

3. Ensure API responses include:
   - Which filters were applied
   - Filter parameters/thresholds
   - Symbol count and list

---

### Task 7: Update Frontend Display
**Agent**: Implementation-engineer
**Objectives**:
1. Update `ScreenerResultsView.tsx` to:
   - Display new filter information appropriately
   - Remove any references to unused data
   - Show comprehensive filter details in the detail view

2. Update the `formatFilters` function to:
   - Include all pipeline filters
   - Show filter parameters (e.g., "RSI(14) < 30" instead of just "RSI")
   - Display in a user-friendly format

3. Frontend table should show:
   - Date/Time
   - Active Filters (formatted nicely)
   - Symbols Found
   - Execution Time
   - Actions (View/Delete)

---

### Task 8: Data Cleanup
**Agent**: Implementation-engineer
**Objectives**:
1. After migration is tested and applied:
   - Clear existing screener_results data (it's temporary cache data)
   - Verify the backup table was created successfully
   - Run a test screening to populate new schema

2. Clean up any orphaned data or broken references

---

### Task 9: Testing
**Agent**: System-tester
**Objectives**:
1. Test complete flow:
   - Run screener with various filter combinations
   - Verify results are saved correctly to database
   - Check cache hit/miss functionality
   - Test frontend display of results

2. Verify:
   - All enabled filters are properly stored
   - Cache matching works correctly
   - Frontend displays accurate filter information
   - No errors in console or logs

3. Test edge cases:
   - Screening with no filters enabled
   - Screening with all filters enabled
   - Cache hits with different filter combinations

---

### Task 10: Documentation
**Agent**: General-purpose
**Objectives**:
1. Update documentation to reflect:
   - New database schema
   - Mapping between pipeline config and database
   - How filters are stored and retrieved

2. Document any breaking changes or migration notes

---

## Execution Order
1. Task 1: Analyze dependencies (understand impact)
2. Task 2: Design new schema (architect the solution)
3. Task 3: Create migration script (prepare database changes)
4. Task 4-6: Update code components (implement changes)
5. Task 8: Clean data and apply migration
6. Task 7: Update frontend (user-facing changes)
7. Task 9: Test everything (verify correctness)
8. Task 10: Document changes

## Success Criteria
- [ ] Screener results table only contains columns for filters in pipeline config
- [ ] Cache functionality works correctly with new schema
- [ ] Frontend displays accurate filter information
- [ ] No data loss during migration
- [ ] All tests pass
- [ ] Performance is maintained or improved

## Rollback Plan
If issues arise:
1. Restore from screener_results_backup table
2. Revert code changes
3. Clear cache to force fresh results
4. Investigate and fix issues before retry