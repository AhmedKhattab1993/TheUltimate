#!/usr/bin/env python3
"""
Optimized pipeline runner with better error handling and progress tracking.
"""

import asyncio
import logging
import sys
import yaml
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add backend to path for imports
sys.path.append(str(Path(__file__).parent))

from app.services.backtest_queue_manager import BacktestQueueManager
from app.services.statistics_aggregator import StatisticsAggregator
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

# Configure logging with better format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)

# Suppress noisy WebSocket warnings
logging.getLogger('app.services.backtest_manager').setLevel(logging.ERROR)


class OptimizedPipeline:
    """Optimized pipeline with progress tracking and error handling."""
    
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
        self.start_time = time.time()
        
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def _log_progress(self, step: int, total_steps: int, message: str):
        """Log progress with timing information."""
        elapsed = time.time() - self.start_time
        progress = (step / total_steps) * 100
        logger.info(f"[{progress:3.0f}%] {message} (elapsed: {elapsed:.1f}s)")
    
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
        self._log_progress(1, 4, "Running stock screener...")
        
        request = self._build_screener_request()
        
        try:
            start = time.time()
            response = await self.api_client.screen_stocks(request)
            screen_time = time.time() - start
            
            symbols = [result.symbol for result in response.results]
            
            logger.info(f"    ✓ Found {len(symbols)} qualifying stocks in {screen_time:.1f}s")
            if symbols:
                logger.info(f"    ✓ Sample symbols: {', '.join(symbols[:5])}")
            
            return symbols
            
        except Exception as e:
            logger.error(f"    ✗ Screening failed: {e}")
            raise
    
    async def run_backtests(self, symbols: List[str]) -> Dict[str, Any]:
        """Run backtests with progress tracking."""
        self._log_progress(2, 4, f"Running backtests for {len(symbols)} symbols...")
        
        backtest_config = self.config['backtesting']
        execution_config = self.config['execution']
        
        # Create backtest requests
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
        
        # Run backtests
        start = time.time()
        results = await self.queue_manager.run_batch(
            backtest_requests,
            timeout_per_backtest=execution_config['timeout_per_backtest'],
            retry_attempts=execution_config['retry_attempts'],
            continue_on_error=execution_config['continue_on_error']
        )
        
        backtest_time = time.time() - start
        successful = sum(1 for r in results.values() if r.get('status') == 'completed')
        
        logger.info(f"    ✓ Completed {successful}/{len(symbols)} backtests in {backtest_time:.1f}s")
        logger.info(f"    ✓ Average time per backtest: {backtest_time/len(symbols):.1f}s")
        
        return results
    
    async def save_results(self, symbols: List[str], backtest_results: Dict[str, Any]):
        """Save results in requested formats."""
        self._log_progress(3, 4, "Processing and saving results...")
        
        # Aggregate statistics
        aggregated_stats = self.stats_aggregator.aggregate_results(backtest_results)
        
        # Add metadata
        aggregated_stats['metadata'] = {
            'pipeline_run_date': datetime.now().isoformat(),
            'total_symbols_screened': len(symbols),
            'total_backtests_run': len(backtest_results),
            'config_file': str(self.config_path),
            'total_runtime_seconds': time.time() - self.start_time
        }
        
        # Output results
        output_config = self.config['output']
        output_dir = Path(output_config['directory'])
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        saved_files = []
        
        if 'json' in output_config['formats']:
            json_path = output_dir / f"pipeline_results_{timestamp}.json"
            self.stats_aggregator.save_json(aggregated_stats, json_path)
            saved_files.append(str(json_path))
        
        if 'csv' in output_config['formats']:
            csv_path = output_dir / f"pipeline_results_{timestamp}.csv"
            self.stats_aggregator.save_csv(aggregated_stats, csv_path)
            saved_files.append(str(csv_path))
        
        if 'html' in output_config['formats']:
            html_path = output_dir / f"pipeline_results_{timestamp}.html"
            self.stats_aggregator.save_html(aggregated_stats, html_path)
            saved_files.append(str(html_path))
        
        logger.info(f"    ✓ Results saved to:")
        for file in saved_files:
            logger.info(f"      - {file}")
        
        # Print summary if requested
        if output_config['print_to_console']:
            self._print_summary(aggregated_stats)
    
    def _print_summary(self, stats: Dict[str, Any]):
        """Print a concise summary of results."""
        print("\n" + "="*60)
        print("PIPELINE SUMMARY")
        print("="*60)
        
        if 'summary' in stats:
            summary = stats['summary']
            print(f"Total Backtests: {summary.get('total_backtests', 0)}")
            print(f"Successful: {summary.get('successful_backtests', 0)}")
            print(f"Failed: {summary.get('failed_backtests', 0)}")
            
            if 'average_return' in summary:
                print(f"\nAverage Return: {summary['average_return']:.2%}")
            if 'best_performer' in summary:
                print(f"Best Performer: {summary['best_performer']['symbol']} ({summary['best_performer']['return']:.2%})")
            if 'worst_performer' in summary:
                print(f"Worst Performer: {summary['worst_performer']['symbol']} ({summary['worst_performer']['return']:.2%})")
        
        print(f"\nTotal Runtime: {stats['metadata']['total_runtime_seconds']:.1f}s")
        print("="*60)
    
    async def cleanup(self):
        """Cleanup resources."""
        self._log_progress(4, 4, "Cleaning up...")
        
        # Close API client session
        if self.api_client.session:
            await self.api_client.close()
        
        logger.info("    ✓ Cleanup completed")
    
    async def run(self):
        """Run the complete pipeline."""
        try:
            # Print header
            print("\n" + "="*60)
            print("OPTIMIZED SCREENER-BACKTEST PIPELINE")
            print("="*60)
            print(f"Config: {self.config_path}")
            print(f"Screening: {self.config['screening']['date_range']['start']} to {self.config['screening']['date_range']['end']}")
            print(f"Strategy: {self.config['backtesting']['strategy']}")
            print(f"Parallel: {self.config['execution']['parallel_backtests']} backtests")
            print("="*60 + "\n")
            
            # Step 1: Screen stocks
            symbols = await self.run_screener()
            
            if not symbols:
                logger.warning("No symbols found by screener. Exiting.")
                return
            
            # Step 2: Run backtests
            backtest_results = await self.run_backtests(symbols)
            
            # Step 3: Save results
            await self.save_results(symbols, backtest_results)
            
            # Step 4: Cleanup
            await self.cleanup()
            
            # Final summary
            total_time = time.time() - self.start_time
            print(f"\n✓ Pipeline completed successfully in {total_time:.1f}s")
            
        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)
            raise
        finally:
            # Ensure cleanup happens
            if self.api_client.session:
                await self.api_client.close()


async def main():
    """Main entry point."""
    # Check if custom config path provided
    config_path = sys.argv[1] if len(sys.argv) > 1 else "pipeline_config.yaml"
    
    # Create and run pipeline
    pipeline = OptimizedPipeline(config_path)
    await pipeline.run()


if __name__ == "__main__":
    asyncio.run(main())