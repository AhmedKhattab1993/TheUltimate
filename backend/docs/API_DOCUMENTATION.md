# Enhanced Backtest API Documentation

## Overview

The enhanced backtest API provides comprehensive access to the new backtest results schema with 40+ performance metrics. The API supports advanced filtering, sorting, pagination, and cache lookup operations.

## Base URL

```
https://your-domain.com/api/v2/backtest
```

## Authentication

All endpoints require valid authentication headers (implementation-specific).

## Enhanced Endpoints

### 1. List Backtest Results from Database

**GET** `/db/results`

Retrieve paginated backtest results with comprehensive filtering and sorting capabilities.

#### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `page` | integer | No | Page number (1-based) | `1` |
| `page_size` | integer | No | Results per page (max 100) | `20` |
| `symbol` | string | No | Filter by stock symbol | `AAPL` |
| `strategy_name` | string | No | Filter by strategy name | `MarketStructure` |
| `initial_cash` | number | No | Filter by initial cash amount | `100000` |
| `pivot_bars` | integer | No | Filter by pivot bars setting | `5` |
| `lower_timeframe` | string | No | Filter by lower timeframe | `5min` |
| `start_date` | date | No | Filter results after this date | `2024-01-01` |
| `end_date` | date | No | Filter results before this date | `2024-12-31` |
| `sort_by` | string | No | Sort field | `total_return` |
| `sort_order` | string | No | Sort direction (asc/desc) | `desc` |

#### Valid Sort Fields

- `created_at` (default)
- `total_return`
- `sharpe_ratio`
- `max_drawdown`
- `win_rate`
- `profit_factor`
- `net_profit`
- `compounding_annual_return`

#### Request Example

```http
GET /api/v2/backtest/db/results?page=1&page_size=10&symbol=AAPL&sort_by=total_return&sort_order=desc
```

#### Response Example

```json
{
  "results": [
    {
      "backtestId": "123e4567-e89b-12d3-a456-426614174000",
      "symbol": "AAPL",
      "strategyName": "MarketStructure",
      "startDate": "2024-01-01",
      "endDate": "2024-12-31",
      "initialCash": 100000,
      "resolution": "Minute",
      "pivotBars": 5,
      "lowerTimeframe": "5min",
      "finalValue": 115250.00,
      "statistics": {
        "totalReturn": 15.25,
        "netProfit": 15.25,
        "netProfitCurrency": 15250.00,
        "compoundingAnnualReturn": 14.87,
        "finalValue": 115250.00,
        "startEquity": 100000.00,
        "endEquity": 115250.00,
        "sharpeRatio": 1.34,
        "sortinoRatio": 1.89,
        "maxDrawdown": 8.75,
        "probabilisticSharpeRatio": 89.5,
        "annualStandardDeviation": 0.18,
        "annualVariance": 0.032,
        "beta": 0.87,
        "alpha": 0.052,
        "totalOrders": 245,
        "totalTrades": 123,
        "winningTrades": 78,
        "losingTrades": 45,
        "winRate": 63.4,
        "lossRate": 36.6,
        "averageWin": 2.8,
        "averageLoss": -1.4,
        "profitFactor": 1.85,
        "profitLossRatio": 2.0,
        "expectancy": 0.85,
        "informationRatio": 0.42,
        "trackingError": 0.15,
        "treynorRatio": 0.18,
        "totalFees": 125.50,
        "estimatedStrategyCapacity": 5000000.00,
        "lowestCapacityAsset": "AAPL R735QTJ8XC9X",
        "portfolioTurnover": 145.2,
        "pivotHighsDetected": 23,
        "pivotLowsDetected": 21,
        "bosSignalsGenerated": 44,
        "positionFlips": 12,
        "liquidationEvents": 0
      },
      "executionTimeMs": 2350,
      "resultPath": "db:123e4567-e89b-12d3-a456-426614174000",
      "status": "completed",
      "errorMessage": null,
      "cacheHit": false,
      "createdAt": "2024-08-17T10:30:00Z"
    }
  ],
  "totalCount": 1,
  "page": 1,
  "pageSize": 10
}
```

### 2. Get Specific Backtest Result

**GET** `/db/results/{result_id}`

Retrieve detailed information for a specific backtest result.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `result_id` | UUID | Yes | Database result ID |

#### Request Example

```http
GET /api/v2/backtest/db/results/123e4567-e89b-12d3-a456-426614174000
```

#### Response

Returns the same structure as a single result from the list endpoint, but with full details including potential equity curve data.

### 3. Cache Lookup

**GET** `/db/cache-lookup`

Perform high-performance cache lookup using the composite index on cache key parameters.

