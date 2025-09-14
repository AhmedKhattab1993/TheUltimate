# Grid Analysis Implementation Plan

## Overview
This document outlines the implementation plan for a comprehensive grid analysis system that performs screening calculations and parameter grid backtesting for all active symbols on a given date.

## Database Schema

### 1. Grid Screening Table
Stores calculated screening values for each symbol on each date.

```sql
CREATE TABLE grid_screening (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    date DATE NOT NULL,
    
    -- Price data
    price DECIMAL(10, 2),  -- Close price
    
    -- Moving averages
    ma_20 DECIMAL(10, 2),
    ma_50 DECIMAL(10, 2),
    ma_200 DECIMAL(10, 2),
    
    -- Technical indicators
    rsi_14 DECIMAL(5, 2),  -- RSI value (0-100)
    gap_percent DECIMAL(10, 2),  -- Gap % from previous close
    
    -- Volume metrics
    prev_day_dollar_volume DECIMAL(20, 2),
    relative_volume DECIMAL(10, 2),  -- 2-day / 20-day ratio
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicates
    CONSTRAINT unique_grid_screening_symbol_date UNIQUE(symbol, date)
);

-- Indexes for efficient querying
CREATE INDEX idx_grid_screening_date ON grid_screening(date);
CREATE INDEX idx_grid_screening_symbol ON grid_screening(symbol);
CREATE INDEX idx_grid_screening_symbol_date ON grid_screening(symbol, date);
```

### 2. Grid Market Structure Table
Stores backtest results for each parameter combination.

```sql
CREATE TABLE grid_market_structure (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    symbol VARCHAR(20) NOT NULL,
    backtest_date DATE NOT NULL,
    
    -- Strategy parameters
    strategy VARCHAR(50) DEFAULT 'market_structure',
    lower_timeframe INTEGER DEFAULT 1,  -- in minutes
    pivot_bars INTEGER NOT NULL,
    
    -- Key performance metrics
    total_return DECIMAL(10, 2),
    sharpe_ratio DECIMAL(10, 2),
    max_drawdown DECIMAL(10, 2),
    win_rate DECIMAL(5, 2),
    profit_factor DECIMAL(10, 2),
    total_trades INTEGER,
    
    -- Full statistics JSON for detailed analysis
    statistics JSONB,
    
    -- Execution metadata
    execution_time_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Unique constraint to prevent duplicate runs
    CONSTRAINT unique_grid_ms_symbol_date_params UNIQUE(symbol, backtest_date, pivot_bars)
);

-- Indexes for analysis
CREATE INDEX idx_grid_ms_symbol_date ON grid_market_structure(symbol, backtest_date);
CREATE INDEX idx_grid_ms_pivot_bars ON grid_market_structure(pivot_bars);
CREATE INDEX idx_grid_ms_total_return ON grid_market_structure(total_return DESC);
CREATE INDEX idx_grid_ms_sharpe_ratio ON grid_market_structure(sharpe_ratio DESC);
```

## Implementation Components

### 1. Grid Screening Calculator
**File**: `backend/app/services/grid_screening_calculator.py`

**Responsibilities**:
- Fetch all active symbols for a given date
- Calculate screening values using existing filters
- Store results in `grid_screening` table
- Parallel execution (10 symbols at a time)
- Skip symbols that already have data for the date

**Key Methods**:
```python
async def calculate_grid_screening(date: str) -> Dict[str, Any]:
    """Calculate all screening values for all symbols on given date"""
    
async def calculate_symbol_screening(symbol: str, date: str, data: np.ndarray) -> Dict[str, float]:
    """Calculate all screening values for a single symbol"""
    
async def get_existing_symbols(date: str) -> Set[str]:
    """Get symbols already processed for this date"""
    
async def store_screening_results(results: List[Dict]) -> None:
    """Bulk insert screening results to database"""
```

### 2. Grid Backtest Manager
**File**: `backend/app/services/grid_backtest_manager.py`

**Responsibilities**:
- Read symbols with screening data for given date
- Generate parameter combinations (pivot_bars: 1, 2, 3, 5, 10, 20)
- Execute backtests in parallel (10 at a time)
- Store results in `grid_market_structure` table
- Clean up output directories
- Skip symbol/parameter combinations already processed

