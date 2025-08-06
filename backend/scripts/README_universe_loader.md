# Universe Data Loader

Production-ready data loader for fetching the entire universe of US common stocks from Polygon.io.

## Features

### Core Functionality
- **Universe Discovery**: Automatically discovers all US common stocks from Polygon.io
- **Bulk Data Loading**: Uses Polygon's grouped aggregates endpoint for maximum efficiency (one API call per day for ALL symbols)
- **Progress Tracking**: JSON-based checkpoint system for resumable operations
- **Graceful Shutdown**: Handles SIGINT/SIGTERM signals to save progress before exit
- **Error Handling**: Comprehensive error handling with retry logic and database logging
- **Data Integrity**: Built-in verification system to check for gaps and invalid data

### Performance Optimizations
- **Streaming Processing**: Handles large data volumes without memory issues
- **Batch Database Inserts**: Configurable batch size for efficient database writes
- **Concurrent Operations**: When using individual API calls, supports configurable concurrency
- **Smart Caching**: Caches universe discovery for 24 hours to reduce API calls

## Usage

### Basic Commands

```bash
# Discover universe of stocks
python universe_data_loader.py --discover

# Load historical data for date range
python universe_data_loader.py --historical --start 2024-01-01 --end 2024-12-31

# Run daily update (most recent trading day)
python universe_data_loader.py --daily

# Run daily update for specific date
python universe_data_loader.py --daily --date 2024-03-15

# Verify data integrity
python universe_data_loader.py --verify --sample-size 200

# Load data for specific symbols only
python universe_data_loader.py --historical --start 2024-01-01 --end 2024-12-31 --symbols "AAPL,MSFT,GOOGL"
```

### Advanced Usage

```bash
# Resume interrupted job
python universe_data_loader.py --resume

# Clear checkpoint for fresh start
python universe_data_loader.py --clear-checkpoint historical_load_2024-01-01_2024-12-31

# Force refresh universe discovery (bypass cache)
python universe_data_loader.py --discover --force-refresh

# Adjust batch size for database inserts
python universe_data_loader.py --historical --start 2024-01-01 --end 2024-12-31 --batch-size 5000
```

## Progress Tracking

The loader maintains progress in `universe_loader_checkpoint.json`:

```json
{
  "historical_load_2024-01-01_2024-12-31": {
    "total_dates": 252,
    "processed_dates": 150,
    "total_bars": 1234567,
    "processed_dates": ["2024-01-02", "2024-01-03", ...],
    "last_processed_date": "2024-06-15",
    "status": "in_progress",
    "last_updated": "2024-03-20T15:30:00"
  }
}
```

## Resume Capability

If the loader is interrupted (crash, CTRL+C, etc.), it automatically:
1. Saves current progress to checkpoint file
2. Can resume from exact point of interruption
3. Skips already processed dates
4. Maintains data consistency

## Error Handling

Errors are logged to both:
1. Console output with detailed information
2. Database `data_fetch_errors` table for tracking and retry

## Performance Characteristics

### Bulk Loading (Recommended)
- **API Calls**: 1 call per trading day (all symbols)
- **Throughput**: ~8,000-10,000 symbols per day
- **Memory**: Streaming processing keeps memory usage low
- **Time**: ~2-5 seconds per trading day

### Individual Loading
- **API Calls**: 1 call per symbol per date range
- **Concurrency**: Configurable (default 50)
- **Use Case**: Specific symbol updates or error recovery

## Database Tables Used

- `daily_bars`: Stores OHLCV data
- `data_coverage`: Tracks loaded date ranges per symbol
- `data_fetch_errors`: Logs errors for retry
- `symbols`: Updated with latest ticker information

## Best Practices

1. **Initial Load**: Use historical mode with bulk loading
   ```bash
   python universe_data_loader.py --historical --start 2020-01-01 --end 2024-12-31
   ```

2. **Daily Updates**: Schedule daily update after market close
   ```bash
   # Add to cron for 5 PM ET daily
   0 17 * * 1-5 python universe_data_loader.py --daily
   ```

3. **Weekly Verification**: Check data integrity weekly
   ```bash
   python universe_data_loader.py --verify --sample-size 500
   ```

4. **Monitor Checkpoints**: Regularly check checkpoint file for stuck jobs

## Troubleshooting

### Common Issues

1. **Rate Limiting**: Adjust `POLYGON_RATE_LIMIT` in environment
2. **Memory Issues**: Reduce `--batch-size` parameter
3. **Stuck Jobs**: Clear checkpoint and restart
4. **Missing Data**: Check `data_fetch_errors` table

### Debug Mode

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
python universe_data_loader.py --historical --start 2024-01-01 --end 2024-01-31
```

## Integration

The loader integrates with existing services:
- Uses `PolygonClient` for API access
- Uses `TickerDiscoveryService` for universe discovery
- Uses `DataCollector` for data storage
- Respects all configuration from `app.config.settings`