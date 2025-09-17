"""
Service for optimizing screener filter parameters based on backtest performance.
"""

import logging
import asyncpg
from typing import List, Dict, Optional, Tuple, Any
from datetime import date, datetime
from itertools import product
import numpy as np
import time

from ..models.filter_optimization import (
    OptimizationRequest,
    OptimizationResponse,
    OptimizationResult,
    OptimizationTarget,
    FilterCombination,
    FilterSearchSpace
)
from ..services.database import db_pool

logger = logging.getLogger(__name__)


class FilterOptimizer:
    """Optimizes screener filter parameters based on historical performance"""
    
    def __init__(self):
        self.db_pool = db_pool
    
    async def optimize_filters(self, request: OptimizationRequest) -> OptimizationResponse:
        """
        Main optimization method that tests different filter combinations
        and ranks them based on the target metric.
        """
        start_time = time.time()
        
        # Generate all filter combinations to test
        combinations = self._generate_filter_combinations(request.search_space)
        logger.info(f"Testing {len(combinations)} filter combinations")
        
        # Test each combination
        results = []
        for i, combo in enumerate(combinations):
            if i % 10 == 0:
                logger.info(f"Testing combination {i+1}/{len(combinations)}")
            
            result = await self._evaluate_filter_combination(
                combo, 
                request.start_date, 
                request.end_date,
                request.pivot_bars,
                request.min_symbols_required
            )
            
            if result and result['total_symbols_matched'] >= request.min_symbols_required:
                # Calculate target score
                target_score = self._calculate_target_score(result, request.target, request.custom_formula)
                
                results.append({
                    'combination': combo,
                    'metrics': result,
                    'target_score': target_score
                })
        
        # Sort by target score (higher is better)
        results.sort(key=lambda x: x['target_score'], reverse=True)
        
        # Format top results
        top_results = []
        for i, r in enumerate(results[:request.max_results]):
            opt_result = OptimizationResult(
                rank=i + 1,
                filter_combination=FilterCombination(**r['combination']),
                avg_sharpe_ratio=r['metrics']['avg_sharpe_ratio'],
                avg_total_return=r['metrics']['avg_total_return'],
                avg_win_rate=r['metrics']['avg_win_rate'],
                avg_profit_factor=r['metrics']['avg_profit_factor'],
                avg_max_drawdown=r['metrics']['avg_max_drawdown'],
                total_symbols_matched=r['metrics']['total_symbols_matched'],
                total_backtests=r['metrics']['total_backtests'],
                target_score=r['target_score'],
                sample_symbols=r['metrics']['sample_symbols'][:10]
            )
            top_results.append(opt_result)
        
        execution_time = int((time.time() - start_time) * 1000)
        
        return OptimizationResponse(
            request_summary={
                'target': request.target.value,
                'date_range': f"{request.start_date} to {request.end_date}",
                'min_symbols': request.min_symbols_required,
                'pivot_bars': request.pivot_bars
            },
            results=top_results,
            total_combinations_tested=len(combinations),
            execution_time_ms=execution_time,
            date_range_analyzed={
                'start': str(request.start_date),
                'end': str(request.end_date)
            },
            optimization_target=request.target.value,
            best_combination=top_results[0] if top_results else None
        )
    
    def _generate_filter_combinations(self, search_space: FilterSearchSpace) -> List[Dict]:
        """Generate all possible filter combinations from the search space"""
        combinations = []
        
        # Generate value ranges for each filter
        ranges = {}
        
        if search_space.price_min:
            ranges['price_min'] = np.arange(
                search_space.price_min.min_value,
                search_space.price_min.max_value + search_space.price_min.step,
                search_space.price_min.step
            )
        
        if search_space.price_max:
            ranges['price_max'] = np.arange(
                search_space.price_max.min_value,
                search_space.price_max.max_value + search_space.price_max.step,
                search_space.price_max.step
            )
        
        if search_space.rsi_min:
            ranges['rsi_min'] = np.arange(
                search_space.rsi_min.min_value,
                search_space.rsi_min.max_value + search_space.rsi_min.step,
                search_space.rsi_min.step
            )
        
        if search_space.rsi_max:
            ranges['rsi_max'] = np.arange(
                search_space.rsi_max.min_value,
                search_space.rsi_max.max_value + search_space.rsi_max.step,
                search_space.rsi_max.step
            )
        
        if search_space.gap_min:
            ranges['gap_min'] = np.arange(
                search_space.gap_min.min_value,
                search_space.gap_min.max_value + search_space.gap_min.step,
                search_space.gap_min.step
            )
        
        if search_space.gap_max:
            ranges['gap_max'] = np.arange(
                search_space.gap_max.min_value,
                search_space.gap_max.max_value + search_space.gap_max.step,
                search_space.gap_max.step
            )
        
        if search_space.volume_min:
            ranges['volume_min'] = np.arange(
                search_space.volume_min.min_value,
                search_space.volume_min.max_value + search_space.volume_min.step,
                search_space.volume_min.step
            )
        
        if search_space.rel_volume_min:
            ranges['rel_volume_min'] = np.arange(
                search_space.rel_volume_min.min_value,
                search_space.rel_volume_min.max_value + search_space.rel_volume_min.step,
                search_space.rel_volume_min.step
            )
        
        # Generate cartesian product of all ranges
        if ranges:
            keys = list(ranges.keys())
            values = [ranges[k] for k in keys]
            
            for combo_values in product(*values):
                combo = {}
                for i, key in enumerate(keys):
                    value = float(combo_values[i])
                    
                    # Group into appropriate filter structures
                    if key in ['price_min', 'price_max']:
                        if 'price_range' not in combo:
                            combo['price_range'] = {}
                        combo['price_range'][key.replace('price_', '')] = value
                    elif key in ['rsi_min', 'rsi_max']:
                        if 'rsi_range' not in combo:
                            combo['rsi_range'] = {}
                        combo['rsi_range'][key.replace('rsi_', '')] = value
                    elif key in ['gap_min', 'gap_max']:
                        if 'gap_range' not in combo:
                            combo['gap_range'] = {}
                        combo['gap_range'][key.replace('gap_', '')] = value
                    else:
                        combo[key] = value
                
                # Validate combinations (e.g., min < max)
                if self._is_valid_combination(combo):
                    combinations.append(combo)
        
        # Add MA conditions if specified
        if search_space.ma_conditions:
            if combinations:
                # Add MA conditions to existing combinations
                new_combinations = []
                for combo in combinations:
                    for ma_condition in search_space.ma_conditions:
                        new_combo = combo.copy()
                        new_combo['ma_condition'] = ma_condition
                        new_combinations.append(new_combo)
                combinations = new_combinations
            else:
                # Only MA conditions
                for ma_condition in search_space.ma_conditions:
                    combinations.append({'ma_condition': ma_condition})
        
        return combinations if combinations else [{}]  # Return empty filter if no ranges specified
    
    def _is_valid_combination(self, combo: Dict) -> bool:
        """Validate that filter combination makes sense"""
        # Check price range
        if 'price_range' in combo and 'min' in combo['price_range'] and 'max' in combo['price_range']:
            if combo['price_range']['min'] >= combo['price_range']['max']:
                return False
        
        # Check RSI range
        if 'rsi_range' in combo and 'min' in combo['rsi_range'] and 'max' in combo['rsi_range']:
            if combo['rsi_range']['min'] >= combo['rsi_range']['max']:
                return False
        
        # Check gap range
        if 'gap_range' in combo and 'min' in combo['gap_range'] and 'max' in combo['gap_range']:
            if combo['gap_range']['min'] >= combo['gap_range']['max']:
                return False
        
        return True
    
    async def _evaluate_filter_combination(
        self, 
        combination: Dict,
        start_date: date,
        end_date: date,
        pivot_bars: Optional[int],
        min_symbols: int
    ) -> Optional[Dict]:
        """Evaluate a single filter combination against historical data"""
        
        # Build the WHERE clause based on the filter combination
        where_conditions = ["gs.date BETWEEN $1 AND $2"]
        params = [start_date, end_date]
        param_count = 2
        
        # Add price filter
        if 'price_range' in combination:
            if 'min' in combination['price_range']:
                param_count += 1
                where_conditions.append(f"gs.price >= ${param_count}")
                params.append(combination['price_range']['min'])
            if 'max' in combination['price_range']:
                param_count += 1
                where_conditions.append(f"gs.price <= ${param_count}")
                params.append(combination['price_range']['max'])
        
        # Add RSI filter
        if 'rsi_range' in combination:
            if 'min' in combination['rsi_range']:
                param_count += 1
                where_conditions.append(f"gs.rsi_14 >= ${param_count}")
                params.append(combination['rsi_range']['min'])
            if 'max' in combination['rsi_range']:
                param_count += 1
                where_conditions.append(f"gs.rsi_14 <= ${param_count}")
                params.append(combination['rsi_range']['max'])
        
        # Add gap filter
        if 'gap_range' in combination:
            if 'min' in combination['gap_range']:
                param_count += 1
                where_conditions.append(f"gs.gap_percent >= ${param_count}")
                params.append(combination['gap_range']['min'])
            if 'max' in combination['gap_range']:
                param_count += 1
                where_conditions.append(f"gs.gap_percent <= ${param_count}")
                params.append(combination['gap_range']['max'])
        
        # Add volume filter
        if 'volume_min' in combination:
            param_count += 1
            where_conditions.append(f"gs.prev_day_dollar_volume >= ${param_count}")
            params.append(combination['volume_min'])
        
        # Add relative volume filter
        if 'rel_volume_min' in combination:
            param_count += 1
            where_conditions.append(f"gs.relative_volume >= ${param_count}")
            params.append(combination['rel_volume_min'])
        
        # Add MA condition
        if 'ma_condition' in combination:
            ma_period = combination['ma_condition'].get('period', 50)
            condition = combination['ma_condition'].get('condition', 'above')
            ma_column = f"ma_{ma_period}"
            
            if condition == 'above':
                where_conditions.append(f"gs.price > gs.{ma_column}")
            else:
                where_conditions.append(f"gs.price < gs.{ma_column}")
        
        # Add pivot bars filter if specified
        if pivot_bars is not None:
            param_count += 1
            where_conditions.append(f"gms.pivot_bars = ${param_count}")
            params.append(pivot_bars)
        
        # Build the query
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
        
        try:
            result = await self.db_pool.fetchrow(query, *params)
            
            if result and result['total_symbols'] and result['total_symbols'] >= min_symbols:
                return {
                    'total_symbols_matched': result['total_symbols'],
                    'total_backtests': result['total_backtests'],
                    'avg_total_return': float(result['avg_total_return'] or 0),
                    'avg_sharpe_ratio': float(result['avg_sharpe_ratio'] or 0),
                    'avg_max_drawdown': float(result['avg_max_drawdown'] or 0),
                    'avg_win_rate': float(result['avg_win_rate'] or 0),
                    'avg_profit_factor': float(result['avg_profit_factor'] or 0),
                    'sample_symbols': result['all_symbols'][:20] if result['all_symbols'] else []
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error evaluating filter combination: {e}")
            return None
    
    def _calculate_target_score(self, metrics: Dict, target: OptimizationTarget, custom_formula: Optional[str]) -> float:
        """Calculate the target score based on the optimization target"""
        
        if target == OptimizationTarget.SHARPE_RATIO:
            return metrics['avg_sharpe_ratio']
        elif target == OptimizationTarget.TOTAL_RETURN:
            return metrics['avg_total_return']
        elif target == OptimizationTarget.WIN_RATE:
            return metrics['avg_win_rate']
        elif target == OptimizationTarget.PROFIT_FACTOR:
            return metrics['avg_profit_factor']
        elif target == OptimizationTarget.MIN_DRAWDOWN:
            # For drawdown, lower is better, so we negate it
            return -metrics['avg_max_drawdown']
        elif target == OptimizationTarget.CUSTOM and custom_formula:
            # Parse and evaluate custom formula
            # For now, we'll use a simple weighted combination
            # In production, you'd want a proper formula parser
            try:
                # Example: "0.4*sharpe + 0.3*win_rate - 0.3*drawdown"
                # This is simplified - in production use a proper expression evaluator
                return (
                    0.4 * metrics['avg_sharpe_ratio'] + 
                    0.3 * (metrics['avg_win_rate'] / 100) + 
                    0.2 * (metrics['avg_total_return'] / 100) -
                    0.1 * metrics['avg_max_drawdown']
                )
            except:
                logger.error("Error evaluating custom formula, using Sharpe ratio")
                return metrics['avg_sharpe_ratio']
        else:
            # Default to Sharpe ratio
            return metrics['avg_sharpe_ratio']