**Key Methods**:
```python
async def run_grid_backtests(date: str) -> Dict[str, Any]:
    """Run all parameter combinations for symbols with screening data"""
    
async def get_existing_backtests(date: str) -> Set[Tuple[str, int]]:
    """Get (symbol, pivot_bars) tuples already processed"""
    
async def execute_backtest_batch(tasks: List[Dict]) -> List[Dict]:
    """Execute a batch of backtests in parallel"""
    
async def store_backtest_results(results: List[Dict]) -> None:
    """Store backtest results in database"""
```

### 3. Main Grid Analysis Script
**File**: `backend/scripts/run_grid_analysis.py`

**Responsibilities**:
- Orchestrate the entire process
- Handle command-line arguments for date range
- Process dates in reverse order (end to start)
- Progress reporting across multiple dates
- Error handling and logging

**Usage**:
```bash
# Process single date
python scripts/run_grid_analysis.py --date 2024-03-01

# Process date range (works backward from end to start)
python scripts/run_grid_analysis.py --start-date 2024-01-01 --end-date 2024-03-01
```

## Execution Flow

### Date Range Processing
1. Parse start and end dates from command line
2. Generate list of trading days between dates (excluding weekends)
3. **Process dates in reverse order** (end date to start date)
4. For each date, execute Phase 1 and Phase 2

### Phase 1: Screening Calculations
1. Fetch all active symbols for the current date (~11,000 symbols)
2. For each batch of 10 symbols:
   - Load required historical data (up to 200 days for MA200)
   - Calculate all screening values:
     - Price (close)
     - MA20, MA50, MA200
     - RSI14
     - Gap %
     - Previous day dollar volume
     - Relative volume (2/20 ratio)
   - Store results in `grid_screening` table

### Phase 2: Grid Backtesting
1. Query symbols with valid screening data for current date
2. For each symbol, generate 6 backtest tasks (pivot_bars: 1, 2, 3, 5, 10, 20)
3. For each batch of 10 backtests:
   - Execute backtests using existing infrastructure
   - Extract key metrics from results
   - Store in `grid_market_structure` table
   - Clean up output directories

### Date Processing Example
```python
# For date range: 2024-01-01 to 2024-01-05
# Processing order will be:
# 1. 2024-01-05 (Friday)
# 2. 2024-01-04 (Thursday)
# 3. 2024-01-03 (Wednesday)
# 4. 2024-01-02 (Tuesday)
# 5. 2024-01-01 (Monday)
```

## Performance Considerations

### Parallel Execution
- **Screening**: 10 symbols processed concurrently
- **Backtesting**: 10 backtests run concurrently
- **Database**: Bulk inserts for efficiency

### Resource Management
- No archiving (saves disk I/O)
- Immediate cleanup of output directories
- Reuse existing database connections

### Time Estimates
- **Per Trading Day**:
  - **Screening**: ~11,000 symbols ÷ 10 parallel = 1,100 batches
    - Estimated: 2-3 hours (assuming 5-10 seconds per batch)
  - **Backtesting**: ~11,000 symbols × 6 parameters = 66,000 backtests
    - At 10 parallel: 6,600 batches
    - Estimated: 8-12 hours (assuming 5-10 seconds per batch)
  - **Total per day**: 10-15 hours

- **For Date Range**:
  - 1 month (22 trading days): ~10-15 days of processing
  - 1 year (252 trading days): ~3-4 months of processing

## Query Examples

### Find Best Parameters by Symbol
```sql
SELECT 
    symbol,
    pivot_bars,
    total_return,
    sharpe_ratio,
    total_trades
FROM grid_market_structure
WHERE backtest_date = '2024-03-01'
    AND symbol = 'AAPL'
ORDER BY sharpe_ratio DESC;
```

### Find Best Overall Parameters
```sql
SELECT 
    pivot_bars,
    AVG(total_return) as avg_return,
    AVG(sharpe_ratio) as avg_sharpe,
    COUNT(*) as symbol_count
FROM grid_market_structure
WHERE backtest_date = '2024-03-01'
    AND total_trades > 10
GROUP BY pivot_bars
ORDER BY avg_sharpe DESC;
```

