# Stock Screener API Documentation

## Overview

The Stock Screener API provides high-performance stock screening capabilities using historical market data from Polygon.io. The API allows you to filter stocks based on various technical criteria including volume, price changes, and moving averages.

## Base URL

```
http://localhost:8000/api/v1
```

## Authentication

Currently, the API does not require authentication. The Polygon.io API key should be configured on the server side via the `POLYGON_API_KEY` environment variable.

## Endpoints

### 1. Health Check

Check the API health status and external service connectivity.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:45.123456",
  "version": "1.0.0",
  "checks": {
    "polygon_api": {
      "status": "healthy",
      "market_status": "open"
    }
  },
  "response_time_ms": 145.23
}
```

### 2. Get Available Symbols

Retrieve the list of symbols available for screening.

**Endpoint:** `GET /symbols`

**Response:**
```json
[
  "AAPL",
  "MSFT",
  "GOOGL",
  "AMZN",
  "META",
  "TSLA",
  "NVDA",
  "..."
]
```

### 3. Get Available Filters

Get detailed information about available filters and their parameters.

**Endpoint:** `GET /filters`

**Response:**
```json
{
  "volume": {
    "description": "Filter stocks based on average trading volume",
    "parameters": {
      "min_average": {
        "type": "float",
        "required": false,
        "description": "Minimum average volume",
        "minimum": 0
      },
      "max_average": {
        "type": "float",
        "required": false,
        "description": "Maximum average volume",
        "minimum": 0
      },
      "lookback_days": {
        "type": "integer",
        "required": false,
        "default": 20,
        "description": "Number of days to calculate average",
        "minimum": 1,
        "maximum": 252
      }
    }
  },
  "price_change": {
    "description": "Filter stocks based on price change percentage",
    "parameters": {
      "min_change": {
        "type": "float",
        "required": false,
        "description": "Minimum price change percentage"
      },
      "max_change": {
        "type": "float",
        "required": false,
        "description": "Maximum price change percentage"
      },
      "period_days": {
        "type": "integer",
        "required": false,
        "default": 1,
        "description": "Period for calculating change",
        "minimum": 1,
        "maximum": 252
      }
    }
  },
  "moving_average": {
    "description": "Filter stocks based on price position relative to moving average",
    "parameters": {
      "period": {
        "type": "integer",
        "required": false,
        "default": 50,
        "description": "Moving average period in days",
        "minimum": 2,
        "maximum": 200
      },
      "condition": {
        "type": "string",
        "required": false,
        "default": "above",
        "description": "Price condition relative to MA",
        "enum": ["above", "below", "crosses_above", "crosses_below"]
      }
    }
  }
}
```

### 4. Screen Stocks

Main endpoint for screening stocks based on specified filters.

**Endpoint:** `POST /screen`

**Request Body:**
```json
{
  "start_date": "2024-01-01",
  "end_date": "2024-01-15",
  "symbols": ["AAPL", "MSFT", "GOOGL"],  // Optional, defaults to preset universe
  "filters": {
    "volume": {
      "min_average": 10000000,
      "lookback_days": 20
    },
    "price_change": {
      "min_change": -2.0,
      "max_change": 5.0,
      "period_days": 1
    },
    "moving_average": {
      "period": 50,
      "condition": "above"
    }
  }
}
```

**Response:**
```json
{
  "request_date": "2024-01-15",
  "total_symbols_screened": 30,
  "total_qualifying_stocks": 12,
  "results": [
    {
      "symbol": "AAPL",
      "qualifying_dates": ["2024-01-05", "2024-01-08", "2024-01-12"],
      "metrics": {
        "avg_volume_20d_mean": 52341256.5,
        "avg_volume_20d_max": 65234123.0,
        "avg_volume_20d_min": 41234567.0,
        "price_change_mean": 1.23,
        "price_change_std": 0.85,
        "price_change_max": 3.45,
        "price_change_min": -1.2,
        "sma_50_value_mean": 175.43,
        "distance_from_sma_50_mean": 2.34,
        "distance_from_sma_50_std": 1.23
      }
    }
  ],
  "execution_time_ms": 3456.78
}
```

## Filter Combinations

When multiple filters are specified, they are combined using AND logic. A stock must pass ALL filters to be included in the results.

### Example: High Volume Breakout Screen

```json
{
  "filters": {
    "volume": {
      "min_average": 20000000,
      "lookback_days": 10
    },
    "price_change": {
      "min_change": 3.0,
      "max_change": 10.0,
      "period_days": 1
    },
    "moving_average": {
      "period": 20,
      "condition": "above"
    }
  }
}
```

This screens for stocks with:
- 10-day average volume > 20 million shares
- Daily price gain between 3% and 10%
- Price above 20-day moving average

## Error Handling

The API returns appropriate HTTP status codes and error messages:

### Common Error Responses

**400 Bad Request**
```json
{
  "error": "Validation Error",
  "message": "end_date must be after start_date"
}
```

**503 Service Unavailable**
```json
{
  "error": "External API Error",
  "message": "Polygon API rate limit exceeded",
  "details": {
    "status": "ERROR",
    "error": "Rate limit exceeded"
  }
}
```

**500 Internal Server Error**
```json
{
  "error": "Internal Server Error",
  "message": "An unexpected error occurred"
}
```

## Rate Limiting

The API inherits rate limits from the Polygon.io API:
- Free tier: 5 requests per minute
- Paid tiers: Higher limits based on subscription

The API automatically handles rate limiting and will queue requests appropriately.

## Performance Considerations

1. **Date Ranges**: Larger date ranges require more data and processing time
2. **Symbol Count**: Screening more symbols increases execution time linearly
3. **Filter Complexity**: Complex filters (especially moving averages) require more computation
4. **Caching**: Currently no caching is implemented; repeated requests fetch fresh data

## Usage Examples

### Python Example

```python
import httpx
import asyncio
from datetime import date, timedelta

async def screen_stocks():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/api/v1/screen",
            json={
                "start_date": str(date.today() - timedelta(days=30)),
                "end_date": str(date.today()),
                "filters": {
                    "volume": {"min_average": 10000000},
                    "moving_average": {"period": 50, "condition": "above"}
                }
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"Found {data['total_qualifying_stocks']} qualifying stocks")
            for result in data['results']:
                print(f"{result['symbol']}: {len(result['qualifying_dates'])} qualifying days")

asyncio.run(screen_stocks())
```

### cURL Example

```bash
curl -X POST http://localhost:8000/api/v1/screen \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-01-15",
    "filters": {
      "volume": {"min_average": 5000000}
    }
  }'
```

## WebSocket Support

Currently not implemented. All endpoints use REST HTTP.

## Versioning

The API uses URL versioning. Current version: `/api/v1`

Future versions will be available at `/api/v2`, etc.