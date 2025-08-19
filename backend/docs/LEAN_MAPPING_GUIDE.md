# LEAN Results to Database Mapping Guide

## Overview

This guide documents how LEAN backtest output is mapped to the enhanced database schema. The mapping process extracts comprehensive performance metrics from LEAN's JSON output and stores them in separate database columns for optimal querying and analysis.

## LEAN Output Structure

LEAN generates several output files after a backtest execution:

```
/Results/
├── config.json          # Configuration used
├── logs.txt             # Execution logs
├── statistics.json      # Performance statistics
├── orders.json          # Order history
├── trades.json          # Trade history
└── equity-curve.json    # Portfolio value over time
```

## Core Mapping Process

### 1. Statistics.json Processing

The primary source for performance metrics is the `statistics.json` file:

```json
{
  "Total Trades": "797",
  "Average Win": "1.62%",
  "Average Loss": "-0.87%",
  "Compounding Annual Return": "-13.256%",
  "Drawdown": "35.800%",
  "Expectancy": "-0.061",
  "Net Profit": "-20.401%",
  "Sharpe Ratio": "-0.591",
  "Probabilistic Sharpe Ratio": "2.023%",
  "Loss Rate": "67%",
  "Win Rate": "33%",
  "Profit-Loss Ratio": "1.85",
  "Alpha": "0",
  "Beta": "0",
  "Annual Standard Deviation": "0.215",
  "Annual Variance": "0.046",
  "Information Ratio": "-0.336",
  "Tracking Error": "0.215",
  "Treynor Ratio": "0",
  "Total Fees": "$1,692.39",
  "Estimated Strategy Capacity": "$1,000,000.00",
  "Lowest Capacity Asset": "AAPL R735QTJ8XC9X",
  "Portfolio Turnover": "129.06%",
  "OrderListHash": "hash-string"
}
```

## Database Column Mappings

### Core Performance Results

| Database Column | LEAN Statistics Key | Data Type | Transformation | Example |
|-----------------|---------------------|-----------|----------------|---------|
| `total_return` | "Net Profit" | DECIMAL(10,4) | Parse percentage | -20.401 |
| `net_profit` | "Net Profit" | DECIMAL(10,4) | Parse percentage | -20.401 |
| `net_profit_currency` | Calculated | DECIMAL(12,2) | net_profit * initial_cash / 100 | -20401.03 |
| `compounding_annual_return` | "Compounding Annual Return" | DECIMAL(10,4) | Parse percentage | -13.256 |
| `final_value` | Calculated | DECIMAL(12,2) | start_equity + net_profit_currency | 79598.97 |
| `start_equity` | Parameter | DECIMAL(12,2) | From initial_cash | 100000.00 |
| `end_equity` | Calculated | DECIMAL(12,2) | start_equity + net_profit_currency | 79598.97 |

### Risk Metrics

| Database Column | LEAN Statistics Key | Data Type | Transformation | Example |
|-----------------|---------------------|-----------|----------------|---------|
| `sharpe_ratio` | "Sharpe Ratio" | DECIMAL(8,4) | Parse decimal | -0.591 |
| `sortino_ratio` | "Sortino Ratio" | DECIMAL(8,4) | Parse decimal (if available) | -0.764 |
| `max_drawdown` | "Drawdown" | DECIMAL(8,4) | Parse percentage | 35.800 |
| `probabilistic_sharpe_ratio` | "Probabilistic Sharpe Ratio" | DECIMAL(8,4) | Parse percentage | 2.023 |
| `annual_standard_deviation` | "Annual Standard Deviation" | DECIMAL(8,4) | Parse decimal | 0.215 |
| `annual_variance` | "Annual Variance" | DECIMAL(8,4) | Parse decimal | 0.046 |
| `beta` | "Beta" | DECIMAL(8,4) | Parse decimal | 0.000 |
| `alpha` | "Alpha" | DECIMAL(8,4) | Parse decimal | 0.000 |

