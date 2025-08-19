# Enhanced Backtest Results Database Schema

## Overview

The `market_structure_results` table has been redesigned to store comprehensive backtest performance metrics in a denormalized structure for optimal query performance. Each metric is stored in a separate column, enabling efficient filtering, sorting, and analysis of backtest results.

## Table Structure

### Core Identifiers

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique result identifier |
| `backtest_id` | UUID | NOT NULL | Backtest execution identifier |
| `symbol` | VARCHAR(10) | NOT NULL | Stock symbol (e.g., "AAPL") |
| `strategy_name` | VARCHAR(50) | NOT NULL | Strategy name (e.g., "MarketStructure") |
| `start_date` | DATE | NOT NULL | Backtest start date |
| `end_date` | DATE | NOT NULL | Backtest end date |
| `created_at` | TIMESTAMP | DEFAULT NOW() | Record creation timestamp |

### Algorithm Parameters

These parameters define the strategy configuration and are part of the cache key system:

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `initial_cash` | DECIMAL(12,2) | NOT NULL | Starting capital amount |
| `resolution` | VARCHAR(20) | NOT NULL | Data resolution (Daily, Minute, etc.) |
| `pivot_bars` | INTEGER | NOT NULL, CHECK (pivot_bars > 0) | Bars for pivot detection |
| `lower_timeframe` | VARCHAR(10) | NOT NULL | Analysis timeframe (e.g., "5min") |

### Core Performance Results

Primary financial performance metrics:

| Column | Type | Description |
|--------|------|-------------|
| `total_return` | DECIMAL(10,4) | Total return percentage |
| `net_profit` | DECIMAL(10,4) | Net profit percentage |
| `net_profit_currency` | DECIMAL(12,2) | Net profit in currency units |
| `compounding_annual_return` | DECIMAL(10,4) | Annualized compounding return |
| `final_value` | DECIMAL(12,2) | Final portfolio value |
| `start_equity` | DECIMAL(12,2) | Starting equity |
| `end_equity` | DECIMAL(12,2) | Ending equity |

### Risk Metrics

Risk-adjusted performance measures:

| Column | Type | Description |
|--------|------|-------------|
| `sharpe_ratio` | DECIMAL(8,4) | Risk-adjusted return (excess return / volatility) |
| `sortino_ratio` | DECIMAL(8,4) | Downside risk-adjusted return |
| `max_drawdown` | DECIMAL(8,4) | Maximum peak-to-trough decline (%) |
| `probabilistic_sharpe_ratio` | DECIMAL(8,4) | Probability Sharpe ratio is statistically significant |
| `annual_standard_deviation` | DECIMAL(8,4) | Annualized volatility |
| `annual_variance` | DECIMAL(8,4) | Annualized variance of returns |
| `beta` | DECIMAL(8,4) | Sensitivity to market movements |
| `alpha` | DECIMAL(8,4) | Excess return over expected market return |

### Trading Statistics

Trade execution and performance metrics:

| Column | Type | Description |
|--------|------|-------------|
| `total_trades` | INTEGER | Total number of completed trades |
| `winning_trades` | INTEGER | Number of profitable trades |
| `losing_trades` | INTEGER | Number of unprofitable trades |
| `win_rate` | DECIMAL(6,2) | Percentage of winning trades |
| `loss_rate` | DECIMAL(6,2) | Percentage of losing trades |
| `average_win` | DECIMAL(8,4) | Average return of winning trades (%) |
| `average_loss` | DECIMAL(8,4) | Average return of losing trades (%) |
| `profit_factor` | DECIMAL(8,4) | Gross profit / gross loss |
| `profit_loss_ratio` | DECIMAL(8,4) | Average win / average loss |
| `expectancy` | DECIMAL(8,4) | Expected value per trade (%) |
| `total_orders` | INTEGER | Total number of orders placed |

### Advanced Metrics

Sophisticated performance measures:

| Column | Type | Description |
|--------|------|-------------|
| `information_ratio` | DECIMAL(8,4) | Active return / tracking error |
| `tracking_error` | DECIMAL(8,4) | Standard deviation of excess returns |
| `treynor_ratio` | DECIMAL(8,4) | Risk-adjusted return using beta |
| `total_fees` | DECIMAL(10,2) | Total transaction costs |
| `estimated_strategy_capacity` | DECIMAL(15,2) | Maximum capital strategy can handle |
| `lowest_capacity_asset` | VARCHAR(50) | Asset limiting strategy capacity |
| `portfolio_turnover` | DECIMAL(8,4) | Rate of trading activity (%) |

### Strategy-Specific Metrics

Metrics specific to the Market Structure strategy:

| Column | Type | Description |
|--------|------|-------------|
| `pivot_highs_detected` | INTEGER | Number of pivot high points identified |
| `pivot_lows_detected` | INTEGER | Number of pivot low points identified |
| `bos_signals_generated` | INTEGER | Break of structure signals generated |
| `position_flips` | INTEGER | Number of long/short position changes |
| `liquidation_events` | INTEGER | Number of forced liquidations |

### Execution Metadata

System execution and performance data:

