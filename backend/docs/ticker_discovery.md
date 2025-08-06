# Ticker Discovery Feature

The ticker discovery feature allows you to screen the entire universe of US common stocks instead of being limited to a predefined list of symbols.

## Overview

By default, the screener uses a predefined list of symbols (configured in settings). With ticker discovery, you can:

1. Fetch all active US common stocks from Polygon API
2. Screen the entire universe (typically 4,000+ stocks)
3. Apply your filters to a much broader set of opportunities

## API Endpoints

### Get All US Stocks
```
GET /api/screener/symbols/us-stocks
```

Returns a list of all active US common stock tickers. This endpoint fetches and paginates through all results from Polygon's reference data.

**Example Response:**
```json
["AAPL", "MSFT", "GOOGL", "AMZN", ...]
```

### Screen with Universe Discovery
```
POST /api/screener/screen
```

Use the `use_all_us_stocks` parameter to screen all US stocks:

**Example Request:**
```json
{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "use_all_us_stocks": true,
    "filters": {
        "volume": {
            "min_average": 1000000,
            "lookback_days": 20
        }
    }
}
```

## Implementation Details

### TickerDiscoveryService

Located in `/backend/app/services/ticker_discovery.py`, this service:

1. Uses Polygon's `/v3/reference/tickers` endpoint
2. Filters for `type=CS` (common stock) and `market=stocks`
3. Handles pagination with cursor-based navigation
4. Returns deduplicated, sorted list of symbols

### Performance Considerations

- Fetching all tickers typically takes 10-30 seconds
- Screening 4,000+ stocks can take several minutes
- The API uses pagination with 1,000 tickers per page
- Rate limiting is handled by the PolygonClient

### Usage Examples

#### Python Example
```python
from app.services.ticker_discovery import TickerDiscoveryService
from app.services.polygon_client import PolygonClient

async with PolygonClient() as client:
    ticker_service = TickerDiscoveryService(client)
    all_stocks = await ticker_service.fetch_all_us_common_stocks()
    print(f"Found {len(all_stocks)} US common stocks")
```

#### API Example
```bash
# Get all US stocks
curl http://localhost:8000/api/screener/symbols/us-stocks

# Screen all US stocks
curl -X POST http://localhost:8000/api/screener/screen \
  -H "Content-Type: application/json" \
  -d '{
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "use_all_us_stocks": true,
    "filters": {
        "volume": {"min_average": 500000}
    }
  }'
```

## Future Enhancements

The current implementation is simple and functional. Future enhancements could include:

1. **Caching**: Cache the ticker list with TTL to avoid repeated API calls
2. **Filtering**: Add exchange, sector, or market cap filters
3. **Incremental Updates**: Only fetch changes since last update
4. **Database Storage**: Store ticker metadata locally
5. **Background Updates**: Refresh ticker list periodically

## Testing

Run the test script to verify functionality:

```bash
cd backend
python test_ticker_discovery.py
```

Or use the example script:

```bash
cd backend
python examples/universe_screening_example.py
```