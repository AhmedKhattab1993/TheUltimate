# Database Table Restructure Plan

## Overview
Replace JSON columns with individual columns for each parameter in both `screener_results` and `market_structure_results` tables to improve queryability and performance.

## Task Breakdown

### Phase 1: Database Schema Redesign

#### Task 1: Analyze Current Schema & Design New Schema
- **Agent**: Software Architect
- **Objectives**:
  - Analyze all possible screener parameters from the pipeline and frontend
  - Analyze all backtest parameters and statistics
  - Design new table structure with individual typed columns
  - Plan migration strategy and data types for each column
- **Deliverables**:
  - Complete schema design for both tables
  - List of all columns with data types
  - Migration approach

#### Task 2: Implement Database Migration
- **Agent**: Implementation Engineer
- **Objectives**:
  - Create new migration SQL file (003_restructure_cache_tables.sql)
  - Drop existing tables (data will be cleared)
  - Create new tables with individual columns
  - Add appropriate indexes
- **Agent**: System Tester
- **Objectives**:
  - Verify new schema is created correctly
  - Check all columns exist with correct types
  - Verify indexes are created

### Phase 2: Update Cache Models & Services

#### Task 3: Update Cache Models
- **Agent**: Implementation Engineer
- **Objectives**:
  - Update `cache_models.py` to use individual fields instead of dictionaries
  - Add typed fields for all screener parameters
  - Add typed fields for all backtest parameters and statistics
  - Remove JSON serialization methods
- **Agent**: System Tester
- **Objectives**:
  - Verify models instantiate correctly
  - Test field validation
  - Ensure all parameters are captured

#### Task 4: Update Cache Service
- **Agent**: Implementation Engineer
- **Objectives**:
  - Modify `cache_service.py` to work with new column structure
  - Update SQL queries to use individual columns
  - Update hash calculation to work with new structure
  - Modify save/retrieve methods for both screener and backtest results
- **Agent**: System Tester
- **Objectives**:
  - Test cache save operations
  - Test cache retrieve operations
  - Verify hash calculation works correctly

### Phase 3: Update Pipeline Integration

#### Task 4.5: Update Pipeline Configuration
- **Agent**: Implementation Engineer
- **Objectives**:
  - Update `pipeline_config.yaml` to include all screener parameters with enable/disable flags
  - Add missing screener filters: volume, market_cap, change, ATR, technical indicators (VWAP, SMA20)
  - Ensure each filter has an `enabled` flag to turn it on/off
  - Match the configuration structure to the new database schema
- **Agent**: System Tester
- **Objectives**:
  - Verify all screener parameters from the schema are configurable
  - Test that enable/disable flags work correctly
  - Ensure backward compatibility with existing configs

#### Task 5: Update Pipeline Storage Logic
- **Agent**: Implementation Engineer
- **Objectives**:
  - Modify `backtest_queue_manager.py` to store individual fields
  - Update `run_screener_backtest_pipeline.py` for new structure
  - Parse all screener parameters from the config including enable/disable flags
  - Ensure all screener parameters are captured and stored
  - Ensure all backtest statistics are stored correctly
- **Agent**: System Tester
- **Objectives**:
  - Run pipeline with `max_backtests: 1`
  - Verify data is stored correctly in database
  - Check all columns are populated

### Phase 4: Update API Endpoints

#### Task 6: Update Backend APIs
- **Agent**: Implementation Engineer
- **Objectives**:
  - Update `screener_results.py` API to query individual columns
  - Update `backtest.py` database endpoints to use new structure
  - Modify response models if needed
  - Ensure backward compatibility with frontend
- **Agent**: System Tester
- **Objectives**:
  - Test all API endpoints
  - Verify responses match expected format
  - Check filtering and pagination still work

### Phase 5: Frontend Updates

#### Task 7: Update Frontend (if needed)
- **Agent**: Implementation Engineer
- **Objectives**:
  - Check if frontend needs updates for new data structure
  - Update Results tab components if necessary
  - Ensure all data displays correctly
- **Agent**: System Tester (Playwright)
- **Objectives**:
  - Test Results tab displays screener results correctly
  - Test Results tab displays backtest results correctly
  - Verify all statistics and parameters show properly

### Phase 6: End-to-End Testing

#### Task 8: Full Integration Test
- **Agent**: System Tester
- **Objectives**:
  - Clear database
  - Run full pipeline (remove max_backtests limit)
  - Verify all results stored correctly
  - Test Results tab shows all data
  - Test caching behavior (run pipeline twice)
  - Verify performance improvements

## Execution Order

1. **Task 1** - Architecture Design (Required first) ✅ COMPLETED
2. **Task 2** - Database Migration (Depends on Task 1) ✅ COMPLETED
3. **Task 3** - Update Models (Depends on Task 2) ✅ COMPLETED
4. **Task 4** - Update Cache Service (Depends on Task 3) ✅ COMPLETED
5. **Task 4.5** - Update Pipeline Configuration (Can be done after Task 4) ⏳ NEXT
6. **Task 5** - Update Pipeline (Depends on Task 4 and 4.5)
7. **Task 6** - Update APIs (Depends on Task 4, can be done after or in parallel with Task 5)
8. **Task 7** - Frontend Updates (Depends on Task 6)
9. **Task 8** - Final Testing (Depends on all previous tasks)

## Success Criteria

- All screener parameters stored in individual columns
- All backtest statistics stored in individual columns
- Improved query performance for filtering and sorting
- Results tab continues to work seamlessly
- Caching functionality maintained
- Pipeline runs successfully with new structure

## Notes

- Current data will be cleared during migration
- Each task includes both implementation and testing phases
- Tasks are designed to be atomic - each can be completed independently
- Rollback plan: Keep migration SQL to recreate old structure if needed