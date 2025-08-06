# Bulk Endpoint Implementation Guide

## Overview

This guide details the implementation of Polygon's bulk endpoints to achieve 10x performance improvement in stock screening. We'll replace 5,161 individual API calls with 1-5 bulk calls.

## Available Bulk Endpoints

### 1. Grouped Daily Bars (Recommended)
```
GET /v2/aggs/grouped/locale/us/market/stocks/{date}
```
- Returns OHLCV data for ALL US stocks for a specific date
- Single call replaces thousands of individual calls
- Includes adjusted prices

### 2. Snapshots API
```
GET /v2/snapshot/locale/us/markets/stocks/tickers
```
- Returns current day's data for all tickers
- Includes additional metrics (day change, min/max)
- Best for current day screening

### 3. Daily Market Summary
```
GET /v1/marketstatus/daily
```
- Comprehensive daily summary
- All active tickers in one response

## Implementation Steps

### Step 1: Add Bulk Methods to PolygonClient

```python
# In app/services/polygon_client.py

async def fetch_grouped_daily_bars(
    self,
    date: str,
    include_otc: bool = False,
    adjusted: bool = True
) -> Dict[str, StockData]:
    """
    Fetch daily bars for ALL US stocks for a specific date.
    
    Args:
        date: Date in YYYY-MM-DD format
        include_otc: Include OTC stocks (default: False)
        adjusted: Return adjusted prices (default: True)
        
    Returns:
        Dictionary mapping symbol to StockData
    """
    endpoint = f"/v2/aggs/grouped/locale/us/market/stocks/{date}"
    
    params = {
        "adjusted": str(adjusted).lower(),
        "include_otc": str(include_otc).lower()
    }
    
    try:
        logger.info(f"Fetching grouped daily bars for {date}")
        data = await self._make_request(endpoint, params)
        
        if "results" not in data or not data["results"]:
            logger.warning(f"No grouped data found for {date}")
            return {}
        
        # Process results into StockData objects
        stock_data_dict = {}
        for bar in data["results"]:
            symbol = bar["T"]  # Ticker symbol
            
            # Create StockBar from grouped data
            stock_bar = StockBar(
                symbol=symbol,
                date=datetime.strptime(date, "%Y-%m-%d").date(),
                open=bar["o"],
                high=bar["h"],
                low=bar["l"],
                close=bar["c"],
                volume=bar["v"],
                vwap=bar.get("vw"),
                transactions=bar.get("n")
            )
            
            stock_data_dict[symbol] = StockData(
                symbol=symbol,
                bars=[stock_bar]
            )
        
        logger.info(f"Fetched data for {len(stock_data_dict)} stocks")
        return stock_data_dict
        
    except PolygonAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching grouped daily bars: {e}")
        raise PolygonAPIError(f"Error fetching grouped data: {str(e)}")

async def fetch_market_snapshot(
    self,
    tickers: Optional[List[str]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Fetch current market snapshot for all or specific tickers.
    
    Args:
        tickers: Optional list of tickers (None = all tickers)
        
    Returns:
        Dictionary mapping symbol to snapshot data
    """
    endpoint = "/v2/snapshot/locale/us/markets/stocks/tickers"
    
    params = {}
    if tickers:
        params["tickers"] = ",".join(tickers)
    
    try:
        logger.info("Fetching market snapshot")
        data = await self._make_request(endpoint, params)
        
        if "tickers" not in data:
            logger.warning("No snapshot data found")
            return {}
        
        # Process into dictionary
        snapshot_dict = {}
        for ticker_data in data["tickers"]:
            symbol = ticker_data["ticker"]
            snapshot_dict[symbol] = ticker_data
        
        logger.info(f"Fetched snapshot for {len(snapshot_dict)} stocks")
        return snapshot_dict
        
    except PolygonAPIError:
        raise
    except Exception as e:
        logger.error(f"Error fetching market snapshot: {e}")
        raise PolygonAPIError(f"Error fetching snapshot: {str(e)}")

async def fetch_date_range_bulk(
    self,
    start_date: date,
    end_date: date,
    adjusted: bool = True
) -> Dict[str, StockData]:
    """
    Fetch data for all stocks across a date range using bulk endpoints.
    
    Args:
        start_date: Start date
        end_date: End date
        adjusted: Use adjusted prices
        
    Returns:
        Dictionary mapping symbol to StockData with multiple bars
    """
    # Calculate number of trading days
    current_date = start_date
    all_dates = []
    
    while current_date <= end_date:
        # Skip weekends (basic check - doesn't account for holidays)
        if current_date.weekday() < 5:  # Monday = 0, Friday = 4
            all_dates.append(current_date.strftime("%Y-%m-%d"))
        current_date += timedelta(days=1)
    
    logger.info(f"Fetching bulk data for {len(all_dates)} trading days")
    
    # Fetch each date in parallel
    tasks = []
    for date_str in all_dates:
        tasks.append(self.fetch_grouped_daily_bars(date_str, adjusted=adjusted))
    
    # Gather results
    daily_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Combine results by symbol
    combined_data = {}
    
    for date_str, result in zip(all_dates, daily_results):
        if isinstance(result, Exception):
            logger.error(f"Error fetching data for {date_str}: {result}")
            continue
            
        for symbol, stock_data in result.items():
            if symbol not in combined_data:
                combined_data[symbol] = StockData(symbol=symbol, bars=[])
            
            # Add bars from this date
            combined_data[symbol].bars.extend(stock_data.bars)
    
    # Sort bars by date for each symbol
    for stock_data in combined_data.values():
        stock_data.bars.sort(key=lambda x: x.date)
    
    logger.info(f"Combined data for {len(combined_data)} stocks")
    return combined_data
```