#### Query Parameters (All Required)

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `symbol` | string | Yes | Stock symbol | `AAPL` |
| `strategy_name` | string | Yes | Strategy name | `MarketStructure` |
| `start_date` | date | Yes | Backtest start date | `2024-01-01` |
| `end_date` | date | Yes | Backtest end date | `2024-12-31` |
| `initial_cash` | number | Yes | Initial cash amount | `100000` |
| `pivot_bars` | integer | Yes | Pivot bars setting | `5` |
| `lower_timeframe` | string | Yes | Lower timeframe | `5min` |

#### Request Example

```http
GET /api/v2/backtest/db/cache-lookup?symbol=AAPL&strategy_name=MarketStructure&start_date=2024-01-01&end_date=2024-12-31&initial_cash=100000&pivot_bars=5&lower_timeframe=5min
```

#### Response (Cache Hit)

Returns the same structure as the get specific result endpoint, with `cacheHit: true`.

#### Response (Cache Miss)

```json
{
  "error": "No cached backtest result found for the specified parameters",
  "detail": "Cache miss - no matching result found",
  "status": 404
}
```

### 4. Aggregated Statistics

**GET** `/db/statistics`

Get aggregated performance statistics across multiple backtest results.

#### Query Parameters

| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| `symbol` | string | No | Filter by symbol | `AAPL` |
| `strategy_name` | string | No | Filter by strategy name | `MarketStructure` |
| `start_date` | date | No | Filter results after date | `2024-01-01` |
| `end_date` | date | No | Filter results before date | `2024-12-31` |

#### Request Example

```http
GET /api/v2/backtest/db/statistics?strategy_name=MarketStructure&start_date=2024-01-01
```

#### Response Example

```json
{
  "summary": {
    "totalBacktests": 150,
    "uniqueSymbols": 45,
    "uniqueStrategies": 3,
    "cacheHitRate": 67.5,
    "profitabilityRate": 58.7,
    "dateRange": {
      "earliest": "2024-01-01T00:00:00Z",
      "latest": "2024-08-17T15:30:00Z"
    }
  },
  "performanceMetrics": {
    "returns": {
      "average": 8.45,
      "standardDeviation": 12.34,
      "minimum": -25.67,
      "maximum": 45.23
    },
    "riskMetrics": {
      "averageSharpeRatio": 0.87,
      "averageMaxDrawdown": 12.45
    },
    "tradingMetrics": {
      "averageWinRate": 61.2,
      "averageProfitFactor": 1.76,
      "averageTotalTrades": 89.5
    }
  },
  "executionMetrics": {
    "averageExecutionTimeMs": 2150.5,
    "cacheHits": 101,
    "profitableBacktests": 88
  },
  "topPerformers": [
    {
      "symbol": "AAPL",
      "strategyName": "MarketStructure",
      "totalReturn": 45.23,
      "sharpeRatio": 2.34,
      "createdAt": "2024-08-15T10:30:00Z"
    }
  ]
}
```

### 5. Delete Backtest Result

**DELETE** `/db/results/{result_id}`

Remove a backtest result from the database.

#### Path Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `result_id` | UUID | Yes | Database result ID |

#### Request Example

```http
DELETE /api/v2/backtest/db/results/123e4567-e89b-12d3-a456-426614174000
```

#### Response Example

```json
{
  "message": "Backtest result '123e4567-e89b-12d3-a456-426614174000' deleted successfully"
}
```

## Enhanced Model Structures

### BacktestStatistics Model

Complete performance metrics model with all 40+ fields:

```json
{
  "totalReturn": "number",
  "netProfit": "number",
  "netProfitCurrency": "number",
  "compoundingAnnualReturn": "number",
  "finalValue": "number",
  "startEquity": "number",
  "endEquity": "number",
  "sharpeRatio": "number",
  "sortinoRatio": "number",
  "maxDrawdown": "number",
  "probabilisticSharpeRatio": "number",
  "annualStandardDeviation": "number",
  "annualVariance": "number",
  "beta": "number",
  "alpha": "number",
  "totalOrders": "integer",
  "totalTrades": "integer",
  "winningTrades": "integer",
  "losingTrades": "integer",
  "winRate": "number",
  "lossRate": "number",
  "averageWin": "number",
  "averageLoss": "number",
  "profitFactor": "number",
  "profitLossRatio": "number",
  "expectancy": "number",
  "informationRatio": "number",
  "trackingError": "number",
  "treynorRatio": "number",
  "totalFees": "number",
  "estimatedStrategyCapacity": "number",
  "lowestCapacityAsset": "string",
  "portfolioTurnover": "number",
  "pivotHighsDetected": "integer|null",
  "pivotLowsDetected": "integer|null",
  "bosSignalsGenerated": "integer|null",
  "positionFlips": "integer|null",
  "liquidationEvents": "integer|null"
}
```

### BacktestResult Model

