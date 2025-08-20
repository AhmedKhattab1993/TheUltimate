#!/usr/bin/env python3
"""
Main pipeline script for running stock screening followed by backtesting.

This script:
1. Loads configuration from pipeline_config.yaml
2. Runs the screener with configured filters
3. Loops through screened symbols and runs backtests
4. Collects statistics from each backtest
5. Prints results and cleans up log folders
"""

import asyncio
import logging
import sys
import yaml
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent))

from app.services.backtest_queue_manager import BacktestQueueManager
from app.services.statistics_aggregator import StatisticsAggregator
from app.services.cleanup_service import CleanupService
from app.services.cache_service import CacheService
from app.models.cache_models import CachedScreenerRequest, CachedScreenerResult
from app.models.simple_requests import (
    SimpleScreenRequest, 
    SimplePriceRangeParams,
    PriceVsMAParams,
    RSIParams,
    GapParams,
    PreviousDayDollarVolumeParams,
    RelativeVolumeParams,
    SimpleFilters
)
from app.services.api_client import APIClient
from app.config import settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ScreenerBacktestPipeline:
    """Main pipeline orchestrator."""
    
    def __init__(self, config_path: str = "pipeline_config.yaml"):
        """Initialize pipeline with configuration."""
        self.config_path = Path(config_path)
        self.config = self._load_config()
        self.api_client = APIClient(base_url=settings.api_base_url)
        
        # Initialize cache service if enabled
        cache_config = self.config.get('caching', {})
        self.cache_enabled = cache_config.get('enabled', False)
        if self.cache_enabled:
            self.cache_service = CacheService(
                screener_ttl_hours=cache_config.get('screener_ttl_hours', 24),
                backtest_ttl_days=cache_config.get('backtest_ttl_days', 7)
            )
            logger.info("Cache service initialized")
        else:
            self.cache_service = None
        
        # Initialize queue manager with cache and storage settings
        storage_config = self.config.get('storage', {})
        self.queue_manager = BacktestQueueManager(
            max_parallel=self.config['execution']['parallel_backtests'],
            startup_delay=self.config['execution'].get('startup_delay', 15.0),
            cache_service=self.cache_service if self.cache_enabled else None,
            enable_storage=storage_config.get('enabled', True),
            enable_cleanup=storage_config.get('cleanup_after_storage', True)
        )
        self.stats_aggregator = StatisticsAggregator()
        self.cleanup_service = CleanupService()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _build_screener_request(self) -> SimpleScreenRequest:
        """Build screener request from configuration."""
        screening_config = self.config['screening']
        filters_config = screening_config['filters']
        
        # Build individual filters based on enabled flags
        filters = SimpleFilters()
        
        # Price Range Filter
        if 'price_range' in filters_config and filters_config['price_range'].get('enabled', False):
            pr = filters_config['price_range']
            filters.price_range = SimplePriceRangeParams(
                min_price=pr['min_price'],
                max_price=pr['max_price']
            )
        
        # Price vs MA Filter
        if 'price_vs_ma' in filters_config and filters_config['price_vs_ma'].get('enabled', False):
            pma = filters_config['price_vs_ma']
            filters.price_vs_ma = PriceVsMAParams(
                ma_period=pma['ma_period'],
                condition=pma['condition']
            )
        
        # RSI Filter
        if 'rsi' in filters_config and filters_config['rsi'].get('enabled', False):
            rsi = filters_config['rsi']
            filters.rsi = RSIParams(
                rsi_period=rsi.get('rsi_period', rsi.get('period', 14)),  # Support both field names
                condition=rsi['condition'],
                threshold=rsi['threshold']
            )
        
        # Gap Filter
        if 'gap' in filters_config and filters_config['gap'].get('enabled', False):
            gap = filters_config['gap']
            filters.gap = GapParams(
                gap_threshold=gap['gap_threshold'],
                direction=gap['direction']
            )
        
        # Previous Day Dollar Volume Filter
        if 'prev_day_dollar_volume' in filters_config and filters_config['prev_day_dollar_volume'].get('enabled', False):
            pddv = filters_config['prev_day_dollar_volume']
            filters.prev_day_dollar_volume = PreviousDayDollarVolumeParams(
                min_dollar_volume=pddv['min_dollar_volume']
            )
        
        # Relative Volume Filter
        if 'relative_volume' in filters_config and filters_config['relative_volume'].get('enabled', False):
            rv = filters_config['relative_volume']
            filters.relative_volume = RelativeVolumeParams(
                recent_days=rv['recent_days'],
                lookback_days=rv['lookback_days'],
                min_ratio=rv['min_ratio']
            )
        
        # Build request
        return SimpleScreenRequest(
            start_date=screening_config['date_range']['start'],
            end_date=screening_config['date_range']['end'],
            filters=filters,
            enable_db_prefiltering=True
        )
    
    async def run_screener(self) -> List[str]:
        """Run the stock screener and return list of symbols."""
        logger.info("Starting stock screening...")
        
        # Build screener request
        request = self._build_screener_request()
        
        # Check cache if enabled
        if self.cache_enabled:
            # Create cache request model based on enabled filters
            cache_request = CachedScreenerRequest(
                start_date=request.start_date,
                end_date=request.end_date,
                # Price filters
                min_price=request.filters.price_range.min_price if request.filters.price_range else None,
                max_price=request.filters.price_range.max_price if request.filters.price_range else None,
                # Price vs MA filter
                price_vs_ma_enabled=request.filters.price_vs_ma is not None,
                price_vs_ma_period=request.filters.price_vs_ma.ma_period if request.filters.price_vs_ma else None,
                price_vs_ma_condition=request.filters.price_vs_ma.condition if request.filters.price_vs_ma else None,
                # RSI filter
                rsi_enabled=request.filters.rsi is not None,
                rsi_period=request.filters.rsi.rsi_period if request.filters.rsi else None,
                rsi_threshold=request.filters.rsi.threshold if request.filters.rsi else None,
                rsi_condition=request.filters.rsi.condition if request.filters.rsi else None,
                # Gap filter
                gap_enabled=request.filters.gap is not None,
                gap_threshold=request.filters.gap.gap_threshold if request.filters.gap else None,
                gap_direction=request.filters.gap.direction if request.filters.gap else None,
                # Previous day dollar volume filter
                prev_day_dollar_volume_enabled=request.filters.prev_day_dollar_volume is not None,
                prev_day_dollar_volume=request.filters.prev_day_dollar_volume.min_dollar_volume if request.filters.prev_day_dollar_volume else None,
                # Relative volume filter
                relative_volume_enabled=request.filters.relative_volume is not None,
                relative_volume_recent_days=request.filters.relative_volume.recent_days if request.filters.relative_volume else None,
                relative_volume_lookback_days=request.filters.relative_volume.lookback_days if request.filters.relative_volume else None,
                relative_volume_min_ratio=request.filters.relative_volume.min_ratio if request.filters.relative_volume else None
            )
            
            # Check cache
            cached_results = await self.cache_service.get_screener_results(cache_request)
            if cached_results is not None:
                logger.info(f"Cache hit! Retrieved {len(cached_results)} symbols from cache")
                # Extract symbols from cached results
                return [result.symbol for result in cached_results]
        
        # Call screener API
        try:
            response = await self.api_client.screen_stocks(request)
            
            logger.info(f"Screening completed: {response.total_qualifying_stocks} stocks found")
            logger.info(f"Execution time: {response.execution_time_ms:.2f}ms")
            
            # Extract symbols
            symbols = [result.symbol for result in response.results]
            
            # Log some statistics
            if symbols:
                logger.info(f"Top qualifying symbols: {', '.join(symbols[:10])}")
            
            # Save to cache if enabled
            if self.cache_enabled and symbols:
                # Create cache models for each result
                cache_results = []
                for result in response.results:
                    cache_result = CachedScreenerResult(
                        symbol=result.symbol,
                        company_name=None,  # SimpleScreenResult doesn't have company_name
                        data_date=request.end_date,  # Use end date as the data date
                        # Copy filter parameters from request
                        # Price filters
                        filter_min_price=request.filters.price_range.min_price if request.filters.price_range else None,
                        filter_max_price=request.filters.price_range.max_price if request.filters.price_range else None,
                        # Price vs MA filter
                        filter_price_vs_ma_enabled=request.filters.price_vs_ma is not None,
                        filter_price_vs_ma_period=request.filters.price_vs_ma.ma_period if request.filters.price_vs_ma else None,
                        filter_price_vs_ma_condition=request.filters.price_vs_ma.condition if request.filters.price_vs_ma else None,
                        # RSI filter
                        filter_rsi_enabled=request.filters.rsi is not None,
                        filter_rsi_period=request.filters.rsi.rsi_period if request.filters.rsi else None,
                        filter_rsi_threshold=request.filters.rsi.threshold if request.filters.rsi else None,
                        filter_rsi_condition=request.filters.rsi.condition if request.filters.rsi else None,
                        # Gap filter
                        filter_gap_enabled=request.filters.gap is not None,
                        filter_gap_threshold=request.filters.gap.gap_threshold if request.filters.gap else None,
                        filter_gap_direction='any' if request.filters.gap and request.filters.gap.direction == 'both' else request.filters.gap.direction if request.filters.gap else None,
                        # Previous day dollar volume filter
                        filter_prev_day_dollar_volume_enabled=request.filters.prev_day_dollar_volume is not None,
                        filter_prev_day_dollar_volume=request.filters.prev_day_dollar_volume.min_dollar_volume if request.filters.prev_day_dollar_volume else None,
                        # Relative volume filter
                        filter_relative_volume_enabled=request.filters.relative_volume is not None,
                        filter_relative_volume_recent_days=request.filters.relative_volume.recent_days if request.filters.relative_volume else None,
                        filter_relative_volume_lookback_days=request.filters.relative_volume.lookback_days if request.filters.relative_volume else None,
                        filter_relative_volume_min_ratio=request.filters.relative_volume.min_ratio if request.filters.relative_volume else None
                    )
                    cache_results.append(cache_result)
                
                # Save all results with 'pipeline' as source
                success = await self.cache_service.save_screener_results(cache_request, cache_results, source='pipeline')
                if success:
                    logger.info(f"Saved {len(cache_results)} screener results to cache with source='pipeline'")
                else:
                    logger.warning("Failed to save screener results to cache")
            
            return symbols
            
        except Exception as e:
            logger.error(f"Screening failed: {e}")
            raise
    
    async def run_backtests(self, symbols: List[str], date_range: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Run backtests for all symbols and collect results.
        
        Args:
            symbols: List of symbols to backtest
            date_range: Optional date range override. If not provided, uses config.
        """
        logger.info(f"Starting backtests for {len(symbols)} symbols...")
        
        backtest_config = self.config['backtesting']
        execution_config = self.config['execution']
        
        # Check if max_backtests limit is set
        max_backtests = execution_config.get('max_backtests', 0)
        
        # Use provided date range or fall back to config (if it exists)
        if date_range is None:
            # Check if date_range exists in config (for backward compatibility)
            if 'date_range' in backtest_config:
                date_range = {
                    'start': backtest_config['date_range']['start'],
                    'end': backtest_config['date_range']['end']
                }
            else:
                # This should not happen in normal flow as we'll always pass date_range
                raise ValueError("No date range provided for backtests")
        
        # Track which backtests need to be run
        backtest_requests = []
        cached_results = {}
        
        for symbol in symbols:
            # Check cache if enabled
            if self.cache_enabled:
                from app.models.cache_models import CachedBacktestRequest
                
                # Extract parameters from backtest configuration
                parameters = backtest_config.get('parameters', {})
                
                # Create cache request model using new cache key parameters
                cache_request = CachedBacktestRequest(
                    symbol=symbol,
                    strategy_name=backtest_config.get('strategy', 'MarketStructure'),
                    start_date=datetime.strptime(date_range['start'], '%Y-%m-%d').date(),
                    end_date=datetime.strptime(date_range['end'], '%Y-%m-%d').date(),
                    initial_cash=backtest_config.get('initial_cash', 100000),
                    pivot_bars=parameters.get('pivot_bars', 20),
                    lower_timeframe=parameters.get('lower_timeframe', '5min'),
                    # Legacy parameters for backward compatibility
                    holding_period=parameters.get('holding_period', 10),
                    gap_threshold=parameters.get('gap_threshold', 2.0),
                    stop_loss=parameters.get('stop_loss'),
                    take_profit=parameters.get('take_profit')
                )
                
                cached_result = await self.cache_service.get_backtest_results(cache_request)
                if cached_result is not None:
                    logger.info(f"Cache hit for backtest: {symbol}")
                    # Convert cached result to expected format with comprehensive metrics
                    cached_results[symbol] = {
                        'statistics': {
                            # Core performance metrics
                            'total_return': float(cached_result.total_return),
                            'net_profit': float(cached_result.net_profit) if cached_result.net_profit else 0.0,
                            'net_profit_currency': float(cached_result.net_profit_currency) if cached_result.net_profit_currency else 0.0,
                            'compounding_annual_return': float(cached_result.compounding_annual_return) if cached_result.compounding_annual_return else 0.0,
                            'final_value': float(cached_result.final_value) if cached_result.final_value else 0.0,
                            'start_equity': float(cached_result.start_equity) if cached_result.start_equity else 0.0,
                            'end_equity': float(cached_result.end_equity) if cached_result.end_equity else 0.0,
                            
                            # Enhanced risk metrics
                            'sharpe_ratio': float(cached_result.sharpe_ratio) if cached_result.sharpe_ratio else 0.0,
                            'sortino_ratio': float(cached_result.sortino_ratio) if cached_result.sortino_ratio else 0.0,
                            'max_drawdown': float(cached_result.max_drawdown) if cached_result.max_drawdown else 0.0,
                            'probabilistic_sharpe_ratio': float(cached_result.probabilistic_sharpe_ratio) if cached_result.probabilistic_sharpe_ratio else 0.0,
                            'annual_standard_deviation': float(cached_result.annual_standard_deviation) if cached_result.annual_standard_deviation else 0.0,
                            'annual_variance': float(cached_result.annual_variance) if cached_result.annual_variance else 0.0,
                            'beta': float(cached_result.beta) if cached_result.beta else 0.0,
                            'alpha': float(cached_result.alpha) if cached_result.alpha else 0.0,
                            
                            # Advanced trading statistics
                            'total_trades': cached_result.total_trades,
                            'winning_trades': cached_result.winning_trades,
                            'losing_trades': cached_result.losing_trades,
                            'win_rate': float(cached_result.win_rate),
                            'loss_rate': float(cached_result.loss_rate) if cached_result.loss_rate else 0.0,
                            'average_win': float(cached_result.average_win) if cached_result.average_win else 0.0,
                            'average_loss': float(cached_result.average_loss) if cached_result.average_loss else 0.0,
                            'profit_factor': float(cached_result.profit_factor) if cached_result.profit_factor else 0.0,
                            'profit_loss_ratio': float(cached_result.profit_loss_ratio) if cached_result.profit_loss_ratio else 0.0,
                            'expectancy': float(cached_result.expectancy) if cached_result.expectancy else 0.0,
                            'total_orders': cached_result.total_orders if cached_result.total_orders else 0,
                            
                            # Advanced metrics
                            'information_ratio': float(cached_result.information_ratio) if cached_result.information_ratio else 0.0,
                            'tracking_error': float(cached_result.tracking_error) if cached_result.tracking_error else 0.0,
                            'treynor_ratio': float(cached_result.treynor_ratio) if cached_result.treynor_ratio else 0.0,
                            'total_fees': float(cached_result.total_fees) if cached_result.total_fees else 0.0,
                            'estimated_strategy_capacity': float(cached_result.estimated_strategy_capacity) if cached_result.estimated_strategy_capacity else 0.0,
                            'lowest_capacity_asset': cached_result.lowest_capacity_asset or "",
                            'portfolio_turnover': float(cached_result.portfolio_turnover) if cached_result.portfolio_turnover else 0.0,
                            
                            # Strategy-specific metrics
                            'pivot_highs_detected': cached_result.pivot_highs_detected if cached_result.pivot_highs_detected else 0,
                            'pivot_lows_detected': cached_result.pivot_lows_detected if cached_result.pivot_lows_detected else 0,
                            'bos_signals_generated': cached_result.bos_signals_generated if cached_result.bos_signals_generated else 0,
                            'position_flips': cached_result.position_flips if cached_result.position_flips else 0,
                            'liquidation_events': cached_result.liquidation_events if cached_result.liquidation_events else 0,
                            
                            # Algorithm parameters
                            'initial_cash': float(cached_result.initial_cash),
                            'pivot_bars': cached_result.pivot_bars,
                            'lower_timeframe': cached_result.lower_timeframe,
                            'strategy_name': cached_result.strategy_name
                        },
                        'from_cache': True,
                        'cache_hit': True
                    }
                    continue
            
            # Add to requests if not cached
            request = {
                'symbol': symbol,
                'strategy': backtest_config['strategy'],
                'start_date': date_range['start'],
                'end_date': date_range['end'],
                'initial_cash': backtest_config['initial_cash'],
                'resolution': backtest_config.get('resolution', 'Daily'),
                'parameters': backtest_config['parameters']
            }
            backtest_requests.append(request)
        
        # Apply max_backtests limit if set
        if max_backtests > 0 and len(backtest_requests) > max_backtests:
            logger.info(f"Limiting backtest executions to {max_backtests} (from {len(backtest_requests)} total)")
            backtest_requests = backtest_requests[:max_backtests]
        
        # Log cache statistics
        if cached_results:
            logger.info(f"Retrieved {len(cached_results)} backtests from cache")
            logger.info(f"Running {len(backtest_requests)} new backtests")
        
        # Run non-cached backtests through queue manager
        if backtest_requests:
            new_results = await self.queue_manager.run_batch(
                backtest_requests,
                timeout_per_backtest=execution_config['timeout_per_backtest'],
                retry_attempts=execution_config['retry_attempts'],
                continue_on_error=execution_config['continue_on_error']
            )
            
            # Note: Cache saving is now handled within BacktestQueueManager after each backtest completes
        else:
            new_results = {}
        
        # Combine cached and new results
        all_results = {**cached_results, **new_results}
        
        return all_results
    
    async def process_results(self, backtest_results: Dict[str, Any]):
        """Process and output backtest results."""
        logger.info("Processing backtest results...")
        
        # Aggregate statistics
        aggregated_stats = self.stats_aggregator.aggregate_results(backtest_results)
        
        # Output results based on configuration
        output_config = self.config['output']
        output_dir = Path(output_config['directory'])
        output_dir.mkdir(exist_ok=True)
        
        # Generate timestamp for filenames
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save in requested formats
        if 'json' in output_config['formats']:
            json_path = output_dir / f"pipeline_results_{timestamp}.json"
            self.stats_aggregator.save_json(aggregated_stats, json_path)
            logger.info(f"Saved JSON results to {json_path}")
        
        if 'csv' in output_config['formats']:
            csv_path = output_dir / f"pipeline_results_{timestamp}.csv"
            self.stats_aggregator.save_csv(aggregated_stats, csv_path)
            logger.info(f"Saved CSV results to {csv_path}")
        
        if 'html' in output_config['formats']:
            html_path = output_dir / f"pipeline_results_{timestamp}.html"
            self.stats_aggregator.save_html(aggregated_stats, html_path)
            logger.info(f"Saved HTML results to {html_path}")
        
        # Print to console if requested
        if output_config['print_to_console']:
            self.stats_aggregator.print_summary(aggregated_stats)
    
    async def cleanup(self):
        """Clean up resources like API client session."""
        # Close API client session
        if self.api_client and self.api_client.session:
            await self.api_client.session.close()
            logger.debug("Closed API client session")
    
    async def cleanup_logs(self, backtest_results: Dict[str, Any]):
        """Clean up backtest logs and temporary files."""
        output_config = self.config['output']
        
        if not output_config['cleanup_logs']:
            logger.info("Log cleanup disabled in configuration")
            return
        
        logger.info("Cleaning up backtest logs...")
        
        # Extract result paths from backtest results
        result_paths = []
        for symbol, result in backtest_results.items():
            if isinstance(result, dict) and 'result_path' in result:
                result_paths.append(result['result_path'])
        
        # Perform cleanup
        await self.cleanup_service.cleanup_backtest_logs(
            result_paths,
            archive=output_config['archive_before_cleanup'],
            archive_format=output_config.get('archive_format', 'tar.gz')
        )
    
    def _get_trading_days(self, start_date: str, end_date: str) -> List[date]:
        """
        Get all trading days between start and end dates (backward order).
        Excludes weekends (Saturday=5, Sunday=6).
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            
        Returns:
            List of dates in backward order (end to start)
        """
        start = datetime.strptime(start_date, '%Y-%m-%d').date()
        end = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        trading_days = []
        current = end
        
        while current >= start:
            # Check if it's a weekday (Monday=0 to Friday=4)
            if current.weekday() < 5:
                trading_days.append(current)
            current = current - timedelta(days=1)
        
        return trading_days
    
    async def run_single_day_pipeline(self, trading_date: date) -> Dict[str, Any]:
        """
        Run the pipeline for a single trading day.
        
        Args:
            trading_date: The date to process
            
        Returns:
            Dict containing symbols found and backtest results for this day
        """
        date_str = trading_date.strftime('%Y-%m-%d')
        logger.info(f"\n{'='*60}")
        logger.info(f"Processing date: {date_str}")
        logger.info(f"{'='*60}")
        
        # Update screening config for this specific date
        original_start = self.config['screening']['date_range']['start']
        original_end = self.config['screening']['date_range']['end']
        
        # Temporarily set both start and end to the same date
        self.config['screening']['date_range']['start'] = date_str
        self.config['screening']['date_range']['end'] = date_str
        
        try:
            # Step 1: Run screener for this day
            logger.info(f"[{date_str}] Running screener...")
            symbols = await self.run_screener()
            
            if not symbols:
                logger.info(f"[{date_str}] No symbols found for this day.")
                return {'date': date_str, 'symbols': [], 'backtest_results': {}}
            
            logger.info(f"[{date_str}] Found {len(symbols)} symbols: {', '.join(symbols[:10])}{'...' if len(symbols) > 10 else ''}")
            
            # Step 2: Run backtests for symbols found on this day
            # Use the same date for both start and end of backtest
            logger.info(f"[{date_str}] Running backtests for {len(symbols)} symbols with date range: {date_str} to {date_str}")
            backtest_date_range = {
                'start': date_str,
                'end': date_str
            }
            backtest_results = await self.run_backtests(symbols, backtest_date_range)
            
            return {
                'date': date_str,
                'symbols': symbols,
                'backtest_results': backtest_results
            }
            
        finally:
            # Restore original date range
            self.config['screening']['date_range']['start'] = original_start
            self.config['screening']['date_range']['end'] = original_end
    
    async def run(self):
        """Run the complete pipeline for each trading day."""
        try:
            # Print pipeline configuration
            logger.info("=" * 80)
            logger.info("SCREENER-BACKTEST PIPELINE (DAY-BY-DAY MODE)")
            logger.info("=" * 80)
            logger.info(f"Configuration loaded from: {self.config_path}")
            start_date = self.config['screening']['date_range']['start']
            end_date = self.config['screening']['date_range']['end']
            logger.info(f"Screening period: {start_date} to {end_date}")
            logger.info(f"Backtest strategy: {self.config['backtesting']['strategy']}")
            logger.info(f"Parallel backtests: {self.config['execution']['parallel_backtests']}")
            max_backtests = self.config['execution'].get('max_backtests', 0)
            if max_backtests > 0:
                logger.info(f"Max backtest executions: {max_backtests}")
            logger.info(f"Cache enabled: {self.cache_enabled}")
            logger.info("=" * 80)
            
            # Clean expired cache if configured
            if self.cache_enabled and self.config.get('caching', {}).get('cleanup_on_startup', True):
                logger.info("Cleaning expired cache entries...")
                screener_cleaned, backtest_cleaned = await self.cache_service.clean_expired_cache()
                logger.info(f"Cleaned {screener_cleaned} screener and {backtest_cleaned} backtest cache entries")
            
            # Get all trading days to process (in backward order)
            trading_days = self._get_trading_days(start_date, end_date)
            logger.info(f"\nFound {len(trading_days)} trading days to process")
            
            # Collect all results
            all_daily_results = []
            all_symbols = set()
            all_backtest_results = {}
            
            # Process each trading day
            for i, trading_date in enumerate(trading_days, 1):
                logger.info(f"\n[DAY {i}/{len(trading_days)}] Processing {trading_date.strftime('%Y-%m-%d')}...")
                
                daily_result = await self.run_single_day_pipeline(trading_date)
                all_daily_results.append(daily_result)
                
                # Aggregate results
                all_symbols.update(daily_result['symbols'])
                all_backtest_results.update(daily_result['backtest_results'])
            
            # Summary
            logger.info("\n" + "=" * 80)
            logger.info("DAILY PROCESSING SUMMARY")
            logger.info("=" * 80)
            logger.info(f"Total trading days processed: {len(trading_days)}")
            logger.info(f"Total unique symbols found: {len(all_symbols)}")
            logger.info(f"Total backtests run: {len(all_backtest_results)}")
            
            # Process aggregate results
            if all_backtest_results:
                logger.info("\n[FINAL] Processing and saving aggregate results...")
                await self.process_results(all_backtest_results)
                
                # Cleanup
                logger.info("\n[FINAL] Cleaning up...")
                await self.cleanup_logs(all_backtest_results)
            
            # Show cache statistics if enabled
            if self.cache_enabled and self.config.get('caching', {}).get('show_stats_on_completion', True):
                logger.info("\n" + "=" * 80)
                logger.info("CACHE STATISTICS")
                logger.info("=" * 80)
                cache_stats = await self.cache_service.get_cache_stats()
                
                screener_stats = cache_stats['screener']
                logger.info(f"Screener Cache:")
                logger.info(f"  Active entries: {screener_stats.get('active_entries', 0)}")
                logger.info(f"  Total hits: {screener_stats.get('total_hits', 0)}")
                logger.info(f"  Total misses: {screener_stats.get('total_misses', 0)}")
                logger.info(f"  Hit rate: {screener_stats.get('hit_rate', 0):.1f}%")
                
                backtest_stats = cache_stats['backtest']
                logger.info(f"\nBacktest Cache:")
                logger.info(f"  Active entries: {backtest_stats.get('active_entries', 0)}")
                logger.info(f"  Total hits: {backtest_stats.get('total_hits', 0)}")
                logger.info(f"  Total misses: {backtest_stats.get('total_misses', 0)}")
                logger.info(f"  Hit rate: {backtest_stats.get('hit_rate', 0):.1f}%")
            
            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        finally:
            # Clean up resources
            await self.cleanup()


async def main():
    """Main entry point."""
    # Check if custom config path provided
    config_path = sys.argv[1] if len(sys.argv) > 1 else "pipeline_config.yaml"
    
    # Create and run pipeline
    pipeline = ScreenerBacktestPipeline(config_path)
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())