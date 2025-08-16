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
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent))

from app.services.backtest_queue_manager import BacktestQueueManager
from app.services.statistics_aggregator import StatisticsAggregator
from app.services.cleanup_service import CleanupService
from app.models.simple_requests import (
    SimpleScreenRequest, 
    SimplePriceRangeParams,
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
        self.queue_manager = BacktestQueueManager(
            max_parallel=self.config['execution']['parallel_backtests'],
            startup_delay=self.config['execution'].get('startup_delay', 15.0)
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
        
        # Build individual filters
        filters = SimpleFilters()
        
        if 'price_range' in filters_config:
            pr = filters_config['price_range']
            filters.price_range = SimplePriceRangeParams(
                min_price=pr['min_price'],
                max_price=pr['max_price']
            )
        
        if 'gap' in filters_config:
            gap = filters_config['gap']
            filters.gap = GapParams(
                gap_threshold=gap['gap_threshold'],
                direction=gap['direction']
            )
        
        if 'prev_day_dollar_volume' in filters_config:
            pddv = filters_config['prev_day_dollar_volume']
            filters.prev_day_dollar_volume = PreviousDayDollarVolumeParams(
                min_dollar_volume=pddv['min_dollar_volume']
            )
        
        if 'relative_volume' in filters_config:
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
            
            return symbols
            
        except Exception as e:
            logger.error(f"Screening failed: {e}")
            raise
    
    async def run_backtests(self, symbols: List[str]) -> Dict[str, Any]:
        """Run backtests for all symbols and collect results."""
        logger.info(f"Starting backtests for {len(symbols)} symbols...")
        
        backtest_config = self.config['backtesting']
        execution_config = self.config['execution']
        
        # Create backtest requests for each symbol
        backtest_requests = []
        for symbol in symbols:
            request = {
                'symbol': symbol,
                'strategy': backtest_config['strategy'],
                'start_date': backtest_config['date_range']['start'],
                'end_date': backtest_config['date_range']['end'],
                'initial_cash': backtest_config['initial_cash'],
                'resolution': backtest_config.get('resolution', 'Daily'),
                'parameters': backtest_config['parameters']
            }
            backtest_requests.append(request)
        
        # Run backtests through queue manager
        results = await self.queue_manager.run_batch(
            backtest_requests,
            timeout_per_backtest=execution_config['timeout_per_backtest'],
            retry_attempts=execution_config['retry_attempts'],
            continue_on_error=execution_config['continue_on_error']
        )
        
        return results
    
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
    
    async def cleanup(self, backtest_results: Dict[str, Any]):
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
    
    async def run(self):
        """Run the complete pipeline."""
        try:
            # Print pipeline configuration
            logger.info("=" * 80)
            logger.info("SCREENER-BACKTEST PIPELINE")
            logger.info("=" * 80)
            logger.info(f"Configuration loaded from: {self.config_path}")
            logger.info(f"Screening period: {self.config['screening']['date_range']['start']} to {self.config['screening']['date_range']['end']}")
            logger.info(f"Backtest strategy: {self.config['backtesting']['strategy']}")
            logger.info(f"Parallel backtests: {self.config['execution']['parallel_backtests']}")
            logger.info("=" * 80)
            
            # Step 1: Run screener
            logger.info("\n[STEP 1/4] Running stock screener...")
            symbols = await self.run_screener()
            
            if not symbols:
                logger.warning("No symbols found by screener. Exiting.")
                return
            
            # Step 2: Run backtests
            logger.info(f"\n[STEP 2/4] Running backtests for {len(symbols)} symbols...")
            backtest_results = await self.run_backtests(symbols)
            
            # Step 3: Process results
            logger.info("\n[STEP 3/4] Processing and saving results...")
            await self.process_results(backtest_results)
            
            # Step 4: Cleanup
            logger.info("\n[STEP 4/4] Cleaning up...")
            await self.cleanup(backtest_results)
            
            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise


async def main():
    """Main entry point."""
    # Check if custom config path provided
    config_path = sys.argv[1] if len(sys.argv) > 1 else "pipeline_config.yaml"
    
    # Create and run pipeline
    pipeline = ScreenerBacktestPipeline(config_path)
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())