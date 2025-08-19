# Screener-Backtest Pipeline

This is an end-to-end pipeline that runs stock screening followed by backtesting on the screened symbols.

## Components

1. **Main Pipeline Script** (`run_screener_backtest_pipeline.py`):
   - Orchestrates the entire pipeline workflow
   - Loads configuration from YAML file
   - Coordinates screening, backtesting, analysis, and cleanup

2. **Backtest Queue Manager** (`app/services/backtest_queue_manager.py`):
   - Manages parallel execution of backtests with concurrency control
   - Handles retries and timeouts
   - Provides progress tracking

3. **Statistics Aggregator** (`app/services/statistics_aggregator.py`):
   - Collects and analyzes results from all backtests
   - Calculates aggregate metrics (average return, Sharpe ratio, win rate, etc.)
   - Exports results in multiple formats (JSON, CSV, HTML)

4. **Cleanup Service** (`app/services/cleanup_service.py`):
   - Cleans up LEAN backtest log directories
   - Optionally archives logs before deletion
   - Manages disk space

## Configuration

The pipeline is configured via `pipeline_config.yaml`. Key settings include:

- **Screening filters**: Price range, gap, dollar volume, relative volume
- **Date ranges**: For both screening and backtesting
- **Execution settings**: Parallel backtests, timeouts, retry attempts
- **Output settings**: Result formats, cleanup options

## Usage

### Basic Usage

```bash
# Run with default configuration
./venv/bin/python run_screener_backtest_pipeline.py

# Run with custom configuration
./venv/bin/python run_screener_backtest_pipeline.py custom_config.yaml
```

### Example Configuration

```yaml
screening:
  filters:
    price_range:
      min_price: 10
      max_price: 100
    gap:
      gap_threshold: 2.0
      direction: "up"
  date_range:
    start: "2024-01-01"
    end: "2024-12-31"

backtesting:
  strategy: "MarketStructure"
  date_range:
    start: "2024-01-01"
    end: "2024-12-31"
  initial_cash: 100000

execution:
  parallel_backtests: 5
  timeout_per_backtest: 300
```

## Output

The pipeline generates:

1. **Summary statistics**: Average returns, Sharpe ratios, win rates across all symbols
2. **Individual results**: Detailed metrics for each symbol
3. **Top/worst performers**: Ranked list of best and worst performing symbols
4. **Multiple formats**: JSON, CSV, and HTML reports

Results are saved to the directory specified in the configuration (default: `./pipeline_results`).

## Requirements

- Python 3.11+
- Virtual environment with dependencies installed
- Running backend API server
- LEAN CLI configured with Polygon data provider
- PostgreSQL database with stock data

## Testing

Test individual components:

```bash
./venv/bin/python test_pipeline_components.py
```

## Monitoring

The pipeline provides real-time progress updates:
- Number of symbols screened
- Backtests running/completed
- Estimated time remaining
- Error notifications

## Error Handling

- Failed backtests are retried based on configuration
- Pipeline can continue on errors if configured
- All errors are logged with details
- Failed symbols are tracked in the final report

## Performance

- Screening uses database pre-filtering for efficiency
- Backtests run in parallel with configurable concurrency
- Results are cached to avoid redundant calculations
- Cleanup runs asynchronously after completion