# Backtest Results Cache System

## Overview

The cache system is designed to avoid redundant backtest computations by storing results based on key parameters that uniquely identify a backtest configuration. The system uses a composite database index for optimal cache lookup performance.

## Cache Key Parameters

The cache system uses exactly **7 parameters** to uniquely identify a backtest configuration:

### Primary Cache Key Components

1. **`symbol`** (VARCHAR) - Stock symbol being tested
   - Example: `"AAPL"`, `"TSLA"`, `"SPY"`
   - Case-sensitive matching

2. **`strategy_name`** (VARCHAR) - Strategy algorithm name
   - Example: `"MarketStructure"`, `"BuyAndHold"`
   - Identifies which trading algorithm was used

3. **`start_date`** (DATE) - Backtest start date
   - Format: `YYYY-MM-DD`
   - Example: `"2024-01-01"`

4. **`end_date`** (DATE) - Backtest end date
   - Format: `YYYY-MM-DD`
   - Example: `"2024-12-31"`

5. **`initial_cash`** (DECIMAL) - Starting capital amount
   - Example: `100000.00`, `250000.00`
   - Exact decimal matching required

6. **`pivot_bars`** (INTEGER) - Number of bars for pivot detection
   - Example: `5`, `10`, `20`
   - Strategy-specific parameter

7. **`lower_timeframe`** (VARCHAR) - Analysis timeframe
   - Example: `"5min"`, `"15min"`, `"1hour"`
   - Defines the resolution for technical analysis

## Composite Index Structure

### Primary Cache Index

```sql
CREATE INDEX idx_backtest_cache_key ON market_structure_results 
(symbol, strategy_name, start_date, end_date, initial_cash, pivot_bars, lower_timeframe);
```

### Index Benefits

- **Sub-millisecond lookups** for exact cache key matches
- **Ordered by selectivity** - most selective columns first
- **Covers all cache key parameters** in a single index scan
- **Supports partial matches** for filtered queries

## Cache Lookup Process

### 1. Hash Generation

Cache requests generate a SHA256 hash from the 7 parameters:

```python
def calculate_cache_hash(symbol: str, strategy_name: str, start_date: date, 
                        end_date: date, initial_cash: Decimal, 
                        pivot_bars: int, lower_timeframe: str) -> str:
    data = {
        'symbol': symbol,
        'strategy_name': strategy_name,
        'date_range': {
            'start': start_date.isoformat(),
            'end': end_date.isoformat()
        },
        'parameters': {
            'initial_cash': float(initial_cash),
            'pivot_bars': pivot_bars,
            'lower_timeframe': lower_timeframe
        }
    }
    json_str = json.dumps(data, sort_keys=True)
    return hashlib.sha256(json_str.encode()).hexdigest()
```

### 2. Database Lookup

```sql
SELECT * FROM market_structure_results 
WHERE symbol = $1 
  AND strategy_name = $2 
  AND start_date = $3 
  AND end_date = $4 
  AND initial_cash = $5 
  AND pivot_bars = $6 
  AND lower_timeframe = $7
ORDER BY created_at DESC
LIMIT 1;
```

### 3. Cache Hit Detection

- **Cache Hit**: Exact match found, return stored results
- **Cache Miss**: No match found, execute new backtest
- **Cache Invalidation**: Results older than TTL are ignored

## API Integration

### Cache Lookup Endpoint

```http
GET /api/v2/backtest/db/cache-lookup?symbol=AAPL&strategy_name=MarketStructure&start_date=2024-01-01&end_date=2024-12-31&initial_cash=100000&pivot_bars=5&lower_timeframe=5min
```

**Response (Cache Hit):**
```json
{
  "backtestId": "uuid-here",
  "symbol": "AAPL",
  "strategyName": "MarketStructure",
  "startDate": "2024-01-01",
  "endDate": "2024-12-31",
  "initialCash": 100000,
  "pivotBars": 5,
  "lowerTimeframe": "5min",
  "statistics": {
    "totalReturn": 15.25,
    "sharpeRatio": 1.34,
    "maxDrawdown": -8.7,
    // ... all performance metrics
  },
  "cacheHit": true,
  "createdAt": "2024-08-17T10:30:00Z"
}
```

**Response (Cache Miss):**
```json
{
  "error": "No cached backtest result found for the specified parameters",
  "status": 404
}
```

## Cache Storage Workflow

### 1. Pre-Execution Check

Before running a backtest:

```python
cache_request = CachedBacktestRequest(
    symbol="AAPL",
    strategy_name="MarketStructure",
    start_date=date(2024, 1, 1),
    end_date=date(2024, 12, 31),
    initial_cash=Decimal("100000.00"),
    pivot_bars=5,
    lower_timeframe="5min"
)

# Check for existing result
cached_result = await cache_service.get_cached_backtest(cache_request)
if cached_result:
    return cached_result  # Cache hit
```

### 2. Post-Execution Storage

After successful backtest execution:

```python
# Store comprehensive results
result = CachedBacktestResult(
    backtest_id=uuid4(),
    symbol=request.symbol,
    strategy_name=request.strategy_name,
    # ... all cache key parameters
    # ... all performance metrics from LEAN output
    cache_hit=False,
    created_at=datetime.utcnow()
)

await cache_service.store_backtest_result(result)
```

## Cache Configuration

### Time-to-Live (TTL)

```yaml
# pipeline_config.yaml
caching:
  enabled: true
  backtest_ttl_days: 7  # Results valid for 7 days
  cleanup_interval_hours: 6  # Clean expired results every 6 hours
```

### Cache Policies

1. **Exact Match Policy**: All 7 parameters must match exactly
2. **TTL Policy**: Results expire after configured days
3. **Cleanup Policy**: Automatic removal of expired entries
4. **Storage Policy**: Full result storage for comprehensive caching

## Performance Metrics

### Cache Effectiveness

Track cache performance with these metrics:

```sql
-- Cache hit rate
SELECT 
    COUNT(CASE WHEN cache_hit = true THEN 1 END) * 100.0 / COUNT(*) as hit_rate_percent,
    COUNT(*) as total_requests,
    COUNT(CASE WHEN cache_hit = true THEN 1 END) as cache_hits,
    COUNT(CASE WHEN cache_hit = false THEN 1 END) as cache_misses
FROM market_structure_results 
WHERE created_at >= NOW() - INTERVAL '7 days';
```

### Query Performance

```sql
-- Index usage verification
EXPLAIN (ANALYZE, BUFFERS) 
SELECT * FROM market_structure_results 
WHERE symbol = 'AAPL' 
  AND strategy_name = 'MarketStructure'
  AND start_date = '2024-01-01'
  AND end_date = '2024-12-31'
  AND initial_cash = 100000
  AND pivot_bars = 5
  AND lower_timeframe = '5min';
```

Expected output should show:
- `Index Scan using idx_backtest_cache_key`
- Execution time < 1ms for cache lookups

## Cache Management

### Manual Cache Operations

```python
# Clear cache for specific symbol
await cache_service.clear_symbol_cache("AAPL")

# Clear cache for date range
await cache_service.clear_date_range_cache(
    start_date=date(2024, 1, 1),
    end_date=date(2024, 3, 31)
)

# Get cache statistics
stats = await cache_service.get_cache_statistics()
```

### Cache Invalidation Triggers

1. **Strategy Code Changes**: Clear all results for affected strategy
2. **Data Updates**: Clear results when historical data is revised
3. **Manual Invalidation**: Administrative cache clearing
4. **TTL Expiration**: Automatic cleanup of old results

## Best Practices

### For Developers

1. **Always check cache first** before executing backtests
2. **Use exact parameter matching** - no fuzzy matching
3. **Store complete results** including all metrics
4. **Handle cache misses gracefully** with fallback to execution
5. **Monitor cache hit rates** to optimize parameter choices

### For System Administrators

1. **Monitor index performance** regularly
2. **Set appropriate TTL values** based on data update frequency
3. **Implement cache warming** for common parameter combinations
4. **Plan for cache storage growth** with appropriate disk space
5. **Regular cleanup scheduling** to prevent unlimited growth

## Troubleshooting

### Common Issues

**Low Cache Hit Rate:**
- Check parameter standardization (e.g., date formats)
- Verify exact decimal matching for `initial_cash`
- Ensure consistent `lower_timeframe` formatting

**Slow Cache Lookups:**
- Verify composite index exists and is being used
- Check for table bloat and consider VACUUM
- Monitor concurrent query load

**Cache Inconsistencies:**
- Verify TTL configuration
- Check for manual data modifications
- Ensure atomic cache operations

### Debugging Queries

```sql
-- Check cache key distribution
SELECT symbol, strategy_name, COUNT(*) as cached_results
FROM market_structure_results 
GROUP BY symbol, strategy_name
ORDER BY cached_results DESC;

-- Find duplicate cache entries (should be none)
SELECT symbol, strategy_name, start_date, end_date, 
       initial_cash, pivot_bars, lower_timeframe, COUNT(*)
FROM market_structure_results 
GROUP BY symbol, strategy_name, start_date, end_date, 
         initial_cash, pivot_bars, lower_timeframe
HAVING COUNT(*) > 1;
```

## Migration and Upgrades

### Adding New Cache Parameters

When adding new cache key parameters:

1. **Update the composite index** to include new parameters
2. **Modify hash calculation** to include new fields
3. **Clear existing cache** or provide migration logic
4. **Update API documentation** with new required parameters

### Backward Compatibility

The cache system maintains backward compatibility by:

1. **Graceful degradation** when optional parameters are missing
2. **Version-aware hashing** for different parameter sets
3. **Legacy parameter support** during transition periods

## Future Enhancements

### Planned Improvements

1. **Hierarchical Caching**: Multi-level cache with in-memory and database tiers
2. **Distributed Caching**: Redis integration for high-performance scenarios
3. **Intelligent Prefetching**: Predictive cache warming based on usage patterns
4. **Cache Compression**: Compress stored results to reduce storage overhead
5. **Cross-Strategy Caching**: Share common calculations across strategies