### Trading Statistics

| Database Column | LEAN Statistics Key | Data Type | Transformation | Example |
|-----------------|---------------------|-----------|----------------|---------|
| `total_trades` | "Total Trades" | INTEGER | Parse integer | 797 |
| `winning_trades` | Calculated | INTEGER | win_rate * total_trades / 100 | 263 |
| `losing_trades` | Calculated | INTEGER | loss_rate * total_trades / 100 | 534 |
| `win_rate` | "Win Rate" | DECIMAL(6,2) | Parse percentage | 33.0 |
| `loss_rate` | "Loss Rate" | DECIMAL(6,2) | Parse percentage | 67.0 |
| `average_win` | "Average Win" | DECIMAL(8,4) | Parse percentage | 1.62 |
| `average_loss` | "Average Loss" | DECIMAL(8,4) | Parse percentage | -0.87 |
| `profit_factor` | "Profit-Loss Ratio" | DECIMAL(8,4) | Parse decimal | 1.85 |
| `profit_loss_ratio` | "Profit-Loss Ratio" | DECIMAL(8,4) | Parse decimal | 1.85 |
| `expectancy` | "Expectancy" | DECIMAL(8,4) | Parse decimal | -0.061 |
| `total_orders` | Calculated | INTEGER | Count from orders.json | 797 |

### Advanced Metrics

| Database Column | LEAN Statistics Key | Data Type | Transformation | Example |
|-----------------|---------------------|-----------|----------------|---------|
| `information_ratio` | "Information Ratio" | DECIMAL(8,4) | Parse decimal | -0.336 |
| `tracking_error` | "Tracking Error" | DECIMAL(8,4) | Parse decimal | 0.215 |
| `treynor_ratio` | "Treynor Ratio" | DECIMAL(8,4) | Parse decimal | 0.000 |
| `total_fees` | "Total Fees" | DECIMAL(10,2) | Parse currency | 1692.39 |
| `estimated_strategy_capacity` | "Estimated Strategy Capacity" | DECIMAL(15,2) | Parse currency | 1000000.00 |
| `lowest_capacity_asset` | "Lowest Capacity Asset" | VARCHAR(50) | Direct string | "AAPL R735QTJ8XC9X" |
| `portfolio_turnover` | "Portfolio Turnover" | DECIMAL(8,4) | Parse percentage | 129.06 |

## Data Transformation Functions

### Percentage Parsing

```python
def parse_percentage(value: str) -> Decimal:
    """
    Parse percentage string to decimal.
    
    Args:
        value: String like "15.25%" or "-20.401%"
        
    Returns:
        Decimal value (15.25 for "15.25%")
    """
    if not value or value == "∞" or value == "-∞":
        return Decimal("0")
    
    # Remove % sign and convert to decimal
    clean_value = value.replace("%", "").replace(",", "")
    try:
        return Decimal(clean_value)
    except (ValueError, InvalidOperation):
        return Decimal("0")
```

### Currency Parsing

```python
def parse_currency(value: str) -> Decimal:
    """
    Parse currency string to decimal.
    
    Args:
        value: String like "$1,692.39" or "($500.00)"
        
    Returns:
        Decimal value
    """
    if not value:
        return Decimal("0")
    
    # Handle negative values in parentheses
    is_negative = value.startswith("(") and value.endswith(")")
    if is_negative:
        value = value[1:-1]  # Remove parentheses
    
    # Remove currency symbols and commas
    clean_value = value.replace("$", "").replace(",", "")
    
    try:
        result = Decimal(clean_value)
        return -result if is_negative else result
    except (ValueError, InvalidOperation):
        return Decimal("0")
```

### Integer Parsing

```python
def parse_integer(value: str) -> int:
    """
    Parse integer string with potential commas.
    
    Args:
        value: String like "1,234" or "797"
        
    Returns:
        Integer value
    """
    if not value:
        return 0
    
    clean_value = value.replace(",", "")
    try:
        return int(clean_value)
    except ValueError:
        return 0
```

