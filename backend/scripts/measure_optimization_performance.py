#!/usr/bin/env python3
"""
Measure performance of filter optimization queries to estimate time for large runs.
"""

import asyncio
import asyncpg
import time
from datetime import date, timedelta
import statistics
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/ultimate_trader")


async def measure_single_query(pool, start_date: date, end_date: date, filter_params: dict):
    """Measure execution time of a single filter combination query."""
    
    # Build WHERE conditions similar to actual optimization
    where_conditions = ["gs.date BETWEEN $1 AND $2"]
    params = [start_date, end_date]
    param_count = 2
    
    if 'price_min' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.price >= ${param_count}")
        params.append(filter_params['price_min'])
    
    if 'price_max' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.price <= ${param_count}")
        params.append(filter_params['price_max'])
    
    if 'rsi_min' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.rsi_14 >= ${param_count}")
        params.append(filter_params['rsi_min'])
    
    if 'rsi_max' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.rsi_14 <= ${param_count}")
        params.append(filter_params['rsi_max'])
    
    if 'gap_min' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.gap_percent >= ${param_count}")
        params.append(filter_params['gap_min'])
    
    if 'gap_max' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.gap_percent <= ${param_count}")
        params.append(filter_params['gap_max'])
    
    if 'volume_min' in filter_params:
        param_count += 1
        where_conditions.append(f"gs.prev_day_dollar_volume >= ${param_count}")
        params.append(filter_params['volume_min'])
    
    if 'pivot_bars' in filter_params:
        param_count += 1
        where_conditions.append(f"gms.pivot_bars >= ${param_count}")
        params.append(filter_params['pivot_bars'])
        param_count += 1
        where_conditions.append(f"gms.pivot_bars <= ${param_count}")
        params.append(filter_params['pivot_bars'] + 1)
    
    where_clause = " AND ".join(where_conditions)
    
    query = f"""
    WITH filtered_data AS (
        SELECT 
            gs.symbol,
            gs.date,
            gms.pivot_bars,
            gms.total_return,
            gms.sharpe_ratio,
            gms.max_drawdown,
            gms.win_rate,
            gms.profit_factor,
            gms.total_trades
        FROM grid_screening gs
        INNER JOIN grid_market_structure gms 
            ON gs.symbol = gms.symbol 
            AND gs.date = gms.backtest_date
        WHERE {where_clause}
            AND gms.total_return IS NOT NULL
    )
    SELECT 
        COUNT(DISTINCT symbol) as total_symbols,
        COUNT(*) as total_backtests,
        AVG(total_return) as avg_total_return,
        AVG(sharpe_ratio) as avg_sharpe_ratio,
        AVG(max_drawdown) as avg_max_drawdown,
        AVG(win_rate) as avg_win_rate,
        AVG(profit_factor) as avg_profit_factor,
        ARRAY_AGG(DISTINCT symbol ORDER BY symbol) as all_symbols
    FROM filtered_data
    """
    
    start_time = time.time()
    try:
        result = await pool.fetchrow(query, *params)
        execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        return {
            'execution_time_ms': execution_time,
            'total_symbols': result['total_symbols'] if result else 0,
            'total_backtests': result['total_backtests'] if result else 0,
            'success': True
        }
    except Exception as e:
        execution_time = (time.time() - start_time) * 1000
        return {
            'execution_time_ms': execution_time,
            'error': str(e),
            'success': False
        }