| Column | Type | Description |
|--------|------|-------------|
| `execution_time_ms` | INTEGER | Backtest execution time in milliseconds |
| `result_path` | VARCHAR(500) | Path to detailed result files |
| `status` | VARCHAR(20) | Execution status (completed, failed, etc.) |
| `error_message` | TEXT | Error details if backtest failed |
| `cache_hit` | BOOLEAN | Whether result was retrieved from cache |

## Cache Key Composite Index

For optimal cache lookup performance, a composite index is created on the cache key parameters:

```sql
CREATE INDEX idx_backtest_cache_key ON market_structure_results 
(symbol, strategy_name, start_date, end_date, initial_cash, pivot_bars, lower_timeframe);
```

### Cache Key Parameters

The following 7 parameters uniquely identify a backtest configuration for caching:

1. **`symbol`** - Stock symbol being tested
2. **`strategy_name`** - Strategy algorithm name
3. **`start_date`** - Backtest start date
4. **`end_date`** - Backtest end date
5. **`initial_cash`** - Starting capital amount
6. **`pivot_bars`** - Number of bars for pivot detection
7. **`lower_timeframe`** - Analysis timeframe setting

## Additional Indexes

For query performance optimization:

```sql
-- Performance sorting
CREATE INDEX idx_backtest_performance ON market_structure_results 
(total_return DESC, sharpe_ratio DESC, max_drawdown ASC);

-- Date range queries
CREATE INDEX idx_backtest_dates ON market_structure_results 
(created_at DESC, start_date, end_date);

-- Symbol and strategy filtering
CREATE INDEX idx_backtest_symbol_strategy ON market_structure_results 
(symbol, strategy_name, created_at DESC);
```

## Data Types and Precision

### Decimal Precision Guidelines

- **Percentages**: `DECIMAL(8,4)` - Supports values like 123.4567%
- **Currency**: `DECIMAL(12,2)` - Supports values up to $999,999,999.99
- **Ratios**: `DECIMAL(8,4)` - Supports precise ratio calculations
- **Large Values**: `DECIMAL(15,2)` - For strategy capacity estimates

### Constraints and Validation

- All percentage values are stored as actual percentages (e.g., 15.25 for 15.25%)
- `pivot_bars` must be greater than 0
- `win_rate` + `loss_rate` should equal 100% when both are present
- `winning_trades` + `losing_trades` should equal `total_trades`

## Migration Notes

### Removed Columns

The following obsolete columns were removed during migration:

- `param_holding_period`
- `param_stop_loss`
- `param_take_profit`
- `avg_return`
- `median_return`
- `std_dev`
- `min_return`
- `max_return`
- `avg_holding_days`
- `best_trade`
- `worst_trade`
- `total_profit`
- `total_loss`
- `time_in_market`

### Data Migration Strategy

1. **Preserve existing data** where column mappings exist
2. **Set default values** for new required columns
3. **Null values allowed** for optional advanced metrics
4. **Recalculate derived metrics** where possible from existing data

## Query Examples

### Cache Lookup
```sql
SELECT * FROM market_structure_results 
WHERE symbol = 'AAPL' 
  AND strategy_name = 'MarketStructure'
  AND start_date = '2024-01-01'
  AND end_date = '2024-12-31'
  AND initial_cash = 100000
  AND pivot_bars = 5
  AND lower_timeframe = '5min'
ORDER BY created_at DESC
LIMIT 1;
```

### Performance Analysis
```sql
SELECT symbol, strategy_name, total_return, sharpe_ratio, max_drawdown,
       win_rate, total_trades, created_at
FROM market_structure_results 
WHERE total_return > 10.0 
  AND sharpe_ratio > 1.0
ORDER BY total_return DESC, sharpe_ratio DESC;
```

### Statistics Aggregation
```sql
SELECT strategy_name,
       COUNT(*) as backtest_count,
       AVG(total_return) as avg_return,
       AVG(sharpe_ratio) as avg_sharpe,
       AVG(max_drawdown) as avg_drawdown,
       AVG(win_rate) as avg_win_rate
FROM market_structure_results 
WHERE created_at >= NOW() - INTERVAL '30 days'
GROUP BY strategy_name
ORDER BY avg_return DESC;
```

## Performance Considerations

### Index Usage

- **Cache lookups** use the composite index for sub-millisecond performance
- **Date range queries** benefit from the date-based indexes
- **Performance sorting** uses dedicated performance indexes

### Query Optimization

- Always include `symbol` and `strategy_name` in WHERE clauses when possible
- Use LIMIT for large result sets
- Consider pagination for frontend display
- Use aggregate queries for statistics rather than client-side calculation

### Storage Efficiency

- Denormalized structure trades storage space for query performance
- NULL values are used for optional metrics to save space
- TEXT fields only used where necessary (error messages)

## Future Enhancements

### Planned Extensions

1. **Additional Strategy Metrics**: Support for new strategy-specific columns
2. **Equity Curve Storage**: Separate table for detailed equity progression
3. **Trade Details**: Linked table for individual trade records
4. **Benchmark Comparison**: Columns for benchmark-relative metrics

### Scalability Considerations

1. **Partitioning**: Consider date-based partitioning for large datasets
2. **Archival**: Implement data lifecycle management for old results
3. **Compression**: Use database compression for historical data
4. **Replication**: Consider read replicas for heavy analytical workloads