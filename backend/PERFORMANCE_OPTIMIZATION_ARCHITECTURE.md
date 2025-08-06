# Stock Screener Performance Optimization Architecture

## Executive Summary

This document outlines optimizations to achieve sub-10 second stock screening performance for 5,161 US stocks without using caching. The current implementation takes 27.92 seconds (184.9 symbols/second) using 100 concurrent API requests. Our target is to achieve <10 seconds through architectural improvements and API optimization.

## Current Performance Analysis

### Bottlenecks Identified

1. **Individual API Calls**: Each stock requires a separate API call to `/v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}`
   - 5,161 individual HTTP requests
   - ~5.4ms average per request (including network latency)
   - Linear scaling with number of symbols

2. **Network Overhead**: 
   - HTTP/1.1 connection setup and teardown
   - TLS handshake for each new connection
   - Request/response headers overhead
   - JSON parsing for each response

3. **Rate Limiting**: Currently set to respect Polygon's rate limits
   - Adds artificial delays when hitting limits
   - Reduces effective parallelism

4. **Data Processing**: 
   - Sequential processing after parallel fetch
   - ThreadPoolExecutor with only 4-8 workers for screening
   - Redundant numpy conversions

## Optimization Strategies

### 1. Use Polygon's Bulk Endpoints (Highest Impact)

**Implementation**: Replace individual ticker calls with bulk market data endpoints

```python
# Instead of 5,161 individual calls:
# GET /v2/aggs/ticker/{symbol}/range/1/day/{start}/{end}

# Use ONE call:
# GET /v2/aggs/grouped/locale/us/market/stocks/{date}
# Returns ALL stocks for a given date

# Or use Snapshot API:
# GET /v2/snapshot/locale/us/markets/stocks/tickers
# Returns current day data for ALL tickers
```

**Expected Performance Gain**: 
- Reduce API calls from 5,161 to 1-5 calls
- Time reduction: ~25 seconds → ~2-3 seconds
- 10x improvement from this change alone

### 2. Aggressive Parallelization

**Implementation**:
```python
# Increase connection pool limits
self.client = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=5.0),
    limits=httpx.Limits(
        max_keepalive_connections=200,  # From 50
        max_connections=500,            # From 100
        keepalive_expiry=30.0
    ),
    http2=True  # Enable HTTP/2
)

# Increase concurrent requests
max_concurrent=500  # From 100

# Use asyncio.TaskGroup for better concurrency
async with asyncio.TaskGroup() as tg:
    for symbol in symbols:
        tg.create_task(fetch_symbol_data(symbol))
```

**Expected Performance Gain**: 
- 2-3x improvement in throughput
- Time reduction: ~27 seconds → ~10-15 seconds

### 3. Connection Pooling & HTTP/2

**Implementation**:
- Enable HTTP/2 for multiplexing
- Persistent connections with keep-alive
- DNS caching
- Pre-warm connections before bulk operations

```python
# Pre-warm connections
async def prewarm_connections(self, num_connections=10):
    """Pre-establish connections to reduce latency"""
    tasks = []
    for _ in range(num_connections):
        tasks.append(self.client.get(self.base_url))
    await asyncio.gather(*tasks, return_exceptions=True)
```

**Expected Performance Gain**: 
- 20-30% reduction in network overhead
- Time reduction: ~27 seconds → ~20 seconds

### 4. Smart Data Fetching

**Implementation**:
- Request only required fields
- Use compressed responses
- Implement field filtering

```python
params = {
    "adjusted": "true",
    "sort": "asc",
    "limit": 50000,
    "fields": "t,o,h,l,c,v,vw"  # Only required fields
}

headers = {
    "Accept-Encoding": "gzip, deflate, br",
    "Accept": "application/json"
}
```

**Expected Performance Gain**: 
- 15-20% reduction in data transfer
- Faster JSON parsing

### 5. Stream Processing Architecture

**Implementation**:
```python
async def stream_and_screen(self):
    """Process stocks as data arrives instead of waiting for all"""
    
    screening_queue = asyncio.Queue(maxsize=1000)
    
    # Producer: Fetch data and queue
    async def producer():
        async for stock_data in self.fetch_stocks_stream():
            await screening_queue.put(stock_data)
    
    # Consumer: Screen as data arrives
    async def consumer():
        while True:
            stock_data = await screening_queue.get()
            result = await self.screen_single(stock_data)
            if result.qualifies:
                yield result
    
    # Run producer and consumers concurrently
    await asyncio.gather(
        producer(),
        *[consumer() for _ in range(10)]
    )
```

**Expected Performance Gain**: 
- Start returning results immediately
- Better CPU utilization
- Perceived performance improvement

### 6. Pre-filtering Strategies

**Implementation**:
- Use Polygon's query parameters to pre-filter
- Skip symbols that can't possibly qualify

