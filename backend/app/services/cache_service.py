"""
Cache service for storing and retrieving screener and backtest results.

This service provides methods to check cache, store results, and manage cache lifecycle.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4

from app.models.cache_models import (
    CachedScreenerRequest,
    CachedScreenerResult,
    CachedBacktestRequest,
    CachedBacktestResult
)
from app.services.database import db_pool

logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing result caching."""
    
    def __init__(self, screener_ttl_hours: int = 24, backtest_ttl_days: int = 7):
        """
        Initialize cache service.
        
        Args:
            screener_ttl_hours: Time-to-live for screener results in hours
            backtest_ttl_days: Time-to-live for backtest results in days
        """
        self.screener_ttl_hours = screener_ttl_hours
        self.backtest_ttl_days = backtest_ttl_days
    
    @staticmethod
    def _convert_decimal_to_float(value: Optional[Decimal]) -> Optional[float]:
        """Convert Decimal to float for database storage."""
        return float(value) if value is not None else None
    
    @staticmethod
    def _convert_float_to_decimal(value: Optional[float]) -> Optional[Decimal]:
        """Convert float from database to Decimal."""
        return Decimal(str(value)) if value is not None else None
    
    async def get_screener_results(
        self, 
        request: CachedScreenerRequest
    ) -> Optional[List[CachedScreenerResult]]:
        """
        Retrieve cached screener results if available.
        
        Args:
            request: Screener request parameters
            
        Returns:
            List of CachedScreenerResult if cache hit, None if cache miss
        """
        # Calculate hash for the parameters
        hash_value = request.calculate_hash()
        
        try:
            # Look for cached results by matching all filter parameters
            query = """
                SELECT 
                    id, symbol, company_name, screened_at, data_date,
                    filter_min_price, filter_max_price,
                    filter_price_vs_ma_enabled, filter_price_vs_ma_period, filter_price_vs_ma_condition,
                    filter_rsi_enabled, filter_rsi_period, filter_rsi_threshold, filter_rsi_condition,
                    filter_gap_enabled, filter_gap_threshold, filter_gap_direction,
                    filter_prev_day_dollar_volume_enabled, filter_prev_day_dollar_volume,
                    filter_relative_volume_enabled, filter_relative_volume_recent_days,
                    filter_relative_volume_lookback_days, filter_relative_volume_min_ratio,
                    session_id, created_at
                FROM screener_results 
                WHERE data_date >= $1 AND data_date <= $2
                AND (filter_min_price = $3 OR (filter_min_price IS NULL AND $3 IS NULL))
                AND (filter_max_price = $4 OR (filter_max_price IS NULL AND $4 IS NULL))
                AND filter_price_vs_ma_enabled = $5
                AND (filter_price_vs_ma_period = $6 OR (filter_price_vs_ma_period IS NULL AND $6 IS NULL))
                AND (filter_price_vs_ma_condition = $7 OR (filter_price_vs_ma_condition IS NULL AND $7 IS NULL))
                AND filter_rsi_enabled = $8
                AND (filter_rsi_period = $9 OR (filter_rsi_period IS NULL AND $9 IS NULL))
                AND (filter_rsi_threshold = $10 OR (filter_rsi_threshold IS NULL AND $10 IS NULL))
                AND (filter_rsi_condition = $11 OR (filter_rsi_condition IS NULL AND $11 IS NULL))
                AND filter_gap_enabled = $12
                AND (filter_gap_threshold = $13 OR (filter_gap_threshold IS NULL AND $13 IS NULL))
                AND (filter_gap_direction = $14 OR (filter_gap_direction IS NULL AND $14 IS NULL))
                AND filter_prev_day_dollar_volume_enabled = $15
                AND (filter_prev_day_dollar_volume = $16 OR (filter_prev_day_dollar_volume IS NULL AND $16 IS NULL))
                AND filter_relative_volume_enabled = $17
                AND (filter_relative_volume_recent_days = $18 OR (filter_relative_volume_recent_days IS NULL AND $18 IS NULL))
                AND (filter_relative_volume_lookback_days = $19 OR (filter_relative_volume_lookback_days IS NULL AND $19 IS NULL))
                AND (filter_relative_volume_min_ratio = $20 OR (filter_relative_volume_min_ratio IS NULL AND $20 IS NULL))
                AND screened_at > NOW() - INTERVAL '{} hours'
                ORDER BY screened_at DESC, symbol
            """.format(self.screener_ttl_hours)
            
            rows = await db_pool.fetch(
                query,
                request.start_date,
                request.end_date,
                self._convert_decimal_to_float(request.min_price),
                self._convert_decimal_to_float(request.max_price),
                request.price_vs_ma_enabled,
                request.price_vs_ma_period,
                request.price_vs_ma_condition,
                request.rsi_enabled,
                request.rsi_period,
                self._convert_decimal_to_float(request.rsi_threshold),
                request.rsi_condition,
                request.gap_enabled,
                self._convert_decimal_to_float(request.gap_threshold),
                request.gap_direction,
                request.prev_day_dollar_volume_enabled,
                self._convert_decimal_to_float(request.prev_day_dollar_volume),
                request.relative_volume_enabled,
                request.relative_volume_recent_days,
                request.relative_volume_lookback_days,
                self._convert_decimal_to_float(request.relative_volume_min_ratio)
            )
            
            if rows:
                # Update cache hit statistics
                await self._update_cache_stats('screener', hit=True)
                logger.info(f"Cache hit for screener with hash {hash_value}")
                
                # Convert rows to CachedScreenerResult objects
                results = []
                for row in rows:
                    result = CachedScreenerResult(
                        id=row['id'],
                        symbol=row['symbol'],
                        company_name=row['company_name'],
                        screened_at=row['screened_at'],
                        data_date=row['data_date'],
                        filter_min_price=self._convert_float_to_decimal(row['filter_min_price']),
                        filter_max_price=self._convert_float_to_decimal(row['filter_max_price']),
                        filter_price_vs_ma_enabled=row['filter_price_vs_ma_enabled'],
                        filter_price_vs_ma_period=row['filter_price_vs_ma_period'],
                        filter_price_vs_ma_condition=row['filter_price_vs_ma_condition'],
                        filter_rsi_enabled=row['filter_rsi_enabled'],
                        filter_rsi_period=row['filter_rsi_period'],
                        filter_rsi_threshold=self._convert_float_to_decimal(row['filter_rsi_threshold']),
                        filter_rsi_condition=row['filter_rsi_condition'],
                        filter_gap_enabled=row['filter_gap_enabled'],
                        filter_gap_threshold=self._convert_float_to_decimal(row['filter_gap_threshold']),
                        filter_gap_direction=row['filter_gap_direction'],
                        filter_prev_day_dollar_volume_enabled=row['filter_prev_day_dollar_volume_enabled'],
                        filter_prev_day_dollar_volume=self._convert_float_to_decimal(row['filter_prev_day_dollar_volume']),
                        filter_relative_volume_enabled=row['filter_relative_volume_enabled'],
                        filter_relative_volume_recent_days=row['filter_relative_volume_recent_days'],
                        filter_relative_volume_lookback_days=row['filter_relative_volume_lookback_days'],
                        filter_relative_volume_min_ratio=self._convert_float_to_decimal(row['filter_relative_volume_min_ratio']),
                        session_id=row['session_id'],
                        created_at=row['created_at']
                    )
                    results.append(result)
                
                return results
            else:
                # Update cache miss statistics
                await self._update_cache_stats('screener', hit=False)
                logger.info(f"Cache miss for screener with hash {hash_value}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving cached screener results: {e}")
            return None
    
    async def save_screener_results(
        self, 
        request: CachedScreenerRequest,
        results: List[CachedScreenerResult]
    ) -> bool:
        """
        Save screener results to cache.
        
        Args:
            request: Screener request parameters
            results: List of screener results to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not results:
            logger.warning("No results to save to cache")
            return False
            
        session_id = uuid4()
        
        try:
            # Insert all results in a batch
            query = """
                INSERT INTO screener_results (
                    id, symbol, company_name, screened_at, data_date,
                    filter_min_price, filter_max_price,
                    filter_price_vs_ma_enabled, filter_price_vs_ma_period, filter_price_vs_ma_condition,
                    filter_rsi_enabled, filter_rsi_period, filter_rsi_threshold, filter_rsi_condition,
                    filter_gap_enabled, filter_gap_threshold, filter_gap_direction,
                    filter_prev_day_dollar_volume_enabled, filter_prev_day_dollar_volume,
                    filter_relative_volume_enabled, filter_relative_volume_recent_days,
                    filter_relative_volume_lookback_days, filter_relative_volume_min_ratio,
                    session_id, created_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25
                )
            """
            
            # Prepare batch data
            batch_data = []
            for result in results:
                batch_data.append((
                    result.id,
                    result.symbol,
                    result.company_name,
                    result.screened_at,
                    result.data_date,
                    self._convert_decimal_to_float(request.min_price),
                    self._convert_decimal_to_float(request.max_price),
                    request.price_vs_ma_enabled,
                    request.price_vs_ma_period,
                    request.price_vs_ma_condition,
                    request.rsi_enabled,
                    request.rsi_period,
                    self._convert_decimal_to_float(request.rsi_threshold),
                    request.rsi_condition,
                    request.gap_enabled,
                    self._convert_decimal_to_float(request.gap_threshold),
                    request.gap_direction,
                    request.prev_day_dollar_volume_enabled,
                    self._convert_decimal_to_float(request.prev_day_dollar_volume),
                    request.relative_volume_enabled,
                    request.relative_volume_recent_days,
                    request.relative_volume_lookback_days,
                    self._convert_decimal_to_float(request.relative_volume_min_ratio),
                    session_id,
                    result.created_at
                ))
            
            # Execute batch insert
            await db_pool.executemany(query, batch_data)
            
            logger.info(f"Saved {len(results)} screener results to cache with session_id {session_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving screener results to cache: {e}")
            return False
    
    async def get_backtest_results(
        self,
        request: CachedBacktestRequest
    ) -> Optional[CachedBacktestResult]:
        """
        Retrieve cached backtest results if available.
        
        Args:
            request: Backtest request parameters
            
        Returns:
            CachedBacktestResult if cache hit, None if cache miss
        """
        hash_value = request.calculate_hash()
        
        try:
            # Look for cached results by matching the new cache key parameters
            query = """
                SELECT 
                    id, backtest_id, symbol, strategy_name,
                    initial_cash, pivot_bars, lower_timeframe,
                    start_date, end_date,
                    total_return, net_profit, net_profit_currency,
                    compounding_annual_return, final_value, start_equity, end_equity,
                    sharpe_ratio, sortino_ratio, max_drawdown,
                    probabilistic_sharpe_ratio, annual_standard_deviation, annual_variance,
                    beta, alpha,
                    total_trades, winning_trades, losing_trades, win_rate, loss_rate,
                    average_win_percentage as average_win, average_loss_percentage as average_loss, 
                    profit_factor, profit_factor as profit_loss_ratio,
                    expectancy, total_orders,
                    information_ratio, tracking_error, treynor_ratio, 
                    total_fees,
                    estimated_strategy_capacity, lowest_capacity_asset, 
                    portfolio_turnover,
                    pivot_highs_detected, pivot_lows_detected, bos_signals_generated,
                    position_flips, liquidation_events,
                    execution_time_ms, result_path, status, error_message, cache_hit,
                    created_at
                FROM market_structure_results 
                WHERE symbol = $1
                AND strategy_name = $2
                AND start_date = $3 AND end_date = $4
                AND initial_cash = $5
                AND pivot_bars = $6
                AND lower_timeframe = $7
                AND status = 'completed'
                AND created_at > NOW() - INTERVAL '{} days'
                ORDER BY created_at DESC
                LIMIT 1
            """.format(self.backtest_ttl_days)
            
            row = await db_pool.fetchrow(
                query,
                request.symbol,
                request.strategy_name,
                request.start_date,
                request.end_date,
                self._convert_decimal_to_float(request.initial_cash),
                request.pivot_bars,
                request.lower_timeframe
            )
            
            if row:
                # Update cache hit statistics
                await self._update_cache_stats('market_structure', hit=True)
                logger.info(f"Cache hit for backtest {request.symbol} with hash {hash_value}")
                
                # Convert row to CachedBacktestResult using new model structure
                result = CachedBacktestResult(
                    id=row['id'],
                    backtest_id=row['backtest_id'],
                    symbol=row['symbol'],
                    strategy_name=row['strategy_name'],
                    initial_cash=self._convert_float_to_decimal(row['initial_cash']),
                    pivot_bars=row['pivot_bars'],
                    lower_timeframe=row['lower_timeframe'],
                    start_date=row['start_date'],
                    end_date=row['end_date'],
                    total_return=self._convert_float_to_decimal(row['total_return']),
                    net_profit=self._convert_float_to_decimal(row['net_profit']),
                    net_profit_currency=self._convert_float_to_decimal(row['net_profit_currency']),
                    compounding_annual_return=self._convert_float_to_decimal(row['compounding_annual_return']),
                    final_value=self._convert_float_to_decimal(row['final_value']),
                    start_equity=self._convert_float_to_decimal(row['start_equity']),
                    end_equity=self._convert_float_to_decimal(row['end_equity']),
                    sharpe_ratio=self._convert_float_to_decimal(row['sharpe_ratio']),
                    sortino_ratio=self._convert_float_to_decimal(row['sortino_ratio']),
                    max_drawdown=self._convert_float_to_decimal(row['max_drawdown']),
                    probabilistic_sharpe_ratio=self._convert_float_to_decimal(row['probabilistic_sharpe_ratio']),
                    annual_standard_deviation=self._convert_float_to_decimal(row['annual_standard_deviation']),
                    annual_variance=self._convert_float_to_decimal(row['annual_variance']),
                    beta=self._convert_float_to_decimal(row['beta']),
                    alpha=self._convert_float_to_decimal(row['alpha']),
                    total_trades=row['total_trades'],
                    winning_trades=row['winning_trades'],
                    losing_trades=row['losing_trades'],
                    win_rate=self._convert_float_to_decimal(row['win_rate']),
                    loss_rate=self._convert_float_to_decimal(row['loss_rate']),
                    average_win=self._convert_float_to_decimal(row['average_win']),
                    average_loss=self._convert_float_to_decimal(row['average_loss']),
                    profit_factor=self._convert_float_to_decimal(row['profit_factor']),
                    profit_loss_ratio=self._convert_float_to_decimal(row['profit_loss_ratio']),
                    expectancy=self._convert_float_to_decimal(row['expectancy']),
                    total_orders=row['total_orders'],
                    information_ratio=self._convert_float_to_decimal(row['information_ratio']),
                    tracking_error=self._convert_float_to_decimal(row['tracking_error']),
                    treynor_ratio=self._convert_float_to_decimal(row['treynor_ratio']),
                    total_fees=self._convert_float_to_decimal(row['total_fees']),
                    estimated_strategy_capacity=self._convert_float_to_decimal(row['estimated_strategy_capacity']),
                    lowest_capacity_asset=row['lowest_capacity_asset'],
                    portfolio_turnover=self._convert_float_to_decimal(row['portfolio_turnover']),
                    pivot_highs_detected=row['pivot_highs_detected'],
                    pivot_lows_detected=row['pivot_lows_detected'],
                    bos_signals_generated=row['bos_signals_generated'],
                    position_flips=row['position_flips'],
                    liquidation_events=row['liquidation_events'],
                    execution_time_ms=row['execution_time_ms'],
                    result_path=row['result_path'],
                    status=row['status'],
                    error_message=row['error_message'],
                    cache_hit=row['cache_hit'],
                    created_at=row['created_at']
                )
                
                return result
            else:
                # Update cache miss statistics
                await self._update_cache_stats('market_structure', hit=False)
                logger.info(f"Cache miss for backtest {request.symbol} with hash {hash_value}")
                return None
                
        except Exception as e:
            logger.error(f"Error retrieving cached backtest results: {e}")
            return None
    
    async def save_backtest_results(
        self,
        result: CachedBacktestResult
    ) -> bool:
        """
        Save backtest results to cache.
        
        Args:
            result: Backtest result to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            # Insert new backtest result with new schema
            query = """
                INSERT INTO market_structure_results (
                    id, backtest_id, symbol, strategy_name,
                    initial_cash, pivot_bars, lower_timeframe,
                    start_date, end_date,
                    total_return, net_profit, net_profit_currency,
                    compounding_annual_return, final_value, start_equity, end_equity,
                    sharpe_ratio, sortino_ratio, max_drawdown,
                    probabilistic_sharpe_ratio, annual_standard_deviation, annual_variance,
                    beta, alpha,
                    total_trades, winning_trades, losing_trades, win_rate, loss_rate,
                    average_win_percentage, average_loss_percentage, profit_factor, profit_loss_ratio,
                    expectancy, total_orders,
                    information_ratio, tracking_error, treynor_ratio,
                    total_fees, estimated_strategy_capacity, lowest_capacity_asset,
                    portfolio_turnover,
                    pivot_highs_detected, pivot_lows_detected, bos_signals_generated,
                    position_flips, liquidation_events,
                    execution_time_ms, result_path, status, error_message, cache_hit,
                    created_at, resolution
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22,
                    $23, $24, $25, $26, $27, $28, $29, $30, $31, $32,
                    $33, $34, $35, $36, $37, $38, $39, $40, $41, $42,
                    $43, $44, $45, $46, $47, $48, $49, $50, $51, $52, $53, $54
                )
            """
            
            await db_pool.execute(
                query,
                result.id,
                result.backtest_id,
                result.symbol,
                result.strategy_name,
                self._convert_decimal_to_float(result.initial_cash),
                result.pivot_bars,
                result.lower_timeframe,
                result.start_date,
                result.end_date,
                self._convert_decimal_to_float(result.total_return),
                self._convert_decimal_to_float(result.net_profit),
                self._convert_decimal_to_float(result.net_profit_currency),
                self._convert_decimal_to_float(result.compounding_annual_return),
                self._convert_decimal_to_float(result.final_value),
                self._convert_decimal_to_float(result.start_equity),
                self._convert_decimal_to_float(result.end_equity),
                self._convert_decimal_to_float(result.sharpe_ratio),
                self._convert_decimal_to_float(result.sortino_ratio),
                self._convert_decimal_to_float(result.max_drawdown),
                self._convert_decimal_to_float(result.probabilistic_sharpe_ratio),
                self._convert_decimal_to_float(result.annual_standard_deviation),
                self._convert_decimal_to_float(result.annual_variance),
                self._convert_decimal_to_float(result.beta),
                self._convert_decimal_to_float(result.alpha),
                result.total_trades,
                result.winning_trades,
                result.losing_trades,
                self._convert_decimal_to_float(result.win_rate),
                self._convert_decimal_to_float(result.loss_rate),
                self._convert_decimal_to_float(result.average_win),
                self._convert_decimal_to_float(result.average_loss),
                self._convert_decimal_to_float(result.profit_factor),
                self._convert_decimal_to_float(result.profit_loss_ratio),
                self._convert_decimal_to_float(result.expectancy),
                result.total_orders,
                self._convert_decimal_to_float(result.information_ratio),
                self._convert_decimal_to_float(result.tracking_error),
                self._convert_decimal_to_float(result.treynor_ratio),
                self._convert_decimal_to_float(result.total_fees),
                self._convert_decimal_to_float(result.estimated_strategy_capacity),
                result.lowest_capacity_asset,
                self._convert_decimal_to_float(result.portfolio_turnover),
                result.pivot_highs_detected,
                result.pivot_lows_detected,
                result.bos_signals_generated,
                result.position_flips,
                result.liquidation_events,
                result.execution_time_ms,
                result.result_path,
                result.status,
                result.error_message,
                result.cache_hit,
                result.created_at,
                result.resolution if hasattr(result, 'resolution') else 'Daily'
            )
            
            logger.info(f"Saved backtest results for {result.symbol} with backtest_id {result.backtest_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving backtest results to cache: {e}")
            return False
    
    async def _update_cache_stats(
        self, 
        cache_type: str, 
        hit: bool
    ) -> None:
        """
        Update cache hit/miss statistics.
        
        Args:
            cache_type: Type of cache ('screener' or 'market_structure')
            hit: True for cache hit, False for cache miss
        """
        try:
            if hit:
                query = """
                    UPDATE cache_metadata 
                    SET total_hits = total_hits + 1,
                        updated_at = NOW()
                    WHERE cache_type = $1
                """
            else:
                query = """
                    UPDATE cache_metadata 
                    SET total_misses = total_misses + 1,
                        updated_at = NOW()
                    WHERE cache_type = $1
                """
            
            await db_pool.execute(query, cache_type)
            
        except Exception as e:
            logger.error(f"Error updating cache statistics: {e}")
    
    async def clean_expired_cache(self) -> Tuple[int, int]:
        """
        Clean expired cache entries.
        
        Returns:
            Tuple of (screener_deleted, backtest_deleted) counts
        """
        try:
            # Delete old screener results based on TTL
            screener_query = """
                DELETE FROM screener_results 
                WHERE screened_at < NOW() - INTERVAL '{} hours'
                RETURNING id
            """.format(self.screener_ttl_hours)
            screener_result = await db_pool.fetch(screener_query)
            screener_count = len(screener_result)
            
            # Delete old backtest results based on TTL
            backtest_query = """
                DELETE FROM market_structure_results 
                WHERE created_at < NOW() - INTERVAL '{} days'
                RETURNING id
            """.format(self.backtest_ttl_days)
            backtest_result = await db_pool.fetch(backtest_query)
            backtest_count = len(backtest_result)
            
            # Update cleanup timestamp
            update_query = """
                UPDATE cache_metadata 
                SET last_cleanup = NOW(), updated_at = NOW()
                WHERE cache_type IN ('screener', 'market_structure')
            """
            await db_pool.execute(update_query)
            
            logger.info(f"Cleaned {screener_count} screener and {backtest_count} backtest cache entries")
            return screener_count, backtest_count
            
        except Exception as e:
            logger.error(f"Error cleaning expired cache: {e}")
            return 0, 0
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        try:
            # Get all cache metadata
            metadata_query = """
                SELECT cache_type, total_hits, total_misses, last_cleanup
                FROM cache_metadata
                WHERE cache_type IN ('screener', 'market_structure')
            """
            metadata_rows = await db_pool.fetch(metadata_query)
            
            # Count active entries
            screener_count_query = """
                SELECT COUNT(*) as count 
                FROM screener_results 
                WHERE screened_at > NOW() - INTERVAL '{} hours'
            """.format(self.screener_ttl_hours)
            screener_count = await db_pool.fetchval(screener_count_query)
            
            backtest_count_query = """
                SELECT COUNT(*) as count 
                FROM market_structure_results 
                WHERE created_at > NOW() - INTERVAL '{} days'
            """.format(self.backtest_ttl_days)
            backtest_count = await db_pool.fetchval(backtest_count_query)
            
            # Process metadata
            stats = {
                'screener': {
                    'active_entries': screener_count or 0,
                    'total_hits': 0,
                    'total_misses': 0,
                    'hit_rate': 0,
                    'last_cleanup': None
                },
                'backtest': {
                    'active_entries': backtest_count or 0,
                    'total_hits': 0,
                    'total_misses': 0,
                    'hit_rate': 0,
                    'last_cleanup': None
                }
            }
            
            for row in metadata_rows:
                cache_type = row['cache_type']
                if cache_type == 'screener':
                    stats['screener']['total_hits'] = row['total_hits'] or 0
                    stats['screener']['total_misses'] = row['total_misses'] or 0
                    total = stats['screener']['total_hits'] + stats['screener']['total_misses']
                    if total > 0:
                        stats['screener']['hit_rate'] = (stats['screener']['total_hits'] / total) * 100
                    if row['last_cleanup']:
                        stats['screener']['last_cleanup'] = row['last_cleanup'].isoformat()
                elif cache_type == 'market_structure':
                    stats['backtest']['total_hits'] = row['total_hits'] or 0
                    stats['backtest']['total_misses'] = row['total_misses'] or 0
                    total = stats['backtest']['total_hits'] + stats['backtest']['total_misses']
                    if total > 0:
                        stats['backtest']['hit_rate'] = (stats['backtest']['total_hits'] / total) * 100
                    if row['last_cleanup']:
                        stats['backtest']['last_cleanup'] = row['last_cleanup'].isoformat()
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting cache statistics: {e}")
            return {
                'screener': {'error': str(e)},
                'backtest': {'error': str(e)}
            }
    
    # Compatibility methods for the old interface
    async def get_screener_results_legacy(
        self, 
        filters: Dict[str, Any], 
        date_range: Dict[str, str]
    ) -> Optional[List[str]]:
        """
        Legacy method for retrieving cached screener results.
        
        Args:
            filters: Screener filter parameters
            date_range: Date range for screening
            
        Returns:
            List of symbols if cache hit, None if cache miss
        """
        # Convert old format to new model
        from datetime import datetime
        request = CachedScreenerRequest(
            start_date=datetime.fromisoformat(date_range['start']).date(),
            end_date=datetime.fromisoformat(date_range['end']).date(),
            min_price=filters.get('min_price'),
            max_price=filters.get('max_price'),
            # Map old filters to new schema
            price_vs_ma_enabled=filters.get('above_sma20', False),
            price_vs_ma_period=20 if filters.get('above_sma20', False) else None,
            price_vs_ma_condition='above' if filters.get('above_sma20', False) else None,
            rsi_enabled=filters.get('rsi_enabled', False),
            rsi_period=filters.get('rsi_period'),
            rsi_threshold=filters.get('rsi_threshold'),
            rsi_condition=filters.get('rsi_condition'),
            gap_enabled=filters.get('min_gap') is not None or filters.get('gap_enabled', False),
            gap_threshold=filters.get('min_gap') or filters.get('gap_threshold'),
            gap_direction=filters.get('gap_direction', 'up') if filters.get('min_gap') is not None else None,
            prev_day_dollar_volume_enabled=filters.get('min_volume') is not None or filters.get('prev_day_dollar_volume_enabled', False),
            prev_day_dollar_volume=Decimal(str(filters['min_volume'] * 100)) if filters.get('min_volume') else filters.get('prev_day_dollar_volume'),  # Rough conversion
            relative_volume_enabled=filters.get('relative_volume_enabled', False),
            relative_volume_recent_days=filters.get('relative_volume_recent_days'),
            relative_volume_lookback_days=filters.get('relative_volume_lookback_days'),
            relative_volume_min_ratio=filters.get('relative_volume_min_ratio')
        )
        
        results = await self.get_screener_results(request)
        if results:
            # Return unique symbols
            symbols = list(set(result.symbol for result in results))
            return symbols
        return None
    
    async def save_screener_results_legacy(
        self, 
        filters: Dict[str, Any], 
        date_range: Dict[str, str],
        symbols: List[str],
        result_count: Optional[int] = None,
        processing_time: Optional[float] = None
    ) -> bool:
        """
        Legacy method for saving screener results.
        
        Args:
            filters: Screener filter parameters
            date_range: Date range for screening
            symbols: List of symbols from screening
            result_count: Number of results
            processing_time: Time taken to process
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Convert old format to new models
        from datetime import datetime
        request = CachedScreenerRequest(
            start_date=datetime.fromisoformat(date_range['start']).date(),
            end_date=datetime.fromisoformat(date_range['end']).date(),
            min_price=filters.get('min_price'),
            max_price=filters.get('max_price'),
            # Map old filters to new schema
            price_vs_ma_enabled=filters.get('above_sma20', False),
            price_vs_ma_period=20 if filters.get('above_sma20', False) else None,
            price_vs_ma_condition='above' if filters.get('above_sma20', False) else None,
            rsi_enabled=filters.get('rsi_enabled', False),
            rsi_period=filters.get('rsi_period'),
            rsi_threshold=filters.get('rsi_threshold'),
            rsi_condition=filters.get('rsi_condition'),
            gap_enabled=filters.get('min_gap') is not None or filters.get('gap_enabled', False),
            gap_threshold=filters.get('min_gap') or filters.get('gap_threshold'),
            gap_direction=filters.get('gap_direction', 'up') if filters.get('min_gap') is not None else None,
            prev_day_dollar_volume_enabled=filters.get('min_volume') is not None or filters.get('prev_day_dollar_volume_enabled', False),
            prev_day_dollar_volume=Decimal(str(filters['min_volume'] * 100)) if filters.get('min_volume') else filters.get('prev_day_dollar_volume'),  # Rough conversion
            relative_volume_enabled=filters.get('relative_volume_enabled', False),
            relative_volume_recent_days=filters.get('relative_volume_recent_days'),
            relative_volume_lookback_days=filters.get('relative_volume_lookback_days'),
            relative_volume_min_ratio=filters.get('relative_volume_min_ratio')
        )
        
        # Create minimal result objects for each symbol
        results = []
        data_date = datetime.fromisoformat(date_range['end']).date()
        for symbol in symbols:
            result = CachedScreenerResult(
                symbol=symbol,
                data_date=data_date
            )
            results.append(result)
        
        return await self.save_screener_results(request, results)
    
    async def get_backtest_results_legacy(
        self,
        symbol: str,
        date_range: Dict[str, str],
        parameters: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Legacy method for retrieving cached backtest results.
        
        Args:
            symbol: Stock symbol
            date_range: Date range for backtest
            parameters: Backtest parameters (must include new cache key parameters)
            
        Returns:
            Statistics dictionary if cache hit, None if cache miss
        """
        # Convert old format to new model - requires new cache key parameters
        from datetime import datetime
        
        # Validate that all required new parameters are present
        required_params = ['strategy_name', 'initial_cash', 'pivot_bars', 'lower_timeframe']
        missing_params = [param for param in required_params if param not in parameters]
        if missing_params:
            logger.warning(f"Missing required cache key parameters: {missing_params}")
            return None
            
        request = CachedBacktestRequest(
            symbol=symbol,
            strategy_name=parameters['strategy_name'],
            start_date=datetime.fromisoformat(date_range['start']).date(),
            end_date=datetime.fromisoformat(date_range['end']).date(),
            initial_cash=Decimal(str(parameters['initial_cash'])),
            pivot_bars=parameters['pivot_bars'],
            lower_timeframe=parameters['lower_timeframe']
        )
        
        result = await self.get_backtest_results(request)
        if result:
            # Convert result back to dictionary format with legacy field mappings
            return {
                'total_return': float(result.total_return),
                'net_profit': float(result.net_profit) if result.net_profit else None,
                'net_profit_currency': float(result.net_profit_currency) if result.net_profit_currency else None,
                'compounding_annual_return': float(result.compounding_annual_return) if result.compounding_annual_return else None,
                'final_value': float(result.final_value) if result.final_value else None,
                'start_equity': float(result.start_equity) if result.start_equity else None,
                'end_equity': float(result.end_equity) if result.end_equity else None,
                'win_rate': float(result.win_rate),
                'loss_rate': float(result.loss_rate) if result.loss_rate else None,
                'total_trades': result.total_trades,
                'winning_trades': result.winning_trades,
                'losing_trades': result.losing_trades,
                'average_win': float(result.average_win) if result.average_win else None,
                'average_loss': float(result.average_loss) if result.average_loss else None,
                'sharpe_ratio': float(result.sharpe_ratio) if result.sharpe_ratio else None,
                'sortino_ratio': float(result.sortino_ratio) if result.sortino_ratio else None,
                'max_drawdown': float(result.max_drawdown) if result.max_drawdown else None,
                'probabilistic_sharpe_ratio': float(result.probabilistic_sharpe_ratio) if result.probabilistic_sharpe_ratio else None,
                'annual_standard_deviation': float(result.annual_standard_deviation) if result.annual_standard_deviation else None,
                'annual_variance': float(result.annual_variance) if result.annual_variance else None,
                'beta': float(result.beta) if result.beta else None,
                'alpha': float(result.alpha) if result.alpha else None,
                'profit_factor': float(result.profit_factor) if result.profit_factor else None,
                'profit_loss_ratio': float(result.profit_loss_ratio) if result.profit_loss_ratio else None,
                'expectancy': float(result.expectancy) if result.expectancy else None,
                'total_orders': result.total_orders,
                'information_ratio': float(result.information_ratio) if result.information_ratio else None,
                'tracking_error': float(result.tracking_error) if result.tracking_error else None,
                'treynor_ratio': float(result.treynor_ratio) if result.treynor_ratio else None,
                'total_fees': float(result.total_fees) if result.total_fees else None,
                'estimated_strategy_capacity': float(result.estimated_strategy_capacity) if result.estimated_strategy_capacity else None,
                'lowest_capacity_asset': result.lowest_capacity_asset,
                'portfolio_turnover': float(result.portfolio_turnover) if result.portfolio_turnover else None,
                'pivot_highs_detected': result.pivot_highs_detected,
                'pivot_lows_detected': result.pivot_lows_detected,
                'bos_signals_generated': result.bos_signals_generated,
                'position_flips': result.position_flips,
                'liquidation_events': result.liquidation_events
            }
        return None
    
    async def save_backtest_results_legacy(
        self,
        symbol: str,
        date_range: Dict[str, str],
        parameters: Dict[str, Any],
        statistics: Dict[str, Any]
    ) -> bool:
        """
        Legacy method for saving backtest results.
        
        Args:
            symbol: Stock symbol
            date_range: Date range for backtest
            parameters: Backtest parameters (must include new cache key parameters)
            statistics: Backtest statistics
            
        Returns:
            True if saved successfully, False otherwise
        """
        # Convert old format to new model - requires new cache key parameters
        from datetime import datetime
        
        # Validate that all required new parameters are present
        required_params = ['strategy_name', 'initial_cash', 'pivot_bars', 'lower_timeframe']
        missing_params = [param for param in required_params if param not in parameters]
        if missing_params:
            logger.warning(f"Missing required cache key parameters: {missing_params}")
            return False
            
        result = CachedBacktestResult(
            backtest_id=uuid4(),
            symbol=symbol,
            strategy_name=parameters['strategy_name'],
            initial_cash=Decimal(str(parameters['initial_cash'])),
            pivot_bars=parameters['pivot_bars'],
            lower_timeframe=parameters['lower_timeframe'],
            start_date=datetime.fromisoformat(date_range['start']).date(),
            end_date=datetime.fromisoformat(date_range['end']).date(),
            total_return=Decimal(str(statistics.get('total_return', 0))),
            net_profit=Decimal(str(statistics['net_profit'])) if statistics.get('net_profit') is not None else None,
            net_profit_currency=Decimal(str(statistics['net_profit_currency'])) if statistics.get('net_profit_currency') is not None else None,
            compounding_annual_return=Decimal(str(statistics['compounding_annual_return'])) if statistics.get('compounding_annual_return') is not None else None,
            final_value=Decimal(str(statistics['final_value'])) if statistics.get('final_value') is not None else None,
            start_equity=Decimal(str(statistics['start_equity'])) if statistics.get('start_equity') is not None else None,
            end_equity=Decimal(str(statistics['end_equity'])) if statistics.get('end_equity') is not None else None,
            win_rate=Decimal(str(statistics.get('win_rate', 0))),
            loss_rate=Decimal(str(statistics['loss_rate'])) if statistics.get('loss_rate') is not None else None,
            total_trades=statistics.get('total_trades', 0),
            winning_trades=statistics.get('winning_trades', 0),
            losing_trades=statistics.get('losing_trades', 0),
            average_win=Decimal(str(statistics['average_win'])) if statistics.get('average_win') is not None else None,
            average_loss=Decimal(str(statistics['average_loss'])) if statistics.get('average_loss') is not None else None,
            sharpe_ratio=Decimal(str(statistics['sharpe_ratio'])) if statistics.get('sharpe_ratio') is not None else None,
            sortino_ratio=Decimal(str(statistics['sortino_ratio'])) if statistics.get('sortino_ratio') is not None else None,
            max_drawdown=Decimal(str(statistics['max_drawdown'])) if statistics.get('max_drawdown') is not None else None,
            probabilistic_sharpe_ratio=Decimal(str(statistics['probabilistic_sharpe_ratio'])) if statistics.get('probabilistic_sharpe_ratio') is not None else None,
            annual_standard_deviation=Decimal(str(statistics['annual_standard_deviation'])) if statistics.get('annual_standard_deviation') is not None else None,
            annual_variance=Decimal(str(statistics['annual_variance'])) if statistics.get('annual_variance') is not None else None,
            beta=Decimal(str(statistics['beta'])) if statistics.get('beta') is not None else None,
            alpha=Decimal(str(statistics['alpha'])) if statistics.get('alpha') is not None else None,
            profit_factor=Decimal(str(statistics['profit_factor'])) if statistics.get('profit_factor') is not None else None,
            profit_loss_ratio=Decimal(str(statistics['profit_loss_ratio'])) if statistics.get('profit_loss_ratio') is not None else None,
            expectancy=Decimal(str(statistics['expectancy'])) if statistics.get('expectancy') is not None else None,
            total_orders=statistics.get('total_orders'),
            information_ratio=Decimal(str(statistics['information_ratio'])) if statistics.get('information_ratio') is not None else None,
            tracking_error=Decimal(str(statistics['tracking_error'])) if statistics.get('tracking_error') is not None else None,
            treynor_ratio=Decimal(str(statistics['treynor_ratio'])) if statistics.get('treynor_ratio') is not None else None,
            total_fees=Decimal(str(statistics['total_fees'])) if statistics.get('total_fees') is not None else None,
            estimated_strategy_capacity=Decimal(str(statistics['estimated_strategy_capacity'])) if statistics.get('estimated_strategy_capacity') is not None else None,
            lowest_capacity_asset=statistics.get('lowest_capacity_asset'),
            portfolio_turnover=Decimal(str(statistics['portfolio_turnover'])) if statistics.get('portfolio_turnover') is not None else None,
            pivot_highs_detected=statistics.get('pivot_highs_detected'),
            pivot_lows_detected=statistics.get('pivot_lows_detected'),
            bos_signals_generated=statistics.get('bos_signals_generated'),
            position_flips=statistics.get('position_flips'),
            liquidation_events=statistics.get('liquidation_events'),
            execution_time_ms=statistics.get('execution_time_ms'),
            result_path=statistics.get('result_path'),
            cache_hit=statistics.get('cache_hit', False)
        )
        
        return await self.save_backtest_results(result)