### Step 2: Refactor Screening API Endpoint

```python
# In app/api/screener.py

@router.post("/screen", response_model=ScreenResponse)
async def screen_stocks(
    request: ScreenRequest,
    polygon_client: PolygonClient = Depends(get_polygon_client)
):
    """Optimized screening using bulk endpoints"""
    start_time = time.time()
    
    # Determine if we need historical data or just current day
    is_single_day = request.start_date == request.end_date
    
    try:
        if is_single_day:
            # Use grouped daily bars for single day
            logger.info(f"Using bulk endpoint for single day: {request.start_date}")
            
            stock_data_dict = await polygon_client.fetch_grouped_daily_bars(
                date=request.start_date.strftime("%Y-%m-%d"),
                include_otc=False,
                adjusted=True
            )
            
            # Filter to requested symbols if specified
            if request.symbols and not request.use_all_us_stocks:
                stock_data_dict = {
                    k: v for k, v in stock_data_dict.items() 
                    if k in request.symbols
                }
        else:
            # For date ranges, use bulk fetch
            logger.info(f"Using bulk endpoints for date range: {request.start_date} to {request.end_date}")
            
            stock_data_dict = await polygon_client.fetch_date_range_bulk(
                start_date=request.start_date,
                end_date=request.end_date,
                adjusted=True
            )
            
            # Filter to requested symbols if specified
            if request.symbols and not request.use_all_us_stocks:
                stock_data_dict = {
                    k: v for k, v in stock_data_dict.items() 
                    if k in request.symbols
                }
        
        # Convert to list for screening engine
        stock_data_list = list(stock_data_dict.values())
        
        # Log performance metrics
        fetch_time = time.time() - start_time
        logger.info(f"Bulk fetch completed in {fetch_time:.2f}s for {len(stock_data_list)} stocks")
        
        # Apply filters (existing code)
        # ... rest of the screening logic remains the same ...
        
    except Exception as e:
        logger.error(f"Error in bulk screening: {e}")
        raise
```

### Step 3: Optimize Pre-filtering

```python
# Add pre-filtering capabilities

async def fetch_grouped_daily_bars_filtered(
    self,
    date: str,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    min_volume: Optional[float] = None,
    adjusted: bool = True
) -> Dict[str, StockData]:
    """
    Fetch daily bars with client-side filtering for performance.
    
    Pre-filters data to reduce memory usage and processing time.
    """
    # Fetch all data
    all_data = await self.fetch_grouped_daily_bars(date, adjusted=adjusted)
    
    # Apply filters
    filtered_data = {}
    
    for symbol, stock_data in all_data.items():
        if not stock_data.bars:
            continue
            
        bar = stock_data.bars[0]
        
        # Apply price filter
        if min_price is not None and bar.close < min_price:
            continue
        if max_price is not None and bar.close > max_price:
            continue
            
        # Apply volume filter
        if min_volume is not None and bar.volume < min_volume:
            continue
        
        filtered_data[symbol] = stock_data
    
    logger.info(f"Pre-filtered from {len(all_data)} to {len(filtered_data)} stocks")
    return filtered_data
```