### Analyze Performance Across Date Range
```sql
SELECT 
    backtest_date,
    pivot_bars,
    AVG(total_return) as avg_return,
    AVG(sharpe_ratio) as avg_sharpe,
    COUNT(DISTINCT symbol) as symbol_count
FROM grid_market_structure
WHERE backtest_date BETWEEN '2024-01-01' AND '2024-03-01'
    AND total_trades > 10
GROUP BY backtest_date, pivot_bars
ORDER BY backtest_date DESC, avg_sharpe DESC;
```

### Correlate Screening Values with Performance
```sql
SELECT 
    gs.rsi_14,
    gs.gap_percent,
    gms.pivot_bars,
    AVG(gms.total_return) as avg_return
FROM grid_screening gs
JOIN grid_market_structure gms 
    ON gs.symbol = gms.symbol 
    AND gs.date = gms.backtest_date
WHERE gs.date = '2024-03-01'
    AND gs.rsi_14 < 30
GROUP BY gs.rsi_14, gs.gap_percent, gms.pivot_bars;
```

## Error Handling

### Screening Errors
- Log failed symbols with reasons
- Continue processing remaining symbols
- Store NULL values for failed calculations

### Backtest Errors
- Retry failed backtests once
- Log persistent failures
- Continue with remaining backtests

## Frontend Integration

### New Tab: Grid Analysis Results
**Component**: `frontend/src/components/GridAnalysisResults.tsx`

This tab will display a combined view of screening values and backtest results in a single table.

#### Combined View Query
```sql
CREATE VIEW grid_analysis_combined AS
SELECT 
    gs.symbol,
    gs.date,
    -- Screening values
    gs.price,
    gs.ma_20,
    gs.ma_50,
    gs.ma_200,
    gs.rsi_14,
    gs.gap_percent,
    gs.prev_day_dollar_volume,
    gs.relative_volume,
    -- Backtest results
    gms.pivot_bars,
    gms.total_return,
    gms.sharpe_ratio,
    gms.max_drawdown,
    gms.win_rate,
    gms.profit_factor,
    gms.total_trades,
    gms.execution_time_ms
FROM grid_screening gs
LEFT JOIN grid_market_structure gms 
    ON gs.symbol = gms.symbol 
    AND gs.date = gms.backtest_date
ORDER BY gs.date DESC, gs.symbol, gms.pivot_bars;
```

#### API Endpoint
**File**: `backend/app/api/grid_analysis.py`

```python
@router.get("/grid-analysis/combined")
async def get_combined_results(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    symbol: Optional[str] = None,
    min_sharpe: Optional[float] = None,
    pivot_bars: Optional[int] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """Get combined screening and backtest results with filtering options"""
```

#### Frontend Features
1. **Data Table with Columns**:
   - Symbol
   - Date
   - Price, MA20, MA50, MA200
   - RSI14, Gap%, Prev Day $Vol, Rel Vol
   - Pivot Bars
   - Total Return, Sharpe, Max DD
   - Win Rate, Profit Factor, Trades

2. **Filtering Options**:
   - Date range picker
   - Symbol search
   - Minimum Sharpe ratio
   - Specific pivot_bars value
   - RSI range filter
   - Gap % threshold

3. **Sorting & Grouping**:
   - Sort by any column
   - Group by symbol (show all pivot_bars variations)
   - Group by pivot_bars (compare across symbols)

4. **Export Features**:
   - Export filtered results to CSV
   - Copy selected rows

5. **Visualization Options**:
   - Heat map of Sharpe ratios by symbol and pivot_bars
   - Scatter plot of screening values vs performance

#### Implementation Files

**Backend**:
- `backend/app/api/grid_analysis.py` - API endpoints
- `backend/migrations/013_create_grid_combined_view.sql` - Database view

**Frontend**:
- `frontend/src/components/GridAnalysisResults.tsx` - Main component
- `frontend/src/services/gridAnalysisService.ts` - API client
- `frontend/src/types/gridAnalysis.ts` - TypeScript types

## Future Enhancements

1. **Resume Capability**: Track progress to resume interrupted runs
2. **Additional Strategies**: Extend to other trading strategies
3. **Real-time Updates**: WebSocket notifications for progress
4. **Caching**: Cache screening calculations for reuse
5. **Optimization**: Further parallelize based on available resources
6. **Advanced Analytics**: ML models to predict best parameters based on screening values