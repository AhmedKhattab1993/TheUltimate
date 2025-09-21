"""
Cache service for storing and retrieving screener and backtest results.

This service provides methods to check cache, store results, and manage cache lifecycle.
"""

import logging
from datetime import datetime, timedelta, date
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
from app.services.screener_repository import (
    ScreenerRunDetail,
    ScreenerResultEntry,
    screener_repository,
)

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
        hash_value = request.calculate_hash()

        try:
            row = await db_pool.fetchrow(
                """
                SELECT id, created_at
                FROM screener_runs
                WHERE metadata->>'cache_hash' = $1
                ORDER BY created_at DESC
                LIMIT 1
                """,
                hash_value,
            )
        except Exception as exc:
            logger.error("Error looking up screener cache entry: %s", exc)
            return None

        if not row:
            await self._update_cache_stats('screener', hit=False)
            logger.info(f"Cache miss for screener with hash {hash_value}")
            return None

        created_at: datetime = row['created_at']
        if created_at < datetime.utcnow() - timedelta(hours=self.screener_ttl_hours):
            await self._update_cache_stats('screener', hit=False)
            logger.info(f"Cache entry expired for screener hash {hash_value}")
            return None

        run_detail = await screener_repository.get_run(row['id'])
        if not run_detail:
            await self._update_cache_stats('screener', hit=False)
            logger.info(f"Cache lookup missing run detail for hash {hash_value}")
            return None

        await self._update_cache_stats('screener', hit=True)
        logger.info(f"Cache hit for screener with hash {hash_value}")

        results: List[CachedScreenerResult] = [
            self._build_cached_screener_result(run_detail, entry)
            for entry in run_detail.results
        ]
        return results or None
    
    async def save_screener_results(
        self, 
        request: CachedScreenerRequest,
        results: List[CachedScreenerResult],
        source: str = 'ui'
    ) -> bool:
        """
        Save screener results to cache.
        
        Args:
            request: Screener request parameters
            results: List of screener results to save
            source: Source of the screener run ('ui' or 'pipeline')
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not results:
            logger.warning("No results to save to cache")
            return False

        session_id = request.session_id or uuid4()
        cache_hash = request.calculate_hash()
        filters_payload = self._filters_from_request(request)
        metadata = {
            "cache_hash": cache_hash,
            "source": source,
            "start_date": request.start_date.isoformat(),
            "end_date": request.end_date.isoformat(),
            "screener_ttl_hours": self.screener_ttl_hours,
        }

        try:
            summary = await screener_repository.create_run(
                filters=filters_payload,
                metadata=metadata,
                symbol_count=len(results),
                session_id=session_id,
            )

            await screener_repository.save_results(
                summary.id,
                [
                    {
                        "id": result.id,
                        "symbol": result.symbol,
                        "metrics": self._metrics_from_result(result, source),
                        "rank": None,
                    }
                    for result in results
                ],
            )

            logger.info(
                "Saved %d screener results to cache run %s (session %s)",
                len(results),
                summary.id,
                session_id,
            )
            return True
        except Exception as exc:
            logger.error("Error saving screener results to cache: %s", exc)
            return False

    # ------------------------------------------------------------------
    # Screener helper utilities
    # ------------------------------------------------------------------
    def _filters_from_request(self, request: CachedScreenerRequest) -> Dict[str, Any]:
        return {
            "date_range": {
                "start": request.start_date.isoformat(),
                "end": request.end_date.isoformat(),
            },
            "min_price": self._convert_decimal_to_float(request.min_price),
            "max_price": self._convert_decimal_to_float(request.max_price),
            "price_vs_ma": {
                "enabled": request.price_vs_ma_enabled,
                "period": request.price_vs_ma_period,
                "min_ratio": self._convert_decimal_to_float(request.price_vs_ma_min_ratio),
                "max_ratio": self._convert_decimal_to_float(request.price_vs_ma_max_ratio),
            },
            "rsi": {
                "enabled": request.rsi_enabled,
                "period": request.rsi_period,
                "min_value": self._convert_decimal_to_float(request.rsi_min_value),
                "max_value": self._convert_decimal_to_float(request.rsi_max_value),
            },
            "gap": {
                "enabled": request.gap_enabled,
                "min_percent": self._convert_decimal_to_float(request.gap_min_percent),
                "max_percent": self._convert_decimal_to_float(request.gap_max_percent),
                "direction": request.gap_direction,
            },
            "prev_day_dollar_volume": {
                "enabled": request.prev_day_dollar_volume_enabled,
                "min_value": self._convert_decimal_to_float(request.prev_day_min_dollar_volume),
                "max_value": self._convert_decimal_to_float(request.prev_day_max_dollar_volume),
            },
            "relative_volume": {
                "enabled": request.relative_volume_enabled,
                "recent_days": request.relative_volume_recent_days,
                "lookback_days": request.relative_volume_lookback_days,
                "min_ratio": self._convert_decimal_to_float(request.relative_volume_min_ratio),
                "max_ratio": self._convert_decimal_to_float(request.relative_volume_max_ratio),
            },
        }

    @staticmethod
    def _metrics_from_result(result: CachedScreenerResult, source: str) -> Dict[str, Any]:
        return {
            "company_name": result.company_name,
            "screened_at": result.screened_at.isoformat(),
            "data_date": result.data_date.isoformat(),
            "source": source,
        }

    def _build_cached_screener_result(
        self,
        run: ScreenerRunDetail,
        entry: ScreenerResultEntry,
    ) -> CachedScreenerResult:
        filters = run.filters or {}
        price_vs_ma = filters.get("price_vs_ma", {})
        rsi = filters.get("rsi", {})
        gap = filters.get("gap", {})
        prev_day = filters.get("prev_day_dollar_volume", {})
        rel_vol = filters.get("relative_volume", {})
        metrics = entry.metrics or {}

        screened_at = self._parse_datetime(metrics.get("screened_at")) or run.created_at
        data_date = self._parse_date(metrics.get("data_date")) or screened_at.date()

        return CachedScreenerResult(
            id=entry.id,
            symbol=entry.symbol,
            company_name=metrics.get("company_name"),
            screened_at=screened_at,
            data_date=data_date,
            filter_min_price=self._convert_float_to_decimal(filters.get("min_price")),
            filter_max_price=self._convert_float_to_decimal(filters.get("max_price")),
            filter_price_vs_ma_enabled=bool(price_vs_ma.get("enabled")),
            filter_price_vs_ma_period=price_vs_ma.get("period"),
            filter_price_vs_ma_min_ratio=self._convert_float_to_decimal(price_vs_ma.get("min_ratio")),
            filter_price_vs_ma_max_ratio=self._convert_float_to_decimal(price_vs_ma.get("max_ratio")),
            filter_rsi_enabled=bool(rsi.get("enabled")),
            filter_rsi_period=rsi.get("period"),
            filter_rsi_min_value=self._convert_float_to_decimal(rsi.get("min_value")),
            filter_rsi_max_value=self._convert_float_to_decimal(rsi.get("max_value")),
            filter_gap_enabled=bool(gap.get("enabled")),
            filter_gap_min_percent=self._convert_float_to_decimal(gap.get("min_percent")),
            filter_gap_max_percent=self._convert_float_to_decimal(gap.get("max_percent")),
            filter_gap_direction=gap.get("direction"),
            filter_prev_day_dollar_volume_enabled=bool(prev_day.get("enabled")),
            filter_prev_day_min_dollar_volume=self._convert_float_to_decimal(prev_day.get("min_value")),
            filter_prev_day_max_dollar_volume=self._convert_float_to_decimal(prev_day.get("max_value")),
            filter_relative_volume_enabled=bool(rel_vol.get("enabled")),
            filter_relative_volume_recent_days=rel_vol.get("recent_days"),
            filter_relative_volume_lookback_days=rel_vol.get("lookback_days"),
            filter_relative_volume_min_ratio=self._convert_float_to_decimal(rel_vol.get("min_ratio")),
            filter_relative_volume_max_ratio=self._convert_float_to_decimal(rel_vol.get("max_ratio")),
            session_id=run.session_id,
            created_at=entry.created_at,
        )

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _parse_date(value: Optional[str]) -> Optional[date]:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    
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
        """Clean expired cache entries and return deleted screener/backtest counts."""

        try:
            screener_deleted = await db_pool.fetch(
                """
                DELETE FROM screener_runs
                WHERE created_at <= NOW() - make_interval(hours => $1::int)
                RETURNING id
                """,
                int(self.screener_ttl_hours),
            )

            await db_pool.execute(
                """
                UPDATE cache_metadata
                SET last_cleanup = NOW(), updated_at = NOW()
                WHERE cache_type = 'screener'
                """
            )

            logger.info(
                "Cleaned %d screener cache entries; backtest cleanup pending new storage",
                len(screener_deleted),
            )
            return len(screener_deleted), 0
        except Exception as exc:
            logger.error(f"Error cleaning expired cache: {exc}")
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
                SELECT COUNT(*) AS count
                FROM screener_runs
                WHERE created_at > NOW() - make_interval(hours => $1::int)
            """
            screener_count = await db_pool.fetchval(screener_count_query, int(self.screener_ttl_hours))

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
                    'active_entries': 0,
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
        price_vs_ma_enabled = bool(filters.get('above_sma20'))
        price_vs_ma_min_ratio = Decimal('1') if price_vs_ma_enabled else None

        rsi_threshold = filters.get('rsi_threshold')
        rsi_condition = filters.get('rsi_condition')
        rsi_min_value = rsi_max_value = None
        if rsi_threshold is not None:
            threshold_decimal = Decimal(str(rsi_threshold))
            if rsi_condition == 'above':
                rsi_min_value = threshold_decimal
            else:
                rsi_max_value = threshold_decimal

        gap_value = filters.get('min_gap') or filters.get('gap_threshold')
        gap_direction = filters.get('gap_direction', 'up') if gap_value is not None else None

        prev_day_volume = filters.get('prev_day_dollar_volume')
        if prev_day_volume is None and filters.get('min_volume'):
            prev_day_volume = Decimal(str(filters['min_volume'])) * 100  # legacy approximation

        relative_min_ratio = filters.get('relative_volume_min_ratio')

        request = CachedScreenerRequest(
            start_date=datetime.fromisoformat(date_range['start']).date(),
            end_date=datetime.fromisoformat(date_range['end']).date(),
            min_price=filters.get('min_price'),
            max_price=filters.get('max_price'),
            # Map old filters to new schema
            price_vs_ma_enabled=price_vs_ma_enabled,
            price_vs_ma_period=20 if price_vs_ma_enabled else None,
            price_vs_ma_min_ratio=price_vs_ma_min_ratio,
            price_vs_ma_max_ratio=None,
            rsi_enabled=filters.get('rsi_enabled', False),
            rsi_period=filters.get('rsi_period'),
            rsi_min_value=rsi_min_value,
            rsi_max_value=rsi_max_value,
            gap_enabled=gap_value is not None or filters.get('gap_enabled', False),
            gap_min_percent=gap_value,
            gap_max_percent=None,
            gap_direction=gap_direction,
            prev_day_dollar_volume_enabled=prev_day_volume is not None,
            prev_day_min_dollar_volume=prev_day_volume,
            prev_day_max_dollar_volume=None,
            relative_volume_enabled=filters.get('relative_volume_enabled', False),
            relative_volume_recent_days=filters.get('relative_volume_recent_days'),
            relative_volume_lookback_days=filters.get('relative_volume_lookback_days'),
            relative_volume_min_ratio=relative_min_ratio,
            relative_volume_max_ratio=None,
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
        price_vs_ma_enabled = bool(filters.get('above_sma20'))
        price_vs_ma_min_ratio = Decimal('1') if price_vs_ma_enabled else None

        rsi_threshold = filters.get('rsi_threshold')
        rsi_condition = filters.get('rsi_condition')
        rsi_min_value = rsi_max_value = None
        if rsi_threshold is not None:
            threshold_decimal = Decimal(str(rsi_threshold))
            if rsi_condition == 'above':
                rsi_min_value = threshold_decimal
            else:
                rsi_max_value = threshold_decimal

        gap_value = filters.get('min_gap') or filters.get('gap_threshold')
        gap_direction = filters.get('gap_direction', 'up') if gap_value is not None else None

        prev_day_volume = filters.get('prev_day_dollar_volume')
        if prev_day_volume is None and filters.get('min_volume'):
            prev_day_volume = Decimal(str(filters['min_volume'])) * 100

        relative_min_ratio = filters.get('relative_volume_min_ratio')

        request = CachedScreenerRequest(
            start_date=datetime.fromisoformat(date_range['start']).date(),
            end_date=datetime.fromisoformat(date_range['end']).date(),
            min_price=filters.get('min_price'),
            max_price=filters.get('max_price'),
            # Map old filters to new schema
            price_vs_ma_enabled=price_vs_ma_enabled,
            price_vs_ma_period=20 if price_vs_ma_enabled else None,
            price_vs_ma_min_ratio=price_vs_ma_min_ratio,
            price_vs_ma_max_ratio=None,
            rsi_enabled=filters.get('rsi_enabled', False),
            rsi_period=filters.get('rsi_period'),
            rsi_min_value=rsi_min_value,
            rsi_max_value=rsi_max_value,
            gap_enabled=gap_value is not None or filters.get('gap_enabled', False),
            gap_min_percent=gap_value,
            gap_max_percent=None,
            gap_direction=gap_direction,
            prev_day_dollar_volume_enabled=prev_day_volume is not None,
            prev_day_min_dollar_volume=prev_day_volume,
            prev_day_max_dollar_volume=None,
            relative_volume_enabled=filters.get('relative_volume_enabled', False),
            relative_volume_recent_days=filters.get('relative_volume_recent_days'),
            relative_volume_lookback_days=filters.get('relative_volume_lookback_days'),
            relative_volume_min_ratio=relative_min_ratio,
            relative_volume_max_ratio=None,
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