```python
# Use market cap and volume filters in API request
params = {
    "market_cap.gte": min_market_cap,
    "volume.gte": min_volume,
    "price.gte": min_price,
    "price.lte": max_price
}
```

**Expected Performance Gain**: 
- Reduce data volume by 50-70%
- Fewer symbols to process

## Recommended Implementation Plan

### Phase 1: Bulk Endpoints (Week 1)
1. Implement grouped aggregates endpoint
2. Refactor data fetching layer
3. Update screening engine for bulk data
4. **Expected Result**: <15 seconds

### Phase 2: Enhanced Parallelization (Week 2)
1. Upgrade to HTTP/2
2. Increase connection pools
3. Implement connection pre-warming
4. **Expected Result**: <10 seconds

### Phase 3: Stream Processing (Week 3)
1. Implement streaming architecture
2. Add pre-filtering
3. Optimize data structures
4. **Expected Result**: <7 seconds

## Performance Projections

| Optimization | Current | Phase 1 | Phase 2 | Phase 3 |
|-------------|---------|---------|---------|---------|
| API Calls | 5,161 | 5 | 5 | 5 |
| Time (seconds) | 27.92 | 12-15 | 8-10 | 5-7 |
| Throughput (symbols/sec) | 184.9 | 344-430 | 516-645 | 737-1032 |

## Architecture Improvements

### 1. Data Pipeline Architecture
```
[Polygon Bulk API] → [Stream Processor] → [Filter Engine] → [Results]
                           ↓
                    [Pre-filter Logic]
                           ↓
                    [Parallel Screeners]
```

### 2. Memory Management
- Use memory-mapped numpy arrays for large datasets
- Implement zero-copy data passing
- Pool and reuse numpy arrays

### 3. Filter Optimization
- Compile filters to numpy expressions
- Use numba JIT compilation for hot paths
- Vectorize all operations

## Code Examples

### Bulk Data Fetching
```python
async def fetch_all_stocks_bulk(self, date: str) -> Dict[str, StockData]:
    """Fetch all US stocks data in a single request"""
    endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{date}"
    
    params = {
        "adjusted": "true",
        "include_otc": "false"
    }
    
    data = await self._make_request(endpoint, params)
    
    # Process bulk response
    stocks = {}
    for result in data.get("results", []):
        symbol = result["T"]
        stocks[symbol] = StockData(
            symbol=symbol,
            bars=[self._parse_bar(symbol, result)]
        )
    
    return stocks
```

### Parallel Screening with Streaming
```python
async def screen_with_streaming(self, filters: List[BaseFilter]):
    """Screen stocks with streaming results"""
    
    # Fetch market snapshot
    snapshot_data = await self.fetch_market_snapshot()
    
    # Create screening tasks
    async def screen_batch(symbols_batch):
        results = []
        for symbol, data in symbols_batch:
            if self.pre_filter(symbol, data):
                result = await self.apply_filters(symbol, data, filters)
                if result.qualifies:
                    results.append(result)
        return results
    
    # Process in batches
    batch_size = 100
    tasks = []
    
    for i in range(0, len(snapshot_data), batch_size):
        batch = list(snapshot_data.items())[i:i+batch_size]
        tasks.append(screen_batch(batch))
    
    # Stream results as they complete
    for coro in asyncio.as_completed(tasks):
        batch_results = await coro
        for result in batch_results:
            yield result
```

## Monitoring and Metrics

### Key Performance Indicators
1. Total execution time
2. API calls per second
3. Symbols processed per second
4. Memory usage
5. CPU utilization
6. Network bandwidth usage

### Performance Dashboard
```python
class PerformanceMonitor:
    def __init__(self):
        self.metrics = {
            'api_calls': 0,
            'symbols_processed': 0,
            'start_time': None,
            'api_response_times': []
        }
    
    def log_api_call(self, response_time):
        self.metrics['api_calls'] += 1
        self.metrics['api_response_times'].append(response_time)
    
    def get_summary(self):
        elapsed = time.time() - self.metrics['start_time']
        return {
            'total_time': elapsed,
            'api_calls': self.metrics['api_calls'],
            'avg_api_response': np.mean(self.metrics['api_response_times']),
            'throughput': self.metrics['symbols_processed'] / elapsed
        }
```

## Conclusion

By implementing these optimizations in phases, we can achieve:
- **Phase 1**: Reduce screening time from 27.92s to ~15s using bulk endpoints
- **Phase 2**: Further reduce to <10s with enhanced parallelization
- **Phase 3**: Achieve 5-7s with streaming and pre-filtering

The most impactful change is using Polygon's bulk endpoints, which alone can provide a 10x improvement. Combined with other optimizations, we can exceed the target performance of sub-10 second screening.