async def run_performance_test():
    """Run performance tests with various filter combinations."""
    
    # Create connection pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=10)
    
    # Test parameters
    end_date = date.today() - timedelta(days=1)
    start_date = end_date - timedelta(days=30)
    
    # Different test scenarios
    test_scenarios = [
        # Simple filters (few conditions)
        {
            'name': 'Simple - Price only',
            'filters': {'price_min': 10, 'price_max': 50}
        },
        {
            'name': 'Simple - Price + RSI',
            'filters': {'price_min': 10, 'price_max': 50, 'rsi_min': 30, 'rsi_max': 70}
        },
        # Medium complexity
        {
            'name': 'Medium - 4 filters',
            'filters': {
                'price_min': 10, 'price_max': 50,
                'rsi_min': 30, 'rsi_max': 70,
                'gap_min': -2, 'gap_max': 2,
                'volume_min': 1000000
            }
        },
        # Complex filters (many conditions)
        {
            'name': 'Complex - All filters',
            'filters': {
                'price_min': 10, 'price_max': 50,
                'rsi_min': 30, 'rsi_max': 70,
                'gap_min': -2, 'gap_max': 2,
                'volume_min': 1000000,
                'pivot_bars': 6
            }
        },
        # Edge cases
        {
            'name': 'Edge - Very restrictive',
            'filters': {
                'price_min': 100, 'price_max': 110,
                'rsi_min': 25, 'rsi_max': 30,
                'gap_min': 4, 'gap_max': 5
            }
        },
        {
            'name': 'Edge - Very broad',
            'filters': {
                'price_min': 1, 'price_max': 1000,
                'rsi_min': 0, 'rsi_max': 100
            }
        }
    ]
    
    print(f"Testing query performance from {start_date} to {end_date}")
    print("=" * 80)
    
    # Run each scenario multiple times to get average
    runs_per_scenario = 5
    
    all_times = []
    
    for scenario in test_scenarios:
        print(f"\nScenario: {scenario['name']}")
        print("-" * 40)
        
        times = []
        symbols_matched = []
        
        for run in range(runs_per_scenario):
            result = await measure_single_query(pool, start_date, end_date, scenario['filters'])
            
            if result['success']:
                times.append(result['execution_time_ms'])
                symbols_matched.append(result['total_symbols'])
                print(f"  Run {run + 1}: {result['execution_time_ms']:.2f}ms - {result['total_symbols']} symbols matched")
            else:
                print(f"  Run {run + 1}: ERROR - {result['error']}")
        
        if times:
            avg_time = statistics.mean(times)
            std_dev = statistics.stdev(times) if len(times) > 1 else 0
            avg_symbols = statistics.mean(symbols_matched)
            all_times.append(avg_time)
            
            print(f"\n  Average: {avg_time:.2f}ms (±{std_dev:.2f}ms)")
            print(f"  Symbols: {avg_symbols:.0f} average matches")
    
    # Overall statistics
    print("\n" + "=" * 80)
    print("OVERALL STATISTICS")
    print("=" * 80)
    
    if all_times:
        overall_avg = statistics.mean(all_times)
        overall_min = min(all_times)
        overall_max = max(all_times)
        
        print(f"Average query time: {overall_avg:.2f}ms")
        print(f"Min query time: {overall_min:.2f}ms")
        print(f"Max query time: {overall_max:.2f}ms")
        
        # Projections for large runs
        print("\n" + "=" * 80)
        print("PROJECTIONS FOR LARGE OPTIMIZATION RUNS")
        print("=" * 80)
        
        combinations = [1000, 10000, 100000, 1000000, 3110400]
        
        print("\nUsing average query time:")
        for combo_count in combinations:
            total_ms = combo_count * overall_avg
            total_seconds = total_ms / 1000
            total_minutes = total_seconds / 60
            total_hours = total_minutes / 60
            
            if total_hours >= 1:
                print(f"  {combo_count:,} combinations: {total_hours:.1f} hours ({total_minutes:.0f} minutes)")
            elif total_minutes >= 1:
                print(f"  {combo_count:,} combinations: {total_minutes:.1f} minutes ({total_seconds:.0f} seconds)")
            else:
                print(f"  {combo_count:,} combinations: {total_seconds:.1f} seconds")
        
        print("\nUsing best-case (minimum) query time:")
        for combo_count in [100000, 1000000, 3110400]:
            total_ms = combo_count * overall_min
            total_minutes = total_ms / 1000 / 60
            total_hours = total_minutes / 60
            
            if total_hours >= 1:
                print(f"  {combo_count:,} combinations: {total_hours:.1f} hours")
            else:
                print(f"  {combo_count:,} combinations: {total_minutes:.1f} minutes")
        
        print("\nUsing worst-case (maximum) query time:")
        for combo_count in [100000, 1000000, 3110400]:
            total_ms = combo_count * overall_max
            total_minutes = total_ms / 1000 / 60
            total_hours = total_minutes / 60
            
            if total_hours >= 1:
                print(f"  {combo_count:,} combinations: {total_hours:.1f} hours")
            else:
                print(f"  {combo_count:,} combinations: {total_minutes:.1f} minutes")
        
        # Parallel processing estimates
        print("\n" + "=" * 80)
        print("PARALLEL PROCESSING ESTIMATES")
        print("=" * 80)
        print("(Assuming database can handle concurrent queries)")
        
        parallel_factors = [2, 4, 8, 16]
        for factor in parallel_factors:
            print(f"\nWith {factor} parallel workers:")
            total_ms = 1000000 * overall_avg / factor
            total_minutes = total_ms / 1000 / 60
            total_hours = total_minutes / 60
            
            if total_hours >= 1:
                print(f"  1,000,000 combinations: {total_hours:.1f} hours")
            else:
                print(f"  1,000,000 combinations: {total_minutes:.1f} minutes")
    
    # Close pool
    await pool.close()


if __name__ == "__main__":
    asyncio.run(run_performance_test())