Enhanced result model with algorithm parameters:

```json
{
  "backtestId": "string",
  "symbol": "string",
  "strategyName": "string",
  "startDate": "date",
  "endDate": "date",
  "initialCash": "number",
  "resolution": "string",
  "pivotBars": "integer",
  "lowerTimeframe": "string",
  "finalValue": "number",
  "statistics": "BacktestStatistics",
  "executionTimeMs": "integer|null",
  "resultPath": "string|null",
  "status": "string",
  "errorMessage": "string|null",
  "cacheHit": "boolean|null",
  "orders": "array|null",
  "equityCurve": "array|null",
  "createdAt": "datetime"
}
```

## Error Handling

### Standard Error Response

```json
{
  "error": "Error message",
  "detail": "Detailed error description",
  "status": 400
}
```

### Common Error Codes

| Status | Error | Description |
|--------|-------|-------------|
| 400 | Validation Error | Invalid parameters or request format |
| 404 | Not Found | Resource not found |
| 422 | Unprocessable Entity | Valid request with semantic errors |
| 500 | Internal Server Error | Unexpected server error |

### Validation Errors

```json
{
  "error": "Validation failed",
  "detail": "pivot_bars must be greater than 0",
  "field": "pivot_bars",
  "status": 400
}
```

## Rate Limiting

- **Cache Lookups**: 1000 requests/minute per IP
- **List Queries**: 100 requests/minute per IP
- **Statistics Queries**: 50 requests/minute per IP
- **Delete Operations**: 20 requests/minute per IP

## Performance Guidelines

### Optimal Query Patterns

1. **Use cache lookups first** before executing new backtests
2. **Include symbol and strategy filters** when possible
3. **Limit page size** to 50 or fewer for large datasets
4. **Use date range filters** to limit result sets
5. **Sort by indexed fields** for better performance

### Response Times

- **Cache Lookups**: < 10ms (with composite index)
- **List Queries**: < 100ms (with proper filtering)
- **Statistics Queries**: < 500ms (depending on data volume)
- **Single Result**: < 50ms

## SDK Examples

### Python SDK Usage

```python
import asyncio
from datetime import date
from decimal import Decimal

# Cache lookup
async def check_cache():
    cache_params = {
        'symbol': 'AAPL',
        'strategy_name': 'MarketStructure',
        'start_date': '2024-01-01',
        'end_date': '2024-12-31',
        'initial_cash': 100000,
        'pivot_bars': 5,
        'lower_timeframe': '5min'
    }
    
    response = await api_client.get('/db/cache-lookup', params=cache_params)
    if response.status_code == 200:
        return response.json()  # Cache hit
    else:
        return None  # Cache miss

# List results with filtering
async def get_filtered_results():
    params = {
        'symbol': 'AAPL',
        'sort_by': 'total_return',
        'sort_order': 'desc',
        'page_size': 20
    }
    
    response = await api_client.get('/db/results', params=params)
    return response.json()
```

### JavaScript/TypeScript SDK Usage

```javascript
// Cache lookup
async function checkCache(cacheParams) {
    try {
        const response = await fetch('/api/v2/backtest/db/cache-lookup?' + 
            new URLSearchParams(cacheParams));
        
        if (response.ok) {
            return await response.json(); // Cache hit
        } else if (response.status === 404) {
            return null; // Cache miss
        } else {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }
    } catch (error) {
        console.error('Cache lookup failed:', error);
        return null;
    }
}

// Get paginated results
async function getBacktestResults(filters = {}) {
    const params = new URLSearchParams({
        page: '1',
        page_size: '20',
        sort_by: 'created_at',
        sort_order: 'desc',
        ...filters
    });
    
    const response = await fetch(`/api/v2/backtest/db/results?${params}`);
    
    if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }
    
    return await response.json();
}
```

## Migration Notes

### Backward Compatibility

The enhanced API maintains backward compatibility with existing endpoints while adding new functionality. Legacy endpoints continue to work but may not return the full set of enhanced metrics.

### Deprecated Endpoints

- `/results` (file-based) - Still supported but consider migrating to `/db/results`
- `/results/{timestamp}` - Replaced by `/db/results/{result_id}`

### Migration Checklist

1. Update client code to use new `/db/` endpoints
2. Handle additional fields in statistics object
3. Update cache lookup logic to use 7-parameter system
4. Implement error handling for enhanced validation
5. Test pagination and filtering functionality

## Future Enhancements

### Planned API Features

1. **Bulk Operations**: Batch result storage and retrieval
2. **WebSocket Streaming**: Real-time result updates
3. **Export Formats**: CSV, Excel, and PDF export options
4. **Advanced Analytics**: Correlation analysis and performance attribution
5. **Benchmarking**: Compare results against market benchmarks