## Strategy-Specific Metrics

### Market Structure Strategy

The Market Structure strategy generates additional metrics not present in standard LEAN output. These are extracted from log files or custom algorithm output:

| Database Column | Source | Extraction Method | Example |
|-----------------|--------|------------------|---------|
| `pivot_highs_detected` | Algorithm logs | Regex: `"Pivot High detected: (\d+)"` | 45 |
| `pivot_lows_detected` | Algorithm logs | Regex: `"Pivot Low detected: (\d+)"` | 42 |
| `bos_signals_generated` | Algorithm logs | Regex: `"BOS signal: (\d+)"` | 87 |
| `position_flips` | Orders analysis | Count direction changes | 15 |
| `liquidation_events` | Orders analysis | Count forced closures | 0 |

### Log Parsing Example

```python
def extract_strategy_metrics(log_content: str) -> Dict[str, int]:
    """
    Extract strategy-specific metrics from log content.
    
    Args:
        log_content: Raw log file content
        
    Returns:
        Dictionary of metric values
    """
    import re
    
    metrics = {}
    
    # Pivot highs
    pivot_highs = re.findall(r'Pivot High detected', log_content)
    metrics['pivot_highs_detected'] = len(pivot_highs)
    
    # Pivot lows
    pivot_lows = re.findall(r'Pivot Low detected', log_content)
    metrics['pivot_lows_detected'] = len(pivot_lows)
    
    # BOS signals
    bos_signals = re.findall(r'BOS signal generated', log_content)
    metrics['bos_signals_generated'] = len(bos_signals)
    
    return metrics
```

## Algorithm Parameters Mapping

### Cache Key Parameters

Parameters that define the backtest configuration:

| Database Column | Source | Description | Example |
|-----------------|--------|-------------|---------|
| `symbol` | Request parameter | Stock symbol | "AAPL" |
| `strategy_name` | Request parameter | Strategy name | "MarketStructure" |
| `start_date` | Request parameter | Start date | "2024-01-01" |
| `end_date` | Request parameter | End date | "2024-12-31" |
| `initial_cash` | Request parameter | Starting capital | 100000.00 |
| `pivot_bars` | Algorithm parameter | Pivot detection bars | 5 |
| `lower_timeframe` | Algorithm parameter | Analysis timeframe | "5min" |

### Additional Parameters

| Database Column | Source | Description | Example |
|-----------------|--------|-------------|---------|
| `resolution` | LEAN config | Data resolution | "Minute" |

## Complete Mapping Implementation

### Main Processing Function

