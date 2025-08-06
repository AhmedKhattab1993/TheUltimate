# Minute Data Loading Feature

## Overview

The universe data loader now supports loading minute-level stock data in addition to daily data. This feature enables high-frequency analysis and backtesting strategies that require intraday price movements.

## Key Features

1. **Intelligent Chunking**: Automatically splits date ranges into 30-day chunks to stay under the 50,000 bar API limit
2. **Priority-Based Loading**: Loads high-volume stocks first based on recent trading activity
3. **Concurrent Processing**: Processes up to 200 symbols simultaneously for optimal performance
4. **Resume Capability**: Can resume interrupted loads from checkpoints
5. **Efficient Storage**: Uses bulk inserts with batching for optimal database performance

## Usage Examples

### Load Historical Minute Data

```bash
# Load minute data for a date range
python scripts/universe_data_loader.py --historical --minute --start 2024-01-01 --end 2024-01-31

# Load minute data for specific symbols
python scripts/universe_data_loader.py --historical --minute --symbols AAPL,MSFT,GOOGL --start 2024-01-01 --end 2024-01-31

# Disable priority loading (process alphabetically)
python scripts/universe_data_loader.py --historical --minute --no-priority --start 2024-01-01 --end 2024-01-31
```

### Daily Updates

```bash
# Load today's minute data
python scripts/universe_data_loader.py --daily --minute

# Load specific date's minute data
python scripts/universe_data_loader.py --daily --minute --date 2024-01-15
```

### Performance Tuning

```bash
# Adjust batch size for database inserts (default: 5000 for minute data)
python scripts/universe_data_loader.py --historical --minute --batch-size 10000 --start 2024-01-01 --end 2024-01-31
```

## Implementation Details

### API Endpoint
- Uses Polygon's aggregate bars endpoint: `/v2/aggs/ticker/{symbol}/range/1/minute/{from}/{to}`
- Respects API rate limits automatically

### Date Chunking Strategy
- Default chunk size: 30 days
- Automatically reduces chunk size if hitting 50k bar limit
- Minimum chunk size: 7 days

### Priority Loading
- Queries recent daily volume data (last 30 days)
- Sorts symbols by average volume (highest first)
- Ensures most liquid stocks are loaded first

### Database Schema
Minute data is stored in the `minute_bars` table:
```sql
CREATE TABLE minute_bars (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    open NUMERIC(10, 2) NOT NULL,
    high NUMERIC(10, 2) NOT NULL,
    low NUMERIC(10, 2) NOT NULL,
    close NUMERIC(10, 2) NOT NULL,
    volume BIGINT NOT NULL,
    vwap NUMERIC(10, 4),
    transactions INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT minute_bars_symbol_time_key UNIQUE (symbol, time)
);
```

### Progress Tracking
- Checkpoint files track processed symbols
- Can resume from interruption
- Separate checkpoints for minute vs daily loads

## Performance Considerations

1. **Network**: Minute data requires many more API calls than daily data
2. **Storage**: Minute data is ~390x larger than daily data (390 bars/day vs 1)
3. **Memory**: Large batches are processed in chunks to manage memory usage
4. **Concurrency**: Limited to 200 concurrent symbol loads to prevent overwhelming the system

## Error Handling

- Automatic retry with exponential backoff
- Logs failed symbols for manual investigation
- Continues processing other symbols on individual failures
- Tracks errors in `data_fetch_errors` table

## Monitoring

Monitor progress through:
- Console output showing current symbol and progress
- Log files with detailed information
- Database coverage table showing loaded date ranges
- Checkpoint files showing resume state