### Step 4: Performance Monitoring

```python
# Add performance tracking

class BulkScreeningMetrics:
    def __init__(self):
        self.metrics = {
            'bulk_api_calls': 0,
            'individual_api_calls': 0,
            'total_symbols_fetched': 0,
            'pre_filter_removed': 0,
            'fetch_time_ms': 0,
            'screen_time_ms': 0,
            'total_time_ms': 0
        }
    
    def log_bulk_fetch(self, num_symbols: int, time_ms: float):
        self.metrics['bulk_api_calls'] += 1
        self.metrics['total_symbols_fetched'] += num_symbols
        self.metrics['fetch_time_ms'] += time_ms
    
    def calculate_improvement(self):
        # Compare to individual API calls
        estimated_individual_time = self.metrics['total_symbols_fetched'] * 5.4  # ms per symbol
        actual_time = self.metrics['total_time_ms']
        improvement_factor = estimated_individual_time / actual_time if actual_time > 0 else 0
        
        return {
            'improvement_factor': improvement_factor,
            'time_saved_seconds': (estimated_individual_time - actual_time) / 1000,
            'api_calls_saved': self.metrics['total_symbols_fetched'] - self.metrics['bulk_api_calls']
        }
```

## Testing the Implementation

### 1. Unit Test for Bulk Fetch
```python
async def test_bulk_fetch():
    """Test bulk endpoint performance"""
    client = PolygonClient()
    
    # Test single day fetch
    start = time.time()
    data = await client.fetch_grouped_daily_bars("2025-08-01")
    elapsed = time.time() - start
    
    print(f"Fetched {len(data)} stocks in {elapsed:.2f}s")
    print(f"That's {len(data)/elapsed:.1f} symbols/second")
    
    # Compare to individual fetches (sample)
    sample_symbols = list(data.keys())[:10]
    start = time.time()
    for symbol in sample_symbols:
        await client.fetch_historical_data(
            symbol, 
            date(2025, 8, 1), 
            date(2025, 8, 1)
        )
    individual_time = time.time() - start
    
    print(f"Individual fetch for 10 symbols: {individual_time:.2f}s")
    print(f"Projected time for {len(data)} symbols: {individual_time * len(data) / 10:.2f}s")
```

### 2. Integration Test
```python
async def test_full_screening_with_bulk():
    """Test complete screening with bulk endpoints"""
    
    request = ScreenRequest(
        start_date=date(2025, 8, 1),
        end_date=date(2025, 8, 1),
        use_all_us_stocks=True,
        filters={
            "price_range": {"min_price": 2.0, "max_price": 10.0},
            "relative_volume": {"min_relative_volume": 2.0}
        }
    )
    
    # Run screening
    start = time.time()
    response = await screen_stocks(request, polygon_client)
    elapsed = time.time() - start
    
    print(f"Screening completed in {elapsed:.2f}s")
    print(f"Found {response.total_qualifying_stocks} qualifying stocks")
    print(f"Screened {response.total_symbols_screened} total symbols")
```

## Expected Results

### Performance Improvements
- **API Calls**: 5,161 → 1 (for single day)
- **Network Time**: ~25s → ~2s
- **Total Time**: ~28s → <10s
- **Throughput**: 185 symbols/sec → 2,500+ symbols/sec

### Resource Usage
- **Memory**: Higher peak usage (all data in memory)
- **Network**: Single large response vs many small ones
- **CPU**: More efficient batch processing

## Rollback Plan

If bulk endpoints have issues:
1. Feature flag to toggle bulk vs individual fetching
2. Fallback to individual fetches on bulk endpoint errors
3. Gradual rollout with monitoring

```python
# Feature flag implementation
USE_BULK_ENDPOINTS = settings.get("USE_BULK_ENDPOINTS", True)

if USE_BULK_ENDPOINTS:
    data = await fetch_grouped_daily_bars(date)
else:
    data = await fetch_batch_historical_data(symbols, start_date, end_date)
```

## Next Steps

1. Implement bulk endpoint methods
2. Add comprehensive error handling
3. Test with production data volumes
4. Monitor API quotas and limits
5. Implement caching for bulk responses
6. Add metrics and alerting