```python
async def process_lean_results(
    result_path: str,
    backtest_request: BacktestRequest,
    backtest_id: UUID
) -> DatabaseBacktestResult:
    """
    Process LEAN backtest results and map to database schema.
    
    Args:
        result_path: Path to LEAN results directory
        backtest_request: Original backtest request
        backtest_id: Unique backtest identifier
        
    Returns:
        Mapped database result object
    """
    
    # Load LEAN statistics
    stats_file = Path(result_path) / "statistics.json"
    with open(stats_file, 'r') as f:
        lean_stats = json.load(f)
    
    # Load logs for strategy-specific metrics
    logs_file = Path(result_path) / "logs.txt"
    log_content = ""
    if logs_file.exists():
        with open(logs_file, 'r') as f:
            log_content = f.read()
    
    # Extract strategy-specific metrics
    strategy_metrics = extract_strategy_metrics(log_content)
    
    # Calculate derived values
    net_profit = parse_percentage(lean_stats.get("Net Profit", "0"))
    initial_cash = float(backtest_request.initial_cash)
    net_profit_currency = net_profit * initial_cash / 100
    
    total_trades = parse_integer(lean_stats.get("Total Trades", "0"))
    win_rate = parse_percentage(lean_stats.get("Win Rate", "0"))
    loss_rate = parse_percentage(lean_stats.get("Loss Rate", "0"))
    
    winning_trades = int(total_trades * win_rate / 100) if win_rate > 0 else 0
    losing_trades = int(total_trades * loss_rate / 100) if loss_rate > 0 else 0
    
    # Create database result object
    return DatabaseBacktestResult(
        backtest_id=backtest_id,
        symbol=backtest_request.symbols[0] if backtest_request.symbols else "UNKNOWN",
        strategy_name=backtest_request.strategy_name,
        start_date=backtest_request.start_date,
        end_date=backtest_request.end_date,
        
        # Algorithm parameters
        initial_cash=backtest_request.initial_cash,
        resolution=backtest_request.resolution,
        pivot_bars=backtest_request.pivot_bars,
        lower_timeframe=backtest_request.lower_timeframe,
        
        # Core performance results
        total_return=net_profit,
        net_profit=net_profit,
        net_profit_currency=Decimal(str(net_profit_currency)),
        compounding_annual_return=parse_percentage(lean_stats.get("Compounding Annual Return", "0")),
        final_value=Decimal(str(initial_cash + net_profit_currency)),
        start_equity=Decimal(str(initial_cash)),
        end_equity=Decimal(str(initial_cash + net_profit_currency)),
        
        # Risk metrics
        sharpe_ratio=parse_decimal(lean_stats.get("Sharpe Ratio", "0")),
        sortino_ratio=parse_decimal(lean_stats.get("Sortino Ratio", "0")),
        max_drawdown=parse_percentage(lean_stats.get("Drawdown", "0")),
        probabilistic_sharpe_ratio=parse_percentage(lean_stats.get("Probabilistic Sharpe Ratio", "0")),
        annual_standard_deviation=parse_decimal(lean_stats.get("Annual Standard Deviation", "0")),
        annual_variance=parse_decimal(lean_stats.get("Annual Variance", "0")),
        beta=parse_decimal(lean_stats.get("Beta", "0")),
        alpha=parse_decimal(lean_stats.get("Alpha", "0")),
        
        # Trading statistics
        total_trades=total_trades,
        winning_trades=winning_trades,
        losing_trades=losing_trades,
        win_rate=win_rate,
        loss_rate=loss_rate,
        average_win=parse_percentage(lean_stats.get("Average Win", "0")),
        average_loss=parse_percentage(lean_stats.get("Average Loss", "0")),
        profit_factor=parse_decimal(lean_stats.get("Profit-Loss Ratio", "0")),
        profit_loss_ratio=parse_decimal(lean_stats.get("Profit-Loss Ratio", "0")),
        expectancy=parse_decimal(lean_stats.get("Expectancy", "0")),
        total_orders=count_orders_from_file(Path(result_path) / "orders.json"),
        
        # Advanced metrics
        information_ratio=parse_decimal(lean_stats.get("Information Ratio", "0")),
        tracking_error=parse_decimal(lean_stats.get("Tracking Error", "0")),
        treynor_ratio=parse_decimal(lean_stats.get("Treynor Ratio", "0")),
        total_fees=parse_currency(lean_stats.get("Total Fees", "0")),
        estimated_strategy_capacity=parse_currency(lean_stats.get("Estimated Strategy Capacity", "1000000")),
        lowest_capacity_asset=lean_stats.get("Lowest Capacity Asset", ""),
        portfolio_turnover=parse_percentage(lean_stats.get("Portfolio Turnover", "0")),
        
        # Strategy-specific metrics
        pivot_highs_detected=strategy_metrics.get('pivot_highs_detected'),
        pivot_lows_detected=strategy_metrics.get('pivot_lows_detected'),
        bos_signals_generated=strategy_metrics.get('bos_signals_generated'),
        position_flips=strategy_metrics.get('position_flips'),
        liquidation_events=strategy_metrics.get('liquidation_events'),
        
        # Execution metadata
        execution_time_ms=None,  # Set by caller
        result_path=str(result_path),
        status="completed",
        error_message=None,
        cache_hit=False,
        created_at=datetime.utcnow()
    )
```

