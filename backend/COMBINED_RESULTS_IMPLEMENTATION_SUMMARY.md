# Combined Screener + Backtest Results Implementation Summary

## Overview
Successfully implemented a combined view that shows both screener and backtest results in a single flat table, allowing users to see all screening parameters alongside backtest performance metrics for each symbol.

## What Was Implemented

### 1. Database Changes
- **Created migration** (`010_add_screener_backtest_link_table.sql`):
  - Added `screener_backtest_links` junction table to handle many-to-many relationships
  - Included `data_date` column to track day-by-day relationships
  - Created `combined_screener_backtest_results` view for easy querying
  - Added appropriate indexes for performance

### 2. Backend Modifications

#### UI Backtest Flow (`app/api/backtest.py`)
- Modified `/run-screener-backtests` endpoint to capture `screener_session_id`
- Updated query to include session_id when using latest UI session
- Added `screening_date` to each backtest request

#### Pipeline Backtest Flow (`run_screener_backtest_pipeline.py`)
- Modified `run_backtests` method to accept `screening_date` parameter
- Updated `run_single_day_pipeline` to pass screening date to backtests
- Set `screener_session_id` on BacktestQueueManager after generating session ID

#### BacktestQueueManager (`app/services/backtest_queue_manager.py`)
- Added `screener_session_id` parameter to constructor
- Implemented `_save_screener_backtest_link` method to save relationships
- Modified backtest save flow to create links when session_id is available

### 3. API Endpoint (`app/api/combined_results.py`)
- Created new API router for combined results
- Implemented `GET /api/v2/combined-results` endpoint with:
  - Filtering by session_id, date range, source, and symbol
  - Pagination support
  - Returns flat table with all screener + backtest columns
- Added `GET /api/v2/combined-results/sessions` for session summary

### 4. Frontend Components

#### CombinedResultsView Component
- Created new component displaying combined results in a data table
- Features:
  - Summary statistics cards (total symbols, avg return, win rate, etc.)
  - Filters for source, symbol, and session ID
  - Export to CSV functionality
  - Pagination
  - Color-coded performance metrics

#### Updated ResultsTab Component
- Changed grid from 2 to 3 columns
- Added "Combined Results" tab
- Updated tab change handler to support 'combined' value

#### Updated ResultsContext
- Modified `activeTab` type to include 'combined'
- Updated SET_ACTIVE_TAB action to accept 'combined'

## How It Works

1. **Screening**: When screening is performed (UI or pipeline), results are saved with `session_id` and `data_date`
2. **Backtesting**: When backtests are triggered from screening results:
   - The system captures which screening session and date triggered the backtest
   - A link is saved in `screener_backtest_links` table
3. **Combined View**: The view joins screener results with their corresponding backtest results
4. **Display**: Frontend shows a flat table with all columns from both tables

## Key Features

- **Day-by-Day Tracking**: Each screening day is tracked separately
- **Many-to-Many Handling**: Same backtest can be linked to multiple screener sessions due to caching
- **Source Tracking**: Distinguishes between UI and pipeline sources
- **Complete Data**: Shows all screening filters alongside all backtest metrics
- **Export Capability**: Results can be exported to CSV for analysis

## Usage

1. Run screening (either through UI or pipeline)
2. Run backtests from screener results
3. Navigate to Results → Combined Results tab
4. Filter and analyze the combined data
5. Export to CSV if needed