## Error Handling

### Missing Statistics

```python
def safe_parse_statistic(stats_dict: dict, key: str, parser_func, default_value):
    """
    Safely parse a statistic with fallback to default.
    
    Args:
        stats_dict: LEAN statistics dictionary
        key: Statistic key to extract
        parser_func: Function to parse the value
        default_value: Default if key missing or parsing fails
        
    Returns:
        Parsed value or default
    """
    try:
        value = stats_dict.get(key)
        if value is None:
            return default_value
        return parser_func(value)
    except Exception:
        return default_value
```

### Data Validation

```python
def validate_parsed_result(result: DatabaseBacktestResult) -> List[str]:
    """
    Validate parsed result for consistency.
    
    Args:
        result: Parsed database result
        
    Returns:
        List of validation errors
    """
    errors = []
    
    # Check win/loss rate consistency
    if result.win_rate and result.loss_rate:
        total_rate = result.win_rate + result.loss_rate
        if abs(total_rate - 100) > 0.1:  # Allow small rounding differences
            errors.append(f"Win rate + Loss rate = {total_rate}%, expected 100%")
    
    # Check trade count consistency
    if result.winning_trades and result.losing_trades and result.total_trades:
        calculated_total = result.winning_trades + result.losing_trades
        if calculated_total != result.total_trades:
            errors.append(f"Winning + Losing trades = {calculated_total}, expected {result.total_trades}")
    
    # Check equity consistency
    if result.start_equity and result.end_equity and result.net_profit_currency:
        expected_end = result.start_equity + result.net_profit_currency
        if abs(float(result.end_equity - expected_end)) > 0.01:
            errors.append(f"End equity inconsistent with start + profit")
    
    return errors
```

## Testing and Validation

### Unit Tests

```python
def test_percentage_parsing():
    assert parse_percentage("15.25%") == Decimal("15.25")
    assert parse_percentage("-20.401%") == Decimal("-20.401")
    assert parse_percentage("∞") == Decimal("0")
    assert parse_percentage("") == Decimal("0")

def test_currency_parsing():
    assert parse_currency("$1,692.39") == Decimal("1692.39")
    assert parse_currency("($500.00)") == Decimal("-500.00")
    assert parse_currency("") == Decimal("0")

def test_mapping_completeness():
    """Test that all database columns are mapped from LEAN output."""
    # Test with sample LEAN statistics
    sample_stats = load_sample_lean_output()
    result = process_lean_results("test_path", sample_request, uuid4())
    
    # Verify all required fields are populated
    assert result.total_return is not None
    assert result.sharpe_ratio is not None
    assert result.total_trades is not None
    # ... additional assertions
```

## Performance Considerations

### Batch Processing

When processing multiple results:

```python
async def process_multiple_results(result_paths: List[str]) -> List[DatabaseBacktestResult]:
    """
    Process multiple LEAN results efficiently.
    
    Args:
        result_paths: List of result directory paths
        
    Returns:
        List of processed results
    """
    tasks = []
    for path in result_paths:
        task = asyncio.create_task(process_lean_results(path, request, uuid4()))
        tasks.append(task)
    
    return await asyncio.gather(*tasks)
```

### Memory Management

For large result sets:

1. **Stream processing** instead of loading all data into memory
2. **Chunked database inserts** for bulk operations
3. **File cleanup** after processing to free disk space

## Future Enhancements

### Planned Improvements

1. **Enhanced Strategy Metrics**: Support for additional strategy-specific measurements
2. **Real-time Processing**: Stream processing of LEAN output during execution
3. **Data Validation**: Enhanced consistency checks and error reporting
4. **Performance Optimization**: Faster parsing for large result sets
5. **Multi-Strategy Support**: Generic mapping framework for different strategies